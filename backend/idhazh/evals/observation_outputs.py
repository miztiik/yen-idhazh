"""Stage and recover the raw files named by one evaluation batch's local receipt."""

from __future__ import annotations

import shutil
from pathlib import Path

from idhazh import ledger
from idhazh.atomic_write import write_atomic
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.observation_lookup import ObservationBatch, ObservationLookupReceipt


def read_pending(
    directory: Path,
    batch: ObservationBatch,
    generation: str,
    previous: ObservationLookupReceipt | None,
) -> ObservationLookupReceipt | None:
    path = directory / "receipt.json"
    if not path.exists():
        return None
    pending = ObservationLookupReceipt.read(path)
    if pending.batch_id != batch.batch_id or pending.payload_sha256 != batch.payload_sha256:
        raise ValueError("the pending evaluation output does not match its immutable batch")
    if previous is None and pending.generation == generation:
        raise ValueError("the pending evaluation generation has no batch receipt")
    if previous is not None and previous.generation == pending.generation and previous != pending:
        raise ValueError("the pending evaluation output disagrees with its applied receipt")
    return pending


def output_paths(state_dir: Path, receipt: ObservationLookupReceipt) -> set[Path]:
    raw = ledger.raw_root(state_dir, LedgerName.SUMMARY_QUALITY_EVALS).resolve()
    paths = {state_dir / name for name in receipt.output_paths}
    for path in paths:
        path.resolve().relative_to(raw)
        if path.resolve() == raw:
            raise ValueError("an evaluation output must name a raw file")
    return paths


def discard_abandoned(
    state_dir: Path,
    pending: ObservationLookupReceipt,
    previous: ObservationLookupReceipt | None,
) -> None:
    retained = output_paths(state_dir, previous) if previous is not None else set()
    for path in output_paths(state_dir, pending) - retained:
        path.unlink(missing_ok=True)


def stage_outputs(
    directory: Path,
    batch: ObservationBatch,
    rows: list[EvalRow],
    generation: str,
) -> ObservationLookupReceipt | None:
    staged = directory / "state"
    if staged.exists():
        shutil.rmtree(staged)
    outputs: list[Path] = []
    if rows:
        identity = batch.identity.model_copy(
            update={"producer": f"{batch.identity.producer}:evaluation-{batch.batch_id}"}
        )
        outputs = ledger.persist(
            staged,
            rows,
            ledger=LedgerName.SUMMARY_QUALITY_EVALS,
            covers=identity.run_id[:10],
            identity=identity,
        )
        if not outputs:
            return None
    receipt = ObservationLookupReceipt.model_validate(
        {
            "batch_id": batch.batch_id,
            "payload_sha256": batch.payload_sha256,
            "generation": generation,
            "accepted": len(rows),
            "output_paths": [path.relative_to(staged).as_posix() for path in outputs],
        }
    )
    write_atomic(directory / "receipt.json", receipt.to_json())
    return receipt


def publish_outputs(
    state_dir: Path, directory: Path, receipt: ObservationLookupReceipt
) -> None:
    for target in sorted(output_paths(state_dir, receipt)):
        source = directory / "state" / target.relative_to(state_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.hardlink_to(source)
        source.unlink()


def finish_outputs(directory: Path) -> None:
    (directory / "receipt.json").unlink(missing_ok=True)
    staged = directory / "state"
    if staged.exists():
        shutil.rmtree(staged)