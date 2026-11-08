"""Can a ready scorer finish when its sibling's model cleanup blocks that API's health?"""

import asyncio
from pathlib import Path

import httpx
from summary_eval_pipeline.contracts import PipelineError, text_sha256
from summary_eval_pipeline.evaluate_pair import EvaluatorOutcomes, evaluate_pair
from summary_eval_pipeline.evaluation import bind_evaluations, read_owned_health
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_eval_pipeline.storage import read_result, write_result
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.shared.contracts.api_paths import API_HEALTH_PATH, EVALUATE_PATH
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.service_cases import service_settings
from summary_evaluator_cases.unieval_cases import (
    RecordedUnievalSupervisor,
    UnievalScenario,
    unieval_settings,
)

from summary_eval_tests.scorer_caller_cases import running_scorers
from summary_eval_tests.test_generation_handoff import generation_phase


class SlowFailedUnieval(RecordedUnievalSupervisor):
    def __init__(self, settings: UnievalSettings, stop_delay_seconds: float) -> None:
        super().__init__(settings, UnievalScenario(load_failure=True))
        self.allow_start = asyncio.Event()
        self.cleanup_started = asyncio.Event()
        self.stop_delay_seconds = stop_delay_seconds

    async def start(self) -> None:
        await self.allow_start.wait()
        await super().start()

    async def stop(self) -> None:
        if not self.cleanup_started.is_set():
            self.cleanup_started.set()
            await asyncio.sleep(self.stop_delay_seconds)
        await super().stop()


def test_native_load_failure_and_slow_join_retain_health_error_and_ready_hhem_result(
    tmp_path: Path,
) -> None:
    async def check() -> None:
        inputs, prepared, receipt, previous = generation_phase()
        requests = bind_evaluations(
            prepared, inputs, receipt, previous,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        pipeline = load_pipeline_settings(REPOSITORY)
        selected_hhem = service_settings()
        _, selected_unieval = unieval_settings()
        # Six seconds with the committed five-second health allowance; no deadline is raised.
        worker = SlowFailedUnieval(selected_unieval, pipeline.http_connect_timeout_ms / 1000 + 1)
        outcomes = EvaluatorOutcomes()
        errors: list[PipelineError] = []
        scoring_paths: list[str] = []
        saved = tmp_path / "hhem.json"

        async def record_scoring(request: httpx.Request) -> None:
            if request.url.path in (EVALUATE_PATH, UNIEVAL_PATH):
                scoring_paths.append(request.url.path)

        async def release_failed_load(response: httpx.Response) -> None:
            if response.request.url.path != API_HEALTH_PATH:
                return
            observed = ApiHealth.model_validate_json(await response.aread())
            if observed.enabled_routes == ("unieval",) and observed.unieval.status == "loading":
                worker.allow_start.set()

        async with running_scorers(
            selected_hhem,
            wait_ready=False,
            selected_unieval=selected_unieval,
            unieval_supervisor=worker,
        ) as service:
            await service.hhem.app.state.controller.loading_task
            service.client.event_hooks["request"].append(record_scoring)
            service.client.event_hooks["response"].append(release_failed_load)
            async def wait_selected(index: int) -> None:
                api = service.apis[index]
                app = service.hhem.app if index == 0 else service.unieval.app
                try:
                    api.health = await read_owned_health(
                        service.client, api.origin, app.state.service_instance_id,
                        api.worker_settings, pipeline, api.scorer,
                        observe=lambda health: setattr(api, "health", health),
                    )
                except WorkflowError as error:
                    api.retain_error(error.error)

            await asyncio.gather(wait_selected(0), wait_selected(1))
            assert worker.cleanup_started.is_set()
            assert service.unieval.app.state.unieval.failure_code == "MODEL_LOAD_FAILED"
            hhem_api, unieval_api = service.apis
            assert hhem_api.health is not None and hhem_api.health.status == "ready"
            assert unieval_api.health is not None and unieval_api.health.unieval.status == "loading"
            assert [(error.code, error.phase, error.service) for error in unieval_api.errors] == [
                ("HTTP_FAILED", "health", "unieval")
            ]

            def save() -> None:
                if outcomes.hhem is not None:
                    write_result(saved, outcomes.hhem)

            await evaluate_pair(
                service.client,
                requests,
                *service.apis,
                selected_hhem,
                selected_unieval,
                pipeline,
                outcomes,
                errors,
                save,
            )
            retained = read_result(saved, EvaluationResult, pipeline.max_response_bytes)
            assert retained == outcomes.hhem and retained.status == "complete"
            assert retained.hhem is not None and outcomes.unieval is None
            assert unieval_api.errors[0].code == "HTTP_FAILED" and not hhem_api.errors
            assert not errors
            assert scoring_paths == [EVALUATE_PATH]
            assert "PrivateModelLoadFailureCanary" not in (
                service.hhem.log.getvalue() + service.unieval.log.getvalue()
            )
        assert worker.exit_confirmed and worker.last_exit is not None
        assert service.hhem.worker.exit_confirmed

    asyncio.run(check())
