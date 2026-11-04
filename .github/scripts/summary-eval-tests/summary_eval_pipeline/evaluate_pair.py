"""How do both native evaluator outcomes survive an independent sibling failure?"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from hhem_evaluator.contracts.api_health import ApiHealth
from hhem_evaluator.contracts.evaluate_request import EvaluateRequest
from hhem_evaluator.contracts.evaluation_result import EvaluationResult
from hhem_evaluator.contracts.service_health import ServiceHealth
from hhem_evaluator.contracts.service_settings import ServiceSettings
from hhem_evaluator.contracts.unieval_request import UnievalRequest
from hhem_evaluator.contracts.unieval_result import UnievalHealth, UnievalResult
from hhem_evaluator.contracts.unieval_settings import UnievalSettings

from .contracts import PipelineError, text_sha256
from .evaluation import evaluate, evaluate_unieval
from .failures import WorkflowError
from .settings import PipelineSettings


@dataclass
class EvaluatorOutcomes:
    hhem: EvaluationResult | None = None
    unieval: UnievalResult | None = None


def require_unieval_work(result: UnievalResult, request: UnievalRequest, status: int) -> None:
    work = result.work
    has_score = any(value is not None for value in result.scores.model_dump().values())
    valid = not has_score or (
        work.source_characters == len(request.source_text) and work.summary_sentences is not None
    )
    if result.scores.consistency is not None:
        valid = (
            valid
            and bool(work.source_spans)
            and work.summary_sentences is not None
            and work.consistency.planned == work.summary_sentences * len(work.source_spans)
        )
    if result.scores.fluency is not None:
        valid = valid and work.fluency.planned == work.summary_sentences
    for dimension in ("coherence", "relevance"):
        if getattr(result.scores, dimension) is not None:
            valid = valid and getattr(work, dimension).planned == 1
    if not valid:
        raise WorkflowError("RECEIPT_INVALID", "evaluation", "unieval", status)


async def evaluate_pair(
    client: httpx.AsyncClient,
    origin: str,
    requests: tuple[EvaluateRequest, UnievalRequest],
    health: ApiHealth,
    settings: ServiceSettings,
    unieval_settings: UnievalSettings,
    pipeline: PipelineSettings,
    outcomes: EvaluatorOutcomes,
    errors: list[PipelineError],
    save: Callable[[], None],
) -> None:
    hhem_request, unieval_request = requests
    if (
        hhem_request.source_text != unieval_request.source_text
        or hhem_request.summary_text != unieval_request.summary_text
        or hhem_request.request_id != unieval_request.request_id
        or hhem_request.correlation_id != unieval_request.correlation_id
    ):
        raise WorkflowError("RECEIPT_INVALID", "input")

    def retain() -> None:
        try:
            save()
        except OSError:
            errors.append(WorkflowError("RESULT_WRITE_FAILED", "evaluation").error)

    async def hhem() -> None:
        try:
            if health.hhem.status != "ready":
                raise WorkflowError(
                    "HEALTH_FAILED",
                    "health",
                    "hhem",
                    source_code=(
                        health.hhem.failure_code if isinstance(health.hhem, ServiceHealth) else None
                    ),
                )
            model = health.hhem.model
            if (
                model is None
                or health.hhem.service_instance_id != health.service_instance_id
                or model.reference != settings.hhem.model.reference
                or model.loaded_revision != settings.hhem.model.revision
                or model.foundation_reference != settings.hhem.foundation.reference
                or model.foundation_revision != settings.hhem.foundation.revision
            ):
                raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "health", "hhem")
            status, result = await evaluate(client, origin, hhem_request, settings, pipeline)
            if (
                result.request_id != hhem_request.request_id
                or result.correlation_id != hhem_request.correlation_id
                or (result.model is not None and result.model != health.hhem.model)
                or (result.worker is not None and result.worker != health.hhem.worker)
            ):
                raise WorkflowError("RECEIPT_INVALID", "evaluation", "hhem", status)
            outcomes.hhem = result
            if status != 200 or result.status != "complete":
                errors.append(
                    WorkflowError("EVALUATION_FAILED", "evaluation", "hhem", status).error
                )
        except WorkflowError as error:
            errors.append(error.error)
        except asyncio.CancelledError:
            errors.append(WorkflowError("TASK_CANCELLED", "evaluation", "hhem").error)
            raise
        finally:
            retain()

    async def unieval() -> None:
        try:
            if health.unieval.status != "ready":
                raise WorkflowError(
                    "HEALTH_FAILED",
                    "health",
                    "unieval",
                    source_code=(
                        health.unieval.failure_code
                        if isinstance(health.unieval, UnievalHealth)
                        else None
                    ),
                )
            model = health.unieval.model
            if (
                model is None
                or health.unieval.service_instance_id != health.service_instance_id
                or model.reference != unieval_settings.assets.model.reference
                or model.loaded_revision != unieval_settings.assets.model.revision
                or model.reference_code_revision != unieval_settings.assets.reference_code_revision
            ):
                raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "health", "unieval")
            status, result = await evaluate_unieval(
                client, origin, unieval_request, unieval_settings, pipeline
            )
            if (
                result.request_id != unieval_request.request_id
                or result.correlation_id != unieval_request.correlation_id
                or result.reference_summary_sha256
                != text_sha256(unieval_request.reference_summary_text)
                or (result.model is not None and result.model != health.unieval.model)
                or (result.worker is not None and result.worker != health.unieval.worker)
                or (
                    result.effective_settings is not None
                    and result.effective_settings.consistency_source_mode
                    != unieval_settings.scoring.consistency_source_mode
                )
                or (
                    result.work.source_characters is not None
                    and result.work.source_characters != len(unieval_request.source_text)
                )
            ):
                raise WorkflowError("RECEIPT_INVALID", "evaluation", "unieval", status)
            require_unieval_work(result, unieval_request, status)
            outcomes.unieval = result
            if status != 200 or result.status != "complete":
                errors.append(
                    WorkflowError("EVALUATION_FAILED", "evaluation", "unieval", status).error
                )
        except WorkflowError as error:
            errors.append(error.error)
        except asyncio.CancelledError:
            errors.append(WorkflowError("TASK_CANCELLED", "evaluation", "unieval").error)
            raise
        finally:
            retain()

    await asyncio.gather(hhem(), unieval())
