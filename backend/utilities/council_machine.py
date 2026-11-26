"""How does a Council runner open and file its own measurements?"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import config, run_context
from idhazh.contracts.council_invocation import Cell
from idhazh.contracts.knobs.council import CouncilTask
from idhazh.contracts.task_performance import TaskPerformanceOutcome
from idhazh.council import performance, session
from idhazh.council.selection import from_environment
from idhazh.publication_paths import IntegrityError
from idhazh.telemetry import machine_api, task_probe
from idhazh.telemetry.host_control import mode
from utilities import machine_task, model_runtime, shard_bound

_BOUNDS_CONFIG = "llm_council_job_timeouts.json"
_BOUND_NAMES = ("planning_timeout_minutes", "collection_timeout_minutes")


def bounds(host: performance.Runner, repo: Path, config_root: Path) -> None:
    day = host.opening.date
    with task_probe.profile(host.recording(repo), host.task(day), host.bundle):
        for key in _BOUND_NAMES:
            print(f"{key}={shard_bound.minutes(config_root, key=key, config_file=_BOUNDS_CONFIG)}")


def close_server(
    host: performance.Runner, *, cell: Cell, repo: Path, config_root: Path,
    outcome: TaskPerformanceOutcome,
) -> None:
    if not cell.runs_model:
        raise ValueError("a model-free cell has no serving observation")
    reading = model_runtime.close_serving_observation(config_root, "llama-server", outcome)
    if reading is not None and (recording := host.recording(repo)) is not None:
        try:
            recording.record(
                host.task(cell.date, CouncilTask.SERVE, cell.tenant), host.bundle, reading,
            )
        except (OSError, ValueError, machine_api.MachineApiError) as error:
            machine_api.unavailable(cell.tenant, "serving receipt", error)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verb", choices=("open", "bounds", "measure", "close-server"))
    parser.add_argument(
        "--phase", required=True, type=performance.Phase, choices=list(performance.Phase),
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--runtime-outcome", choices=("success", "failure", "cancelled", "skipped"))
    before, marker, command = _split_command(argv)
    args = parser.parse_args(before)
    phase: performance.Phase = args.phase
    cell = None
    selection = None
    run_id = str(args.run_id)
    revision, attempt = os.environ["GITHUB_SHA"], run_context.run_attempt()
    if args.verb == "measure" and not marker:
        parser.error("measure requires a trusted command after --")
    if (job := os.environ.get("GITHUB_JOB")) and job != phase:
        raise IntegrityError("Council machine evidence does not name this workflow job")
    settings = config.load(args.config_root)
    selected = mode(settings.app.observability)
    if args.verb == "measure" and selected == "off":
        return machine_task.run(command, instrument=False)
    if phase is performance.Phase.JUDGE or (
        args.verb == "measure" and phase in (performance.Phase.DRAW, performance.Phase.SETTLE)
    ):
        try:
            council = config.load_council(args.config_root)
            selection = from_environment(council).identify(
                run_id=run_id, attempt=attempt, git_sha=revision,
            )
        except (OSError, ValueError, SystemExit):
            if args.verb != "measure":
                raise
            machine_api.warn(f"Council {phase} has no admissible measurement scope")
            return machine_task.run(command, instrument=False)
    if phase is performance.Phase.JUDGE:
        assert selection is not None
        tenant, day = os.environ["COUNCIL_TENANT"], os.environ["COUNCIL_DATE"]
        judge = selection.judge(tenant, day)
        cell = Cell(
            tenant=tenant, date=day, shard=int(os.environ["COUNCIL_SHARD"]), shards=judge.shards,
            runs_model=council.declaration(tenant).runs_model,
        )
    host = performance.runner(
        session.COUNCIL_ROOT, phase, run_id=run_id, attempt=attempt,
        git_sha=revision, cell=cell, selection=selection,
    )
    if args.verb == "open":
        host.capture(settings)
    elif args.verb == "bounds":
        bounds(host, config.REPO_ROOT, args.config_root)
    elif args.verb == "close-server":
        if selected == "off":
            return 0
        assert cell is not None
        result = args.runtime_outcome
        close_server(
            host, cell=cell, repo=config.REPO_ROOT, config_root=args.config_root,
            outcome="success" if result == "success" else "cancelled" if result == "cancelled"
            else "error",
        )
    elif args.verb == "measure":
        days = [host.opening.date]
        if phase in (performance.Phase.DRAW, performance.Phase.SETTLE) and selection is not None:
            days.extend(selection.dates)
        return machine_task.run(
            command, run_id=host.opening.writer.run_id, days=tuple(dict.fromkeys(days)),
            legacy_opening=host.opening.writer if selected == "python" else None,
        )
    return 0


def _split_command(argv: list[str] | None) -> tuple[list[str], bool, list[str]]:
    words = sys.argv[1:] if argv is None else argv
    if "--" not in words:
        return words, False, []
    marker = words.index("--")
    return words[:marker], True, words[marker + 1:]


if __name__ == "__main__":
    raise SystemExit(main())
