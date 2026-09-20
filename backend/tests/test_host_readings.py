"""What does the host sampler report, and what does it do when the machine will not answer?

Every reading here comes from a `/proc` or `/sys` path that does not exist on the
machines this project is written on, so the degraded path is the ordinary one
locally and the filled path is the ordinary one in CI. Both are driven here, from
files the test writes, because a reading only CI can take is a reading nobody
checks - and a test that reads the machine it runs on passes or fails on the
weather.

Sibling question, sibling module: `backend/tests/pipeline/test_work_health_payload.py`
asks whether the cells reach the row a shard leaves on disk. This one asks
whether the readings are right, and whether two rows of one shard can disagree.
"""

from __future__ import annotations

import os
import threading
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import fields
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR, REPO_ROOT, read_text
from pytest import MonkeyPatch

from idhazh.contracts.item_health import ItemHealthRow
from idhazh.telemetry import host

#: A kernel peak the test chooses, so the assertion is against a known answer
#: and never against whatever host ran the suite.
A_KERNEL_PEAK = 15_032_385_536

#: Two real `/proc/stat` reads twenty seconds apart, taken by the probe on a
#: `ubuntu-latest` runner on 2026-08-30. The gap is what makes it an oracle: the
#: tick delta has to reproduce twenty seconds of four processors at 100 Hz, and
#: no hand-written file can be checked that way.
PROC_STAT_AT_START = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-start.txt"
PROC_STAT_AT_END = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-end.txt"

#: What the probe slept for, what the runner reported to `nproc`, and the
#: kernel's tick rate. Guardrail #2 fixes the second at 4.
PROBE_SECONDS = 20
PROBE_PROCESSORS = 4
USER_HZ = 100


def test_a_machine_with_no_proc_records_empty_and_never_raises() -> None:
    """A missing instrument degrades the row rather than the run (section 1a)."""
    watch = host.Watch(interval_s=0)

    cells = watch.close()

    assert set(cells.cells()) == {
        "cpu_busy_pct",
        "cpu_busy_max",
        "cpu_busy_min",
        "load_1m",
        "llama_rss_bytes",
        "llama_rss_peak_bytes",
        "python_rss_bytes",
        "cgroup_peak_bytes",
        "os_mem_available_bytes",
        "os_mem_total_bytes",
        "os_mem_cached_bytes",
        "os_swap_free_bytes",
        "os_swap_total_bytes",
        "os_mem_available_min_bytes",
    }


def test_the_busy_share_is_the_whole_item_and_not_a_mean_of_samples(
    monkeypatch: MonkeyPatch,
) -> None:
    """A mean of ratios taken over uneven intervals is a number nobody can add up.

    The two captures are written by the test, so the arithmetic is checked
    against a known answer rather than against whatever the box was doing.
    """
    captures = iter(
        [
            "cpu  100 0 100 800 0 0 0 0 0 0\n",
            "cpu  300 0 300 1400 0 0 0 0 0 0\n",
        ]
    )

    def one_file(path: Path) -> str | None:
        # Only the aggregate counters are answered. Every other reading stays
        # absent, which is what the developer box does anyway.
        return next(captures, None) if path == host.PROC_STAT else None

    monkeypatch.setattr(host, "_text", one_file)

    cells = host.Watch(interval_s=0).close()

    # 400 busy ticks of 1,000 elapsed.
    assert cells.cpu_busy_pct == pytest.approx(40.0)


def test_a_zero_interval_takes_both_ends_and_never_starts_a_thread(
    monkeypatch: MonkeyPatch,
) -> None:
    """`waiting_heartbeat_seconds = 0` turns the heartbeat off, not the readings.

    The captures are written here because the both-ends half cannot fail without
    them: on a machine with no `/proc/stat` every cell reads absent, so the
    assertion would pass whether or not either end was taken. The second capture
    answers every read after the first, because `close()` runs twice - once from
    the `with`, once by hand - and a starved second close reports absence.
    """
    opening = iter(["cpu  100 0 100 800 0 0 0 0 0 0\n"])
    settled = "cpu  250 0 250 1500 0 0 0 0 0 0\n"

    def one_file(path: Path) -> str | None:
        return next(opening, settled) if path == host.PROC_STAT else None

    monkeypatch.setattr(host, "_text", one_file)
    ticks: list[float] = []

    with host.Watch(interval_s=0, on_tick=ticks.append) as watch:
        pass

    assert ticks == []
    # 300 busy ticks of 1,000 elapsed, with no sample taken between the two ends.
    assert watch.close().cells()["cpu_busy_pct"] == pytest.approx(30.0)


#: The six cells the machine's own account of itself fills. Named once, so a
#: seventh cannot be added to the sampler and left out of an assertion below.
MACHINE_CELLS = (
    "os_mem_available_bytes",
    "os_mem_total_bytes",
    "os_mem_cached_bytes",
    "os_swap_free_bytes",
    "os_swap_total_bytes",
    "os_mem_available_min_bytes",
)

#: One machine's memory, at three instants a test chooses. The job's floor is
#: the lowest of the three and is deliberately read OUTSIDE the item's window.
A_JOB_FLOOR_KB = 4_000_000
A_WINDOW_OPEN_KB = 9_000_000
A_WINDOW_FLOOR_KB = 7_000_000

A_MACHINES_MEMORY_KB = 16_373_964
A_PAGE_CACHE_KB = 6_100_000
A_SWAP_KB = 4_194_300


def meminfo(available_kb: int, *, swap_total_kb: int = A_SWAP_KB) -> str:
    """One `/proc/meminfo`, in the kernel's own layout and its own unit.

    Written here rather than read off the box: this file does not exist on the
    machines this suite runs on, and a test that read the real one would assert
    against whatever the developer had open.
    """
    return (
        f"MemTotal:       {A_MACHINES_MEMORY_KB} kB\n"
        f"MemFree:         1000000 kB\n"
        f"MemAvailable:   {available_kb} kB\n"
        f"Cached:         {A_PAGE_CACHE_KB} kB\n"
        f"SwapCached:            0 kB\n"
        f"SwapTotal:      {swap_total_kb} kB\n"
        f"SwapFree:       {swap_total_kb} kB\n"
    )


def only_meminfo(readings: Iterator[str]) -> Callable[[Path], str | None]:
    """A machine that answers `/proc/meminfo` once per read and nothing else.

    Every other reading stays absent, which is what the developer box does
    anyway, so the assertions below are about the one file under test.
    """

    def one_file(path: Path) -> str | None:
        return next(readings) if path == host.MEMINFO else None

    return one_file


def test_the_memory_floor_is_this_items_window_and_never_the_whole_jobs(
    monkeypatch: MonkeyPatch,
) -> None:
    """The Oracle for `os_mem_available_min_bytes`: the model window, and only it.

    `Watch` opens when the model starts on this item and closes when it stops,
    so a reading taken either side of it belongs to the shard and not to the
    item. The scripted sequence puts the job's lowest reading outside the watch
    at both ends: a floor taken over the queue window instead would be that
    number on nearly every row, because a shard's items overlap.
    """
    monkeypatch.setattr(
        host,
        "_text",
        only_meminfo(
            iter(
                [
                    meminfo(A_JOB_FLOOR_KB),
                    meminfo(A_WINDOW_OPEN_KB),
                    meminfo(A_WINDOW_FLOOR_KB),
                    meminfo(A_JOB_FLOOR_KB),
                ]
            )
        ),
    )

    host.meminfo_bytes()
    cells = host.Watch(interval_s=0).close()
    host.meminfo_bytes()

    filled = {name: cells.cells()[name] for name in MACHINE_CELLS}
    assert all(value is not None for value in filled.values()), filled
    assert cells.os_mem_available_min_bytes == A_WINDOW_FLOOR_KB * 1024
    assert cells.os_mem_available_min_bytes != A_JOB_FLOOR_KB * 1024
    assert cells.os_mem_available_bytes == A_WINDOW_FLOOR_KB * 1024
    assert cells.os_mem_total_bytes == A_MACHINES_MEMORY_KB * 1024
    assert cells.os_mem_cached_bytes == A_PAGE_CACHE_KB * 1024
    assert cells.os_swap_free_bytes == cells.os_swap_total_bytes == A_SWAP_KB * 1024


def test_a_reading_the_sampler_took_mid_item_reaches_the_floor(
    monkeypatch: MonkeyPatch,
) -> None:
    """The tightest instant is usually neither end, so the ticks have to count.

    The watch is held open until its own heartbeat has fired at least once, so
    the assertion is about a sample the thread took rather than about how fast
    the box that ran the suite happened to be.
    """
    level = {"kb": A_WINDOW_OPEN_KB}

    def one_file(path: Path) -> str | None:
        return meminfo(level["kb"]) if path == host.MEMINFO else None

    monkeypatch.setattr(host, "_text", one_file)
    ticked = threading.Event()
    watch = host.Watch(interval_s=0.01, on_tick=lambda _: ticked.set())

    level["kb"] = A_WINDOW_FLOOR_KB
    with watch:
        assert ticked.wait(timeout=10.0), "the sampler never ticked"
        level["kb"] = A_WINDOW_OPEN_KB
    cells = watch.close()

    assert cells.os_mem_available_min_bytes == A_WINDOW_FLOOR_KB * 1024
    assert cells.os_mem_available_bytes == A_WINDOW_OPEN_KB * 1024


def test_an_item_whose_machine_never_answered_records_six_nulls(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Nulls and never zeros: a zero here would read as a machine out of memory.

    This is the ordinary path on every machine this project is written on, so
    the degraded arm is the one a developer sees and the filled one is CI's.
    """
    monkeypatch.setattr(host, "MEMINFO", tmp_path / "absent")

    cells = host.Watch(interval_s=0).close()

    assert [cells.cells()[name] for name in MACHINE_CELLS] == [None] * len(MACHINE_CELLS)
    assert host.meminfo_bytes() == dict.fromkeys(host.MEMINFO_KEYS)


def test_a_box_with_no_swap_records_zero_rather_than_nothing(monkeypatch: MonkeyPatch) -> None:
    """A free figure of zero is ambiguous on its own, and the pair is what settles it.

    `SwapFree` at zero says "this machine has no swap" and "swap is fully
    consumed" equally, and only the second is an emergency. A machine carrying
    no swap reports a real zero, so the pair records zero - which is a different
    fact from the cell nothing filled, and the case above is the other one.
    """
    monkeypatch.setattr(
        host, "_text", only_meminfo(iter([meminfo(A_WINDOW_OPEN_KB, swap_total_kb=0)] * 2))
    )

    cells = host.Watch(interval_s=0).close()

    assert cells.os_swap_total_bytes == 0
    assert cells.os_swap_free_bytes == 0
    assert cells.os_mem_available_bytes == A_WINDOW_OPEN_KB * 1024


def test_a_meminfo_line_this_project_does_not_read_is_ignored() -> None:
    """Five keys out of about fifty, and a key the file lacks is unknown.

    The kernel adds lines between releases, so the reader takes the five it
    names and leaves the rest - and a `MemAvailable` that is not a plain count
    is a reading nobody took, never a zero.
    """
    assert host.meminfo_bytes("Hugepagesize: 2048 kB\n") == dict.fromkeys(host.MEMINFO_KEYS)
    assert host.meminfo_bytes("MemAvailable:   nonsense kB\n")["MemAvailable"] is None
    assert host.meminfo_bytes(meminfo(A_WINDOW_OPEN_KB))["MemAvailable"] == (
        A_WINDOW_OPEN_KB * 1024
    )


def test_the_runner_name_is_read_off_the_platform_and_never_invented() -> None:
    """A developer machine publishes nothing and says so with an empty cell."""
    assert host.runner_name({"RUNNER_NAME": "  ubuntu-4core-3  "}) == "ubuntu-4core-3"
    assert host.runner_name({"RUNNER_NAME": "   "}) is None
    assert host.runner_name({}) is None


def test_the_server_pid_is_found_by_asking_the_kernel(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The alternative is an environment variable set in a shell and read in a stage.

    Driven from a `/proc` the test builds, so the case the developer box cannot
    produce - a process table with the server in it - is present rather than
    waited for.
    """
    for pid, comm in (("1", "systemd"), ("742", "llama-server"), ("900", "python3")):
        entry = tmp_path / pid
        entry.mkdir()
        (entry / "comm").write_text(f"{comm}\n", encoding="utf-8")
    (tmp_path / "self").mkdir()
    monkeypatch.setattr(host, "PROC", tmp_path)

    assert host.llama_server_pid() == 742
    assert host.llama_server_pid("nothing-runs-under-this-name") is None


def test_a_process_table_this_machine_will_not_open_reports_nothing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Nothing here is retried and nothing raises."""
    monkeypatch.setattr(host, "PROC", tmp_path / "absent")

    assert host.llama_server_pid() is None


#: One process's memory, at values the test chooses. `VmPeak` is the VIRTUAL
#: high-water mark - a different fact that shares a prefix with `VmHWM` - so a
#: reader matching on `Vm` rather than on the whole key is caught here.
A_SERVER_RSS_KB = 12_570_364
A_SERVER_PEAK_KB = 12_884_901
A_VIRTUAL_PEAK_KB = 23_456_789
OUR_OWN_RSS_KB = 1_530_112


def proc_status(name: str, *, rss_kb: int, peak_kb: int) -> str:
    """One `/proc/<pid>/status`, in the kernel's own layout and its own unit.

    Written here rather than read off the box: the file does not exist on the
    machines this suite runs on. The neighbouring lines are real ones, so the
    two that are read have to be found among the rest rather than on their own.
    """
    return (
        f"Name:\t{name}\n"
        "State:\tS (sleeping)\n"
        f"VmPeak:\t{A_VIRTUAL_PEAK_KB} kB\n"
        f"VmHWM:\t{peak_kb} kB\n"
        f"VmRSS:\t{rss_kb} kB\n"
        f"RssAnon:\t{rss_kb - 2048} kB\n"
        "Threads:\t9\n"
    )


def test_one_open_a_tick_answers_both_of_a_processs_status_lines(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Two lines of one file describe one instant, so one open has to answer both.

    **The Oracle is the count, not the values.** A second open returns the same
    two numbers on any quiet machine, so reading the values back would pass
    whether the file was opened once or twice; what can fail is how many times
    it was opened. One open per process per tick, and two processes are read, so
    a tick opens two status files and never three.

    The values are asserted underneath only so that one open recovering nothing
    from the file cannot pass. **What this cannot settle:** nothing material -
    the values are unchanged by construction.
    """
    # One more than our own, so the two processes are two files whatever pid the
    # test worker drew.
    server_pid = os.getpid() + 1
    for pid, status in (
        (server_pid, proc_status("llama-server", rss_kb=A_SERVER_RSS_KB, peak_kb=A_SERVER_PEAK_KB)),
        (os.getpid(), proc_status("python3", rss_kb=OUR_OWN_RSS_KB, peak_kb=OUR_OWN_RSS_KB)),
    ):
        entry = tmp_path / str(pid)
        entry.mkdir()
        (entry / "status").write_text(status, encoding="utf-8")
    monkeypatch.setattr(host, "PROC", tmp_path)
    # A spy over the module's one reader, so what is counted is a real open of a
    # real file rather than a stand-in that returned text (Guardrail #7).
    reads_a_file = host._text
    opened: list[Path] = []

    def counted(path: Path) -> str | None:
        opened.append(path)
        return reads_a_file(path)

    monkeypatch.setattr(host, "_text", counted)

    # A zero interval starts no sampling thread, so the ticks are the two ends.
    cells = host.Watch(interval_s=0, server_pid=server_pid).close()

    ticks = 2
    opens = Counter(opened)
    assert opens[tmp_path / str(server_pid) / "status"] == ticks
    assert opens[tmp_path / str(os.getpid()) / "status"] == ticks
    assert max(opens.values()) <= ticks, f"a file was opened twice in one tick: {opens}"
    assert cells.llama_rss_bytes == A_SERVER_RSS_KB * 1024
    assert cells.llama_rss_peak_bytes == A_SERVER_PEAK_KB * 1024
    assert cells.python_rss_bytes == OUR_OWN_RSS_KB * 1024


def test_a_status_line_this_project_does_not_read_is_ignored(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Two keys out of about sixty, matched whole, and a key the file lacks is unknown.

    A pid nobody named and a process this machine will not open are the same
    answer as a file with neither line in it: two unknowns, never two zeros.
    """
    entry = tmp_path / "9931"
    entry.mkdir()
    (entry / "status").write_text(f"VmPeak:\t{A_VIRTUAL_PEAK_KB} kB\n", encoding="utf-8")
    monkeypatch.setattr(host, "PROC", tmp_path)

    assert host.status_bytes(9931) == dict.fromkeys(host.STATUS_KEYS)
    assert host.status_bytes(None) == dict.fromkeys(host.STATUS_KEYS)
    assert host.status_bytes(4242) == dict.fromkeys(host.STATUS_KEYS)


def _aggregate_cpu_line(text: str) -> list[int]:
    """The ten counters on the one `cpu ` line of a /proc/stat capture."""
    aggregate = [line for line in text.splitlines() if line.split()[:1] == ["cpu"]]
    assert len(aggregate) == 1, "a /proc/stat capture has exactly one aggregate cpu line"
    return [int(cell) for cell in aggregate[0].split()[1:]]


def test_the_two_proc_stat_captures_an_oracle_reads_are_committed() -> None:
    """A test over a fixture that is not there proves nothing and still passes.

    `.gitignore` carries `*.log`, and a capture named after the file it came
    from has been silently ignored before - so the files are asserted present
    rather than assumed.
    """
    for path in (PROC_STAT_AT_START, PROC_STAT_AT_END):
        assert path.is_file(), path.name


def test_the_processor_busy_share_is_read_from_a_real_proc_stat_pair() -> None:
    """The Oracle for `cpu_shares_between`: the capture proves its own window.

    Twenty seconds of four processors at 100 Hz is 8,000 ticks. A real pair
    reproduces that, and a hand-written pair only does so by arithmetic somebody
    already did - which is the same arithmetic under test. The busy share itself
    is worked out here from the raw text, field by field, so this cannot pass by
    agreeing with the function about a mistake.

    The reading is near zero because the probe slept through its own window. The
    shape is what is under test; the expected value on a work shard is near 100.

    **This runner reported no stolen ticks at either end**, which is asserted
    rather than assumed: a capture with steal in it would make the subtraction
    below and the one in the function differ, and the reader deserves to know
    which arm of the arithmetic this fixture exercises.
    """
    at_start = read_text(PROC_STAT_AT_START)
    at_end = read_text(PROC_STAT_AT_END)
    start = _aggregate_cpu_line(at_start)
    end = _aggregate_cpu_line(at_end)
    # guest sits inside user and guest_nice inside nice, so a plain sum of the
    # line counts both twice. idle and iowait are the processors standing free,
    # and steal is time the host gave to somebody else's machine.
    available = (sum(end) - end[8] - end[9]) - (sum(start) - start[8] - start[9])
    idle = (end[3] + end[4]) - (start[3] + start[4])
    stolen = end[7] - start[7]
    shares = host.cpu_shares_between(at_start, at_end)

    assert stolen == 0 and end[7] == 0, "this pair was taken on a runner with no stolen ticks"
    assert available == pytest.approx(PROBE_SECONDS * PROBE_PROCESSORS * USER_HZ, rel=0.01)
    assert shares is not None
    assert shares.busy_pct == pytest.approx(100 * (available - idle - stolen) / available, abs=0.005)
    assert shares.steal_pct == 0.0


def test_a_capture_nobody_took_is_absent_rather_than_a_share_of_zero() -> None:
    """An empty variable and a truncated read are both unknown, and unknown is not zero."""
    at_start = read_text(PROC_STAT_AT_START)

    assert host.cpu_ticks(None) is None
    assert host.cpu_ticks("") is None
    assert host.cpu_ticks("cpu\n") is None
    assert host.cpu_ticks("cpu not a number\n") is None
    assert host.cpu_shares_between(at_start, None) is None
    assert host.cpu_shares_between(None, at_start) is None
    assert host.cpu_shares_between(at_start, at_start) is None, (
        "a window of no elapsed ticks has no share to report"
    )


#: A window a test writes, with a quarter of it handed to somebody else. The
#: deltas are user 400, system 200, idle 150, iowait 50 and steal 200, so the
#: interval is 1,000 ticks of which 600 were ours and 200 were never offered.
A_WINDOW_AT_START = "cpu  1000 0 1000 1000 1000 0 0 1000 0 0\n"
A_WINDOW_AT_END = "cpu  1400 0 1200 1150 1050 0 0 1200 0 0\n"
OUR_SHARE_PCT = 60.0
THE_STOLEN_SHARE_PCT = 20.0
THE_IDLE_SHARE_PCT = 15.0
THE_IOWAIT_SHARE_PCT = 5.0


def test_the_busy_share_leaves_out_what_the_host_gave_another_tenant() -> None:
    """The Oracle for `cpu_shares_between`: four shares that add up to the interval.

    Stolen ticks are time the hypervisor ran somebody else's machine on a
    processor this one was charged for. Counting them as busy - which this
    project did until 2026-09-20 - reports the window above at 80 percent busy,
    when 60 percent was our work and 20 percent was a processor we did not get.

    The sum is the half that cannot be satisfied by moving the theft to the
    other side: busy, stolen, idle and iowait have to account for the whole
    interval and nothing may be counted twice.

    **What it cannot settle:** whether the hypervisor's own steal accounting is
    accurate. That is the platform's contract, not this project's.
    """
    shares = host.cpu_shares_between(A_WINDOW_AT_START, A_WINDOW_AT_END)

    assert shares is not None
    assert shares.busy_pct == OUR_SHARE_PCT
    assert shares.steal_pct == THE_STOLEN_SHARE_PCT
    assert (
        shares.busy_pct + shares.steal_pct + THE_IDLE_SHARE_PCT + THE_IOWAIT_SHARE_PCT == 100.0
    ), "the four shares are the whole interval, and one of them is not ours"


def test_a_kernel_that_does_not_account_theft_records_nothing_rather_than_zero() -> None:
    """A steal figure of zero is a claim about the host, and a short line makes none.

    The column arrived in Linux 2.6.11 and every runner this project draws
    reports it, so this is the arm a developer machine will never produce - which
    is why it is written here rather than waited for. The busy figure is still
    the best the kernel can give: a kernel that does not account theft has
    already folded it into user and system time, and nothing downstream can
    unpick that.
    """
    no_steal_field = ("cpu  1000 0 1000 1000 1000 0 0\n", "cpu  1400 0 1200 1150 1050 0 0\n")

    shares = host.cpu_shares_between(*no_steal_field)

    assert shares is not None
    assert shares.steal_pct is None
    assert shares.busy_pct == pytest.approx(75.0), "600 ours plus the 200 nobody accounted"


def test_the_sampler_reports_the_corrected_busy_share_and_the_stolen_one(
    monkeypatch: MonkeyPatch,
) -> None:
    """The item's own cells, not only the arithmetic underneath them.

    The two captures are written by the test, so the window is a known one
    rather than whatever the box that ran the suite was doing. A zero interval
    starts no sampling thread, so the reading is the two ends and the maximum
    and the minimum are that same whole-item figure.
    """
    captures = iter([A_WINDOW_AT_START, A_WINDOW_AT_END])

    def one_file(path: Path) -> str | None:
        return next(captures, None) if path == host.PROC_STAT else None

    monkeypatch.setattr(host, "_text", one_file)

    cells = host.Watch(interval_s=0).close()

    assert cells.cpu_busy_pct == OUR_SHARE_PCT
    assert cells.cpu_steal_pct == THE_STOLEN_SHARE_PCT
    assert cells.cpu_busy_max == cells.cpu_busy_min == OUR_SHARE_PCT


#: One process's fault counters, at values the test chooses. The minor count is
#: the neighbouring field, so a reader off by one lands on it and is caught.
A_MINOR_FAULT_COUNT = 1_234_567
FAULTS_AT_ITEM_OPEN = 4_096
FAULTS_AT_ITEM_CLOSE = 4_621

#: The kernel brackets the command and it may hold a space or a bracket of its
#: own, so a name carrying both is what the fixture uses.
A_SERVER_COMMAND = "llama-server (ggml)"


def proc_stat(pid: int, *, major_faults: int) -> str:
    """One `/proc/<pid>/stat`, in the kernel's own layout and its own order.

    Written here rather than read off the box: the file does not exist on the
    machines this suite runs on. The fields before and after the fault count are
    real ones, so the count has to be found by position among the rest.
    """
    ppid, pgrp, session, tty_nr, tpgid, flags = 1, pid, pid, 0, -1, 4_194_560
    cminflt, cmajflt, utime, stime = 0, 0, 4_200, 310
    return (
        f"{pid} ({A_SERVER_COMMAND}) S {ppid} {pgrp} {session} {tty_nr} {tpgid} {flags} "
        f"{A_MINOR_FAULT_COUNT} {cminflt} {major_faults} {cmajflt} {utime} {stime} 0 0 20 0 9\n"
    )


def _a_server_the_test_owns(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> tuple[int, dict[str, int], list[Path]]:
    """A process table the test owns, whose fault counter it moves by hand.

    Returns the pid, the counter the test writes into, and the list every open
    is appended to - so a test can assert how OFTEN a file was read as well as
    what it said.
    """
    # One more than our own, so the two processes are two files whatever pid the
    # test worker drew.
    server_pid = os.getpid() + 1
    entry = tmp_path / str(server_pid)
    entry.mkdir()
    stat_file = entry / "stat"
    faults = {"count": FAULTS_AT_ITEM_OPEN}
    monkeypatch.setattr(host, "PROC", tmp_path)
    # A spy over the module's one reader, so what is counted is a real open of a
    # real file rather than a stand-in that returned text (Guardrail #7).
    reads_a_file = host._text
    opened: list[Path] = []

    def counted(path: Path) -> str | None:
        opened.append(path)
        if path == stat_file:
            stat_file.write_text(
                proc_stat(server_pid, major_faults=faults["count"]), encoding="utf-8"
            )
        return reads_a_file(path)

    monkeypatch.setattr(host, "_text", counted)
    return server_pid, faults, opened


def test_the_fault_count_is_the_difference_across_the_item(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The Oracle for the fault count: two counter reads, and the item is the gap.

    A major fault is a page the process had to wait for off disk. llama.cpp maps
    the weights file-backed, so a kernel reclaiming them charges the next token
    back to storage - and the pages leave an RSS figure without touching a swap
    counter, which is why nothing else on the row can see it.

    The counter runs from the process's start, so one read says nothing about an
    item and the reading is the difference. The counter is moved between the two
    ends by the test, so the answer is a known one.

    **What it cannot settle:** whether a fault was a weight page or another
    mapping - the counter is per process, not per mapping.
    """
    server_pid, faults, _ = _a_server_the_test_owns(monkeypatch, tmp_path)

    watch = host.Watch(interval_s=0, server_pid=server_pid)
    faults["count"] = FAULTS_AT_ITEM_CLOSE

    assert watch.close().llama_major_faults == FAULTS_AT_ITEM_CLOSE - FAULTS_AT_ITEM_OPEN


def test_the_fault_counter_is_read_at_the_items_ends_and_never_on_a_tick(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A counter differenced across the window, so the tick interval cannot move it.

    The two watches are the whole assertion: one with the sampling thread off
    and one that is held open until it has taken a sample. The status file is
    read every tick and proves the second watch really sampled; the fault
    counter has to come out at the same count as the first, or the figure is a
    gauge and `logging.waiting_heartbeat_seconds` silently changes it.
    """
    server_pid, _, opened = _a_server_the_test_owns(monkeypatch, tmp_path)
    stat_file = tmp_path / str(server_pid) / "stat"
    status_file = tmp_path / str(server_pid) / "status"

    with host.Watch(interval_s=0, server_pid=server_pid):
        pass
    at_rest = Counter(opened)
    opened.clear()
    ticked = threading.Event()
    with host.Watch(interval_s=0.01, server_pid=server_pid, on_tick=lambda _: ticked.set()):
        assert ticked.wait(timeout=10.0), "the sampler never ticked"
    sampling = Counter(opened)

    assert sampling[status_file] > at_rest[status_file], "the sampler took no sample to compare"
    assert sampling[stat_file] == at_rest[stat_file] > 0, (
        f"the fault counter was read {sampling[stat_file]} times with the sampler running "
        f"against {at_rest[stat_file]} with it off"
    )


def test_a_server_that_started_again_mid_item_records_no_fault_count(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A count that went down is a counter that started again, not a negative number of faults.

    The alternative is a difference that reads as a quiet item on the morning the
    server died and came back, which is the one morning the count is worth
    having.
    """
    server_pid, faults, _ = _a_server_the_test_owns(monkeypatch, tmp_path)

    watch = host.Watch(interval_s=0, server_pid=server_pid)
    faults["count"] = FAULTS_AT_ITEM_OPEN - 1

    assert watch.close().llama_major_faults is None


def test_a_fault_counter_this_machine_will_not_answer_reports_nothing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A pid nobody named, a process gone, and a file of the wrong shape are all unknown.

    The command is bracketed and carries a bracket of its own here, so a reader
    splitting on the FIRST one lands on the wrong field and is caught - and the
    minor count sits one field before the major one, so an off-by-one is caught
    as well.
    """
    entry = tmp_path / "9931"
    entry.mkdir()
    (entry / "stat").write_text(proc_stat(9931, major_faults=FAULTS_AT_ITEM_OPEN), encoding="utf-8")
    (tmp_path / "4242").mkdir()
    (tmp_path / "4242" / "stat").write_text("4242 (a-truncated-read)\n", encoding="utf-8")
    monkeypatch.setattr(host, "PROC", tmp_path)

    assert host.major_faults(9931) == FAULTS_AT_ITEM_OPEN
    assert host.major_faults(9931) != A_MINOR_FAULT_COUNT
    assert host.major_faults(4242) is None
    assert host.major_faults(None) is None
    assert host.major_faults(7777) is None


def test_the_aggregate_line_is_read_out_of_a_whole_capture_or_out_of_the_line_alone() -> None:
    """The workflow used to pass one line and the sampler passes the whole file.

    Both are the same fact with the per-processor lines attached or not, so one
    reader takes both rather than two readers taking one each.
    """
    whole = read_text(PROC_STAT_AT_START)
    aggregate = next(line for line in whole.splitlines() if line.split()[:1] == ["cpu"])

    assert host.cpu_ticks(whole) == host.cpu_ticks(aggregate)
    assert host.cpu_ticks(aggregate) is not None


def test_the_kernel_peak_reads_the_file_and_the_line_the_shard_job_copies_it_into(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The Oracle for `cgroup_peak_bytes`: the kernel's own file, and nothing else.

    The kernel writes a bare count. Anything else is unknown, and unknown is not
    zero - which is what a GitHub-hosted runner has measured every time this
    project has looked, because the file is not there at all.

    The shard job copies the same count into `memory-peak.txt` for the run
    artifact and the operator's own read of the job log. Nothing parses that
    copy, so the workflow half is asserted here only to prove the number a
    person reads and the number this function reads come from one file.
    """
    workflow = read_text(REPO_ROOT / ".github" / "workflows" / "digest.yml")
    assert "cgroup_memory_peak_bytes=$(cat /sys/fs/cgroup/memory.peak)" in workflow
    assert "cgroup_memory_peak_bytes=unavailable" in workflow

    # The kernel's own shape, from the file this module opens. Built here: the
    # path is absent on every machine that runs this.
    kernel_file = tmp_path / "memory.peak"
    kernel_file.write_text(f"{A_KERNEL_PEAK}\n", encoding="utf-8")
    monkeypatch.setattr(host, "CGROUP_PEAK", kernel_file)

    assert host.cgroup_peak_bytes() == A_KERNEL_PEAK

    kernel_file.write_text("unavailable\n", encoding="utf-8")

    assert host.cgroup_peak_bytes() is None, "anything that is not a count is unknown"

    monkeypatch.setattr(host, "CGROUP_PEAK", tmp_path / "absent")

    assert host.cgroup_peak_bytes() is None


def test_the_processor_is_read_once_here_and_never_reported_in(
    monkeypatch: MonkeyPatch,
) -> None:
    """One reader for one fact, so two rows of one shard cannot name two parts.

    It answers on every machine this suite runs on, so what is asserted is that
    it answered rather than what it said - and that a host with nothing to say
    records nothing instead of an empty string.
    """
    assert host.cpu_model() is not None

    monkeypatch.setattr(host, "host_cpu", lambda: "   ")

    assert host.cpu_model() is None, "a probe that said nothing is not a part with no name"


def test_one_sampler_call_reaches_every_row_and_they_cannot_disagree() -> None:
    """Every row one shard writes names one machine, because one call read it.

    The processor cannot change inside a job, so a second reading per item is an
    extra `/proc/cpuinfo` open for an answer already taken - and two readings are
    two answers nobody can reconcile (Guardrail #10).

    **What it cannot settle.** Whether either sample is representative of the
    item's whole run - a single point sample never is - and it says nothing
    about `cpu_busy_pct`, which is one item's window and is SUPPOSED to differ
    between two items of one shard.
    """
    once = host.host_facts(environ={"RUNNER_NAME": "ubuntu-4core-3"})

    item_cells = host.Watch(interval_s=0, facts=once).close().cells()

    assert item_cells["cgroup_peak_bytes"] == once.cgroup_peak_bytes
    assert once.shard_cells()["cpu_model"] == once.cpu_model
    assert once.runner_name == "ubuntu-4core-3", (
        "the label is still read here, and `state/host-fingerprint/` is what writes it down"
    )
    assert "runner_name" not in once.shard_cells(), (
        "the item row retired the column on 2026-09-17; the host record carries it once a job"
    )
    assert once.shard_cells()["job"] is None, (
        "no file on the host names the workflow job, so nothing may invent one"
    )


def test_every_host_cell_the_sampler_names_is_a_column_the_item_row_declares() -> None:
    """Sixteen names, and the row has to hold all sixteen or the cells go nowhere.

    Pure code over the contract, so it cannot age out with the archive and it
    cannot pass by reading a day that happens to carry them (section 13). A cell
    the sampler emits under a name `ItemHealthRow` does not declare is a cell the
    recorder would refuse, which is a failure at the end of an eight-minute item
    rather than here.

    **The other direction is asserted too**, because it is the one that fails
    silently: a reading the sampler takes on every item and leaves out of
    `cells()` is computed 80 times a shard and written down nowhere. The two
    below are held deliberately, and this list empties when the row declares
    them.
    """
    every_reading = host.HostCells(*(None,) * len(fields(host.HostCells)))
    sampled = set(every_reading.cells()) | set(
        host.HostFacts(cpu_model=None, runner_name=None, cgroup_peak_bytes=None).shard_cells()
    )

    assert sampled == {
        "cpu_busy_pct",
        "cpu_busy_max",
        "cpu_busy_min",
        "load_1m",
        "llama_rss_bytes",
        "llama_rss_peak_bytes",
        "python_rss_bytes",
        "cgroup_peak_bytes",
        "os_mem_available_bytes",
        "os_mem_total_bytes",
        "os_mem_cached_bytes",
        "os_swap_free_bytes",
        "os_swap_total_bytes",
        "os_mem_available_min_bytes",
        "cpu_model",
        "job",
    }
    assert sampled <= set(ItemHealthRow.model_fields)
    assert {field.name for field in fields(host.HostCells)} - set(every_reading.cells()) == {
        "cpu_steal_pct",
        "llama_major_faults",
    }, "a reading taken on every item and left out of the cells is written down nowhere"
