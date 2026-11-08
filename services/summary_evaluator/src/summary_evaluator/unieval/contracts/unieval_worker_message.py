"""Which bounded native packets identify UniEval planning and every scored comparison?"""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from summary_evaluator.shared.contracts.base import Count, PositiveCount, Score, Uuid4
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.unieval.contracts.unieval_contract import (
    Dimension,
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
    work: UnievalWork
    errors: tuple[UnievalError, ...]


class UnievalPrediction(RequestPacket):
    kind: Literal["prediction"] = "prediction"
    dimension: Dimension
    index: Count
    sentence_index: Count | None
    source_index: Count | None
    score: Score | None
    error: UnievalError | None


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
