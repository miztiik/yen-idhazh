"""Validate native Gemma arithmetic lineage and development selection with bounded real fixtures."""

import json
from pathlib import Path
from typing import Literal

import numpy as np
import pytest
from test_story_dataset import (
    answer,
    articles,
    manifest,
    policy,
    seeded_store,
)
from test_story_encoder_candidates import registered_candidate

from idhazh.contracts.encoder_reading import EncoderReading
from idhazh.contracts.story_candidates import VectorCache
from idhazh.contracts.story_evaluation import DevelopmentConfig, RetrievalRun
from idhazh.contracts.story_vectors import VectorExtensionSnapshot, VectorSnapshot
from idhazh.story_dataset.evaluation import evaluate
from idhazh.story_dataset.partitions import build_partition
from idhazh.story_dataset.predictions import freeze_development, predict
from idhazh.story_dataset.storage import canonical, digest, file_hash, now
from idhazh.story_dataset.vector_derivation import derive_gemma
from idhazh.story_dataset.vectors import model_matrix, register_extension
from idhazh.story_dataset.workers import export_batch, import_submission

pytestmark = pytest.mark.contract


def native_fixture(root: Path) -> VectorSnapshot:
    _, vectors = registered_candidate(root)
    reading = EncoderReading.model_validate(
        json.loads((root / "reading.json").read_text())["encoders"][0]
    )
    reading.model_id = "google/embeddinggemma-2"
    reading.slug = "embeddinggemma-two"
    reading.prefix = "task: sentence similarity | query: "
    reading.model_options = {"revision": "a" * 40}
    reading.encode_options = {"prompt": ""}
    reading.numbers_an_article = 768
    (root / "reading.json").write_text(json.dumps({"encoders": [reading.model_dump(mode="json")]}))
    ids = list(articles())
    matrix = np.random.default_rng(1).normal(size=(len(ids), 768)).astype(np.float32)
    np.save(root / "old.npy", matrix)
    cache = vectors.caches[0].model_copy(
        update={
            "slug": reading.slug,
            "model_id": reading.model_id,
            "revision": "a" * 40,
            "dimensions": 768,
            "rows": len(ids),
            "file_sha256": file_hash(root / "old.npy"),
            "reading_sha256": digest(reading),
            "settings_sha256": digest(
                {
                    "prefix": reading.prefix,
                    "model_options": reading.model_options,
                    "encode_options": reading.encode_options,
                }
            ),
        }
    )
    return vectors.model_copy(
        update={
            "article_ids": ids,
            "text_sha256": [digest(i) for i in ids],
            "missing_article_ids": [],
            "caches": [cache],
            "readings_sha256": file_hash(root / "reading.json"),
        }
    )


@pytest.mark.parametrize("dimensions", [128, 256, 512])
def test_derived_prefix_l2_lineage_preserves_native_bytes(
    tmp_path: Path, dimensions: Literal[128, 256, 512]
) -> None:
    native = native_fixture(tmp_path)
    matrix = np.zeros((len(native.article_ids), 768), dtype=np.float32)
    matrix[:, [0, 127, 128, 256, 767]] = [3, 4, 12, 84, 1000]
    matrix[1, [0, 127, 128, 256, 767]] = [5, 12, 84, 132, -2000]
    np.save(tmp_path / "old.npy", matrix)
    native.caches[0].file_sha256 = file_hash(tmp_path / "old.npy")
    # Prefix lengths are 5/13/85 and 13/85/157; the final column is excluded.
    columns, first, second = {
        128: ([0, 127], [3 / 5, 4 / 5], [5 / 13, 12 / 13]),
        256: ([0, 127, 128], [3 / 13, 4 / 13, 12 / 13], [5 / 85, 12 / 85, 84 / 85]),
        512: (
            [0, 127, 128, 256],
            [3 / 85, 4 / 85, 12 / 85, 84 / 85],
            [5 / 157, 12 / 157, 84 / 157, 132 / 157],
        ),
    }[dimensions]
    expected = np.zeros((len(native.article_ids), dimensions), dtype=np.float32)
    expected[:, columns] = first
    expected[1, columns] = second
    before = canonical(native)
    derived = derive_gemma(native, tmp_path, tmp_path, "embeddinggemma-two", dimensions)
    saved = np.load(tmp_path / derived.caches[0].file)
    np.testing.assert_allclose(saved, expected, rtol=float(np.finfo(np.float32).eps), atol=0)
    np.testing.assert_allclose(np.linalg.norm(saved, axis=1), 1, atol=1e-6)
    assert saved.shape == (len(articles()), dimensions) and saved.dtype == np.float32
    assert derived.derivation.base_vector_revision == digest(native)
    assert derived.derivation.base_files_sha256 == [native.caches[0].file_sha256]
    assert derived.derivation.model_dump()["inference"] is False
    assert derived.derivation.slug != "embeddinggemma-two"
    assert before == canonical(native)
    np.testing.assert_array_equal(matrix, np.load(tmp_path / "old.npy"))
    assert derive_gemma(native, tmp_path, tmp_path, "embeddinggemma-two", dimensions) == derived


@pytest.mark.parametrize(
    "bad", ["shape", "dtype", "nonfinite", "zero", "zero-prefix", "hash", "pin"]
)
def test_native_validation_refuses_invalid_derivation(tmp_path: Path, bad: str) -> None:
    native = native_fixture(tmp_path)
    matrix = np.load(tmp_path / "old.npy")
    if bad == "shape":
        matrix = matrix[:, :512]
    elif bad == "dtype":
        matrix = matrix.astype(np.float64)
    elif bad == "nonfinite":
        matrix[0, 0] = np.inf
    elif bad == "zero":
        matrix[0] = 0
    elif bad == "zero-prefix":
        matrix[0, :128] = 0
    elif bad == "hash":
        native.caches[0].file_sha256 = "f" * 64
    else:
        native.caches[0].revision = None
    if bad not in ("hash", "pin"):
        np.save(tmp_path / "old.npy", matrix)
        native.caches[0].file_sha256 = file_hash(tmp_path / "old.npy")
    with pytest.raises(ValueError):
        derive_gemma(native, tmp_path, tmp_path, "embeddinggemma-two", 128)


def test_dimensions_selected_in_development_and_identical_for_both_roles(tmp_path: Path) -> None:
    native = native_fixture(tmp_path)
    derived = derive_gemma(native, tmp_path, tmp_path, "embeddinggemma-two", 128)
    store = seeded_store(tmp_path)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        partition = build_partition(store, manifest(), set(articles()), policy(), set())
        universe = [i for i, p in partition.article_partitions.items() if p == "confirmation"]
        config = DevelopmentConfig(
            source_sha256=manifest().source_sha256,
            partition_sha256=digest(partition),
            frozen_at=now(),
            parameters={},
            reason="Generated numeric fixture only; no quality selection claim.",
        )
        freeze_development(store, config, partition)
        with pytest.raises(ValueError, match="selected in development"):
            predict(
                store,
                partition,
                derived,
                config,
                universe,
                derived.derivation.slug,
                "confirmation",
                "story",
                1,
            )
        assert store.setting("confirmation-opened") is None
        config = config.model_copy(
            update={"parameters": {"vector_candidates": {derived.derivation.slug: digest(derived)}}}
        )
        freeze_development(store, config, partition)
        alternative = config.model_copy(update={
            "parameters": {
                "vector_candidates": {derived.derivation.slug: digest(derived)},
                "cosine_threshold": 0.5,
            },
        })
        freeze_development(store, alternative, partition)
        result = predict(
            store,
            partition,
            derived,
            config,
            universe,
            derived.derivation.slug,
            "confirmation",
            "story",
            1,
        )
        assert isinstance(result, RetrievalRun)
        assert result.vector_manifest_sha256 == digest(derived)
        assert store.setting("confirmation-opened") == digest(config)
        with pytest.raises(ValueError, match="already opened"):
            predict(
                store, partition, derived, alternative, universe, derived.derivation.slug,
                "confirmation", "story", 1,
            )
        assert store.setting("confirmation-opened") == digest(config)
        wrong_settings = result.model_copy(update={
            "development_config_sha256": digest(alternative),
        })
        blocked = evaluate(
            store, manifest(), partition, derived, None, retrieval=wrong_settings,
        )
        assert any("already opened" in blocker for blocker in blocked.blockers)
        assert store.setting("confirmation-opened") == digest(config)
        report = evaluate(store, manifest(), partition, derived, None, retrieval=result)
        assert any("qrels" in blocker for blocker in report.blockers)
        assert not any("vector candidate" in blocker for blocker in report.blockers)
        unselected = config.model_copy(update={"parameters": {}})
        with store.transaction():
            store.save("development-config", digest(unselected), unselected)
        wrong = result.model_copy(update={"development_config_sha256": digest(unselected)})
        rejected = evaluate(store, manifest(), partition, derived, None, retrieval=wrong)
        assert any("vector candidate" in blocker for blocker in rejected.blockers)
        with pytest.raises(ValueError, match="already opened"):
            freeze_development(store, config.model_copy(update={"parameters": {}}), partition)
    finally:
        store.close()


def test_native_extension_coverage_derives_same_representation_and_refuses_conflict(
    tmp_path: Path,
) -> None:
    import hashlib

    native = native_fixture(tmp_path)
    all_ids = list(native.article_ids)
    matrix = np.load(tmp_path / "old.npy")
    expected_rows = {}
    for row, identity in enumerate(all_ids):
        left, right, length = (3, 4, 5) if row % 2 == 0 else (5, -12, 13)
        matrix[row, :128] = 0
        matrix[row, row] = left
        matrix[row, 127] = right
        expected_rows[identity] = np.zeros(128, dtype=np.float32)
        expected_rows[identity][row] = left / length
        expected_rows[identity][127] = right / length
    selected = all_ids[:4]
    np.save(tmp_path / "old.npy", matrix[4:])
    native = native.model_copy(update={
        "article_ids": all_ids[4:], "text_sha256": native.text_sha256[4:],
        "missing_article_ids": selected,
        "caches": [native.caches[0].model_copy(update={
            "rows": len(all_ids) - 4, "file_sha256": file_hash(tmp_path / "old.npy"),
        })],
    })
    before = (tmp_path / "old.npy").read_bytes()
    np.save(tmp_path / "extension.npy", matrix[:4])
    cache = VectorCache(**{
        **native.caches[0].model_dump(),
        "file": "extension.npy", "file_sha256": file_hash(tmp_path / "extension.npy"),
        "rows": 4,
    })
    extension = VectorExtensionSnapshot(
        path_base="dataset-root", source_sha256=native.source_sha256,
        slug="embeddinggemma-two", article_ids=selected,
        article_input_sha256=[articles()[i].input_sha256 for i in selected],
        summary_sha256=[
            hashlib.sha256(articles()[i].source.summary.encode()).hexdigest() for i in selected
        ],
        runtime_versions={"fixture": "arithmetic-only"}, cache=cache,
    )
    store = seeded_store(tmp_path)
    try:
        with store.transaction():
            store.save("vectors", digest(native), native)
            store.set_setting("vectors", digest(native))
        updated = register_extension(store, native, articles(), extension)
        derived = derive_gemma(updated, tmp_path, tmp_path, "embeddinggemma-two", 128)
        ids, combined = model_matrix(updated, "embeddinggemma-two", tmp_path)
        assert derived.article_ids == ids
        assert ids == all_ids[4:] + selected
        assert set(ids) == set(all_ids)
        np.testing.assert_array_equal(combined, np.concatenate((matrix[4:], matrix[:4])))
        np.testing.assert_allclose(
            np.load(tmp_path / derived.caches[0].file),
            np.array([expected_rows[identity] for identity in all_ids[4:] + selected]),
            rtol=float(np.finfo(np.float32).eps),
            atol=0,
        )
        assert derived.derivation.base_files_sha256 == [
            updated.caches[0].file_sha256, updated.extensions[0].cache.file_sha256,
        ]
        assert (tmp_path / "old.npy").read_bytes() == before
        conflict = extension.model_copy(update={
            "cache": cache.model_copy(update={"revision": "b" * 40}),
        })
        with pytest.raises(ValueError, match="settings/revision"):
            register_extension(store, updated, articles(), conflict)
    finally:
        store.close()
