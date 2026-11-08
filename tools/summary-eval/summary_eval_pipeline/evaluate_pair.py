"""How do both native evaluator outcomes survive an independent sibling failure?"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from local_api_host.propagate_trace_context import (
    OperationMetadata,
    create_child_operation,
    create_root_operation,
)
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.service_health import ServiceHealth
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_result import UnievalHealth, UnievalResult
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.resolve_unieval_selection import resolve_unieval_selection

from .contracts import PipelineError, text_sha256
from .evaluation import evaluate, evaluate_unieval
from .failures import WorkflowError
from .phase_services import ScorerService, guard_work
from .settings import PipelineSettings
from .trace_context import ResponseTraceObservation


@dataclass
class EvaluatorOutcomes:
    hhem: EvaluationResult | None = None
    unieval: UnievalResult | None = None
    hhem_operation: OperationMetadata | None = None
    unieval_operation: OperationMetadata | None = None
    hhem_trace: ResponseTraceObservation | None = None
    unieval_trace: ResponseTraceObservation | None = None


def require_unieval_work(
    result: UnievalResult, request: UnievalRequest, settings: UnievalSettings, status: int
) -> None:
    work = result.work
    controls, skip = resolve_unieval_selection(request, settings.scoring)
    if (
        (
            result.effective_settings is not None
            and (
                result.effective_settings.model_dump(exclude={"source_budget_tokens"})
                != controls.model_dump()
                or result.relevance_skip_reason != skip
            )
        )
        or (
            skip is not None
            and (
                work.relevance.planned is not None
                or work.relevance.completed != 0
                or result.scores.relevance is not None
                or any(error.dimension == "relevance" for error in result.errors)
            )
        )
    ):
        raise WorkflowError("RECEIPT_INVALID", "evaluation", "unieval", status)
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
    requests: tuple[EvaluateRequest, UnievalRequest],
    hhem_api: ScorerService,
    unieval_api: ScorerService,
    settings: ServiceSettings,
    unieval_settings: UnievalSettings,
    pipeline: PipelineSettings,
    outcomes: EvaluatorOutcomes,
    errors: list[PipelineError],
    save: Callable[[], object],
    *,
    operation_metadata: OperationMetadata | None = None,
) -> None:
    hhem_request, unieval_request = requests
    if (
        hhem_request.source_text != unieval_request.source_text
        or hhem_request.summary_text != unieval_request.summary_text
        or hhem_request.request_id != unieval_request.request_id
        or hhem_request.correlation_id != unieval_request.correlation_id
    ):
        raise WorkflowError("RECEIPT_INVALID", "input")
    reference_hash = (
        text_sha256(unieval_request.reference_summary_text)
        if unieval_request.reference_summary_text is not None else None
    )
    phase_operation = operation_metadata or create_root_operation()

    def observe_hhem(value: ResponseTraceObservation) -> None:
        outcomes.hhem_trace = value

    def observe_unieval(value: ResponseTraceObservation) -> None:
        outcomes.unieval_trace = value

    def retain() -> None:
        try:
            save()
        except OSError:
            errors.append(WorkflowError("RESULT_WRITE_FAILED", "evaluation").error)

    async def hhem() -> None:
        try:
            health = hhem_api.health
            if health is None or hhem_api.errors:
                return
            if (
                hhem_api.scorer != "hhem"
                or health.enabled_routes != ("hhem",)
                or settings.listener != hhem_api.api_settings.listener
            ):
                raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "health", "hhem")
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
            outcomes.hhem_operation = create_child_operation(phase_operation)
            operation = evaluate(
                client, hhem_api.origin, hhem_request, settings, pipeline,
                operation_metadata=outcomes.hhem_operation, observe_trace=observe_hhem,
            )
            status, result = (
                await guard_work(operation, hhem_api.owner, pipeline)
                if hhem_api.owner is not None else await operation
            )
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
            if error.error.service == "api" or error.error.phase == "health":
                hhem_api.retain_error(error.error)
            else:
                errors.append(error.error)
        except asyncio.CancelledError:
            errors.append(WorkflowError("TASK_CANCELLED", "evaluation", "hhem").error)
            raise
        except (OSError, ValueError, KeyError, TypeError):
            errors.append(WorkflowError("EVALUATION_FAILED", "evaluation", "hhem").error)
        finally:
            retain()

    async def unieval() -> None:
        try:
            health = unieval_api.health
            if health is None or unieval_api.errors:
                return
            if (
                unieval_api.scorer != "unieval"
                or health.enabled_routes != ("unieval",)
                or unieval_settings.listener != unieval_api.api_settings.listener
            ):
                raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "health", "unieval")
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
            outcomes.unieval_operation = create_child_operation(phase_operation)
            operation = evaluate_unieval(
                client, unieval_api.origin, unieval_request, unieval_settings, pipeline,
                operation_metadata=outcomes.unieval_operation, observe_trace=observe_unieval,
            )
            status, result = (
                await guard_work(operation, unieval_api.owner, pipeline)
                if unieval_api.owner is not None else await operation
            )
            if (
                result.request_id != unieval_request.request_id
                or result.correlation_id != unieval_request.correlation_id
                or result.reference_summary_sha256
                != reference_hash
                or (result.model is not None and result.model != health.unieval.model)
                or (result.worker is not None and result.worker != health.unieval.worker)
                or (
                    result.work.source_characters is not None
                    and result.work.source_characters != len(unieval_request.source_text)
                )
            ):
                raise WorkflowError("RECEIPT_INVALID", "evaluation", "unieval", status)
            require_unieval_work(result, unieval_request, unieval_settings, status)
            outcomes.unieval = result
            if status != 200 or result.status != "complete":
                errors.append(
                    WorkflowError("EVALUATION_FAILED", "evaluation", "unieval", status).error
                )
        except WorkflowError as error:
            if error.error.service == "api" or error.error.phase == "health":
                unieval_api.retain_error(error.error)
            else:
                errors.append(error.error)
        except asyncio.CancelledError:
            errors.append(WorkflowError("TASK_CANCELLED", "evaluation", "unieval").error)
            raise
        except (OSError, ValueError, KeyError, TypeError):
            errors.append(WorkflowError("EVALUATION_FAILED", "evaluation", "unieval").error)
        finally:
            retain()

    await asyncio.gather(hhem(), unieval())
