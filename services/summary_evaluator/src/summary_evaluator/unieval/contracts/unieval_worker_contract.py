"""Which current private UniEval packet version requires the actual worker operation?"""

from typing import Final, Literal

from local_api_host.propagate_trace_context import OperationMetadata
from pydantic import ConfigDict, field_validator

from summary_evaluator.shared.bound_operation_metadata import validate_worker_operation_metadata
from summary_evaluator.shared.contracts.base import NativeContract

UNIEVAL_WORKER_VERSION: Final = "2026-11-09"


class UnievalWorkerContract(NativeContract):
    """Reject mixed live protocols without changing native scores or recordings."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": UNIEVAL_WORKER_VERSION,
            "readCompatibility": "current_only; replace old owned processes before issuing packets",
            "changelog": [
                {
                    "version": UNIEVAL_WORKER_VERSION,
                    "change": "Retain dimension-bound input measurements in refused work.",
                },
                {
                    "version": "2026-11-08",
                    "change": "Bind actual operations and optional relevance selection.",
                }
            ],
        }
    )

    version: Literal["2026-11-09"]
    operation_metadata: OperationMetadata

    @field_validator("operation_metadata")
    @classmethod
    def require_bounded_actual_operation(cls, value: OperationMetadata) -> OperationMetadata:
        return validate_worker_operation_metadata(value)
