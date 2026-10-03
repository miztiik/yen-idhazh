"""Publish an immutable evaluation batch and its exact-key index as one generation."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from pydantic import TypeAdapter

from idhazh import ledger
from idhazh.atomic_write import write_atomic
from idhazh.contracts.base import Sha256, canonical_json, derive_text_digest
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.observation_lookup import (
    ObservationBatch,
    ObservationLookupEntry,
    ObservationLookupNode,
    ObservationLookupRoot,
    ObservationLookupSettings,
    ObservationPreparation,
)
from idhazh.evals import observation_outputs
from idhazh.evals.lookup_nodes import node_path
from idhazh.evals.observation_lookup import ROOT_NAME, ObservationLookup

_BATCH_ID = TypeAdapter(Sha256)


class _PreparedLookup(ObservationLookup):
    """Hand back every affected index path before publishing or retiring a node."""

    def __init__(self, root: Path, record_paths: Callable[[Iterable[Path]], None]) -> None:
        super().__init__(root)
        self._record_paths = record_paths

    def _publish(
        self,
        before: str | None,
        after: ObservationLookupRoot,
        created: dict[Path, tuple[ObservationLookupNode, bytes]],
        superseded: list[ObservationLookupNode],
    ) -> None:
        self._record_paths(
            {self.root / ROOT_NAME, *created}
            | {node_path(self.root, node) for node in superseded}
        )
        super()._publish(before, after, created, superseded)


def lookup_root(state_dir: Path) -> Path:
    return ledger.tree_root(state_dir, LedgerName.SUMMARY_QUALITY_EVALS_INDEX) / "lookup"


def incoming_path(state_dir: Path, batch_id: str) -> Path:
    return (
        ledger.tree_root(state_dir, LedgerName.SUMMARY_QUALITY_EVALS_INDEX)
        / "incoming"
        / f"{_BATCH_ID.validate_python(batch_id)}.json"
    )


def input_root(state_dir: Path) -> Path:
    state_root = next(
        (
            parent
            for parent in (state_dir, *state_dir.parents)
            if parent.name == ledger.STATE_DIRNAME
        ),
        state_dir,
    )
    runtime = state_root.parent / "backend" / "var" / "evaluation-inputs"
    return (
        runtime
        if state_root == state_dir
        else runtime / "trials" / state_dir.relative_to(state_root)
    )


def preparation_path(state_dir: Path, identity: WriterIdentity) -> Path:
    return input_root(state_dir) / identity.run_id / f"{identity.job.value}-{identity.shard}.json"


def row_digest(row: EvalRow) -> str:
    from idhazh.evals.writer import observation_digest

    return observation_digest(row.model_dump(mode="json"))


def initialize_fresh(state_dir: Path, settings: ObservationLookupSettings) -> set[Path]:
    root = lookup_root(state_dir)
    if (root / ROOT_NAME).exists():
        return set()
    legacy = ledger.tree_root(state_dir, LedgerName.SUMMARY_QUALITY_EVALS_INDEX)
    legacy_history = legacy.exists() and any(
        path.name not in {"incoming", "lookup"} for path in legacy.iterdir()
    )
    if legacy_history or any(
        path.exists()
        for path in (
            ledger.raw_root(state_dir, LedgerName.SUMMARY_QUALITY_EVALS),
            ledger.compact_index_path(
                state_dir, LedgerName.SUMMARY_QUALITY_EVALS, Period.DAILY
            ).parent,
        )
    ):
        raise FileNotFoundError(
            "existing evaluation history needs an explicit observation lookup migration"
        )
    with ObservationLookup(root) as lookup:
        if not (root / ROOT_NAME).exists():
            lookup.initialize(ledger.OBSERVATION_KEY, settings)
        return set(lookup.changed)


def save_batch(state_dir: Path, batch: ObservationBatch) -> None:
    path = input_root(state_dir) / "batches" / f"{batch.batch_id}.json"
    if path.exists():
        if ObservationBatch.read(path) != batch:
            raise ValueError("an evaluation input batch changed after it was sealed")
    else:
        write_atomic(path, batch.to_json())
    manifest = preparation_path(state_dir, batch.identity)
    before = (
        ObservationPreparation.read(manifest)
        if manifest.exists()
        else ObservationPreparation.model_validate({"batches": [], "paths": []})
    )
    if batch.batch_id not in before.batches:
        before.batches.append(batch.batch_id)
        write_atomic(manifest, before.to_json())


def load_batch(state_dir: Path, batch_id: str) -> ObservationBatch:
    """Recover one named input, validating its address before retaining it locally."""
    batch_id = _BATCH_ID.validate_python(batch_id)
    local = input_root(state_dir) / "batches" / f"{batch_id}.json"
    batch = ObservationBatch.read(local if local.exists() else incoming_path(state_dir, batch_id))
    if batch.batch_id != batch_id:
        raise ValueError("the evaluation input does not match its recomputed batch identity")
    save_batch(state_dir, batch)
    return batch


def apply_batch(
    state_dir: Path, batch: ObservationBatch, *, manifest_path: Path | None = None
) -> tuple[int, set[Path]]:
    """Admit candidates against one generation, preserving the complete batch for retry."""
    save_batch(state_dir, batch)
    directory = input_root(state_dir) / "outputs" / batch.batch_id
    handback_path = directory / "paths.json"
    handback = (
        ObservationPreparation.read(handback_path)
        if handback_path.exists()
        else ObservationPreparation.model_validate({"batches": [batch.batch_id], "paths": []})
    )
    if handback.batches != [batch.batch_id]:
        raise ValueError("the prepared evaluation paths belong to another batch")
    changed = {state_dir.parent / name for name in handback.paths}

    def record_paths(paths: Iterable[Path]) -> None:
        changed.update(paths)
        handback.paths = sorted(path.relative_to(state_dir.parent).as_posix() for path in changed)
        write_atomic(handback_path, handback.to_json())
        record_changed(state_dir, batch.identity, changed, manifest_path=manifest_path)

    with _PreparedLookup(lookup_root(state_dir), record_paths) as lookup:
        record_paths(lookup.changed)
        manifest = lookup.manifest()
        if manifest.key_fields != ledger.OBSERVATION_KEY:
            raise ValueError(
                "the observation lookup uses another measurement key; migrate explicitly"
            )
        previous = lookup.receipt(batch.batch_id)
        if previous is not None and previous.payload_sha256 != batch.payload_sha256:
            raise ValueError("the replayed evaluation batch does not match its receipt")
        pending = observation_outputs.read_pending(directory, batch, manifest.generation, previous)
        if pending is not None:
            record_paths(observation_outputs.output_paths(state_dir, pending))
            observation_outputs.discard_abandoned(state_dir, pending, previous)
        if previous is not None:
            observation_outputs.finish_outputs(directory)
            return 0, changed
        incoming: dict[str, EvalRow] = {}
        for row in batch.rows:
            incoming.setdefault(row_digest(row), row)
        held = lookup.recorded(incoming)
        fresh = {digest: row for digest, row in incoming.items() if digest not in held}
        generation = derive_text_digest(canonical_json([manifest.generation, batch.batch_id]))
        receipt = observation_outputs.stage_outputs(
            directory, batch, list(fresh.values()), generation
        )
        if receipt is None:
            return 0, changed
        record_paths(observation_outputs.output_paths(state_dir, receipt))
        observation_outputs.publish_outputs(state_dir, directory, receipt)
        entries = [
            ObservationLookupEntry(namespace="observation", identity=digest) for digest in fresh
        ]
        entries.append(
            ObservationLookupEntry(namespace="batch", identity=batch.batch_id, receipt=receipt)
        )
        lookup.put(entries, generation=generation)
        record_paths(lookup.changed)
        observation_outputs.finish_outputs(directory)
    return len(fresh), changed


def record_changed(
    state_dir: Path,
    identity: WriterIdentity,
    paths: Iterable[Path],
    *,
    manifest_path: Path | None = None,
) -> None:
    names = {path.relative_to(state_dir.parent).as_posix() for path in paths}
    manifests = {preparation_path(state_dir, identity)}
    if manifest_path is not None:
        manifests.add(manifest_path)
    for path in sorted(manifests):
        manifest = ObservationPreparation.read(path)
        manifest.paths = sorted(set(manifest.paths) | names)
        write_atomic(path, manifest.to_json())


def file_batch(
    state_dir: Path,
    rows: Iterable[EvalRow],
    identity: WriterIdentity,
    settings: ObservationLookupSettings,
) -> int:
    """Restore this job's saved batches before a downstream projection reads its rows."""
    pending = list(rows)
    batch = (
        ObservationBatch.model_validate({"identity": identity, "rows": pending})
        if pending
        else None
    )
    if batch is not None:
        save_batch(state_dir, batch)
    manifest_path = preparation_path(state_dir, identity)
    if not manifest_path.exists():
        return 0
    manifest = ObservationPreparation.read(manifest_path)
    if not manifest.batches:
        return 0
    initialized = initialize_fresh(state_dir, settings)
    record_changed(state_dir, identity, initialized)
    accepted = 0
    for batch_id in manifest.batches:
        saved = load_batch(state_dir, batch_id)
        count, changed = apply_batch(state_dir, saved)
        record_changed(state_dir, identity, changed)
        if batch is not None and batch_id == batch.batch_id:
            accepted = count
    return accepted


def prepare(
    state_dir: Path,
    manifest_path: Path,
    *,
    settings: ObservationLookupSettings | None = None,
) -> list[str]:
    """Reapply only this job's named input, after a stale generation has been restored."""
    if not manifest_path.exists():
        return []
    manifest = ObservationPreparation.read(manifest_path)
    initialized = (
        initialize_fresh(state_dir, settings)
        if settings is not None and manifest.batches
        else set()
    )
    for batch_id in manifest.batches:
        batch = load_batch(state_dir, batch_id)
        _, changed = apply_batch(state_dir, batch, manifest_path=manifest_path)
        with ObservationLookup(lookup_root(state_dir)) as lookup:
            if lookup.receipt(batch.batch_id) is None:
                raise RuntimeError("evaluation preparation did not produce a batch receipt")
        pending = incoming_path(state_dir, batch.batch_id)
        pending.unlink(missing_ok=True)
        manifest.paths = sorted(
            set(manifest.paths)
            | {
                path.relative_to(state_dir.parent).as_posix()
                for path in initialized | changed | {pending}
            }
        )
        write_atomic(manifest_path, manifest.to_json())
        initialized = set()
    return manifest.paths