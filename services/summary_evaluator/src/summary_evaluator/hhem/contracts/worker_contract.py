"""Which current private HHEM packet version requires an actual issued operation?"""

from typing import Final, Literal

from local_api_host.propagate_trace_context import OperationMetadata
from pydantic import ConfigDict, field_validator

from summary_evaluator.shared.bound_operation_metadata import validate_worker_operation_metadata
from summary_evaluator.shared.contracts.base import NativeContract

HHEM_WORKER_VERSION: Final = "2026-11-08"


class WorkerContract(NativeContract):
    """Reject mixed live worker generations rather than migrate transient packets."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": HHEM_WORKER_VERSION,
            "readCompatibility": "current_only; replace old owned processes before issuing packets",
            "changelog": [
                {
                    "version": HHEM_WORKER_VERSION,
                    "change": "Require issued operation metadata on every private worker packet.",
                }
            ],
        }
    )

    version: Literal["2026-11-08"]
    operation_metadata: OperationMetadata

    @field_validator("operation_metadata")
    @classmethod
    def require_bounded_actual_operation(cls, value: OperationMetadata) -> OperationMetadata:
        return validate_worker_operation_metadata(value)
