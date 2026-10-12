"""Does one strict memory control resolve before any production collection starts?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONFIG_DIR

from idhazh import cli, config
from utilities.memory_profiling_control import resolve, write_override
from utilities.runtime_sweep import require_memory_for_sweep


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


@pytest.mark.parametrize("value", ["false", "true", "0", "yes", "OFF"])
def test_cli_refuses_non_protocol_memory_values(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["work", "--config", str(CONFIG_DIR), "--memory-profiling", value])
    assert raised.value.code == 2
    assert "memory profiling must be 'on' or 'off'" in capsys.readouterr().err


def test_cli_refuses_off_before_legacy_work_collection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(
            [
                "work",
                "--config",
                str(CONFIG_DIR),
                "--state-root",
                str(tmp_path),
                "--memory-profiling",
                "off",
            ]
        )
    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert "Python remains the authoritative work-stage collector" in error
    assert not tuple(tmp_path.iterdir())


def test_memory_dependent_runtime_sweep_refuses_off() -> None:
    require_memory_for_sweep(True)
    with pytest.raises(RuntimeError, match="requires memory profiling"):
        require_memory_for_sweep(False)


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
