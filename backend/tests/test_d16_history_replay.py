"""Replay the exact supplied D16 history manifest through migrated consumers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from idhazh.contracts.host_migration import HistoryManifest
from idhazh.telemetry.host_history_bundle import dry_run
from idhazh.telemetry.host_history_files import legacy_raw_git_path

REPO = Path(__file__).resolve().parents[2]
SOURCE_TREE_COMMIT = "e328c5f885c67a516f88214e87a54e014c3ef665"
VIEW_TREE_COMMIT = "65b6e08d3dfbb973b7271f1d9a47db3016df75e8"
MANIFEST_SHA256 = "8b577d763b968d9fc43478d758d2afc61adb9130a177966054580fb780bca1e3"
SCOPE_SHA256 = "02b4069ca27531dad642cc06b3fa8c8ef0492c4f2c4a0662c51aa7e8ae008074"
EVIDENCE_SHA256 = "af6069b05dac4183c84b0313a9138a359f531b3c70959c691548c2d339308607"
VIEW_SHA256 = "fd1215d16e894e676c771447acad034626473f41e36b532e1c61b96644ab3c21"


@pytest.fixture
def replay_workspace() -> Iterator[Path]:
    parent = REPO / "backend" / "var" / "d16-replay-tests"
    parent.mkdir(parents=True, exist_ok=True)
    root = parent / str(uuid.uuid4())
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root)


def _manifest() -> HistoryManifest:
    path = REPO / "tests" / "fixtures" / "host-events" / "d16-supplied-history-manifest.json"
    encoded = path.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == MANIFEST_SHA256
    document = json.loads(encoded)
    assert isinstance(document, dict)
    assert set(document) == {
        "version",
        "converted_at",
        "invocation",
        "isolated_root",
        "range_start",
        "range_end",
        "roots",
        "closed_periods",
        "sources",
        "legacy_raw_evidence",
    }
    assert all(
        set(source)
        == {"root", "path", "kind", "sha256", "bytes", "covers", "period", "dependencies"}
        for source in document["sources"]
    )
    assert all(
        set(evidence)
        == {"compact_path", "path", "sha256", "bytes", "git_commit", "git_blob", "attempt"}
        for evidence in document["legacy_raw_evidence"]
    )
    return HistoryManifest.model_validate(document)


def _git_blob(revision: str, path: str) -> bytes:
    environment = os.environ.copy()
    environment.update({"GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"})
    result = subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "cat-file",
            "blob",
            f"{revision}:{path}",
        ],
        cwd=REPO,
        env=environment,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(f"missing pinned Git blob: {revision}:{path}")
    return result.stdout


def _materialize_inputs(manifest: HistoryManifest, workspace: Path) -> None:
    sources = {source.path: source for source in manifest.sources}
    roots = {root.name: root for root in manifest.roots}
    inputs = [
        (
            VIEW_TREE_COMMIT if source.kind == "view" else SOURCE_TREE_COMMIT,
            source.path,
            source.path,
        )
        for source in manifest.sources
    ]
    for evidence in manifest.legacy_raw_evidence:
        compact = sources[evidence.compact_path]
        git_path = legacy_raw_git_path(evidence, roots[compact.root])
        inputs.append((evidence.git_commit, git_path, evidence.path))
    for revision, git_path, relative_path in inputs:
        target = workspace / Path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_git_blob(revision, git_path))


def _input_hashes(manifest: HistoryManifest, workspace: Path) -> dict[str, tuple[int, str]]:
    inputs = {
        source.path: (source.bytes, source.sha256)
        for source in manifest.sources
    } | {
        evidence.path: (evidence.bytes, evidence.sha256)
        for evidence in manifest.legacy_raw_evidence
    }
    actual: dict[str, tuple[int, str]] = {}
    for relative_path in inputs:
        path = workspace / Path(relative_path)
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        actual[relative_path] = (path.stat().st_size, digest)
    assert actual == inputs, "materialized history inputs differ from the manifest"
    return actual


def _history_config() -> dict[str, Any]:
    config_root = REPO / "config"
    experiment = json.loads((config_root / "host-telemetry-experiment.json").read_bytes())
    migration = json.loads((config_root / "host-history-migration.json").read_bytes())
    return {
        "verification_limits": experiment["verification_limits"],
        "history_migration_limits": migration["history_migration_limits"],
    }


@pytest.mark.skipif(sys.platform != "linux", reason="this regression runs on Ubuntu CI")
def test_supplied_manifest_replays_exact_migrated_consumers(
    replay_workspace: Path,
) -> None:
    manifest = _manifest()
    assert len(manifest.sources) == 308
    assert len(manifest.legacy_raw_evidence) == 29
    assert manifest.scope_hash() == SCOPE_SHA256

    _materialize_inputs(manifest, replay_workspace)
    original_inputs = _input_hashes(manifest, replay_workspace)
    report = dry_run(
        manifest,
        workspace_root=replay_workspace,
        config_document=_history_config(),
    )

    assert _input_hashes(manifest, replay_workspace) == original_inputs
    assert report.scope_hash == SCOPE_SHA256
    assert report.evidence_hash == EVIDENCE_SHA256
    assert report.consumer_mode == "migrated_consumers"
    assert report.inventory_complete
    assert report.historical_readiness == "ready"
    assert report.blocked_by == ()
    assert report.production_cutover_readiness == "blocked"
    assert report.production_cutover_blocked_by == (
        "d7_all_family_single_writer_ubuntu_evidence_not_verified",
    )
    assert len(report.files) == 308
    assert all(file.status == "candidate_complete" for file in report.files)
    assert tuple(
        (file.old_physical_sha256, file.original_bytes) for file in report.files
    ) == tuple((source.sha256, source.bytes) for source in manifest.sources)
    assert all(
        (replay_workspace / report.bundle_root / file.candidate_path).is_file()
        for file in report.files
        if file.candidate_path is not None
    )
    assert report.original_settled_keys == report.normalized_settled_keys == 815

    replay = report.consumer_replay
    assert replay is not None
    assert replay.candidate_source_count == 307
    assert replay.host_rows_read == 815
    assert replay.work_rows_read == 587
    assert replay.view_bytes == 2542
    assert replay.view_sha256 == VIEW_SHA256
    assert (replay_workspace / report.bundle_root / "report.json").is_file()
