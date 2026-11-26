"""Provide publisher oracles exact rows from the real, network-free native handler."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from idhazh.telemetry import machine_api, machine_evidence
from idhazh.telemetry.machine_evidence import ExpectedFile, VerifiedFile
from support.paths import REPO_ROOT


@dataclass(frozen=True)
class Batch:
    private: Path
    requests: tuple[tuple[ExpectedFile, Mapping[str, object], Path], ...]
    opening: VerifiedFile | None = None


def write_batches(batches: Sequence[Batch]) -> tuple[VerifiedFile, ...]:
    this_run = []
    for batch in batches:
        first = batch.requests[0][0]
        writer = first.writer
        days = {expected.date for expected, _, _ in batch.requests}
        execution: dict[str, object] = {
            "run_id": writer.run_id, "attempt": writer.attempt, "pipeline_name": writer.pipeline_name,
            "shard": writer.shard, "git_sha": writer.git_sha,
        }
        host = batch.opening
        if host is not None:
            host.place(batch.private)
            days.add(host.envelope.covers)
            if host.envelope.identity.pipeline_name is None:
                execution["legacy_opening_writer"] = host.envelope.identity.model_dump(mode="json")
        execution["accounting_days"] = sorted(days)
        this_run.append({
            "state": str(batch.private / "state"), "execution": execution,
            "requests": [
                machine_api.record_request(
                    date=expected.date, identity=expected.writer,
                    measurement={
                        "task_kind": expected.kind, "subject_id": expected.subject,
                        "outcome": "success",
                        "host_unit_id": None if host is None else str(host.envelope.unit_id),
                        **measurement,
                    },
                )
                for expected, measurement, _ in batch.requests
            ],
        })
    bun = shutil.which("bun")
    assert bun is not None
    result = subprocess.run(
        [bun, "run", "--no-install", "test/write-workflow-performance.ts"],
        cwd=REPO_ROOT / "services" / "host-probes", input=json.dumps(this_run), text=True,
        capture_output=True, timeout=40, check=False,
    )
    assert result.returncode == 0, result.stderr
    proofs = []
    replies = iter(result.stdout.splitlines())
    for batch in batches:
        for expected, _, store in batch.requests:
            reply = machine_api.Written.model_validate_json(next(replies))
            (receipt,) = reply.files
            proof = machine_evidence.verify_file(batch.private, "state/" + receipt.path, expected)
            assert proof.row == reply.row
            proof.save_receipt(store, expected)
            proofs.append(proof)
    assert next(replies, None) is None
    return tuple(proofs)
