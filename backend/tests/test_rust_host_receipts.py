"""Do actual native interruption and recovery retain exact evidence without Python target writes?"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from idhazh.contracts.host_output import (
    CandidateFileEnvelope,
    CorrectedHostFingerprintRow,
    HostPlannedFile,
    HostStoredRow,
    HostWriteCompletion,
    HostWritePlan,
    HostWriterIdentity,
    canonical_host_rows,
    fingerprint_v2,
    host_file_id,
    host_unit_id,
)
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.telemetry.host_output_verify import VerificationLimits, verify_host_output
from utilities.publication_evidence import confirmed
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, PublicationRequest, contains, safe_file

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / "tests/fixtures/host-events/publication-parity.json").read_bytes())
LIMITS = VerificationLimits(**json.loads(
    (ROOT / "config/host-telemetry-experiment.json").read_bytes()
)["verification_limits"])
pytestmark = pytest.mark.contract


def native(mode: str, plan_path: str, evidence: str, stage: str | None = None) -> subprocess.CompletedProcess[bytes]:
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "backend/var/rust-host-telemetry"))
    binary = target / "debug" / ("receipts-fixture.exe" if os.name == "nt" else "receipts-fixture")
    assert binary.is_file(), "Build the locked native receipts fixture before running tests."
    command = [str(binary), mode, plan_path, evidence]
    if stage is not None:
        command.extend(["--interrupt-after", stage])
    return subprocess.run(command, cwd=ROOT, capture_output=True, check=False, timeout=60)


def plan_input(codec: dict[str, str]) -> tuple[HostWritePlan, str, str]:
    root = f"backend/var/d12-python/{uuid4()}"
    source = json.loads((ROOT / FIXTURE["source_fixture"]).read_bytes())
    writer = HostWriterIdentity.model_validate(source["identity"])
    publisher = HostWriterIdentity.model_validate(writer.model_dump() | {"producer": "utilities.receipts-fixture"})
    planned = []
    for raw in sorted(source["rows"], key=lambda row: row["date"]):
        row = CorrectedHostFingerprintRow.model_validate(raw)
        row = CorrectedHostFingerprintRow.model_validate(
            row.model_dump() | {"fingerprint": fingerprint_v2(row), "fingerprint_version": 2}
        )
        unit = host_unit_id(covers=row.date, identity=writer)
        file = host_file_id(unit=unit, attempt=writer.attempt, written_at_ms=source["written_at_ms"])
        stored = HostStoredRow.model_validate(row.model_dump() | {
            "ledger": "host-fingerprint", "covers": row.date, "attempt": writer.attempt, "unit_id": str(unit),
        })
        envelope = CandidateFileEnvelope.model_validate({
            "version": "2026-10-10", "row_schema_version": "2026-10-10",
            "tier": "raw", "ledger": "host-fingerprint", "covers": row.date,
            "written_at_ms": source["written_at_ms"], "identity": writer,
            "unit_id": unit, "file_id": file,
            "content_sha256": hashlib.sha256(canonical_host_rows([stored])).hexdigest(),
            "writer": "idhazh_rust.ledger.json_lines" if codec["format"] == "json" else "idhazh_rust.ledger.parquet",
            "writer_version": "0.1.0" if codec["format"] == "json" else "60.0.0",
            "compression": codec["compression"],
        })
        suffix = "json" if codec["format"] == "json" else "parquet"
        planned.append(HostPlannedFile.model_validate({
            "envelope": envelope, "format": codec["format"],
            "relative_path": f"raw/host-fingerprint/{row.date.replace('-', '/')}/{file}.{suffix}",
            "rows": [stored],
        }))
    plan = HostWritePlan.model_validate({
        "event_id": uuid4(), "target_root": f"{root}/state",
        "publication_identity": publisher, "files": planned,
    })
    path = f"{root}/input.json"
    (ROOT / root).mkdir(parents=True)
    # The only Python write is the typed input command, never a host target.
    (ROOT / path).write_text(plan.to_json(), encoding="utf-8", newline="\n")
    return plan, path, f"{root}/evidence"


def verify(plan: HostWritePlan, completion: HostWriteCompletion, *, require_all: bool = True) -> None:
    result = verify_host_output(
        plan, completion, workspace_root=ROOT, target_root=plan.target_root,
        publication_identity=plan.publication_identity, limits=LIMITS, require_all=require_all,
    )
    if require_all:
        assert result.complete


@pytest.mark.parametrize("codec", FIXTURE["codecs"])
@pytest.mark.parametrize("stage", FIXTURE["interruption_stages"])
def test_real_subprocess_interruption_then_recovery_and_idempotent_retry(
    codec: dict[str, str], stage: str,
) -> None:
    plan, input_path, evidence = plan_input(codec)
    stopped = native("write", input_path, evidence, stage)
    assert stopped.returncode == 70, stopped.stderr.decode()
    retained = f"{evidence}/{plan.event_id}.plan.json"
    assert HostWritePlan.model_validate_json((ROOT / retained).read_bytes()) == plan
    recovered = native("recover", retained, evidence)
    assert recovered.returncode == 0, recovered.stderr.decode()
    partial = HostWriteCompletion.model_validate(json.loads(recovered.stdout)["completion"])
    expected = 0 if stage in ("plan", "before-file-0") else 2 if stage.endswith("-1") else 1
    assert len(partial.receipt.writes) == expected
    if expected:
        verify(plan, partial, require_all=False)
    before = {path: (ROOT / path).read_bytes() for path in partial.receipt.writes}
    retried = native("retry", retained, evidence)
    assert retried.returncode == 0, retried.stderr.decode()
    completion = HostWriteCompletion.model_validate(json.loads(retried.stdout)["completion"])
    verify(plan, completion)
    assert len(completion.receipt.writes) == 2
    for path, data in before.items():
        assert (ROOT / path).read_bytes() == data
    assert json.loads(native("retry", retained, evidence).stdout)["completion"] == completion.model_dump(mode="json")
    if expected < 2:
        with pytest.raises(ValueError, match="missing from receipt"):
            verify(plan, partial, require_all=False)


def test_existing_receipt_shape_and_independent_publisher_path_scope() -> None:
    plan, input_path, evidence = plan_input(FIXTURE["codecs"][0])
    output = native("write", input_path, evidence)
    assert output.returncode == 0, output.stderr.decode()
    completion = HostWriteCompletion.model_validate(json.loads(output.stdout)["completion"])
    receipt = PublicationReceipt.model_validate(completion.receipt.model_dump(mode="json"))
    assert receipt.identity.producer == "utilities.receipts-fixture"
    exact = f"{plan.target_root}/raw/host-fingerprint"
    for path, digest in receipt.writes.items():
        assert contains(exact, path)
        assert not contains("state/raw/item-health", path)
        assert hashlib.sha256(safe_file(ROOT, path, exists=True).read_bytes()).hexdigest() == digest
    retained = f"{evidence}/{plan.event_id}.plan.json"
    complete = f"{evidence}/{plan.event_id}.completed-2.json"
    arguments = [
        sys.executable, "-m", "utilities.verify_host_output",
        "--workspace-root", str(ROOT), "--target-root", plan.target_root,
        "--plan", retained, "--completion", complete, "--run-id", plan.publication_identity.run_id,
        "--attempt", "2", "--job", "work", "--shard", "0",
        "--git-sha", plan.publication_identity.git_sha,
        "--publication-producer", plan.publication_identity.producer, "--receipt-only",
    ]
    for key, value in asdict(LIMITS).items():
        arguments.extend(["--" + key.replace("_", "-"), str(value)])
    before = {path: (ROOT / path).read_bytes() for path in receipt.writes}
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, check=False, timeout=60)
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()
    assert PublicationReceipt.model_validate_json(result.stdout) == receipt
    assert {path: (ROOT / path).read_bytes() for path in receipt.writes} == before

    # Use a generated repository around the same native files. Do not copy,
    # re-encode, stage or publish them in the source repository.
    artifact_root = input_path.rsplit("/", 1)[0]
    repository_root = ROOT / artifact_root
    for args in [
        ["init", "--quiet"], ["config", "core.autocrlf", "false"],
        ["-c", "user.name=miztiik", "-c", "user.email=miztiik@users.noreply.github.com",
         "commit", "--quiet", "--allow-empty", "-m", "Initialize generated publication fixture"],
    ]:
        subprocess.run(["git", "-C", str(repository_root), *args], check=True, capture_output=True)
    git = Repository(repository_root)
    source = git.git("rev-parse", "HEAD").strip()
    writes = {Path(path).relative_to(artifact_root).as_posix(): digest
              for path, digest in receipt.writes.items()}
    permissions = ("state/raw/host-fingerprint",)
    checked = confirmed(git, writes, source=source, permissions=permissions)
    request = PublicationRequest(
        identity=receipt.identity, message="Check exact native fixture bytes",
        source_tip=source, write_permissions=permissions, delete_permissions=(), writes=checked,
    )
    request.validate(repository_root)
    assert set(git.objects(request)) == set(writes)
    with pytest.raises(IntegrityError, match="authority"):
        confirmed(git, writes, source=source, permissions=("state/raw/item-health",))
    forged = dict(checked)
    first = next(iter(forged))
    forged[first] = replace(forged[first], sha256="0" * 64)
    with pytest.raises(IntegrityError, match="bytes changed"):
        replace(request, writes=forged).validate(repository_root)
    assert {path: (ROOT / path).read_bytes() for path in receipt.writes} == before


@pytest.mark.parametrize("change", ["event", "identity", "digest", "foreign-path"])
def test_native_and_read_only_verifier_refuse_forged_receipts(change: str) -> None:
    plan, input_path, evidence = plan_input(FIXTURE["codecs"][0])
    output = native("write", input_path, evidence)
    assert output.returncode == 0, output.stderr.decode()
    payload: dict[str, Any] = json.loads(output.stdout)["completion"]
    if change == "event":
        payload["event_id"] = str(uuid4())
    elif change == "identity":
        payload["receipt"]["identity"]["git_sha"] = "b" * 40
    elif change == "digest":
        first = next(iter(payload["receipt"]["writes"]))
        payload["receipt"]["writes"][first] = "0" * 64
    else:
        payload["receipt"]["writes"]["state/raw/item-health/foreign.json"] = "0" * 64
    completion = HostWriteCompletion.model_validate(payload)
    with pytest.raises(ValueError):
        verify(plan, completion)
    snapshot = ROOT / f"{evidence}/{plan.event_id}.completed-2.json"
    snapshot.write_text(completion.to_json(), encoding="utf-8", newline="\n")
    assert native("recover", f"{evidence}/{plan.event_id}.plan.json", evidence).returncode != 0
