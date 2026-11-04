"""Can a ready sibling score when failed model cleanup blocks a later shared-health request?"""

import asyncio
from pathlib import Path

import httpx
from summary_eval_pipeline.contracts import (
    PhaseEvidence,
    PipelineError,
    ServiceShutdown,
    text_sha256,
)
from summary_eval_pipeline.evaluate_pair import EvaluatorOutcomes, evaluate_pair
from summary_eval_pipeline.evaluation import bind_evaluations, read_owned_health
from summary_eval_pipeline.phase_result import build_evidence
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_eval_pipeline.storage import read_result, write_result

from hhem_evaluator.contracts.api_health import ApiHealth
from hhem_evaluator.contracts.base import EVALUATE_PATH
from hhem_evaluator.contracts.unieval_settings import UnievalSettings
from hhem_evaluator.unieval_router import UNIEVAL_PATH

from .contract_examples import REPOSITORY
from .service_cases import running_service, service_settings
from .test_generation_handoff import generation_phase
from .unieval_cases import RecordedUnievalSupervisor, UnievalScenario, unieval_settings


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
        requests = bind_evaluations(prepared, inputs, receipt, previous, 1 << 20)
        pipeline = load_pipeline_settings(REPOSITORY)
        selected_hhem = service_settings()
        _, selected_unieval = unieval_settings()
        # Six seconds with the committed five-second health allowance; no deadline is raised.
        worker = SlowFailedUnieval(selected_unieval, pipeline.http_connect_timeout_ms / 1000 + 1)
        outcomes = EvaluatorOutcomes()
        errors: list[PipelineError] = []
        scoring_paths: list[str] = []
        saved = tmp_path / "evaluation.json"

        async def record_scoring(request: httpx.Request) -> None:
            if request.url.path in (EVALUATE_PATH, UNIEVAL_PATH):
                scoring_paths.append(request.url.path)

        async def release_failed_load(response: httpx.Response) -> None:
            if response.request.url.path != "/health":
                return
            observed = ApiHealth.model_validate_json(await response.aread())
            if observed.hhem.status == "ready" and observed.unieval.status == "loading":
                worker.allow_start.set()

        async with running_service(
            selected_hhem,
            routes=("hhem", "unieval"),
            wait_ready=False,
            unieval_settings=selected_unieval,
            unieval_supervisor=worker,
        ) as service:
            await service.app.state.controller.loading_task
            service.client.event_hooks["request"].append(record_scoring)
            service.client.event_hooks["response"].append(release_failed_load)
            health = await read_owned_health(
                service.client,
                "http://127.0.0.1:3010",
                service.app.state.service_instance_id,
                selected_hhem,
                pipeline,
                ("hhem", "unieval"),
                max(
                    selected_hhem.worker.startup_timeout_ms,
                    selected_unieval.worker.startup_timeout_ms,
                ),
                errors=errors,
            )
            assert worker.cleanup_started.is_set()
            assert service.app.state.unieval.failure_code == "MODEL_LOAD_FAILED"
            assert health.hhem.status == "ready" and health.unieval.status == "loading"
            assert [(error.code, error.phase, error.service) for error in errors] == [
                ("HTTP_FAILED", "health", "api")
            ]

            def save() -> None:
                write_result(
                    saved,
                    build_evidence(
                        outcomes.hhem,
                        None,
                        None,
                        ServiceShutdown(
                            api_stopped=None, host_stopped=None, worker_exit_confirmed=None
                        ),
                        errors,
                        run=prepared.run,
                        phase="evaluation",
                        reference_summary_sha256=prepared.reference_summary_sha256,
                        generation_sha256=text_sha256(receipt.model_dump_json()),
                        evaluation_request_id=requests[0].request_id,
                        evaluation_correlation_id=requests[0].correlation_id,
                        api_health=health,
                        unieval=outcomes.unieval,
                    ),
                )

            await evaluate_pair(
                service.client,
                "http://127.0.0.1:3010",
                requests,
                health,
                selected_hhem,
                selected_unieval,
                pipeline,
                outcomes,
                errors,
                save,
            )
            retained = read_result(saved, PhaseEvidence, pipeline.max_response_bytes)
            assert retained.status == "partial"
            assert retained.evaluation is not None and retained.evaluation.status == "complete"
            assert retained.evaluation.hhem is not None and retained.unieval is None
            assert retained.errors[0].code == "HTTP_FAILED"
            assert retained.api_health == health
            assert scoring_paths == [EVALUATE_PATH]
            assert "PrivateModelLoadFailureCanary" not in service.log.getvalue()
        assert worker.exit_confirmed and worker.last_exit is not None
        assert service.worker.exit_confirmed

    asyncio.run(check())
