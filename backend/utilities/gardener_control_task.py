"""How does a gardener control command keep its exact work and exit status under a probe?"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from types import FrameType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import config, crash_trace, run_context
from idhazh.gardener.control_fingerprints import (
    OPERATIONS,
    Job,
    Operation,
    expected,
    recording,
    task_file,
)
from idhazh.telemetry import machine_api, machine_evidence, task_probe
from utilities import gardener_shards


def _run_history(command: list[str], worktree: Path) -> int:
    env = dict(os.environ)
    env.pop(machine_api.ORIGIN_ENV, None)
    env.pop(machine_api.STATE_ROOT_ENV, None)
    with subprocess.Popen(command, cwd=worktree, env=env) as child:
        def forward(signum: int, _frame: FrameType | None) -> None:
            child.send_signal(signum)

        # The listener signals this wrapper; the original history process must see it.
        signals = (signal.SIGINT, signal.SIGTERM)
        previous = {sig: signal.signal(sig, forward) for sig in signals}
        try:
            return child.wait()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def run(
    operation: Operation, *, repo: Path, opening: machine_evidence.ExpectedFile, bundle: Path,
    command: list[str] | None = None, worktree: Path | None = None,
) -> int:
    observer = recording(repo, bundle, opening)
    with task_probe.profile(observer, task_file(opening, operation), bundle) as result:
        if operation is Operation.PLAN:
            status = gardener_shards.main([])
        else:
            if command is None or worktree is None:
                raise ValueError("history observation requires the original command and checkout")
            # A wrapper waiting for the actual command owns no useful worker readings.
            result.facts.update(worker_cpu_time_ms=None, worker_rss_peak_kib=None)
            status = _run_history(command, worktree)
        if status:
            interrupted = (
                -signal.SIGINT, -signal.SIGTERM, 128 + signal.SIGINT, 128 + signal.SIGTERM,
            )
            result.outcome = "cancelled" if status in interrupted else "error"
        return 128 - status if status < 0 else status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", type=Operation, choices=(*OPERATIONS[Job.PLAN], *OPERATIONS[Job.HISTORY]),
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--history-root", type=Path)
    parser.add_argument("--today")
    parser.add_argument("--history-run-id")
    args = parser.parse_args(argv)
    job = Job(os.environ["GITHUB_JOB"])
    if args.operation not in OPERATIONS[job]:
        parser.error("the operation must belong to this runner")
    attempt = run_context.run_attempt()
    opening = expected(job, run_id=args.run_id, attempt=attempt, revision=os.environ["GITHUB_SHA"])
    command = None
    if args.operation is Operation.CHECK_HISTORY:
        command = ["python3", "backend/utilities/corpus_squash_due.py"]
    elif args.operation is Operation.SQUASH:
        if not args.today or not args.history_run_id:
            parser.error("the ordinary history command requires its original day and run ID")
        command = [
            "python", "backend/utilities/corpus_history.py", "--today", args.today,
            "--run-id", args.history_run_id, "--attempt", str(attempt),
        ]
    return run(
        args.operation, repo=config.REPO_ROOT, opening=opening, bundle=args.out,
        command=command, worktree=args.history_root,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crash_trace.install()
    raise SystemExit(main())
