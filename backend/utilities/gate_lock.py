"""Run one heavy gate at a time on a machine that holds many worktrees.

The symptom this exists for. The same 1,675-test backend suite that CI finishes
in 62.68 s took 630.55 s on a developer box here, and three browser suites
running at once turned a commit CI had already passed into 11 failures. The box
is one machine, and every agent working in its own worktree starts its own gate
the moment it is ready. Nothing coordinates them, so the gates fight over the
same cores and the slowest one fails a timeout it would never have reached
alone. The failure looks like a broken branch and is not one.

Wrap the three gates measured as CPU-bound, and nothing else:

    python backend/utilities/gate_lock.py -- python -m pytest
    python backend/utilities/gate_lock.py -- npm run build
    python backend/utilities/gate_lock.py -- npm run test:browser

`ruff`, `mypy`, `svelte-check`, `shellcheck` and `bundle-gate` stay unwrapped.
Serialising a gate that finishes in seconds only adds waiting.

How it works. One lock file in the user temp directory, created with `O_CREAT`
plus `O_EXCL` - the one file operation Windows and Linux both make atomic, so
exactly one process wins the create and every other one is told the file is
already there. The winner's record carries its pid, its worktree and the second
it started, so a caller that loses says who holds the lock, from where and for
how long instead of just hanging. Standard library only, no new dependency
(Rule #8).

Two rules keep a lock from outliving the gate it belongs to. A lock whose pid is
gone is reclaimed, and a lock older than the reclaim line is reclaimed whatever
its pid says. Both are logged. A lock that could survive its holder would stop
every gate on the box, which is worse than the contention it prevents - and for
the same reason a caller that waits out `--timeout` runs the gate anyway rather
than failing it. This is a scheduling aid; it may not turn contention into a red
gate, because a red gate under contention is the defect it exists to remove.

Inside CI it does nothing at all. A GitHub runner is one job alone on its own
machine (Rule #2), and CI's `gates` job at 62.68 s is not the problem this
solves.

It reads no configuration and imports nothing from `idhazh`, so it runs from a
fresh clone with any supported Python and no install. Every knob is a flag whose
default is a constant below.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

LOG: Final = logging.getLogger("gate_lock")

# One name for the whole machine. Two worktrees are two checkouts of one
# repository on one set of cores, so they contend on the same file.
LOCK_FILENAME: Final = "yen-idhazh-gate.lock"

# Short enough that a freed lock is picked up almost at once, long enough that a
# queue of waiters costs nothing measurable.
POLL_SECONDS: Final = 2.0

# How often a waiter names the holder again. Every poll would be noise; once
# would scroll away behind a gate that runs for minutes.
REPORT_SECONDS: Final = 30.0

# A lock older than this is reclaimed whatever its pid says. The longest gate
# measured on this box is 1,098 s (full backend suite, 2026-08-30, Windows 11,
# 12 logical CPUs, n=8 runs spanning 452 to 1,098 s), so this is 6.6x the worst
# real case: far outside a live gate, and still bounded, so no lock can stop the
# box for good.
STALE_AFTER_SECONDS: Final = 7200.0

# How long a caller waits before giving up and running unlocked.
WAIT_TIMEOUT_SECONDS: Final = 3600.0

# `os.O_BINARY` exists only on Windows, where the C runtime would otherwise
# translate a newline on the way to disk. Written as a statement rather than a
# conditional expression: mypy narrows an `if` on `sys.platform` and does not
# narrow the same test inside an expression, so the one-line version fails the
# type gate on Linux while passing it on Windows.
if sys.platform == "win32":
    _BINARY = os.O_BINARY
else:
    _BINARY = 0

# What an unset or switched-off `CI` looks like. GitHub Actions sets `CI=true`.
_CI_OFF: Final = frozenset({"", "0", "false", "no", "off"})


if sys.platform == "win32":
    # `os.kill(pid, 0)` is NOT a liveness probe on Windows. CPython routes any
    # signal other than the two console events to `TerminateProcess`, so the
    # textbook probe can kill the very gate this tool exists to protect.
    # Measured 2026-08-30 on CPython 3.14.2 the child survived it - but this
    # repository supports 3.12 through 3.14 and a scheduling aid may not rest on
    # which of them somebody installed. `OpenProcess` cannot terminate anything
    # on any version.
    _SYNCHRONIZE: Final = 0x0010_0000
    _WAIT_TIMEOUT: Final = 0x0000_0102
    _ERROR_ACCESS_DENIED: Final = 5
    _KERNEL32: Final = ctypes.WinDLL("kernel32", use_last_error=True)
    # A handle is wider than the default `c_int` return type on 64-bit Windows.
    _KERNEL32.OpenProcess.restype = ctypes.c_void_p

    def pid_alive(pid: int) -> bool:
        """Is a process holding this pid right now?"""
        if pid <= 0:
            return False
        handle = _KERNEL32.OpenProcess(_SYNCHRONIZE, False, pid)
        if handle is None:
            # A process another account owns exists but will not open. Reading
            # that as "gone" would reclaim a lock somebody is using.
            return bool(ctypes.get_last_error() == _ERROR_ACCESS_DENIED)
        try:
            # The handle opens for an exited process too, while anything still
            # holds a handle to it - measured 2026-08-30, a just-killed child
            # opened and waited 0. Only the wait answers the question.
            return bool(_KERNEL32.WaitForSingleObject(handle, 0) == _WAIT_TIMEOUT)
        finally:
            _KERNEL32.CloseHandle(ctypes.c_void_p(handle))

else:

    def pid_alive(pid: int) -> bool:
        """Is a process holding this pid right now?"""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            # It exists and belongs to another account.
            return True
        except OSError:
            return False
        return True


@dataclass(frozen=True)
class Holder:
    """The record in the lock file: who is running what, from where, since when."""

    pid: int
    worktree: str
    command: str
    created_at: float

    def to_json(self) -> str:
        return json.dumps(
            {
                "pid": self.pid,
                "worktree": self.worktree,
                "command": self.command,
                "created_at": self.created_at,
            },
            sort_keys=True,
        )

    def describe(self, now: float) -> str:
        """The sentence a blocked caller needs: who, where, what and how long."""
        return (
            f"pid {self.pid} in {self.worktree} running `{self.command}`, "
            f"held for {max(0.0, now - self.created_at):.0f} s"
        )


def default_lock_path() -> Path:
    """The one lock every worktree on this machine contends on."""
    return Path(tempfile.gettempdir()) / LOCK_FILENAME


def running_in_ci(env: Mapping[str, str]) -> bool:
    """Is this a CI runner? A runner is one job alone and never takes the lock."""
    return env.get("CI", "").strip().lower() not in _CI_OFF


def holder_for(command: Sequence[str], *, worktree: Path | None = None) -> Holder:
    """Our own record. The worktree is absolute because naming it is the point."""
    root = (Path.cwd() if worktree is None else worktree).resolve()
    return Holder(
        pid=os.getpid(),
        # Forward slashes per CLAUDE.md section 2. Absolute is the exception the
        # section allows: a reader has to be able to tell two checkouts apart.
        worktree=root.as_posix(),
        command=" ".join(command),
        created_at=time.time(),
    )


def parse_holder(raw: str) -> Holder | None:
    """The record those bytes hold, or None when they are not a record."""
    try:
        record = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    try:
        return Holder(
            pid=int(record["pid"]),
            worktree=str(record["worktree"]),
            command=str(record["command"]),
            created_at=float(record["created_at"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def read_holder(path: Path) -> Holder | None:
    """Who holds the lock, or None when nothing readable does."""
    raw = _read_bytes(path)
    if raw is None:
        return None
    return parse_holder(raw.decode("utf-8", errors="replace"))


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        # Windows refuses a read while the winner still has the file open. The
        # caller loops and the create decides, so there is nothing to report.
        return None


def _try_create(path: Path, holder: Holder) -> bool:
    """Win the lock, or answer False because somebody else already has it."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | _BINARY
    try:
        descriptor = os.open(path, flags, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(holder.to_json().encode("utf-8"))
    return True


def reclaim_if_free(path: Path, *, stale_after: float, now: float | None = None) -> str | None:
    """Remove a lock nobody is holding. Answers why it went, or None if it stands.

    Two residual races are worth stating rather than pretending away.

    A pid answers "is some process this number", never "is it the one that took
    the lock". An operating system that has recycled the number reports a dead
    holder as alive, and the standard library exposes no portable way to read
    another process's start time - which is why `created_at` rides in the record
    and `stale_after` reclaims regardless. Inside that window a recycled pid does
    keep a dead holder's lock, and this tool cannot see the difference.

    Two waiters can judge one record stale in the same instant. Both re-read the
    bytes they judged, one unlinks and the other is told the file is gone, and
    the create that follows is still decided by `O_EXCL` - so the pair is safe.
    What remains is a waiter the scheduler suspends between its re-read and its
    unlink for long enough that another waiter reclaims, creates and starts: the
    late unlink would then take a fresh lock. That window is microseconds wide
    and it is the price of a lock file with no lease.
    """
    raw = _read_bytes(path)
    if raw is None:
        return None
    holder = parse_holder(raw.decode("utf-8", errors="replace"))
    moment = time.time() if now is None else now
    if holder is None:
        reason = f"its record is not readable ({len(raw)} bytes)"
    elif not pid_alive(holder.pid):
        reason = f"pid {holder.pid} is gone ({holder.describe(moment)})"
    elif moment - holder.created_at > stale_after:
        reason = (
            f"it is past the {stale_after:.0f} s reclaim line ({holder.describe(moment)})"
        )
    else:
        return None
    # Re-read immediately before unlinking and only remove the exact bytes that
    # were judged. Without this, a holder that released between the read above
    # and this line would cost its successor a lock it legitimately holds.
    if _read_bytes(path) != raw:
        return None
    try:
        path.unlink()
    except OSError:
        return None
    return reason


def acquire(
    path: Path,
    holder: Holder,
    *,
    poll: float = POLL_SECONDS,
    stale_after: float = STALE_AFTER_SECONDS,
    timeout: float = WAIT_TIMEOUT_SECONDS,
    report_every: float = REPORT_SECONDS,
) -> bool:
    """Take the lock, or answer False after `timeout` seconds of waiting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    # Negative so the first pass through the wait reports the holder at once.
    reported = -report_every
    while True:
        if _try_create(path, holder):
            return True
        reason = reclaim_if_free(path, stale_after=stale_after)
        if reason is not None:
            LOG.warning("reclaimed the gate lock: %s", reason)
            continue
        waited = time.monotonic() - started
        if waited >= timeout:
            return False
        if waited - reported >= report_every:
            reported = waited
            current = read_holder(path)
            held_by = "somebody" if current is None else current.describe(time.time())
            LOG.info("waiting for the gate lock, held by %s (%.0f s so far)", held_by, waited)
        time.sleep(poll)


def release(path: Path, holder: Holder) -> bool:
    """Drop the lock, but only while the record on disk is still ours."""
    if read_holder(path) != holder:
        LOG.warning("the gate lock is no longer ours, so it stays where it is")
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def run_command(command: Sequence[str]) -> int:
    """Run the gate and hand back its exit code.

    `shutil.which` first, because Windows will not start `npm` from a bare name:
    the loader appends `.exe` and never `.CMD`, so the call raises
    `FileNotFoundError` while the same program runs from its full path (measured
    2026-08-30). Resolving here also keeps the run off a shell, so nothing in the
    command line is ever interpreted as a shell operator.
    """
    program = shutil.which(command[0])
    if program is None:
        LOG.error("no %s on PATH, so there is nothing to run", command[0])
        return 127
    return subprocess.run([program, *command[1:]], check=False).returncode


def split_argv(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    """Ours before the first `--`, the gate and all of its own flags after it.

    Done by hand rather than through argparse, because `pytest -q` and
    `--durations=25` would otherwise have to be told apart from our flags.
    """
    ours = list(argv)
    if "--" not in ours:
        return ours, []
    cut = ours.index("--")
    return ours[:cut], ours[cut + 1 :]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gate_lock",
        description=(
            "Hold a machine-wide lock while one heavy gate runs, so two worktrees "
            "never fight over the same cores. Name the gate after a `--`."
        ),
        epilog="example: python backend/utilities/gate_lock.py -- python -m pytest",
    )
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=None,
        help=f"Where the lock lives. Default: {LOCK_FILENAME} in the user temp directory.",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=POLL_SECONDS,
        help=f"Seconds between attempts while waiting. Default: {POLL_SECONDS}.",
    )
    parser.add_argument(
        "--stale-after",
        type=float,
        default=STALE_AFTER_SECONDS,
        help=(
            "Reclaim a lock older than this many seconds even when its pid still "
            f"reads alive. Default: {STALE_AFTER_SECONDS:.0f}."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=WAIT_TIMEOUT_SECONDS,
        help=(
            "Seconds to wait before running the gate unlocked rather than failing "
            f"it. Default: {WAIT_TIMEOUT_SECONDS:.0f}."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    ours, command = split_argv(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(ours)
    if not command:
        parser.error("name the gate after a `--`, for example: -- python -m pytest")
    # CLAUDE.md section 1b takes the level from `config/`. This tool reads no
    # config on purpose - it has to run with any Python and no install - so the
    # level is fixed at INFO, which is what the one message it prints needs.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    if running_in_ci(os.environ):
        LOG.info("CI is set, so the gate runs unlocked")
        return run_command(command)

    lock = default_lock_path() if args.lock_file is None else Path(args.lock_file)
    holder = holder_for(command)
    if acquire(
        lock,
        holder,
        poll=float(args.poll),
        stale_after=float(args.stale_after),
        timeout=float(args.timeout),
    ):
        try:
            return run_command(command)
        finally:
            release(lock, holder)

    LOG.warning(
        "gave up waiting for the gate lock after %.0f s and ran unlocked; "
        "refusing to run would turn contention into a failed gate",
        float(args.timeout),
    )
    return run_command(command)


if __name__ == "__main__":
    raise SystemExit(main())
