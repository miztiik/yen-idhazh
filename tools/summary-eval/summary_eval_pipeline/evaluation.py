"""How is the owned API checked before scoring the saved generated pair?"""

import asyncio
import time
from collections.abc import Callable

import httpx
from local_api_host.propagate_trace_context import OperationMetadata, create_child_operation
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.serve_http.contracts.api_health import ApiHealth, DisabledEvaluatorHealth
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.shared.contracts.api_paths import API_HEALTH_PATH, EVALUATE_PATH
from summary_evaluator.shared.contracts.service_settings import WorkerSettings
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH

from .contracts import ServiceName, text_sha256
from .failures import WorkflowError
from .http import call_local_api
from .inputs import ManualInputs, encode_request
from .phase_contracts import PhaseEvidence, PhaseResult, starts_no_scorers
from .run_contracts import (
    GenerationReceipt,
    GenerationResult,
    PreparedResult,
    PreparedRun,
)
from .settings import PipelineSettings
from .trace_context import ResponseTraceObserver


def bind_evaluations(
    prepared: PreparedResult,
    inputs: ManualInputs,
    receipt: GenerationResult,
    generation: PhaseResult,
    *,
    generation_sha256: str,
) -> tuple[EvaluateRequest, UnievalRequest]:
    if (
        not isinstance(prepared, PreparedRun)
        or not isinstance(receipt, GenerationReceipt)
        or not isinstance(generation, PhaseEvidence)
    ):
        raise WorkflowError("RECEIPT_INVALID", "input")
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
        or receipt.reference_summary_sha256 != inputs.reference_summary_sha256
        or receipt.evaluate_relevance != prepared.evaluate_relevance
        or receipt.evaluate_relevance != inputs.evaluate_relevance
        or receipt.summary_sha256 != text_sha256(receipt.summary_text)
        or receipt.loaded.model_id != prepared.selected.model_id
        or receipt.loaded.sha256 != prepared.selected.sha256
        or receipt.loaded.weights_path != f"backend/models/{prepared.selected.filename}"
        or generation.run != prepared.run
        or generation.phase != "generation"
        or generation.shutdown.llama_stopped is not True
        or not starts_no_scorers(generation)
        or generation.shutdown.host_stopped is not True
        or generation.generation_sha256 != generation_sha256
        or generation.reference_summary_sha256 != prepared.reference_summary_sha256
        or generation.evaluate_relevance != prepared.evaluate_relevance
    ):
        raise WorkflowError("RECEIPT_INVALID", "input")
    request = EvaluateRequest(
        source_text=inputs.source_text,
        summary_text=receipt.summary_text,
        hhem_full=False,
        request_id=create_execution_id(),
        correlation_id=create_execution_id(),
    )
    reference = (
        {"reference_summary_text": inputs.reference_summary_text}
        if inputs.reference_summary_text is not None else {}
    )
    unieval = UnievalRequest.model_validate({
        **reference,
        "source_text": request.source_text,
        "summary_text": request.summary_text,
        "evaluate_relevance": prepared.evaluate_relevance,
        "request_id": request.request_id,
        "correlation_id": request.correlation_id,
    })
    return request, unieval


async def read_owned_health(
    client: httpx.AsyncClient,
    base_url: str,
    service_instance_id: str,
    settings: WorkerSettings,
    pipeline: PipelineSettings,
    scorer: ApiComponent,
    *,
    deadline: float | None = None,
    observe: Callable[[ApiHealth], None] | None = None,
    operation_metadata: OperationMetadata | None = None,
    observe_trace: ResponseTraceObserver | None = None,
) -> ApiHealth:
    if deadline is None:
        deadline = time.monotonic() + settings.startup_timeout_ms / 1000
    service: ServiceName = scorer
    while (remaining := deadline - time.monotonic()) > 0:
        status, health = await call_local_api(
            client,
            "GET",
            base_url + API_HEALTH_PATH,
            ApiHealth,
            pipeline,
            min(remaining * 1000, pipeline.http_connect_timeout_ms),
            service=service,
            phase="health",
            operation_metadata=(
                create_child_operation(operation_metadata)
                if operation_metadata is not None else None
            ),
            observe_trace=observe_trace,
        )
        observed = getattr(health, scorer)
        if (
            health.service_instance_id != service_instance_id
            or health.enabled_routes != (scorer,)
            or any(
                getattr(health, name).status != "disabled"
                for name in ("hhem", "unieval")
                if name != scorer
            )
            or (
                observed.status == "ready"
                and observed.service_instance_id != service_instance_id
            )
        ):
            raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "health", service, status)
        if observe is not None:
            observe(health)
        if status == 200 and health.status == "ready":
            return health
        if status != 503 or health.status not in ("loading", "failed", "stopping"):
            raise WorkflowError("HEALTH_FAILED", "health", service, status)
        if observed.status != "loading":
            raise WorkflowError(
                "HEALTH_FAILED", "health", service, status,
                source_code=(
                    observed.failure_code
                    if not isinstance(observed, DisabledEvaluatorHealth) else None
                ),
            )
        await asyncio.sleep(
            min(
                pipeline.poll_interval_ms / 1000,
                max(0, deadline - time.monotonic()),
            )
        )
    raise WorkflowError("HEALTH_FAILED", "health", service)


async def evaluate(
    client: httpx.AsyncClient,
    base_url: str,
    request: EvaluateRequest,
    settings: ServiceSettings,
    pipeline: PipelineSettings,
    *,
    operation_metadata: OperationMetadata | None = None,
    observe_trace: ResponseTraceObserver | None = None,
) -> tuple[int, EvaluationResult]:
    body = encode_request(request)
    if len(body) > settings.listener.max_body_bytes:
        raise WorkflowError("INPUT_TOO_LARGE", "evaluation", "hhem")
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
        body=body,
        operation_metadata=operation_metadata,
        observe_trace=observe_trace,
    )


async def evaluate_unieval(
    client: httpx.AsyncClient,
    base_url: str,
    request: UnievalRequest,
    settings: UnievalSettings,
    pipeline: PipelineSettings,
    *,
    operation_metadata: OperationMetadata | None = None,
    observe_trace: ResponseTraceObserver | None = None,
) -> tuple[int, UnievalResult]:
    body = encode_request(request)
    if len(body) > settings.listener.max_body_bytes:
        raise WorkflowError("INPUT_TOO_LARGE", "evaluation", "unieval")
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
        body=body,
        operation_metadata=operation_metadata,
        observe_trace=observe_trace,
    )
