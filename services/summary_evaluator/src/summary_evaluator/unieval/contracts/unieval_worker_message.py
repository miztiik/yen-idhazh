"""Which bounded native packets identify UniEval planning and every scored comparison?"""

from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, RootModel, model_validator

from summary_evaluator.shared.contracts.base import Count, PositiveCount, Score, Uuid4
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.unieval.contracts.unieval_contract import (
    Dimension,
    RelevanceSkipReason,
)
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_request import (
    EffectiveUnievalControls,
    UnievalRequest,
)
from summary_evaluator.unieval.contracts.unieval_result import UnievalModelIdentity, UnievalWork
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.contracts.unieval_worker_contract import UnievalWorkerContract


class UnievalBootstrap(UnievalWorkerContract):
    kind: Literal["bootstrap"] = "bootstrap"
    settings: UnievalSettings


class UnievalReady(UnievalWorkerContract):
    kind: Literal["ready"] = "ready"
    worker: WorkerIdentity
    model: UnievalModelIdentity


class UnievalStartupFailed(UnievalWorkerContract):
    kind: Literal["startup_failed"] = "startup_failed"
    error: UnievalError


class UnievalCommand(UnievalWorkerContract):
    kind: Literal["evaluate"] = "evaluate"
    execution_id: Uuid4
    generation: PositiveCount
    request: UnievalRequest


class RequestPacket(UnievalWorkerContract):
    execution_id: Uuid4
    generation: PositiveCount


class UnievalPrepared(RequestPacket):
    kind: Literal["planned"] = "planned"
    effective_settings: EffectiveUnievalControls
    relevance_skip_reason: RelevanceSkipReason | None
    work: UnievalWork
    errors: tuple[UnievalError, ...]

    @model_validator(mode="after")
    def require_resolved_refusals(self) -> Self:
        if any(
            error.code == "MODEL_INPUT_TOO_LONG"
            or (
                error.allowed_tokens is not None
                and error.allowed_tokens != self.effective_settings.max_input_tokens
            )
            for error in self.errors
        ):
            raise ValueError(
                "Planned refusals require public dimensions and the resolved allowance"
            )
        if any(error.code == "WINDOW_BUDGET_INSUFFICIENT" for error in self.errors) and (
            self.effective_settings.consistency_source_mode != "all_source_windows"
            or self.work.consistency.planned is not None
            or self.work.source_spans
        ):
            raise ValueError("Window geometry requires a refused explicit source-window plan")
        for error in self.errors:
            self.work.require_refusal_index(error)
        return self


class UnievalPrediction(RequestPacket):
    kind: Literal["prediction"] = "prediction"
    dimension: Dimension
    index: Count
    sentence_index: Count | None
    source_index: Count | None
    score: Score | None
    error: UnievalError | None

    @model_validator(mode="after")
    def require_measured_comparison(self) -> Self:
        if self.error is not None and (
            self.error.code == "MODEL_INPUT_TOO_LONG"
            or (
                self.error.input_tokens is not None
                and (
                    self.error.dimension != self.dimension
                    or self.error.index != self.index
                )
            )
        ):
            raise ValueError("Measured refusal must retain the issued comparison identity")
        return self


class UnievalFinished(RequestPacket):
    kind: Literal["finished"] = "finished"


class UnievalReply(
    RootModel[
        Annotated[
            UnievalReady
            | UnievalStartupFailed
            | UnievalPrepared
            | UnievalPrediction
            | UnievalFinished,
            Field(discriminator="kind"),
        ]
    ]
):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        hide_input_in_errors=True,
        json_schema_extra=UnievalWorkerContract.model_config["json_schema_extra"],
    )


def validate_request_reply(command: UnievalCommand, reply: RequestPacket) -> None:
    """Reject another request or operation before accepting native progress."""
    for field in RequestPacket.model_fields:
        if getattr(command, field) != getattr(reply, field):
            raise ValueError("UniEval outcome does not match the outstanding command")
