"""Does one strict memory control resolve before any production collection starts?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONFIG_DIR

from idhazh import cli, config
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.telemetry.host_control import memory_override
from utilities.memory_profiling_control import resolve, write_override


def test_config_default_and_cli_override_resolve_once() -> None:
    loaded = config.load(CONFIG_DIR)
    assert loaded.app.observability.memory_profiling_enabled is True
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
    monkeypatch: pytest.MonkeyPatch, choice: str
) -> None:
    monkeypatch.setenv("MEMORY_PROFILING", choice)
    expected = choice != "off"
    assert config.load(CONFIG_DIR).app.observability.memory_profiling_enabled is expected
    assert config.load_gardener(CONFIG_DIR).app.observability.memory_profiling_enabled is expected
    assert config.with_memory_profiling_override(
        config.load(CONFIG_DIR), not expected
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
