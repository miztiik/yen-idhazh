"""How does a Council runner open and file its own measurements?"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import config, run_context
from idhazh.contracts.council_invocation import Cell, SelectedModel
from idhazh.contracts.knobs.council import CouncilTask
from idhazh.council import performance, session
from idhazh.council.model_selection import verify_model
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


def run_judge(
    host: performance.Runner, *, cell: Cell, model: SelectedModel | None,
    config_root: Path, startup_seconds: float, command: list[str],
) -> int:
    if model is None:
        return subprocess.run(command, check=False).returncode
    with model_runtime.own_native_model(
        config_root, models_file=model.models_file, startup_seconds=startup_seconds,
    ) as server:
        if (server.model_id, server.weights_sha256) != (model.model_id, model.weights_sha256):
            raise IntegrityError("the loaded native model differs from the Council selection")
        server.assert_owned()
        code = subprocess.run(command, check=False).returncode
        if (recording := host.recording(config.REPO_ROOT)) is not None:
            try:
                reading = server.observe("success" if code == 0 else "error")
                if reading is not None:
                    recording.record(
                        host.task(cell.date, CouncilTask.SERVE, cell.tenant), host.bundle, reading,
                    )
            except (OSError, ValueError, machine_api.MachineApiError) as error:
                machine_api.unavailable(cell.tenant, "serving receipt", error)
        return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verb", choices=("open", "bounds", "measure", "judge"))
    parser.add_argument(
        "--phase", required=True, type=performance.Phase, choices=list(performance.Phase),
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    before, marker, command = _split_command(argv)
    args = parser.parse_args(before)
    phase: performance.Phase = args.phase
    cell = None
    selection = None
    run_id = str(args.run_id)
    revision, attempt = os.environ["GITHUB_SHA"], run_context.run_attempt()
    if args.verb in ("measure", "judge") and (not marker or not command):
        parser.error(f"{args.verb} requires a trusted command after --")
    if args.verb == "judge" and phase is not performance.Phase.JUDGE:
        parser.error("judge requires the judge phase")
    if (job := os.environ.get("GITHUB_JOB")) and job != phase:
        raise IntegrityError("Council machine evidence does not name this workflow job")
    settings = config.load(args.config_root)
    selected = mode(settings.app.observability)
    if args.verb == "measure" and phase is performance.Phase.JUDGE:
        # machine_task execs on Linux. Own the server inside its child, where the
        # machine API is already scoped to this runner and cleanup can still run.
        command = [
            sys.executable, "-m", "utilities.council_machine", "judge",
            "--phase", phase.value, "--run-id", run_id, "--config-root", str(args.config_root),
            "--", *command,
        ]
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
    elif args.verb == "judge":
        assert cell is not None and selection is not None
        return run_judge(
            host, cell=cell, model=verify_model(council, selection.judge(cell.tenant, cell.date)),
            config_root=args.config_root, command=command,
            startup_seconds=timedelta(minutes=council.shard_preamble_minutes).total_seconds(),
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
