"""How can a consistent worker state be frozen and resumed without committing SQLite?"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, cast

from idhazh.contracts.base import Model
from idhazh.contracts.story_annotation import (
    AnnotationRecord,
    CatalogReview,
    CatalogSnapshot,
    CheckpointArtifact,
    CheckpointFile,
    CheckpointRecord,
    DatasetCheckpoint,
    WorkerBatch,
    WorkerSubmission,
)
from idhazh.contracts.story_candidates import PairRecord, PairSubmission, PairWorkerBatch
from idhazh.contracts.story_evaluation import Partition, StoryPolicy
from idhazh.contracts.story_source import SourceFreeze
from idhazh.contracts.story_vectors import VectorSnapshot
from idhazh.story_dataset.catalog import empty_catalog
from idhazh.story_dataset.storage import (
    Store,
    canonical,
    digest,
    file_hash,
    now,
    read_model,
    write_model,
)

ARTIFACT_MODELS: dict[str, type[Model]] = {
    "batch": WorkerBatch,
    "pair-batch": PairWorkerBatch,
    "submission": WorkerSubmission,
    "pair-submission": PairSubmission,
}
RECORD_MODELS: dict[str, type[Model]] = {
    "annotation": AnnotationRecord,
    "review": AnnotationRecord,
    "pair": PairRecord,
    "pair-review": PairRecord,
    "catalog-review": CatalogReview,
}
ArtifactKind = Literal["batch", "pair-batch", "submission", "pair-submission"]
BindingKind = Literal["batch-submission", "pair-batch-submission"]


def rebuild_catalog(current: CatalogSnapshot, review: CatalogReview) -> CatalogSnapshot:
    if current.revision != review.expected_revision:
        raise ValueError("checkpoint catalog history is not contiguous")
    entities = {item.id: item for item in current.entities}
    for item in review.entities:
        if item.id in entities and entities[item.id] != item:
            raise ValueError("checkpoint changes an immutable catalog identity")
        entities[item.id] = item
    return CatalogSnapshot(
        revision=digest({"previous": current.revision, "review": review}),
        entities=list(entities.values()),
        aliases={**current.aliases, **review.aliases},
        proposal_resolutions={**current.proposal_resolutions, **review.proposal_resolutions},
    )


def publish_lines(path: Path, lines: Iterator[bytes]) -> CheckpointFile:
    if path.exists():
        raise ValueError("checkpoint output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    rows = 0
    try:
        with part.open("xb") as stream:
            for line in lines:
                stream.write(line)
                rows += 1
        part.rename(path)
    finally:
        part.unlink(missing_ok=True)
    return CheckpointFile(
        path=path.name, sha256=file_hash(path), bytes=path.stat().st_size, rows=rows
    )


def export_checkpoint(
    root: Path, output: Path, manifest: SourceFreeze, policy: StoryPolicy
) -> DatasetCheckpoint:
    """A read transaction fixes every SELECT to one epoch, even with active workers."""
    if output.exists():
        raise ValueError("use a new immutable checkpoint directory")
    db = sqlite3.connect((root / "state.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("BEGIN")
    try:
        settings = dict(db.execute("SELECT key,value FROM settings"))
        if settings.get("source") != manifest.source_sha256:
            raise ValueError("checkpoint database belongs to a different source")
        files: dict[
            Literal["artifacts", "history", "catalog", "vectors", "partition"], CheckpointFile
        ] = {}

        def artifacts() -> Iterator[bytes]:
            for kind in ARTIFACT_MODELS:
                for identity, raw in db.execute(
                    "SELECT id,payload FROM artifacts WHERE kind=? ORDER BY id", (kind,)
                ):
                    value = ARTIFACT_MODELS[kind].model_validate_json(raw)
                    if kind in ("submission", "pair-submission"):
                        if digest(value) != identity:
                            raise ValueError("submission identity differs from its payload")
                        value = value.model_copy(update={"decisions": {}})
                    yield canonical(
                        CheckpointArtifact(
                            kind=cast(ArtifactKind, kind),
                            id=identity, payload=json.loads(canonical(value))
                        )
                    )

        catalog = empty_catalog()

        def history() -> Iterator[bytes]:
            nonlocal catalog
            for sequence, kind, identity, subject, raw in db.execute(
                "SELECT sequence,kind,id,subject,payload FROM records ORDER BY sequence"
            ):
                if kind not in RECORD_MODELS:
                    raise ValueError(f"unsupported checkpoint record kind: {kind}")
                value = RECORD_MODELS[kind].model_validate_json(raw)
                if isinstance(value, CatalogReview):
                    catalog = rebuild_catalog(catalog, value)
                    saved = db.execute(
                        "SELECT payload FROM artifacts WHERE kind='catalog' AND id=?",
                        (catalog.revision,),
                    ).fetchone()
                    if (
                        subject != catalog.revision
                        or saved is None
                        or saved[0] != canonical(catalog).decode()
                    ):
                        raise ValueError("catalog replay differs from the saved immutable snapshot")
                yield canonical(
                    CheckpointRecord(
                        sequence=sequence,
                        kind=kind,
                        id=identity,
                        subject=subject,
                        payload=json.loads(canonical(value)),
                    )
                )

        files["artifacts"] = publish_lines(output / "artifacts.jsonl", artifacts())
        files["history"] = publish_lines(output / "history.jsonl", history())
        if settings.get("catalog", empty_catalog().revision) != catalog.revision:
            raise ValueError("checkpoint catalog tip differs from its history")
        write_model(output / "catalog.json", catalog)
        files["catalog"] = CheckpointFile(
            path="catalog.json",
            sha256=file_hash(output / "catalog.json"),
            bytes=(output / "catalog.json").stat().st_size,
            rows=1,
        )
        vector_id = settings.get("vectors")
        if vector_id:
            raw = db.execute(
                "SELECT payload FROM artifacts WHERE kind='vectors' AND id=?", (vector_id,)
            ).fetchone()
            if raw is None:
                raise ValueError("checkpoint vector revision is missing")
            vectors = VectorSnapshot.model_validate_json(raw[0])
            if digest(vectors) != vector_id or vectors.source_sha256 != manifest.source_sha256:
                raise ValueError("checkpoint vector identity differs")
            write_model(output / "vectors.json", vectors)
            files["vectors"] = CheckpointFile(
                path="vectors.json",
                sha256=file_hash(output / "vectors.json"),
                bytes=(output / "vectors.json").stat().st_size,
                rows=1,
            )
        partition_id = settings.get("partition")
        if partition_id:
            saved_partition = db.execute(
                "SELECT payload FROM artifacts WHERE kind='partition' AND id=?", (partition_id,)
            ).fetchone()
            if saved_partition is None:
                raise ValueError("checkpoint partition revision is missing")
            partition = Partition.model_validate_json(saved_partition[0])
            if digest(partition) != partition_id:
                raise ValueError("checkpoint partition identity differs")
            write_model(output / "partition.json", partition)
            files["partition"] = CheckpointFile(
                path="partition.json", sha256=file_hash(output / "partition.json"),
                bytes=(output / "partition.json").stat().st_size, rows=1,
            )
        bindings: dict[Literal["batch-submission", "pair-batch-submission"], dict[str, str]] = {}
        for kind, model in (
            ("batch-submission", WorkerSubmission),
            ("pair-batch-submission", PairSubmission),
        ):
            bindings[cast(BindingKind, kind)] = {
                identity: digest(model.model_validate_json(raw))
                for identity, raw in db.execute(
                    "SELECT id,payload FROM artifacts WHERE kind=?", (kind,)
                )
            }
        omitted: dict[str, list[str]] = {}
        for kind, identity in db.execute("SELECT kind,id FROM artifacts ORDER BY kind,id"):
            if kind in ARTIFACT_MODELS or kind in bindings or kind == "catalog":
                continue
            if kind == "vectors" and identity == vector_id:
                continue
            if kind == "partition" and identity == partition_id:
                continue
            omitted.setdefault(kind, []).append(identity)
        result = DatasetCheckpoint(
            recorded_at=now(),
            source_sha256=manifest.source_sha256,
            policy_sha256=digest(policy),
            files=files,
            settings=settings,
            submission_bindings=bindings,
            omitted_artifacts=omitted,
        )
        write_model(output / "checkpoint.json", result)
        return result
    finally:
        db.rollback()
        db.close()


def restore_checkpoint(
    store: Store, checkpoint: Path, manifest: SourceFreeze, policy: StoryPolicy
) -> DatasetCheckpoint:
    """Restore atomically into an empty local index; omitted evidence stays explicit."""
    value = read_model(checkpoint / "checkpoint.json", DatasetCheckpoint)
    if value.source_sha256 != manifest.source_sha256 or value.policy_sha256 != digest(policy):
        raise ValueError("checkpoint source or policy differs")
    for entry in value.files.values():
        path = (checkpoint / entry.path).resolve()
        if not path.is_relative_to(checkpoint.resolve()):
            raise ValueError("checkpoint file escapes its root")
        if path.stat().st_size != entry.bytes or file_hash(path) != entry.sha256:
            raise ValueError("checkpoint file hash or size differs")
    with store.transaction():
        for table in ("records", "artifacts", "settings"):
            if store.db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise ValueError("checkpoint restore requires an empty index")
        catalog = empty_catalog()
        store.save("catalog", catalog.revision, catalog)
        decisions: dict[str, dict[str, object]] = {}
        with (checkpoint / value.files["history"].path).open("rb") as stream:
            previous = 0
            for line in stream:
                row = CheckpointRecord.model_validate_json(line)
                if row.sequence <= previous:
                    raise ValueError("checkpoint record sequence is not increasing")
                previous = row.sequence
                record = RECORD_MODELS[row.kind].model_validate(row.payload)
                if isinstance(record, CatalogReview):
                    if digest(record) != row.id:
                        raise ValueError("catalog review identity differs")
                    catalog = rebuild_catalog(catalog, record)
                    if catalog.revision != row.subject:
                        raise ValueError("catalog review revision differs")
                    store.save("catalog", catalog.revision, catalog)
                elif isinstance(record, (AnnotationRecord, PairRecord)):
                    if record.record_id != row.id:
                        raise ValueError("history record identity differs")
                    subject = (
                        record.article_id
                        if isinstance(record, AnnotationRecord)
                        else record.pair_id
                    )
                    decisions.setdefault(record.submission_sha256, {})[subject] = record.decision
                store.db.execute(
                    "INSERT INTO records(sequence,kind,id,subject,payload) VALUES(?,?,?,?,?)",
                    (row.sequence, row.kind, row.id, row.subject, canonical(record).decode()),
                )
        if catalog != read_model(checkpoint / value.files["catalog"].path, CatalogSnapshot):
            raise ValueError("restored catalog differs from the checkpoint")
        with (checkpoint / value.files["artifacts"].path).open("rb") as stream:
            for line in stream:
                artifact = CheckpointArtifact.model_validate_json(line)
                model = ARTIFACT_MODELS[artifact.kind].model_validate(artifact.payload)
                if artifact.kind in ("submission", "pair-submission"):
                    data = model.model_dump()
                    data["decisions"] = decisions.get(artifact.id, {})
                    model = ARTIFACT_MODELS[artifact.kind].model_validate(data)
                    if digest(model) != artifact.id:
                        raise ValueError("reconstructed submission differs from its identity")
                store.save(artifact.kind, artifact.id, model)
        for kind, bindings in value.submission_bindings.items():
            source_kind = "submission" if kind == "batch-submission" else "pair-submission"
            for batch_id, submission_id in bindings.items():
                model = store.get(source_kind, submission_id, ARTIFACT_MODELS[source_kind])
                store.save(kind, batch_id, model)
        if "vectors" in value.files:
            vectors = read_model(checkpoint / value.files["vectors"].path, VectorSnapshot)
            if digest(vectors) != value.settings.get("vectors"):
                raise ValueError("restored vector revision differs")
            store.save("vectors", digest(vectors), vectors)
        if "partition" in value.files:
            partition = read_model(checkpoint / value.files["partition"].path, Partition)
            if digest(partition) != value.settings.get("partition"):
                raise ValueError("restored partition revision differs")
            store.save("partition", digest(partition), partition)
        for key, setting in value.settings.items():
            if key in ("partition", "pair-frame") and any(
                setting in identities for identities in value.omitted_artifacts.values()
            ):
                continue
            store.set_setting(key, setting)
    return value
