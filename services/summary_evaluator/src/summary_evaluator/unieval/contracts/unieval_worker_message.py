"""Which bounded native packets identify UniEval planning and every scored comparison?"""

from typing import Annotated, Literal

from pydantic import Field, RootModel

from summary_evaluator.shared.contracts.base import Count, PositiveCount, Score, Uuid4
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.unieval.contracts.unieval_contract import (
    Dimension,
    UnievalContract,
    UnievalVersion,
)
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_request import (
    EffectiveUnievalControls,
    UnievalRequest,
)
from summary_evaluator.unieval.contracts.unieval_result import UnievalModelIdentity, UnievalWork
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings


class UnievalBootstrap(UnievalContract):
    kind: Literal["bootstrap"] = "bootstrap"
    version: UnievalVersion
    settings: UnievalSettings


class UnievalReady(UnievalContract):
    kind: Literal["ready"] = "ready"
    version: UnievalVersion
    worker: WorkerIdentity
    model: UnievalModelIdentity


class UnievalStartupFailed(UnievalContract):
    kind: Literal["startup_failed"] = "startup_failed"
    version: UnievalVersion
    error: UnievalError


class UnievalCommand(UnievalContract):
    kind: Literal["evaluate"] = "evaluate"
    version: UnievalVersion
    execution_id: Uuid4
    generation: PositiveCount
    request: UnievalRequest


class RequestPacket(UnievalContract):
    version: UnievalVersion
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
    pass
