"""Retain real failed-child controls across queue timeout and reader scheduling boundaries."""

import contextlib
import queue
import threading

import pytest
from summary_eval_pipeline.contracts import WORKFLOW_VERSION
from summary_eval_pipeline.control import ServiceControl, StartupPacket
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.phase_services import PhaseServices
from summary_eval_pipeline.services import CONTROL_PACKET_CAPACITY, OwnedService
from summary_eval_pipeline.settings import load_pipeline_settings

from hhem_evaluator.api_settings import load_api_settings
from hhem_evaluator.shared.contracts.service_settings import StartupContext

from .contract_examples import REPOSITORY, REQUEST_ID
from .generation_cases import example_run
from .pipeline_cases import owned_child_command
from .test_pipeline_lifetime import CHILD_STARTUP_MS


def start_scheduled_failure(
    release: threading.Event,
    drained: threading.Event,
) -> OwnedService:
    class ScheduledService(OwnedService):
        def _read_control(self) -> None:
            assert release.wait(30), "The bounded test must release its actual control reader."
            try:
                super()._read_control()
            finally:
                drained.set()

    return ScheduledService(
        "host",
        owned_child_command("coded_startup_failure"),
        REPOSITORY,
        StartupPacket(
            version=WORKFLOW_VERSION,
            startup_id=REQUEST_ID,
            context=StartupContext(),
        ),
        None,
        load_pipeline_settings(REPOSITORY).model_copy(
            update={"host_stop_grace_ms": 500, "host_forced_stop_ms": 1000}
        ),
    )


def test_exit_after_queue_timeout_prioritizes_three_validated_controls_before_fallback() -> None:
    release, drained = threading.Event(), threading.Event()
    child = start_scheduled_failure(release, drained)

    class TimeoutBoundaryQueue(queue.Queue[ServiceControl | None]):
        observed_entries = 0

        def get(
            self,
            block: bool = True,
            timeout: float | None = None,
        ) -> ServiceControl | None:
            try:
                return super().get(block, timeout)
            except queue.Empty:
                if block and timeout is not None:
                    release.set()
                    assert drained.wait(5)
                    self.observed_entries = self.qsize()
                raise

    controls = TimeoutBoundaryQueue(CONTROL_PACKET_CAPACITY)
    child.messages = controls
    try:
        assert child.process.wait(timeout=30) == 1
        with pytest.raises(WorkflowError) as original:
            child.wait_ready(CHILD_STARTUP_MS)
        assert controls.observed_entries == 3
        assert original.value.error.code == "STARTUP_FAILED"
        assert original.value.error.source_code == "MACHINE_API_STARTUP_INVALID"
        errors = [original.value.error]
        services = PhaseServices(example_run(), host=child)
        services.close(
            child.settings,
            load_api_settings(REPOSITORY / "config" / "fastapi-server.json"),
            errors,
            False,
            pipeline=child.manual,
        )
        assert [(error.code, error.source_code) for error in errors] == [
            ("STARTUP_FAILED", "MACHINE_API_STARTUP_INVALID"),
            ("SERVICE_STOP_FAILED", "MACHINE_EVIDENCE_INVALID"),
        ]
        assert child.process.returncode == 1 and services.host_stopped is False
    finally:
        release.set()
        if not child.closed:
            with contextlib.suppress(WorkflowError):
                child.close(1500)


def test_cleanup_retains_original_startup_failure_first_discovered_without_readiness() -> None:
    release, drained = threading.Event(), threading.Event()
    child = start_scheduled_failure(release, drained)
    try:
        assert child.process.wait(timeout=30) == 1
        with pytest.raises(WorkflowError) as observed:
            child.wait_ready(CHILD_STARTUP_MS)
        assert observed.value.error.code == "CHILD_EXITED"
        release.set()
        assert drained.wait(5)
        errors = [observed.value.error]
        services = PhaseServices(example_run(), host=child)
        services.close(
            child.settings,
            load_api_settings(REPOSITORY / "config" / "fastapi-server.json"),
            errors,
            False,
            pipeline=child.manual,
        )
        assert child.ready is None and child.process.returncode == 1
        assert [(error.code, error.source_code) for error in errors] == [
            ("CHILD_EXITED", None),
            ("STARTUP_FAILED", "MACHINE_API_STARTUP_INVALID"),
            ("SERVICE_STOP_FAILED", "MACHINE_EVIDENCE_INVALID"),
        ]
    finally:
        release.set()
        if not child.closed:
            with contextlib.suppress(WorkflowError):
                child.close(1500)
