"""Hold one approved change in an operator-controlled offline local checkout.

OS/index locks serialize maintenance/cooperative Git, not arbitrary writes or the
remote Ubuntu filesystem. The operator must keep this checkout offline throughout.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Timer
from uuid import uuid4

from idhazh.contracts.host_history_transaction import (
    JOURNAL_VERSION,
    HistoryApplyApproval,
    HistoryMaintenanceOwner,
)
from idhazh.publication_lock import acquire_lock, release_lock
from idhazh.telemetry.host_output_verify import VerificationLimits, _read_bytes, _safe_path

# Fixed known launchers, not a repository scan or a configurable process supervisor.
KNOWN_PROCESS_NAMES = ("python", "pythonw", "node", "idhazh-host-telemetry", "llama-server")
KNOWN_WRITER_ENTRYPOINTS = (
    "idhazh", "idhazh.exe",
    "d7_host_telemetry.py", "host_telemetry_session.py", "host_telemetry_workload.py",
    "migrate_host_fingerprints.py", "gardener_publish.py", "publish_to_repo.py",
    "digest_publish.py", "digest_assemble.py", "data_wrangler.py",
    "record_publish.py", "council_publish.py", "council_matrix.py",
    "encoder_publish.py", "compare_summary_encoders.py", "runtime_sweep.py",
    "gardener_shards.py", "measure_corpus.py", "measure_llm.py", "memory_sampler.py",
    "publication_git.py", "pipeline_test_publish.py",
)


class MaintenanceError(RuntimeError):
    """The checkout is not exclusively held; an operator must resolve the conflict."""


def _command(workspace: Path, args: Sequence[str], cap: int, timeout: float) -> bytes:
    # Do not let inherited Git overrides redirect the lock to another checkout.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", TZ="UTC", LC_ALL="C")
    with subprocess.Popen(
        args, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as process:
        timer = Timer(timeout, process.kill)
        timer.start()
        try:
            assert process.stdout is not None
            output: bytes = process.stdout.read(cap + 1)
            if len(output) > cap:
                raise MaintenanceError("maintenance command exceeds its output bound")
            code = process.wait(timeout=timeout)
            if code != 0:
                raise MaintenanceError(
                    f"maintenance command failed or timed out: {args[0]} (exit {code})"
                )
            return output
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
            process.wait()


def _read_small(path: Path, cap: int) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(cap + 1)
    if len(data) > cap:
        raise MaintenanceError("maintenance input exceeds its byte bound")
    return data


def _process_created_at(workspace: Path, cap: int, timeout: float) -> str:
    if sys.platform == "win32":
        script = (
            "$ErrorActionPreference='Stop';"
            f"(Get-CimInstance Win32_Process -Filter 'ProcessId={os.getpid()}'"
            ").CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')"
        )
        args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
        return _command(workspace, args, cap, timeout).decode("ascii").strip()
    else:
        if not Path("/proc/self/stat").exists():
            raise MaintenanceError("local process start time is unavailable")
        ticks = _read_small(Path("/proc/self/stat"), cap).rsplit(b")", 1)[1].split()[19]
        boot = next(
            line.split()[1] for line in _read_small(Path("/proc/stat"), cap).splitlines()
            if line.startswith(b"btime ")
        )
        started = datetime.fromtimestamp(int(boot) + int(ticks) / os.sysconf("SC_CLK_TCK"), UTC)
        return started.strftime("%Y-%m-%dT%H:%M:%SZ")


def _refuse_writers(workspace: Path, cap: int, timeout: float, max_processes: int) -> None:
    if sys.platform == "win32":
        filters = " OR ".join(f"Name='{name}.exe'" for name in KNOWN_PROCESS_NAMES)
        script = (
            "$ErrorActionPreference='Stop';"
            "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
            "ConvertTo-Json -Compress -InputObject "
            f"@(Get-CimInstance Win32_Process -Filter \"{filters}\" | "
            f"Select-Object -First {max_processes + 1} ProcessId,Name,CommandLine)"
        )
        args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
        raw = _command(workspace, args, cap, timeout)
        processes = [
            (item["ProcessId"], item["Name"], item["CommandLine"]) for item in json.loads(raw)
        ]
    else:
        names = (*KNOWN_PROCESS_NAMES, "idhazh-host-tel", "python3",
                 "python3.12", "python3.13", "python3.14")
        raw = _command(
            workspace, ["ps", "-C", ",".join(names), "-o", "pid=,comm="],
            cap, timeout,
        )
        processes = [
            (int(parts[0]), parts[1], "")
            for line in raw.decode("utf-8").splitlines() if (parts := line.split(None, 1))
        ]
    if len(processes) > max_processes:
        raise MaintenanceError("local writer inspection exceeds its process bound")
    target = str(workspace).replace("\\", "/").casefold()
    for pid, name, command in processes:
        if pid == os.getpid():
            continue
        name = name.casefold()
        if sys.platform == "win32":
            if not command:
                raise MaintenanceError(f"cannot resolve a potential local writer: PID {pid}")
            tokens = [token.strip('"') for token in shlex.split(command, posix=False)]
        else:
            # ps flattens argv: inline Python code must not become module arguments.
            try:
                arguments = _read_small(Path("/proc") / str(pid) / "cmdline", cap)
            except FileNotFoundError:
                continue
            tokens = [os.fsdecode(token) for token in arguments.split(b"\0") if token]
            if not tokens:
                raise MaintenanceError(f"cannot resolve a potential local writer: PID {pid}")
            command = "\0".join(tokens)
        scripts = [
            token for token in tokens if Path(token).name.casefold() in KNOWN_WRITER_ENTRYPOINTS
        ]
        module = any(
            token == "-m" and (
                tokens[index + 1] == "idhazh"
                or tokens[index + 1].startswith(("idhazh.", "utilities."))
            )
            for index, token in enumerate(tokens[:-1])
        )
        native = name.removesuffix(".exe") in ("idhazh-host-telemetry", "idhazh-host-tel",
                                               "llama-server")
        node = name.removesuffix(".exe") == "node" and any(
            part in command.replace("\\", "/").casefold()
            for part in (target, "backend/", "frontend/", "yen-idhazh")
        )
        if not (scripts or module or native or node):
            continue
        scopes = [
            tokens[index + 1] for index, token in enumerate(tokens[:-1])
            if token in ("--workspace", "--repo")
        ]
        unresolved = not scopes or any(
            not Path(token).is_absolute() or not Path(token).is_dir() for token in scopes
        ) or any(
            not Path(token).is_absolute() or not Path(token).exists() for token in scripts
        )
        if unresolved or target in command.replace("\\", "/").casefold() or any(
            Path(token).resolve().is_relative_to(workspace)
            or workspace.is_relative_to(Path(token).resolve()) for token in (*scripts, *scopes)
        ):
            raise MaintenanceError(
                f"known or unresolved local writer is active: PID {pid} "
                f"({name}; scripts={[Path(path).name for path in scripts]}; "
                f"scopes={scopes}; unresolved={unresolved})"
            )


class MaintenanceLease:
    """A context-owned lease; successful checks re-read the actual checkout and lock."""

    def __init__(
        self, workspace: Path, approval: HistoryApplyApproval,
        cap: int, timeout: float,
    ) -> None:
        self._active = False
        self._workspace, self._approval = workspace, approval
        self._cap, self._timeout = cap, timeout
        self._index = Path(self._git("rev-parse", "--path-format=absolute", "--git-path", "index"))
        self._head = Path(self._git("rev-parse", "--path-format=absolute", "--git-path", "HEAD"))
        self._head_bytes = _read_bytes(self._head, root=self._head.parent, cap=cap)
        self._owner = HistoryMaintenanceOwner(
            version=JOURNAL_VERSION, nonce=uuid4(), pid=os.getpid(),
            process_created_at=_process_created_at(workspace, cap, timeout),
            target_device=approval.target_device, target_inode=approval.target_inode,
            manifest_sha256=approval.manifest_sha256, scope_hash=approval.scope_hash,
            report_evidence_hash=approval.report_evidence_hash,
            git_head=self._git("rev-parse", "--verify", "HEAD"),
            git_index_sha256=self._index_hash(),
        )
        self._lock = self._index.with_name(self._index.name + ".lock")
        self._lock_bytes = (self._owner.model_dump_json() + "\n").encode("utf-8")
        self._lock_identity: tuple[int, int] | None = None

    @property
    def owner(self) -> HistoryMaintenanceOwner:
        return self._owner

    def _git(self, *args: str) -> str:
        output = _command(self._workspace, ["git", *args], self._cap, self._timeout)
        return output.decode("utf-8").strip()

    def _index_hash(self) -> str | None:
        try:
            data = _read_bytes(self._index, root=self._index.parent, cap=self._cap)
        except FileNotFoundError:
            return None
        return hashlib.sha256(data).hexdigest()

    def _require_own_lock(self) -> None:
        try:
            info = self._lock.lstat()
            if (info.st_dev, info.st_ino) == self._lock_identity and (
                _read_bytes(self._lock, root=self._lock.parent, cap=self._cap) == self._lock_bytes
            ):
                return
        except (OSError, ValueError):
            pass
        raise MaintenanceError("Git index lock changed; lock recovery needed")

    def require_active(
        self, workspace: Path, *, manifest_sha256: str, scope_hash: str,
        report_evidence_hash: str,
    ) -> None:
        if not self._active or os.getpid() != self._owner.pid:
            raise MaintenanceError("maintenance lease has been released")
        bound = HistoryApplyApproval.model_validate(self._approval.model_dump() | {
            "manifest_sha256": manifest_sha256, "scope_hash": scope_hash,
            "report_evidence_hash": report_evidence_hash,
        })
        if bound != self._approval:
            raise MaintenanceError("maintenance lease scope differs from approval")
        path = _safe_path(workspace.absolute(), workspace.absolute())
        info = path.stat()
        if (info.st_dev, info.st_ino) != (
            self._owner.target_device, self._owner.target_inode,
        ) or not self._workspace.samefile(path):
            raise MaintenanceError("maintenance target physical identity changed")
        if (
            self._git("rev-parse", "--verify", "HEAD") != self._owner.git_head
            or _read_bytes(self._head, root=self._head.parent, cap=self._cap) != self._head_bytes
            or self._index_hash() != self._owner.git_index_sha256
            or Path(self._git("rev-parse", "--path-format=absolute", "--git-path", "index"))
            != self._index
        ):
            raise MaintenanceError("maintenance Git HEAD or index changed")
        self._require_own_lock()


@contextmanager
def offline_maintenance(
    workspace: Path, approval: HistoryApplyApproval,
) -> Iterator[MaintenanceLease]:
    approval = HistoryApplyApproval.model_validate(approval.model_dump())
    workspace = _safe_path(workspace.absolute(), workspace.absolute())
    info = workspace.stat()
    if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (
        approval.target_device, approval.target_inode,
    ):
        raise MaintenanceError("approval target physical identity differs")
    root = Path(__file__).resolve().parents[3]
    # The repository-authored configuration has a fixed 64 KiB input envelope.
    config_path = root / "config" / "host-telemetry-experiment.json"
    config = json.loads(_read_bytes(config_path, root=root, cap=65536))
    cap = VerificationLimits(**config["verification_limits"]).max_file_bytes
    migration_path = root / "config" / "host-history-migration.json"
    migration = json.loads(_read_bytes(migration_path, root=root, cap=65536))
    timeout_seconds = migration["offline_maintenance"]["command_timeout_seconds"]
    max_processes = config["capture_limits"]["max_processes"]
    for value in (timeout_seconds, max_processes):
        if type(value) is not int or value < 1:
            raise MaintenanceError("invalid maintenance inspection bounds")
    timeout = float(timeout_seconds)
    _refuse_writers(workspace, cap, timeout, max_processes)
    top = _command(workspace, ["git", "rev-parse", "--show-toplevel"], cap, timeout)
    if not Path(top.decode("utf-8").strip()).samefile(workspace):
        raise MaintenanceError("maintenance target must be the Git checkout root")
    lock_path = workspace / "backend" / "var" / "d17-maintenance" / "owner.lock"
    directory = workspace
    for part in ("backend", "var", "d17-maintenance"):
        directory /= part
        directory.mkdir(exist_ok=True)
        _safe_path(workspace, directory)
    try:
        _safe_path(workspace, lock_path)
    except FileNotFoundError:
        pass
    with lock_path.open("a+b") as handle:
        opened = os.fstat(handle.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise MaintenanceError("maintenance OS lock is not a dedicated regular file")
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        acquire_lock(handle.fileno())
        lease: MaintenanceLease | None = None
        try:
            lease = MaintenanceLease(workspace, approval, cap, timeout)
            if len(lease._lock_bytes) > cap:
                raise MaintenanceError("maintenance owner exceeds its byte bound")
            try:
                descriptor = os.open(lease._lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                raise MaintenanceError("Git index lock exists; lock recovery needed") from None
            with os.fdopen(descriptor, "wb") as index_lock:
                owned = os.fstat(index_lock.fileno())
                lease._lock_identity = owned.st_dev, owned.st_ino
                index_lock.write(lease._lock_bytes)
                index_lock.flush()
                os.fsync(index_lock.fileno())
            lease._active = True
            lease.require_active(workspace, manifest_sha256=approval.manifest_sha256,
                                 scope_hash=approval.scope_hash,
                                 report_evidence_hash=approval.report_evidence_hash)
            yield lease
        finally:
            try:
                if lease is not None:
                    lease._active = False
                    if lease._lock_identity is not None:
                        lease._require_own_lock()
                        lease._lock.unlink()
            finally:
                handle.seek(0)
                release_lock(handle.fileno())
