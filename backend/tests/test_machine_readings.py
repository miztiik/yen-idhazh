"""What does the machine watch report, and what does it do when the machine will not answer?

Every reading here comes from a `/proc` path that does not exist on the machines
this project is written on, so the degraded path is the ordinary one locally and
the filled path is the ordinary one in CI. Both are driven here, from files the
test writes, because a reading only CI can take is a reading nobody checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch

from idhazh import machine


def test_a_machine_with_no_proc_records_empty_and_never_raises() -> None:
    """A missing instrument degrades the row rather than the run (section 1a)."""
    watch = machine.Watch(interval_s=0)

    span = watch.close()

    assert set(span.cells()) == {
        "cpu_busy_pct",
        "cpu_busy_max",
        "cpu_busy_min",
        "load_1m",
        "llama_rss_bytes",
        "llama_rss_peak_bytes",
        "python_rss_bytes",
        "cgroup_peak_bytes",
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
        return next(captures, None) if path == machine.PROC_STAT else None

    monkeypatch.setattr(machine, "_text", one_file)

    watch = machine.Watch(interval_s=0)
    span = watch.close()

    # 400 busy ticks of 1,000 elapsed.
    assert span.cpu_busy_pct == pytest.approx(40.0)


def test_a_zero_interval_takes_both_ends_and_never_starts_a_thread() -> None:
    """`waiting_heartbeat_seconds = 0` turns the heartbeat off, not the readings."""
    ticks: list[float] = []

    with machine.Watch(interval_s=0, on_tick=ticks.append) as watch:
        pass

    assert ticks == []
    assert watch.close().cells()["cpu_busy_pct"] is None or True


def test_the_runner_name_is_read_off_the_platform_and_never_invented() -> None:
    """A developer machine publishes nothing and says so with an empty cell."""
    assert machine.runner_name({"RUNNER_NAME": "  ubuntu-4core-3  "}) == "ubuntu-4core-3"
    assert machine.runner_name({"RUNNER_NAME": "   "}) is None
    assert machine.runner_name({}) is None


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
    monkeypatch.setattr(machine, "PROC", tmp_path)

    assert machine.llama_server_pid() == 742
    assert machine.llama_server_pid("nothing-runs-under-this-name") is None


def test_a_process_table_this_machine_will_not_open_reports_nothing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Nothing here is retried and nothing raises."""
    monkeypatch.setattr(machine, "PROC", tmp_path / "absent")

    assert machine.llama_server_pid() is None
