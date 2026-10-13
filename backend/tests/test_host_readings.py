"""Do native host values retain their names, nulls and caller-supplied job identity?"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_events import HostWindowCells
from idhazh.telemetry import host
from idhazh.telemetry.item_heartbeat import ItemHeartbeat


def test_unknown_host_facts_keep_the_work_job_identity() -> None:
    facts = host.HostFacts(cpu_model=None, runner_name=None, job=ServerJob.WORK)
    assert facts.shard_cells() == {"cpu_model": None, "machine_job": "work"}
    assert host.HostFacts(cpu_model=None, runner_name=None).shard_cells()["machine_job"] is None


def test_native_fact_labels_are_carried_without_a_second_reading() -> None:
    facts = host.HostFacts(cpu_model="Fixture processor", runner_name="fixture", job=ServerJob.WORK)
    assert facts.shard_cells() == {"cpu_model": "Fixture processor", "machine_job": "work"}
    assert facts.runner_name == "fixture"


def test_item_host_cells_serialize_every_native_field_and_preserve_unknowns() -> None:
    assert host.HostCells().cells() == HostWindowCells().model_dump()
    native = HostWindowCells(
        cpu_busy_pct=25.0,
        cpu_busy_max=50.0,
        cpu_busy_min=10.0,
        cpu_steal_pct=2.0,
        load_1m=1.5,
        llama_rss_bytes=8192,
        llama_rss_anon_bytes=4096,
        llama_rss_peak_bytes=16384,
        llama_major_faults=3,
        python_rss_bytes=2048,
        python_rss_anon_bytes=1024,
        os_mem_available_bytes=65536,
        os_mem_total_bytes=131072,
        os_mem_cached_bytes=32768,
        os_swap_free_bytes=0,
        os_swap_total_bytes=0,
        os_mem_available_min_bytes=49152,
    )
    assert host.HostCells(**native.model_dump()).cells() == native.model_dump()


def test_runner_label_is_unknown_when_the_platform_supplies_none() -> None:
    assert host.runner_name({"RUNNER_NAME": "  ubuntu-4core-3  "}) == "ubuntu-4core-3"
    assert host.runner_name({"RUNNER_NAME": "   "}) is None
    assert host.runner_name({}) is None


def test_server_pid_lookup_reads_only_generated_process_names(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    for pid, name in ((1, "systemd"), (742, "llama-server")):
        entry = tmp_path / str(pid)
        entry.mkdir()
        (entry / "comm").write_text(name + "\n", encoding="ascii")
    (tmp_path / "999").mkdir()
    (tmp_path / "not-a-pid").mkdir()
    monkeypatch.setattr(host, "PROC", tmp_path)
    assert host.llama_server_pid() == 742
    assert host.llama_server_pid("missing-server") is None
    monkeypatch.setattr(host, "PROC", tmp_path / "missing")
    assert host.llama_server_pid() is None


@pytest.mark.parametrize("interval", [0.0, -1.0])
def test_disabled_heartbeat_never_starts_a_timer(interval: float) -> None:
    ticks: list[float] = []
    with ItemHeartbeat(interval_s=interval, on_tick=ticks.append) as heartbeat:
        assert all(value is None for value in heartbeat.close().cells().values())
    assert not ticks


@pytest.mark.parametrize("raised", [None, RuntimeError, KeyboardInterrupt])
def test_heartbeat_joins_its_last_callback_on_success_failure_and_cancellation(
    raised: type[BaseException] | None,
) -> None:
    ticked = threading.Event()
    threads: list[threading.Thread] = []
    ticks: list[float] = []

    def tick(elapsed: float) -> None:
        threads.append(threading.current_thread())
        ticks.append(elapsed)
        ticked.set()

    heartbeat = ItemHeartbeat(interval_s=0.005, on_tick=tick)

    def run() -> None:
        with heartbeat:
            assert ticked.wait(1)
            if raised is not None:
                raise raised()

    if raised is None:
        run()
    else:
        with pytest.raises(raised):
            run()
    assert ticks and all(elapsed > 0 for elapsed in ticks)
    assert all(not thread.is_alive() for thread in threads)
    assert all(value is None for value in heartbeat.close().cells().values())
