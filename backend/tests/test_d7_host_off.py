"""Does off launch the real child without native inputs or inherited session state?"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from workflows._harness import _copy_config

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "backend" / "utilities" / "d7_host_telemetry.py"


def _handoff(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) % 3 == 0
    for index in range(0, len(lines), 3):
        assert lines[index].endswith("<<D7_EOF") and lines[index + 2] == "D7_EOF"
    return {
        lines[index].removesuffix("<<D7_EOF"): lines[index + 1]
        for index in range(0, len(lines), 3)
    }


@pytest.mark.parametrize("returncode", [0, 17])
def test_off_runs_a_real_child_with_an_invalid_binary_and_clears_session_state(
    tmp_path: Path, returncode: int
) -> None:
    run_id = f"2026-10-13-{uuid4().hex}"
    output = tmp_path / "child-environment.json"
    handoff = tmp_path / "github-env"
    inherited = {
        f"IDHAZH_HOST_TELEMETRY_{name}": "invalid-inherited-value"
        for name in (
            "SESSION", "WORKSPACE", "MANIFEST", "CONFIG", "INVOCATION", "ARTIFACT_ROOT",
            "ENV_FILE", "RECEIPT", "EFFECTIVE_CONFIG", "BINARY", "WORKER_PID",
            "WORKER_START_TICKS", "MEMORY_PROFILING", "VERIFIED", "SKIPPED",
        )
    }
    child = (
        "import json,os,sys; from pathlib import Path; "
        "Path(sys.argv[1]).write_text(json.dumps("
        "{k:v for k,v in os.environ.items() if k.startswith('IDHAZH_HOST_TELEMETRY_')})); "
        "sys.exit(int(sys.argv[2]))"
    )
    completed = subprocess.run(
        [
            sys.executable, "-B", str(WRAPPER), "run", "--mode", "off", "--job", "work",
            "--run-id", run_id, "--binary", str(tmp_path / "absent-native-executable"),
            "--", sys.executable, "-B", "-c", child, str(output), str(returncode),
        ],
        cwd=tmp_path,
        env={**os.environ, **inherited, "GITHUB_ENV": str(handoff)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == returncode, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "IDHAZH_HOST_TELEMETRY_MODE": "off"
    }
    environment = _handoff(handoff)
    assert environment["IDHAZH_HOST_TELEMETRY_MODE"] == "off"
    assert environment["IDHAZH_HOST_TELEMETRY_SKIPPED"] == "host-telemetry-off"
    assert environment["IDHAZH_HOST_TELEMETRY_VERIFIED"] == "0"
    assert all(environment[key] == "" for key in inherited if key not in {
        "IDHAZH_HOST_TELEMETRY_VERIFIED", "IDHAZH_HOST_TELEMETRY_SKIPPED"
    })
    assert not (ROOT / "backend" / "var" / "d7-host-telemetry" / run_id).exists()
    assert not (tmp_path / "backend").exists()


@pytest.mark.parametrize("requested_mode", ["rust", "legacy"])
def test_a_known_producers_master_false_forces_off_before_native_checks(
    tmp_path: Path, requested_mode: str
) -> None:
    config_root = tmp_path / "config"
    _copy_config(config_root)
    app_path = config_root / "idhazh.json"
    app = json.loads(app_path.read_text(encoding="utf-8"))
    app["observability"]["host_telemetry_enabled"] = False
    app_path.write_text(json.dumps(app), encoding="ascii")
    handoff = tmp_path / "github-env"
    completed = subprocess.run(
        [
            sys.executable, "-B", str(WRAPPER), "run", "--mode", requested_mode, "--job", "runtime",
            "--binary", str(tmp_path / "absent-native-executable"), "--",
            sys.executable, str(ROOT / "backend" / "utilities" / "runtime_sweep.py"),
            "sweep", "--config", str(config_root), "--help",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "GITHUB_ENV": str(handoff),
            "PYTHONPATH": str(ROOT / "backend"),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout
    environment = _handoff(handoff)
    assert environment["IDHAZH_HOST_TELEMETRY_MODE"] == "off"
    assert environment["IDHAZH_HOST_TELEMETRY_SKIPPED"] == "host-telemetry-off"
    assert environment["IDHAZH_HOST_TELEMETRY_VERIFIED"] == "0"
    assert not (tmp_path / "backend").exists()
