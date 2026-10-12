"""Does a native runtime repeat measure its actual workers without a second sampler?"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utilities.runtime_sweep import (
    launcher_workspace,
    native_memory,
    require_memory_for_sweep,
    work_command,
)


def test_native_work_command_keeps_the_exact_plan_and_process_identity(tmp_path: Path) -> None:
    command = work_command(
        config_root=Path("candidate"),
        date="2026-09-27",
        execution=123,
        shard=1,
        shards=2,
        commit_sha="a" * 40,
        native=True,
    )
    boundary = command.index("--")
    launcher, worker = command[:boundary], command[boundary + 1 :]
    assert launcher[launcher.index("--run-id") + 1] == "2026-09-27-123"
    assert launcher[launcher.index("--job") + 1] == "work"
    assert worker[1:4] == ["backend/utilities/digest_publish.py", "run", "work"]
    assert worker[worker.index("--config") + 1] == "candidate"
    for argv in (launcher, worker):
        assert argv[argv.index("--shard") + 1] == "1"
    assert worker[worker.index("--execution") + 1] == "123"
    assert worker[worker.index("--shards") + 1] == "2"


def test_legacy_work_command_opens_no_event_session(tmp_path: Path) -> None:
    command = work_command(
        config_root=tmp_path,
        date="2026-09-27",
        execution=123,
        shard=0,
        shards=1,
        commit_sha="a" * 40,
        native=False,
    )
    assert command[1:4] == ["-m", "idhazh", "work"]
    assert "d7_host_telemetry.py" not in " ".join(command)


def test_native_memory_consumes_only_named_monitor_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "native-artifacts"
    root.mkdir()
    readings = [{"VmRSS": "123 kB", "VmHWM": "456 kB"}, {}]
    (root / "server-rss-samples.jsonl").write_text(
        "\n".join(json.dumps(row) for row in readings) + "\n", encoding="ascii"
    )
    (root / "cgroup-memory-peak.txt").write_text("16384\n", encoding="ascii")
    assert native_memory(tmp_path) == (readings, "16384")


def test_absent_native_memory_stays_unmeasured(tmp_path: Path) -> None:
    assert native_memory(tmp_path) == ([], None)
    with pytest.raises(RuntimeError, match="requires memory profiling"):
        require_memory_for_sweep(False)


def test_invalid_native_status_artifact_is_not_a_successful_reading(tmp_path: Path) -> None:
    root = tmp_path / "native-artifacts"
    root.mkdir()
    (root / "server-rss-samples.jsonl").write_text('{"VmRSS": 123}\n', encoding="ascii")
    with pytest.raises(ValueError, match="invalid status"):
        native_memory(tmp_path)


def test_native_artifact_handoff_uses_session_not_repository_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    session = tmp_path / "backend/var/d7-host-telemetry/selected"
    session.mkdir(parents=True)
    handoff = tmp_path / "child.env"
    handoff.write_text(
        f"IDHAZH_HOST_TELEMETRY_WORKSPACE={tmp_path}\n"
        f"IDHAZH_HOST_TELEMETRY_SESSION<<D7_EOF\n{session}\nD7_EOF\n",
        encoding="utf-8",
    )
    assert launcher_workspace(handoff) == session
    handoff.write_text(f"IDHAZH_HOST_TELEMETRY_SESSION={tmp_path}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="escapes"):
        launcher_workspace(handoff)
