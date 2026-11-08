"""Do real scorer calls and owned lifetimes retain their issued evaluation operations?"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest
from local_api_host.propagate_trace_context import (
    OperationMetadata,
    create_child_operation,
    create_root_operation,
    write_trace_context,
)
from pydantic import ValidationError
from summary_eval_pipeline.contracts import WORKFLOW_VERSION, PipelineError, text_sha256
from summary_eval_pipeline.control import StartupPacket
from summary_eval_pipeline.evaluate_pair import EvaluatorOutcomes, evaluate_pair
from summary_eval_pipeline.evaluation import bind_evaluations, evaluate, evaluate_unieval
from summary_eval_pipeline.scorer_control import (
    SCORER_CONTROL_VERSION,
    ScorerReady,
    ScorerStartupPacket,
    ScorerStopped,
)
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_eval_pipeline.storage import write_result
from summary_eval_pipeline.trace_context import ResponseTraceObservation, read_response_trace
from summary_evaluator.hhem.contracts.evaluation_event import EvaluationEvent
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.worker_message import ScoreWindow, WindowOutcome, WorkerReply
from summary_evaluator.serve_http.contracts.server_event import ServerEvent
from summary_evaluator.shared.contracts.api_paths import EVALUATE_PATH
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    RequestPacket,
    UnievalCommand,
    UnievalReply,
    validate_request_reply,
)
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH
from summary_evaluator_cases.contract_examples import REPOSITORY, REQUEST_ID
from summary_evaluator_cases.service_cases import service_settings
from summary_evaluator_cases.unieval_cases import (
    UnievalScenario,
    read_unieval_inputs,
    unieval_settings,
)

from summary_eval_tests.scorer_caller_cases import running_scorers
from summary_eval_tests.test_generation_handoff import generation_phase
from summary_eval_tests.test_pipeline_lifetime import CHILD_STARTUP_MS
from summary_eval_tests.test_scorer_api_isolation import read_observation, start_scorer


def test_scorer_launch_retains_required_native_operation_without_changing_flat_startup() -> None:
    phase = create_root_operation(trace_state="first=value,second=other")
    launch = create_child_operation(phase)
    startup = StartupPacket(
        version=WORKFLOW_VERSION, startup_id=REQUEST_ID, context=StartupContext()
    )
    value = {
        "version": SCORER_CONTROL_VERSION,
        "scorer": "hhem",
        "startup": startup.model_dump(mode="json"),
        "operation_metadata": launch.model_dump(mode="json"),
    }
    packet = ScorerStartupPacket.model_validate_json(json.dumps(value))
    assert packet.operation_metadata == launch
    assert packet.startup == startup
    assert "operation_metadata" not in packet.startup.model_dump(mode="json")
    del value["operation_metadata"]
    with pytest.raises(ValidationError):
        ScorerStartupPacket.model_validate_json(json.dumps(value))


@pytest.mark.parametrize("fault", ["missing", "invalid", "orphan", "state", "duplicate"])
def test_response_observation_uses_the_shared_optional_carrier_policy(fault: str) -> None:
    caller = create_child_operation(create_root_operation(trace_state="first=value"))
    remote = create_child_operation(caller)
    headers = httpx.Headers(write_trace_context(remote))
    if fault == "missing":
        headers = httpx.Headers()
    elif fault == "invalid":
        headers["traceparent"] = "PrivateResponseTraceCanary"
    elif fault == "orphan":
        del headers["traceparent"]
    elif fault == "state":
        headers["tracestate"] = "PrivateResponseTraceCanary"
    else:
        headers = httpx.Headers([
            ("traceparent", write_trace_context(remote)["traceparent"]),
            ("traceparent", write_trace_context(caller)["traceparent"]),
        ])
    observed = read_response_trace(headers)
    if fault == "state":
        assert isinstance(observed, OperationMetadata)
        assert observed.trace_id == remote.trace_id and observed.span_id == remote.span_id
        assert observed.trace_state is None and observed.parent_span_id is None
        assert observed.links == ()
    else:
        assert observed == ("missing" if fault == "missing" else "invalid")
    assert caller.parent_span_id is not None and caller.span_id != remote.span_id


def test_valid_remote_headers_never_invent_a_parent_or_replace_the_caller() -> None:
    caller = create_child_operation(create_root_operation(trace_state="first=value,second=other"))
    remote = create_child_operation(caller)
    before = caller.model_dump(mode="json")
    observed = read_response_trace(httpx.Headers(write_trace_context(remote)))
    assert isinstance(observed, OperationMetadata)
    assert observed.span_id == remote.span_id and observed.span_id != caller.span_id
    assert observed.trace_id == caller.trace_id and observed.trace_state == caller.trace_state
    assert observed.parent_span_id is None and observed.links == ()
    assert caller.model_dump(mode="json") == before


def test_interleaved_equal_correlation_attempts_retain_real_receiving_and_worker_ancestry() -> None:
    async def check() -> None:
        inputs, prepared, receipt, previous = generation_phase()
        requests = bind_evaluations(
            prepared, inputs, receipt, previous,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        phases = (
            create_root_operation(trace_state="first=one,second=left"),
            create_root_operation(trace_state="first=two,second=right"),
        )
        hhem = service_settings()
        _, unieval = unieval_settings()
        outcomes = (EvaluatorOutcomes(), EvaluatorOutcomes())
        errors: tuple[list[PipelineError], list[PipelineError]] = ([], [])
        async with running_scorers(hhem, selected_unieval=unieval) as case:
            await asyncio.gather(*(
                evaluate_pair(
                    case.client, requests, *case.apis, hhem, unieval,
                    load_pipeline_settings(REPOSITORY), result, failures, lambda: None,
                    operation_metadata=phase,
                )
                for phase, result, failures in zip(phases, outcomes, errors, strict=True)
            ))
            receiving = {operation.span_id: operation for operation in case.transport.receiving}
            calls = []
            for phase, result, failures in zip(phases, outcomes, errors, strict=True):
                for caller, observed in (
                    (result.hhem_operation, result.hhem_trace),
                    (result.unieval_operation, result.unieval_trace),
                ):
                    assert isinstance(caller, OperationMetadata)
                    assert isinstance(observed, OperationMetadata)
                    assert caller.trace_id == phase.trace_id
                    assert caller.parent_span_id == phase.span_id
                    actual = receiving[observed.span_id]
                    assert actual.parent_span_id == caller.span_id
                    assert actual.span_id != caller.span_id
                    assert actual.trace_state == phase.trace_state == observed.trace_state
                    assert observed.parent_span_id is None
                    calls.append(caller.span_id)
                assert result.hhem is not None and result.hhem.status == "complete"
                assert result.unieval is not None
                assert result.hhem.request_id == result.unieval.request_id == requests[0].request_id
                assert result.hhem.correlation_id == requests[0].correlation_id
                expected = []
                for path, contract, retained, scorer in (
                    (EVALUATE_PATH, EvaluationResult, result.hhem, "hhem"),
                    (UNIEVAL_PATH, UnievalResult, result.unieval, "unieval"),
                ):
                    response_observation = next(
                        response for response in case.transport.responses
                        if response.request.url.path == path
                        and isinstance(
                            request_operation := read_response_trace(response.request.headers),
                            OperationMetadata,
                        )
                        and request_operation.trace_id == phase.trace_id
                    )
                    native = contract.model_validate_json(response_observation.body)
                    assert retained == native
                    if response_observation.status != 200 or native.status != "complete":
                        expected.append(("EVALUATION_FAILED", scorer))
                assert sorted((error.code, error.service) for error in failures) == sorted(expected)
            assert len(set(calls)) == len(calls)
            native_operations = {
                (operation.trace_id, operation.span_id): operation
                for observer in case.traces for _, operation in observer.records
            }
            for envelope, operation in case.traces[0].records:
                if (
                    isinstance(envelope.data, EvaluationEvent)
                    and envelope.data.operation == "request"
                ):
                    assert operation == receiving[operation.span_id]
                    assert envelope.traceparent == write_trace_context(operation)["traceparent"]
            commands = [
                ScoreWindow.model_validate_json(encoded) for encoded in case.hhem.worker.commands
            ]
            for command in commands:
                assert command.operation_metadata.parent_span_id is not None
                enclosing = native_operations[
                    (command.operation_metadata.trace_id, command.operation_metadata.parent_span_id)
                ]
                assert enclosing.parent_span_id in receiving
            for encoded in case.hhem.worker.replies:
                reply = WorkerReply.model_validate_json(encoded).root
                if isinstance(reply, WindowOutcome):
                    assert any(
                        reply.operation_metadata == command.operation_metadata
                        for command in commands
                    )
            unieval_commands = [
                UnievalCommand.model_validate_json(encoded)
                for encoded in case.unieval_worker.commands
            ]
            assert {command.operation_metadata.trace_id for command in unieval_commands} == {
                phase.trace_id for phase in phases
            }
            for unieval_command in unieval_commands:
                assert unieval_command.operation_metadata.parent_span_id in receiving
            for encoded in case.unieval_worker.replies:
                unieval_reply = UnievalReply.model_validate_json(encoded).root
                if isinstance(unieval_reply, RequestPacket):
                    issued = next(
                        command for command in unieval_commands
                        if command.execution_id == unieval_reply.execution_id
                    )
                    validate_request_reply(issued, unieval_reply)
                    assert unieval_reply.operation_metadata == issued.operation_metadata

    asyncio.run(check())


@pytest.mark.parametrize("fault", ["missing", "invalid", "state", "native"])
def test_sibling_trace_or_native_failure_cannot_erase_actual_scores_or_saved_native_results(
    tmp_path: Path, fault: str,
) -> None:
    async def check() -> None:
        inputs, prepared, receipt, previous = generation_phase()
        requests = bind_evaluations(
            prepared, inputs, receipt, previous,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        hhem = service_settings()
        _, unieval = unieval_settings()
        outcomes = EvaluatorOutcomes()
        errors: list[PipelineError] = []
        phase = create_root_operation(trace_state="first=value")
        async with running_scorers(
            hhem, selected_unieval=unieval,
            unieval_scenario=UnievalScenario(fail_at=0) if fault == "native" else None,
        ) as case:
            if fault != "native":
                case.transport.trace_faults[UNIEVAL_PATH] = fault

            def retain() -> None:
                if outcomes.hhem is not None:
                    write_result(tmp_path / "hhem.json", outcomes.hhem)
                if outcomes.unieval is not None:
                    write_result(tmp_path / "unieval.json", outcomes.unieval)

            await evaluate_pair(
                case.client, requests, *case.apis, hhem, unieval,
                load_pipeline_settings(REPOSITORY), outcomes, errors, retain,
                operation_metadata=phase,
            )
            assert outcomes.hhem is not None and outcomes.hhem.status == "complete"
            assert outcomes.unieval is not None
            assert isinstance(outcomes.hhem_trace, OperationMetadata)
            if fault in ("missing", "invalid"):
                assert outcomes.unieval_trace == fault
            else:
                assert isinstance(outcomes.unieval_trace, OperationMetadata)
                assert outcomes.unieval_trace.trace_state == (
                    None if fault == "state" else phase.trace_state
                )
            expected = []
            for path, contract, result, scorer in (
                (EVALUATE_PATH, EvaluationResult, outcomes.hhem, "hhem"),
                (UNIEVAL_PATH, UnievalResult, outcomes.unieval, "unieval"),
            ):
                actual = next(
                    response for response in case.transport.responses
                    if response.request.url.path == path
                )
                native = contract.model_validate_json(actual.body)
                assert result == native
                if actual.status != 200 or native.status != "complete":
                    expected.append(("EVALUATION_FAILED", scorer))
            assert (tmp_path / "hhem.json").read_bytes() == outcomes.hhem.model_dump_json().encode()
            assert (tmp_path / "unieval.json").read_bytes() == (
                outcomes.unieval.model_dump_json().encode()
            )
            assert [(error.code, error.service) for error in errors] == expected

    asyncio.run(check())


@pytest.mark.parametrize(
    ("fault", "fail_at"), [("missing", None), ("invalid", 0), ("state", None)]
)
def test_recorded_unieval_complete_and_partial_results_survive_response_trace_failures(
    fault: str, fail_at: int | None,
) -> None:
    async def check() -> None:
        request = read_unieval_inputs().cases[0].request
        _, settings = unieval_settings()
        phase = create_root_operation(trace_state="first=value")
        observations: list[ResponseTraceObservation] = []
        async with running_scorers(
            selected_unieval=settings, unieval_scenario=UnievalScenario(fail_at=fail_at),
        ) as case:
            case.transport.trace_faults[UNIEVAL_PATH] = fault
            status, result = await evaluate_unieval(
                case.client, case.apis[1].origin, request, settings,
                load_pipeline_settings(REPOSITORY),
                operation_metadata=create_child_operation(phase), observe_trace=observations.append,
            )
            actual = next(
                response for response in case.transport.responses
                if response.request.url.path == UNIEVAL_PATH
            )
            assert result == UnievalResult.model_validate_json(actual.body)
            assert status == actual.status
            if fail_at is None:
                assert result.status == "complete" and status == 200
            else:
                assert result.status == "partial" and result.errors
                assert any(value is not None for value in result.scores.model_dump().values())
            if fault in ("missing", "invalid"):
                assert observations == [fault]
            else:
                assert isinstance(observations[0], OperationMetadata)
                assert observations[0].trace_id == phase.trace_id
                assert observations[0].trace_state is None

    asyncio.run(check())


def test_failed_response_observer_keeps_the_native_result_and_reports_only_a_fixed_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def check() -> None:
        inputs, prepared, receipt, previous = generation_phase()
        request, _ = bind_evaluations(
            prepared, inputs, receipt, previous,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        settings = service_settings()

        def failed_observer(_value: object) -> None:
            raise RuntimeError("PrivateTraceObserverCanary")

        async with running_scorers(settings) as case:
            status, result = await evaluate(
                case.client, case.apis[0].origin, request, settings,
                load_pipeline_settings(REPOSITORY),
                operation_metadata=create_child_operation(create_root_operation()),
                observe_trace=failed_observer,
            )
            assert status == 200 and result.status == "complete"
            assert "scorer_trace_observation_failed" in caplog.text
            assert "PrivateTraceObserverCanary" not in caplog.text
            assert inputs.source_text not in caplog.text

    asyncio.run(check())


@pytest.mark.skipif(
    sys.platform != "linux", reason="Native API start-pin and lifespan proof is Linux"
)
@pytest.mark.parametrize("scorer", ["hhem", "unieval"])
def test_owned_launch_is_really_adopted_by_service_controller_load_and_native_calls(
    scorer: str, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    phase = create_root_operation(trace_state="first=value,second=other")
    assert scorer in ("hhem", "unieval")
    child = start_scorer(
        "hhem" if scorer == "hhem" else "unieval", tmp_path, operation_metadata=phase
    )
    try:
        ready = child.wait_ready(CHILD_STARTUP_MS)
        assert isinstance(ready, ScorerReady)
        assert isinstance(child.packet, ScorerStartupPacket)
        launch = child.packet.operation_metadata
        assert launch.parent_span_id == phase.span_id
        assert ready.launch_operation_metadata == launch
        assert ready.operation_metadata.parent_span_id == launch.span_id
        observed = read_observation(child, tmp_path / "before.json")

        def operation(key: str) -> OperationMetadata:
            return OperationMetadata.model_validate_json(json.dumps(observed[key]))

        service, controller, load = (
            operation("service_operation"),
            operation("controller_operation"),
            operation("worker_load_operation"),
        )
        assert service == ready.operation_metadata
        assert controller.parent_span_id == service.span_id
        assert load.parent_span_id == controller.span_id
        caller, receiving, remote = (
            operation("caller_operation"),
            operation("receiving_operation"),
            operation("response_operation"),
        )
        assert caller.parent_span_id == launch.span_id
        assert receiving.parent_span_id == caller.span_id
        assert remote.span_id == receiving.span_id and remote.parent_span_id is None
        assert all(
            value.trace_id == phase.trace_id and value.trace_state == phase.trace_state
            for value in (launch, service, controller, load, caller, receiving, remote)
        )
        native = EvaluationResult if scorer == "hhem" else UnievalResult
        assert native.model_validate_json(json.dumps(observed["result"])).status == "complete"
        stopped = child.close(CHILD_STARTUP_MS)
        assert isinstance(stopped, ScorerStopped)
        assert stopped.operation_metadata == ready.operation_metadata
        assert stopped.launch_operation_metadata == launch
        assert stopped.worker_exit.confirmed is True and child.process.returncode == 0
        relayed = [
            ServerEvent.model_validate_json(line) for line in capsys.readouterr().err.splitlines()
        ]
        records = observed["trace_records"]
        assert isinstance(records, list) and records
        for record in records:
            assert isinstance(record, dict)
            original = ServerEvent.model_validate_json(json.dumps(record["event"]))
            assert original in relayed
    finally:
        if not child.closed:
            child.close(CHILD_STARTUP_MS)
