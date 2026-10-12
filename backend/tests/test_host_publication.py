"""Do real Rust files reach publication unchanged, under independently declared authority?"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from gardener._garden import an_origin, git, quiet_git, write
from retention._trees import health_row

from idhazh import completed_writes, ledger
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_output import (
    HOST_PRODUCER,
    HostPlannedFile,
    HostPublicationReceipt,
    HostStoredRow,
    HostWriteCompletion,
    HostWritePlan,
    HostWriterIdentity,
    canonical_host_rows,
    fingerprint_v2,
    host_file_id,
    host_unit_id,
)
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.outcome import Shard
from idhazh.ledger import paths
from idhazh.telemetry import host_publication as host_publication_module
from idhazh.telemetry.host_output_verify import VerificationLimits
from idhazh.telemetry.host_publication import (
    MODE_ENV,
    RECEIPT_ENV,
    consume_host_publication,
    reconcile_host_writes,
    verify_host_publication,
)
from utilities import digest_publish, gardener_publish, publication_evidence, record_publish
from utilities.publish_to_repo import Status

ROOT = Path(__file__).resolve().parents[2]
DAY = "2026-10-10"
RETRY = {
    "deadline_seconds": {"default": 300},
    "base_step_seconds": 0.001,
    "ceiling_seconds": 0.001,
    "ceiling_after": 1,
}
pytestmark = pytest.mark.contract


def native_receipt(
    repo: Path,
    identity: WriterIdentity,
    *,
    codec: str = "json",
    prefix: tuple[str, ...] = ("host-fingerprint",),
) -> tuple[HostPublicationReceipt, VerificationLimits]:
    """Only Rust files raw rows; Python supplies a typed plan and rebases receipt coordinates."""
    config = json.loads((ROOT / "config/host-telemetry-experiment.json").read_bytes())
    limits = VerificationLimits(**config["verification_limits"])
    fixture = json.loads((ROOT / "tests/fixtures/host-events/file-parity.json").read_bytes())
    writer = HostWriterIdentity.model_validate(identity.model_dump() | {"producer": HOST_PRODUCER})
    unit = host_unit_id(covers=DAY, identity=writer)
    file_id = host_file_id(
        unit=unit, attempt=identity.attempt, written_at_ms=fixture["written_at_ms"]
    )
    row = HostStoredRow.model_validate(
        fixture["row"]
        | {
            "run_id": identity.run_id,
            "job": identity.job,
            "shard": identity.shard,
            "ledger": "host-fingerprint",
            "covers": DAY,
            "attempt": identity.attempt,
            "unit_id": str(unit),
        }
    )
    row = HostStoredRow.model_validate(
        row.model_dump() | {"fingerprint": fingerprint_v2(row), "fingerprint_version": 2}
    )
    planned = HostPlannedFile.model_validate(
        {
            "format": codec,
            "relative_path": (
                f"raw/{'/'.join(prefix)}/{DAY.replace('-', '/')}/{file_id}."
                + ("json" if codec == "json" else "parquet")
            ),
            "rows": [row],
            "envelope": {
                "version": "2026-10-10",
                "row_schema_version": "2026-10-10",
                "tier": "raw",
                "ledger": "host-fingerprint",
                "covers": DAY,
                "written_at_ms": fixture["written_at_ms"],
                "identity": writer,
                "unit_id": unit,
                "file_id": file_id,
                "content_sha256": hashlib.sha256(canonical_host_rows([row])).hexdigest(),
                "writer": (
                    "idhazh_rust.ledger.json_lines"
                    if codec == "json"
                    else "idhazh_rust.ledger.parquet"
                ),
                "writer_version": "0.1.0" if codec == "json" else "60.0.0",
                "compression": "none" if codec == "json" else "zstd",
            },
        }
    )
    repo_relative = repo.relative_to(ROOT).as_posix()
    plan = HostWritePlan(
        version="2026-10-10",
        event_id=uuid4(),
        target_root=f"{repo_relative}/state",
        publication_identity=writer,
        prefix=prefix,
        files=(planned,),
    )
    source = repo / "backend/var/input.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(plan.to_json(), encoding="ascii", newline="\n")
    binary = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "backend/var/rust-host-telemetry"))
    binary /= "debug/receipts-fixture.exe" if os.name == "nt" else "debug/receipts-fixture"
    assert binary.is_file(), "Build the locked native receipts fixture before these tests."
    result = subprocess.run(
        [
            str(binary),
            "write",
            source.relative_to(ROOT).as_posix(),
            f"{repo_relative}/backend/var/native-evidence",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode()
    completion = HostWriteCompletion.model_validate(json.loads(result.stdout)["completion"])
    # Absolute files remain where Rust wrote them. Only the workspace coordinate changes.
    receipt = HostPublicationReceipt(
        version=completion.receipt.version,
        identity=completion.receipt.identity,
        writes={
            Path(path).relative_to(repo_relative).as_posix(): digest
            for path, digest in completion.receipt.writes.items()
        },
    )
    return receipt, limits


@pytest.fixture
def case(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, Path, WriterIdentity]]:
    workspace = ROOT / "backend/var/host-publication-tests" / uuid4().hex
    workspace.mkdir(parents=True)
    quiet_git(workspace, monkeypatch)
    monkeypatch.setenv(MODE_ENV, "legacy")
    monkeypatch.delenv(RECEIPT_ENV, raising=False)
    try:
        origin, repo = an_origin(workspace, {"config/push-retry.json": json.dumps(RETRY) + "\n"})
        source = git(repo, "rev-parse", "HEAD").strip()
        identity = WriterIdentity(
            run_id=f"{DAY}-42",
            attempt=1,
            job="work",
            shard=0,
            git_sha=source,
            producer="utilities.digest_publish",
        )
        yield origin, repo, identity
    finally:
        shutil.rmtree(workspace, onexc=remove_readonly)


def remove_readonly(action: Any, path: str, error: BaseException) -> None:
    if not isinstance(error, PermissionError):
        raise error
    Path(path).chmod(stat.S_IWRITE | stat.S_IREAD)
    action(path)


@pytest.mark.parametrize("codec", ["json", "parquet"])
def test_publisher_stages_same_rust_bytes_and_keeps_foreign_index(
    case: tuple[Path, Path, WriterIdentity],
    codec: str,
) -> None:
    origin, repo, identity = case
    receipt, limits = native_receipt(repo, identity, codec=codec)
    with completed_writes.collect() as python_completed:
        ledger.persist(
            repo / "state",
            [health_row(day=DAY, run=42, number=1, stage=ItemStage.PUBLISH)],
            ledger=LedgerName.ITEM_HEALTH,
            covers=DAY,
            identity=identity.model_copy(update={"producer": "stages.record"}),
        )
    publication_evidence.save(repo, identity, "record", python_completed)
    before = {
        path: ((repo / path).read_bytes(), (repo / path).stat().st_mtime_ns)
        for path in receipt.writes
    }
    write(repo / "foreign-index", "not an output\n")
    git(repo, "add", "foreign-index")
    index = (repo / ".git/index").read_bytes()
    result = digest_publish.land(
        repo=repo, identity=identity, date=DAY, host_receipt=receipt, host_limits=limits
    )
    assert result.status is Status.LANDED
    assert (repo / ".git/index").read_bytes() == index
    for path, (data, modified) in before.items():
        actual = subprocess.run(
            ["git", f"--git-dir={origin}", "show", f"main:{path}"],
            capture_output=True,
            check=True,
        ).stdout
        assert actual == data == (repo / path).read_bytes()
        assert (repo / path).stat().st_mtime_ns == modified
    assert git(origin, "ls-tree", "main", "--", "foreign-index") == ""
    for path in python_completed:
        relative = path.relative_to(repo).as_posix()
        assert (
            subprocess.run(
                ["git", f"--git-dir={origin}", "show", f"main:{relative}"],
                capture_output=True,
                check=True,
            ).stdout
            == path.read_bytes()
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", f"{DAY}-43"),
        ("attempt", 2),
        ("job", "plan"),
        ("shard", 1),
        ("git_sha", "a" * 40),
    ],
)
def test_receipt_never_supplies_the_expected_invocation(
    case: tuple[Path, Path, WriterIdentity],
    field: str,
    value: Any,
) -> None:
    _, repo, identity = case
    receipt, limits = native_receipt(repo, identity)
    foreign = WriterIdentity.model_validate(identity.model_dump() | {field: value})
    with pytest.raises(ValueError, match="another executed invocation"):
        verify_host_publication(receipt, repo=repo, identity=foreign, date=DAY, limits=limits)


def test_native_date_registry_and_byte_budgets_are_independent(
    case: tuple[Path, Path, WriterIdentity],
) -> None:
    _, repo, identity = case
    receipt, limits = native_receipt(repo, identity, prefix=("pipeline-tests", "host-fingerprint"))
    with pytest.raises(ValueError, match="registry address"):
        verify_host_publication(receipt, repo=repo, identity=identity, date=DAY, limits=limits)
    registry = paths.overlay_registry(("pipeline-tests",))
    assert verify_host_publication(
        receipt, repo=repo, identity=identity, date=DAY, limits=limits, registry=registry
    ) == dict(receipt.writes)
    with pytest.raises(ValueError, match="registry address"):
        verify_host_publication(
            receipt,
            repo=repo,
            identity=identity,
            date="2026-10-11",
            limits=limits,
            registry=registry,
        )
    with pytest.raises(ValueError, match="byte limit"):
        verify_host_publication(
            receipt,
            repo=repo,
            identity=identity,
            date=DAY,
            limits=replace(limits, max_total_bytes=1),
            registry=registry,
        )


def test_missing_or_changed_native_evidence_is_not_a_success(
    case: tuple[Path, Path, WriterIdentity],
) -> None:
    _, repo, identity = case
    with pytest.raises(ValueError, match="completed host receipt"):
        consume_host_publication(
            repo=repo, identity=identity, date=DAY, environment={MODE_ENV: "rust"}
        )
    assert (
        consume_host_publication(repo=repo / "absent", identity=identity, date=DAY, environment={})
        == {}
    )
    receipt, limits = native_receipt(repo, identity)
    path = next(iter(receipt.writes))
    with (repo / path).open("ab") as file:
        file.write(b"\n")
    with pytest.raises(ValueError, match="SHA256"):
        verify_host_publication(receipt, repo=repo, identity=identity, date=DAY, limits=limits)
    (repo / path).unlink()
    with pytest.raises(OSError):
        verify_host_publication(receipt, repo=repo, identity=identity, date=DAY, limits=limits)


def test_serialized_receipt_is_bounded_and_cannot_replace_python_health(
    case: tuple[Path, Path, WriterIdentity],
) -> None:
    _, repo, identity = case
    receipt, limits = native_receipt(repo, identity)
    target = repo / "backend/var/receipt.json"
    target.write_text(receipt.to_json(), encoding="ascii", newline="\n")
    environment = {MODE_ENV: "rust", RECEIPT_ENV: target.relative_to(repo).as_posix()}
    native = consume_host_publication(
        repo=repo, identity=identity, date=DAY, limits=limits, environment=environment
    )
    write(
        repo / "config/host-telemetry-experiment.json",
        (ROOT / "config/host-telemetry-experiment.json").read_text(encoding="ascii"),
    )
    assert (
        consume_host_publication(repo=repo, identity=identity, date=DAY, environment=environment)
        == native
    )
    health = {"state/raw/item-health/health.json": "a" * 64}
    assert reconcile_host_writes(health, native) == health | native
    foreign = dict(native)
    foreign[next(iter(foreign))] = "b" * 64
    with pytest.raises(ValueError, match="native host ownership"):
        reconcile_host_writes(foreign, native)
    with pytest.raises(ValueError, match="file byte limit"):
        consume_host_publication(
            repo=repo,
            identity=identity,
            date=DAY,
            limits=replace(limits, max_file_bytes=1),
            environment=environment,
        )


def test_only_the_independent_off_control_admits_empty_native_receipt(
    case: tuple[Path, Path, WriterIdentity],
) -> None:
    _, repo, identity = case
    receipt, limits = native_receipt(repo, identity)
    with pytest.raises(ValueError, match="disabled host instrumentation"):
        verify_host_publication(
            receipt, repo=repo, identity=identity, date=DAY, limits=limits, host_enabled=False
        )
    empty = HostPublicationReceipt.model_validate(receipt.model_dump(mode="json") | {"writes": {}})
    assert (
        verify_host_publication(
            empty, repo=repo, identity=identity, date=DAY, limits=limits, host_enabled=False
        )
        == {}
    )
    with pytest.raises(ValueError, match="conflicts with native host ownership"):
        reconcile_host_writes(receipt.writes, {})
    with pytest.raises(ValueError, match="no completed host evidence"):
        verify_host_publication(empty, repo=repo, identity=identity, date=DAY, limits=limits)
    foreign = identity.model_copy(update={"attempt": identity.attempt + 1})
    with pytest.raises(ValueError, match="another executed invocation"):
        verify_host_publication(
            empty, repo=repo, identity=foreign, date=DAY, limits=limits, host_enabled=False
        )


def test_publisher_uses_the_same_closed_ledger_control_as_the_producer(
    case: tuple[Path, Path, WriterIdentity],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, repo, identity = case
    receipt, limits = native_receipt(repo, identity)
    empty = HostPublicationReceipt.model_validate(receipt.model_dump(mode="json") | {"writes": {}})
    monkeypatch.setattr(host_publication_module.ledger, "accepts_new_rows", lambda *args: False)
    assert (
        consume_host_publication(
            repo=repo,
            identity=identity,
            date=DAY,
            receipt=empty,
            limits=limits,
            host_enabled=True,
        )
        == {}
    )


@pytest.mark.parametrize("correction", ["empty", "foreign-path", "wrong-hash", "python-writer"])
def test_receipt_reconciliation_refuses_missing_foreign_or_non_native_files(
    case: tuple[Path, Path, WriterIdentity],
    correction: str,
) -> None:
    _, repo, identity = case
    receipt, limits = native_receipt(repo, identity)
    writes = dict(receipt.writes)
    path = next(iter(writes))
    if correction == "empty":
        writes.clear()
    elif correction == "foreign-path":
        writes["state/raw/item-health/foreign.json"] = writes[path]
    elif correction == "wrong-hash":
        writes[path] = "0" * 64
    else:
        # A real Python codec emits a different physical file; no native bytes are copied.
        from idhazh.contracts.host_fingerprint import HostFingerprintRow

        fixture = json.loads((ROOT / "tests/fixtures/host-events/file-parity.json").read_bytes())
        row = HostFingerprintRow.model_validate(
            fixture["row"] | {"run_id": identity.run_id, "job": identity.job, "shard": 0}
        )
        with completed_writes.collect() as evidence:
            ledger.persist(
                repo / "state",
                [row],
                ledger=LedgerName.HOST_FINGERPRINT,
                covers=DAY,
                identity=identity.model_copy(update={"producer": HOST_PRODUCER}),
            )
        writes = {held.relative_to(repo).as_posix(): digest for held, digest in evidence.items()}
    forged = HostPublicationReceipt.model_validate(
        receipt.model_dump(mode="json") | {"writes": writes}
    )
    with pytest.raises(ValueError):
        verify_host_publication(forged, repo=repo, identity=identity, date=DAY, limits=limits)


@pytest.mark.parametrize("permitted", [False, True])
def test_gardener_native_files_need_separate_publication_authority(
    case: tuple[Path, Path, WriterIdentity],
    permitted: bool,
) -> None:
    origin, repo, held = case
    identity = WriterIdentity.model_validate(
        held.model_dump() | {"job": "run-tasks", "producer": "gardener.runner"}
    )
    receipt, limits = native_receipt(repo, identity)
    record = "state/raw/gardener/2026/10/10/record.json"
    write(repo / record, '{"task":"generated-publication-case"}\n')
    shard = Shard(
        index=0,
        task_names=("generated-publication-case",),
        record_path=record,
        written_paths=frozenset({record}),
        deleted_paths=frozenset(),
        owned_prefixes=frozenset({"state/raw/gardener"}),
        message="generated gardener publication",
    )
    before = git(origin, "rev-parse", "main")
    result = gardener_publish.publish(
        shard,
        attempts=1,
        repo=repo,
        identity=identity,
        write_permissions=(
            ("state/raw/gardener", "state/raw/host-fingerprint")
            if permitted
            else ("state/raw/gardener",)
        ),
        delete_permissions=(),
        host_receipt=receipt,
        host_limits=limits,
    )
    if not permitted:
        assert result.exit_code == 2
        assert git(origin, "rev-parse", "main") == before
    else:
        assert result.exit_code == 0
        for path in receipt.writes:
            assert (
                subprocess.run(
                    ["git", f"--git-dir={origin}", "show", f"main:{path}"],
                    capture_output=True,
                    check=True,
                ).stdout
                == (repo / path).read_bytes()
            )


@pytest.mark.parametrize("job", ["runtime", "collect"])
def test_measure_consumes_native_pipeline_registry_without_python_probe(
    case: tuple[Path, Path, WriterIdentity],
    monkeypatch: pytest.MonkeyPatch,
    job: str,
) -> None:
    origin, repo, held = case
    identity = WriterIdentity.model_validate(
        held.model_dump() | {"job": job, "producer": "utilities.record_publish"}
    )
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("GITHUB_SHA", identity.git_sha)
    receipt, limits = native_receipt(repo, identity, prefix=("pipeline-tests", "host-fingerprint"))
    if job == "runtime":
        receipt_path = repo / "backend/var/publication-receipt.json"
        receipt_path.write_text(receipt.to_json(), encoding="ascii", newline="\n")
        write(
            repo / "config/host-telemetry-experiment.json",
            (ROOT / "config/host-telemetry-experiment.json").read_text(encoding="ascii"),
        )
        monkeypatch.setenv(MODE_ENV, "rust")
        monkeypatch.setenv(RECEIPT_ENV, str(receipt_path))
        command = [
            "land",
            "measure",
            "--date",
            DAY,
            "--execution",
            "42",
            "--commit",
            identity.git_sha,
            "--job",
            job,
        ]
        before = git(origin, "rev-parse", "main")
        with monkeypatch.context() as invocation:
            invocation.chdir(repo)
            assert record_publish.main([*command, "--no-host-fingerprint"]) == 2
            assert git(origin, "rev-parse", "main") == before
            assert record_publish.main([*command, "--host-fingerprint"]) == 0
    else:
        assert (
            record_publish.land(
                "measure",
                repo=repo,
                date=DAY,
                identity=identity,
                host_receipt=receipt,
                host_limits=limits,
            )
            == 0
        )
    for path in receipt.writes:
        native = (repo / path).read_bytes()
        assert (
            subprocess.run(
                ["git", f"--git-dir={origin}", "show", f"main:{path}"],
                capture_output=True,
                check=True,
            ).stdout
            == native
        )
