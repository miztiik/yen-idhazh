"""Prove score retention, pinned resource coverage, input privacy and owned cleanup."""

import asyncio
import json
import math
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from hhem_evaluator.call_local_api import call_local_api
from hhem_evaluator.collect_task_profile import TaskMeasurement
from hhem_evaluator.contracts.base import SCHEMA_VERSION
from hhem_evaluator.contracts.evaluate_request import EvaluateRequest
from hhem_evaluator.contracts.host_profile_reader import (
    ProcessCpuValue,
    TaskIdentity,
)
from hhem_evaluator.contracts.service_health import ServiceHealth
from hhem_evaluator.contracts.service_settings import StartupContext
from hhem_evaluator.contracts.worker_identity import WorkerIdentity
from hhem_evaluator.contracts.workflow_control import StartupPacket
from hhem_evaluator.contracts.workflow_report import ServiceShutdown, WorkflowReport
from hhem_evaluator.fail_manual_evaluation import WorkflowFailure
from hhem_evaluator.load_manual_settings import load_manual_settings
from hhem_evaluator.observe_manual_evaluation import (
    ManualObservation,
    observe_manual_evaluation,
    read_owned_health,
)
from hhem_evaluator.own_services import OwnedService
from hhem_evaluator.report_evaluation import (
    build_report,
    build_resource_evidence,
    render_report,
    write_report,
)

from .contract_examples import CORRELATION_ID, REPOSITORY, REQUEST_ID, example_worker
from .manual_cases import NativeHostPipe, NativeTransports, owned_child_command, prepare_proc
from .replay_predictions import Scenario, read_recordings
from .service_cases import running_service, service_settings


def task_identity() -> TaskIdentity:
    return TaskIdentity(
        pipeline_name="hhem-offline-test",
        task_name="evaluate-supplied-text",
        run_id="recorded-run",
        request_id=REQUEST_ID,
        correlation_id=CORRELATION_ID,
    )


def observed_report(observation: ManualObservation) -> WorkflowReport:
    final = observation.final_health
    resources = build_resource_evidence(
        observation.measurement,
        final.worker if final is not None else None,
        ServiceShutdown(hhem_stopped=None, host_stopped=None, worker_exit_confirmed=None),
    )
    return build_report(observation.evaluation, resources, observation.errors)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("normal", None),
        ("disabled", "configured_off"),
        ("memory_off", "measurement_unavailable"),
        ("missing_memory", "measurement_unavailable"),
        ("owner_exited", "profile_interrupted"),
        ("pid_reused", "profile_interrupted"),
        ("stop_failed", "profile_stop_failed"),
        ("partial", "profile_interrupted"),
        ("partial_and_stop_failed", "profile_stop_failed"),
    ],
)
def test_actual_handlers_preserve_scores_and_explain_resource_coverage(
    tmp_path: Path,
    mode: str,
    expected: str | None,
) -> None:
    async def check() -> None:
        inputs, predictions, _ = read_recordings(REPOSITORY)
        case = inputs.cases[3]
        request = EvaluateRequest(
            source_text=case.source_text,
            summary_text=case.summary_text,
            hhem_full=False,
            request_id=REQUEST_ID,
            correlation_id=CORRELATION_ID,
        )
        manual = load_manual_settings(REPOSITORY)
        pending = mode in ("stop_failed", "partial_and_stop_failed")
        controls: dict[str, bool | int] = {"lifecycle_timeout_ms": 1000}
        if mode == "disabled":
            controls["enabled"] = False
        if mode == "memory_off":
            controls["memory_enabled"] = False
        async with running_service(scenarios=(Scenario(actions=("hold",)),)) as service:
            health = service.app.state.controller.health()
            worker = health.worker
            assert worker is not None and worker.start_ticks is not None
            prepare_proc(tmp_path, worker)
            if mode == "missing_memory":
                (tmp_path / str(worker.pid) / "status").unlink()
            host = NativeHostPipe(
                tmp_path,
                task_profile=controls,
                report_mode="pending" if pending else "normal",
            )
            observation = ManualObservation()

            async def close_observation() -> None:
                prepare_proc(tmp_path, worker, closing=True, write_status=mode != "missing_memory")
                if mode in ("owner_exited", "partial", "partial_and_stop_failed"):
                    if mode != "owner_exited":
                        assert service.worker.exit_confirmed
                        assert service.worker.worker is None
                    (tmp_path / str(worker.pid) / "stat").unlink()
                elif mode == "pid_reused":
                    path = tmp_path / str(worker.pid) / "stat"
                    path.write_text(
                        path.read_text().replace(
                            worker.start_ticks or "", str(int(worker.start_ticks or "0") + 1)
                        ),
                        encoding="utf-8",
                    )

            transport = NativeTransports(
                httpx.ASGITransport(app=service.app), host, close_observation
            )
            try:
                async with httpx.AsyncClient(
                    transport=transport,
                    trust_env=False,
                    follow_redirects=False,
                ) as client:
                    if mode in ("partial", "partial_and_stop_failed"):
                        service.log.fail_terminal = True
                    run = asyncio.create_task(
                        observe_manual_evaluation(
                            client,
                            "http://127.0.0.1:3010",
                            "http://127.0.0.1:3011",
                            health,
                            task_identity(),
                            request,
                            service.app.state.controller.settings,
                            manual,
                            5000,
                            observation,
                        )
                    )
                    assert (await service.worker.handshake())["phase"] == "loading"
                    assert (await service.worker.handshake())["phase"] == "prediction"
                    await service.worker.release_prediction()
                    await run
                report = observed_report(observation)
                assert report.evaluation is not None
                assert report.evaluation.hhem == predictions.cases[3].score
                assert report.evaluation.hhem_full is None
                assert report.evaluation.effective_settings is not None
                assert report.evaluation.effective_settings.hhem_full is False
                assert (
                    sum(
                        event.operation == "primary" and event.phase == "started"
                        for event in service.log.events
                    )
                    == 1
                )
                assert not any(event.operation == "full" for event in service.log.events)
                assert report.resources.initial_worker == worker
                if mode in ("partial", "partial_and_stop_failed"):
                    assert report.resources.final_worker is None
                else:
                    assert report.resources.final_worker == worker
                assert report.resources.reason == expected
                if mode == "normal":
                    assert report.status == "complete"
                    profile = report.resources.profile
                    assert profile is not None
                    measured = profile.processes.worker
                    assert measured.sampled_rss_max_kb == 700
                    assert measured.cpu.value is not None
                    assert measured.cpu.value.cpu_time_ms == 3000
                    assert math.isclose(
                        measured.cpu.value.percent_one_core,
                        measured.cpu.value.cpu_time_ms / measured.cpu_interval_ms * 100,
                    )
                    missing_identity = build_resource_evidence(
                        observation.measurement,
                        None,
                        report.resources.shutdown,
                    )
                    assert missing_identity.status == "incomplete"
                    assert missing_identity.reason == "measurement_unavailable"
                    retained = build_report(report.evaluation, missing_identity, [])
                    assert retained.evaluation == report.evaluation
                    assert retained.status == "partial"
                if mode == "disabled":
                    assert report.resources.profile is None and host.requests == 1
                if mode in ("memory_off", "missing_memory"):
                    profile = report.resources.profile
                    assert profile is not None
                    assert profile.processes.worker.sampled_rss_max_kb is None
                    assert profile.processes.worker.unavailable["sampled_rss_max_kb"] == (
                        "configured_off" if mode == "memory_off" else "missing_file"
                    )
                if mode in ("owner_exited", "pid_reused"):
                    profile = report.resources.profile
                    assert profile is not None and profile.outcome == "cancelled"
                    assert profile.end_reason == mode
                if mode in ("partial", "partial_and_stop_failed"):
                    assert report.evaluation.status == "partial"
                    assert report.evaluation.terminal_event_id is None
                    assert any(
                        error.code == "EVALUATION_FAILED"
                        and error.http_status == 500
                        and error.phase == "evaluation"
                        for error in report.errors
                    )
                    if not pending:
                        assert report.resources.profile is not None
                        assert report.resources.profile.end_reason == "owner_exited"
                        assert report.resources.profile.outcome == "cancelled"
                if pending:
                    assert any(
                        error.phase == "cleanup" and error.http_status == 500
                        for error in report.errors
                    )
                directory = tmp_path / "report"
                write_report(report, directory)
                saved = WorkflowReport.model_validate_json((directory / "report.json").read_bytes())
                assert saved == report
                rendered = render_report(report)
                serialized = saved.model_dump_json()
                for text in (
                    case.source_text,
                    case.summary_text,
                    "PrivateSourceCanary",
                    "PrivateSummaryCanary",
                ):
                    assert text not in serialized and text not in rendered
                    assert text not in service.log.getvalue()
                assert '"samples"' not in serialized and '"cache_counters"' not in serialized
                profile = report.resources.profile
                if profile is not None:
                    rss = profile.processes.worker.sampled_rss_max_kb
                    if rss is not None:
                        assert f"{rss / 1024:.3f} MiB ({rss} KiB)" in rendered
                if mode in ("partial", "partial_and_stop_failed"):
                    assert service.worker.exit_confirmed
                    assert service.worker.last_exit == (worker.generation, worker.pid)
                else:
                    assert service.worker.process is not None and service.worker.process.is_alive()
            finally:
                closed = await asyncio.to_thread(host.close)
                assert closed["clean"] is (not pending)
                assert host.process.poll() is not None

    asyncio.run(check())


def test_actual_worker_replacement_cannot_be_complete_resource_coverage(tmp_path: Path) -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        async with running_service(scenarios=(Scenario(actions=("crash",)), Scenario())) as service:
            controller = service.app.state.controller
            health = controller.health()
            worker = health.worker
            assert worker is not None
            prepare_proc(tmp_path, worker)
            host = NativeHostPipe(tmp_path)

            async def replacement() -> None:
                assert controller.recovery_task is not None
                await controller.recovery_task
                assert controller.loading_task is not None
                await controller.loading_task
                assert controller.health().status == "ready"
                (tmp_path / str(worker.pid) / "stat").unlink()

            observation = ManualObservation()
            try:
                async with httpx.AsyncClient(
                    transport=NativeTransports(
                        httpx.ASGITransport(app=service.app), host, replacement
                    ),
                    trust_env=False,
                    follow_redirects=False,
                ) as client:
                    await observe_manual_evaluation(
                        client,
                        "http://127.0.0.1:3010",
                        "http://127.0.0.1:3011",
                        health,
                        task_identity(),
                        EvaluateRequest(
                            source_text=case.source_text,
                            summary_text=case.summary_text,
                            hhem_full=False,
                            request_id=REQUEST_ID,
                            correlation_id=CORRELATION_ID,
                        ),
                        controller.settings,
                        load_manual_settings(REPOSITORY),
                        5000,
                        observation,
                    )
                report = observed_report(observation)
                assert report.resources.status == "incomplete"
                assert report.resources.reason == "worker_replaced"
                assert report.resources.initial_worker == worker
                assert report.resources.final_worker is not None
                assert report.resources.final_worker.generation == worker.generation + 1
                assert report.resources.final_worker.pid != worker.pid
                assert report.resources.profile is not None
                assert report.resources.profile.end_reason == "owner_exited"
                assert host.requests == 2, (
                    "A replacement must not retarget or start another profile"
                )
            finally:
                assert (await asyncio.to_thread(host.close))["clean"] is True

    asyncio.run(check())


def test_bad_readiness_identity_is_rejected_against_the_real_health_handler() -> None:
    async def check() -> None:
        async with running_service() as service:
            with pytest.raises(WorkflowFailure) as error:
                await read_owned_health(
                    service.client,
                    "http://127.0.0.1:3010",
                    REQUEST_ID,
                    service.app.state.controller.settings,
                    load_manual_settings(REPOSITORY),
                )
            assert error.value.error.code == "STARTUP_IDENTITY_MISMATCH"
            assert not any(event.operation == "primary" for event in service.log.events)

    asyncio.run(check())


def test_actual_health_response_enforces_the_exact_response_byte_allowance() -> None:
    async def check() -> None:
        async with running_service() as service:
            url = "http://127.0.0.1:3010/api/2026-11-02/health"
            body = (await service.client.get(url)).content
            manual = load_manual_settings(REPOSITORY)
            exact = manual.model_copy(update={"max_response_bytes": len(body)})
            status, health = await call_local_api(
                service.client,
                "GET",
                url,
                ServiceHealth,
                exact,
                5000,
                service="hhem",
                phase="health",
            )
            assert status == 200 and health.worker == service.worker.worker
            overflow = manual.model_copy(update={"max_response_bytes": len(body) - 1})
            with pytest.raises(WorkflowFailure) as failure:
                await call_local_api(
                    service.client,
                    "GET",
                    url,
                    ServiceHealth,
                    overflow,
                    5000,
                    service="hhem",
                    phase="health",
                )
            assert failure.value.error.code == "RESPONSE_TOO_LARGE"
            assert failure.value.error.http_status == 200
            assert not any(event.operation == "primary" for event in service.log.events)

    asyncio.run(check())


@pytest.mark.parametrize("reason", ["pin_unavailable", "native_unavailable"])
def test_unavailable_profiling_does_not_invent_zeroes(tmp_path: Path, reason: str) -> None:
    async def check() -> None:
        worker = example_worker()
        if reason == "pin_unavailable":
            worker = WorkerIdentity(
                generation=worker.generation,
                pid=worker.pid,
                start_ticks=None,
                pin_unavailable_reason="unsupported_platform",
            )
        prepare_proc(tmp_path, worker)
        host = NativeHostPipe(tmp_path, platform="unsupported")
        measurement = TaskMeasurement(worker, task_identity())
        try:
            async with httpx.AsyncClient(
                transport=NativeTransports(None, host),
                trust_env=False,
                follow_redirects=False,
            ) as client:
                failure = await measurement.start(
                    client, "http://127.0.0.1:3011", load_manual_settings(REPOSITORY), 5000
                )
            assert measurement.profile is None and measurement.started is None
            if reason == "pin_unavailable":
                assert failure is None and host.requests == 0
                assert measurement.reason == "pin_unavailable"
            else:
                assert failure is not None and failure.http_status == 409
                assert measurement.reason == "profile_start_failed"
        finally:
            assert (await asyncio.to_thread(host.close))["clean"] is True

    asyncio.run(check())


def test_parent_pipe_eof_closes_the_actual_native_collector(tmp_path: Path) -> None:
    async def check() -> None:
        worker = example_worker()
        prepare_proc(tmp_path, worker)
        host = NativeHostPipe(tmp_path)
        identity = task_identity()
        response = await asyncio.to_thread(
            host.request,
            "/api/2026-10-24/start-task-profile",
            json.dumps(
                {
                    "identity": identity.model_dump(mode="json"),
                    "target": {"pid": worker.pid, "start_ticks": worker.start_ticks},
                }
            ).encode(),
        )
        assert response["status"] == 200
        assert (await asyncio.to_thread(host.close)) == {
            "kind": "closed",
            "clean": True,
            "end_reason": "service_stopped",
            "outcome": "cancelled",
        }
        assert host.process.poll() == 0
        assert (tmp_path / str(worker.pid) / "stat").is_file()

    asyncio.run(check())


@pytest.mark.parametrize("mode", ["clean", "mismatch", "early_exit", "blocked_close"])
def test_only_owned_children_are_joined_even_when_readiness_or_close_fails(mode: str) -> None:
    settings = service_settings(
        worker={
            "stop_grace_ms": 500,
            "forced_stop_ms": 1000,
            "shutdown_timeout_ms": 1500,
        }
    )
    child = OwnedService(
        "host",
        owned_child_command(mode),
        REPOSITORY,
        StartupPacket(version=SCHEMA_VERSION, startup_id=REQUEST_ID, context=StartupContext()),
        settings,
        load_manual_settings(REPOSITORY),
    )
    try:
        if mode in ("mismatch", "early_exit"):
            with pytest.raises(WorkflowFailure) as failure:
                child.wait_ready(10000)
            assert failure.value.error.code == (
                "STARTUP_IDENTITY_MISMATCH" if mode == "mismatch" else "CHILD_EXITED"
            )
        else:
            ready = child.wait_ready(10000)
            assert ready.pid == child.process.pid and child.process.poll() is None
    finally:
        if mode in ("early_exit", "blocked_close"):
            with pytest.raises(WorkflowFailure) as close:
                child.close(100 if mode == "blocked_close" else 1500)
            assert close.value.error.phase == "cleanup"
        else:
            assert child.close(1500).clean
        assert child.process.poll() is not None


def test_one_core_cpu_percent_is_not_capped_or_coerced() -> None:
    value = ProcessCpuValue(cpu_time_ms=3000, percent_one_core=300)
    assert value.percent_one_core == 300
    for invalid in (True, "300", -1, float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            ProcessCpuValue.model_validate({"cpu_time_ms": 3000, "percent_one_core": invalid})


@pytest.mark.parametrize("blocked", [False, True])
def test_actual_api_parent_watcher_closes_or_exits_its_own_child(blocked: bool) -> None:
    settings = service_settings()
    mode = "parent_loss_blocked" if blocked else "parent_loss"
    child = OwnedService(
        "host",
        owned_child_command(mode),
        REPOSITORY,
        StartupPacket(version=SCHEMA_VERSION, startup_id=REQUEST_ID, context=StartupContext()),
        settings,
        load_manual_settings(REPOSITORY),
    )
    child.wait_ready(10000)
    assert child.process.stdin is not None
    child.process.stdin.close()
    child.process.wait(timeout=5)
    if blocked:
        with pytest.raises(WorkflowFailure):
            child.close(1000)
        assert child.process.returncode == 1
    else:
        assert child.close(1000).clean
        assert child.process.returncode == 0


def test_invalid_child_diagnostics_are_failed_without_forwarding_raw_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    child = OwnedService(
        "hhem",
        owned_child_command("invalid_event"),
        REPOSITORY,
        StartupPacket(version=SCHEMA_VERSION, startup_id=REQUEST_ID, context=StartupContext()),
        service_settings(),
        load_manual_settings(REPOSITORY),
    )
    try:
        with pytest.raises(WorkflowFailure) as failure:
            child.wait_ready(10000)
            assert child.events_failed.wait(5)
            child.check_alive()
        assert failure.value.error.code == "EVENT_STREAM_FAILED"
    finally:
        with pytest.raises(WorkflowFailure):
            child.close(1500)
    assert child.process.poll() is not None
    output = capsys.readouterr()
    assert "PrivateRawChildCanary" not in output.out + output.err
