"""Do selected native callers keep their own deadlines, origins and request byte allowances?"""

import asyncio
import time
from pathlib import Path

import pytest
from summary_eval_pipeline.contracts import PipelineError, text_sha256
from summary_eval_pipeline.evaluate_pair import EvaluatorOutcomes, evaluate_pair
from summary_eval_pipeline.evaluation import bind_evaluations, read_owned_health
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.inputs import encode_request
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_eval_pipeline.storage import write_result
from summary_evaluator.shared.contracts.api_paths import EVALUATE_PATH
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.service_cases import service_settings
from summary_evaluator_cases.unieval_cases import read_unieval_recordings, unieval_settings

from summary_eval_tests.scorer_caller_cases import running_scorers
from summary_eval_tests.test_generation_handoff import generation_phase


@pytest.mark.parametrize("scorer", ["hhem", "unieval"])
def test_a_request_exceeding_its_listener_bound_never_runs_or_cancels_its_ready_peer(
    tmp_path: Path, scorer: str,
) -> None:
    async def check() -> None:
        inputs, prepared, receipt, previous = generation_phase()
        if scorer == "hhem":
            cases, _, _ = read_unieval_recordings()
            recorded = cases.cases[0].request
            inputs = inputs.model_copy(update={
                "source_text": recorded.source_text,
                "reference_summary_text": recorded.reference_summary_text,
            })
            prepared = prepared.model_copy(update={
                "source_sha256": text_sha256(inputs.source_text),
                "reference_summary_sha256": text_sha256(inputs.reference_summary_text),
            })
            receipt = receipt.model_copy(update={
                "source_sha256": prepared.source_sha256,
                "reference_summary_sha256": prepared.reference_summary_sha256,
                "summary_text": recorded.summary_text,
                "summary_sha256": text_sha256(recorded.summary_text),
            })
            previous = previous.model_copy(update={
                "reference_summary_sha256": prepared.reference_summary_sha256,
                "generation_sha256": text_sha256(receipt.model_dump_json()),
            })
        requests = bind_evaluations(
            prepared, inputs, receipt, previous,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        hhem_settings = service_settings()
        _, selected_unieval = unieval_settings()
        if scorer == "hhem":
            hhem_settings = service_settings(
                listener={"max_body_bytes": len(encode_request(requests[0])) - 1}
            )
        else:
            selected_unieval = selected_unieval.model_copy(update={
                "listener": selected_unieval.listener.model_copy(
                    update={"max_body_bytes": len(encode_request(requests[1])) - 1}
                )
            })
        outcomes = EvaluatorOutcomes()
        errors: list[PipelineError] = []
        async with running_scorers(
            hhem_settings, selected_unieval=selected_unieval,
        ) as service:
            peer = service.apis[1 if scorer == "hhem" else 0]
            assert peer.health is not None
            before = peer.health

            def save() -> None:
                if outcomes.hhem is not None:
                    write_result(tmp_path / "hhem.json", outcomes.hhem)
                if outcomes.unieval is not None:
                    write_result(tmp_path / "unieval.json", outcomes.unieval)

            await evaluate_pair(
                service.client, requests, *service.apis, hhem_settings, selected_unieval,
                load_pipeline_settings(REPOSITORY), outcomes, errors, save,
            )
            assert peer.health == before and not peer.errors
            assert getattr(outcomes, scorer) is None
            completed = outcomes.unieval if scorer == "hhem" else outcomes.hhem
            assert completed is not None and completed.status == "complete"
            assert (tmp_path / ("unieval.json" if scorer == "hhem" else "hhem.json")).is_file()
            assert [(error.code, error.service) for error in errors] == [
                ("INPUT_TOO_LARGE", scorer)
            ]
            scoring = [
                request.url.path for request in service.transport.requests
                if request.url.path in (EVALUATE_PATH, UNIEVAL_PATH)
            ]
            assert scoring == [UNIEVAL_PATH if scorer == "hhem" else EVALUATE_PATH]
            if scorer == "hhem":
                observed = await service.unieval.app.state.unieval.health()
            else:
                observed = service.hhem.app.state.controller.health()
            assert observed.worker == getattr(before, peer.scorer).worker
            assert observed.service_instance_id == before.service_instance_id

    asyncio.run(check())


@pytest.mark.parametrize("fault", ["scorer", "instance", "deadline"])
def test_readiness_refuses_crossed_identity_and_does_not_reset_an_expired_worker_deadline(
    fault: str,
) -> None:
    async def check() -> None:
        async with running_scorers() as service:
            hhem, unieval = service.apis
            assert hhem.health is not None and unieval.health is not None
            before = len(service.transport.requests)
            with pytest.raises(WorkflowError) as failure:
                await read_owned_health(
                    service.client, hhem.origin,
                    unieval.health.service_instance_id if fault == "instance"
                    else hhem.health.service_instance_id,
                    hhem.worker_settings, load_pipeline_settings(REPOSITORY),
                    "unieval" if fault == "scorer" else "hhem",
                    deadline=time.monotonic() if fault == "deadline" else None,
                )
            assert failure.value.error.code == (
                "HEALTH_FAILED" if fault == "deadline" else "STARTUP_IDENTITY_MISMATCH"
            )
            if fault == "deadline":
                assert len(service.transport.requests) == before
            assert not hhem.errors and not unieval.errors
            assert not any(
                request.url.path in (EVALUATE_PATH, UNIEVAL_PATH)
                for request in service.transport.requests
            )

    asyncio.run(check())
