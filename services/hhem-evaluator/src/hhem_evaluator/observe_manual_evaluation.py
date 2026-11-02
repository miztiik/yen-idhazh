"""How is one real API evaluation bracketed by the original worker's profile?"""

import asyncio
import time
from dataclasses import dataclass, field

import httpx

from .call_local_api import call_local_api
from .collect_task_profile import TaskMeasurement
from .contracts.base import API_PREFIX
from .contracts.evaluate_request import EvaluateRequest
from .contracts.evaluation_result import EvaluationResult
from .contracts.host_profile_reader import TaskIdentity
from .contracts.service_health import ServiceHealth
from .contracts.service_settings import ServiceSettings
from .contracts.workflow_report import WorkflowError
from .fail_manual_evaluation import WorkflowFailure
from .load_manual_settings import ManualSettings
from .read_manual_inputs import encode_request


@dataclass
class ManualObservation:
    evaluation: EvaluationResult | None = None
    final_health: ServiceHealth | None = None
    measurement: TaskMeasurement | None = None
    errors: list[WorkflowError] = field(default_factory=list)


async def read_owned_health(
    client: httpx.AsyncClient,
    api_url: str,
    instance_id: str,
    settings: ServiceSettings,
    manual: ManualSettings,
) -> tuple[int, ServiceHealth]:
    status, health = await call_local_api(
        client,
        "GET",
        api_url + API_PREFIX + "/health",
        ServiceHealth,
        manual,
        settings.listener.body_read_timeout_ms,
        service="hhem",
        phase="health",
    )
    if health.service_instance_id != instance_id:
        raise WorkflowFailure("STARTUP_IDENTITY_MISMATCH", "health", "hhem", status)
    if (status == 200) != (health.status == "ready") or status not in (200, 503):
        raise WorkflowFailure("HEALTH_FAILED", "health", "hhem", status)
    return status, health


async def wait_owned_health(
    client: httpx.AsyncClient,
    api_url: str,
    instance_id: str,
    settings: ServiceSettings,
    manual: ManualSettings,
) -> ServiceHealth:
    deadline = time.monotonic() + settings.worker.startup_timeout_ms / 1000
    while True:
        status, health = await read_owned_health(client, api_url, instance_id, settings, manual)
        if status == 200:
            return health
        if health.status not in ("loading", "replacing") or time.monotonic() >= deadline:
            raise WorkflowFailure("STARTUP_FAILED", "startup", "hhem", status)
        await asyncio.sleep(manual.poll_interval_ms / 1000)


async def observe_manual_evaluation(
    client: httpx.AsyncClient,
    api_url: str,
    host_url: str | None,
    health: ServiceHealth,
    identity: TaskIdentity,
    request: EvaluateRequest,
    settings: ServiceSettings,
    manual: ManualSettings,
    profile_timeout_ms: int,
    observation: ManualObservation,
) -> None:
    if health.worker is None:
        raise WorkflowFailure("HEALTH_FAILED", "health", "hhem")
    measurement = TaskMeasurement(health.worker, identity)
    observation.measurement = measurement
    if host_url is None:
        measurement.reason = "profile_start_failed"
    else:
        failure = await measurement.start(client, host_url, manual, profile_timeout_ms)
        if failure is not None:
            observation.errors.append(failure)
    try:
        timeout_ms = (
            settings.listener.body_read_timeout_ms
            + settings.queue.wait_timeout_ms
            + settings.evaluation.timeout_ms
            + settings.worker.shutdown_timeout_ms
        )
        status, result = await call_local_api(
            client,
            "POST",
            api_url + API_PREFIX + "/evaluate",
            EvaluationResult,
            manual,
            timeout_ms,
            service="hhem",
            phase="evaluation",
            body=encode_request(request),
        )
        observation.evaluation = result
        if status != 200 or result.status != "complete":
            observation.errors.append(
                WorkflowFailure("EVALUATION_FAILED", "evaluation", "hhem", status).error
            )
        if result.hhem is not None and (
            result.request_id != identity.request_id
            or result.correlation_id != identity.correlation_id
        ):
            raise WorkflowFailure("RESPONSE_INVALID", "evaluation", "hhem", status)
    except WorkflowFailure as failure:
        observation.errors.append(failure.error)
    finally:
        try:
            _, observation.final_health = await read_owned_health(
                client, api_url, health.service_instance_id, settings, manual
            )
        except WorkflowFailure as failure:
            observation.errors.append(failure.error)
        if host_url is not None:
            stop_failure = await measurement.stop(
                client,
                host_url,
                manual,
                profile_timeout_ms,
                "error" if observation.errors else "success",
            )
            if stop_failure is not None:
                observation.errors.append(stop_failure)
