"""Can an invalid native reply escape request binding or erase the sibling's actual score?"""

import asyncio
import json

import httpx
import pytest
from summary_eval_pipeline.contracts import PipelineError, text_sha256
from summary_eval_pipeline.evaluate_pair import EvaluatorOutcomes, evaluate_pair
from summary_eval_pipeline.evaluation import bind_evaluations
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH
from summary_evaluator_cases.contract_examples import REPOSITORY, REQUEST_ID
from summary_evaluator_cases.service_cases import service_settings
from summary_evaluator_cases.unieval_cases import (
    UnievalScenario,
    unieval_settings,
)

from summary_eval_tests.scorer_caller_cases import running_scorers
from summary_eval_tests.test_generation_handoff import generation_phase


class AlteredEvaluatorReply(httpx.AsyncBaseTransport):
    """Damage an actual native reply at the HTTP boundary, never fabricate a prediction."""

    def __init__(self, transport: httpx.AsyncBaseTransport, fault: str, event: str) -> None:
        self.transport, self.fault, self.event = transport, fault, event

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self.transport.handle_async_request(request)
        if request.url.path != UNIEVAL_PATH:
            return response
        data = json.loads(await response.aread())
        if self.fault == "request":
            data["request_id"] = REQUEST_ID
        elif self.fault == "reference":
            data["reference_summary_sha256"] = "b" * 64
        elif self.fault == "model":
            for name in ("configured_revision", "loaded_revision", "tokenizer_revision"):
                data["model"][name] = "b" * 40
        elif self.fault == "mode":
            data["effective_settings"]["consistency_source_mode"] = "full_source_prompt"
        elif self.fault == "source":
            data["work"]["source_characters"] += 1
            data["work"]["source_spans"][-1]["end"] += 1
        elif self.fault == "controls":
            data["effective_settings"]["max_input_tokens"] += 1
        elif self.fault in ("selection", "skip"):
            data["relevance_skip_reason"] = (
                "disabled" if self.fault == "selection" else "reference_not_supplied"
            )
            if self.fault == "selection":
                data["effective_settings"]["evaluate_relevance"] = False
            else:
                data["reference_summary_sha256"] = None
            data["scores"]["relevance"] = None
            data["work"]["relevance"] = {"planned": None, "completed": 0}
            data["errors"] = [
                error for error in data["errors"] if error["dimension"] != "relevance"
            ]
        encoded = (
            self.event.encode()
            if self.fault == "event"
            else b"{"
            if self.fault == "malformed"
            else json.dumps(data).encode()
        )
        return httpx.Response(
            response.status_code,
            content=encoded,
            headers={"Content-Type": "application/json"},
            request=request,
        )

    async def aclose(self) -> None:
        await self.transport.aclose()


@pytest.mark.parametrize(
    "fault",
    [
        "request", "reference", "model", "mode", "source", "event", "malformed",
        "controls", "selection", "skip",
    ],
)
def test_invalid_response_has_no_score_and_preserves_the_actual_hhem_result(fault: str) -> None:
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
        async with running_scorers(
            selected_hhem,
            selected_unieval=selected_unieval,
            unieval_scenario=UnievalScenario(fail_at=0),
        ) as service:
            transport = AlteredEvaluatorReply(
                service.transport, fault, service.hhem.log.envelopes[0].model_dump_json()
            )
            async with httpx.AsyncClient(
                transport=transport, trust_env=False
            ) as client:
                await evaluate_pair(
                    client,
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
            expected = "RESPONSE_INVALID" if fault in ("event", "malformed") else "RECEIPT_INVALID"
            assert any(error.code == expected and error.service == "unieval" for error in errors)
        assert service.unieval_worker.exit_confirmed and service.hhem.worker.exit_confirmed

    asyncio.run(check())
