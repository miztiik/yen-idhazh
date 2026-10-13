"""Exercise real maintenance locks and Git state only in generated local checkouts."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from idhazh.contracts.host_history_transaction import (
    JOURNAL_VERSION,
    HistoryApplyApproval,
    HistoryMaintenanceOwner,
)
from idhazh.telemetry.host_history_maintenance import (
    MaintenanceError,
    MaintenanceLease,
    _command,
    offline_maintenance,
)

pytestmark = pytest.mark.contract


def _git(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", *args], cwd=workspace, env=env,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=check,
    )


@pytest.fixture
def workspace() -> Iterator[Path]:
    # Keep all generated files beneath this checkout, not the system temp directory.
    with tempfile.TemporaryDirectory(prefix=".d17-fixture-", dir=Path.cwd()) as directory:
        root = Path(directory)
        _git(root, "init", "--quiet")
        _git(root, "config", "user.name", "Generated fixture")
        _git(root, "config", "user.email", "fixture@example.invalid")
        _git(root, "config", "commit.gpgsign", "false")
        (root / "tracked.txt").write_bytes(b"generated original\n")
        _git(root, "add", "tracked.txt")
        _git(root, "commit", "--quiet", "-m", "generated fixture")
        yield root


def _approval(workspace: Path) -> HistoryApplyApproval:
    info = workspace.stat()
    revision = _git(workspace, "rev-parse", "HEAD").stdout.decode("ascii").strip()
    return HistoryApplyApproval(
        version=JOURNAL_VERSION, authority="unattended_user",
        authorized_at="2026-10-13T00:00:00Z",
        manifest_sha256=hashlib.sha256(b"generated manifest").hexdigest(),
        scope_hash=hashlib.sha256(b"generated scope").hexdigest(),
        report_evidence_hash=hashlib.sha256(b"generated evidence").hexdigest(),
        d16_revision=revision, d7_revision=revision,
        target_device=info.st_dev, target_inode=info.st_ino,
    )


def _check(lease: MaintenanceLease, workspace: Path, approval: HistoryApplyApproval) -> None:
    lease.require_active(
        workspace, manifest_sha256=approval.manifest_sha256,
        scope_hash=approval.scope_hash, report_evidence_hash=approval.report_evidence_hash,
    )


def _git_path(workspace: Path, name: str) -> Path:
    return Path(_git(
        workspace, "rev-parse", "--path-format=absolute", "--git-path", name,
    ).stdout.decode("utf-8").strip())


def test_real_git_staging_is_blocked_and_state_is_preserved(workspace: Path) -> None:
    approval = _approval(workspace)
    index, head = _git_path(workspace, "index"), _git_path(workspace, "HEAD")
    original_index, original_head = index.read_bytes(), head.read_bytes()
    with offline_maintenance(workspace, approval) as lease:
        index_lock = index.with_name(index.name + ".lock")
        owner = HistoryMaintenanceOwner.model_validate_json(index_lock.read_bytes())
        assert owner == lease.owner
        assert owner.pid == os.getpid()
        assert owner.git_index_sha256 == hashlib.sha256(original_index).hexdigest()
        assert owner.target_inode == workspace.stat().st_ino
        assert datetime.fromisoformat(owner.process_created_at) <= datetime.now(UTC)
        _check(lease, workspace, approval)
        with pytest.raises(FileExistsError):
            os.open(index_lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        (workspace / "tracked.txt").write_bytes(b"generated unstaged edit\n")
        staged = _git(workspace, "add", "tracked.txt", check=False)
        assert staged.returncode != 0
        assert b"index.lock" in staged.stderr
        assert index.read_bytes() == original_index
        assert head.read_bytes() == original_head
        _check(lease, workspace, approval)
        owner_lock = workspace / "backend" / "var" / "d17-maintenance" / "owner.lock"
        lock_identity = owner_lock.stat().st_dev, owner_lock.stat().st_ino
    assert not index_lock.exists()
    assert (owner_lock.stat().st_dev, owner_lock.stat().st_ino) == lock_identity
    assert (workspace / "tracked.txt").read_bytes() == b"generated unstaged edit\n"
    assert index.read_bytes() == original_index
    assert head.read_bytes() == original_head
    with pytest.raises(MaintenanceError, match="released"):
        _check(lease, workspace, approval)
    with offline_maintenance(workspace, approval) as renewed:
        _check(renewed, workspace, approval)
    assert (owner_lock.stat().st_dev, owner_lock.stat().st_ino) == lock_identity


def test_existing_index_lock_is_never_reclaimed(workspace: Path) -> None:
    lock = _git_path(workspace, "index").with_name("index.lock")
    lock.write_bytes(b"foreign existing lock\n")
    with pytest.raises(MaintenanceError, match="exists; lock recovery needed"):
        with offline_maintenance(workspace, _approval(workspace)):
            pytest.fail("an existing Git lock was reclaimed")
    assert lock.read_bytes() == b"foreign existing lock\n"


def test_exception_removes_only_owned_index_lock(workspace: Path) -> None:
    approval = _approval(workspace)
    index = _git_path(workspace, "index")
    original = index.read_bytes()
    with pytest.raises(ValueError, match="generated interruption"):
        with offline_maintenance(workspace, approval) as lease:
            _check(lease, workspace, approval)
            raise ValueError("generated interruption")
    assert not index.with_name("index.lock").exists()
    assert index.read_bytes() == original
    with pytest.raises(MaintenanceError, match="released"):
        _check(lease, workspace, approval)


@pytest.mark.parametrize("field", ["manifest_sha256", "scope_hash", "report_evidence_hash"])
def test_scope_mismatch_is_refused(workspace: Path, field: str) -> None:
    approval = _approval(workspace)
    with offline_maintenance(workspace, approval) as lease:
        different = approval.model_copy(update={field: "f" * 64})
        with pytest.raises(MaintenanceError, match="scope differs"):
            _check(lease, workspace, different)


@pytest.mark.parametrize("field", ["manifest_sha256", "scope_hash", "report_evidence_hash"])
def test_invalid_approval_hash_is_revalidated(workspace: Path, field: str) -> None:
    invalid = _approval(workspace).model_copy(update={field: "not-a-hash"})
    with pytest.raises(ValueError):
        with offline_maintenance(workspace, invalid):
            pytest.fail("invalid approval was accepted")
    assert not _git_path(workspace, "index").with_name("index.lock").exists()


def test_different_target_and_wrong_approval_identity_are_refused(workspace: Path) -> None:
    approval = _approval(workspace)
    other = workspace / "other"
    other.mkdir()
    with offline_maintenance(workspace, approval) as lease:
        with pytest.raises(MaintenanceError, match="physical identity"):
            _check(lease, other, approval)
    invalid = approval.model_copy(update={"target_inode": other.stat().st_ino})
    with pytest.raises(MaintenanceError, match="physical identity"):
        with offline_maintenance(workspace, invalid):
            pytest.fail("a different physical checkout was accepted")


@pytest.mark.parametrize("git_file", ["HEAD", "index"])
def test_changed_git_bytes_are_refused_without_restoring_foreign_changes(
    workspace: Path, git_file: str,
) -> None:
    approval = _approval(workspace)
    path = _git_path(workspace, git_file)
    original = path.read_bytes()
    changed = ((approval.d16_revision + "\n").encode("ascii") if git_file == "HEAD"
               else original + b"generated external edit")
    with offline_maintenance(workspace, approval) as lease:
        path.write_bytes(changed)
        with pytest.raises(MaintenanceError, match="Git HEAD or index changed"):
            _check(lease, workspace, approval)
    assert path.read_bytes() == changed
    path.write_bytes(original)


def test_changed_head_revision_is_refused_even_if_head_file_is_unchanged(workspace: Path) -> None:
    approval = _approval(workspace)
    future = _git(
        workspace, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "generated next commit",
    ).stdout.decode("ascii").strip()
    head = _git_path(workspace, "HEAD")
    original = head.read_bytes()
    with offline_maintenance(workspace, approval) as lease:
        _git(workspace, "update-ref", "HEAD", future)
        assert head.read_bytes() == original
        with pytest.raises(MaintenanceError, match="Git HEAD or index changed"):
            _check(lease, workspace, approval)
    assert _git(workspace, "rev-parse", "HEAD").stdout.decode("ascii").strip() == future


def test_missing_original_index_is_preserved(workspace: Path) -> None:
    approval = _approval(workspace)
    index = _git_path(workspace, "index")
    index.unlink()
    with offline_maintenance(workspace, approval) as lease:
        assert lease.owner.git_index_sha256 is None
        _check(lease, workspace, approval)
        assert _git(workspace, "add", "tracked.txt", check=False).returncode != 0
    assert not index.exists()
    assert not index.with_name("index.lock").exists()


def test_os_lock_cannot_alias_another_generated_file(workspace: Path) -> None:
    lock = workspace / "backend" / "var" / "d17-maintenance" / "owner.lock"
    lock.parent.mkdir(parents=True)
    original = (workspace / "tracked.txt").read_bytes()
    os.link(workspace / "tracked.txt", lock)
    with pytest.raises(MaintenanceError, match="dedicated regular file"):
        with offline_maintenance(workspace, _approval(workspace)):
            pytest.fail("the OS lock aliased another file")
    assert (workspace / "tracked.txt").read_bytes() == original
    assert lock.read_bytes() == original


@pytest.mark.parametrize("replacement", ["different-bytes", "same-bytes-new-inode", "missing"])
def test_foreign_lock_replacement_is_refused_and_preserved(
    workspace: Path, replacement: str,
) -> None:
    approval = _approval(workspace)
    lock = _git_path(workspace, "index").with_name("index.lock")
    with pytest.raises(MaintenanceError, match="lock recovery needed"):
        with offline_maintenance(workspace, approval) as lease:
            original = lock.read_bytes()
            if replacement == "different-bytes":
                lock.write_bytes(b"foreign replacement\n")
            elif replacement == "same-bytes-new-inode":
                foreign = lock.with_name("generated-foreign.lock")
                foreign.write_bytes(original)
                foreign.replace(lock)
            else:
                lock.unlink()
            with pytest.raises(MaintenanceError, match="lock recovery needed"):
                _check(lease, workspace, approval)
    if replacement == "missing":
        assert not lock.exists()
    else:
        assert lock.read_bytes() == (
            original if replacement == "same-bytes-new-inode" else b"foreign replacement\n"
        )
    with pytest.raises(MaintenanceError, match="released"):
        _check(lease, workspace, approval)


def test_linked_worktree_uses_its_actual_index(workspace: Path) -> None:
    linked = workspace / "generated-worktree"
    _git(workspace, "worktree", "add", "--quiet", "--detach", str(linked), "HEAD")
    assert (linked / ".git").is_file()
    linked_index = _git_path(linked, "index")
    main_index = _git_path(workspace, "index")
    assert linked_index != main_index
    original = main_index.read_bytes(), linked_index.read_bytes()
    with offline_maintenance(linked, _approval(linked)) as lease:
        assert linked_index.with_name("index.lock").exists()
        assert not main_index.with_name("index.lock").exists()
        _check(lease, linked, _approval(linked))
        assert _git(linked, "add", "tracked.txt", check=False).returncode != 0
    assert (main_index.read_bytes(), linked_index.read_bytes()) == original
    assert not linked_index.with_name("index.lock").exists()


def test_real_local_known_writer_process_is_refused(workspace: Path) -> None:
    script = workspace / "host_telemetry_session.py"
    ready = workspace / "generated-process-ready"
    script.write_text(
        "import pathlib, time\n"
        "pathlib.Path('generated-process-ready').write_bytes(b'ready')\n"
        "time.sleep(30)\n",
        encoding="utf-8", newline="\n",
    )
    process = subprocess.Popen(
        [sys.executable, "-B", str(script), "--workspace", str(workspace)],
        cwd=workspace, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.read_bytes() == b"ready"
        with pytest.raises(MaintenanceError, match="local writer"):
            with offline_maintenance(workspace, _approval(workspace)):
                pytest.fail("known local writer was not refused")
        assert not _git_path(workspace, "index").with_name("index.lock").exists()
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_subprocess_output_and_time_are_bounded(workspace: Path) -> None:
    with pytest.raises(MaintenanceError, match="output bound"):
        _command(workspace, [sys.executable, "-B", "-c", "print('x' * 1024)"], 32, 5)
    with pytest.raises(MaintenanceError, match="failed or timed out"):
        _command(workspace, [sys.executable, "-B", "-c", "import time; time.sleep(30)"], 32, 0.1)
