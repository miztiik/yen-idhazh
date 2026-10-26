"""Which identities does a checkpoint take once its evidence paths are portable?"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from collections import defaultdict, deque
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from idhazh.contracts.base import Model
from idhazh.contracts.story_annotation import (
    AnnotationRecord,
    CatalogReview,
    CatalogSnapshot,
    DatasetCheckpoint,
    WorkerBatch,
    WorkerSubmission,
)
from idhazh.contracts.story_candidates import PairRecord, PairSubmission, PairWorkerBatch
from idhazh.contracts.story_source import SourceFreeze
from idhazh.contracts.story_vectors import VectorSnapshot
from idhazh.story_dataset.catalog import empty_catalog
from idhazh.story_dataset.checkpoints import (
    ARTIFACT_MODELS,
    RECORD_MODELS,
    export_checkpoint,
    rebuild_catalog,
    restore_checkpoint,
)
from idhazh.story_dataset.portable_evidence import LOCAL_ABSOLUTE_PATH
from idhazh.story_dataset.source import load_policy
from idhazh.story_dataset.storage import Store, canonical, digest, read_model, write_model

MODELS: dict[str, type[Model]] = {**ARTIFACT_MODELS, **RECORD_MODELS, "vectors": VectorSnapshot}
BINDING_SUBMISSION: dict[str, type[Model]] = {
    "batch-submission": WorkerSubmission,
    "pair-batch-submission": PairSubmission,
}
IDENTITY_FIELD: dict[str, str] = {
    "batch": "batch_id",
    "pair-batch": "batch_id",
    "annotation": "record_id",
    "review": "record_id",
    "pair": "record_id",
    "pair-review": "record_id",
}
REFERENCE_POOLS: dict[str, str] = {
    "batch_id": "batches",
    "submission_sha256": "submissions",
    "catalog_revision": "revisions",
    "expected_revision": "revisions",
    "supersedes": "records",
    "review_target": "records",
    "review_targets": "records",
    "correction_targets": "records",
}


@dataclass(frozen=True)
class Node:
    kind: str
    key: str
    payload: dict[str, Any]
    sequence: int | None
    subject: str | None


def portable_reference(path: str) -> str:
    name = re.split(r"[\\/]", path)[-1]
    if not name:
        raise ValueError("an absolute evidence path must end in a file name")
    return name


DRIVE_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s\"'<>|,;)\]}]*")


def scrub_local_paths(text: str) -> str:
    """Prose keeps a local file name only, because a folder name can name a person."""

    def replace(match: re.Match[str]) -> str:
        name = re.split(r"[\\/]", match.group(0))[-1]
        return name if PurePosixPath(name).suffix else "<local folder>"

    return DRIVE_PATH.sub(replace, text)


def rewrite(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: rewrite_field(key, item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite(item, mapping) for item in value]
    if isinstance(value, str):
        return mapping[value] if value in mapping else scrub_local_paths(value)
    return value


def rewrite_field(key: str, value: Any, mapping: dict[str, str]) -> Any:
    if key == "evidence_reference" and isinstance(value, str) and LOCAL_ABSOLUTE_PATH.match(value):
        return portable_reference(value)
    return rewrite(value, mapping)


def strings(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def identity_of(model: Model) -> str:
    """Each formula is the one the worker or the catalog uses to name the object."""
    if isinstance(model, WorkerBatch):
        return digest(
            {
                "source": model.source_sha256,
                "policy": model.policy_sha256,
                "operation": model.operation,
                "catalog": model.catalog_revision,
                "articles": [article.article_id for article in model.articles],
                "targets": model.review_targets,
                "corrections": model.correction_targets,
            }
        )
    if isinstance(model, PairWorkerBatch):
        return digest(
            {
                "frame": model.frame_sha256,
                "pairs": [pair.pair_id for pair in model.pairs],
                "operation": model.operation,
                "targets": model.review_targets,
                "corrections": model.correction_targets,
            }
        )
    if isinstance(model, AnnotationRecord):
        return digest({"submission": model.submission_sha256, "article": model.article_id})
    if isinstance(model, PairRecord):
        return digest({"submission": model.submission_sha256, "pair": model.pair_id})
    return digest(model)


def load_nodes(store: Store) -> tuple[dict[str, Node], list[tuple[str, str, dict[str, Any]]]]:
    nodes: dict[str, Node] = {}
    for sequence, kind, identity, subject, raw in store.db.execute(
        "SELECT sequence,kind,id,subject,payload FROM records ORDER BY sequence"
    ):
        nodes[identity] = Node(kind, identity, json.loads(raw), sequence, subject)
    bindings: list[tuple[str, str, dict[str, Any]]] = []
    for kind, identity, raw in store.db.execute("SELECT kind,id,payload FROM artifacts"):
        if kind == "catalog":
            continue
        if kind in BINDING_SUBMISSION:
            bindings.append((kind, identity, json.loads(raw)))
        elif kind in MODELS:
            nodes[identity] = Node(kind, identity, json.loads(raw), None, None)
        else:
            raise ValueError(f"unsupported artifact kind in checkpoint: {kind}")
    return nodes, bindings


def check_identities(nodes: dict[str, Node]) -> None:
    """Refuse to re-key unless every saved identity follows its formula."""
    for node in nodes.values():
        model = MODELS[node.kind].model_validate(node.payload)
        field = IDENTITY_FIELD.get(node.kind)
        if identity_of(model) != node.key or (field and node.payload[field] != node.key):
            raise ValueError(f"{node.kind} identity does not follow its formula")


def revision_producers(nodes: dict[str, Node]) -> tuple[dict[str, str], dict[str, str]]:
    """Map each catalog revision to the review that produced it, and each review to its revision."""
    reviews = sorted(
        (node for node in nodes.values() if node.kind == "catalog-review"),
        key=lambda node: node.sequence or 0,
    )
    snapshot = empty_catalog()
    producer: dict[str, str] = {}
    revision_of: dict[str, str] = {}
    for node in reviews:
        snapshot = rebuild_catalog(snapshot, CatalogReview.model_validate(node.payload))
        producer[snapshot.revision] = node.key
        revision_of[node.key] = snapshot.revision
    return producer, revision_of


def dependency_order(nodes: dict[str, Node], producer: dict[str, str]) -> list[str]:
    """Order objects so every object comes after the objects its payload names."""
    needs = {
        key: {producer[text] for text in strings(node.payload) if text in producer} - {key}
        for key, node in nodes.items()
    }
    waiting = {key: len(parts) for key, parts in needs.items()}
    unlocks: dict[str, list[str]] = defaultdict(list)
    for key, parts in needs.items():
        for part in parts:
            unlocks[part].append(key)
    ready = deque(sorted(key for key, count in waiting.items() if count == 0))
    order: list[str] = []
    while ready:
        key = ready.popleft()
        order.append(key)
        for child in unlocks[key]:
            waiting[child] -= 1
            if waiting[child] == 0:
                ready.append(child)
    if len(order) != len(nodes):
        raise ValueError("checkpoint identities depend on each other in a cycle")
    return order


def rekey(
    order: list[str], nodes: dict[str, Node], revision_of: dict[str, str]
) -> tuple[
    dict[str, str], dict[str, tuple[str, Model, int | None, str | None]], dict[str, CatalogSnapshot]
]:
    empty = empty_catalog()
    snapshots: dict[str, CatalogSnapshot] = {empty.revision: empty}
    mapping: dict[str, str] = {}
    rebuilt: dict[str, tuple[str, Model, int | None, str | None]] = {}
    for key in order:
        node = nodes[key]
        payload = rewrite(node.payload, mapping)
        model = MODELS[node.kind].model_validate(payload)
        subject = node.subject
        if isinstance(model, CatalogReview):
            snapshot = rebuild_catalog(snapshots[model.expected_revision], model)
            snapshots[snapshot.revision] = snapshot
            mapping[revision_of[key]] = snapshot.revision
            subject = snapshot.revision
        identity = identity_of(model)
        field = IDENTITY_FIELD.get(node.kind)
        if field:
            payload[field] = identity
            model = MODELS[node.kind].model_validate(payload)
        if identity in rebuilt:
            raise ValueError("two checkpoint objects collapsed into one identity")
        mapping[key] = identity
        rebuilt[identity] = (node.kind, model, node.sequence, subject)
    return mapping, rebuilt, snapshots


def rebind(
    bindings: list[tuple[str, str, dict[str, Any]]],
    mapping: dict[str, str],
    rebuilt: dict[str, tuple[str, Model, int | None, str | None]],
) -> list[tuple[str, str, Model]]:
    result: list[tuple[str, str, Model]] = []
    for kind, old_batch, payload in bindings:
        old_submission = digest(BINDING_SUBMISSION[kind].model_validate(payload))
        _, model, _, _ = rebuilt[mapping[old_submission]]
        result.append((kind, mapping[old_batch], model))
    return result


def has_local_absolute_path(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            (
                key == "evidence_reference"
                and isinstance(item, str)
                and bool(LOCAL_ABSOLUTE_PATH.match(item))
            )
            or has_local_absolute_path(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(has_local_absolute_path(item) for item in value)
    return False


def local_path_remains(value: Any) -> bool:
    """No evidence reference may be absolute, and no text may hold a drive path."""
    return has_local_absolute_path(value) or any(DRIVE_PATH.search(text) for text in strings(value))


def check_references(store: Store) -> None:
    """Every named object must exist in the restored checkpoint, and no local path may remain."""
    pools: dict[str, set[str]] = {"batches": set(), "submissions": set(), "revisions": set()}
    for kind, identity in store.db.execute("SELECT kind,id FROM artifacts"):
        if kind in ("batch", "pair-batch"):
            pools["batches"].add(identity)
        elif kind in ("submission", "pair-submission"):
            pools["submissions"].add(identity)
        elif kind == "catalog":
            pools["revisions"].add(identity)
    records = {
        identity: json.loads(raw)
        for identity, raw in store.db.execute("SELECT id,payload FROM records")
    }
    pools["records"] = set(records)
    payloads = [*records.values()]
    for (raw,) in store.db.execute("SELECT payload FROM artifacts"):
        payloads.append(json.loads(raw))
    for payload in payloads:
        if local_path_remains(payload):
            raise ValueError("a restored checkpoint still names a local path")
        for field, pool in REFERENCE_POOLS.items():
            value = payload.get(field)
            named = value.values() if isinstance(value, dict) else [value] if value else []
            if any(item not in pools[pool] for item in named):
                raise ValueError(f"restored checkpoint has a dangling {field} reference")


def rekey_checkpoint(
    checkpoint: Path, manifest_path: Path, policy_path: Path, output: Path
) -> DatasetCheckpoint:
    if output.exists():
        raise ValueError("use a new immutable checkpoint directory")
    manifest = read_model(manifest_path, SourceFreeze)
    policy = load_policy(policy_path)
    original = read_model(checkpoint / "checkpoint.json", DatasetCheckpoint)
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)
        source = Store(scratch / "source")
        try:
            restore_checkpoint(source, checkpoint, manifest, policy)
            nodes, bindings = load_nodes(source)
        finally:
            source.close()
        check_identities(nodes)
        revision_producer, revision_of = revision_producers(nodes)
        producer = {**{key: key for key in nodes}, **revision_producer}
        mapping, rebuilt, snapshots = rekey(dependency_order(nodes, producer), nodes, revision_of)
        rebound = rebind(bindings, mapping, rebuilt)
        rekeyed = Store(scratch / "rekeyed")
        try:
            with rekeyed.transaction():
                for revision, snapshot in snapshots.items():
                    rekeyed.save("catalog", revision, snapshot)
                for identity, (kind, model, sequence, subject) in rebuilt.items():
                    if sequence is None:
                        rekeyed.save(kind, identity, model)
                    else:
                        rekeyed.db.execute(
                            "INSERT INTO records(sequence,kind,id,subject,payload) "
                            "VALUES(?,?,?,?,?)",
                            (sequence, kind, identity, subject, canonical(model).decode()),
                        )
                for kind, batch, model in rebound:
                    rekeyed.save(kind, batch, model)
                for key, value in original.settings.items():
                    rekeyed.set_setting(key, rewrite(value, mapping))
        finally:
            rekeyed.close()
        export_checkpoint(scratch / "rekeyed", output, manifest, policy)
        written = read_model(output / "checkpoint.json", DatasetCheckpoint)
        (output / "checkpoint.json").unlink()
        write_model(
            output / "checkpoint.json",
            written.model_copy(update={"omitted_artifacts": original.omitted_artifacts}),
        )
        verify = Store(scratch / "verify")
        try:
            restore_checkpoint(verify, output, manifest, policy)
            check_references(verify)
        finally:
            verify.close()
    return read_model(output / "checkpoint.json", DatasetCheckpoint)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("config") / "story-dataset.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = rekey_checkpoint(args.checkpoint, args.manifest, args.policy, args.output)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
