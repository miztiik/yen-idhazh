"""Which bounded files and executed independent fixture cases support this evidence?"""

from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from idhazh.contracts.host_evidence import EvidenceFile, GateEvidence
from idhazh.telemetry.host_evidence_inputs import ComparisonSettings, read_bytes

GATE_MODULES = frozenset(
    {
        "test_rust_host_file_parity",
        "test_rust_host_store_parity",
        "test_rust_host_receipts",
        "test_host_event_rust_parity",
        "test_host_event_resource_parity",
        "test_host_migration",
        "test_host_fingerprint_migration",
    }
)
CORRECTED_GATE = "test_same_cargo_harness_files_pass_read_only_verifier_and_python_instruments"
CANONICAL_GATES = (
    "test_ascii_canonical_objects_match_python_exact_bytes_and_hashes",
    "test_envelope_plan_completion_exact_fields_provenance_and_conflicts",
)


def file_evidence(workspace: Path, path: Path, maximum: int) -> EvidenceFile:
    raw = read_bytes(path, maximum)
    return EvidenceFile(
        path=path.relative_to(workspace).as_posix(),
        bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def validate_gates(workspace: Path, config: ComparisonSettings) -> GateEvidence:
    path = workspace / "gates.xml"
    tree = ET.fromstring(read_bytes(path, config.max_junit_bytes))
    cases = list(tree.iter("testcase"))
    if not cases or any(
        list(case.iter(tag)) for case in cases for tag in ("failure", "error", "skipped")
    ):
        raise ValueError("required fixture evidence has failures, skips or no executed cases")
    names = tuple(f"{case.get('classname', '')}.{case.get('name', '')}" for case in cases)
    if any(not any(module in name for name in names) for module in GATE_MODULES):
        raise ValueError("required independent replay, file/receipt or history gates are absent")
    for required in (CORRECTED_GATE, *CANONICAL_GATES):
        if not any(required in name for name in names):
            raise ValueError(
                f"independent corrected or canonical fixture evidence absent: {required}"
            )
    return GateEvidence(
        file=file_evidence(workspace, path, config.max_junit_bytes), cases=len(cases), names=names
    )


def artifact_inventory(workspace: Path, config: ComparisonSettings) -> tuple[EvidenceFile, ...]:
    files: list[EvidenceFile] = []
    total = entries = 0
    for parent, directories, names in os.walk(workspace, followlinks=False):
        entries += len(directories) + len(names)
        if entries > config.max_artifact_files:
            raise ValueError("generated artifact inventory exceeds its configured entry cap")
        for name in (*directories, *names):
            path = Path(parent) / name
            if path.is_symlink() or path.is_junction():
                raise ValueError("artifact upload must not follow foreign links")
        for name in sorted(names):
            path = Path(parent) / name
            if path == workspace / "report.json":
                continue
            total += path.stat().st_size
            if total > config.max_artifact_bytes:
                raise ValueError("generated artifact inventory exceeds its configured byte cap")
            files.append(file_evidence(workspace, path, config.max_artifact_bytes))
    return tuple(files)
