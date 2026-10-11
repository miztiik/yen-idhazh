"""Exercise real approved example evidence through atomic annotation and catalog review."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from idhazh.contracts.story_annotation import (
    AnnotationRecord,
    ArticleDecision,
    CatalogReview,
    IdentityProposal,
    WorkerBatch,
    WorkerSubmission,
)
from idhazh.contracts.story_candidates import VectorManifest
from idhazh.contracts.story_evaluation import StoryPolicy
from idhazh.contracts.story_examples import ApprovedFixtures
from idhazh.contracts.story_source import ArticleEvidence, SourceFreeze
from idhazh.story_dataset.catalog import (
    empty_catalog,
    read_catalog,
    review_catalog,
    validate_catalog,
)
from idhazh.story_dataset.checkpoints import export_checkpoint, restore_checkpoint
from idhazh.story_dataset.source import freeze, load_articles, load_policy, validate_freeze
from idhazh.story_dataset.status import dataset_status
from idhazh.story_dataset.storage import Store, canonical, digest, file_hash, now, read_model
from idhazh.story_dataset.workers import (
    audit_selected,
    export_batch,
    import_submission,
    latest_annotations,
)

pytestmark = pytest.mark.contract
FIXTURE = Path(__file__).parent / "fixtures" / "story-dataset"


@pytest.fixture
def work() -> Iterator[Path]:
    path = Path("backend") / "var" / "story-tests" / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def fixtures() -> ApprovedFixtures:
    return read_model(FIXTURE / "approved.json", ApprovedFixtures)


def articles() -> dict[str, ArticleEvidence]:
    return {
        row.article_id: row for example in fixtures().examples for row in (example.a, example.b)
    }


def manifest() -> SourceFreeze:
    return SourceFreeze(
        source_sha256="1" * 64,
        source_bytes=1,
        articles=len(articles()),
        first_days=sorted({row.source.first_day for row in articles().values()}),
        frozen_at=now(),
        source_description="Real approved B1-B10 test subset only.",
        regression_hashes={},
        approved_examples_sha256=fixtures().approved_examples_sha256,
    )


def policy() -> StoryPolicy:
    return load_policy(Path("config") / "story-dataset.json").model_copy(
        update={"batch_size": 20, "metadata_neighbors": 1}
    )


def seeded_store(path: Path) -> Store:
    store = Store(path)
    review_catalog(store, fixtures().catalog, set(articles()))
    return store


def answer(batch: WorkerBatch, worker_id: str = "primary-example-fixture") -> WorkerSubmission:
    decisions = {
        identity: decision
        for example in fixtures().examples
        for identity, decision in (
            (example.a.article_id, example.a_decision),
            (example.b.article_id, example.b_decision),
        )
    }
    return WorkerSubmission(
        batch_id=batch.batch_id,
        source_sha256=batch.source_sha256,
        catalog_revision=batch.catalog_revision,
        worker_id=worker_id,
        operation=batch.operation,
        decisions={row.article_id: decisions[row.article_id] for row in batch.articles},
        supersedes=batch.correction_targets,
    )


def test_approved_multi_memberships_are_equal_and_partial_is_not_duplicate() -> None:
    approved = {example.id: example for example in fixtures().examples}
    assert len(approved["B7"].a_decision.memberships) == 2
    assert len(approved["B7"].b_decision.memberships) == 1
    assert len(approved["B8"].b_decision.memberships) == 2
    assert (
        approved["B7"].pair_decision.coverage == approved["B8"].pair_decision.coverage == "partial"
    )
    assert "primary" not in type(approved["B7"].a_decision.memberships[0]).model_fields
    assert approved["B6"].pair_decision.story == "shared"
    assert approved["B6"].pair_decision.occurrence == "different"
    assert approved["B4"].pair_decision.topic == "shared"
    assert approved["B4"].pair_decision.event == "different"
    for name in ("B1", "B2", "B3", "B9"):
        assert approved[name].pair_decision.coverage == "duplicate"


def test_checkpoint_replays_exact_histories_catalog_and_submissions(work: Path) -> None:
    store = seeded_store(work / "live")
    restored = Store(work / "restored")
    try:
        with store.transaction():
            store.set_setting("source", manifest().source_sha256)
        batch = export_batch(store, manifest(), articles(), policy())
        submission = answer(batch)
        import_submission(store, manifest(), articles(), submission)
        corrections = export_batch(
            store, manifest(), articles(), policy(), article_ids=[batch.articles[0].article_id]
        )
        import_submission(store, manifest(), articles(), answer(corrections, "correction-fixture"))
        outstanding = export_batch(
            store, manifest(), articles(), policy(), article_ids=[batch.articles[1].article_id]
        )
        before = list(store.db.execute("SELECT sequence,kind,id,subject,payload FROM records"))
        snapshot = export_checkpoint(store.root, work / "epoch", manifest(), policy())
        assert snapshot.files["history"].rows == len(before)
        restore_checkpoint(restored, work / "epoch", manifest(), policy())
        assert list(restored.db.execute(
            "SELECT sequence,kind,id,subject,payload FROM records"
        )) == before
        assert read_catalog(restored) == read_catalog(store)
        assert dataset_status(restored, manifest()) == dataset_status(store, manifest())
        assert restored.get("batch", outstanding.batch_id, WorkerBatch) == outstanding
        assert import_submission(restored, manifest(), articles(), submission) == 0
        assert restored.get("submission", digest(submission), WorkerSubmission) == submission
        with pytest.raises(ValueError, match="empty index"):
            restore_checkpoint(restored, work / "epoch", manifest(), policy())
    finally:
        store.close()
        restored.close()


def test_checkpoint_refuses_tampering_and_changed_source_without_partial_restore(work: Path) -> None:
    store = seeded_store(work / "live")
    restored = Store(work / "restored")
    try:
        with store.transaction():
            store.set_setting("source", manifest().source_sha256)
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        export_checkpoint(store.root, work / "epoch", manifest(), policy())
        with pytest.raises(ValueError, match="new immutable"):
            export_checkpoint(store.root, work / "epoch", manifest(), policy())
        with pytest.raises(ValueError, match="source or policy"):
            restore_checkpoint(
                restored, work / "epoch",
                manifest().model_copy(update={"source_sha256": "2" * 64}), policy()
            )
        with (work / "epoch" / "history.jsonl").open("ab") as stream:
            stream.write(b"{}\n")
        with pytest.raises(ValueError, match="hash or size"):
            restore_checkpoint(restored, work / "epoch", manifest(), policy())
        assert restored.db.execute("SELECT count(*) FROM records").fetchone()[0] == 0
        assert restored.setting("source") is None
    finally:
        store.close()
        restored.close()


def test_checkpoint_declares_omitted_pair_frame_without_committing_it(work: Path) -> None:
    from idhazh.story_dataset.sampling import build_pairs

    store = seeded_store(work / "live")
    restored = Store(work / "restored")
    try:
        frame = build_pairs(manifest(), articles(), policy(), None)
        with store.transaction():
            store.set_setting("source", manifest().source_sha256)
            store.save("pair-frame", digest(frame), frame)
            store.set_setting("pair-frame", digest(frame))
        snapshot = export_checkpoint(store.root, work / "epoch", manifest(), policy())
        assert snapshot.omitted_artifacts == {"pair-frame": [digest(frame)]}
        restore_checkpoint(restored, work / "epoch", manifest(), policy())
        assert restored.setting("pair-frame") is None
        assert restored.db.execute(
            "SELECT count(*) FROM artifacts WHERE kind='pair-frame'"
        ).fetchone()[0] == 0
    finally:
        store.close()
        restored.close()


def test_checkpoint_preserves_confirmation_exposure_without_omitted_config(work: Path) -> None:
    from idhazh.contracts.story_evaluation import DevelopmentConfig
    from idhazh.story_dataset.partitions import build_partition
    from idhazh.story_dataset.predictions import freeze_development

    store = seeded_store(work / "live")
    restored = Store(work / "restored")
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        partition = build_partition(store, manifest(), set(articles()), policy(), set())
        config = DevelopmentConfig(
            source_sha256=manifest().source_sha256, partition_sha256=digest(partition),
            frozen_at=now(), parameters={"cosine_threshold": 0.9}, reason="Fixture settings.",
        )
        freeze_development(store, config, partition)
        with store.transaction():
            store.set_setting("source", manifest().source_sha256)
            store.set_setting("confirmation-opened", digest(config))
        export_checkpoint(store.root, work / "epoch", manifest(), policy())
        restore_checkpoint(restored, work / "epoch", manifest(), policy())
        assert restored.setting("confirmation-opened") == digest(config)
        from idhazh.contracts.story_evaluation import Partition

        assert restored.setting("partition") == digest(partition)
        previous = restored.get("partition", str(restored.setting("partition")), Partition)
        rebuilt = build_partition(
            restored, manifest(), set(articles()), policy(), set(), previous=previous
        )
        assert digest(rebuilt) == digest(partition)
        with pytest.raises(ValueError, match="already opened"):
            freeze_development(
                restored, config.model_copy(update={"parameters": {"cosine_threshold": 0.8}}),
                rebuilt,
            )
    finally:
        store.close()
        restored.close()


def test_worker_catalog_sidecar_keeps_bound_revision_after_concurrent_review(work: Path) -> None:
    from idhazh.contracts.story_annotation import CatalogSnapshot
    from idhazh.story_dataset.commands import write_batch

    store = seeded_store(work)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        old_catalog = read_catalog(store)
        reviewed = review_catalog(
            store, CatalogReview(
                expected_revision=old_catalog.revision, reviewer="fixture-reviewer",
                reason="Another review committed between batch export and sidecar write.",
            ), set(articles()),
        )
        assert reviewed.revision != batch.catalog_revision
        output = work / "batch.json"
        write_batch(store, batch, output)
        assert read_model(output.with_suffix(".catalog.json"), CatalogSnapshot) == old_catalog
    finally:
        store.close()


def test_b10_source_findings_are_real_but_boundary_remains_unresolved() -> None:
    example = fixtures().examples[-1]
    assert example.id == "B10" and example.a_decision.state == "unresolved"
    assert example.pair_decision.story == "unresolved"
    assert example.pair_decision.occurrence == "same"
    assert example.pair_decision.coverage == "unresolved"
    assert len(example.a_decision.source_checks) == 2
    assert all(check.checked_at is None for check in example.a_decision.source_checks)
    assert not any("Negotiated terms" in item.name for item in fixtures().catalog.entities)


def test_schema_rejects_ranking_fake_human_and_unreasoned_uncertainty() -> None:
    decision = fixtures().examples[0].a_decision.model_dump()
    decision["memberships"][0]["primary"] = True
    with pytest.raises(ValidationError):
        ArticleDecision.model_validate(decision)
    with pytest.raises(ValidationError):
        ArticleDecision.model_validate(
            {
                "input_sha256": "0" * 64,
                "state": "unresolved",
                "memberships": [],
                "reason": "Unsure.",
            }
        )
    with pytest.raises(ValidationError):
        WorkerSubmission.model_validate(
            {
                "batch_id": "0" * 64,
                "source_sha256": "0" * 64,
                "catalog_revision": "0" * 64,
                "worker_id": "x",
                "operation": "primary",
                "label_source": "human",
                "decisions": {},
            }
        )


def test_blind_batch_contains_exact_full_summary_and_no_acquisition_data(work: Path) -> None:
    store = seeded_store(work)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        for row in batch.articles:
            assert row.source.summary == articles()[row.article_id].source.summary
            assert row.source.title == articles()[row.article_id].source.title
        data = canonical(batch)
        assert b"cosine" not in data and b"challenge_tags" not in data
        assert batch.catalog_revision == read_catalog(store).revision
        assert store.get("batch", batch.batch_id, WorkerBatch) == batch
    finally:
        store.close()


@pytest.mark.parametrize("mutation", ["hash", "foreign", "missing", "catalog", "source", "parent"])
def test_import_validation_is_fail_closed_and_atomic(work: Path, mutation: str) -> None:
    store = seeded_store(work)
    try:
        selected = [fixtures().examples[0].a.article_id, fixtures().examples[0].b.article_id]
        batch = export_batch(store, manifest(), articles(), policy(), article_ids=selected)
        payload = answer(batch).model_dump()
        identity = selected[-1]
        if mutation == "hash":
            payload["decisions"][identity]["input_sha256"] = "0" * 64
        elif mutation == "foreign":
            payload["decisions"]["a-" + "0" * 64] = payload["decisions"].pop(identity)
        elif mutation == "missing":
            del payload["decisions"][identity]
        elif mutation == "catalog":
            payload["catalog_revision"] = "0" * 64
        elif mutation == "source":
            payload["source_sha256"] = "0" * 64
        else:
            payload["decisions"][identity]["memberships"][0]["event"] = "event-" + "0" * 64
        with pytest.raises(ValueError):
            import_submission(
                store, manifest(), articles(), WorkerSubmission.model_validate(payload)
            )
        assert latest_annotations(store) == {}
        assert store.records("annotation", AnnotationRecord) == []
    finally:
        store.close()


def test_resume_idempotency_and_explicit_correction_keep_old_payload_bytes(work: Path) -> None:
    store = seeded_store(work)
    try:
        identity = fixtures().examples[0].a.article_id
        batch = export_batch(store, manifest(), articles(), policy(), article_ids=[identity])
        submission = answer(batch)
        assert import_submission(store, manifest(), articles(), submission) == 1
        before = canonical(store.records("annotation", AnnotationRecord)[0])
        assert import_submission(store, manifest(), articles(), submission) == 0
        correction_batch = export_batch(
            store, manifest(), articles(), policy(), article_ids=[identity]
        )
        corrected = answer(correction_batch, "correction-example-fixture")
        corrected.decisions[identity].reason += " Explicit provenance correction."
        assert import_submission(store, manifest(), articles(), corrected) == 1
        history = store.records("annotation", AnnotationRecord)
        assert canonical(history[0]) == before
        assert history[1].supersedes == history[0].record_id
        assert dataset_status(store, manifest()).rows_visited == 1
        assert dataset_status(store, manifest()).history_records == 2
    finally:
        store.close()
    resumed = Store(work)
    try:
        assert len(resumed.records("annotation", AnnotationRecord)) == 2
    finally:
        resumed.close()


def test_progress_counts_real_unresolved_records_not_estimated_labels(work: Path) -> None:
    store = seeded_store(work)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        status = dataset_status(store, manifest())
        assert (
            status.rows_visited,
            status.annotated,
            status.unresolved,
            status.catalog_pending,
        ) == (20, 18, 2, 0)
        assert status.unvisited == 0 and status.independently_reviewed == 0
        assert status.acceptance_status == "unapproved"
        assert status.full_archive_evaluation == "blocked"
    finally:
        store.close()


def test_parallel_batch_reservations_do_not_visit_or_duplicate_rows(work: Path) -> None:
    store = seeded_store(work)
    try:
        small = policy().model_copy(update={"batch_size": 5})
        first = export_batch(store, manifest(), articles(), small)
        second = export_batch(store, manifest(), articles(), small)
        assert {row.article_id for row in first.articles}.isdisjoint(
            row.article_id for row in second.articles
        )
        assert dataset_status(store, manifest()).rows_visited == 0
        assert store.get("batch", first.batch_id, WorkerBatch) == first
    finally:
        store.close()


def test_proposals_are_pending_until_explicit_catalog_reconciliation(work: Path) -> None:
    store = Store(work)
    try:
        example = fixtures().examples[0]
        identity = example.a.article_id
        batch = export_batch(store, manifest(), articles(), policy(), article_ids=[identity])
        entities = fixtures().catalog.entities
        path = example.a_decision.memberships[0]
        used = {path.topic, path.event, path.story, *path.occurrence_refs}
        refs = {
            item.id: "proposal:" + item.id.split("-")[0] for item in entities if item.id in used
        }
        proposals = [
            IdentityProposal(
                ref=refs[item.id],
                kind=item.kind,
                name=item.name,
                parent_refs=[refs[parent] for parent in item.parent_ids],
                definition=item.definition,
                evidence_article_ids=[identity],
            )
            for item in entities
            if item.id in used
        ]
        payload = example.a_decision.model_dump()
        payload["memberships"][0].update(
            {
                "topic": refs[path.topic],
                "event": refs[path.event],
                "story": refs[path.story],
                "occurrence_refs": [refs[r] for r in path.occurrence_refs],
            }
        )
        submission = WorkerSubmission(
            batch_id=batch.batch_id,
            source_sha256=batch.source_sha256,
            catalog_revision=batch.catalog_revision,
            operation="primary",
            worker_id="proposal-fixture",
            proposals=proposals,
            decisions={identity: ArticleDecision.model_validate(payload)},
        )
        import_submission(store, manifest(), articles(), submission)
        assert dataset_status(store, manifest()).catalog_pending == 1
        review = fixtures().catalog.model_copy(
            update={
                "proposal_resolutions": {
                    batch.batch_id + ":" + local: canonical_id
                    for canonical_id, local in refs.items()
                },
            }
        )
        review_catalog(store, review, set(articles()))
        assert dataset_status(store, manifest()).catalog_pending == 0
        assert dataset_status(store, manifest()).annotated == 1
        stale = CatalogReview(
            expected_revision=empty_catalog().revision,
            reviewer="model reviewer",
            reason="Stale review.",
        )
        with pytest.raises(ValueError, match="catalog changed"):
            review_catalog(store, stale, set(articles()))
    finally:
        store.close()


def test_catalog_rejects_unknown_parents_and_alias_cycles(work: Path) -> None:
    store = seeded_store(work)
    try:
        catalog = read_catalog(store)
        broken = catalog.model_copy(deep=True)
        event = next(item for item in broken.entities if item.kind == "event")
        event.parent_ids = ["topic-" + "0" * 64]
        with pytest.raises(ValueError, match="unknown"):
            validate_catalog(broken, set(articles()))
        event_ids = [item.id for item in catalog.entities if item.kind == "event"][:2]
        catalog.aliases = {event_ids[0]: event_ids[1], event_ids[1]: event_ids[0]}
        with pytest.raises(ValueError, match="cycle"):
            validate_catalog(catalog, set(articles()))
    finally:
        store.close()


def test_catalog_resolution_cannot_break_an_independent_review_path(work: Path) -> None:
    store = seeded_store(work)
    try:
        example, unrelated = fixtures().examples[:2]
        identity = example.a.article_id
        primary = export_batch(store, manifest(), articles(), policy(), article_ids=[identity])
        import_submission(store, manifest(), articles(), answer(primary))
        batch = export_batch(
            store, manifest(), articles(), policy(), operation="review", article_ids=[identity]
        )
        independent = answer(batch, "independent-example-fixture")
        independent.independent_of = batch.independent_of_workers
        membership = independent.decisions[identity].memberships[0]
        ref = "proposal:independent-food-enforcement"
        independent.proposals = [
            IdentityProposal(
                ref=ref,
                kind="story",
                name="Food-platform enforcement announcement",
                parent_refs=[membership.event],
                definition="The enforcement announcement covered by the real B1 source.",
                evidence_article_ids=[identity],
            )
        ]
        independent.decisions[identity].memberships = [
            membership.model_copy(update={"story": ref, "occurrence_refs": []})
        ]
        import_submission(store, manifest(), articles(), independent)
        original_revision = read_catalog(store).revision
        invalid = CatalogReview(
            expected_revision=original_revision,
            reviewer="independent catalog fixture",
            reason="Exercise refusal of a resolution to the unrelated B2 event's story.",
            proposal_resolutions={
                batch.batch_id + ":" + ref: unrelated.a_decision.memberships[0].story
            },
        )
        with pytest.raises(ValueError, match="breaks a membership path"):
            review_catalog(store, invalid, set(articles()))
        assert read_catalog(store).revision == original_revision
    finally:
        store.close()


def test_review_is_blind_independent_and_does_not_replace_primary(work: Path) -> None:
    store = seeded_store(work)
    try:
        example = fixtures().examples[-1]
        identity = example.a.article_id
        batch = export_batch(store, manifest(), articles(), policy(), article_ids=[identity])
        import_submission(store, manifest(), articles(), answer(batch))
        review = export_batch(store, manifest(), articles(), policy(), operation="review")
        assert review.review_targets and b"decision" not in canonical(review)
        same_worker = answer(review)
        same_worker.independent_of = ["primary-example-fixture"]
        with pytest.raises(ValueError, match="independent"):
            import_submission(store, manifest(), articles(), same_worker)
        independent = answer(review, "independent-example-fixture")
        independent.independent_of = ["primary-example-fixture"]
        assert import_submission(store, manifest(), articles(), independent) == 1
        assert len(latest_annotations(store)) == 1
        status = dataset_status(store, manifest())
        assert status.independently_reviewed == 1 and status.review_conflicts == 1
        assert status.unresolved == 1
    finally:
        store.close()


def test_random_audit_is_reproducible_engineering_selection() -> None:
    selected = {i for i in articles() if audit_selected(i, policy())}
    assert selected == {i for i in articles() if audit_selected(i, policy())}
    assert all(
        audit_selected(i, policy().model_copy(update={"random_audit_fraction": 1}))
        for i in articles()
    )


def test_source_freeze_preserves_bytes_and_refuses_source_or_regression_changes(work: Path) -> None:
    root = work / "corpus" / "story-dataset-1"
    root.mkdir(parents=True)
    path = root / "articles.jsonl"
    raw = b"".join(canonical(row.source) for row in articles().values())
    path.write_bytes(raw)
    from idhazh.story_dataset.source import REGRESSION_FILES

    for name in REGRESSION_FILES:
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"Original named regression bytes.\n")
    selected = policy().model_copy(
        update={
            "expected_articles": 20,
            "expected_bytes": len(raw),
            "expected_sha256": file_hash(path),
        }
    )
    frozen = freeze(root, work, selected, FIXTURE / "approved.json")
    assert path.read_bytes() == raw and frozen.articles == 20
    validate_freeze(root, work, selected)
    (work / REGRESSION_FILES[0]).write_bytes(b"Changed.\n")
    with pytest.raises(ValueError, match="regression"):
        validate_freeze(root, work, selected)
    path.write_bytes(raw + b"\n")
    with pytest.raises(ValueError, match="freeze"):
        validate_freeze(root, work, selected)


def test_source_parser_rejects_repeated_urls_and_extra_rows(work: Path) -> None:
    path = work / "articles.jsonl"
    row = fixtures().examples[0].a.source
    path.write_bytes(canonical(row) * 2)
    with pytest.raises(ValueError, match="repeated URL"):
        load_articles(path, 2)
    with pytest.raises(ValueError, match="bounded"):
        load_articles(path, 1)


def vector_fixture() -> VectorManifest:
    import numpy as np

    from idhazh.contracts.story_candidates import VectorCache, VectorManifest, VectorOrder

    order = read_model(FIXTURE / "vector-order.json", VectorOrder)
    order_hash = file_hash(FIXTURE / "vector-order.json")
    config = Path("config") / "encoder-comparison.json"
    caches = []
    for slug, expected_hash in order.vectors_sha256.items():
        path = (FIXTURE / (slug + ".npy")).resolve()
        assert file_hash(path) == expected_hash
        saved = np.load(path, mmap_mode="r", allow_pickle=False)
        caches.append(
            VectorCache(
                slug=slug,
                file=str(path),
                file_sha256=expected_hash,
                rows=saved.shape[0],
                dimensions=saved.shape[1],
                reading_sha256=order_hash,
                input_sha256=order_hash,
                model_id="recorded-" + slug,
                revision=None,
                settings_sha256=order_hash,
            )
        )
    return VectorManifest(
        source_sha256=manifest().source_sha256,
        input_sha256=order_hash,
        input_file=str((FIXTURE / "vector-order.json").resolve()),
        readings_file=str((FIXTURE / "vector-order.json").resolve()),
        readings_sha256=order_hash,
        encoder_config_file=str(config.resolve()),
        encoder_config_sha256=file_hash(config),
        max_sequence_length=256,
        article_ids=order.article_ids,
        text_sha256=[digest(articles()[i].source.summary) for i in order.article_ids],
        missing_article_ids=[],
        caches=caches,
    )


def test_known_probability_pair_sampling_reports_separate_overlapping_streams() -> None:
    from idhazh.story_dataset.sampling import build_pairs, sample_indices

    selected = policy().model_copy(update={"representative_pair_probability": 1.0})
    frame = build_pairs(manifest(), articles(), selected)
    assert frame.population_size == 190 and len(frame.pairs) == 190
    assert all(row.representative_probability == 1 for row in frame.pairs)
    assert any(row.challenge_tags for row in frame.pairs)
    assert all(len(row.missing_vector_articles) == 2 for row in frame.pairs)
    assert sample_indices(190, 0.25, 3) == sample_indices(190, 0.25, 3)
    assert len(sample_indices(190, 0.25, 3)) < 190


def test_four_real_vector_slices_union_ranks_without_averaging() -> None:
    from idhazh.story_dataset.sampling import build_pairs
    from idhazh.story_dataset.vectors import ranked_neighbors

    vectors = vector_fixture()
    queries = vectors.article_ids[:2]
    union = ranked_neighbors(vectors, queries, 3, 2)
    assert {r.model for ranks in union.values() for r in ranks} == {c.slug for c in vectors.caches}
    assert all(1 <= r.rank <= 3 for ranks in union.values() for r in ranks)
    frame = build_pairs(
        manifest(),
        articles(),
        policy().model_copy(update={"top_k": 3}),
        vectors,
        queries,
    )
    assert any(row.ranks for row in frame.pairs)
    assert any("encoder-rank-disagreement" in row.challenge_tags for row in frame.pairs)
    assert "average_cosine" not in frame.model_dump_json()


def test_changed_text_vector_rows_are_not_zero_score_easy_negatives() -> None:
    from idhazh.story_dataset.vectors import covered_ids, ranked_neighbors

    vectors = vector_fixture()
    excluded = vectors.article_ids[0]
    vectors.text_conflict_article_ids = [excluded]
    assert excluded not in covered_ids(vectors)
    union = ranked_neighbors(vectors, vectors.article_ids[:2], 3, 2)
    assert all(excluded not in pair for pair in union)


def test_pair_worker_view_and_import_are_independent_of_article_memberships(work: Path) -> None:
    from idhazh.contracts.story_candidates import PairRecord, PairSubmission
    from idhazh.story_dataset.pair_workers import export_pairs, import_pairs
    from idhazh.story_dataset.sampling import build_pairs, pair_id

    store = Store(work)
    try:
        example = fixtures().examples[0]
        frame = build_pairs(
            manifest(),
            articles(),
            policy().model_copy(update={"representative_pair_probability": 1}),
        )
        batch = export_pairs(
            store, frame, articles(), 20, [pair_id(example.a.article_id, example.b.article_id)]
        )
        assert b"cosine" not in canonical(batch) and b"representative_probability" not in canonical(
            batch
        )
        assert (
            batch.pairs[0].a.source.summary
            == articles()[batch.pairs[0].a.article_id].source.summary
        )
        submission = PairSubmission(
            batch_id=batch.batch_id,
            source_sha256=batch.source_sha256,
            worker_id="pair-fixture",
            decisions={batch.pairs[0].pair_id: example.pair_decision},
        )
        assert import_pairs(store, submission) == 1
        assert import_pairs(store, submission) == 0
        assert len(store.records("pair", PairRecord)) == 1
        assert not latest_annotations(store)
    finally:
        store.close()


def test_pair_export_prepares_frame_once_outside_lock_and_preserves_bytes(work: Path) -> None:
    import sys
    from types import FrameType

    from idhazh.contracts.story_candidates import PairEvidence, PairFrame, PairWorkerBatch
    from idhazh.story_dataset.pair_workers import PAIR_INSTRUCTIONS, export_pairs
    from idhazh.story_dataset.sampling import build_pairs

    evidence = articles()
    frame = build_pairs(manifest(), evidence, policy())
    selected = frame.pairs[0]
    fingerprint = digest(frame)
    expected = PairWorkerBatch(
        batch_id=digest(
            {
                "frame": fingerprint,
                "pairs": [selected.id],
                "operation": "primary",
                "targets": {},
                "corrections": {},
            }
        ),
        source_sha256=frame.source_sha256,
        frame_sha256=fingerprint,
        pairs=[
            PairEvidence(
                pair_id=selected.id,
                input_sha256=digest({"a": evidence[selected.a], "b": evidence[selected.b]}),
                a=evidence[selected.a],
                b=evidence[selected.b],
            )
        ],
        instructions=PAIR_INSTRUCTIONS,
    )
    store = Store(work)
    calls: list[bool] = []
    statements: list[str] = []

    def observe(python_frame: FrameType, event: str, argument: object) -> None:
        if (
            event == "call"
            and python_frame.f_code is canonical.__code__
            and isinstance(python_frame.f_locals["value"], PairFrame)
        ):
            calls.append(store.db.in_transaction)

    try:
        with store.transaction():
            store.save("pair-frame", fingerprint, frame)
        changes = store.db.total_changes
        store.db.set_trace_callback(statements.append)
        previous = sys.getprofile()
        sys.setprofile(observe)
        try:
            batch = export_pairs(store, frame, evidence, 1, [selected.id])
            repeated = export_pairs(store, frame, evidence, 1, [selected.id])
        finally:
            sys.setprofile(previous)
        assert calls == [False, False]
        assert canonical(batch) == canonical(repeated) == canonical(expected)
        assert canonical(store.get("pair-batch", batch.batch_id, PairWorkerBatch)) == canonical(
            expected
        )
        assert canonical(store.get("pair-frame", fingerprint, PairFrame)) == canonical(frame)
        assert store.db.total_changes == changes + 1
        assert not any(s.startswith("INSERT") and "'pair-frame'" in s for s in statements)
    finally:
        store.close()


@pytest.mark.parametrize("corruption", ["invalid-json", "invalid-schema", "changed", "whitespace"])
def test_pair_export_rejects_corrupt_registered_frame_without_reserving(
    work: Path, corruption: str
) -> None:
    from idhazh.story_dataset.pair_workers import export_pairs
    from idhazh.story_dataset.sampling import build_pairs

    frame = build_pairs(manifest(), articles(), policy())
    fingerprint = digest(frame)
    bad = {
        "invalid-json": "{",
        "invalid-schema": "{}",
        "changed": canonical(frame.model_copy(update={"seed": frame.seed + 1})).decode(),
        "whitespace": canonical(frame).decode() + "\n",
    }[corruption]
    store = Store(work)
    try:
        with store.transaction():
            store.db.execute("INSERT INTO artifacts VALUES('pair-frame',?,?)", (fingerprint, bad))
        with pytest.raises(ValueError, match="immutable pair-frame differs"):
            export_pairs(store, frame, articles(), 1)
        assert store.db.execute("SELECT kind,id,payload FROM artifacts").fetchall() == [
            ("pair-frame", fingerprint, bad)
        ]
        assert not store.db.in_transaction
    finally:
        store.close()


def test_pair_export_registers_modified_frame_by_its_actual_bytes_and_rolls_back_conflict(
    work: Path,
) -> None:
    from idhazh.contracts.story_candidates import PairFrame
    from idhazh.story_dataset.pair_workers import export_pairs
    from idhazh.story_dataset.sampling import build_pairs

    frame = build_pairs(manifest(), articles(), policy())
    store = Store(work)
    try:
        original = export_pairs(store, frame, articles(), 1, [frame.pairs[0].id])
        frame.seed += 1
        changed = export_pairs(store, frame, articles(), 1, [frame.pairs[0].id])
        assert original.frame_sha256 != changed.frame_sha256 == digest(frame)
        assert original.batch_id != changed.batch_id
        assert canonical(store.get("pair-frame", changed.frame_sha256, PairFrame)) == canonical(
            frame
        )
        with store.transaction():
            store.db.execute(
                "DELETE FROM artifacts WHERE kind='pair-frame' AND id=?", (changed.frame_sha256,)
            )
            store.db.execute(
                "UPDATE artifacts SET payload=? WHERE kind='pair-batch' AND id=?",
                (
                    canonical(
                        changed.model_copy(update={"instructions": "Conflicting request."})
                    ).decode(),
                    changed.batch_id,
                ),
            )
        with pytest.raises(ValueError, match="immutable pair-batch differs"):
            export_pairs(store, frame, articles(), 1, [frame.pairs[0].id])
        assert not store.db.execute(
            "SELECT 1 FROM artifacts WHERE kind='pair-frame' AND id=?", (changed.frame_sha256,)
        ).fetchone()
    finally:
        store.close()


def test_pair_export_revalidates_mutated_models_before_beginning_transaction(work: Path) -> None:
    from idhazh.story_dataset.pair_workers import export_pairs
    from idhazh.story_dataset.sampling import build_pairs

    frame = build_pairs(manifest(), articles(), policy()).model_copy(update={"seed": "2"})
    store = Store(work)
    statements: list[str] = []
    try:
        store.db.set_trace_callback(statements.append)
        with pytest.warns(UserWarning, match="PydanticSerializationUnexpectedValue"):
            with pytest.raises(ValidationError):
                export_pairs(store, frame, articles(), 1)
        assert not statements
        assert not store.db.execute("SELECT 1 FROM artifacts").fetchone()
    finally:
        store.close()


def test_pair_export_uses_prepared_snapshot_while_waiting_for_writer(work: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from idhazh.contracts.story_candidates import PairFrame, PairWorkerBatch
    from idhazh.story_dataset.pair_workers import export_pairs
    from idhazh.story_dataset.sampling import build_pairs

    evidence = articles()
    frame = build_pairs(manifest(), evidence, policy())
    fingerprint = digest(frame)
    payload = canonical(frame)
    ready, start, beginning = Event(), Event(), Event()

    def export() -> PairWorkerBatch:
        worker = Store(work)
        try:
            worker.db.set_trace_callback(
                lambda statement: beginning.set() if statement == "BEGIN IMMEDIATE" else None
            )
            ready.set()
            assert start.wait(10)
            return export_pairs(worker, frame, evidence, 1)
        finally:
            worker.close()

    store = Store(work)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(export)
            try:
                assert ready.wait(10)
                with store.transaction():
                    start.set()
                    assert beginning.wait(10)
                    frame.seed += 1
                    frame.pairs[0].challenge_tags.append("changed-while-waiting")
            finally:
                start.set()
            batch = pending.result(timeout=10)
        assert batch.frame_sha256 == fingerprint != digest(frame)
        assert canonical(store.get("pair-frame", fingerprint, PairFrame)) == payload
    finally:
        store.close()


def test_concurrent_pair_exports_reserve_disjoint_batches(work: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from idhazh.contracts.story_candidates import PairWorkerBatch
    from idhazh.story_dataset.pair_workers import export_pairs
    from idhazh.story_dataset.sampling import build_pairs

    evidence = articles()
    frame = build_pairs(manifest(), evidence, policy())
    barrier = Barrier(2, timeout=10)

    def export() -> PairWorkerBatch:
        store = Store(work)
        try:
            barrier.wait()
            return export_pairs(store, frame, evidence, 1)
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: export(), range(2)))
    assert first.frame_sha256 == second.frame_sha256 == digest(frame)
    assert {row.pair_id for row in first.pairs}.isdisjoint(row.pair_id for row in second.pairs)


def test_invalid_partial_duplicate_relation_and_unresolved_pair_fail_closed() -> None:
    from idhazh.contracts.story_candidates import PairDecision

    example = fixtures().examples[7]
    data = example.pair_decision.model_dump()
    data["coverage"] = "duplicate"
    with pytest.raises(ValueError, match="same occurrence"):
        PairDecision.model_validate(data)
    data = fixtures().examples[9].pair_decision.model_dump()
    data["unresolved_reasons"] = []
    with pytest.raises(ValueError, match="unresolved"):
        PairDecision.model_validate(data)


def test_event_partition_tracks_all_memberships_and_quarantines_new_crossings(work: Path) -> None:
    from idhazh.contracts.story_candidates import CandidatePair, PairFrame
    from idhazh.story_dataset.partitions import build_partition
    from idhazh.story_dataset.sampling import pair_id

    store = seeded_store(work)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        first = build_partition(store, manifest(), set(articles()), policy(), set())
        b8 = fixtures().examples[7]
        assert first.component_ids[b8.a.article_id] == first.component_ids[b8.b.article_id]
        assert first.article_partitions[fixtures().examples[-1].a.article_id] == "quarantine"
        assert set(first.article_partitions.values()) >= {"development", "confirmation"}
        groups = {
            name: [i for i, part in first.article_partitions.items() if part == name]
            for name in ("development", "confirmation")
        }
        left, right = groups["development"][0], groups["confirmation"][0]
        link = PairFrame(
            source_sha256=manifest().source_sha256,
            population="all-unordered-distinct-frozen-archive-articles",
            population_size=190,
            sampling="independent-bernoulli-geometric-skip",
            seed=policy().seed,
            representative_probability=0.1,
            pairs=[
                CandidatePair(
                    id=pair_id(left, right), a=left, b=right, challenge_tags=["new-known-link"]
                )
            ],
        )
        updated = build_partition(store, manifest(), set(articles()), policy(), set(), link, first)
        assert updated.article_partitions[left] == updated.article_partitions[right] == "quarantine"
        assert any("crossing" in reason for reason in updated.blocked_reasons)
        repeat = build_partition(store, manifest(), set(articles()), policy(), set(), link, updated)
        assert repeat.article_partitions == updated.article_partitions
    finally:
        store.close()


def test_frozen_regression_articles_are_never_confirmation(work: Path) -> None:
    from idhazh.story_dataset.partitions import build_partition

    store = seeded_store(work)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        example = fixtures().examples[0]
        result = build_partition(
            store, manifest(), set(articles()), policy(), {example.a.article_id}
        )
        assert result.article_partitions[example.a.article_id] == "quarantine"
        assert result.article_partitions[example.b.article_id] == "quarantine"
    finally:
        store.close()


def test_complete_qrels_metrics_and_unjudged_negative_guard() -> None:
    from idhazh.story_dataset.metrics import neighbor_metrics

    assert neighbor_metrics(["relevant", "negative"], {"relevant": True, "negative": False}, 1) == {
        "precision_at_k": 1,
        "recall_at_k": 1,
        "ndcg_at_k": 1,
    }
    with pytest.raises(ValueError, match="unjudged"):
        neighbor_metrics(["unknown"], {"relevant": True, "negative": False}, 1)
    with pytest.raises(ValueError, match="both"):
        neighbor_metrics(["relevant"], {"relevant": True}, 1)
    with pytest.raises(ValueError, match="both"):
        neighbor_metrics(["negative"], {"negative": False}, 1)


def test_overlapping_pairwise_metrics_do_not_assume_single_partition() -> None:
    from idhazh.story_dataset.metrics import overlap_pair_metrics

    gold = {"a": {"s1", "s2"}, "b": {"s1"}, "c": {"s2"}, "d": {"s3"}}
    metrics = overlap_pair_metrics(gold, gold)
    assert metrics["overlap_pair_f1"] == 1
    assert metrics["shared_gold_pairs"] == 2 and metrics["disjoint_gold_pairs"] == 4
    predicted = {"a": {"p"}, "b": {"p"}, "c": {"q"}, "d": {"r"}}
    assert overlap_pair_metrics(gold, predicted)["overlap_pair_recall"] == 0.5
    with pytest.raises(ValueError, match="both"):
        overlap_pair_metrics({"a": {"s"}, "b": {"s"}}, {"a": {"p"}, "b": {"p"}})


def test_pipeline_reports_blocked_not_fake_perfect_scores(work: Path) -> None:
    from idhazh.story_dataset.evaluation import evaluate

    store = Store(work)
    try:
        report = evaluate(store, manifest(), None, None, None)
        assert report.state == "blocked" and report.metrics == {}
        assert report.evaluated_queries == 0
        assert report.acceptance_status == "unapproved"
    finally:
        store.close()


def test_real_saved_vector_prediction_and_overlapping_cluster_pilot(work: Path) -> None:
    from idhazh.contracts.story_evaluation import ClusterRun, DevelopmentConfig, RetrievalRun
    from idhazh.story_dataset.evaluation import evaluate
    from idhazh.story_dataset.partitions import build_partition
    from idhazh.story_dataset.predictions import freeze_development, predict
    from idhazh.story_dataset.vector_files import snapshot_vectors

    store = seeded_store(work)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        partition = build_partition(store, manifest(), set(articles()), policy(), set())
        config = DevelopmentConfig(
            source_sha256=manifest().source_sha256,
            partition_sha256=digest(partition),
            frozen_at=now(),
            parameters={"cosine_threshold": 0.9},
            reason="Provisional engineering fixture baseline, not quality selection.",
        )
        freeze_development(store, config, partition)
        universe = [i for i, p in partition.article_partitions.items() if p == "confirmation"]
        vectors = snapshot_vectors(work, vector_fixture())
        retrieval = predict(
            store, partition, vectors, config, universe, "gte-small", "confirmation", "story", 1
        )
        assert isinstance(retrieval, RetrievalRun) and len(retrieval.rankings) == len(universe)
        with pytest.raises(ValueError, match="already opened"):
            freeze_development(
                store, config.model_copy(update={"reason": "Retrofitted."}), partition
            )
        report = evaluate(store, manifest(), partition, vectors, None, retrieval)
        assert report.state == "blocked" and report.metrics == {}
        assert any("qrels" in blocker for blocker in report.blockers)
        clusters = predict(
            store,
            partition,
            vectors,
            config,
            universe,
            "gte-small",
            "confirmation",
            "story",
            1,
            cluster=True,
        )
        assert isinstance(clusters, ClusterRun)
        cluster_report = evaluate(store, manifest(), partition, vectors, None, clusters=clusters)
        assert cluster_report.state == "pilot-measured"
        assert cluster_report.evaluated_articles == len(universe)
        assert cluster_report.acceptance_status == "unapproved"
        assert "story:overlap_pair_precision" in cluster_report.metrics
        with store.transaction():
            store.db.execute("DELETE FROM settings WHERE key='confirmation-opened'")
        assert evaluate(
            store, manifest(), partition, vectors, None, clusters=clusters
        ).state == "pilot-measured"
        assert store.setting("confirmation-opened") == digest(config)
        with pytest.raises(ValueError, match="already opened"):
            freeze_development(
                store, config.model_copy(update={"parameters": {"cosine_threshold": 0.8}}),
                partition,
            )
    finally:
        store.close()


def test_unknown_membership_quarantine_can_clear_without_redrawing_exposed_groups(
    work: Path,
) -> None:
    from idhazh.story_dataset.partitions import build_partition

    store = seeded_store(work)
    try:
        waiting = build_partition(store, manifest(), set(articles()), policy(), set())
        assert set(waiting.article_partitions.values()) == {"quarantine"}
        assert all(r == ["unknown-membership"] for r in waiting.quarantine_reasons.values())
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        completed = build_partition(
            store, manifest(), set(articles()), policy(), set(), previous=waiting
        )
        assert set(completed.article_partitions.values()) >= {"development", "confirmation"}
    finally:
        store.close()


def test_temporary_uncertainty_keeps_original_partition_exposure(work: Path) -> None:
    from idhazh.story_dataset.partitions import build_partition

    store = seeded_store(work)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        first = build_partition(store, manifest(), set(articles()), policy(), set())
        left = next(i for i, p in first.article_partitions.items() if p == "development")
        right = next(i for i, p in first.article_partitions.items() if p == "confirmation")
        uncertain_batch = export_batch(
            store, manifest(), articles(), policy(), article_ids=[left]
        )
        uncertain = answer(uncertain_batch, "uncertain-correction")
        uncertain.decisions[left] = uncertain.decisions[left].model_copy(update={
            "state": "unresolved", "memberships": [],
            "unresolved_reasons": ["Fixture evidence requires a correction."],
        })
        import_submission(store, manifest(), articles(), uncertain)
        waiting = build_partition(
            store, manifest(), set(articles()), policy(), set(), previous=first
        )
        assert waiting.article_partitions[left] == "quarantine"
        assert waiting.article_exposure[left] == "development"
        with store.transaction():
            store.set_setting("source", manifest().source_sha256)
        export_checkpoint(store.root, work / "exposure-epoch", manifest(), policy())
        replay = Store(work / "exposure-replay")
        try:
            restore_checkpoint(replay, work / "exposure-epoch", manifest(), policy())
            from idhazh.contracts.story_evaluation import Partition

            restored_waiting = replay.get(
                "partition", str(replay.setting("partition")), Partition
            )
            assert restored_waiting == waiting
            assert restored_waiting.article_exposure[left] == "development"
        finally:
            replay.close()
        corrected_batch = export_batch(
            store, manifest(), articles(), policy(), article_ids=[left]
        )
        corrected = answer(corrected_batch, "resolved-correction")
        corrected.decisions[left] = corrected.decisions[left].model_copy(update={
            "memberships": latest_annotations(store)[right].decision.memberships,
        })
        import_submission(store, manifest(), articles(), corrected)
        result = build_partition(
            store, manifest(), set(articles()), policy(), set(), previous=restored_waiting
        )
        assert result.article_partitions[left] == result.article_partitions[right] == "quarantine"
        assert "new-crossing-link" in result.quarantine_reasons[left]
    finally:
        store.close()


def test_pair_review_is_blind_independent_and_preserves_primary(work: Path) -> None:
    from idhazh.contracts.story_candidates import PairRecord, PairSubmission
    from idhazh.story_dataset.pair_workers import export_pairs, import_pairs
    from idhazh.story_dataset.sampling import build_pairs, pair_id

    store = Store(work)
    try:
        example = fixtures().examples[-1]
        identity = pair_id(example.a.article_id, example.b.article_id)
        frame = build_pairs(
            manifest(),
            articles(),
            policy().model_copy(update={"representative_pair_probability": 1}),
        )
        first = export_pairs(store, frame, articles(), 20, [identity])
        primary = PairSubmission(
            batch_id=first.batch_id,
            source_sha256=first.source_sha256,
            worker_id="pair-primary",
            decisions={identity: example.pair_decision},
        )
        import_pairs(store, primary)
        review = export_pairs(store, frame, articles(), 20, operation="review", audit_fraction=0)
        assert len(review.pairs) == 1 and b'"decision":' not in canonical(review)
        same = PairSubmission(
            batch_id=review.batch_id,
            source_sha256=review.source_sha256,
            operation="review",
            worker_id="pair-primary",
            independent_of=["pair-primary"],
            decisions={identity: example.pair_decision},
        )
        with pytest.raises(ValueError, match="independent"):
            import_pairs(store, same)
        assert import_pairs(store, same.model_copy(update={"worker_id": "pair-independent"})) == 1
        assert len(store.records("pair", PairRecord)) == 1
        assert len(store.records("pair-review", PairRecord)) == 1
    finally:
        store.close()


def test_source_backed_challenges_preserve_probability_and_need_evidence() -> None:
    from idhazh.contracts.story_candidates import ChallengeAddition, ChallengeProposal
    from idhazh.story_dataset.sampling import add_challenges, build_pairs

    example = fixtures().examples[-1]
    frame = build_pairs(
        manifest(),
        articles(),
        policy().model_copy(update={"representative_pair_probability": 1}),
    )
    proposal = ChallengeProposal(
        a=example.a.article_id,
        b=example.b.article_id,
        tags=["source-backed-extended-time"],
        reason=example.pair_decision.reason,
    )
    addition = ChallengeAddition(
        source_sha256=manifest().source_sha256,
        expected_frame_sha256=digest(frame),
        proposals=[proposal],
    )
    with pytest.raises(ValueError, match="source-check"):
        add_challenges(frame, addition, articles(), vector_fixture())
    proposal.source_checks = example.a_decision.source_checks
    updated = add_challenges(frame, addition, articles(), vector_fixture())
    assert len(updated.pairs) == len(frame.pairs)
    assert all(row.representative_probability == 1 for row in updated.pairs)
    assert any(row.source_checks and row.acquisition_notes for row in updated.pairs)


def test_vector_extension_reuses_real_rows_and_refuses_cross_input_hash(work: Path) -> None:
    import hashlib

    import numpy as np

    from idhazh.contracts.story_candidates import VectorExtension
    from idhazh.story_dataset.vector_files import snapshot_vectors, vector_path
    from idhazh.story_dataset.vectors import covered_ids, model_matrix, register_extension

    vectors = snapshot_vectors(work, vector_fixture())
    cache = next(cache for cache in vectors.caches if cache.slug == "gte-small")
    identity = vectors.article_ids[0]
    vectors.text_conflict_article_ids = [identity]
    path = work / "selected.npy"
    original = np.load(vector_path(vectors, cache.file, work), allow_pickle=False)
    np.save(path, original[:1], allow_pickle=False)
    extension = VectorExtension(
        source_sha256=vectors.source_sha256,
        slug=cache.slug,
        article_ids=[identity],
        article_input_sha256=[articles()[identity].input_sha256],
        summary_sha256=[hashlib.sha256(articles()[identity].source.summary.encode()).hexdigest()],
        cache=cache.model_copy(
            update={
                "rows": 1,
                "file": str(path.resolve()),
                "file_sha256": file_hash(path),
            }
        ),
        runtime_versions={"fixture": "recorded-real-saved-row"},
    )
    store = Store(work)
    try:
        broken = extension.model_copy(update={"article_input_sha256": ["0" * 64]})
        with pytest.raises(ValueError, match="hash"):
            register_extension(store, vectors, articles(), broken)
        valid_base = vectors.model_copy(update={"text_conflict_article_ids": []})
        with pytest.raises(ValueError, match="already-valid"):
            register_extension(store, valid_base, articles(), extension)
        assert store.setting("vectors") is None
        updated = register_extension(store, vectors, articles(), extension)
        assert identity in covered_ids(updated, cache.slug)
        assert identity not in covered_ids(updated)
        model_ids, matrix = model_matrix(updated, cache.slug, work)
        np.testing.assert_array_equal(matrix[model_ids.index(identity)], original[0])
        assert register_extension(store, updated, articles(), extension) == updated
        from idhazh.story_dataset.vectors import ranked_neighbors

        neighbors = ranked_neighbors(updated, [identity], 1, 1, work)
        evidence = [
            item for group in neighbors.values() for item in group if item.model == cache.slug
        ]
        assert evidence and evidence[0].query_vector_sha256 == extension.cache.file_sha256
        assert evidence[0].neighbor_vector_sha256 == cache.file_sha256
        assert evidence[0].vector_sha256 == digest({
            "query": extension.cache.file_sha256, "neighbor": cache.file_sha256
        })
    finally:
        store.close()


def copied_legacy_vectors(work: Path) -> tuple[VectorManifest, dict[str, Path]]:
    """Use small real slices, with checkout evidence separate from a stable cache."""
    vectors = vector_fixture()
    checkout = work / "old-checkout"
    checkout.mkdir()
    for field in ("input_file", "readings_file", "encoder_config_file"):
        target = checkout / (field + ".json")
        shutil.copyfile(getattr(vectors, field), target)
        setattr(vectors, field, str(target.resolve()))
    cache_root = work / "session-cache"
    cache_root.mkdir()
    for cache in vectors.caches:
        target = cache_root / (cache.slug + ".npy")
        shutil.copyfile(cache.file, target)
        cache.file = str(target.resolve())
    moved = work / "new-checkout"
    shutil.move(checkout, moved)
    return vectors, {
        vectors.input_sha256: moved / "input_file.json",
        vectors.readings_sha256: moved / "readings_file.json",
        vectors.encoder_config_sha256: moved / "encoder_config_file.json",
    }


def save_legacy_vectors(store: Store, vectors: VectorManifest) -> str:
    revision = digest(vectors)
    with store.transaction():
        store.save("vectors", revision, vectors)
        store.set_setting("vectors", revision)
    return revision


def test_vector_relocation_preserves_history_bytes_settings_order_and_rankings(work: Path) -> None:
    import numpy as np

    from idhazh.contracts.story_vectors import VectorSnapshot
    from idhazh.story_dataset.vector_files import read_vectors, relocate_vectors, vector_path
    from idhazh.story_dataset.vectors import covered_ids, model_matrix, ranked_neighbors

    original, replacements = copied_legacy_vectors(work)
    original.text_conflict_article_ids = original.article_ids[:1]
    legacy_bytes = canonical(original)
    saved_files = {cache.file: Path(cache.file).read_bytes() for cache in original.caches}
    root = work / "dataset"
    store = seeded_store(root)
    try:
        batch = export_batch(store, manifest(), articles(), policy())
        import_submission(store, manifest(), articles(), answer(batch))
        history_before = canonical(store.records("annotation", AnnotationRecord))
        revision = save_legacy_vectors(store, original)
        assert canonical(read_vectors(store, revision)) == legacy_bytes
        output = root / "vectors-relocated.json"
        snapshot = relocate_vectors(store, revision, replacements, output)
        assert snapshot.previous_revision == revision
        assert store.setting("vectors") == digest(snapshot)
        assert canonical(read_vectors(store, revision)) == legacy_bytes
        assert canonical(store.records("annotation", AnnotationRecord)) == history_before
        assert read_vectors(store, digest(snapshot)) == snapshot
        assert read_model(output, VectorSnapshot) == snapshot
        before = original.model_dump(exclude={"input_file", "readings_file", "encoder_config_file"})
        after = snapshot.model_dump(
            exclude={
                "version",
                "path_base",
                "previous_revision",
                "input_file",
                "readings_file",
                "encoder_config_file",
            }
        )
        for old_cache, new_cache in zip(before["caches"], after["caches"], strict=True):
            old_cache.pop("file")
            new_cache.pop("file")
        assert before == after
        for cache in snapshot.caches:
            assert not Path(cache.file).is_absolute() and "\\" not in cache.file
            old = next(c for c in original.caches if c.slug == cache.slug)
            assert vector_path(snapshot, cache.file, root).read_bytes() == saved_files[old.file]
            assert Path(old.file).read_bytes() == saved_files[old.file]
            old_ids, old_matrix = model_matrix(original, cache.slug)
            new_ids, new_matrix = model_matrix(snapshot, cache.slug, root)
            assert new_ids == old_ids
            np.testing.assert_array_equal(new_matrix, old_matrix)
        assert covered_ids(snapshot) == covered_ids(original)
        queries = snapshot.article_ids[:2]
        ranks = ranked_neighbors(snapshot, queries, 3, 2, root)
    finally:
        store.close()
    moved_root = work / "moved-dataset"
    shutil.move(root, moved_root)
    shutil.rmtree(work / "new-checkout")
    shutil.rmtree(work / "session-cache")
    reopened = Store(moved_root)
    try:
        moved_snapshot = read_vectors(reopened, str(reopened.setting("vectors")))
        assert canonical(moved_snapshot) == canonical(snapshot)
        assert ranked_neighbors(moved_snapshot, queries, 3, 2, moved_root) == ranks
        assert dataset_status(reopened, manifest()).vector_covered == len(covered_ids(snapshot))
    finally:
        reopened.close()


@pytest.mark.parametrize("target", ["input", "readings", "config", "cache", "foreign", "stale"])
def test_vector_relocation_fails_closed_before_registering_a_revision(
    work: Path, target: str
) -> None:
    from idhazh.story_dataset.vector_files import relocate_vectors

    original, replacements = copied_legacy_vectors(work)
    store = Store(work / "dataset")
    try:
        revision = save_legacy_vectors(store, original)
        before = canonical(original)
        if target in ("input", "readings", "config"):
            selected = {
                "input": original.input_sha256,
                "readings": original.readings_sha256,
                "config": original.encoder_config_sha256,
            }[target]
            replacements[selected].write_bytes(b"Different bytes.\n")
        elif target == "cache":
            Path(original.caches[0].file).write_bytes(b"Different vector bytes.\n")
        elif target == "foreign":
            replacements["0" * 64] = next(iter(replacements.values()))
        output = store.root / "new-vectors.json"
        with pytest.raises(ValueError):
            relocate_vectors(
                store, "0" * 64 if target == "stale" else revision, replacements, output
            )
        assert store.setting("vectors") == revision
        assert canonical(store.get("vectors", revision, VectorManifest)) == before
        assert store.db.execute("SELECT count(*) FROM artifacts").fetchone()[0] == 1
        assert not output.exists() and not (store.root / "vector-evidence").exists()
    finally:
        store.close()


def test_vector_relocation_refuses_immutable_output_and_corrupt_snapshot_objects(
    work: Path,
) -> None:
    from idhazh.story_dataset.vector_files import relocate_vectors

    original, replacements = copied_legacy_vectors(work)
    store = Store(work / "dataset")
    try:
        revision = save_legacy_vectors(store, original)
        output = store.root / "historical-vectors.json"
        output.write_bytes(canonical(original))
        with pytest.raises(ValueError, match="immutable artifact"):
            relocate_vectors(store, revision, replacements, output)
        assert store.setting("vectors") == revision and output.read_bytes() == canonical(original)
        target = store.root / "vector-evidence" / (original.input_sha256 + ".json")
        target.write_bytes(b"Corrupt previously copied bytes.\n")
        with pytest.raises(ValueError, match="immutable vector evidence"):
            relocate_vectors(store, revision, replacements, store.root / "new.json")
        assert target.read_bytes() == b"Corrupt previously copied bytes.\n"
        assert store.setting("vectors") == revision
    finally:
        store.close()


@pytest.mark.parametrize(
    "path", ["../escape.npy", "C:\\old\\file.npy", "/absolute.npy", "a\\b.npy"]
)
def test_vector_snapshot_contract_refuses_nonportable_paths(work: Path, path: str) -> None:
    from idhazh.contracts.story_vectors import VectorSnapshot
    from idhazh.story_dataset.vector_files import snapshot_vectors

    snapshot = snapshot_vectors(work, vector_fixture())
    data = snapshot.model_dump(mode="json")
    data["caches"][0]["file"] = path
    with pytest.raises(ValidationError):
        VectorSnapshot.model_validate(data)


def test_portable_vectors_require_explicit_root_and_hash_unchanged_copied_evidence(
    work: Path,
) -> None:
    from idhazh.story_dataset.vector_files import snapshot_vectors, vector_path
    from idhazh.story_dataset.vectors import validate_vectors

    snapshot = snapshot_vectors(work, vector_fixture())
    with pytest.raises(ValueError, match="dataset root"):
        validate_vectors(snapshot)
    validate_vectors(snapshot, work)
    path = vector_path(snapshot, snapshot.caches[0].file, work)
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="saved vector bytes changed"):
        validate_vectors(snapshot, work)


def test_initial_vector_registration_creates_portable_evidence_not_absolute_paths(
    work: Path,
) -> None:
    import hashlib

    from idhazh.contracts.encoder_reading import EncoderReading, ReadingState
    from idhazh.contracts.story_vectors import VectorSnapshot
    from idhazh.story_dataset.vector_files import read_vectors, vector_path
    from idhazh.story_dataset.vectors import register_vectors, validate_vectors

    original = vector_fixture()
    source = work / "encoder-input.json"
    summaries = [articles()[identity].source.summary for identity in original.article_ids]
    source.write_bytes(
        canonical(
            {
                "urls": [articles()[identity].source.url for identity in original.article_ids],
                "texts": summaries,
            }
        )
    )
    input_hash = file_hash(source)
    readings = [
        EncoderReading(
            slug=cache.slug,
            model_id=cache.model_id,
            parameters_millions=0,
            why="Real saved-vector fixture registration.",
            state=ReadingState.MEASURED,
            written_at=now(),
            articles_to_encode=len(summaries),
            articles_done=len(summaries),
            numbers_an_article=cache.dimensions,
            pair_set_sha256=input_hash,
            separation=0.5,
        )
        for cache in original.caches
    ]
    readings_path = work / "readings.json"
    readings_path.write_bytes(canonical({"encoders": readings}))
    config_path = work / "config.json"
    config_path.write_bytes(canonical({"encode": {"max_sequence_length": 256}}))
    frozen = manifest().model_copy(
        update={"regression_hashes": {"corpus/encoder-comparison-1/pairs.json": input_hash}}
    )
    store = Store(work / "dataset")
    try:
        saved = register_vectors(
            store,
            frozen,
            articles(),
            source,
            readings_path,
            {c.slug: Path(c.file) for c in original.caches},
            config_path,
        )
        assert isinstance(saved, VectorSnapshot) and saved.previous_revision is None
        assert saved.article_ids == original.article_ids
        assert saved.text_sha256 == [
            hashlib.sha256(text.encode()).hexdigest() for text in summaries
        ]
        validate_vectors(saved, store.root)
        assert read_vectors(store, digest(saved)) == saved
        assert vector_path(saved, saved.input_file, store.root).read_bytes() == source.read_bytes()
        assert saved.missing_article_ids == original.missing_article_ids
        with pytest.raises(ValueError, match="relocate-vectors"):
            register_vectors(
                store,
                frozen,
                articles(),
                source,
                readings_path,
                {c.slug: Path(c.file) for c in original.caches},
                config_path,
            )
    finally:
        store.close()


def test_vector_extension_snapshot_and_lineage_survive_dataset_move(work: Path) -> None:
    import hashlib

    import numpy as np

    from idhazh.contracts.story_candidates import VectorExtension
    from idhazh.contracts.story_vectors import VectorExtensionSnapshot
    from idhazh.story_dataset.vector_files import read_vectors, snapshot_vectors, vector_path
    from idhazh.story_dataset.vectors import model_matrix, register_extension, validate_vectors

    root = work / "dataset"
    snapshot = snapshot_vectors(root, vector_fixture())
    identity = snapshot.article_ids[0]
    snapshot.text_conflict_article_ids = [identity]
    cache = snapshot.caches[0]
    array = np.load(vector_path(snapshot, cache.file, root), allow_pickle=False)[:1]
    external = work / "selected-external.npy"
    np.save(external, array, allow_pickle=False)
    extension = VectorExtension(
        source_sha256=snapshot.source_sha256,
        slug=cache.slug,
        article_ids=[identity],
        article_input_sha256=[articles()[identity].input_sha256],
        summary_sha256=[hashlib.sha256(articles()[identity].source.summary.encode()).hexdigest()],
        cache=cache.model_copy(
            update={"rows": 1, "file": str(external.resolve()), "file_sha256": file_hash(external)}
        ),
        runtime_versions={"fixture": "recorded-real-saved-row"},
    )
    store = Store(root)
    try:
        initial_revision = save_legacy_vectors(store, snapshot)
        before = canonical(read_vectors(store, initial_revision))
        wrong_model = extension.model_copy(
            update={"cache": extension.cache.model_copy(update={"model_id": "different-model"})}
        )
        with pytest.raises(ValueError, match="settings/revision"):
            register_extension(store, snapshot, articles(), wrong_model)
        updated = register_extension(store, snapshot, articles(), extension)
        assert updated.previous_revision == initial_revision
        assert canonical(read_vectors(store, initial_revision)) == before
        relative = updated.extensions[0]
        descriptor = VectorExtensionSnapshot(
            **relative.model_dump(mode="json"), path_base="dataset-root"
        )
        assert register_extension(store, updated, articles(), descriptor) == updated
        assert (
            relative.cache.file.startswith("vector-evidence/") and "\\" not in relative.cache.file
        )
        expected_bytes = external.read_bytes()
    finally:
        store.close()
    external.unlink()
    moved = work / "moved-dataset"
    shutil.move(root, moved)
    reopened = Store(moved)
    try:
        selected = read_vectors(reopened, str(reopened.setting("vectors")))
        validate_vectors(selected, moved)
        assert (
            vector_path(selected, selected.extensions[0].cache.file, moved).read_bytes()
            == expected_bytes
        )
        ids, matrix = model_matrix(selected, cache.slug, moved)
        np.testing.assert_array_equal(matrix[ids.index(identity)], array[0])
    finally:
        reopened.close()


def test_relocation_cli_uses_explicit_hash_mappings_and_preserves_legacy_export(work: Path) -> None:
    import os
    import subprocess
    import sys

    from idhazh.contracts.story_vectors import VectorSnapshot
    from idhazh.story_dataset.source import REGRESSION_FILES
    from idhazh.story_dataset.vector_files import read_vectors

    old, replacements = copied_legacy_vectors(work)
    repository = work / "generated-repository"
    for name in REGRESSION_FILES:
        target = repository / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"Bounded generated regression fixture.\n")
    root = work / "dataset"
    root.mkdir()
    source = root / "articles.jsonl"
    source.write_bytes(b"".join(canonical(row.source) for row in articles().values()))
    selected_policy = policy().model_copy(
        update={
            "expected_articles": len(articles()),
            "expected_bytes": source.stat().st_size,
            "expected_sha256": file_hash(source),
        }
    )
    frozen = freeze(root, repository, selected_policy, FIXTURE / "approved.json")
    old.source_sha256 = frozen.source_sha256
    legacy = root / "vectors.json"
    legacy.write_bytes(canonical(old))
    store = Store(root)
    try:
        revision = save_legacy_vectors(store, old)
    finally:
        store.close()
    policy_path = work / "policy.json"
    policy_path.write_bytes(canonical(selected_policy))
    output = root / "vectors-relocated.json"
    command = [
        sys.executable,
        "-m",
        "idhazh.story_dataset.cli",
        "--repository",
        str(repository.resolve()),
        "--root",
        str(root.resolve()),
        "--policy",
        str(policy_path.resolve()),
        "relocate-vectors",
        "--expected-revision",
        revision,
        "--output",
        str(output.resolve()),
    ]
    for sha256, path in replacements.items():
        command.extend(["--file", f"{sha256}={path.resolve()}"])
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(Path("backend").resolve())},
    )
    assert result.returncode == 0, result.stderr
    assert "no input or vector bytes changed" in result.stdout
    snapshot = read_model(output, VectorSnapshot)
    store = Store(root)
    try:
        assert read_vectors(store, str(store.setting("vectors"))) == snapshot
        assert legacy.read_bytes() == canonical(old)
    finally:
        store.close()


@pytest.mark.parametrize("mutation", [None, "input", "settings", "existing-output"])
def test_selected_encoding_resumes_portable_bytes_without_loading_a_model(
    work: Path, mutation: str | None
) -> None:
    import hashlib

    import numpy as np

    from idhazh.contracts.encoder_reading import EncoderReading, ReadingState
    from idhazh.contracts.story_vectors import VectorExtensionSnapshot
    from idhazh.story_dataset.encoding import encode_selected
    from idhazh.story_dataset.vector_files import snapshot_file, snapshot_vectors, vector_path

    frozen_articles = articles()
    vectors = vector_fixture()
    cache = vectors.caches[0]
    reading = EncoderReading(
        slug=cache.slug,
        model_id=cache.model_id,
        parameters_millions=0,
        why="Generated pinned reading for descriptor-validation tests; no model run.",
        state=ReadingState.MEASURED,
        written_at=now(),
        articles_to_encode=len(vectors.article_ids),
        articles_done=len(vectors.article_ids),
        numbers_an_article=cache.dimensions,
        separation=0.5,
        pair_set_sha256=vectors.input_sha256,
        model_options={"revision": "1" * 40},
    )
    readings_path = work / "generated-readings.json"
    readings_path.write_bytes(canonical({"encoders": [reading]}))
    vectors.readings_file = str(readings_path.resolve())
    vectors.readings_sha256 = file_hash(readings_path)
    cache.reading_sha256 = digest(reading)
    cache.revision = "1" * 40
    cache.settings_sha256 = digest(
        {
            "prefix": reading.prefix,
            "model_options": reading.model_options,
            "encode_options": reading.encode_options,
        }
    )
    root = work / "dataset"
    snapshot = snapshot_vectors(root, vectors)
    output = work / "selected.npy"
    selected = snapshot.article_ids[:1]
    summaries = [frozen_articles[i].source.summary for i in selected]
    raw_vectors = work / "recorded-subset.npy"
    np.save(
        raw_vectors,
        np.load(vector_path(snapshot, snapshot.caches[0].file, root))[:1],
        allow_pickle=False,
    )
    expected_hash = file_hash(raw_vectors)
    descriptor = VectorExtensionSnapshot(
        path_base="dataset-root",
        source_sha256=snapshot.source_sha256,
        slug=cache.slug,
        article_ids=selected,
        article_input_sha256=[frozen_articles[i].input_sha256 for i in selected],
        summary_sha256=[hashlib.sha256(text.encode()).hexdigest() for text in summaries],
        cache=cache.model_copy(
            update={
                "rows": 1,
                "file": snapshot_file(root, raw_vectors, expected_hash, ".npy"),
                "file_sha256": expected_hash,
                "input_sha256": digest(summaries),
            }
        ),
        runtime_versions={"fixture": "recorded-real-saved-row"},
    )
    if mutation == "input":
        descriptor.article_input_sha256 = ["0" * 64]
    elif mutation == "settings":
        descriptor.cache.settings_sha256 = "0" * 64
    if mutation == "existing-output":
        output.write_bytes(raw_vectors.read_bytes())
        with pytest.raises(ValueError, match="already exists"):
            encode_selected(frozen_articles, snapshot, selected, cache.slug, policy(), output, root)
        assert file_hash(output) == expected_hash
        return
    output.with_suffix(".json").write_bytes(canonical(descriptor))
    raw_vectors.unlink()
    if mutation:
        with pytest.raises(ValueError, match="resumed"):
            encode_selected(frozen_articles, snapshot, selected, cache.slug, policy(), output, root)
    else:
        before = output.with_suffix(".json").read_bytes()
        resumed = encode_selected(
            frozen_articles, snapshot, selected, cache.slug, policy(), output, root
        )
        assert resumed == descriptor and output.with_suffix(".json").read_bytes() == before
        assert file_hash(vector_path(resumed, resumed.cache.file, root)) == expected_hash
        assert not output.exists()
