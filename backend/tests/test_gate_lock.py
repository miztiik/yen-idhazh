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
import tempfile
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


def test_monotonic_is_one_clock_across_processes(tmp_path: Path) -> None:
    """The oracle compares readings taken in different processes, so prove it can.

    A reading a child took has to fall between two the parent took either side of
    it. If the clocks had separate origins this would fail, and every non-overlap
    assertion below would be meaningless rather than wrong.
    """
    reader = _write(tmp_path / "clock.py", CLOCK_SOURCE)

    before = time.monotonic()
    done = subprocess.run(
        [sys.executable, str(reader)], capture_output=True, text=True, timeout=60, check=True
    )
    after = time.monotonic()

    child = float(done.stdout.strip())
    assert before <= child <= after, f"parent {before}..{after}, child {child}"


def test_the_lock_lets_one_gate_run_at_a_time(tmp_path: Path) -> None:
    """The row's oracle: K real subprocesses, and no two of them overlap.

    Also the acceptance gate about a fresh clone - the working directory is
    outside the repository and the environment carries no `PYTHONPATH`, so the
    tool is running with nothing set up for it.
    """
    worker = _write(tmp_path / "worker.py", WORKER_SOURCE)
    record = tmp_path / "intervals.txt"
    lock = tmp_path / "gate.lock"
    command = [sys.executable, str(worker), str(record), str(HOLD_SECONDS)]

    results = _run_together(
        [_argv(lock, command) for _ in range(WORKERS)],
        cwd=tmp_path,
        env=_developer_environment(),
    )

    assert [code for code, _ in results] == [0] * WORKERS, results
    intervals = _intervals(record)
    assert len(intervals) == WORKERS, f"only {len(intervals)} of {WORKERS} workers ran"
    assert _overlapping(intervals) == [], f"gates ran at the same time: {intervals}"
    assert not lock.exists(), "the last worker left the lock behind"


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


def test_ci_walks_past_a_lock_somebody_else_is_holding(tmp_path: Path) -> None:
    """The same carve-out with no timing in it: a standing lock is simply ignored."""
    lock = tmp_path / "gate.lock"
    standing = gate_lock.Holder(
        pid=os.getpid(),
        worktree="/some/other/worktree",
        command="npm run test:browser",
        created_at=time.time(),
    )
    lock.write_text(standing.to_json(), encoding="ascii")
    worker = _write(tmp_path / "worker.py", WORKER_SOURCE)
    record = tmp_path / "intervals.txt"
    env = _developer_environment()
    env["CI"] = "true"

    done = subprocess.run(
        _argv(lock, [sys.executable, str(worker), str(record), "0"], timeout=1.0),
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert len(_intervals(record)) == 1
    assert lock.read_text(encoding="ascii") == standing.to_json()


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


def test_pid_alive_answers_for_a_live_process_and_for_one_that_has_exited() -> None:
    """Both halves matter.

    A probe that always says "alive" never reclaims and one lock stops the box.
    A probe that always says "gone" reclaims a lock a running gate is holding.
    On Windows the exited case is the sharp one: `OpenProcess` still opens a
    handle for a process that has exited while anything holds a handle to it, so
    only the wait separates the two.
    """
    child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
    try:
        assert gate_lock.pid_alive(child.pid) is True
    finally:
        child.communicate(timeout=60)

    assert gate_lock.pid_alive(child.pid) is False
    assert gate_lock.pid_alive(0) is False
    assert gate_lock.pid_alive(-1) is False
    assert gate_lock.pid_alive(os.getpid()) is True


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


def test_a_live_holder_keeps_its_lock(tmp_path: Path) -> None:
    lock = tmp_path / "gate.lock"
    mine = gate_lock.holder_for(["python", "-m", "pytest"])
    lock.write_text(mine.to_json(), encoding="ascii")

    assert gate_lock.reclaim_if_free(lock, stale_after=gate_lock.STALE_AFTER_SECONDS) is None
    assert lock.exists()
    assert gate_lock.read_holder(lock) == mine


def test_a_lock_past_the_reclaim_line_goes_even_though_its_pid_is_alive(tmp_path: Path) -> None:
    """The backstop for a recycled pid, which reads as alive and is not the holder."""
    lock = tmp_path / "gate.lock"
    ancient = gate_lock.Holder(
        pid=os.getpid(),
        worktree="/a/worktree",
        command="npm run build",
        created_at=time.time() - 10_000.0,
    )
    lock.write_text(ancient.to_json(), encoding="ascii")
    assert gate_lock.pid_alive(ancient.pid) is True

    reason = gate_lock.reclaim_if_free(lock, stale_after=gate_lock.STALE_AFTER_SECONDS)

    assert reason is not None
    assert "reclaim line" in reason
    assert not lock.exists()


def test_a_lock_whose_record_will_not_parse_is_reclaimed(tmp_path: Path) -> None:
    """Otherwise a truncated write would wedge every gate until somebody noticed."""
    lock = tmp_path / "gate.lock"
    lock.write_text('{"pid": 12', encoding="ascii")

    reason = gate_lock.reclaim_if_free(lock, stale_after=gate_lock.STALE_AFTER_SECONDS)

    assert reason is not None
    assert "not readable" in reason
    assert not lock.exists()


def test_a_record_that_is_not_ours_is_left_where_it_is(tmp_path: Path) -> None:
    """The same guard the reclaim uses, from the release side, with no race in it."""
    lock = tmp_path / "gate.lock"
    theirs = gate_lock.Holder(
        pid=os.getpid(), worktree="/theirs", command="npm run build", created_at=time.time()
    )
    ours = gate_lock.Holder(
        pid=os.getpid(), worktree="/ours", command="python -m pytest", created_at=time.time()
    )
    lock.write_text(theirs.to_json(), encoding="ascii")

    assert gate_lock.release(lock, ours) is False
    assert lock.exists()
    assert gate_lock.release(lock, theirs) is True
    assert not lock.exists()
    assert gate_lock.release(lock, theirs) is False


def test_the_record_survives_a_round_trip_and_says_who_where_and_how_long() -> None:
    holder = gate_lock.holder_for(["npm", "run", "test:browser"], worktree=REPO_ROOT)

    assert gate_lock.parse_holder(holder.to_json()) == holder
    assert holder.pid == os.getpid()
    # CLAUDE.md section 2: forward slashes on the way out of the process.
    assert "\\" not in holder.worktree
    assert holder.worktree == REPO_ROOT.resolve().as_posix()

    sentence = holder.describe(holder.created_at + 90.0)
    assert f"pid {os.getpid()}" in sentence
    assert holder.worktree in sentence
    assert "npm run test:browser" in sentence
    assert "held for 90 s" in sentence


def test_a_record_that_is_not_one_reads_as_no_record() -> None:
    assert gate_lock.parse_holder("") is None
    assert gate_lock.parse_holder("[]") is None
    assert gate_lock.parse_holder('{"pid": 1}') is None
    assert gate_lock.parse_holder('{"pid": "x", "worktree": "/a", "command": "c", "created_at": 1}') is None


def test_running_in_ci_reads_the_variable_a_runner_sets() -> None:
    assert gate_lock.running_in_ci({}) is False
    assert gate_lock.running_in_ci({"CI": ""}) is False
    assert gate_lock.running_in_ci({"CI": "false"}) is False
    assert gate_lock.running_in_ci({"CI": "0"}) is False
    # What GitHub Actions actually sets.
    assert gate_lock.running_in_ci({"CI": "true"}) is True
    assert gate_lock.running_in_ci({"CI": "TRUE"}) is True
    assert gate_lock.running_in_ci({"CI": "1"}) is True


def test_split_argv_keeps_the_gates_own_flags() -> None:
    ours, command = gate_lock.split_argv(
        ["--retry-every", "1", "--", "python", "-m", "pytest", "-q", "--durations=25"]
    )

    assert ours == ["--retry-every", "1"]
    assert command == ["python", "-m", "pytest", "-q", "--durations=25"]
    assert gate_lock.split_argv(["--retry-every", "1"]) == (["--retry-every", "1"], [])
    # Only the first `--` is ours, so a gate that needs one of its own keeps it.
    assert gate_lock.split_argv(["--", "npm", "run", "build", "--", "--mode=x"]) == (
        [],
        ["npm", "run", "build", "--", "--mode=x"],
    )


def test_the_default_lock_is_one_file_for_the_whole_machine() -> None:
    """Two worktrees are two checkouts on one set of cores, so they share a file."""
    path = gate_lock.default_lock_path()

    assert path == gate_lock.default_lock_path()
    assert path.parent == Path(tempfile.gettempdir())
    assert path.name == gate_lock.LOCK_FILENAME


def test_a_gate_that_is_not_on_path_is_reported_rather_than_run() -> None:
    assert gate_lock.run_command(["yen-idhazh-no-such-program-exists"]) == 127


def test_it_needs_nothing_installed_and_reads_no_configuration() -> None:
    """The acceptance gate, read off the source.

    A lock that needed the virtual environment could not guard the run that
    builds it, and a knob in `config/idhazh.json` would move a contract model and
    a generated schema, which is Level 5 (CLAUDE.md section 6).
    """
    source = GATE_LOCK.read_bytes().decode("utf-8")
    imports = [
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    ]
    modules = {line.split()[1].split(".")[0] for line in imports}

    assert modules <= set(sys.stdlib_module_names), sorted(modules - set(sys.stdlib_module_names))
    assert not any("idhazh" in line for line in imports)
