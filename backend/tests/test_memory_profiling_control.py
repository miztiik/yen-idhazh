"""Does one strict memory control resolve before any production collection starts?"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, writer_identity

from idhazh import cli, config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages import common
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


def test_cli_memory_off_admits_unbound_work_on_a_recorded_empty_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in tuple(os.environ):
        if name.startswith("IDHAZH_HOST_TELEMETRY_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    plan = RunPlan(
        version=RunPlan.schema_version(),
        date="2026-10-13",
        run_id="2026-10-13-37",
        generated_at="2026-10-13T00:00:00Z",
        shards=1,
    )
    assert ledger.persist(
        common.STATE_ROOT,
        [plan],
        ledger=LedgerName.RUN_PLAN,
        covers=plan.date,
        identity=writer_identity(plan.run_id, job=ServerJob.PLAN),
    )
    assert (
        cli.main(
            [
                "work",
                "--config",
                str(CONFIG_DIR),
                "--date",
                plan.date,
                "--execution",
                "37",
                "--no-faithfulness",
                "--memory-profiling",
                "off",
            ]
        )
        == 0
    )
    assert not ledger.raw_root(common.STATE_ROOT, LedgerName.HOST_FINGERPRINT).exists()
    assert ledger.load_days(common.STATE_ROOT, LedgerName.RUN_PLAN, [plan.date], model=RunPlan) == [
        plan
    ]


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("legacy", "IDHAZH_HOST_TELEMETRY_MODE must be 'rust'; Python collection was removed"),
        ("rust", "native host session needs --host-event-workspace"),
    ],
)
def test_memory_off_does_not_hide_an_invalid_selected_host_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    message: str,
) -> None:
    for name in tuple(os.environ):
        if name.startswith("IDHAZH_HOST_TELEMETRY_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", mode)
    with pytest.raises(SystemExit) as refused:
        cli.main(["work", "--config", str(CONFIG_DIR), "--memory-profiling", "off"])
    assert refused.value.code == 2
    assert message in capsys.readouterr().err
    assert not common.STATE_ROOT.exists()


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
