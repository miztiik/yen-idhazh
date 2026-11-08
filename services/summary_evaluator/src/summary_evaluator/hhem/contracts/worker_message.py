"""Which validated JSON packets may cross the owned scoring-process boundary?"""

from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, RootModel, model_validator

from summary_evaluator.hhem.contracts.base import Comparison
from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.model_identity import ModelIdentity
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.hhem.contracts.worker_contract import WorkerContract
from summary_evaluator.shared.contracts.base import (
    Count,
    Milliseconds,
    NativeContract,
    NonblankText,
    PositiveCount,
    Score,
    Uuid4,
)
from summary_evaluator.shared.contracts.service_settings import ModelAssetSettings, StartupContext
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity


class FrozenAssets(NativeContract):
    """Name the immutable model and foundation assets selected at startup."""

    model: ModelAssetSettings
    foundation: ModelAssetSettings


class WorkerBootstrap(WorkerContract):
    """Freeze settings and logical asset identities before any text is sent."""

    kind: Literal["bootstrap"]
    settings: ServiceSettings
    assets: FrozenAssets
    context: StartupContext

    @model_validator(mode="after")
    def require_matching_assets(self) -> Self:
        if (
            self.assets.model != self.settings.hhem.model
            or self.assets.foundation != self.settings.hhem.foundation
        ):
            raise ValueError("Bootstrap assets must match the frozen startup settings")
        return self


class WorkerStarted(WorkerContract):
    """Report the owned process separately from model readiness."""

    kind: Literal["worker_started"]
    worker: WorkerIdentity


class WorkerReady(WorkerContract):
    """Require fingerprints before reporting a loaded model."""

    kind: Literal["ready"]
    worker: WorkerIdentity
    model: ModelIdentity


class WorkerFailed(WorkerContract):
    """Report a closed startup failure instead of incomplete readiness."""

    kind: Literal["worker_failed"]
    worker: WorkerIdentity
    error: ErrorDetail

    @model_validator(mode="after")
    def require_startup_failure(self) -> Self:
        if self.error.phase != "worker" or self.error.window_index is not None:
            raise ValueError("Startup failure requires worker phase without a window")
        if self.error.code not in (
            "MODEL_LOAD_FAILED",
            "MODEL_IDENTITY_CHANGED",
            "WORKER_PROTOCOL_FAILED",
            "INTERNAL_ERROR",
        ):
            raise ValueError("Startup failure requires a closed worker startup error")
        return self


class WindowIdentity(WorkerContract):
    """Identify the exact active command, including its end-exclusive word range."""

    execution_id: Uuid4
    generation: PositiveCount
    comparison: Comparison
    window_index: Count
    start_word: Count
    end_word: PositiveCount

    @model_validator(mode="after")
    def require_nonempty_range(self) -> Self:
        if self.end_word <= self.start_word:
            raise ValueError("end_word must be greater than start_word")
        return self


class ScoreWindow(WindowIdentity):
    """Carry source then summary text only through the private scoring command."""

    kind: Literal["score_window"]
    source_text: NonblankText
    summary_text: NonblankText

    @model_validator(mode="after")
    def require_matching_word_range(self) -> Self:
        if len(self.source_text.split()) != self.end_word - self.start_word:
            raise ValueError("source_text must match the declared word range")
        return self


class WindowOutcome(WindowIdentity):
    """Return one valid score or one closed failure, never input text."""

    kind: Literal["window_scored", "window_failed"]
    score: Score | None
    scoring_ms: Milliseconds | None
    error: ErrorDetail | None

    @model_validator(mode="after")
    def require_consistent_window_outcome(self) -> Self:
        if self.kind == "window_scored":
            if self.score is None or self.error is not None:
                raise ValueError("window_scored requires a score without an error")
        elif self.score is not None or self.error is None:
            raise ValueError("window_failed requires an error without a score")
        if self.error is not None and (
            self.error.phase != self.comparison or self.error.window_index != self.window_index
        ):
            raise ValueError("Window failure must match the comparison and window identity")
        return self


type CommandPacket = Annotated[WorkerBootstrap | ScoreWindow, Field(discriminator="kind")]
type ReplyPacket = Annotated[
    WorkerStarted | WorkerReady | WorkerFailed | WindowOutcome, Field(discriminator="kind")
]
_PACKET_READER_CONFIG = ConfigDict(
    strict=True,
    frozen=True,
    hide_input_in_errors=True,
    json_schema_extra=WorkerContract.model_config["json_schema_extra"],
)


class WorkerCommand(RootModel[CommandPacket]):
    """Read a closed command without adding a field to its JSON envelope."""

    model_config = _PACKET_READER_CONFIG


class WorkerReply(RootModel[ReplyPacket]):
    """Read a closed outcome without adding a field to its JSON envelope."""

    model_config = _PACKET_READER_CONFIG


def validate_window_reply(command: ScoreWindow, outcome: WindowOutcome) -> None:
    """Reject a stale or out-of-order outcome against its one outstanding command."""
    for field in WindowIdentity.model_fields:
        if getattr(command, field) != getattr(outcome, field):
            raise ValueError("Window outcome does not match the outstanding command")
