"""Does host opt-out leave work, waiting logs and private artifacts independent?"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from support.ledger import SEED_COMMIT
from support.paths import CONFIG_DIR

from idhazh import config
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.telemetry import native_capture
from idhazh.telemetry.host_control import MODE_ENV, enabled, mode
from idhazh.telemetry.item_heartbeat import ItemHeartbeat
from utilities import start_shard_memory
from utilities.host_telemetry_control import resolve


def test_dispatch_and_master_switch_resolve_the_same_mode(tmp_path: Path) -> None:
    app = config.load(CONFIG_DIR).app
    app.observability.host_telemetry_enabled = True
    path = tmp_path / "idhazh.json"
    path.write_text(app.to_json(), encoding="ascii")
    assert mode(app.observability, {}) == "typescript"
    for selected in ("typescript", "off"):
        assert resolve(selected, tmp_path) == mode(app.observability, {MODE_ENV: selected})
    app.observability.host_telemetry_enabled = False
    path.write_text(app.to_json(), encoding="ascii")
    assert resolve("typescript", tmp_path) == "off"
    assert not enabled(app.observability, {MODE_ENV: "typescript"})


@pytest.mark.parametrize("unsupported", ["python", "false"])
def test_invalid_mode_is_refused_even_when_master_is_off(tmp_path: Path, unsupported: str) -> None:
    with pytest.raises(ValueError, match="typescript or off"):
        resolve(unsupported, tmp_path)
    with pytest.raises(ValueError, match="typescript or off"):
        enabled(ObservabilityConfig(host_telemetry_enabled=False), {MODE_ENV: unsupported})


@pytest.mark.parametrize("control", ["dispatch-off", "config-off", "memory-off"])
def test_disabled_native_instruments_create_no_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, control: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(MODE_ENV, "off" if control == "dispatch-off" else "typescript")
    monkeypatch.setenv("MEMORY_PROFILING", "off" if control == "memory-off" else "on")
    settings = config.load(CONFIG_DIR)
    settings.app.observability.host_telemetry_enabled = control != "config-off"
    root = tmp_path / "config"
    root.mkdir()
    (root / "idhazh.json").write_text(settings.app.to_json(), encoding="ascii")
    if control != "memory-off":
        writer = native_capture.writer_for_task(
            "2026-11-26-17", SEED_COMMIT, pipeline="encoder-evaluation", task="score-vectors",
        )
        assert native_capture.file_opening(
            date="2026-11-26", writer=writer, state=tmp_path / "state", settings=settings,
        ) == (None, [])
        assert not (tmp_path / "state").exists()
    start_shard_memory.main()
    assert not (tmp_path / "backend" / "var" / "shard-memory").exists()
    assert not (tmp_path / "memory-sampler.log").exists()


def test_heartbeat_can_tick_without_populating_item_host_cells() -> None:
    ticked = threading.Event()
    with ItemHeartbeat(interval_s=0.005, on_tick=lambda _: ticked.set()) as heartbeat:
        assert ticked.wait(timeout=2)
        assert all(value is None for value in heartbeat.close().cells().values())
