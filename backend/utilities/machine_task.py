"""Run a trusted workflow command inside the existing Machine API listener."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import config, run_context
from idhazh.telemetry import machine_api
from idhazh.telemetry.host_control import DEFAULT_MODE, MODE_ENV
from utilities import memory_profiling_control


def run(
    command: list[str], *, run_id: str | None = None, days: tuple[str, ...] = (),
    instrument: bool = True,
) -> int:
    if not command:
        raise ValueError("a trusted workflow command is required")
    env = dict(os.environ)
    env.pop(machine_api.ORIGIN_ENV, None)
    env.pop(machine_api.STATE_ROOT_ENV, None)
    argv = command
    if instrument and env.get("IDHAZH_MACHINE_APIS_READY") == "true":
        run_id = run_id or f"{env['IDHAZH_MACHINE_ACCOUNTING_DAY']}-{env['GITHUB_RUN_ID']}"
        days = days or (env.get("IDHAZH_MACHINE_ACCOUNTING_DAY") or run_id[:10],)
        memory = memory_profiling_control.resolve(
            env.get("MEMORY_PROFILING", "inherit"), config.REPO_ROOT / "config",
        )
        argv = [
            "bun", "run", "--no-install", "services/host-probes/src/api/run-recording-task.ts",
            ",".join(days), run_id, str(run_context.run_attempt()),
            env["IDHAZH_MACHINE_PIPELINE"], env["IDHAZH_MACHINE_SHARD"],
            env["GITHUB_SHA"], "on" if memory else "off", *command,
        ]
    elif instrument and env.get(MODE_ENV) == DEFAULT_MODE:
        print(
            "::warning title=Task Performance::Machine API runtime was not prepared",
            file=sys.stderr,
        )
    if os.name != "nt":
        os.execvpe(argv[0], argv, env)
    return subprocess.run(argv, env=env, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command: list[str] = args.command
    return run(command[1:] if command[:1] == ["--"] else command, run_id=args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
