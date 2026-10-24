"""Does one strict memory control resolve before any production collection starts?"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from council._config import copy_config
from support.paths import CONFIG_DIR

from idhazh import cli, config
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.gardener import GardenerConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.telemetry.host_control import memory_override
from utilities.memory_profiling_control import resolve, write_override


def test_config_default_and_cli_override_resolve_once() -> None:
    loaded = config.load(CONFIG_DIR)
    loaded.app.observability.memory_profiling_enabled = True
    assert (
        config.with_memory_profiling_override(
            loaded, False
        ).app.observability.memory_profiling_enabled
        is False
    )
    assert loaded.app.observability.memory_profiling_enabled is True
    assert config.with_memory_profiling_override(loaded, None) is loaded


@pytest.mark.parametrize("choice", ["inherit", "on", "off"])
def test_workflow_environment_resolves_memory_for_every_settings_loader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, choice: str
) -> None:
    root = copy_config(tmp_path)
    gardener_path = root / "idhazh_gardener.json"
    shutil.copyfile(CONFIG_DIR / gardener_path.name, gardener_path)
    gardener = GardenerConfig.model_validate_json(gardener_path.read_text(encoding="utf-8"))
    declarations = root / "gardener"
    declarations.mkdir()
    for name in gardener.task_names:
        declaration = f"{name}.json"
        shutil.copyfile(
            CONFIG_DIR / "gardener" / declaration,
            declarations / declaration,
        )
    path = root / "idhazh.json"
    app = AppConfig.from_json(path.read_text(encoding="utf-8"))
    app.observability.memory_profiling_enabled = False
    path.write_text(app.to_json(), encoding="utf-8", newline="\n")
    monkeypatch.setenv("MEMORY_PROFILING", choice)
    expected = {"inherit": False, "on": True, "off": False}[choice]
    assert config.load(root).app.observability.memory_profiling_enabled is expected
    assert config.load_gardener(root).app.observability.memory_profiling_enabled is expected
    assert config.with_memory_profiling_override(
        config.load(root), not expected
    ).app.observability.memory_profiling_enabled is not expected


@pytest.mark.parametrize("value", ["false", "true", "", "0", "yes", "OFF"])
def test_memory_environment_refuses_non_choices(value: str) -> None:
    with pytest.raises(ValueError, match="inherit, on or off"):
        memory_override({"MEMORY_PROFILING": value})


def test_memory_setting_refuses_truthy_strings() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ObservabilityConfig.model_validate({"memory_profiling_enabled": "false"})


@pytest.mark.parametrize("value", ["false", "true", "0", "yes", "OFF"])
def test_cli_refuses_non_protocol_memory_values(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["work", "--config", str(CONFIG_DIR), "--memory-profiling", value])
    assert raised.value.code == 2
    assert "memory profiling must be 'on' or 'off'" in capsys.readouterr().err






def test_yaml_control_inherits_validated_config_and_accepts_only_protocol_values(
    tmp_path: Path,
) -> None:
    root = tmp_path / "config"
    root.mkdir()
    app = config.load(CONFIG_DIR).app
    app.observability.host_telemetry_enabled = True
    app.observability.memory_profiling_enabled = True
    (root / "idhazh.json").write_text(app.to_json(), encoding="utf-8", newline="\n")
    assert resolve("inherit", root)
    assert resolve("on", root)
    assert not resolve("off", root)
    assert not write_override("off", root)
    assert not resolve("inherit", root)
    assert write_override("on", root)
    assert resolve("inherit", root)
    with pytest.raises(ValueError, match="inherit, on or off"):
        resolve("false", root)
