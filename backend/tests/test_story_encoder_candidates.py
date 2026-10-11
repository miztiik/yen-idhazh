"""Exercise generated pinned provenance and numeric units without models, mocks or network."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import TypeAdapter
from test_story_dataset import answer, articles, manifest, policy, seeded_store

from idhazh.contracts.encoder_reading import EncoderReading, ReadingState
from idhazh.contracts.story_candidate_evaluation import CandidateEvaluationSnapshot
from idhazh.contracts.story_candidates import VectorCache
from idhazh.contracts.story_encoder_candidate import CandidateVectorUnit, PinnedEncoderCandidate
from idhazh.contracts.story_evaluation import DevelopmentConfig, RetrievalRun
from idhazh.contracts.story_source import SourceCheck
from idhazh.contracts.story_vector_derivation import DerivedVectorSnapshot
from idhazh.contracts.story_vectors import VectorSnapshot
from idhazh.story_dataset.candidate_evaluation import materialize_candidate
from idhazh.story_dataset.encoder_candidates import (
    register_candidate_unit,
    register_pinned_candidate,
)
from idhazh.story_dataset.evaluation import evaluate
from idhazh.story_dataset.partitions import build_partition
from idhazh.story_dataset.pinned_encoding import encode_pinned_selected
from idhazh.story_dataset.predictions import freeze_development, predict
from idhazh.story_dataset.storage import canonical, digest, file_hash, now, write_model
from idhazh.story_dataset.vectors import covered_ids, model_matrix, validate_vectors
from idhazh.story_dataset.workers import export_batch, import_submission

pytestmark = pytest.mark.contract
PIN = "f" * 40


def registered_candidate(root: Path) -> tuple[PinnedEncoderCandidate, VectorSnapshot]:
    rows = list(articles())[:2]
    reading = EncoderReading(
        slug="fixture-control",
        model_id="fixture/model",
        parameters_millions=0,
        why="Generated fixture only; no actual model provenance claim.",
        written_at=now(),
        state=ReadingState.MEASURED,
        articles_to_encode=2,
        articles_done=2,
        numbers_an_article=2,
        separation=0.5,
    )
    (root / "reading.json").write_text(
        json.dumps({"encoders": [reading.model_dump(mode="json")]}), encoding="utf-8"
    )
    (root / "input.json").write_text("{}", encoding="utf-8")
    (root / "config.json").write_text("{}", encoding="utf-8")
    np.save(root / "old.npy", np.eye(2, dtype=np.float32))
    legacy = VectorSnapshot(
        path_base="dataset-root",
        source_sha256=manifest().source_sha256,
        input_sha256=file_hash(root / "input.json"),
        input_file="input.json",
        readings_file="reading.json",
        readings_sha256=file_hash(root / "reading.json"),
        encoder_config_file="config.json",
        encoder_config_sha256=file_hash(root / "config.json"),
        max_sequence_length=256,
        article_ids=rows,
        text_sha256=[digest(i) for i in rows],
        missing_article_ids=sorted(set(articles()) - set(rows)),
        caches=[
            VectorCache(
                slug=reading.slug,
                model_id=reading.model_id,
                revision=None,
                file="old.npy",
                file_sha256=file_hash(root / "old.npy"),
                rows=2,
                dimensions=2,
                reading_sha256=digest(reading),
                input_sha256=file_hash(root / "input.json"),
                settings_sha256=digest({"prefix": "", "model_options": {}, "encode_options": {}}),
            )
        ],
    )
    metadata = root / "metadata.json"
    metadata.write_text(json.dumps({"id": reading.model_id, "sha": PIN}), encoding="utf-8")
    check = SourceCheck(
        url=f"https://huggingface.co/api/models/{reading.model_id}/revision/{PIN}?expand[]=sha",
        checked_at=now(),
        state="read",
        finding="Generated offline metadata fixture.",
        evidence_sha256=file_hash(metadata),
    )
    return register_pinned_candidate(legacy, root, reading.slug, PIN, metadata, check, root), legacy


def generated_unit(
    root: Path, candidate: PinnedEncoderCandidate, ids: list[str]
) -> CandidateVectorUnit:
    path = root / "generated.npy"
    np.save(path, np.ones((len(ids), candidate.dimensions), dtype=np.float32))
    evidence = articles()
    return CandidateVectorUnit(
        path_base="dataset-root",
        candidate_revision=digest(candidate),
        encoded_at=now(),
        source_sha256=candidate.source_sha256,
        slug=candidate.slug,
        article_ids=ids,
        article_input_sha256=[evidence[i].input_sha256 for i in ids],
        summary_sha256=[
            hashlib.sha256(evidence[i].source.summary.encode()).hexdigest() for i in ids
        ],
        runtime_versions={"fixture": "generated-not-a-real-encoder-run"},
        cache=VectorCache(
            slug=candidate.slug,
            model_id=candidate.model_id,
            revision=PIN,
            file=path.name,
            file_sha256=file_hash(path),
            rows=len(ids),
            dimensions=candidate.dimensions,
            reading_sha256=digest(candidate),
            input_sha256=digest([candidate.prefix + evidence[i].source.summary for i in ids]),
            settings_sha256=digest(
                {
                    "prefix": candidate.prefix,
                    "model_options": candidate.model_options,
                    "encode_options": candidate.encode_options,
                }
            ),
        ),
    )


def test_new_pin_preserves_unknown_legacy_and_has_no_borrowed_coverage(tmp_path: Path) -> None:
    candidate, legacy = registered_candidate(tmp_path)
    before = canonical(legacy)
    assert candidate.legacy_model_revision is None
    assert candidate.legacy_vector_revision == digest(legacy)
    assert candidate.slug != legacy.caches[0].slug
    assert not candidate.legacy_vectors_reusable
    ids = list(articles())[2:4]
    unit = generated_unit(tmp_path, candidate, ids)
    state = register_candidate_unit(tmp_path, candidate, articles(), unit)
    assert {i for row in state.units for i in row.article_ids} == set(ids)
    assert not set(legacy.article_ids) & set(ids)
    assert register_candidate_unit(tmp_path, candidate, articles(), unit, state) == state
    assert canonical(legacy) == before and legacy.caches[0].revision is None
    assert np.load(tmp_path / "old.npy").dtype == np.float32
    with pytest.raises(ValueError, match="duplicates"):
        register_candidate_unit(
            tmp_path,
            candidate,
            articles(),
            unit.model_copy(update={"encoded_at": "2026-10-11T00:00:00Z"}),
            state,
        )


@pytest.mark.parametrize("bad", ["revision", "legacy-reading", "input", "float64"])
def test_candidate_import_refuses_mixed_provenance_inputs_and_dtype(
    tmp_path: Path, bad: str
) -> None:
    candidate, legacy = registered_candidate(tmp_path)
    unit = generated_unit(tmp_path, candidate, list(articles())[:2])
    if bad == "revision":
        unit.cache.revision = None
    elif bad == "legacy-reading":
        unit.cache.reading_sha256 = legacy.caches[0].reading_sha256
    elif bad == "input":
        unit.article_input_sha256[0] = "0" * 64
    else:
        np.save(tmp_path / "generated.npy", np.ones((2, 2), dtype=np.float64))
        unit.cache.file_sha256 = file_hash(tmp_path / "generated.npy")
    with pytest.raises(ValueError):
        register_candidate_unit(tmp_path, candidate, articles(), unit)
    assert not (tmp_path / "candidate-vector-states").exists()


def test_candidate_encoding_resumes_exact_registered_unit_without_model_load(
    tmp_path: Path,
) -> None:
    candidate, _ = registered_candidate(tmp_path)
    ids = list(articles())[:2]
    unit = generated_unit(tmp_path, candidate, ids)
    write_model(tmp_path / "generated.json", unit)
    assert (
        encode_pinned_selected(
            candidate, articles(), ids, policy(), tmp_path, tmp_path / "generated.npy"
        )
        == unit
    )
    with pytest.raises(ValueError, match="order"):
        encode_pinned_selected(
            candidate,
            articles(),
            list(reversed(ids)),
            policy(),
            tmp_path,
            tmp_path / "generated.npy",
        )


def test_fresh_encoding_refuses_an_unregistered_candidate_before_model_loading(tmp_path: Path) -> None:
    candidate, _ = registered_candidate(tmp_path)
    tampered = candidate.model_copy(update={"prefix": "unapproved replacement"})
    with pytest.raises(ValueError, match="not registered"):
        encode_pinned_selected(
            tampered, articles(), list(articles())[:2], policy(), tmp_path, tmp_path / "fresh.npy"
        )
    assert not (tmp_path / "fresh.npy").exists()


def test_candidate_state_snapshots_arrays_and_rechecks_retained_bytes(tmp_path: Path) -> None:
    candidate, _ = registered_candidate(tmp_path)
    first = generated_unit(tmp_path, candidate, list(articles())[:2])
    state = register_candidate_unit(tmp_path, candidate, articles(), first)
    held = state.units[0]
    assert held.cache.file.startswith("vector-evidence/")
    second = generated_unit(tmp_path, candidate, list(articles())[2:4])
    original = tmp_path / held.cache.file
    np.save(original, np.zeros((2, 2), dtype=np.float32))
    with pytest.raises(ValueError, match="bytes"):
        register_candidate_unit(tmp_path, candidate, articles(), second, state)


def test_materialized_candidate_uses_only_saved_units_and_preserves_unknown_legacy(
    tmp_path: Path,
) -> None:
    candidate, legacy = registered_candidate(tmp_path)
    before = canonical(legacy)
    old_array = (tmp_path / "old.npy").read_bytes()
    ids = list(articles())[2:6]
    first = generated_unit(tmp_path, candidate, ids[:2])
    state = register_candidate_unit(tmp_path, candidate, articles(), first)
    second = generated_unit(tmp_path, candidate, ids[2:])
    state = register_candidate_unit(tmp_path, candidate, articles(), second, state)
    state_before = canonical(state)
    output = tmp_path / "evaluation"
    snapshot = materialize_candidate(candidate, state, articles(), tmp_path, output)
    validate_vectors(snapshot, output)
    actual_ids, matrix = model_matrix(snapshot, candidate.slug, output)
    assert actual_ids == ids and covered_ids(snapshot, candidate.slug) == set(ids)
    assert snapshot.candidate_state_sha256 == digest(state)
    assert snapshot.ordered_ids_sha256 == digest(ids)
    assert snapshot.native_files_sha256 == [unit.cache.file_sha256 for unit in state.units]
    assert snapshot.unit_sha256 == [digest(unit) for unit in state.units]
    assert set(snapshot.missing_article_ids) == set(articles()) - set(ids)
    assert snapshot.inference is False
    np.testing.assert_array_equal(matrix, np.ones((4, candidate.dimensions)))
    assert canonical(state) == state_before and canonical(legacy) == before
    assert (tmp_path / "old.npy").read_bytes() == old_array
    assert legacy.caches[0].revision is None
    assert materialize_candidate(candidate, state, articles(), tmp_path, output) == snapshot


@pytest.mark.parametrize("bad", ["state", "array", "snapshot-order", "snapshot-pin", "output"])
def test_materialized_candidate_refuses_tampered_lineage(tmp_path: Path, bad: str) -> None:
    candidate, _ = registered_candidate(tmp_path)
    unit = generated_unit(tmp_path, candidate, list(articles())[:3])
    state = register_candidate_unit(tmp_path, candidate, articles(), unit)
    output = tmp_path / "evaluation"
    snapshot = materialize_candidate(candidate, state, articles(), tmp_path, output)
    if bad == "state":
        state.candidate_revision = "0" * 64
        with pytest.raises(ValueError, match="lineage"):
            materialize_candidate(candidate, state, articles(), tmp_path, output)
    elif bad == "array":
        np.save(tmp_path / state.units[0].cache.file, np.zeros((3, 2), dtype=np.float32))
        with pytest.raises(ValueError, match="bytes"):
            materialize_candidate(candidate, state, articles(), tmp_path, output)
    elif bad == "output":
        (output / snapshot.caches[0].file).write_bytes(b"corrupt")
        with pytest.raises(ValueError, match="immutable"):
            materialize_candidate(candidate, state, articles(), tmp_path, output)
    else:
        if bad == "snapshot-order":
            snapshot.article_ids.reverse()
        else:
            snapshot.caches[0].revision = None
        with pytest.raises(ValueError):
            validate_vectors(snapshot, output)


def test_materialized_candidate_requires_separate_output_root(tmp_path: Path) -> None:
    candidate, _ = registered_candidate(tmp_path)
    unit = generated_unit(tmp_path, candidate, list(articles())[:3])
    state = register_candidate_unit(tmp_path, candidate, articles(), unit)
    with pytest.raises(ValueError, match="separate"):
        materialize_candidate(candidate, state, articles(), tmp_path, tmp_path)


@pytest.mark.parametrize("bad", ["native-bytes", "aggregate-bytes", "official-metadata"])
def test_materialized_candidate_replays_retained_numeric_lineage(
    tmp_path: Path, bad: str,
) -> None:
    candidate, _ = registered_candidate(tmp_path)
    ids = list(articles())[:3]
    state = register_candidate_unit(
        tmp_path, candidate, articles(), generated_unit(tmp_path, candidate, ids[:2])
    )
    state = register_candidate_unit(
        tmp_path, candidate, articles(), generated_unit(tmp_path, candidate, ids[2:]), state
    )
    output = tmp_path / "evaluation"
    snapshot = materialize_candidate(candidate, state, articles(), tmp_path, output)
    if bad == "native-bytes":
        np.save(output / state.units[0].cache.file, np.zeros((2, 2), dtype=np.float32))
    elif bad == "aggregate-bytes":
        np.save(output / snapshot.caches[0].file, np.full((3, 2), 2, dtype=np.float32))
        snapshot.caches[0].file_sha256 = file_hash(output / snapshot.caches[0].file)
    else:
        (output / candidate.official_metadata_file).write_bytes(b"changed")
    with pytest.raises(ValueError, match=r"native|metadata"):
        validate_vectors(snapshot, output)


def test_candidate_snapshot_roundtrip_and_frozen_confirmation(tmp_path: Path) -> None:
    candidate, _ = registered_candidate(tmp_path)
    state = register_candidate_unit(
        tmp_path, candidate, articles(), generated_unit(tmp_path, candidate, list(articles()))
    )
    output = tmp_path / "evaluation"
    snapshot = materialize_candidate(candidate, state, articles(), tmp_path, output)
    adapter: TypeAdapter[
        CandidateEvaluationSnapshot | DerivedVectorSnapshot | VectorSnapshot
    ] = TypeAdapter(
        CandidateEvaluationSnapshot | DerivedVectorSnapshot | VectorSnapshot
    )
    restored = adapter.validate_json(canonical(snapshot))
    assert isinstance(restored, CandidateEvaluationSnapshot) and restored == snapshot
    moved = tmp_path / "moved"
    output.rename(moved)
    validate_vectors(restored, moved)
    store = seeded_store(moved)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        partition = build_partition(store, manifest(), set(articles()), policy(), set())
        universe = [i for i, p in partition.article_partitions.items() if p == "confirmation"]
        config = DevelopmentConfig(
            source_sha256=manifest().source_sha256,
            partition_sha256=digest(partition),
            frozen_at=now(), parameters={}, reason="Generated offline wiring fixture.",
        )
        freeze_development(store, config, partition)
        with pytest.raises(ValueError, match="selected in development"):
            predict(store, partition, restored, config, universe, candidate.slug,
                    "confirmation", "story", 1)
        assert store.setting("confirmation-opened") is None
        selected = config.model_copy(update={
            "parameters": {"vector_candidates": {candidate.slug: digest(restored)}}
        })
        freeze_development(store, selected, partition)
        result = predict(store, partition, restored, selected, universe, candidate.slug,
                         "confirmation", "story", 1)
        assert isinstance(result, RetrievalRun)
        report = evaluate(store, manifest(), partition, restored, None, retrieval=result)
        assert any("qrels" in reason for reason in report.blockers)
        assert not any("vector candidate" in reason for reason in report.blockers)
        assert store.setting("confirmation-opened") == digest(selected)
    finally:
        store.close()
