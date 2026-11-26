"""Which named observations belong to one actual Council runner?"""

from __future__ import annotations

import os
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from idhazh import config
from idhazh.contracts.council_invocation import Cell
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.council import CouncilTask, task_name
from idhazh.council import run_identity, work_files
from idhazh.council.selection import Selection
from idhazh.council.tenancy import ShardResult
from idhazh.telemetry import machine_api, machine_evidence, silicon, task_probe
from idhazh.telemetry.host_control import MODE_ENV, mode

PIPELINE = "council"


class Phase(StrEnum):
    BOUNDS = "job_bounds"
    DRAW = "draw"
    JUDGE = "judge"
    SETTLE = "save_council_results"


@dataclass(frozen=True, slots=True)
class Runner:
    phase: Phase
    root: Path
    bundle: Path
    opening: machine_evidence.ExpectedFile
    trial: bool = False

    def tenant_store(self, selection: Selection, tenant: str) -> Path:
        if selection.trial(tenant) and not self.trial:
            base = self.root if self.phase is Phase.SETTLE else self.bundle
            return work_files.invocation_root(base, selection, tenant)
        return self.bundle

    def task(
        self, day: str, phase: CouncilTask | None = None, tenant: str | None = None,
    ) -> machine_evidence.ExpectedFile:
        if phase is None:
            if self.phase is not Phase.BOUNDS or tenant is not None:
                raise ValueError("only the bounds runner has a non-tenant task")
            return task_probe.task_file(
                self.opening.writer, pipeline=PIPELINE, task=self.phase, day=day,
            )
        if tenant is None:
            raise ValueError("a Council work phase requires its declared tenant")
        return task_probe.task_file(
            self.opening.writer, pipeline=PIPELINE, task=task_name(phase, tenant), day=day,
            kind="judge" if phase is CouncilTask.JUDGE
            else "model-serving" if phase is CouncilTask.SERVE else "workflow-task",
            subject=tenant if phase is CouncilTask.JUDGE else None,
        )

    def capture(self, settings: config.Settings) -> None:
        """Capture on this runner only, before any of its work starts."""
        knobs = settings.app.observability
        selected = mode(knobs)
        if selected == "off" or not knobs.host_fingerprint:
            return
        writer = self.opening.writer
        if machine_evidence.read_receipt(self.bundle, self.opening) is not None:
            return
        if selected == "typescript":
            machine_evidence.capture_opening(config.REPO_ROOT, self.bundle, self.opening)
            return
        _, paths = silicon.file_machine_row(
            date=self.opening.date, run_id=writer.run_id, settings=settings,
            state_root=self.bundle / machine_evidence.STATE, commit_sha=writer.git_sha,
            job=writer.job, shard=writer.shard, attempt=writer.attempt,
        )
        if not paths:
            machine_api.warn(f"Council opening fingerprint not written for {self.phase}")
            return
        (path,) = paths
        proof = machine_evidence.verify_file(
            self.bundle, path.relative_to(self.bundle).as_posix(), self.opening,
        )
        proof.save_receipt(self.bundle, self.opening)

    def recording(self, repo: Path) -> task_probe.Recording | None:
        if not os.environ.get(machine_api.ORIGIN_ENV):
            return None
        try:
            opening = machine_evidence.read_receipt(self.bundle, self.opening)
        except (OSError, ValueError) as error:
            machine_api.unavailable(self.opening.writer.task_key, "opening evidence", error)
            opening = None
        return task_probe.Recording.for_job(repo, opening)


def runner(
    root: Path, phase: Phase, *, run_id: str, attempt: int, git_sha: str,
    cell: Cell | None = None, selection: Selection | None = None,
) -> Runner:
    day, shard, task = run_identity.opened_on(run_id), 0, phase.value
    bundle = root / "outgoing" / phase.value
    trial = False
    if phase is Phase.DRAW:
        bundle = root / "outgoing" / "planner"
    if phase is Phase.JUDGE:
        if cell is None or selection is None:
            raise ValueError("a judging runner requires its selected cell")
        day, shard = cell.date, cell.shard
        task = task_name(CouncilTask.JUDGE, cell.tenant)
        bundle = root / "outgoing" / f"shard-{cell.tenant}-{day}-{shard}"
        trial = selection.trial(cell.tenant)
        if trial:
            bundle = work_files.invocation_root(bundle, selection, cell.tenant)
    native = os.environ.get(MODE_ENV) != "python"
    writer = WriterIdentity(
        run_id=run_id, attempt=attempt, git_sha=git_sha, shard=shard,
        job=phase.value if native else task,
        pipeline_name=PIPELINE if native else None, task_name=task if native else None,
        producer=silicon.PRODUCER,
    )
    opening = machine_evidence.ExpectedFile(writer, day, native=native)
    return Runner(phase, root, bundle, opening, trial)


def selected_runner(
    root: Path, phase: Phase, selection: Selection, *, cell: Cell | None = None,
) -> Runner:
    return runner(
        root, phase, run_id=selection.run_id, attempt=selection.attempt,
        git_sha=selection.git_sha, cell=cell, selection=selection,
    )


def profile(
    host: Runner, recording: task_probe.Recording | None, selection: Selection,
    phase: CouncilTask, tenant: str, day: str,
) -> AbstractContextManager[machine_api.TaskClose]:
    return task_probe.profile(
        recording, host.task(day, phase, tenant), host.tenant_store(selection, tenant),
    )


def complete(
    observation: machine_api.TaskClose, result: ShardResult, *, judge: str | None = None,
) -> None:
    observation.outcome = (
        "cancelled" if result.outcome is ShardOutcome.STOPPED_ON_DEADLINE
        else "error" if result.outcome is ShardOutcome.FAILED else "success"
    )
    observation.facts.update(
        model_calls=result.model_calls, tokens_in=result.tokens_in, tokens_out=result.tokens_out,
        model_seconds=result.model_seconds,
    )
    if judge is not None:
        observation.facts.update(task_kind="judge", subject_id=judge)
