"""Which observed state can a body-free service health response report?"""

from typing import Self

from pydantic import model_validator

from .base import Count, NativeContract, PositiveCount, SchemaVersion, ServiceStatus, Uuid4
from .error_detail import ErrorCode
from .model_identity import ModelIdentity
from .worker_identity import WorkerIdentity


class ServiceHealth(NativeContract):
    """Require observed model and worker identities before reporting readiness."""

    version: SchemaVersion
    service_instance_id: Uuid4
    status: ServiceStatus
    worker: WorkerIdentity | None
    model: ModelIdentity | None
    queue_depth: Count
    queue_capacity: PositiveCount
    failure_code: ErrorCode | None

    @model_validator(mode="after")
    def require_honest_readiness(self) -> Self:
        if self.queue_depth > self.queue_capacity:
            raise ValueError("queue_depth must not exceed queue_capacity")
        if self.status == "ready" and (
            self.worker is None or self.model is None or self.failure_code is not None
        ):
            raise ValueError("Ready requires worker and model identities without failure")
        if self.status == "failed" and self.failure_code is None:
            raise ValueError("Failed health requires a closed failure_code")
        return self

    @property
    def http_status(self) -> int:
        return 200 if self.status == "ready" else 503
