"""Compare cached vectors on the complete judged frame without loading any encoder."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np
from pydantic import TypeAdapter

from idhazh.contracts.base import Url
from idhazh.contracts.encoder_evaluation import (
    EncoderEvaluation,
    EvaluatedEncoder,
    EvaluationSettings,
    LabelProvenance,
    VectorSource,
)
from idhazh.contracts.encoder_reading import EncoderReading, ReadingState
from utilities.compare_summary_encoders import read_config
from utilities.encoder_judgment_audit import EligiblePair, audit_pairs, split_components
from utilities.encoder_judgment_metrics import (
    FloatArray,
    calibrate_threshold,
    operating_point,
    paired_bootstrap,
    ranking_metrics,
)
from utilities.record_encoder_judgments import read_frame, read_judgments
from utilities.score_encoder_separation import read_pairs

# A fixed list of this instrument's own sources, not a scan over the repository.
CODE_FILES = (
    "backend/idhazh/contracts/base.py",
    "backend/idhazh/contracts/encoder_evaluation.py",
    "backend/idhazh/contracts/encoder_judgment.py",
    "backend/idhazh/contracts/encoder_reading.py",
    "backend/utilities/evaluate_encoder_judgments.py",
    "backend/utilities/encoder_judgment_audit.py",
    "backend/utilities/encoder_judgment_metrics.py",
    "backend/utilities/record_encoder_judgments.py",
    "backend/utilities/compare_summary_encoders.py",
    "backend/utilities/score_encoder_separation.py",
)
LIMITATIONS = [
    "All labels are model-written; zero human validation. No original author model was "
    "recorded for the first recovered judgments.",
    "The frame is a title/metadata-enriched selection, not a representative production "
    "population. It has no hard_match selection group.",
    "Judged rows are not necessarily unique or evaluable pairs. Coverage exclusions and "
    "conflicting repeat verdicts remain unadjudicated.",
    "Every link in the judged frame joins article components, including excluded pairs. "
    "Separate events without shared articles or known links can still cross the split.",
    "The precision target is calibration-only in this enriched sample, not a guarantee "
    "of held-out precision or deployed precision.",
    "The paired percentile bootstrap measures held-out component sampling uncertainty "
    "conditional on this fixed split, labels and thresholds; it does not measure label "
    "error, threshold-estimation uncertainty or multiple-comparison-adjusted significance.",
    "Whole-data AP is descriptive, not held-out evidence. No split or seed was retried.",
    "Saved costs came from separate GitHub 4-vCPU/16-GB/no-GPU runs, not controlled "
    "same-silicon trials. Single timings have no confidence estimate and do not show "
    "that parameter count caused speed.",
    "Jina merged weights contain about 212M parameters; 239M describes the advertised "
    "multi-adapter family. CC-BY-NC-4.0 is not commercial-adoption approval. "
    "Gemma is text-only 270M, Apache-2.0.",
    "Cosine is computed in float64 from saved finite, nonzero vectors. No encoder is "
    "loaded and no text is encoded. No production encoder choice changes.",
]


def file_hash(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def score_vectors(
    path: Path, reading: EncoderReading, input_hash: str,
    rows: int, pairs: list[EligiblePair],
) -> tuple[FloatArray, str]:
    if reading.state != ReadingState.MEASURED or reading.pair_set_sha256 != input_hash:
        raise ValueError(f"{reading.slug}: requires a measured reading with the exact input hash")
    if reading.articles_done != rows or reading.numbers_an_article is None:
        raise ValueError(f"{reading.slug}: reading does not cover the encoded input rows")
    saved = np.load(path, allow_pickle=False)
    if saved.shape != (rows, reading.numbers_an_article) or saved.dtype.kind != "f":
        raise ValueError(f"{reading.slug}: vector shape or floating dtype differs from its reading")
    vectors = np.asarray(saved, dtype=np.float64)
    if not np.isfinite(vectors).all():
        raise ValueError(f"{reading.slug}: vectors contain non-finite values")
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms == 0):
        raise ValueError(f"{reading.slug}: vectors contain zero-length rows")
    left = np.asarray([item.left for item in pairs], dtype=np.int64)
    right = np.asarray([item.right for item in pairs], dtype=np.int64)
    scores: FloatArray = (
        np.sum(vectors[left] * vectors[right], axis=1) / (norms[left] * norms[right])
    )
    return scores, str(saved.dtype)


def evaluate(
    corpus: Path,
    vector_root: Path,
    sources: list[VectorSource],
    settings: EvaluationSettings,
    *,
    code_commit: str,
    labels_commit: str,
    source_hashes: dict[str, str],
) -> EncoderEvaluation:
    """Audit and fix the split before opening vectors or inspecting any score."""
    frame_path = corpus / "judgments" / "pairs.json"
    judgment_path = corpus / "judgments" / "verdicts.jsonl"
    encoded_path = corpus / "pairs.json"
    reading_path = corpus / "readings" / "encoders.json"
    frame, frame_hash = read_frame(frame_path)
    judgments = read_judgments(judgment_path, frame, frame_hash)
    encoded = read_pairs(encoded_path)
    urls = TypeAdapter(list[Url]).validate_python(encoded["urls"], strict=True)
    texts = TypeAdapter(list[str]).validate_python(encoded["texts"], strict=True)
    coverage, eligible = audit_pairs(
        frame, judgments, urls, texts, settings.expected_judgments,
    )
    split, components = split_components(
        frame, eligible, settings.calibration_fraction, settings.split_seed,
    )
    calibration_ids = set(split.calibration.pair_ids)
    calibration_index = np.asarray([
        i for i, item in enumerate(eligible) if item.pair.id in calibration_ids
    ], dtype=np.int64)
    held_index = np.asarray([
        i for i, item in enumerate(eligible) if item.pair.id not in calibration_ids
    ], dtype=np.int64)
    labels = np.asarray([item.label for item in eligible], dtype=np.int64)
    readings = TypeAdapter(list[EncoderReading]).validate_python(
        json.loads(reading_path.read_bytes())["encoders"],
    )
    by_slug = {reading.slug: reading for reading in readings}
    if len(by_slug) != len(readings):
        raise ValueError("the saved readings contain duplicate encoder slugs")
    source_slugs = [source.slug for source in sources]
    if not sources or len(source_slugs) != len(set(source_slugs)):
        raise ValueError("vector sources must name distinct encoders")
    if settings.reference not in source_slugs:
        raise ValueError("the configured reference needs a vector source")
    unknown = set(source_slugs) - by_slug.keys()
    if unknown:
        raise ValueError(f"no saved reading for {sorted(unknown)}")
    input_hash = file_hash(encoded_path)
    scores: dict[str, FloatArray] = {}
    dtypes: dict[str, str] = {}
    vector_hashes: dict[str, str] = {}
    for source in sources:
        vector_path = vector_root / source.file
        scores[source.slug], dtypes[source.slug] = score_vectors(
            vector_path, by_slug[source.slug], input_hash, len(urls), eligible,
        )
        vector_hashes[source.slug] = file_hash(vector_path)
    held_scores = {slug: values[held_index] for slug, values in scores.items()}
    bootstrap, intervals, differences = paired_bootstrap(
        labels[held_index], held_scores, [components[int(i)] for i in held_index], settings,
    )
    reference = ranking_metrics(
        labels[held_index], held_scores[settings.reference],
    ).average_precision
    results = []
    for source in sources:
        values = scores[source.slug]
        calibration = calibrate_threshold(
            labels[calibration_index], values[calibration_index], settings.precision_target,
        )
        held_metrics = ranking_metrics(labels[held_index], values[held_index])
        results.append(EvaluatedEncoder(
            reading=by_slug[source.slug], vectors=source,
            vector_sha256=vector_hashes[source.slug], vector_dtype=dtypes[source.slug],
            calibration=calibration,
            held_out=held_metrics,
            held_out_operating_point=operating_point(
                labels[held_index], values[held_index], calibration.threshold, calibration.reason,
            ),
            held_out_ap_interval=intervals[source.slug],
            held_out_ap_minus_reference=held_metrics.average_precision - reference,
            held_out_ap_difference_interval=differences[source.slug],
            whole_data_descriptive=ranking_metrics(labels, values),
        ))
    return EncoderEvaluation(
        written_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        code_commit=code_commit,
        source_sha256={
            **source_hashes,
            "corpus/encoder-comparison-1/pairs.json": input_hash,
            "corpus/encoder-comparison-1/readings/encoders.json": file_hash(reading_path),
        },
        runtime_versions={
            "python": platform.python_version(),
            **{
                package: version(package)
                for package in ("numpy", "scipy", "scikit-learn", "pydantic")
            },
        },
        settings=settings,
        labels=LabelProvenance(
            history_rows=len(judgments),
            labeler_counts=dict(sorted(Counter(record.labeler for record in judgments).items())),
            label_source="model", human_reviewed=0,
            labels_commit=labels_commit, judgments_sha256=file_hash(judgment_path),
            frame_sha256=frame_hash,
        ),
        coverage=coverage, split=split, bootstrap=bootstrap, encoders=results,
        limitations=LIMITATIONS,
    )


def save_report(report: EncoderEvaluation, output: Path) -> None:
    validated = EncoderEvaluation.model_validate_json(report.model_dump_json())
    output.parent.mkdir(parents=True, exist_ok=True)
    beside = output.with_suffix(output.suffix + ".part")
    beside.write_text(validated.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    beside.replace(output)
    EncoderEvaluation.model_validate_json(output.read_bytes())


def git_text(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True,
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--vector-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    config_path = args.config.resolve()
    config_name = config_path.relative_to(root).as_posix()
    settings = read_config(config_path)
    evaluation = EvaluationSettings.model_validate(settings["judgment_evaluation"])
    sources = TypeAdapter(list[VectorSource]).validate_python(settings["judgment_vectors"])
    code_commit = git_text(root, "rev-parse", "HEAD")
    source_hashes = {}
    for name in (*CODE_FILES, config_name):
        path = root / name
        committed = subprocess.run(
            ["git", "-C", str(root), "show", f"{code_commit}:{name}"],
            check=True, capture_output=True,
        ).stdout
        if committed != path.read_bytes():
            raise ValueError(f"{name}: commit the instrument and config before recording a reading")
        source_hashes[name] = file_hash(path)
    labels_name = (
        args.corpus.resolve() / "judgments" / "verdicts.jsonl"
    ).relative_to(root).as_posix()
    labels_commit = git_text(root, "log", "-1", "--format=%H", "--", labels_name)
    label_bytes = subprocess.run(
        ["git", "-C", str(root), "show", f"{labels_commit}:{labels_name}"],
        check=True, capture_output=True,
    ).stdout
    if label_bytes != (root / labels_name).read_bytes():
        raise ValueError("judgments differ from their recorded label commit")
    report = evaluate(
        args.corpus, args.vector_root, sources, evaluation,
        code_commit=code_commit, labels_commit=labels_commit, source_hashes=source_hashes,
    )
    save_report(report, args.out)
    print(f"{len(report.coverage.judged_ids)} judged rows; "
          f"{len(report.coverage.eligible_ids)} eligible unique pairs; zero human review")
    for result in report.encoders:
        print(f"{result.reading.slug}: held-out AP {result.held_out.average_precision:.6f}; "
              f"AUC {result.held_out.area_under_curve:.6f}; "
              f"precision {result.held_out_operating_point.precision}; "
              f"recall {result.held_out_operating_point.recall}")


if __name__ == "__main__":
    main()
