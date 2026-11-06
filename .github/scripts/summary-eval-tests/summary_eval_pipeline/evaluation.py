"""How is the owned API checked before scoring the saved generated pair?"""

import asyncio
import time

import httpx
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.shared.contracts.api_paths import API_HEALTH_PATH, EVALUATE_PATH
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH

from .contracts import GenerationReceipt, PhaseEvidence, PipelineError, PreparedRun, text_sha256
from .failures import WorkflowError
from .http import call_local_api
from .inputs import ManualInputs, encode_request
from .settings import PipelineSettings


def bind_evaluations(
    prepared: PreparedRun,
    inputs: ManualInputs,
    receipt: GenerationReceipt,
    generation: PhaseEvidence,
    max_body_bytes: int,
) -> tuple[EvaluateRequest, UnievalRequest]:
    if (
        prepared.status != "complete"
        or receipt.status != "complete"
        or receipt.summary_text is None
        or receipt.loaded is None
        or receipt.run != prepared.run
        or receipt.selected != prepared.selected
        or receipt.source_sha256 != text_sha256(inputs.source_text)
        or receipt.source_sha256 != prepared.source_sha256
        or receipt.reference_summary_sha256 != prepared.reference_summary_sha256
        or receipt.reference_summary_sha256 != text_sha256(inputs.reference_summary_text)
        or receipt.summary_sha256 != text_sha256(receipt.summary_text)
        or receipt.loaded.model_id != prepared.selected.model_id
        or receipt.loaded.sha256 != prepared.selected.sha256
        or receipt.loaded.weights_path != f"backend/models/{prepared.selected.filename}"
        or generation.run != prepared.run
        or generation.phase != "generation"
        or generation.shutdown.llama_stopped is not True
        or generation.shutdown.api_stopped is not None
        or generation.shutdown.host_stopped is not True
        or generation.generation_sha256 != text_sha256(receipt.model_dump_json())
        or generation.reference_summary_sha256 != prepared.reference_summary_sha256
    ):
        raise WorkflowError("RECEIPT_INVALID", "input")
    request = EvaluateRequest(
        source_text=inputs.source_text,
        summary_text=receipt.summary_text,
        hhem_full=False,
        request_id=create_execution_id(),
        correlation_id=create_execution_id(),
    )
    unieval = UnievalRequest(
        source_text=request.source_text,
        summary_text=request.summary_text,
        reference_summary_text=inputs.reference_summary_text,
        request_id=request.request_id,
        correlation_id=request.correlation_id,
    )
    if any(len(encode_request(value)) > max_body_bytes for value in (request, unieval)):
        raise WorkflowError("INPUT_TOO_LARGE", "input")
    return request, unieval


async def read_owned_health(
    client: httpx.AsyncClient,
    base_url: str,
    service_instance_id: str,
    settings: ServiceSettings,
    pipeline: PipelineSettings,
    components: tuple[ApiComponent, ...] = ("hhem",),
    startup_timeout_ms: int | None = None,
    *,
    errors: list[PipelineError],
) -> ApiHealth:
    deadline = (
        time.monotonic()
        + (
            startup_timeout_ms
            if startup_timeout_ms is not None
            else settings.worker.startup_timeout_ms
        )
        / 1000
    )
    last: ApiHealth | None = None
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            status, health = await call_local_api(
                client,
                "GET",
                base_url + API_HEALTH_PATH,
                ApiHealth,
                pipeline,
                min(remaining * 1000, pipeline.http_connect_timeout_ms),
                service="api",
                phase="health",
            )
        except WorkflowError as error:
            if error.error.code != "HTTP_FAILED" or last is None or len(components) < 2:
                raise
            errors.append(error.error)
            return last
        if health.service_instance_id != service_instance_id or health.enabled_routes != components:
            raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "health", "api", status)
        last = health
        if status == 200 and health.status == "ready":
            return health
        if status != 503 or health.status not in ("loading", "failed", "stopping"):
            raise WorkflowError("HEALTH_FAILED", "health", "api", status)
        states = [getattr(health, component).status for component in components]
        if all(state != "loading" for state in states):
            if len(components) > 1:
                return health
            raise WorkflowError("HEALTH_FAILED", "health", "api", status)
        await asyncio.sleep(
            min(
                pipeline.poll_interval_ms / 1000,
                max(0, deadline - time.monotonic()),
            )
        )
    # One component's load failure or timeout must not erase a ready sibling.
    if len(components) > 1 and last is not None:
        return last
    raise WorkflowError("HEALTH_FAILED", "health", "api")


async def evaluate(
    client: httpx.AsyncClient,
    base_url: str,
    request: EvaluateRequest,
    settings: ServiceSettings,
    pipeline: PipelineSettings,
) -> tuple[int, EvaluationResult]:
    # Validate error-status responses too: they can contain a valid partial score.
    return await call_local_api(
        client,
        "POST",
        base_url + EVALUATE_PATH,
        EvaluationResult,
        pipeline,
        settings.queue.wait_timeout_ms
        + settings.evaluation.timeout_ms
        + settings.worker.shutdown_timeout_ms
        + pipeline.http_connect_timeout_ms,
        service="hhem",
        phase="evaluation",
        body=encode_request(request),
    )


async def evaluate_unieval(
    client: httpx.AsyncClient,
    base_url: str,
    request: UnievalRequest,
    settings: UnievalSettings,
    pipeline: PipelineSettings,
) -> tuple[int, UnievalResult]:
    return await call_local_api(
        client,
        "POST",
        base_url + UNIEVAL_PATH,
        UnievalResult,
        pipeline,
        settings.queue.wait_timeout_ms
        + settings.evaluation.timeout_ms
        + settings.worker.shutdown_timeout_ms
        + pipeline.http_connect_timeout_ms,
        service="unieval",
        phase="evaluation",
        body=encode_request(request),
    )
