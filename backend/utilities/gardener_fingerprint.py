"""How does one gardener control runner launch the recorder with its opening identity?"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import ledger, run_context
from idhazh.gardener.control_fingerprints import Job, expected
from idhazh.publication_paths import IntegrityError
from idhazh.telemetry import machine_api, machine_evidence
from idhazh.telemetry.host_control import MODE_ENV
from utilities import host_telemetry_control, machine_task


def retain(
    state: Path, destination: Path, expected_file: machine_evidence.ExpectedFile,
    response: machine_api.Captured,
) -> None:
    if len(response.files) != 1:
        raise IntegrityError("native fingerprint must return one completed file")
    (receipt,) = response.files
    expected_path = ledger.raw_path(
        machine_evidence.STATE, machine_evidence.HOST, expected_file.date, receipt.file_id,
    ).as_posix()
    if f"state/{receipt.path}" != expected_path or receipt.covers != expected_file.date:
        raise IntegrityError("native fingerprint receipt is outside its exact raw path")
    proof = machine_evidence.verify_file(state.parent, expected_path, expected_file)
    if (
        proof.row != response.row or str(proof.envelope.unit_id) != receipt.unit_id
        or proof.envelope.content_sha256 != receipt.content_sha256
    ):
        raise IntegrityError("native fingerprint receipt does not match the completed file")
    proof.save_receipt(destination, expected_file)


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
    if args.command:
        if args.command[0] != "--" or len(args.command) < 2:
            parser.error("pass the trusted command after --")
        try:
            instrument = host_telemetry_control.resolve(
                os.environ.get(MODE_ENV, "python"), Path("config"),
            ) != "off"
        except (OSError, ValueError) as error:
            machine_api.unavailable(args.job, "control selection", error)
            instrument = False
        return machine_task.run(
            args.command[1:], run_id=args.run_id, days=(wanted.date,),
            legacy_opening=wanted.writer, instrument=instrument,
        )
    if args.out is None:
        parser.error("opening capture requires --out")
    if machine_evidence.read_receipt(args.out, wanted) is not None:
        raise IntegrityError("this runner already has a captured opening")
    client = machine_api.MachineApi.for_job()
    if client is None:
        machine_api.warn(f"Gardener {args.job} fingerprint unavailable: no machine listener")
        return 1
    response = client.fingerprint(wanted.date, wanted.writer)
    if isinstance(response, machine_api.Captured):
        retain(machine_api.private_state(Path.cwd()), args.out, wanted, response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
