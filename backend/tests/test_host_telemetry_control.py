"""Does whole-host telemetry off bypass collection while preserving work and waiting logs?"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import FrameType

import pytest
from conftest import CONFIG_DIR, SEED_COMMIT
from pydantic import ValidationError

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry import job_machine, silicon
from idhazh.telemetry.host_control import enabled
from idhazh.telemetry.item_heartbeat import ItemHeartbeat
from utilities.host_telemetry_control import resolve


def test_master_switch_overrides_python_collection(tmp_path: Path) -> None:
    app = config.load(CONFIG_DIR).app
    root = tmp_path / "config"
    root.mkdir()
    path = root / "idhazh.json"
    path.write_text(app.to_json(), encoding="ascii")
    assert app.observability.host_telemetry_enabled
    for mode in ("python", "off"):
        assert resolve(mode, root) == mode
    app.observability.host_telemetry_enabled = False
    path.write_text(app.to_json(), encoding="ascii")
    for mode in ("python", "off"):
        assert resolve(mode, root) == "off"
        assert not enabled(app.observability, {"IDHAZH_HOST_TELEMETRY_MODE": mode})
    with pytest.raises(ValueError, match="python or off"):
        resolve("false", root)
    with pytest.raises(ValidationError):
        ObservabilityConfig.model_validate({"host_telemetry_enabled": "false"})


@pytest.mark.parametrize("choice", ["rust", "legacy", "native", "shadow", "false"])
def test_only_python_and_off_are_valid_even_when_master_is_off(
    tmp_path: Path, choice: str
) -> None:
    with pytest.raises(ValueError, match="python or off"):
        resolve(choice, tmp_path)
    with pytest.raises(ValueError, match="python or off"):
        enabled(ObservabilityConfig(host_telemetry_enabled=False),
                {"IDHAZH_HOST_TELEMETRY_MODE": choice})


def test_missing_mode_defaults_to_python() -> None:
    assert enabled(ObservabilityConfig(), {})
    assert enabled(ObservabilityConfig(), {"IDHAZH_HOST_TELEMETRY_MODE": "python"})


@pytest.mark.parametrize("via_config", [False, True], ids=["dispatch-off", "config-off"])
def test_off_writes_neither_python_host_half(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, via_config: bool
) -> None:
    settings = config.load(CONFIG_DIR)
    settings.app.observability.host_telemetry_enabled = not via_config
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "python" if via_config else "off")
    with job_machine.record(
        date="2026-10-10", run_id="2026-10-10-17", settings=settings,
        state_root=tmp_path / "state", commit_sha=SEED_COMMIT, job=ServerJob.RUNTIME,
    ) as paths:
        assert paths == []
    for writer in (silicon.file_machine_row, silicon.file_job_clock):
        result, written = writer(
            date="2026-10-10", run_id="2026-10-10-17", settings=settings,
            state_root=tmp_path / "state", commit_sha=SEED_COMMIT,
        )
        assert result is None and written == []
    assert not ledger.raw_root(tmp_path / "state", LedgerName.HOST_FINGERPRINT).exists()
    assert not (tmp_path / "backend").exists()


def test_off_watch_preserves_heartbeat_and_returns_unknown_cells() -> None:
    ticked = threading.Event()
    intervals: list[float] = []

    def tick(elapsed: float) -> None:
        intervals.append(elapsed)
        ticked.set()

    with ItemHeartbeat(interval_s=0.005, on_tick=tick) as heartbeat:
        assert ticked.wait(timeout=2)
        cells = heartbeat.close()
    assert intervals and all(value >= 0 for value in intervals)
    assert all(value is None for value in cells.cells().values())
    assert heartbeat._thread is None




@pytest.mark.parametrize("control", ["dispatch-off", "config-off", "memory-off", "python-on"])
def test_real_work_preserves_item_health_under_host_and_memory_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, control: str
) -> None:
    from pipeline._builders import (
        a_server_that_refuses_every_completion,
        captured_article_fetch,
        isolate_ledgers,
        plan,
    )

    from idhazh.contracts.item_health import ItemHealthRow
    from idhazh.stages.work import stage_work
    from idhazh.telemetry import host
    from idhazh.telemetry.record import HEALTH_SUFFIX

    monkeypatch.setenv(
        "IDHAZH_HOST_TELEMETRY_MODE", "off" if control == "dispatch-off" else "python"
    )
    monkeypatch.setenv("MEMORY_PROFILING", "off" if control == "memory-off" else "on")
    settings = config.load(CONFIG_DIR)
    settings.app.observability.host_telemetry_enabled = control != "config-off"
    isolate_ledgers(tmp_path, monkeypatch)
    run_plan = plan()
    observed: list[str] = []

    def profile(frame: FrameType, event: str, argument: object) -> None:
        if event == "call" and frame.f_globals.get("__name__") == "idhazh.telemetry.host":
            if frame.f_code.co_filename == host.__file__ and frame.f_code.co_name not in (
                "cells", "shard_cells"
            ):
                observed.append(frame.f_code.co_name)

    with a_server_that_refuses_every_completion() as server:
        previous = sys.getprofile()
        sys.setprofile(profile)
        try:
            stage_work(
                run_plan, settings=settings, scorer=None, fetcher=captured_article_fetch,
                model_endpoint=server.endpoint,
            )
        finally:
            sys.setprofile(previous)
    items = tmp_path / "run" / run_plan.date / "items"
    health = [
        ItemHealthRow.from_json(path.read_text(encoding="utf-8"))
        for path in items.glob(f"*{HEALTH_SUFFIX}")
    ]
    assert len(health) == len(run_plan.items)
    assert all(row.machine_job == ServerJob.WORK and row.machine_shard == 0 for row in health)
    if control in ("dispatch-off", "config-off"):
        assert all(row.cpu_busy_pct is None and row.llama_rss_bytes is None for row in health)
        assert observed == [], "whole-host off called a Python host collector"
    else:
        assert "read_now" in observed
        if control == "memory-off":
            assert not {"status_bytes", "meminfo_bytes", "major_faults"} & set(observed)
            assert all(row.llama_rss_bytes is None and row.os_mem_total_bytes is None
                       for row in health)
        else:
            assert "status_bytes" in observed
