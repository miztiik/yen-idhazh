"""Which Council runner observations can follow the settled active selection?"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from idhazh.contracts.council_invocation import Cell
from idhazh.contracts.knobs.council import CouncilTask
from idhazh.council import performance, run_identity
from idhazh.council.selection import Selection
from idhazh.telemetry import machine_api, machine_evidence


@dataclass(frozen=True, slots=True)
class Bundle:
    name: str
    runner: performance.Runner
    prefix: Path
    tasks: tuple[machine_evidence.ExpectedFile, ...]

    def markers(self) -> tuple[str, ...]:
        return tuple(
            (self.prefix / expected.receipt).as_posix()
            for expected in (self.runner.opening, *self.tasks)
        )

    def readings(
        self, downloads: Mapping[str, Path], *, expect_opening: bool,
    ) -> tuple[machine_evidence.VerifiedFile, ...]:
        root = downloads.get(self.name)
        if root is None:
            if expect_opening:
                machine_api.warn(f"Council machine evidence not delivered: {self.name}")
            return ()
        return read(
            root / self.prefix, self.runner.opening, self.tasks, expect_opening=expect_opening,
        )


def read(
    root: Path, expected: machine_evidence.ExpectedFile,
    tasks: tuple[machine_evidence.ExpectedFile, ...], *, expect_opening: bool,
) -> tuple[machine_evidence.VerifiedFile, ...]:
    opening = machine_evidence.read_receipt(root, expected)
    if opening is None and expect_opening:
        machine_api.warn(
            f"Council opening fingerprint not delivered for {expected.writer.task_key} "
            f"on {expected.date} shard {expected.writer.shard}"
        )
    admitted = [] if opening is None else [opening]
    for task in tasks:
        proof = machine_evidence.read_receipt(root, task)
        if proof is not None:
            machine_evidence.verify_host_link(proof, opening)
            admitted.append(proof)
    return tuple(admitted)


def incoming(root: Path, selected: Selection, cells: tuple[Cell, ...]) -> tuple[Bundle, ...]:
    bounds = performance.selected_runner(root, performance.Phase.BOUNDS, selected)
    draw = performance.selected_runner(root, performance.Phase.DRAW, selected)
    bundles = [
        Bundle(
            f"council-bounds-{selected.run_id}-{selected.attempt}", bounds, Path(),
            (bounds.task(bounds.opening.date),),
        ),
        Bundle(
            f"council-selection-{selected.anchor_date}", draw, Path(),
            tuple(
                draw.task(day, CouncilTask.PREPARE, judge.tenant)
                for judge in selected.judges if not selected.trial(judge.tenant)
                for day in judge.dates
            ),
        ),
    ]
    for cell in cells:
        judge_runner = performance.selected_runner(
            root, performance.Phase.JUDGE, selected, cell=cell,
        )
        suffix = f"{cell.tenant}-{cell.date}-{cell.shard}"
        bundle_root = root / "outgoing" / f"shard-{suffix}"
        bundles.append(Bundle(
            f"council-metrics-{suffix}", judge_runner, judge_runner.bundle.relative_to(bundle_root),
            (
                judge_runner.task(cell.date, CouncilTask.JUDGE, cell.tenant),
                *((judge_runner.task(cell.date, CouncilTask.SERVE, cell.tenant),)
                  if cell.runs_model else ()),
            ),
        ))
    return tuple(bundles)


def scopes(selected: Selection) -> tuple[str, ...]:
    """The venue admits days from the invocation, not from artifact receipts."""
    days = {
        run_identity.opened_on(selected.run_id),
        *(
            day for judge in selected.judges if not selected.trial(judge.tenant)
            for day in judge.dates
        ),
    }
    return tuple(machine_evidence.raw_scope(machine_evidence.TASK, day) for day in sorted(days))
