"""Retain real failed-child controls across queue timeout and reader scheduling boundaries."""

import contextlib
import json
import queue
import threading

import pytest
from local_api_host.propagate_trace_context import create_child_operation
from pydantic import ValidationError
from summary_eval_pipeline.contracts import WORKFLOW_VERSION
from summary_eval_pipeline.control import (
    MACHINE_STARTUP_VERSION,
    MachineStartup,
    MachineStartupPacket,
    ServiceControl,
    StartupPacket,
    encode_control_packet,
)
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.phase_services import PhaseServices
from summary_eval_pipeline.scorer_control import (
    SCORER_CONTROL_VERSION,
    ScorerControl,
    ScorerReady,
    ScorerStartup,
    ScorerStartupPacket,
)
from summary_eval_pipeline.services import CONTROL_PACKET_CAPACITY, OwnedService
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator.shared.bound_operation_metadata import maximum_worker_operation_metadata
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator_cases.contract_examples import REPOSITORY, REQUEST_ID

from summary_eval_tests.generation_cases import example_run
from summary_eval_tests.pipeline_cases import owned_child_command
from summary_eval_tests.test_pipeline_lifetime import CHILD_STARTUP_MS


def full_startup() -> StartupPacket:
    run = example_run()
    return StartupPacket(
        version=WORKFLOW_VERSION, startup_id=REQUEST_ID, context=StartupContext(
            run_id=run.run_id, pipeline_name="pipeline", task_name="evaluation"
        ),
        git_sha=run.git_sha, attempt=run.attempt, run=run,
        request_id=REQUEST_ID, correlation_id=REQUEST_ID,
    )


def test_private_families_retain_legacy_absence_without_changing_global_versions() -> None:
    flat = full_startup()
    launch = maximum_worker_operation_metadata()
    machine = MachineStartupPacket(
        version=MACHINE_STARTUP_VERSION, startup=flat, operation_metadata=launch
    )
    scorer = ScorerStartupPacket(
        version=SCORER_CONTROL_VERSION, scorer="hhem", startup=flat, operation_metadata=launch
    )
    for wrapper in (machine, scorer):
        assert wrapper.version == "2026-11-08"
        assert wrapper.startup == flat
        assert wrapper.model_json_schema()["version"] == wrapper.version
    assert flat.version == WORKFLOW_VERSION == "2026-11-05"
    assert MachineStartup.model_validate_json(flat.model_dump_json()).root == flat
    assert MachineStartup.model_validate_json(machine.model_dump_json()).root == machine
    previous = scorer.model_dump(mode="json", exclude={"operation_metadata"})
    previous["version"] = "2026-11-07"
    saved = ScorerStartup.model_validate_json(json.dumps(previous)).root
    assert saved.model_dump(mode="json") == previous
    assert "operation_metadata" not in saved.model_dump(mode="json")


@pytest.mark.parametrize("kind", ["ready", "failed", "stopped"])
def test_previous_scorer_controls_remain_untraced_and_current_controls_require_both_operations(
    kind: str,
) -> None:
    launch = maximum_worker_operation_metadata()
    operation = create_child_operation(launch)
    current: dict[str, object] = {
        "version": SCORER_CONTROL_VERSION, "kind": kind, "service": "api",
        "scorer": "hhem", "startup_id": REQUEST_ID,
        "launch_operation_metadata": launch.model_dump(mode="json"),
        "operation_metadata": operation.model_dump(mode="json"),
    }
    if kind == "failed":
        current.update({"pid": 1, "error_code": None, "http_status": None})
    else:
        current.update({
            "process": {"pid": 1, "start_ticks": "1", "pin_unavailable_reason": None},
            "log_file": None, "log_available": False,
        })
        if kind == "ready":
            current["service_instance_id"] = REQUEST_ID
        else:
            current.update({
                "clean": True, "worker_exit": {"pid": None, "exit_code": None, "confirmed": None},
                "error_code": None, "cleanup_error_code": None, "http_status": None,
            })
    saved = ScorerControl.model_validate_json(json.dumps(current)).root
    assert saved.model_dump(mode="json") == current
    previous = {
        key: value for key, value in current.items()
        if key not in ("operation_metadata", "launch_operation_metadata")
    }
    previous["version"] = "2026-11-07"
    old = ScorerControl.model_validate_json(json.dumps(previous)).root
    assert old.model_dump(mode="json") == previous
    for removed in ("operation_metadata", "launch_operation_metadata"):
        with pytest.raises(ValidationError):
            ScorerControl.model_validate_json(json.dumps({
                key: value for key, value in current.items() if key != removed
            }))
    with pytest.raises(ValidationError):
        ScorerControl.model_validate_json(json.dumps({**current, "version": "2026-11-09"}))
    with pytest.raises(ValidationError):
        ScorerControl.model_validate_json(json.dumps({**current, "version": "2026-11-07"}))


@pytest.mark.parametrize("fault", ["parent", "trace", "state", "span", "links"])
def test_current_service_metadata_cannot_cross_its_launch_operation(fault: str) -> None:
    launch = maximum_worker_operation_metadata()
    operation = create_child_operation(launch)
    metadata = operation.model_dump(mode="json")
    changes: dict[str, object] = {
        "parent": {"parentSpanId": "a" * 16},
        "trace": {"traceId": "a" * 32},
        "state": {"traceState": "other=value"},
        "span": {"spanId": launch.span_id},
        "links": {"links": [{"traceId": launch.trace_id, "spanId": launch.span_id}]},
    }
    patch = changes[fault]
    assert isinstance(patch, dict)
    with pytest.raises(ValidationError):
        ScorerReady.model_validate_json(json.dumps({
            "version": SCORER_CONTROL_VERSION, "kind": "ready", "service": "api",
            "scorer": "hhem", "startup_id": REQUEST_ID,
            "process": {"pid": 1, "start_ticks": "1", "pin_unavailable_reason": None},
            "service_instance_id": REQUEST_ID,
            "log_file": None, "log_available": False,
            "launch_operation_metadata": launch.model_dump(mode="json"),
            "operation_metadata": {**metadata, **patch},
        }))


def test_complete_private_packets_include_native_metadata_escaping_and_jsonl_newline() -> None:
    startup = full_startup()
    launch = maximum_worker_operation_metadata()
    packets = (
        MachineStartupPacket(
            version=MACHINE_STARTUP_VERSION, startup=startup, operation_metadata=launch
        ),
        ScorerStartupPacket(
            version=SCORER_CONTROL_VERSION, scorer="hhem", startup=startup,
            operation_metadata=launch,
        ),
        ScorerReady(
            version=SCORER_CONTROL_VERSION, kind="ready", service="api", scorer="hhem",
            startup_id=startup.startup_id,
            process=ProcessIdentity(pid=1, start_ticks="1", pin_unavailable_reason=None),
            service_instance_id=REQUEST_ID, log_file=None, log_available=False,
            launch_operation_metadata=launch, operation_metadata=create_child_operation(launch),
        ),
    )
    configured_cap = load_pipeline_settings(REPOSITORY).control_max_bytes
    for packet in packets:
        line = packet.model_dump_json().encode("utf-8") + b"\n"
        assert b"\\\\" in line and b'"traceState"' in line and b'"links"' in line
        assert encode_control_packet(packet, len(line)) == line
        assert len(line) <= configured_cap
        assert encode_control_packet(packet, configured_cap) == line
        with pytest.raises(ValueError, match="complete private packet"):
            encode_control_packet(packet, len(line) - 1)


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

    class TimeoutBoundaryQueue(queue.Queue[ServiceControl | ScorerControl | None]):
        observed_entries = 0

        def get(
            self,
            block: bool = True,
            timeout: float | None = None,
        ) -> ServiceControl | ScorerControl | None:
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
        services.close(errors, False, pipeline=child.manual)
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
        services.close(errors, False, pipeline=child.manual)
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
