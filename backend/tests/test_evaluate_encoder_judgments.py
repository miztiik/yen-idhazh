"""Real generated pairs and vectors exercise the offline evaluation without a model."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from idhazh.contracts.encoder_evaluation import (
    EncoderEvaluation,
    EvaluationSettings,
    VectorSource,
)
from idhazh.contracts.encoder_judgment import EncoderJudgment, JudgmentFrame, PairVerdict
from idhazh.contracts.encoder_reading import EncoderReading, ReadingState
from utilities.encoder_judgment_audit import audit_pairs, split_components
from utilities.encoder_judgment_metrics import (
    calibrate_threshold,
    operating_point,
    paired_bootstrap,
    ranking_metrics,
)
from utilities.evaluate_encoder_judgments import evaluate, file_hash, save_report, score_vectors
from utilities.record_encoder_judgments import append_decisions, read_frame, read_judgments


def settings(expected: int = 24, **updates: int | float | str) -> EvaluationSettings:
    return EvaluationSettings.model_validate({
        "expected_judgments": expected, "calibration_fraction": 0.3,
        "split_seed": 20261009, "precision_target": 0.95,
        "bootstrap_rounds": 100, "bootstrap_seed": 20261010,
        "interval_level": 0.95, "minimum_valid_draws": 20, "reference": "gte-small",
        **updates,
    })


def frame_fixture(root: Path, verdicts: list[str]) -> tuple[JudgmentFrame, list[EncoderJudgment]]:
    directory = root / "judgments"
    directory.mkdir(parents=True)
    rows = []
    for index in range(len(verdicts)):
        articles = [
            {"title": "A title used only for sampling", "summary": f"Summary {index} {side}.",
             "outlet": "example.org", "day": "2026-09-01",
             "url": f"https://example.org/{index}-{side}"}
            for side in ("a", "b")
        ]
        rows.append({"id": f"p{index + 1:04d}", "group": "encoders_differ",
                     "verdict": "", "note": "", "a": articles[0], "b": articles[1]})
    frame = JudgmentFrame.model_validate({
        "version": "2026-10-09", "pairs_to_read": len(rows), "repeated": 0,
        "groups": {}, "taken": {}, "verdicts_allowed": list(PairVerdict), "rows": rows,
    })
    return write_judgments(root, frame, verdicts)


def write_judgments(
    root: Path, frame: JudgmentFrame, verdicts: list[str],
) -> tuple[JudgmentFrame, list[EncoderJudgment]]:
    path = root / "judgments" / "pairs.json"
    path.write_text(frame.model_dump_json() + "\n", encoding="utf-8", newline="\n")
    decisions = root / "batch.json"
    decisions.write_text(json.dumps({
        pair.id: {"verdict": verdict, "note": "Generated test event identity."}
        for pair, verdict in zip(frame.rows, verdicts, strict=True)
    }), encoding="utf-8", newline="\n")
    output = root / "judgments" / "verdicts.jsonl"
    if output.exists():
        output.unlink()
    append_decisions(path, output, decisions, "fixture-model", "model")
    loaded, digest = read_frame(path)
    return loaded, read_judgments(output, loaded, digest)


def encoded_articles(frame: JudgmentFrame) -> tuple[list[str], list[str]]:
    articles = {article.url: article.summary for pair in frame.rows for article in (pair.a, pair.b)}
    return list(articles), list(articles.values())


def test_audit_reports_reversed_agreements_conflicts_uncertainty_and_text_coverage(tmp_path: Path) -> None:
    verdicts = ["same", "different", "cannot_tell", "same", "different", "same", "different"]
    frame, _ = frame_fixture(tmp_path, verdicts)
    reverse = frame.rows[0].model_copy(update={
        "id": "p0008", "a": frame.rows[0].b, "b": frame.rows[0].a, "group": "repeat",
    })
    conflict = frame.rows[1].model_copy(update={"id": "p0009", "group": "repeat"})
    frame = frame.model_copy(update={
        "rows": [*frame.rows, reverse, conflict], "pairs_to_read": 9, "repeated": 2,
    })
    frame, records = write_judgments(tmp_path, frame, [*verdicts, "same", "same"])
    urls, texts = encoded_articles(frame)
    texts[urls.index(frame.rows[4].a.url)] += " changed"
    texts[urls.index(frame.rows[5].a.url)] += " changed"
    for index in (5, 3):
        slot = urls.index(frame.rows[index].b.url)
        del urls[slot]
        del texts[slot]
    audit, eligible = audit_pairs(frame, records, urls, texts, 9)
    assert audit.unique_pairs == 7 and audit.repeated_rows == 2
    assert [repeat.agreement for repeat in audit.repeats] == [True, False]
    assert audit.repeats[0].pair_ids == ["p0001", "p0008"]
    assert audit.repeats[0].reversed_ids == ["p0008"]
    assert audit.repeats[1].verdicts == {"p0002": "different", "p0009": "same"}
    assert audit.missing_vector_ids == ["p0004", "p0006"]
    assert audit.changed_summary_ids == ["p0005", "p0006"]
    assert audit.cannot_tell_ids == ["p0003"]
    assert audit.url_covered_rows == 7 and audit.exact_text_covered_rows == 6
    assert audit.excluded_unique_ids == {
        "conflicting_repeat": ["p0002"], "cannot_tell": ["p0003"],
        "missing_vector": ["p0004", "p0006"], "changed_summary": ["p0005"],
    }
    assert audit.removed_duplicate_ids == ["p0008"]
    assert [item.pair.id for item in eligible] == ["p0001", "p0007"]
    assert eligible[0].aliases == ("p0001", "p0008")


def test_unknown_incomplete_duplicate_and_human_records_fail_explicitly(tmp_path: Path) -> None:
    frame, records = frame_fixture(tmp_path, ["same", "different"])
    urls, texts = encoded_articles(frame)
    for changed_records, message in (
        (records[:-1], "coverage differs"),
        ([*records[:-1], records[-1].model_copy(update={"pair_id": "p9999"})], "unknown"),
        ([*records, records[0]], "one initial judgment"),
        ([records[0].model_copy(update={"label_source": "human", "human_verdict": "same"}),
          records[1]], "zero human review"),
    ):
        with pytest.raises(ValueError, match=message):
            audit_pairs(frame, changed_records, urls, texts, 2)
    with pytest.raises(ValueError, match="expected 3"):
        audit_pairs(frame, records, urls, texts, 3)
    with pytest.raises(ValueError, match="must be unique"):
        audit_pairs(frame, records, [*urls, urls[0]], [*texts, texts[0]], 2)
    with pytest.raises(ValueError, match="no eligible"):
        audit_pairs(frame, records, [], [], 2)


def test_component_split_is_deterministic_and_keeps_excluded_links_and_repeats_together(tmp_path: Path) -> None:
    verdicts = ["same", "different"] * 12
    frame, _ = frame_fixture(tmp_path, verdicts)
    reverse = frame.rows[0].model_copy(update={
        "id": "p0025", "a": frame.rows[0].b, "b": frame.rows[0].a,
    })
    # The unscored link must still keep the two otherwise disjoint eligible pairs together.
    excluded = frame.rows[0].model_copy(update={
        "id": "p0026", "a": frame.rows[0].b, "b": frame.rows[1].a,
    })
    frame = frame.model_copy(update={
        "rows": [*frame.rows, reverse, excluded], "pairs_to_read": 26,
    })
    frame, records = write_judgments(tmp_path, frame, [*verdicts, "same", "cannot_tell"])
    urls, texts = encoded_articles(frame)
    _, eligible = audit_pairs(frame, records, urls, texts, 26)
    split, groups = split_components(frame, eligible, 0.3, 20261009)
    again, again_groups = split_components(frame, eligible, 0.3, 20261009)
    assert split == again and groups == again_groups
    assert groups[0] == groups[1]
    assert eligible[0].aliases == ("p0001", "p0025")
    calibration = set(split.calibration.pair_ids)
    held_out = set(split.held_out.pair_ids)
    cal_urls = {
        article.url for item in eligible if item.pair.id in calibration
        for article in (item.pair.a, item.pair.b)
    }
    held_urls = {
        article.url for item in eligible if item.pair.id in held_out
        for article in (item.pair.a, item.pair.b)
    }
    assert not cal_urls & held_urls
    assert split.shared_articles == 0
    assert ("p0001" in calibration) == ("p0002" in calibration)


def test_split_blockers_do_not_retry_or_call_full_data_held_out(tmp_path: Path) -> None:
    frame, records = frame_fixture(tmp_path, ["same", "different"])
    urls, texts = encoded_articles(frame)
    _, eligible = audit_pairs(frame, records, urls, texts, 2)
    with pytest.raises(ValueError, match=r"class coverage blocked.*no split retries"):
        split_components(frame, eligible, 0.3, 1)
    with pytest.raises(ValueError, match="1 active components"):
        split_components(frame.model_copy(update={"rows": frame.rows[:1]}), eligible[:1], 0.3, 1)


def test_calibration_cannot_cut_inside_a_tied_score_block() -> None:
    labels = np.asarray([1, 0, 1, 0], dtype=np.int64)
    scores = np.asarray([0.9, 0.9, 0.8, 0.7], dtype=np.float64)
    point = calibrate_threshold(labels, scores, 0.95)
    assert point.threshold is None and point.precision is None and point.tp is None
    assert point.reason == "calibration precision target unattainable"
    scores = np.asarray([0.95, 0.9, 0.9, 0.7], dtype=np.float64)
    strict = calibrate_threshold(labels, scores, 0.95)
    assert strict.threshold == 0.95 and strict.precision == 1 and strict.recall == 0.5
    complete = calibrate_threshold(labels, scores, 2 / 3)
    assert complete.threshold == 0.9 and complete.tp == 2 and complete.fp == 1
    assert complete.recall == 1
    held = operating_point(labels, scores, 1.0)
    assert held.precision is None and held.recall == 0 and held.reason is not None
    assert (held.tp, held.fp, held.fn, held.tn) == (0, 0, 2, 2)
    with pytest.raises(ValueError, match="both binary classes"):
        ranking_metrics(np.ones(4, dtype=np.int64), scores)
    with pytest.raises(ValueError, match="finite"):
        ranking_metrics(labels, np.asarray([0.9, np.nan, 0.8, 0.7]))


def test_bootstrap_is_paired_deterministic_and_counts_one_class_draws() -> None:
    labels = np.asarray([1, 0], dtype=np.int64)
    scores = np.asarray([0.7, 0.4], dtype=np.float64)
    config = settings(2)
    scored = {"gte-small": scores, "candidate": scores.copy()}
    actual = paired_bootstrap(labels, scored, ["positive", "negative"], config)
    repeated = paired_bootstrap(labels, dict(reversed(list(scored.items()))),
                                ["positive", "negative"], config)
    assert actual == repeated
    audit, aps, differences = actual
    assert 0 < audit.one_class_draws < config.bootstrap_rounds
    assert audit.valid_draws + audit.one_class_draws == config.bootstrap_rounds
    assert differences["candidate"].lower == differences["candidate"].upper == 0
    assert aps["candidate"] == aps["gte-small"]
    insufficient, intervals, _ = paired_bootstrap(
        labels, scored, ["positive", "negative"], settings(2, bootstrap_rounds=1),
    )
    assert insufficient.valid_draws <= 1
    assert intervals["candidate"].lower is None and intervals["candidate"].reason is not None
    with pytest.raises(ValueError, match="1 held-out components"):
        paired_bootstrap(labels, scored, ["one", "one"], config)


def evaluation_fixture(root: Path) -> tuple[list[VectorSource], EvaluationSettings]:
    frame, _ = frame_fixture(root, ["same", "different"] * 12)
    urls, texts = encoded_articles(frame)
    encoded_path = root / "pairs.json"
    encoded_path.write_text(json.dumps({"urls": urls, "texts": texts}), encoding="utf-8", newline="\n")
    readings = []
    sources = []
    for number, slug in enumerate(("gte-small", "minilm-l6", "jina-v5-nano", "embeddinggemma-two")):
        source = VectorSource(slug=slug, file=f"{slug}.npy", run_id="123", artifact=f"vectors-{slug}")
        sources.append(source)
        vectors = np.random.default_rng(number).normal(size=(len(urls), 4))
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        np.save(root / source.file, vectors)
        readings.append(EncoderReading(
            slug=slug, model_id=f"fixture/{slug}", parameters_millions=1, why="generated vectors",
            state=ReadingState.MEASURED, pair_set_sha256=file_hash(encoded_path),
            written_at="2026-10-09T00:00:00Z", articles_to_encode=len(urls),
            articles_done=len(urls), numbers_an_article=4, separation=0.5,
        ).model_dump())
    (root / "readings").mkdir()
    (root / "readings" / "encoders.json").write_text(json.dumps({"encoders": readings}), encoding="utf-8")
    return sources, settings()


def test_real_four_vector_report_round_trip_and_provenance_validation(tmp_path: Path) -> None:
    sources, config = evaluation_fixture(tmp_path)
    original_labels = (tmp_path / "judgments" / "verdicts.jsonl").read_bytes()
    report = evaluate(
        tmp_path, tmp_path, sources, config,
        code_commit="a" * 40, labels_commit="b" * 40, source_hashes={},
    )
    assert report.labels.human_reviewed == 0
    assert report.labels.label_source == "model"
    assert report.labels.labeler_counts == {"fixture-model": 24}
    assert len(report.encoders) == 4
    for encoder in report.encoders:
        assert encoder.calibration.threshold == encoder.held_out_operating_point.threshold
        assert len(encoder.vector_sha256) == 64
    output = tmp_path / "judgments" / "evaluation.json"
    save_report(report, output)
    assert EncoderEvaluation.model_validate_json(output.read_bytes()) == report
    assert b"NaN" not in output.read_bytes() and b"\r" not in output.read_bytes()
    assert (tmp_path / "judgments" / "verdicts.jsonl").read_bytes() == original_labels
    raw = report.model_dump()
    raw["labels"]["human_reviewed"] = 1
    with pytest.raises(ValidationError):
        EncoderEvaluation.model_validate(raw)
    raw = report.model_dump()
    raw["encoders"][0]["held_out"]["average_precision"] = float("nan")
    with pytest.raises(ValidationError):
        EncoderEvaluation.model_validate(raw)
    raw = report.model_dump()
    raw["encoders"][0]["held_out_operating_point"]["threshold"] = 9.0
    with pytest.raises(ValidationError):
        EncoderEvaluation.model_validate(raw)


@pytest.mark.parametrize("fault", ["hash", "rows", "dimensions", "nan", "zero"])
def test_saved_vector_validation_fails_closed(tmp_path: Path, fault: str) -> None:
    sources, _ = evaluation_fixture(tmp_path)
    frame, digest = read_frame(tmp_path / "judgments" / "pairs.json")
    records = read_judgments(tmp_path / "judgments" / "verdicts.jsonl", frame, digest)
    urls, texts = encoded_articles(frame)
    _, eligible = audit_pairs(frame, records, urls, texts, 24)
    source = sources[0]
    reading = EncoderReading.model_validate(
        json.loads((tmp_path / "readings" / "encoders.json").read_bytes())["encoders"][0],
    )
    path = tmp_path / source.file
    vectors = np.load(path)
    if fault == "hash":
        reading = reading.model_copy(update={"pair_set_sha256": "0" * 64})
    elif fault == "rows":
        vectors = vectors[:-1]
    elif fault == "dimensions":
        vectors = vectors[:, :-1]
    elif fault == "nan":
        vectors[0, 0] = np.nan
    else:
        vectors[0, :] = 0
    np.save(path, vectors)
    with pytest.raises(ValueError):
        score_vectors(path, reading, file_hash(tmp_path / "pairs.json"), len(urls), eligible)
