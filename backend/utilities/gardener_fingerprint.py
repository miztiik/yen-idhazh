"""How does one gardener control runner launch the recorder with its opening identity?"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import run_context
from idhazh.gardener.control_fingerprints import Job, expected
from idhazh.publication_paths import IntegrityError
from idhazh.telemetry import machine_api, machine_evidence
from idhazh.telemetry.host_control import MODE_ENV
from utilities import host_telemetry_control, machine_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job", required=True, type=Job, choices=list(Job))
    parser.add_argument("--out", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Trusted command after --")
    args = parser.parse_args(argv)
    if args.job != os.environ["GITHUB_JOB"]:
        raise IntegrityError("control evidence does not name this workflow job")
    wanted = expected(
        args.job, run_id=args.run_id, attempt=run_context.run_attempt(),
        revision=os.environ["GITHUB_SHA"],
    )
    requested = os.environ.get(MODE_ENV, "typescript")
    if args.command:
        if args.command[0] != "--" or len(args.command) < 2:
            parser.error("pass the trusted command after --")
        try:
            instrument = host_telemetry_control.resolve(requested, Path("config")) != "off"
        except (OSError, ValueError) as error:
            machine_api.unavailable(args.job, "control selection", error)
            instrument = False
        return machine_task.run(
            args.command[1:], run_id=args.run_id, days=(wanted.date,), instrument=instrument,
        )
    if args.out is None:
        parser.error("opening capture requires --out")
    if host_telemetry_control.resolve(requested, Path("config")) == "off":
        return 0
    if machine_evidence.read_receipt(args.out, wanted) is not None:
        raise IntegrityError("this runner already has a captured opening")
    machine_evidence.capture_opening(Path.cwd(), args.out, wanted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
