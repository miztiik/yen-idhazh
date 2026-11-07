"""Which bounded private packets carry one complete coverage result or one safe failure?"""

from typing import Annotated, Literal

from pydantic import Field, RootModel

from summary_evaluator.shared.contracts.base import PositiveCount, Uuid4
from summary_evaluator.shared.contracts.error_policy import ErrorCode
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.source_coverage.contracts.base import CoverageContract, CoverageVersion
from summary_evaluator.source_coverage.contracts.evaluate_request import CoverageRequest
from summary_evaluator.source_coverage.contracts.evaluation_result import CoverageMetrics
from summary_evaluator.source_coverage.contracts.model_identity import CoverageModelIdentity
from summary_evaluator.source_coverage.contracts.scoring_warning import CoverageWarningCode
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings


class CoverageBootstrap(CoverageContract):
    kind: Literal["bootstrap"] = "bootstrap"
    version: CoverageVersion
    settings: CoverageSettings


class CoverageReady(CoverageContract):
    kind: Literal["ready"] = "ready"
    version: CoverageVersion
    worker: WorkerIdentity
    model: CoverageModelIdentity


class CoverageStartupFailed(CoverageContract):
    kind: Literal["startup_failed"] = "startup_failed"
    version: CoverageVersion
    code: ErrorCode


class CoverageCommand(CoverageContract):
    kind: Literal["evaluate"] = "evaluate"
    version: CoverageVersion
    execution_id: Uuid4
    generation: PositiveCount
    request: CoverageRequest


class CoverageCompleted(CoverageContract):
    kind: Literal["completed"] = "completed"
    version: CoverageVersion
    execution_id: Uuid4
    generation: PositiveCount
    metrics: CoverageMetrics
    warnings: tuple[CoverageWarningCode, ...] = ()


class CoverageFailed(CoverageContract):
    kind: Literal["failed"] = "failed"
    version: CoverageVersion
    execution_id: Uuid4
    generation: PositiveCount
    code: ErrorCode
    warnings: tuple[CoverageWarningCode, ...] = ()


class CoverageReply(
    RootModel[
        Annotated[
            CoverageReady | CoverageStartupFailed | CoverageCompleted | CoverageFailed,
            Field(discriminator="kind"),
        ]
    ]
):
    pass
