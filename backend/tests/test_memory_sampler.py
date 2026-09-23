"""Does the memory sampler detach, take both marks in one pass, and read them back?"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Final

import pytest

from utilities import memory_sampler

#: The program, run the way a workflow step runs it.
MODULE: Final = Path(memory_sampler.__file__).resolve()

#: How long the detachment arm waits for a process to go away before it calls
#: that a failure. Generous, because it is bounding a scheduler and not a
#: computation.
PATIENCE_SECONDS: Final = 30.0

#: `os.getsid` is the one call that proves detachment rather than describing it,
#: and neither it nor `setsid` exists off POSIX.
posix_only: Final = pytest.mark.skipif(sys.platform == "win32", reason="setsid is POSIX")


def _a_process(root: Path, pid: int, comm: str, status: str, cmdline: str = "") -> None:
    """One `/proc/<pid>` entry, holding exactly what this test wants read."""
    entry = root / str(pid)
    entry.mkdir(parents=True)
    (entry / "comm").write_text(comm + "\n", encoding="utf-8")
    if status:
        (entry / "status").write_text(status, encoding="utf-8")
    if cmdline:
        (entry / "cmdline").write_bytes(cmdline.encode("utf-8"))


def _a_proc_tree(tmp_path: Path) -> Path:
    """A `/proc` holding a server, two python processes, and two that do not count."""
    root = tmp_path / "proc"
    root.mkdir()
    _a_process(root, 100, "llama-server", "VmRSS:\t5000000 kB\nVmHWM:\t6000000 kB\n")
    _a_process(
        root,
        200,
        "python3",
        "Name:\tpython3\nVmRSS:\t1000 kB\nVmHWM:\t1200 kB\n",
        # NUL-separated, exactly as the kernel writes it.
        "python3\x00-u\x00-m\x00idhazh\x00work\x00--shard\x000\x00",
    )
    # No high-water row at all, which is what a short-lived process can look
    # like, and no command line either.
    _a_process(root, 300, "python3.12", "VmRSS:\t500 kB\n")
    _a_process(root, 400, "bash", "VmRSS:\t900 kB\nVmHWM:\t900 kB\n")
    # Gone between the walk and the read. It is the normal case on a busy host.
    _a_process(root, 500, "python3", "")
    (root / "meminfo").write_text(
        "MemTotal:       16384000 kB\n"
        "MemFree:          100000 kB\n"
        "MemAvailable:   12000000 kB\n"
        "Committed_AS:    9000000 kB\n",
        encoding="utf-8",
    )
    return root


def test_the_count_and_the_roll_call_come_off_one_walk(tmp_path: Path) -> None:
    """A count of three cannot say which three, and here two of them are not ours.

    Over the four captures of run `2026-08-29-3` the peak lands at three python
    processes on every shard, and two of those three are already running at the
    first sample - taken before the job's own python starts. About 4 percent of
    the recorded python figure belongs to something the job never launched, and
    the roll-call is what turns the next run into the answer.

    So the sum and the roll-call have to come off the SAME pass. Two passes over
    `/proc` seconds apart would sum a set the roll-call never named, and nothing
    on either file would say so.
    """
    root = _a_proc_tree(tmp_path)

    record, rows = memory_sampler.sample_once(100, proc_root=root, cgroup_paths=(), now="ts")

    assert record["python_procs"] == len(rows) == 2, rows
    assert [row["pid"] for row in rows] == [200, 300]
    assert record["python_vmrss_kb"] == 1500
    # 300 has no high-water mark, so it contributes what it holds now. That is
    # the lower bound the shell summed, and both marks are taken because of it.
    assert record["python_vmhwm_kb"] == 1700
    assert record["llama_vmrss_kb"] == 5_000_000
    assert record["llama_vmhwm_kb"] == 6_000_000
    assert record["mem_total_kb"] == 16_384_000
    assert record["mem_available_kb"] == 12_000_000
    assert record["committed_as_kb"] == 9_000_000
    assert all(row["ts"] == record["ts"] for row in rows)


def test_the_roll_call_carries_three_argv_fields_and_never_the_whole_line(
    tmp_path: Path,
) -> None:
    """`comm` is `python3` for every one of them, which names nothing.

    The executable and argv 1 to 3 separate a hosted-tool-cache `python -m
    idhazh` from a distribution `/usr/bin/python3 -u /usr/sbin/...` and stop
    there, so a secret further along a command line is never copied into an
    artifact a run uploads (CLAUDE.md section 1b).
    """
    root = _a_proc_tree(tmp_path)

    _, rows = memory_sampler.sample_once(100, proc_root=root, cgroup_paths=(), now="ts")

    named = next(row for row in rows if row["pid"] == 200)
    assert named["args"] == "-u -m idhazh", "argv 4 onwards reached the artifact"
    assert named["comm"] == "python3"
    # No symlink in the fixture tree, and a reading that was not taken is null.
    assert named["exe"] is None


def test_a_reading_that_was_not_taken_is_null_rather_than_zero(tmp_path: Path) -> None:
    """An empty cell reads as zero, and zero available memory is a different claim.

    The shell wrote the word `absent` into a tab-separated cell to say this.
    JSON carries it, so the reader never has to know a sentinel.
    """
    root = tmp_path / "proc"
    root.mkdir()

    record, rows = memory_sampler.sample_once(404, proc_root=root, cgroup_paths=(), now="ts")

    assert rows == []
    assert record["llama_vmrss_kb"] is None
    assert record["llama_vmhwm_kb"] is None
    assert record["mem_available_kb"] is None
    assert record["cgroup_current_bytes"] is None
    assert record["python_procs"] == 0


def _wrote(tmp_path: Path, name: str, records: list[dict[str, Any]]) -> None:
    (tmp_path / name).write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )


def _ran(tmp_path: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MODULE), *argv],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _waited_for(path: Path, wanted: str) -> str:
    """The first line of a file that holds `wanted`, once the file holds one."""
    deadline = time.monotonic() + PATIENCE_SECONDS
    while time.monotonic() < deadline:
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if wanted in line:
                    return line
        time.sleep(0.1)
    raise AssertionError(f"{path.name} never said {wanted!r}")


def test_the_summary_prints_the_five_figures_off_the_records(tmp_path: Path) -> None:
    """The `awk` program this replaced named its columns and read them by position.

    A column inserted anywhere but the end shifted every field after it, and the
    job log then reported `python_procs` - a count of three - as a peak in
    kilobytes. Nothing failed and the number was out by six orders of magnitude.
    The agreement was held by a third copy of the column order written down in a
    test file, so the writer and the reader agreed with that copy rather than
    with each other.

    One program writes the records and the same program reads them now, keyed
    rather than positional, so there is no order left to disagree about. What is
    still worth asserting is the arithmetic, and that a row with no reading in
    it is skipped rather than counted as a zero peak.
    """
    _wrote(
        tmp_path,
        "rss-samples.jsonl",
        [
            {
                "ts": "a",
                "llama_vmrss_kb": 10,
                "llama_vmhwm_kb": 11,
                "python_vmrss_kb": 3,
                "python_procs": 2,
                "python_vmhwm_kb": 4,
            },
            {
                "ts": "b",
                "llama_vmrss_kb": 20,
                "llama_vmhwm_kb": 25,
                "python_vmrss_kb": 7,
                "python_procs": 2,
                "python_vmhwm_kb": 9,
            },
            {"ts": "c", "llama_vmhwm_kb": None, "python_vmhwm_kb": None},
        ],
    )
    _wrote(
        tmp_path,
        "python-procs.jsonl",
        [
            {"ts": "a", "pid": 200, "comm": "python3", "vmrss_kb": 1, "exe": "/bin/py", "args": "-m idhazh"},
            {"ts": "b", "pid": 200, "comm": "python3", "vmrss_kb": 5, "exe": "/bin/py", "args": "-m idhazh"},
            {"ts": "a", "pid": 300, "comm": "python3", "vmrss_kb": 2, "exe": "/bin/py", "args": "-u"},
        ],
    )

    completed = _ran(tmp_path, "summarize")

    assert completed.returncode == 0, completed.stderr
    assert (
        "peak llama VmHWM 25 kB, peak python VmHWM 9 kB, "
        "most the two held at once 27 kB, n=3 samples" in completed.stderr
    ), completed.stderr
    assert "python 200  python3  /bin/py  -m idhazh peak VmRSS 5 kB in 2 samples" in (
        completed.stderr
    )
    assert "python 300  python3  /bin/py  -u peak VmRSS 2 kB in 1 samples" in completed.stderr
    # CLAUDE.md section 1b: every record goes to stderr through `logging`, and
    # stdout is left for a value a program reads. A sibling row spent a
    # production break on prose reaching `$GITHUB_OUTPUT`.
    assert completed.stdout == "", completed.stdout


def test_the_summary_says_a_file_is_missing_and_does_not_fail_the_step(tmp_path: Path) -> None:
    """It runs under `if: always()` on a shard that may have died early.

    A summary that raised would turn a lost measurement into a red step on a job
    that had already failed for its own reasons, and hide the real one.
    """
    completed = _ran(tmp_path, "summarize")

    assert completed.returncode == 0, completed.stderr
    assert "rss-samples.jsonl not found" in completed.stderr
    assert "python-procs.jsonl not found" in completed.stderr


@posix_only
def test_the_pid_file_names_the_loop_and_not_the_process_that_launched_it(
    tmp_path: Path,
) -> None:
    """The bug this shape removes: a pid file naming something that never sampled.

    The shell backgrounded itself with `&` and wrote `$!`, which is the pid of
    the backgrounded *shell* rather than of the sampling loop. A sampler that
    died at once left that file naming a live shell, the step passed, and the
    run learned nothing about its own memory until somebody opened an empty
    artifact.

    The file is checked against the loop's own account of itself in the log,
    rather than against the pid the launcher was started under. That is what
    makes this POSIX and not a portability wart: a Windows venv runs the
    interpreter through a trampoline, so the two are different numbers there and
    the parent's `Popen.pid` names neither the sampler nor anything else useful.
    On the runner `python3` is the interpreter itself, and this program cannot
    run anywhere without a `/proc` in any case.

    Nothing here waits on a clock. The target is a process that has already been
    reaped, so the loop writes its first line and stops.
    """
    reaped = subprocess.Popen([sys.executable, "-c", ""])
    reaped.wait()

    launcher = subprocess.Popen(
        [sys.executable, str(MODULE), "start-sampler", "--pid", str(reaped.pid)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    launcher.communicate(timeout=PATIENCE_SECONDS)

    said = _waited_for(tmp_path / "memory-sampler.log", "as pid ")
    claimed = int(said.rsplit("as pid ", 1)[1].split()[0])
    recorded = int((tmp_path / "memory-sampler.pid").read_text(encoding="utf-8"))

    assert recorded == claimed, "the pid file names a process that is not the sampling loop"
    assert recorded != reaped.pid, "the pid file names the process being watched"


def test_a_loop_that_is_already_gone_is_refused_rather_than_recorded(tmp_path: Path) -> None:
    """A green step with a pid file naming a dead process is the failure to beat.

    The parent gives the loop a short grace and then says whether it is still
    there. This drives that check with a process that really has exited, so the
    answer turns on the check rather than on how long a Python interpreter takes
    to start on the host running the suite.
    """
    already = subprocess.Popen([sys.executable, "-c", "raise SystemExit(3)"])
    already.wait()
    log = tmp_path / "memory-sampler.log"
    log.write_text("what it said before it went\n", encoding="utf-8")

    with pytest.raises(SystemExit) as refused:
        memory_sampler._refuse_a_sampler_that_died_at_startup(already, log)

    assert "before it took a sample" in str(refused.value)
    assert "what it said before it went" in str(refused.value), "the log tail is the diagnosis"


@posix_only
def test_the_loop_outlives_the_parent_and_stops_when_its_target_does(tmp_path: Path) -> None:
    """The oracle. The parent exits and the loop keeps sampling, in its own session.

    `os.getsid` is the one call that proves detachment rather than describing
    it: `start_new_session` calls `setsid`, so the loop has no controlling
    terminal and SIGHUP is never delivered to it at all.

    The target is reaped here on purpose. A process that has exited and not been
    waited on is a zombie, and a zombie keeps its `/proc` entry - so the loop
    would go on sampling a process that is gone, exactly as `kill -0` would have
    reported it alive.
    """
    target = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        launched = _ran(tmp_path, "start-sampler", "--pid", str(target.pid), "--every", "0.1")
        assert launched.returncode == 0, launched.stderr

        loop = int((tmp_path / "memory-sampler.pid").read_text(encoding="utf-8"))
        assert loop != target.pid
        if sys.platform != "win32":
            os.kill(loop, 0)
            assert os.getsid(loop) != os.getsid(0), (
                "the loop shares the session it was launched from"
            )

        samples = tmp_path / "rss-samples.jsonl"
        deadline = time.monotonic() + PATIENCE_SECONDS
        while time.monotonic() < deadline:
            if samples.exists() and len(samples.read_text(encoding="utf-8").splitlines()) >= 2:
                break
            time.sleep(0.1)
        written = samples.read_text(encoding="utf-8").splitlines()
        assert len(written) >= 2, written
        assert json.loads(written[0])["ts"], written[0]
    finally:
        target.terminate()
        target.wait()

    deadline = time.monotonic() + PATIENCE_SECONDS
    while time.monotonic() < deadline:
        try:
            os.kill(loop, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    with pytest.raises(ProcessLookupError):
        os.kill(loop, 0)