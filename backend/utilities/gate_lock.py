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

How it works. One lock file in the user temp directory. The record is written to
a private file first and then linked into place, because `os.link` refuses an
existing destination on both Windows and Linux - so exactly one caller wins, and
the lock never exists without the record that says who won it. That is the
temp-file-plus-rename discipline CLAUDE.md section 1a already asks of every
written unit, applied to the lock itself. The record carries the winner's pid,
its worktree and the second it took the lock, so a caller that loses says who
holds the lock, from where and for how long instead of just hanging. Standard
library only, no new dependency (Rule #8).

Taking a lock away from a dead holder is the one step no single file operation
can decide, because deleting a file is unconditional: a caller that judged a
record stale a moment ago will happily delete whatever sits at that path now,
including a lock somebody else has since won. So the delete runs under a second
exclusive create, `<lock>.reclaim`, and the invariant is that exactly one caller
can transition the lock from "held by a dead holder" to absent. Every other
caller sees either the old record or the new one, never neither.

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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

LOG: Final = logging.getLogger("gate_lock")

# One name for the whole machine. Two worktrees are two checkouts of one
# repository on one set of cores, so they contend on the same file.
LOCK_FILENAME: Final = "yen-idhazh-gate.lock"

# The companion file that decides who may delete the lock. It sits beside the
# lock so both are in one directory and one clean-up.
RIGHT_SUFFIX: Final = ".reclaim"

# How long a seat at that companion file can stand before anybody may take it.
# The seat is held across two reads and one unlink, so this is four orders of
# magnitude of headroom, and it is not a knob: nothing about a gate changes how
# long a read and an unlink take. It has to be far shorter than the lock's own
# reclaim line, because a caller CAN leak a seat while staying alive - on
# Windows an unlink fails outright while any other process has the file open,
# and the callers waiting on this lock read it in a loop. Measured 2026-08-30:
# with the lock's 7,200 s line the first leaked seat stopped twenty callers for
# six minutes and would have stopped them for two hours.
SEAT_SECONDS: Final = 30.0

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
        # Windows refuses a read on a name whose last handle is closing, which
        # is what a lock being released looks like from here. The caller loops
        # and the create decides, so there is nothing to report.
        return None


def right_path(path: Path) -> Path:
    """The companion file that decides who may delete `path`."""
    return path.with_name(path.name + RIGHT_SUFFIX)


def _try_create(path: Path, holder: Holder) -> Holder | None:
    """Take `path`, or answer None because somebody else already has it.

    Answers the record that went in. Its `created_at` is the moment the lock was
    won rather than the moment this process started, so a caller that queued for
    five minutes is not then reported to the next waiter as having held the lock
    for five minutes.

    The record is written to a private file and only then linked into place.
    Creating the lock and writing the record as two steps leaves it readable as
    zero bytes for the microseconds in between, and a caller that reads those
    bytes judges the winner's own record unreadable wreckage and deletes a lock
    that was being taken. `os.link` publishes the name and the bytes together and
    refuses an existing destination, which is what picks the one winner -
    measured 2026-08-30 on Windows 11 (errno 17, winerror 183) and the
    documented POSIX behaviour.

    A caller killed between the write and the link leaves the private file
    behind. It is a few hundred bytes in the temp directory and nothing reads it.
    """
    # A stat before a scratch file. The link below is what decides - this only
    # keeps a caller from building a record for a lock somebody plainly holds.
    # Without it every pass of the wait costs a create and a delete, and measured
    # 2026-08-30 with 20 callers spinning on one lock that turned the temp
    # directory itself into the bottleneck.
    if path.exists():
        return None
    won = replace(holder, created_at=time.time())
    descriptor, name = tempfile.mkstemp(dir=str(path.parent), prefix=f"{path.name}.", suffix=".tmp")
    scratch = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(won.to_json().encode("utf-8"))
        # `mkstemp` is private to its creator. The lock is read by every gate on
        # the machine, so it keeps the permissions a lock file has always had.
        scratch.chmod(0o644)
        try:
            os.link(scratch, path)
        except FileExistsError:
            return None
        except PermissionError:
            # Windows only, and it means contention rather than a broken
            # directory: a name whose last handle is closing is "delete
            # pending", and every create on it is refused until the entry really
            # goes. Measured 2026-08-30, 36 of 50 rounds at 20 callers on one
            # lock: the old code let this out of `os.open` as a traceback and a
            # non-zero exit, which is the scheduling aid failing the gate it
            # exists to protect. A lost create is a lost create.
            return None
    finally:
        try:
            scratch.unlink()
        except OSError:
            pass
    return won


def _why_unheld(raw: bytes, *, stale_after: float, now: float | None = None) -> str | None:
    """Why nobody is holding the record in `raw`, or None because somebody is."""
    holder = parse_holder(raw.decode("utf-8", errors="replace"))
    moment = time.time() if now is None else now
    if holder is None:
        return f"its record is not readable ({len(raw)} bytes)"
    if not pid_alive(holder.pid):
        return f"pid {holder.pid} is gone ({holder.describe(moment)})"
    if moment - holder.created_at > stale_after:
        return f"it is past the {stale_after:.0f} s reclaim line ({holder.describe(moment)})"
    return None


def _delete_exactly(path: Path, raw: bytes) -> bool:
    """Remove `path`, but only while it still holds exactly these bytes."""
    if _read_bytes(path) != raw:
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def take_the_right(path: Path) -> Holder | None:
    """Win the sole right to delete `path`, or answer None and leave it to whoever has it.

    Deleting a file is unconditional, so two callers that judged one record stale
    can both delete - the second removing a lock the first has already won, after
    which both run. Re-reading the bytes immediately before the unlink narrows
    that to microseconds; it does not close it, because nothing makes the read
    and the unlink one step. This exclusive create does: exactly one caller at a
    time may take the lock away from a dead holder, so every other caller sees
    either the old record or the new one and never neither.

    A seat can outlive its use even though the caller that took it is alive,
    because the give-back is an unlink and on Windows an unlink fails while any
    other process has the file open. So the seat answers to `SEAT_SECONDS` as
    well as to the liveness probe, and that one delete is serialised by nothing -
    there is nothing left to serialise it with.
    """
    right = right_path(path)
    standing = _read_bytes(right)
    if standing is not None:
        why = _why_unheld(standing, stale_after=SEAT_SECONDS)
        if why is None:
            return None
        LOG.warning("took over an abandoned seat at the gate lock's reclaim: %s", why)
        _delete_exactly(right, standing)
    try:
        return _try_create(right, holder_for(["gate_lock", "reclaim"]))
    except OSError as error:
        LOG.warning("no seat at the gate lock's reclaim could be taken (%s)", error)
        return None


def _give_back_the_right(path: Path, mine: Holder) -> None:
    """Hand the seat on.

    A record that cannot be read counts as ours. We took the seat, and treating
    an unreadable one as somebody else's is how a seat gets held for ever by a
    caller that is still running - which stops every reclaim on the machine.
    """
    right = right_path(path)
    standing = _read_bytes(right)
    if standing is not None and standing != mine.to_json().encode("utf-8"):
        return
    try:
        right.unlink()
    except OSError:
        # Windows refuses this while another caller has the seat open to read.
        # `SEAT_SECONDS` is what stops that from being permanent.
        LOG.warning("the seat at the gate lock's reclaim would not go back yet")


def reclaim_if_free(path: Path, *, stale_after: float, now: float | None = None) -> str | None:
    """Remove a lock nobody is holding. Answers why it went, or None if it stands.

    The delete runs under `right_path(path)`, so exactly one caller can take the
    lock from "held by a dead holder" to absent. Without that, two callers that
    judged the same record stale both delete, the second one removing a lock the
    first has already won, and both then run their gate - which is the defect
    this repairs. It reached CI once, as two of five worker intervals overlapping
    for the whole hold.

    One residual race is worth stating rather than pretending away. A pid answers
    "is some process this number", never "is it the one that took the lock". An
    operating system that has recycled the number reports a dead holder as alive,
    and the standard library exposes no portable way to read another process's
    start time - which is why `created_at` rides in the record and `stale_after`
    reclaims regardless. Inside that window a recycled pid does keep a dead
    holder's lock, and this tool cannot see the difference.
    """
    raw = _read_bytes(path)
    if raw is None:
        return None
    reason = _why_unheld(raw, stale_after=stale_after, now=now)
    if reason is None:
        return None
    mine = take_the_right(path)
    if mine is None:
        return None
    try:
        return reason if _delete_exactly(path, raw) else None
    finally:
        _give_back_the_right(path, mine)


def acquire(
    path: Path,
    holder: Holder,
    *,
    poll: float = POLL_SECONDS,
    stale_after: float = STALE_AFTER_SECONDS,
    timeout: float = WAIT_TIMEOUT_SECONDS,
    report_every: float = REPORT_SECONDS,
) -> Holder | None:
    """Take the lock and answer the record that went in, or None after `timeout`.

    Hand the record that comes back to `release`. It is not the `holder` that
    went in: its `created_at` is the second the lock was won.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        LOG.warning("the gate lock has nowhere to live (%s), so the gate runs unlocked", error)
        return None
    started = time.monotonic()
    # Negative so the first pass through the wait reports the holder at once.
    reported = -report_every
    while True:
        try:
            won = _try_create(path, holder)
        except OSError as error:
            # The temp directory will not hold a lock at all. Saying so and
            # running unlocked is the promise; refusing would fail the gate.
            LOG.warning("no gate lock could be taken (%s), so the gate runs unlocked", error)
            return None
        if won is not None:
            return won
        reason = reclaim_if_free(path, stale_after=stale_after)
        if reason is not None:
            LOG.warning("reclaimed the gate lock: %s", reason)
            continue
        waited = time.monotonic() - started
        if waited >= timeout:
            return None
        if waited - reported >= report_every:
            reported = waited
            current = read_holder(path)
            held_by = "somebody" if current is None else current.describe(time.time())
            LOG.info("waiting for the gate lock, held by %s (%.0f s so far)", held_by, waited)
        time.sleep(poll)


def release(path: Path, holder: Holder) -> bool:
    """Drop the lock, but only while the record on disk is still ours.

    This is a compare and delete and it does not take the reclaim seat, unlike
    `reclaim_if_free`. The only caller that can remove our record while we are
    alive is one that has judged it past the reclaim line, and `created_at` is
    now the second the lock was won - so reaching that needs a gate still
    running 7,200 s in, which is 6.6x the longest one ever measured here. The
    seat would cost six file operations on every single hand-over to cover it,
    and a hand-over that is slow is the thing this tool exists to avoid.
    """
    raw = holder.to_json().encode("utf-8")
    if _read_bytes(path) != raw:
        LOG.warning("the gate lock is no longer ours, so it stays where it is")
        return False
    return _delete_exactly(path, raw)


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
        "--retry-every",
        type=float,
        default=POLL_SECONDS,
        # Not `--poll`. `test_summarize.py::test_exactly_one_function_spells_a_
        # llama_server_flag` holds a closed-world set of the files under
        # `backend/` that may spell a llama-server flag, and `--poll` is one of
        # them. A flag that reads like the inference server's is a flag somebody
        # will one day pass to the wrong program.
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
    won = acquire(
        lock,
        holder,
        poll=float(args.retry_every),
        stale_after=float(args.stale_after),
        timeout=float(args.timeout),
    )
    if won is not None:
        try:
            return run_command(command)
        finally:
            release(lock, won)

    LOG.warning(
        "gave up waiting for the gate lock after %.0f s and ran unlocked; "
        "refusing to run would turn contention into a failed gate",
        float(args.timeout),
    )
    return run_command(command)


if __name__ == "__main__":
    raise SystemExit(main())
