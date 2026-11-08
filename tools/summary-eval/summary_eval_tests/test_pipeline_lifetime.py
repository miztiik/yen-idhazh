"""Preserve private channels, parent-loss deadlines and trustworthy worker-exit receipts."""

import asyncio
import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

import pytest
from summary_eval_pipeline.contracts import WORKFLOW_VERSION, PipelineError
from summary_eval_pipeline.control import HostReady, ServiceStopped, StartupPacket
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.native_log import NativeDiagnosticData, NativeEvent, NativeLog
from summary_eval_pipeline.phase_services import PhaseServices, ScorerService
from summary_eval_pipeline.phases import guard_work
from summary_eval_pipeline.scorer_control import (
    SCORER_CONTROL_VERSION,
    ScorerStartupPacket,
    ScorerStopped,
)
from summary_eval_pipeline.services import OwnedService
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator_cases.contract_examples import REPOSITORY, REQUEST_ID
from summary_evaluator_cases.service_cases import service_settings

from summary_eval_tests.generation_cases import example_run
from summary_eval_tests.pipeline_cases import owned_child_command

# Fixture readiness includes a cold interpreter and installed-package imports.
CHILD_STARTUP_MS = 60000


def start_child(service: Literal["api", "host"], mode: str) -> OwnedService:
    startup = StartupPacket(
        version=WORKFLOW_VERSION, startup_id=REQUEST_ID, context=StartupContext()
    )
    scorer: ApiComponent = "unieval" if mode == "unconfirmed_unieval_stop" else "hhem"
    return OwnedService(
        service,
        owned_child_command(mode),
        REPOSITORY,
        ScorerStartupPacket(version=SCORER_CONTROL_VERSION, scorer=scorer, startup=startup)
        if service == "api"
        else startup,
        service_settings(
            worker={
                "stop_grace_ms": 500,
                "forced_stop_ms": 1000,
                "shutdown_timeout_ms": 1500,
            }
        ).worker
        if service == "api"
        else None,
        load_pipeline_settings(REPOSITORY).model_copy(
            update={"host_stop_grace_ms": 500, "host_forced_stop_ms": 1000}
        ),
        api_settings=load_scorer_api_settings(
            REPOSITORY / "config" / "summary-evals" / "api.json", scorer
        )
        if service == "api"
        else None,
    )


def scorer_service(child: OwnedService) -> ScorerService:
    assert (
        child.scorer is not None and child.api_settings is not None and child.settings is not None
    )
    return ScorerService(
        scorer=child.scorer,
        api_settings=child.api_settings,
        worker_settings=child.settings,
        owner=child,
        started=time.monotonic(),
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
    child = start_child("api", "invalid_event")
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
    child = start_child("api", "raw_inherited_output")
    child.wait_ready(CHILD_STARTUP_MS)
    stopped = child.close(6000)
    assert isinstance(stopped, ScorerStopped)
    assert stopped.clean and stopped.worker_exit.confirmed is True
    assert child.process.poll() == 0
    output = str(capsys.readouterr())
    assert "PrivateInheritedOutputCanary" not in output
    assert "PrivateInheritedErrorCanary" not in output


@pytest.mark.parametrize(
    ("mode", "confirmed"),
    [
        ("unclean_stop", True),
        ("unconfirmed_stop", False),
        ("unconfirmed_unieval_stop", False),
    ],
)
def test_unclean_shutdown_preserves_each_observed_worker_exit(
    mode: str, confirmed: bool
) -> None:
    child = start_child("api", mode)
    child.wait_ready(CHILD_STARTUP_MS)
    with pytest.raises(WorkflowError) as failure:
        child.close(6000)
    assert failure.value.error.code == "SERVICE_STOP_FAILED"
    assert child.process.poll() == 0
    assert isinstance(child.stopped, ScorerStopped)
    assert child.stopped.worker_exit.confirmed is confirmed
    assert not child.protocol_failed.is_set() and not child.events_failed.is_set()


def test_original_work_failure_and_both_real_cleanup_failures_remain_separate() -> None:
    api = start_child("api", "unclean_stop")
    host = start_child("host", "early_exit")
    api.wait_ready(CHILD_STARTUP_MS)
    with pytest.raises(WorkflowError):
        host.wait_ready(CHILD_STARTUP_MS)
    original = WorkflowError("EVALUATION_FAILED", "evaluation", "hhem").error
    errors = [original]
    api_service = scorer_service(api)
    services = PhaseServices(example_run(), scorer_apis={"hhem": api_service}, host=host)
    services.close(errors, False, pipeline=load_pipeline_settings(REPOSITORY))
    assert errors[0] == original
    assert [(error.code, error.service) for error in errors[1:]] == [
        ("SERVICE_STOP_FAILED", "host"),
    ]
    assert [(error.code, error.service) for error in api_service.errors] == [
        ("SERVICE_STOP_FAILED", "hhem")
    ]
    assert api.process.poll() is not None and host.process.poll() is not None
    assert isinstance(api.stopped, ScorerStopped)
    assert api.stopped.worker_exit.confirmed is True
    assert api_service.stopped is False


def test_host_cleanup_keeps_its_advertised_budget_plus_the_workflow_stop_grace() -> None:
    observed: list[int] = []

    class ObservedService(OwnedService):
        def close(self, timeout_ms: int) -> ServiceStopped:
            observed.append(timeout_ms)
            result = super().close(timeout_ms)
            assert isinstance(result, ServiceStopped)
            return result

    pipeline = load_pipeline_settings(REPOSITORY)
    host = ObservedService(
        "host",
        owned_child_command("clean"),
        REPOSITORY,
        StartupPacket(version=WORKFLOW_VERSION, startup_id=REQUEST_ID, context=StartupContext()),
        None,
        pipeline,
    )
    try:
        ready = host.wait_ready(CHILD_STARTUP_MS)
        assert isinstance(ready, HostReady) and host.settings is None
        assert host.stop_grace_ms == pipeline.host_stop_grace_ms
        assert host.forced_stop_ms == pipeline.host_forced_stop_ms
        errors: list[PipelineError] = []
        services = PhaseServices(example_run(), host=host)
        services.close(errors, True, pipeline=pipeline)
        assert observed == [ready.lifecycle_timeout_ms + pipeline.host_stop_grace_ms]
        assert errors == [] and services.host_stopped is True
        assert host.process.poll() == 0
        assert services.scorer_apis == {}
    finally:
        if not host.closed:
            with contextlib.suppress(WorkflowError):
                host.close(pipeline.host_shutdown_timeout_ms)


def test_unieval_cleanup_failure_preserves_the_original_error_and_independent_hhem_exit() -> None:
    api = start_child("api", "unconfirmed_unieval_stop")
    hhem = start_child("api", "raw_inherited_output")
    api.wait_ready(CHILD_STARTUP_MS)
    hhem.wait_ready(CHILD_STARTUP_MS)
    original = WorkflowError("EVALUATION_FAILED", "evaluation", "unieval").error
    errors = [original]
    unieval_service, hhem_service = scorer_service(api), scorer_service(hhem)
    services = PhaseServices(
        example_run(), scorer_apis={"hhem": hhem_service, "unieval": unieval_service}
    )
    services.close(errors, False, pipeline=load_pipeline_settings(REPOSITORY))
    assert errors[0] == original
    assert [(error.phase, error.service) for error in unieval_service.errors] == [
        ("cleanup", "unieval"),
    ]
    assert isinstance(hhem.stopped, ScorerStopped) and isinstance(api.stopped, ScorerStopped)
    assert hhem.stopped.worker_exit.confirmed is True and hhem_service.stopped is True
    assert api.stopped.worker_exit.confirmed is False and unieval_service.stopped is False
    assert hhem_service.errors == []
    assert api.process.poll() is not None
    assert hhem.process.poll() is not None


@pytest.mark.parametrize("failure", ["open", "write"])
def test_native_log_mirror_failure_warns_and_does_not_fail_useful_work(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    directory = tmp_path / "logs"
    if failure == "open":
        directory.write_text("A regular file is not a log directory.", encoding="utf-8")
    logger = NativeLog(directory, example_run(), load_pipeline_settings(REPOSITORY).native_logging)
    if failure == "write":
        assert logger.file is not None and logger.file.stream is not None
        logger.file.stream.close()
    logger.event(NativeDiagnosticData(component="llama", action="ready", level="INFO"))
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
            str(REPOSITORY / "tools" / "summary-eval" / name),
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
    child = start_child("api", "early_exit")
    child.process.wait(timeout=30)
    try:

        async def check() -> None:
            done = asyncio.get_running_loop().create_future()
            done.set_result("A completed result is not a shutdown observation.")
            actual = await guard_work(done, child, load_pipeline_settings(REPOSITORY))
            assert actual == done.result()

        asyncio.run(check())
    finally:
        with pytest.raises(WorkflowError):
            child.close(1000)


def test_exited_child_retains_validated_startup_and_separate_cleanup_cause_codes() -> None:
    child = start_child("host", "coded_startup_failure")
    child.process.wait(timeout=30)
    with pytest.raises(WorkflowError) as original:
        child.wait_ready(CHILD_STARTUP_MS)
    assert original.value.error.code == "STARTUP_FAILED"
    assert original.value.error.source_code == "MACHINE_API_STARTUP_INVALID"
    with pytest.raises(WorkflowError) as cleanup:
        child.close(1000)
    assert cleanup.value.error.code == "SERVICE_STOP_FAILED"
    assert cleanup.value.error.source_code == "MACHINE_EVIDENCE_INVALID"
    assert child.process.returncode == 1
    assert child.stopped is not None
    assert child.stopped.error_code == original.value.error.source_code
