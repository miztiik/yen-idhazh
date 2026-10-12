from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = (
    "digest.yml",
    "measure.yml",
    "encoder-comparison.yml",
    "idhazh-gardener.yml",
    "llm-council.yml",
)


def test_named_producers_select_one_reversible_telemetry_writer() -> None:
    for name in WORKFLOWS:
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        assert "IDHAZH_HOST_TELEMETRY_MODE" in text
        assert "vars.IDHAZH_HOST_TELEMETRY_MODE" in text
        assert ".github/actions/d7-host-telemetry" in text
        assert "d7_host_telemetry.py run" in text
        assert "d7_host_telemetry.py cleanup" in text
        assert "IDHAZH_HOST_TELEMETRY_VERIFIED" in text


def test_d7_launcher_declares_isolated_identity_and_lifecycle_order() -> None:
    text = (ROOT / "backend/utilities/d7_host_telemetry.py").read_text(encoding="utf-8")
    assert "backend/var/d7-host-telemetry" in text
    assert "effective-config.json" in text
    assert "IDHAZH_HOST_TELEMETRY_WORKER_PID" in text
    assert "IDHAZH_HOST_TELEMETRY_WORKER_START_TICKS" in text
    assert "IDHAZH_MODEL_SERVER_PID" in text
    assert "IDHAZH_MODEL_SERVER_START_TICKS" in text
    assert "monitor = subprocess.Popen" in text
    assert text.index("monitor = subprocess.Popen") < text.index("gate.touch()")
    assert text.index("gate.touch()") < text.index('_stop(workspace, manifest, "completed")')
    assert "monitor.stopped" in text
    assert "receipt.json" in text
    assert "monitor-cleanup" in text


def test_model_server_exports_pid_reuse_safe_identity() -> None:
    text = (ROOT / ".github/actions/model-server/action.yml").read_text(encoding="utf-8")
    assert "server_pid:" in text
    assert "server_start_ticks:" in text
    assert "IDHAZH_MODEL_SERVER_PID=$pid" in text
    assert "IDHAZH_MODEL_SERVER_START_TICKS=$start_ticks" in text
