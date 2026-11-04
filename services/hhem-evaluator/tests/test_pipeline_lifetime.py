"""Preserve private channels, parent-loss deadlines and trustworthy worker-exit receipts."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

import pytest
from summary_eval_pipeline.contracts import WORKFLOW_VERSION
from summary_eval_pipeline.control import StartupPacket
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.native_log import NativeEvent, NativeLog
from summary_eval_pipeline.phase_services import PhaseServices
from summary_eval_pipeline.phases import guard_work
from summary_eval_pipeline.services import OwnedService
from summary_eval_pipeline.settings import load_pipeline_settings

from hhem_evaluator.api_settings import load_api_settings
from hhem_evaluator.contracts.server_event import ApiDiagnosticData
from hhem_evaluator.contracts.service_settings import StartupContext

from .contract_examples import REPOSITORY, REQUEST_ID
from .generation_cases import example_run
from .pipeline_cases import owned_child_command
from .service_cases import service_settings

# Fixture readiness includes a cold interpreter and installed-package imports.
CHILD_STARTUP_MS = 60000


def start_child(service: Literal["hhem", "host"], mode: str) -> OwnedService:
    return OwnedService(
        service,
        owned_child_command(mode),
        REPOSITORY,
        StartupPacket(version=WORKFLOW_VERSION, startup_id=REQUEST_ID, context=StartupContext()),
        service_settings(
            worker={
                "stop_grace_ms": 500,
                "forced_stop_ms": 1000,
                "shutdown_timeout_ms": 1500,
            }
        ),
        load_pipeline_settings(REPOSITORY),
    )


@pytest.mark.parametrize("mode", ["clean", "mismatch", "early_exit", "blocked_close"])
def test_only_owned_children_are_joined_even_when_readiness_or_close_fails(mode: str) -> None:
    child = start_child("host", mode)
    try:
        if mode in ("mismatch", "early_exit"):
            with pytest.raises(WorkflowError) as failure:
                child.wait_ready(CHILD_STARTUP_MS)
            assert failure.value.error.code == (
                "STARTUP_IDENTITY_MISMATCH" if mode == "mismatch" else "CHILD_EXITED"
            )
        else:
            ready = child.wait_ready(CHILD_STARTUP_MS)
            assert ready.pid == child.process.pid and child.process.poll() is None
    finally:
        if mode in ("early_exit", "blocked_close"):
            with pytest.raises(WorkflowError):
                child.close(100 if mode == "blocked_close" else 1500)
        else:
            assert child.close(1500).clean
        assert child.process.poll() is not None


@pytest.mark.parametrize("blocked", [False, True])
def test_actual_api_parent_watcher_closes_or_exits_its_own_child(blocked: bool) -> None:
    child = start_child("host", "parent_loss_blocked" if blocked else "parent_loss")
    child.wait_ready(CHILD_STARTUP_MS)
    assert child.process.stdin is not None
    child.process.stdin.close()
    child.process.wait(timeout=5)
    if blocked:
        with pytest.raises(WorkflowError):
            child.close(1000)
        assert child.process.returncode == 1
    else:
        assert child.close(1000).clean
        assert child.process.returncode == 0


def test_invalid_child_diagnostics_fail_without_forwarding_raw_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    child = start_child("hhem", "invalid_event")
    try:
        with pytest.raises(WorkflowError) as failure:
            child.wait_ready(CHILD_STARTUP_MS)
            assert child.events_failed.wait(5)
            child.check_alive()
        assert failure.value.error.code == "EVENT_STREAM_FAILED"
    finally:
        with pytest.raises(WorkflowError):
            child.close(1500)
    assert child.process.poll() is not None
    assert "PrivateRawChildCanary" not in str(capsys.readouterr())


def test_inherited_output_cannot_corrupt_a_private_shutdown_receipt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    child = start_child("hhem", "raw_inherited_output")
    child.wait_ready(CHILD_STARTUP_MS)
    stopped = child.close(6000)
    assert stopped.clean and stopped.worker_exit_confirmed is True
    assert child.process.poll() == 0
    output = str(capsys.readouterr())
    assert "PrivateInheritedOutputCanary" not in output
    assert "PrivateInheritedErrorCanary" not in output


@pytest.mark.parametrize(
    ("mode", "confirmed"), [("unclean_stop", True), ("unconfirmed_stop", False)]
)
def test_unclean_shutdown_preserves_an_observed_worker_exit(mode: str, confirmed: bool) -> None:
    child = start_child("hhem", mode)
    child.wait_ready(CHILD_STARTUP_MS)
    with pytest.raises(WorkflowError) as failure:
        child.close(6000)
    assert failure.value.error.code == "SERVICE_STOP_FAILED"
    assert child.process.poll() == 0
    assert child.stopped is not None and child.stopped.worker_exit_confirmed is confirmed
    assert not child.protocol_failed.is_set() and not child.events_failed.is_set()


def test_original_work_failure_and_both_real_cleanup_failures_remain_separate() -> None:
    api = start_child("hhem", "unclean_stop")
    host = start_child("host", "early_exit")
    api.wait_ready(CHILD_STARTUP_MS)
    with pytest.raises(WorkflowError):
        host.wait_ready(CHILD_STARTUP_MS)
    original = WorkflowError("EVALUATION_FAILED", "evaluation", "hhem").error
    errors = [original]
    services = PhaseServices(example_run(), api=api, host=host)
    services.close(
        service_settings(),
        load_api_settings(REPOSITORY / "config" / "fastapi-server.json"),
        errors,
        False,
    )
    assert errors[0] == original
    assert [(error.code, error.service) for error in errors[1:]] == [
        ("SERVICE_STOP_FAILED", "host"),
        ("SERVICE_STOP_FAILED", "hhem"),
    ]
    assert api.process.poll() is not None and host.process.poll() is not None
    assert services.shutdown().worker_exit_confirmed is True
    assert services.shutdown().hhem_stopped is False


@pytest.mark.parametrize("failure", ["open", "write"])
def test_native_log_mirror_failure_warns_and_does_not_fail_useful_work(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    directory = tmp_path / "logs"
    if failure == "open":
        directory.write_text("A regular file is not a log directory.", encoding="utf-8")
    logger = NativeLog(directory, example_run(), service_settings().logging)
    if failure == "write":
        assert logger.file is not None and logger.file.stream is not None
        logger.file.stream.close()
    logger.event(ApiDiagnosticData(component="llama", action="ready", level="INFO"))
    logger.close()
    assert logger.available is False
    events = [
        NativeEvent.model_validate_json(line) for line in capsys.readouterr().err.splitlines()
    ]
    assert any(event.data.code == "LOG_FILE_UNAVAILABLE" for event in events)
    assert any(event.data.action == "ready" for event in events)
    assert logger.filename == "llama-server_2026_11_04_123456_1.log"


@pytest.mark.parametrize("name", ["run.py", "report.py", "serve.py"])
def test_current_entrypoints_resolve_contracts_without_inherited_pythonpath(name: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY / ".github" / "scripts" / "summary-eval-tests" / name),
            "--help",
        ],
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_completed_work_survives_a_simultaneous_real_child_exit() -> None:
    child = start_child("hhem", "early_exit")
    child.process.wait(timeout=30)
    try:

        async def check() -> None:
            done = asyncio.get_running_loop().create_future()
            done.set_result("A completed result is not a shutdown observation.")
            actual = await guard_work(done, child, None, load_pipeline_settings(REPOSITORY))
            assert actual == done.result()

        asyncio.run(check())
    finally:
        with pytest.raises(WorkflowError):
            child.close(1000)
