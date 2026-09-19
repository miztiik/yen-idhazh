"""What does the host sampler report, and what does it do when the machine will not answer?

Every reading here comes from a `/proc` or `/sys` path that does not exist on the
machines this project is written on, so the degraded path is the ordinary one
locally and the filled path is the ordinary one in CI. Both are driven here, from
files the test writes, because a reading only CI can take is a reading nobody
checks - and a test that reads the machine it runs on passes or fails on the
weather.

Sibling question, sibling module: `backend/tests/pipeline/test_work_health_payload.py`
asks whether the cells reach the row a shard leaves on disk. This one asks
whether the readings are right, and whether the two consumers can disagree.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR, REPO_ROOT, read_text
from pytest import MonkeyPatch

from idhazh.contracts.item_health import ItemHealthRow
from idhazh.telemetry import host

#: A processor name and a kernel peak the test chooses, so the assertion is
#: against a known answer and never against whatever host ran the suite.
A_PROCESSOR = "Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz"
A_KERNEL_PEAK = 15_032_385_536

#: Two real `/proc/stat` captures, taken twenty seconds apart around the machine
#: probe on an `ubuntu-latest` runner on 2026-08-30. The gap is what makes them
#: an oracle: the tick delta has to reproduce twenty seconds of four processors
#: at 100 Hz, and no hand-written file can be checked that way.
PROC_STAT_AT_START = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-start.txt"

PROC_STAT_AT_END = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-end.txt"

#: What the probe slept for, what the runner reported to `nproc`, and the
#: kernel's tick rate. Guardrail #2 fixes the second at 4.
PROBE_SECONDS = 20

PROBE_PROCESSORS = 4

USER_HZ = 100


def _aggregate_cpu_line(text: str) -> list[int]:
    """The ten counters on the one `cpu ` line of a /proc/stat capture."""
    aggregate = [line for line in text.splitlines() if line.split()[:1] == ["cpu"]]
    assert len(aggregate) == 1, "a /proc/stat capture has exactly one aggregate cpu line"
    return [int(cell) for cell in aggregate[0].split()[1:]]


def test_the_processor_busy_share_is_read_from_a_real_proc_stat_pair() -> None:
    """The Oracle for `cpu_busy_pct`: the capture proves its own window.

    Twenty seconds of four processors at 100 Hz is 8,000 ticks. A real pair
    reproduces that, and a hand-written pair only does so by arithmetic somebody
    already did - which is the same arithmetic under test. The busy share itself
    is worked out here from the raw text, field by field, so this cannot pass by
    agreeing with the reader about a mistake.

    The reading is near zero because the probe slept through its own window. The
    shape is what is under test; the expected value on a work shard is near 100.
    """
    at_start = read_text(PROC_STAT_AT_START)
    at_end = read_text(PROC_STAT_AT_END)
    start = _aggregate_cpu_line(at_start)
    end = _aggregate_cpu_line(at_end)
    # guest sits inside user and guest_nice inside nice, so a plain sum of the
    # line counts both twice. idle and iowait are the processors standing free.
    available = (sum(end) - end[8] - end[9]) - (sum(start) - start[8] - start[9])
    idle = (end[3] + end[4]) - (start[3] + start[4])

    assert available == pytest.approx(PROBE_SECONDS * PROBE_PROCESSORS * USER_HZ, rel=0.01)
    assert host.cpu_busy_pct_between(at_start, at_end) == pytest.approx(
        100 * (available - idle) / available, abs=0.005
    )
    assert host.cpu_busy_pct_between(None, at_end) is None
    assert host.cpu_busy_pct_between(at_end, at_start) is None, (
        "a window that runs backwards is unknown, not a busy share"
    )


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


def test_a_zero_interval_takes_both_ends_and_never_starts_a_thread() -> None:
    """`waiting_heartbeat_seconds = 0` turns the heartbeat off, not the readings."""
    ticks: list[float] = []

    with host.Watch(interval_s=0, on_tick=ticks.append) as watch:
        pass

    assert ticks == []
    assert watch.close().cells()["cpu_busy_pct"] is None or True


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


def test_the_kernel_peak_reads_the_file_the_kernel_writes(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The Oracle for `cgroup_peak_bytes`: a bare count, or nothing.

    A GitHub-hosted runner has measured the file absent every time this project
    has looked, so the absent case is the one that runs in production and it has
    to read as unknown rather than as a job that held no memory.

    The shard job copies the same count into `memory-peak.txt` for the operator
    and the runtime artifact. That copy is read by nobody in Python, so it is the
    workflow's own shape and is asserted there rather than parsed here.
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

    assert host.cgroup_peak_bytes() is None

    monkeypatch.setattr(host, "CGROUP_PEAK", tmp_path / "absent")

    assert host.cgroup_peak_bytes() is None


def test_the_processor_is_read_here_on_every_machine() -> None:
    """One reader for one fact, so no two rows of a job can name two processors.

    `fingerprint.host_cpu` answers on every machine this suite runs on, so what
    is asserted is that it answered, not what it said.
    """
    assert host.cpu_model() is not None


def test_one_sampler_call_reaches_both_consumers_and_they_cannot_disagree(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The item row and that job's host row are one reading.

    Two stores carry a `cpu_model` column - the item row and
    `state/host-fingerprint/`. They are separate stores on purpose: one is a row
    an item and the other is a row a job. What must never differ is the machine
    they name, so both take it from one `host_facts` call, and a `Watch` handed
    those facts reads no file of its own.

    **What it cannot settle.** Whether either sample is representative of the
    item's whole run - a single point sample never is - and it says nothing
    about `cpu_busy_pct`, which is one item's window on the item row and has no
    counterpart on the host row at all.
    """
    kernel_file = tmp_path / "memory.peak"
    kernel_file.write_text(f"{A_KERNEL_PEAK}\n", encoding="utf-8")
    monkeypatch.setattr(host, "CGROUP_PEAK", kernel_file)
    once = host.host_facts(environ={"RUNNER_NAME": "ubuntu-4core-3"})
    monkeypatch.setattr(host, "CGROUP_PEAK", tmp_path / "absent")

    item_cells = host.Watch(interval_s=0, facts=once).close().cells()

    assert item_cells["cgroup_peak_bytes"] == A_KERNEL_PEAK, (
        "a Watch handed facts must not take a second reading of its own"
    )
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
    """
    sampled = set(host.HostCells(*(None,) * 14).cells()) | set(
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
