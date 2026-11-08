"""Do actual native engines retain independent outcomes for the same saved pair?"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from summary_eval_pipeline.contracts import PipelineError, text_sha256
from summary_eval_pipeline.evaluate_pair import EvaluatorOutcomes, evaluate_pair
from summary_eval_pipeline.evaluation import bind_evaluations, read_owned_health
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_eval_pipeline.storage import read_result, write_result
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.shared.contracts.api_paths import EVALUATE_PATH
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult
from summary_evaluator.unieval.load_unieval_resources import load_unieval_resources
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.replay_predictions import Scenario
from summary_evaluator_cases.service_cases import service_settings
from summary_evaluator_cases.unieval_cases import (
    UnievalScenario,
    read_unieval_recordings,
    unieval_settings,
)

from summary_eval_tests.scorer_caller_cases import running_scorers
from summary_eval_tests.test_generation_handoff import generation_phase


@pytest.mark.parametrize("failure", ["hhem", "unieval", "coherence", "malformed_prediction"])
def test_same_pair_and_reference_requests_preserve_native_sibling_and_partial_results(
    tmp_path: Path, failure: str
) -> None:
    async def check() -> None:
        inputs, prepared, receipt, previous = generation_phase()
        _, selected_unieval = unieval_settings()
        hhem_scenario = Scenario()
        unieval_scenario = UnievalScenario(fail_at=0)
        if failure != "unieval":
            cases, _, _ = read_unieval_recordings()
            case = cases.cases[0].request
            inputs = inputs.model_copy(
                update={
                    "source_text": case.source_text,
                    "reference_summary_text": case.reference_summary_text,
                }
            )
            prepared = prepared.model_copy(
                update={
                    "source_sha256": text_sha256(inputs.source_text),
                    "reference_summary_sha256": text_sha256(inputs.reference_summary_text),
                }
            )
            receipt = receipt.model_copy(
                update={
                    "source_sha256": prepared.source_sha256,
                    "reference_summary_sha256": prepared.reference_summary_sha256,
                    "summary_text": case.summary_text,
                    "summary_sha256": text_sha256(case.summary_text),
                }
            )
            previous = previous.model_copy(
                update={
                    "reference_summary_sha256": prepared.reference_summary_sha256,
                    "generation_sha256": text_sha256(receipt.model_dump_json()),
                }
            )
            hhem_scenario = Scenario(actions=("raise",))
            unieval_scenario = UnievalScenario(
                invalid_at=2 if failure == "malformed_prediction" else None
            )
        if failure == "coherence":
            assert receipt.summary_text is not None
            resources = load_unieval_resources(selected_unieval, REPOSITORY)
            tokens = resources.token_count(
                selected_unieval.prompts.coherence.format(
                    summary=receipt.summary_text, source=inputs.source_text
                )
            )
            selected_unieval = selected_unieval.model_copy(
                update={
                    "scoring": selected_unieval.scoring.model_copy(
                        update={"max_input_tokens": tokens - 1}
                    )
                }
            )
        requests = bind_evaluations(
            prepared, inputs, receipt, previous,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        selected_hhem = service_settings()
        outcomes = EvaluatorOutcomes()
        errors: list[PipelineError] = []
        seen: dict[str, dict[str, object]] = {}
        hhem_saved, unieval_saved = tmp_path / "hhem.json", tmp_path / "unieval.json"
        pipeline = load_pipeline_settings(REPOSITORY)

        async def record_request(request: httpx.Request) -> None:
            if request.url.path in (EVALUATE_PATH, UNIEVAL_PATH):
                seen[request.url.path] = json.loads(request.content)

        async with running_scorers(
            selected_hhem,
            (hhem_scenario,) if failure == "unieval" else (hhem_scenario, Scenario()),
            selected_unieval=selected_unieval,
            unieval_scenario=unieval_scenario,
        ) as service:
            service.client.event_hooks["request"].append(record_request)
            hhem_api, unieval_api = service.apis
            assert hhem_api.health is not None and unieval_api.health is not None
            assert hhem_api.health.hhem.worker is not None
            assert unieval_api.health.unieval.worker is not None
            assert hhem_api.health.hhem.worker.pid != unieval_api.health.unieval.worker.pid
            assert hhem_api.origin != unieval_api.origin

            def save() -> None:
                if outcomes.hhem is not None:
                    write_result(hhem_saved, outcomes.hhem)
                if outcomes.unieval is not None:
                    write_result(unieval_saved, outcomes.unieval)

            await evaluate_pair(
                service.client,
                requests,
                hhem_api,
                unieval_api,
                selected_hhem,
                selected_unieval,
                pipeline,
                outcomes,
                errors,
                save,
            )
            assert (
                read_result(hhem_saved, EvaluationResult, pipeline.max_response_bytes)
                == outcomes.hhem
            )
            assert (
                read_result(unieval_saved, UnievalResult, pipeline.max_response_bytes)
                == outcomes.unieval
            )
            sent = {
                request.url.path: (request.url.host, request.url.port)
                for request in service.transport.requests if request.url.path in seen
            }
            assert sent[EVALUATE_PATH] == (
                hhem_api.api_settings.listener.host, hhem_api.api_settings.listener.port
            )
            assert sent[UNIEVAL_PATH] == (
                unieval_api.api_settings.listener.host, unieval_api.api_settings.listener.port
            )
            for path in (EVALUATE_PATH, UNIEVAL_PATH):
                assert seen[path]["source_text"] == inputs.source_text
                assert seen[path]["summary_text"] == receipt.summary_text
            assert "reference_summary_text" not in seen[EVALUATE_PATH]
            assert seen[UNIEVAL_PATH]["reference_summary_text"] == inputs.reference_summary_text
            logs = service.hhem.log.getvalue() + service.unieval.log.getvalue()
            assert inputs.reference_summary_text not in logs
            assert inputs.source_text not in logs
            assert receipt.summary_text is not None
            assert receipt.summary_text not in logs
            assert outcomes.hhem is not None and outcomes.unieval is not None
            assert outcomes.unieval.reference_summary_sha256 == prepared.reference_summary_sha256
            if failure == "unieval":
                assert outcomes.hhem.status == "complete"
                assert outcomes.unieval.status == "failed"
            else:
                assert outcomes.hhem.status == "failed"
                assert outcomes.unieval.status == ("complete" if failure == "hhem" else "partial")
                if failure == "coherence":
                    assert outcomes.unieval.scores.coherence is None
                    assert outcomes.unieval.scores.relevance is not None
                    assert outcomes.unieval.scores.consistency is not None
                    assert any(
                        error.code == "COHERENCE_INPUT_TOO_LONG"
                        for error in outcomes.unieval.errors
                    )
                    assert any(
                        error.service == "unieval" and error.http_status == 400 for error in errors
                    )
                elif failure == "malformed_prediction":
                    assert outcomes.unieval.scores.fluency is not None
                    assert any(
                        error.code == "INVALID_MODEL_OUTPUT" for error in outcomes.unieval.errors
                    )
        assert service.hhem.worker.exit_confirmed and service.unieval_worker.exit_confirmed

    asyncio.run(check())


def test_a_failed_component_health_does_not_discard_the_ready_sibling() -> None:
    async def check() -> None:
        _, selected_unieval = unieval_settings()
        selected_hhem = service_settings()
        inputs, prepared, receipt, previous = generation_phase()
        requests = bind_evaluations(
            prepared, inputs, receipt, previous,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        pipeline = load_pipeline_settings(REPOSITORY)
        async with running_scorers(
            selected_hhem,
            selected_unieval=selected_unieval,
        ) as service:
            worker = service.unieval_worker
            assert worker.lifetime is not None and worker.process is not None
            worker.lifetime.close()
            await asyncio.to_thread(worker.process.join, 5)
            errors: list[PipelineError] = []
            api = service.apis[1]
            with pytest.raises(WorkflowError) as failure:
                await read_owned_health(
                    service.client, api.origin, service.unieval.app.state.service_instance_id,
                    api.worker_settings, pipeline, "unieval",
                    observe=lambda health: setattr(api, "health", health),
                )
            api.retain_error(failure.value.error)
            assert api.health is not None and api.health.unieval.status == "failed"
            outcomes = EvaluatorOutcomes()
            await evaluate_pair(
                service.client,
                requests,
                *service.apis,
                selected_hhem,
                selected_unieval,
                pipeline,
                outcomes,
                errors,
                lambda: None,
            )
            assert outcomes.hhem is not None and outcomes.hhem.status == "complete"
            assert outcomes.unieval is None
            assert any(
                error.service == "unieval" and error.code == "HEALTH_FAILED"
                for error in service.apis[1].errors
            )
        assert worker.exit_confirmed and service.hhem.worker.exit_confirmed

    asyncio.run(check())


def test_cancellation_keeps_the_saved_sibling_and_native_interrupted_result() -> None:
    async def check() -> None:
        inputs, prepared, receipt, previous = generation_phase()
        requests = bind_evaluations(
            prepared, inputs, receipt, previous,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        _, selected_unieval = unieval_settings()
        selected_hhem = service_settings()
        pipeline = load_pipeline_settings(REPOSITORY)
        outcomes = EvaluatorOutcomes()
        errors: list[PipelineError] = []
        saved = asyncio.Event()
        async with running_scorers(
            selected_hhem,
            selected_unieval=selected_unieval,
            unieval_scenario=UnievalScenario(block_at=0),
        ) as service:
            worker = service.unieval_worker
            work = asyncio.create_task(
                evaluate_pair(
                    service.client,
                    requests,
                    *service.apis,
                    selected_hhem,
                    selected_unieval,
                    pipeline,
                    outcomes,
                    errors,
                    lambda: saved.set() if outcomes.hhem is not None else None,
                )
            )
            async with asyncio.timeout(20):
                await saved.wait()
                while service.unieval.app.state.unieval.active_task is None:
                    await asyncio.sleep(0)
            work.cancel()
            with pytest.raises(asyncio.CancelledError):
                await work
            assert outcomes.hhem is not None and outcomes.hhem.status == "complete"
            assert outcomes.unieval is not None and outcomes.unieval.status == "failed"
            assert all(value is None for value in outcomes.unieval.scores.model_dump().values())
            assert any(error.code == "SERVICE_STOPPED" for error in outcomes.unieval.errors)
            assert any(
                error.code == "EVALUATION_FAILED"
                and error.service == "unieval"
                and error.http_status == 503
                for error in errors
            )
        assert worker.exit_confirmed and service.hhem.worker.exit_confirmed

    asyncio.run(check())
