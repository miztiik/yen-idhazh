from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from idhazh import config, ledger
from idhazh.cli import (
    _environment_memory_override,
    _event_path,
    _host_event_client,
    _workflow_host_event_mode,
)
from idhazh.contracts.host_events import HostProducerInvocation, HostSessionManifest
from idhazh.contracts.host_output import HostWriterIdentity
from idhazh.contracts.ledger_name import LedgerName

ROOT = Path(__file__).resolve().parents[2]


def test_workflow_mode_is_legacy_by_default_and_native_only_when_selected() -> None:
    assert _workflow_host_event_mode({}) is None
    assert _workflow_host_event_mode({"IDHAZH_HOST_TELEMETRY_MODE": "legacy"}) == "legacy"
    assert _workflow_host_event_mode({"IDHAZH_HOST_TELEMETRY_MODE": "rust"}) == "rust"
    assert _workflow_host_event_mode({"IDHAZH_HOST_TELEMETRY_MODE": "off"}) == "off"
    with pytest.raises(ValueError, match="'legacy', 'rust' or 'off'"):
        _workflow_host_event_mode({"IDHAZH_HOST_TELEMETRY_MODE": "shadow"})


def test_named_session_paths_use_explicit_arguments_before_launcher_environment(
    tmp_path: Path,
) -> None:
    explicit = tmp_path / "explicit"
    from_environment = tmp_path / "environment"

    assert (
        _event_path(
            explicit,
            {"IDHAZH_HOST_TELEMETRY_WORKSPACE": str(from_environment)},
            "IDHAZH_HOST_TELEMETRY_WORKSPACE",
        )
        == explicit
    )
    assert (
        _event_path(
            None,
            {"IDHAZH_HOST_TELEMETRY_WORKSPACE": str(from_environment)},
            "IDHAZH_HOST_TELEMETRY_WORKSPACE",
        )
        == from_environment
    )
    assert _event_path(None, {}, "IDHAZH_HOST_TELEMETRY_WORKSPACE") is None


def test_launcher_memory_control_is_strict_and_preserves_config_when_absent() -> None:
    assert _environment_memory_override({}) is None
    assert _environment_memory_override({"IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING": "true"}) is True
    assert (
        _environment_memory_override({"IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING": "false"}) is False
    )
    with pytest.raises(ValueError, match="must be 'true' or 'false'"):
        _environment_memory_override({"IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING": "off"})


def test_cli_native_mode_requires_independent_invocation_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "rust")
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_CONFIG", str(tmp_path / "native-config.json"))
    monkeypatch.delenv("IDHAZH_HOST_TELEMETRY_INVOCATION", raising=False)
    with pytest.raises(ValueError, match="INVOCATION"):
        _host_event_client(
            argparse.ArgumentParser(),
            argparse.Namespace(
                host_event_workspace=None,
                host_event_manifest=None,
                host_event_config=None,
                host_event_mode=None,
            ),
            config.load(ROOT / "config"),
        )


def test_cli_opens_native_client_from_launcher_paths_and_resolved_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = json.loads((ROOT / "tests/fixtures/host-events/manifest.json").read_bytes())
    session_id = uuid4()
    source.update(
        {
            "session_id": str(session_id),
            "event_root": (
                f"backend/var/host-events/{source['run_id']}/{source['attempt']}/"
                f"{source['job']}/{source['shard']}/{session_id}"
            ),
            "output_roots": [f"backend/var/d7-output/{source['run_id']}/{session_id}"],
        }
    )
    native = json.loads((ROOT / "config/host-telemetry-experiment.json").read_bytes())
    manifest = HostSessionManifest.model_validate(source)
    for name in ("controls", "limits", "capture_limits"):
        native[name] = manifest.model_dump(mode="json")[name]
    (tmp_path / "manifest.json").write_text(manifest.to_json(), encoding="ascii", newline="\n")
    (tmp_path / "native-config.json").write_text(
        json.dumps(native, sort_keys=True) + "\n", encoding="ascii", newline="\n"
    )
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "rust")
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MANIFEST", str(tmp_path / "manifest.json"))
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_CONFIG", str(tmp_path / "native-config.json"))
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING", "true")
    settings = config.load(ROOT / "config")
    invocation = HostProducerInvocation(
        date=manifest.date,
        identity=HostWriterIdentity(
            **manifest.model_dump(include={"run_id", "attempt", "job", "shard", "git_sha"}),
            producer="telemetry.silicon",
        ),
        command=(sys.executable, *sys.argv),
        stage="work",
        shards=1,
        host_enabled=settings.app.observability.host_fingerprint
        and ledger.accepts_new_rows(LedgerName.HOST_FINGERPRINT, 0),
    )
    (tmp_path / "invocation.json").write_text(
        invocation.model_dump_json() + "\n", encoding="ascii", newline="\n"
    )
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_INVOCATION", str(tmp_path / "invocation.json"))

    client = _host_event_client(
        argparse.ArgumentParser(),
        argparse.Namespace(
            host_event_workspace=None,
            host_event_manifest=None,
            host_event_config=None,
            host_event_mode=None,
        ),
        settings,
    )

    assert client is not None and client.native
    assert client.workspace == tmp_path
    assert client.manifest.session_id == session_id

    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "legacy")
    settings.app.observability.host_event_shadow = False
    legacy_client = _host_event_client(
        argparse.ArgumentParser(),
        argparse.Namespace(
            host_event_workspace=None,
            host_event_manifest=None,
            host_event_config=None,
            host_event_mode=None,
        ),
        settings,
    )
    assert legacy_client is None

    settings.app.observability.host_event_shadow = True
    shadow_client = _host_event_client(
        argparse.ArgumentParser(),
        argparse.Namespace(
            host_event_workspace=None,
            host_event_manifest=None,
            host_event_config=None,
            host_event_mode=None,
        ),
        settings,
    )
    assert shadow_client is not None and not shadow_client.native
