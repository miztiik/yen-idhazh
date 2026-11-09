"""Which exact application payloads define the native GLiNER2 API?"""

from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

# The creation date identifies this protocol, independently of the model or clock.
API_VERSION: Final = "2026-11-08"
ANALYSIS_CONTRACT_VERSION: Final = "2026-11-09"
API_PREFIX: Final = f"/api/{API_VERSION}"
ANALYZE_TEXT_PATH: Final = f"{API_PREFIX}/analyze-text-gliner"
HEALTH_PATH: Final = f"{API_PREFIX}/get-gliner-health"
SCHEMA_PATH: Final = f"{API_PREFIX}/get-gliner-schema"
APPLICATION_TITLE: Final = "gliner-api"

OperationName = Literal["analyze-text-gliner"]
HealthStatus = Literal["loading", "ready", "disabled", "failed", "stopping"]
ErrorCode = Literal[
    "INVALID_REQUEST",
    "NOT_FOUND",
    "METHOD_NOT_ALLOWED",
    "BODY_TOO_LARGE",
    "HOST_FORBIDDEN",
    "ORIGIN_FORBIDDEN",
    "SERVICE_DISABLED",
    "MODEL_UNAVAILABLE",
    "INPUT_UNSUPPORTED",
    "INVALID_RESULT",
    "ANALYSIS_FAILED",
    "LOGGING_FAILED",
]

ERROR_POLICIES: Final[dict[ErrorCode, tuple[str, bool, int]]] = {
    "INVALID_REQUEST": ("The GLiNER request is invalid.", False, 422),
    "NOT_FOUND": ("The requested GLiNER operation does not exist.", False, 404),
    "METHOD_NOT_ALLOWED": ("The method is not accepted for this GLiNER operation.", False, 405),
    "BODY_TOO_LARGE": ("The request body is too large.", False, 413),
    "HOST_FORBIDDEN": ("The request Host header is not accepted.", False, 403),
    "ORIGIN_FORBIDDEN": ("Browser Origin requests are not accepted.", False, 403),
    "SERVICE_DISABLED": ("The GLiNER service is disabled.", False, 503),
    "MODEL_UNAVAILABLE": ("The configured GLiNER model is not available.", True, 503),
    "INPUT_UNSUPPORTED": ("The native model cannot process this input.", False, 422),
    "INVALID_RESULT": ("The native model returned an invalid result.", True, 500),
    "ANALYSIS_FAILED": ("The GLiNER operation failed.", True, 500),
    "LOGGING_FAILED": ("The GLiNER diagnostic could not be delivered.", True, 500),
}


def require_nonblank_utf8(value: str) -> str:
    """Preserve valid input exactly, rather than trimming or repairing it."""
    if not value.strip():
        raise ValueError("Text must not be blank")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Text must be valid UTF-8") from None
    return value


ExactText = Annotated[str, AfterValidator(require_nonblank_utf8)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class ApiContract(BaseModel):
    """Reject undeclared fields, invalid numbers and input coercion."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
        json_schema_extra={
            "version": API_VERSION,
            "changelog": [
                {"version": API_VERSION, "change": "Declare native GLiNER2 API payloads."}
            ],
        },
    )


class ResultValidationError(ValueError):
    """Refuse a damaged native prediction without retaining its contents."""


class ErrorDetail(ApiContract):
    """Describe one fixed safe failure without request data or raw diagnostics."""

    code: ErrorCode
    message: str
    retryable: bool

    @model_validator(mode="after")
    def require_safe_policy(self) -> Self:
        message, retryable, _status = ERROR_POLICIES[self.code]
        if self.message != message or self.retryable != retryable:
            raise ValueError("Error details must match the declared policy")
        return self

    @classmethod
    def from_code(cls, code: ErrorCode) -> "ErrorDetail":
        message, retryable, _status = ERROR_POLICIES[code]
        return cls(code=code, message=message, retryable=retryable)

    @property
    def http_status(self) -> int:
        return ERROR_POLICIES[self.code][2]


class ErrorResult(ApiContract):
    """Return one application-level failure."""

    error: ErrorDetail


class GlinerHealth(ApiContract):
    """Report genuine provider availability without model or worker metadata."""

    enabled: bool
    status: HealthStatus
    error: ErrorDetail | None

    @model_validator(mode="after")
    def require_consistent_readiness(self) -> Self:
        if self.enabled == (self.status == "disabled"):
            raise ValueError("Disabled status must match provider enablement")
        if (self.status == "ready") != (self.error is None):
            raise ValueError("Only genuinely ready health may omit its failure")
        if self.status == "disabled" and (
            self.error is None or self.error.code != "SERVICE_DISABLED"
        ):
            raise ValueError("Disabled health must carry the disabled failure")
        return self
