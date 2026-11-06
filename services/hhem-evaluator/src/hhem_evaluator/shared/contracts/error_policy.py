"""Which closed failures retain their existing HTTP status and safe wording?"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

ErrorCode = Literal[
    "INVALID_JSON",
    "INVALID_REQUEST",
    "INPUT_TIMEOUT",
    "BODY_TOO_LARGE",
    "UNSUPPORTED_MEDIA",
    "ORIGIN_FORBIDDEN",
    "HOST_FORBIDDEN",
    "WINDOW_LIMIT_EXCEEDED",
    "QUEUE_FULL",
    "QUEUE_TIMEOUT",
    "SERVICE_DISABLED",
    "SERVICE_STOPPED",
    "WORKER_NOT_READY",
    "MODEL_LOAD_FAILED",
    "MODEL_IDENTITY_CHANGED",
    "MODEL_SCORING_FAILED",
    "INVALID_MODEL_OUTPUT",
    "WORKER_EXITED",
    "WORKER_PROTOCOL_FAILED",
    "WORKER_STOP_FAILED",
    "EVALUATION_TIMEOUT",
    "CLIENT_DISCONNECTED",
    "LOGGING_FAILED",
    "INTERNAL_ERROR",
]


@dataclass(frozen=True)
class ErrorPolicy:
    """Bind a closed failure to its response status and body-free wording."""

    http_status: int | None
    message: str


ERROR_POLICIES: Mapping[ErrorCode, ErrorPolicy] = MappingProxyType(
    {
        "INVALID_JSON": ErrorPolicy(400, "The request body is not valid JSON."),
        "INVALID_REQUEST": ErrorPolicy(400, "The request does not match the evaluation contract."),
        "INPUT_TIMEOUT": ErrorPolicy(408, "The request body was not received before its deadline."),
        "BODY_TOO_LARGE": ErrorPolicy(413, "The request body exceeds the configured byte limit."),
        "UNSUPPORTED_MEDIA": ErrorPolicy(415, "The request requires unencoded UTF-8 JSON."),
        "ORIGIN_FORBIDDEN": ErrorPolicy(403, "Browser-origin requests are not accepted."),
        "HOST_FORBIDDEN": ErrorPolicy(403, "The request host is not accepted."),
        "WINDOW_LIMIT_EXCEEDED": ErrorPolicy(
            400, "The comparison exceeds the configured window limit."
        ),
        "QUEUE_FULL": ErrorPolicy(429, "The waiting queue has no available reservation."),
        "QUEUE_TIMEOUT": ErrorPolicy(503, "The request expired while waiting for evaluation."),
        "SERVICE_DISABLED": ErrorPolicy(503, "The evaluation service is disabled."),
        "SERVICE_STOPPED": ErrorPolicy(503, "The evaluation service is stopping."),
        "WORKER_NOT_READY": ErrorPolicy(503, "The scoring process is not ready."),
        "MODEL_LOAD_FAILED": ErrorPolicy(500, "The scoring model could not be loaded."),
        "MODEL_IDENTITY_CHANGED": ErrorPolicy(500, "The loaded model identity changed."),
        "MODEL_SCORING_FAILED": ErrorPolicy(500, "The scoring model could not finish the window."),
        "INVALID_MODEL_OUTPUT": ErrorPolicy(500, "The scoring model returned an invalid score."),
        "WORKER_EXITED": ErrorPolicy(500, "The scoring process exited before completing its work."),
        "WORKER_PROTOCOL_FAILED": ErrorPolicy(
            500, "The scoring process returned an invalid packet."
        ),
        "WORKER_STOP_FAILED": ErrorPolicy(500, "The scoring process exit could not be confirmed."),
        "EVALUATION_TIMEOUT": ErrorPolicy(504, "The evaluation exceeded its configured deadline."),
        "CLIENT_DISCONNECTED": ErrorPolicy(None, "The caller disconnected before delivery."),
        "LOGGING_FAILED": ErrorPolicy(500, "The terminal evaluation event could not be written."),
        "INTERNAL_ERROR": ErrorPolicy(500, "The evaluation could not be completed."),
    }
)
