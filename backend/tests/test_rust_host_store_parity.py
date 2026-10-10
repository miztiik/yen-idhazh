"""Can the independent verifier read the exact files persisted by the native store?"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from idhazh.contracts.host_output import HostWriteCompletion, HostWritePlan
from idhazh.telemetry.host_output_verify import VerificationLimits, verify_host_output

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/host-events/storage-parity.json"
pytestmark = pytest.mark.contract


def binary() -> Path:
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "backend/var/rust-host-telemetry"))
    binary_path = target / "debug" / ("storage-fixture.exe" if os.name == "nt" else "storage-fixture")
    assert binary_path.is_file(), "Build the locked Rust storage-fixture before parity tests."
    return binary_path


@pytest.fixture(scope="module")
def native_proofs() -> list[dict[str, Any]]:
    result = subprocess.run(
        [str(binary()), FIXTURE.relative_to(ROOT).as_posix(), f"backend/var/d11-python/{uuid4()}"],
        cwd=ROOT, capture_output=True, check=False, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode()
    proofs: list[dict[str, Any]] = json.loads(result.stdout)
    assert len(proofs) == 4
    return proofs


@pytest.mark.parametrize("harness", [False, True])
@pytest.mark.parametrize("index", range(4))
def test_original_stored_bytes_have_exact_independently_verified_identity(
    native_proofs: list[dict[str, Any]], harness: bool, index: int,
) -> None:
    proofs = native_proofs
    if harness:
        path = ROOT / "backend/var/d11-rust-tests/proofs.json"
        assert path.is_file(), "Cargo store tests must produce their actual-file proof."
        proofs = json.loads(path.read_bytes())
    plan = HostWritePlan.model_validate(proofs[index]["plan"])
    completion = HostWriteCompletion.model_validate(proofs[index]["completion"])
    original = {file.relative_path: (ROOT / plan.target_root / file.relative_path).read_bytes()
                for file in plan.files}
    limits = VerificationLimits(**json.loads(
        (ROOT / "config/host-telemetry-experiment.json").read_bytes()
    )["verification_limits"])
    verified = verify_host_output(
        plan, completion, workspace_root=ROOT, target_root=plan.target_root,
        publication_identity=plan.publication_identity, limits=limits,
    )
    assert verified.complete and len(verified.files) == 2
    assert [file.envelope.covers for file in verified.files] == ["2026-10-09", "2026-10-10"]
    for expected, actual in zip(plan.files, verified.files, strict=True):
        assert actual.envelope.identity.producer == "telemetry.silicon"
        assert plan.publication_identity.producer == "utilities.host-fixture"
        assert actual.rows[0].attempt == 2
        data = original[expected.relative_path]
        assert actual.physical_sha256 == hashlib.sha256(data).hexdigest()
        assert actual.envelope.content_sha256 != actual.physical_sha256
        assert (ROOT / plan.target_root / expected.relative_path).read_bytes() == data


def test_native_store_has_no_reverse_observation_or_engine_dependencies() -> None:
    modules = ("identity", "filenames", "paths", "envelope", "store")
    for name in modules:
        source = (ROOT / f"backend/rust/host-telemetry/src/ledger/{name}.rs").read_text()
        for forbidden in ("use arrow_", "use parquet::", "crate::producers", "crate::sampling",
                          "crate::probe_inputs"):
            assert forbidden not in source, (name, forbidden)
