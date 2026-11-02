"""How is the owned API checked before one native evaluation request?"""

import asyncio
import time

import httpx

from hhem_evaluator.contracts.base import API_PREFIX, EVALUATE_PATH
from hhem_evaluator.contracts.evaluate_request import EvaluateRequest
from hhem_evaluator.contracts.evaluation_result import EvaluationResult
from hhem_evaluator.contracts.service_health import ServiceHealth
from hhem_evaluator.contracts.service_settings import ServiceSettings

from .failures import WorkflowFailure
from .http import call_local_api
from .inputs import encode_request
from .settings import PipelineSettings


async def read_owned_health(
    client: httpx.AsyncClient,
    base_url: str,
    service_instance_id: str,
    settings: ServiceSettings,
    pipeline: PipelineSettings,
) -> ServiceHealth:
    deadline = time.monotonic() + settings.worker.startup_timeout_ms / 1000
    while (remaining := deadline - time.monotonic()) > 0:
        status, health = await call_local_api(
            client,
            "GET",
            base_url + API_PREFIX + "/health",
            ServiceHealth,
            pipeline,
            min(remaining * 1000, pipeline.http_connect_timeout_ms),
            service="hhem",
            phase="health",
        )
        if health.service_instance_id != service_instance_id:
            raise WorkflowFailure("STARTUP_IDENTITY_MISMATCH", "health", "hhem", status)
        if status == 200 and health.status == "ready":
            return health
        if status != 503 or health.status != "loading":
            raise WorkflowFailure("HEALTH_FAILED", "health", "hhem", status)
        await asyncio.sleep(
            min(
                pipeline.poll_interval_ms / 1000,
                max(0, deadline - time.monotonic()),
            )
        )
    raise WorkflowFailure("HEALTH_FAILED", "health", "hhem")


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
        + pipeline.http_connect_timeout_ms,
        service="hhem",
        phase="evaluation",
        body=encode_request(request),
    )
