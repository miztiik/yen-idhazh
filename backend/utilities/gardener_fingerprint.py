"""How does one gardener control runner retain its exact opening capture?"""

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
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.job != os.environ["GITHUB_JOB"]:
        raise IntegrityError("fingerprint does not name this workflow job")
    wanted = expected(
        args.job, run_id=args.run_id, attempt=run_context.run_attempt(),
        revision=os.environ["GITHUB_SHA"],
    )
    if machine_evidence.read_receipt(args.out, wanted) is not None:
        raise IntegrityError("this runner already has a captured opening")
    client = machine_api.MachineApi.for_job()
    if client is None:
        machine_api.warn(f"Gardener {args.job} fingerprint unavailable: no machine listener")
        return 1
    response = client.fingerprint(wanted.date, wanted.writer)
    if isinstance(response, machine_api.Captured):
        retain(machine_api.private_state(Path.cwd()), args.out, wanted, response)
        if output := os.environ.get("GITHUB_OUTPUT"):
            with Path(output).open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(f"run_id={wanted.writer.run_id}\nattempt={wanted.writer.attempt}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
