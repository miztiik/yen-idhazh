"""Tests for the machine-wide gate lock.

The claim is non-overlap under real concurrency, so the oracle starts K real
subprocesses. Threads in one interpreter would share the process and would pass
even with the lock removed at the operating-system level, which is why none is
used here.

Every subprocess is given its own `--lock-file` under `tmp_path`. Pointing a
test at the real machine-wide lock would make the suite wait for whichever agent
is holding it, which is the opposite of the point.

`time.monotonic()` is the clock in the interval pairs. It is system-wide on both
platforms this repository runs on, so two processes can be compared against it -
`time.perf_counter()` carries no such promise. The first test proves the
property rather than asserting it, because every later assertion rests on it.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Final

from utilities import gate_lock

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
GATE_LOCK: Final = REPO_ROOT / "backend" / "utilities" / "gate_lock.py"

# Five is enough to be a queue rather than a pair, and a quarter of a second is
# well past the ~15 ms floor a Windows monotonic tick can have.
WORKERS: Final = 5
HOLD_SECONDS: Final = 0.25

# A crowd, for the arm that drives the reclaim path. Every caller in it fails the
# create, judges the planted record stale and goes for the delete at the same
# moment, which is the interleaving that produced the defect. Ten callers on a
# 4 vCPU runner is a real queue; the hold is short because the point is the
# handover, not the holding.
CROWD: Final = 10
CROWD_HOLD_SECONDS: Final = 0.1

# The unlocked arm has to overlap to be a control, so its hold is long enough to
# cover five process starts on a loaded box.
UNLOCKED_HOLD_SECONDS: Final = 1.2

# One worker: mark the moment the gate started, hold the box, mark the moment it
# stopped, then append the pair. The whole span is time the caller held the lock,
# because `gate_lock` runs the command and only then releases.
WORKER_SOURCE: Final = """import sys
import time

target = sys.argv[1]
hold = float(sys.argv[2])
start = time.monotonic()
time.sleep(hold)
end = time.monotonic()
with open(target, "a", encoding="ascii") as handle:
    handle.write(f"{start:.6f} {end:.6f}\\n")
"""

# Report the reading a child takes, so the parent can bracket it.
CLOCK_SOURCE: Final = """import time

print(time.monotonic())
"""

# How many locks the watcher below stands over. Each one is a separate chance to
# catch a lock that exists before its record does, and one catch is the finding.
LOCKS_WATCHED: Final = 120

# Spin on each lock in turn and report the first bytes that ever come back. A
# poll cycle here is a few microseconds, so the reading lands within microseconds
# of the lock appearing - which is where a two-step create is still empty. The
# size rides in front of the record so an empty reading is a line rather than
# nothing at all, and the `ready` file per lock is what keeps the watcher from
# falling behind the parent and reading only finished files.
WATCHER_SOURCE: Final = """import pathlib
import sys

room = pathlib.Path(sys.argv[1])
seen = pathlib.Path(sys.argv[2])
count = int(sys.argv[3])

lines = []
for index in range(count):
    lock = room / f"lock-{index:04d}"
    (room / f"ready-{index:04d}").write_text("go", encoding="ascii")
    while True:
        try:
            raw = lock.read_bytes()
        except OSError:
            continue
        break
    lines.append(f"{len(raw)}|" + raw.decode("utf-8", errors="replace"))
seen.write_text("\\n".join(lines) + "\\n", encoding="ascii")
"""


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="ascii")
    return path


def _developer_environment() -> dict[str, str]:
    """A developer machine, not a runner.

    `CI` goes because a runner never takes the lock and the suite itself runs on
    one. `PYTHONPATH` goes because the tool imports nothing from `idhazh` and
    the acceptance gate is that it runs with nothing set up.
    """
    env = dict(os.environ)
    env.pop("CI", None)
    env.pop("PYTHONPATH", None)
    return env


def _argv(
    lock: Path,
    command: Sequence[str],
    *,
    poll: float = 0.05,
    timeout: float | None = None,
) -> list[str]:
    flags = ["--lock-file", str(lock), "--retry-every", str(poll)]
    if timeout is not None:
        flags += ["--timeout", str(timeout)]
    return [sys.executable, str(GATE_LOCK), *flags, "--", *command]


def _run_together(
    argvs: Sequence[Sequence[str]],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float = 300.0,
) -> list[tuple[int, str]]:
    """Start every command, then collect each one. Returns (exit code, stderr)."""
    runs = [
        subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for argv in argvs
    ]
    try:
        collected: list[tuple[int, str]] = []
        for run in runs:
            _, errors = run.communicate(timeout=timeout)
            collected.append((run.returncode, errors))
        return collected
    finally:
        for run in runs:
            if run.poll() is None:
                run.kill()


def _intervals(record: Path) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for line in record.read_text(encoding="ascii").splitlines():
        if not line.strip():
            continue
        start, end = line.split()
        pairs.append((float(start), float(end)))
    return pairs


def _marks(directory: Path) -> list[tuple[float, float]]:
    """Every worker's own pair, read from its own file.

    One shared file would be enough for the arm above, where a lost line and an
    overlap are the same finding. The arm below has to say WHICH intervals
    overlapped, and two callers appending to one file at the same instant on
    Windows can lose one of them - so each worker gets a file nobody else writes.
    """
    pairs: list[tuple[float, float]] = []
    for mark in sorted(directory.iterdir()):
        pairs.extend(_intervals(mark))
    return pairs


def _a_lock_nobody_is_holding(age: float = 10.0 * gate_lock.STALE_AFTER_SECONDS) -> gate_lock.Holder:
    """A record past the reclaim line, so every caller that meets it must reclaim.

    The pid is this test's own and is alive, so it is the age that decides and
    the arm is the same on both platforms.
    """
    return gate_lock.Holder(
        pid=os.getpid(),
        worktree="/a/worktree/that/is/long/gone",
        command="python -m pytest",
        created_at=time.time() - age,
    )


def _overlapping(intervals: Sequence[tuple[float, float]]) -> list[tuple[int, int]]:
    """Index pairs whose intervals overlap. Empty means the gates were serialised.

    Sorting by start makes the adjacent comparison sufficient: if every next
    start is at or after the previous end, the ends are sorted too and no pair
    anywhere in the list can overlap.
    """
    order = sorted(range(len(intervals)), key=lambda index: intervals[index][0])
    return [
        (before, after)
        for before, after in pairwise(order)
        if intervals[after][0] < intervals[before][1]
    ]


def _exited_pid() -> int:
    """A pid that has certainly exited, still reserved by a handle we hold.

    The child reads stdin and stops when it is closed, so nothing has to be
    killed and nothing has to be waited out. `Popen` keeps its handle, so on
    Windows the number cannot be handed to another process while we ask about it.
    """
    child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
    child.communicate(timeout=60)
    assert child.returncode == 0
    return child.pid
def test_ci_runs_the_gate_unlocked_and_the_same_workers_then_overlap(tmp_path: Path) -> None:
    """The control arm, and decision 4 in one run.

    Identical commands and one identical lock path, with `CI` set the way a
    GitHub runner sets it. If the workers still overlap then the carve-out is
    real, and the arm above is measuring the lock rather than a machine too slow
    to run two things at once.
    """
    worker = _write(tmp_path / "worker.py", WORKER_SOURCE)
    record = tmp_path / "intervals.txt"
    lock = tmp_path / "gate.lock"
    command = [sys.executable, str(worker), str(record), str(UNLOCKED_HOLD_SECONDS)]
    env = _developer_environment()
    env["CI"] = "true"

    results = _run_together(
        [_argv(lock, command) for _ in range(WORKERS)], cwd=tmp_path, env=env
    )

    assert [code for code, _ in results] == [0] * WORKERS, results
    intervals = _intervals(record)
    assert len(intervals) == WORKERS
    assert _overlapping(intervals) != [], f"nothing overlapped without the lock: {intervals}"
    assert not lock.exists(), "a runner wrote a lock file"
def test_a_waiter_names_the_holder_then_runs_the_gate_rather_than_failing_it(
    tmp_path: Path,
) -> None:
    """Decision 3, and the rule that a scheduling aid may not manufacture a red gate.

    The standing lock names this test's own pid, which is alive, so it is never
    reclaimed and the caller really does wait out its `--timeout`.
    """
    lock = tmp_path / "gate.lock"
    standing = gate_lock.Holder(
        pid=os.getpid(),
        worktree="/some/other/worktree",
        command="npm run test:browser",
        created_at=time.time() - 42.0,
    )
    lock.write_text(standing.to_json(), encoding="ascii")
    worker = _write(tmp_path / "worker.py", WORKER_SOURCE)
    record = tmp_path / "intervals.txt"

    done = subprocess.run(
        _argv(lock, [sys.executable, str(worker), str(record), "0"], timeout=0.2),
        cwd=tmp_path,
        env=_developer_environment(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert f"pid {os.getpid()}" in done.stderr
    assert "/some/other/worktree" in done.stderr
    assert "npm run test:browser" in done.stderr
    assert re.search(r"held for \d+ s", done.stderr) is not None, done.stderr
    assert "gave up waiting" in done.stderr
    assert len(_intervals(record)) == 1, "the gate did not run"
    assert lock.read_text(encoding="ascii") == standing.to_json(), "it took a lock it never won"


def test_the_gates_exit_code_comes_back_and_the_lock_goes(tmp_path: Path) -> None:
    lock = tmp_path / "gate.lock"

    done = subprocess.run(
        _argv(lock, [sys.executable, "-c", "raise SystemExit(3)"]),
        cwd=tmp_path,
        env=_developer_environment(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert done.returncode == 3
    assert not lock.exists()
def test_a_lock_with_nowhere_to_live_runs_the_gate_rather_than_failing_it(
    tmp_path: Path,
) -> None:
    """The standing promise, met at the create rather than only at the timeout.

    A lock path whose parent is a file has nowhere to be created. A scheduling
    aid that raises here fails the gate it exists to protect, so it says what
    happened and hands back nothing.
    """
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("", encoding="ascii")
    holder = gate_lock.holder_for(["python", "-m", "pytest"])

    assert gate_lock.acquire(blocked / "gate.lock", holder, poll=0.01, timeout=0.2) is None
def test_a_gate_has_to_be_named_after_a_double_dash() -> None:
    done = subprocess.run(
        [sys.executable, str(GATE_LOCK)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert done.returncode == 2
    assert "--" in done.stderr
def test_a_lock_whose_holder_is_gone_is_reclaimed(tmp_path: Path) -> None:
    """Decision 2. A lock that outlives its holder would stop every gate on the box."""
    lock = tmp_path / "gate.lock"
    dead = gate_lock.Holder(
        pid=_exited_pid(),
        worktree="/a/worktree/that/crashed",
        command="python -m pytest",
        created_at=time.time(),
    )
    lock.write_text(dead.to_json(), encoding="ascii")

    reason = gate_lock.reclaim_if_free(lock, stale_after=gate_lock.STALE_AFTER_SECONDS)

    assert reason is not None
    assert f"pid {dead.pid} is gone" in reason
    assert "/a/worktree/that/crashed" in reason
    assert not lock.exists()
