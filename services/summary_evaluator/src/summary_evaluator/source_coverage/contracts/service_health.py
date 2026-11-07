"""Which coverage worker and queue are actually available without collecting machine readings?"""

from typing import Self

from pydantic import model_validator

from summary_evaluator.shared.contracts.base import Count, PositiveCount, ServiceStatus, Uuid4
from summary_evaluator.shared.contracts.error_policy import ErrorCode
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.source_coverage.contracts.base import CoverageContract, CoverageVersion
from summary_evaluator.source_coverage.contracts.model_identity import CoverageModelIdentity


class CoverageHealth(CoverageContract):
    version: CoverageVersion
    service_instance_id: Uuid4
    status: ServiceStatus
    model: CoverageModelIdentity | None
    worker: WorkerIdentity | None
    queue_depth: Count
    queue_capacity: PositiveCount
    failure_code: ErrorCode | None

    @model_validator(mode="after")
    def require_observed_readiness(self) -> Self:
        if self.status == "ready" and (
            self.model is None or self.worker is None or self.failure_code is not None
        ):
            raise ValueError("Coverage readiness requires its actual model and owned worker")
        return self
