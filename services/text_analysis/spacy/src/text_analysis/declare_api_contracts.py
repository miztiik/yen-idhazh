"""Which strict request, response, worker and CloudEvents shapes define text analysis?"""

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Literal, Self, cast
from uuid import UUID

from local_api_host.propagate_trace_context import read_trace_context
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StrictBool,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue, SkipJsonSchema
from starlette.datastructures import Headers

from text_analysis.declare_service_settings import (
    FeatureName,
    LanguageCode,
    ModelProfile,
    RawFeatureName,
)

API_SCHEMA_VERSION = "2026-11-09"
INITIAL_API_SCHEMA_VERSION = "2026-11-07"
API_PREFIX = "/api/2026-11-08"
ANALYZE_TEXT_PATH = f"{API_PREFIX}/run-ner-spacy"
HEALTH_PATH = f"{API_PREFIX}/get-spacy-health"
SCHEMA_PATH = f"{API_PREFIX}/get-spacy-schema"
EVENT_SOURCE = "/services/text-analysis"

COMPACT_FEATURE_SCHEMA = {
    "version": API_SCHEMA_VERSION,
    "changelog": [
        {
            "version": API_SCHEMA_VERSION,
            "change": "Add grouped English entities and ranked source-anchored terms.",
        },
        {
            "version": INITIAL_API_SCHEMA_VERSION,
            "change": "Declare multilingual text-analysis API contracts.",
        },
    ],
}
HEALTH_SCHEMA = {
    "version": API_SCHEMA_VERSION,
    "changelog": [
        {
            "version": API_SCHEMA_VERSION,
            "change": "Expose resolved language defaults and known English term limits.",
        },
        {
            "version": INITIAL_API_SCHEMA_VERSION,
            "change": "Declare multilingual text-analysis API contracts.",
        },
    ],
}

OutcomeStatus = Literal["complete", "partial", "failed"]
FeatureStatus = Literal["complete", "failed"]
HealthStatus = Literal["ready", "disabled", "failed", "stopping"]
ServiceEventStatus = Literal[
    "starting",
    "ready",
    "disabled",
    "failed",
    "stopping",
    "stopped",
]
ErrorCode = Literal[
    "INVALID_REQUEST",
    "BODY_TOO_LARGE",
    "HOST_FORBIDDEN",
    "ORIGIN_FORBIDDEN",
    "SERVICE_DISABLED",
    "BUSY",
    "LANGUAGE_UNAVAILABLE",
    "UNSUPPORTED_MODEL_PROFILE",
    "UNSUPPORTED_FEATURE",
    "MODEL_UNAVAILABLE",
    "FEATURE_UNAVAILABLE",
    "FEATURE_FAILED",
    "ANALYSIS_FAILED",
]
FeatureErrorCode = Literal["FEATURE_UNAVAILABLE", "FEATURE_FAILED"]
ServiceFailureCode = Literal[
    "ANALYSIS_FAILED",
    "INVALID_SERVER_SETTINGS",
    "LISTENER_BIND_FAILED",
    "LOGGING_FAILED",
    "STARTUP_FAILED",
    "SHUTDOWN_FAILED",
]
EventType = Literal[
    "text-analysis.service.started",
    "text-analysis.service.ready",
    "text-analysis.service.stopped",
    "text-analysis.service.failed",
    "text-analysis.request.completed",
    "text-analysis.request.partial",
    "text-analysis.request.failed",
]
EventLevel = Literal["INFO", "ERROR"]

ERROR_POLICIES: dict[ErrorCode, tuple[str, bool, int]] = {
    "INVALID_REQUEST": ("The text-analysis request is invalid.", False, 422),
    "BODY_TOO_LARGE": ("The request body is too large.", False, 413),
    "HOST_FORBIDDEN": ("The request Host header is not accepted.", False, 403),
    "ORIGIN_FORBIDDEN": ("Browser Origin requests are not accepted.", False, 403),
    "SERVICE_DISABLED": ("The text-analysis service is disabled.", False, 503),
    "BUSY": ("The text-analysis service is busy.", True, 429),
    "LANGUAGE_UNAVAILABLE": ("The selected language is not available.", False, 422),
    "UNSUPPORTED_MODEL_PROFILE": (
        "The selected model profile is not supported.",
        False,
        422,
    ),
    "UNSUPPORTED_FEATURE": ("The selected feature is not supported.", False, 422),
    "MODEL_UNAVAILABLE": ("The selected model is not available.", True, 503),
    "FEATURE_UNAVAILABLE": ("The selected feature is not available.", False, 422),
    "FEATURE_FAILED": ("The selected feature failed.", True, 422),
    "ANALYSIS_FAILED": ("The text analysis failed.", True, 500),
}


def _validate_nonblank_text(value: str) -> str:
    if not value.strip():
        raise ValueError("Text must not be blank")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Text must be valid UTF-8") from None
    return value


def _omit_default(schema: JsonSchemaValue) -> None:
    schema.pop("default", None)


NonblankText = Annotated[
    str,
    StringConstraints(strict=True, min_length=1),
    AfterValidator(_validate_nonblank_text),
]
Milliseconds = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


def _normalize_json_tuple(value: object, info: ValidationInfo) -> object:
    return tuple(value) if info.mode == "json" and isinstance(value, list) else value


FeatureSequence = Annotated[
    tuple[FeatureName, ...],
    BeforeValidator(_normalize_json_tuple),
]
RawFeatureSequence = Annotated[
    tuple[RawFeatureName, ...],
    BeforeValidator(_normalize_json_tuple),
]
EvidenceOccurrences = Annotated[
    tuple["EvidenceSpan", ...],
    BeforeValidator(_normalize_json_tuple),
    Field(min_length=1),
]


class ApiContract(BaseModel):
    """Reject undeclared fields and coercion in every API-owned shape."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
        json_schema_extra={
            "version": INITIAL_API_SCHEMA_VERSION,
            "changelog": [
                {
                    "version": INITIAL_API_SCHEMA_VERSION,
                    "change": "Declare multilingual text-analysis API contracts.",
                }
            ],
        },
    )


class AnalyzeTextRequest(ApiContract):
    """Select exact text, language, model profile and ordered features."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    text: NonblankText
    language: LanguageCode
    model_profile: ModelProfile | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )
    features: FeatureSequence | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )

    @model_validator(mode="before")
    @classmethod
    def refuse_explicit_null_optionals(cls, value: object) -> object:
        if isinstance(value, Mapping) and any(
            name in value and value[name] is None for name in ("model_profile", "features")
        ):
            raise ValueError("Optional request fields must be omitted instead of null")
        return value

    @field_validator("features")
    @classmethod
    def require_nonempty_distinct_features(
        cls, value: tuple[FeatureName, ...] | None
    ) -> tuple[FeatureName, ...] | None:
        if value is not None and (not value or len(set(value)) != len(value)):
            raise ValueError("features must be nonempty and distinct")
        return value


class ErrorDetail(ApiContract):
    """Return one fixed safe error without retaining request or exception data."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    code: ErrorCode
    message: str
    retryable: StrictBool
    feature: FeatureName | None

    @model_validator(mode="after")
    def require_declared_policy(self) -> Self:
        message, retryable, _status = ERROR_POLICIES[self.code]
        if self.message != message or self.retryable is not retryable:
            raise ValueError("Error details must match the declared safe policy")
        feature_code = self.code in ("FEATURE_UNAVAILABLE", "FEATURE_FAILED")
        if feature_code != (self.feature is not None):
            raise ValueError("Only feature-level errors may name a feature")
        return self

    @classmethod
    def from_code(
        cls, code: ErrorCode, *, feature: FeatureName | None = None
    ) -> "ErrorDetail":
        message, retryable, _status = ERROR_POLICIES[code]
        return cls(code=code, message=message, retryable=retryable, feature=feature)

    @property
    def http_status(self) -> int:
        return ERROR_POLICIES[self.code][2]


class ErrorResult(ApiContract):
    """Wrap one request-level safe error."""

    error: ErrorDetail


class EvidenceSpan(ApiContract):
    """Locate exact returned evidence in the original Unicode source."""

    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    sentence_index: int = Field(ge=0)

    @model_validator(mode="after")
    def require_forward_span(self) -> Self:
        if self.end_char <= self.start_char:
            raise ValueError("Evidence spans must be forward half-open offsets")
        return self


class EntityMention(EvidenceSpan):
    """Add the model's entity label to one exact source mention."""

    label: str = Field(min_length=1)


class NamedEntityRecord(ApiContract):
    """Group one presented name while retaining every exact source occurrence."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    text: NonblankText
    type: NonblankText
    occurrences: EvidenceOccurrences

    @model_validator(mode="after")
    def require_first_source_spelling(self) -> Self:
        if self.text != self.occurrences[0].text:
            raise ValueError("Grouped entity text must preserve the first source spelling")
        return self


class ImportantTermRecord(ApiContract):
    """Return one finite phrase rank with its exact original-source occurrences."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    text: NonblankText
    score: float = Field(ge=0, allow_inf_nan=False)
    occurrences: EvidenceOccurrences

    @model_validator(mode="after")
    def require_original_phrase_spelling(self) -> Self:
        if self.text != self.occurrences[0].text:
            raise ValueError("Important term text must preserve its first source spelling")
        return self


class SentenceSpan(EvidenceSpan):
    """Represent one source sentence with its ordered index."""


class RelationRecord(ApiContract):
    """Keep one sentence-local action and its exact relation evidence."""

    sentence_index: int = Field(ge=0)
    action: EvidenceSpan
    actors: Annotated[
        tuple[EvidenceSpan, ...],
        BeforeValidator(_normalize_json_tuple),
        Field(min_length=1),
    ]
    objects: Annotated[
        tuple[EvidenceSpan, ...],
        BeforeValidator(_normalize_json_tuple),
    ]
    times: Annotated[
        tuple[EvidenceSpan, ...],
        BeforeValidator(_normalize_json_tuple),
    ]
    places: Annotated[
        tuple[EvidenceSpan, ...],
        BeforeValidator(_normalize_json_tuple),
    ]

    @model_validator(mode="after")
    def require_sentence_local_evidence(self) -> Self:
        spans = (self.action, *self.actors, *self.objects, *self.times, *self.places)
        if any(span.sentence_index != self.sentence_index for span in spans):
            raise ValueError("Relation evidence must remain inside one sentence")
        return self


class TokenRecord(ApiContract):
    """Expose one ordered token and nullable model annotations."""

    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    sentence_index: int = Field(ge=0)
    lemma: str | None
    part_of_speech: str | None
    dependency: str | None
    head_index: int | None
    morphology: str | None

    @model_validator(mode="after")
    def require_forward_token(self) -> Self:
        if self.end_char <= self.start_char:
            raise ValueError("Token offsets must be forward")
        return self


class EntitiesData(ApiContract):
    mentions: Annotated[
        tuple[EntityMention, ...],
        BeforeValidator(_normalize_json_tuple),
    ]


class NamedEntitiesData(ApiContract):
    """Return source-ordered document-local entity groups."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    entities: Annotated[
        tuple[NamedEntityRecord, ...],
        BeforeValidator(_normalize_json_tuple),
    ]


class ImportantTermsData(ApiContract):
    """Return unique source-anchored terms in ascending YAKE score order."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    terms: Annotated[
        tuple[ImportantTermRecord, ...],
        BeforeValidator(_normalize_json_tuple),
    ]


class SentencesData(ApiContract):
    sentences: Annotated[
        tuple[SentenceSpan, ...],
        BeforeValidator(_normalize_json_tuple),
    ]


class RelationsData(ApiContract):
    relations: Annotated[
        tuple[RelationRecord, ...],
        BeforeValidator(_normalize_json_tuple),
    ]


class NounPhrasesData(ApiContract):
    phrases: Annotated[
        tuple[EvidenceSpan, ...],
        BeforeValidator(_normalize_json_tuple),
    ]


class LinguisticTokensData(ApiContract):
    tokens: Annotated[
        tuple[TokenRecord, ...],
        BeforeValidator(_normalize_json_tuple),
    ]


class DocumentMetricsData(ApiContract):
    codepoint_count: int = Field(ge=0)
    utf8_byte_count: int = Field(ge=0)
    token_count: int = Field(ge=0)
    sentence_count: int = Field(ge=0)
    entity_count: int = Field(ge=0)
    relation_count: int | None

    @field_validator("relation_count")
    @classmethod
    def require_nonnegative_relation_count(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("relation_count must be nonnegative")
        return value


FeatureData = (
    EntitiesData
    | SentencesData
    | RelationsData
    | NounPhrasesData
    | LinguisticTokensData
    | DocumentMetricsData
    | NamedEntitiesData
    | ImportantTermsData
)

FEATURE_DATA_TYPES: dict[FeatureName, type[ApiContract]] = {
    "entities": EntitiesData,
    "sentences": SentencesData,
    "relations": RelationsData,
    "noun_phrases": NounPhrasesData,
    "linguistic_tokens": LinguisticTokensData,
    "document_metrics": DocumentMetricsData,
    "named_entities": NamedEntitiesData,
    "important_terms": ImportantTermsData,
}


class FeatureResult(ApiContract):
    """Return exactly one complete data value or one feature-local failure."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    feature: FeatureName
    status: FeatureStatus
    data: FeatureData | None
    error: ErrorDetail | None

    @model_validator(mode="after")
    def require_one_feature_outcome(self) -> Self:
        if self.status == "complete":
            expected = FEATURE_DATA_TYPES[self.feature]
            if self.error is not None or not isinstance(self.data, expected):
                raise ValueError("Complete features require their matching typed data")
        else:
            if (
                self.data is not None
                or self.error is None
                or self.error.feature != self.feature
                or self.error.code not in ("FEATURE_UNAVAILABLE", "FEATURE_FAILED")
            ):
                raise ValueError("Failed features require one matching feature error")
        return self


class ModelIdentity(ApiContract):
    """Name the exact profile, package and runtime used for one analysis."""

    profile: ModelProfile
    package: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    spacy_version: str = Field(min_length=1)


class AnalysisResult(ApiContract):
    """Return ordered feature outcomes without service, trace or timing state."""

    status: OutcomeStatus
    language: Literal["en", "zh"]
    model: ModelIdentity
    features: Annotated[
        tuple[FeatureResult, ...],
        BeforeValidator(_normalize_json_tuple),
        Field(min_length=1),
    ]

    @model_validator(mode="after")
    def require_aggregate_status(self) -> Self:
        complete = sum(item.status == "complete" for item in self.features)
        expected: OutcomeStatus = (
            "complete"
            if complete == len(self.features)
            else "failed"
            if complete == 0
            else "partial"
        )
        if self.status != expected:
            raise ValueError("Result status must aggregate the feature outcomes")
        if len({item.feature for item in self.features}) != len(self.features):
            raise ValueError("Result features must remain distinct")
        return self


class ProfileCapability(ApiContract):
    profile: ModelProfile
    package: str = Field(min_length=1)
    model_version: str = Field(min_length=1)


class LegacyLanguageCapability(ApiContract):
    """Read one exact initial language capability without inventing new fields."""

    language: LanguageCode
    enabled: StrictBool
    default_profile: ModelProfile | None
    supported_features: RawFeatureSequence
    profiles: Annotated[
        tuple[ProfileCapability, ...],
        BeforeValidator(_normalize_json_tuple),
    ]


class LanguageCapability(ApiContract):
    """Declare resolved feature defaults and an explicitly known or unknown limit."""

    model_config = ConfigDict(json_schema_extra=HEALTH_SCHEMA)

    language: LanguageCode
    enabled: StrictBool
    default_profile: ModelProfile | None
    supported_features: FeatureSequence
    default_features: FeatureSequence
    important_terms_limit: int | None = Field(ge=0)
    profiles: Annotated[
        tuple[ProfileCapability, ...],
        BeforeValidator(_normalize_json_tuple),
    ]

    @model_validator(mode="after")
    def require_applicable_term_limit(self) -> Self:
        if self.enabled and (
            not self.default_features
            or len(set(self.default_features)) != len(self.default_features)
        ):
            raise ValueError("Enabled language defaults must be nonempty and distinct")
        if not self.enabled and self.default_features:
            raise ValueError("Disabled languages must not declare default features")
        available = (
            self.language == "en"
            and self.enabled
            and "important_terms" in self.supported_features
        )
        if available != (self.important_terms_limit is not None):
            raise ValueError("Only available English Important Terms declare a known limit")
        return self


class _HealthState(ApiContract):
    """Validate the shared live and retained health-state invariants."""

    enabled: StrictBool
    status: HealthStatus
    active_requests: int = Field(ge=0)
    max_concurrent_requests: int = Field(ge=1, le=2)
    pool_ready: StrictBool
    spacy_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_consistent_health(self) -> Self:
        if self.active_requests > self.max_concurrent_requests:
            raise ValueError("Active requests cannot exceed configured capacity")
        if self.status == "ready" and (not self.enabled or not self.pool_ready):
            raise ValueError("Ready health requires an enabled usable pool")
        if not self.enabled and (self.status != "disabled" or self.pool_ready):
            raise ValueError("Disabled health cannot expose a ready pool")
        return self


class LegacyTextAnalysisHealth(_HealthState):
    """Read exact initial health evidence with recorded global defaults only."""

    default_features: RawFeatureSequence
    allowed_features: RawFeatureSequence
    languages: Annotated[
        tuple[LegacyLanguageCapability, ...],
        BeforeValidator(_normalize_json_tuple),
    ]

    def resolve_default_features(
        self, language: LanguageCode
    ) -> tuple[RawFeatureName, ...]:
        """Use the recorded global order, never the current service configuration."""
        if not any(item.language == language for item in self.languages):
            raise ValueError("Language is absent from retained health evidence")
        return self.default_features

    def resolve_important_terms_limit(self, language: LanguageCode) -> None:
        """Keep a historical limit unknown even when English was available."""
        if not any(item.language == language for item in self.languages):
            raise ValueError("Language is absent from retained health evidence")
        return None


class TextAnalysisHealth(_HealthState):
    """Report current configured capacity and complete language capabilities."""

    model_config = ConfigDict(json_schema_extra=HEALTH_SCHEMA)

    default_features: FeatureSequence
    allowed_features: FeatureSequence
    languages: Annotated[
        tuple[LanguageCapability, ...],
        BeforeValidator(_normalize_json_tuple),
    ]


class AnalysisCommand(ApiContract):
    """Carry only trusted validated analysis input into one executor process."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    text: NonblankText
    language: Literal["en", "zh"]
    profile: ModelProfile
    features: Annotated[
        FeatureSequence,
        Field(min_length=1),
    ]


class AnalysisOutcome(ApiContract):
    """Return one validated worker outcome with process timing evidence."""

    model: ModelIdentity | None
    features: Annotated[
        tuple[FeatureResult, ...],
        BeforeValidator(_normalize_json_tuple),
    ]
    model_load_ms: Milliseconds
    analysis_ms: Milliseconds
    error: ErrorDetail | None

    @model_validator(mode="after")
    def require_worker_outcome(self) -> Self:
        if self.error is None:
            if self.model is None or not self.features:
                raise ValueError("Successful worker outcomes require model and feature results")
        elif self.model is not None or self.features or self.error.feature is not None:
            raise ValueError("Request-level worker failures must not retain partial results")
        return self


class RequestFeatureStatus(ApiContract):
    """Summarize one feature without retaining its returned evidence."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    feature: FeatureName
    status: FeatureStatus
    error_code: FeatureErrorCode | None

    @model_validator(mode="after")
    def require_feature_error_status(self) -> Self:
        if (self.status == "failed") != (self.error_code is not None):
            raise ValueError("Feature event status and error code must agree")
        return self


class ServiceEventData(ApiContract):
    """Expose safe service lifecycle state without process or exception data."""

    level: EventLevel
    enabled: StrictBool
    status: ServiceEventStatus
    active_requests: int = Field(ge=0)
    max_concurrent_requests: int = Field(ge=1, le=2)
    pool_ready: StrictBool
    error_code: ServiceFailureCode | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )

    @model_validator(mode="after")
    def require_failure_code_only_for_failure(self) -> Self:
        if self.active_requests > self.max_concurrent_requests:
            raise ValueError("Service event active requests cannot exceed capacity")
        if (self.status == "failed") != (self.error_code is not None):
            raise ValueError("Only failed service events may carry an error code")
        return self

    @model_serializer(mode="wrap")
    def serialize_without_nulls(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, object]:
        serialized = cast(dict[str, object], handler(self))
        return {key: value for key, value in serialized.items() if value is not None}


class RequestEventData(ApiContract):
    """Expose request outcomes and timings without text, spans or raw failures."""

    model_config = ConfigDict(json_schema_extra=COMPACT_FEATURE_SCHEMA)

    level: EventLevel
    language: LanguageCode | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )
    model_profile: ModelProfile | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )
    package: str | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )
    model_version: str | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )
    spacy_version: str | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )
    requested_features: FeatureSequence
    feature_statuses: Annotated[
        tuple[RequestFeatureStatus, ...],
        BeforeValidator(_normalize_json_tuple),
    ]
    active_requests: int = Field(ge=0)
    max_concurrent_requests: int = Field(ge=1, le=2)
    model_load_ms: Milliseconds
    analysis_ms: Milliseconds
    total_ms: Milliseconds
    result_status: OutcomeStatus
    error_code: ErrorCode | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )

    @model_validator(mode="after")
    def require_aggregate_request_event(self) -> Self:
        if self.active_requests > self.max_concurrent_requests:
            raise ValueError("Request event active requests cannot exceed capacity")
        identity = (
            self.package,
            self.model_version,
            self.spacy_version,
        )
        if any(value is not None for value in identity) != all(
            value is not None for value in identity
        ):
            raise ValueError("Request event model identity must be complete or absent")
        if self.feature_statuses:
            if tuple(item.feature for item in self.feature_statuses) != self.requested_features:
                raise ValueError("Request event feature statuses must preserve request order")
            if (
                self.language is None
                or self.model_profile is None
                or not all(value is not None for value in identity)
            ):
                raise ValueError("Feature outcomes require resolved model identity")
            completed = sum(item.status == "complete" for item in self.feature_statuses)
            expected: OutcomeStatus = (
                "complete"
                if completed == len(self.feature_statuses)
                else "failed"
                if completed == 0
                else "partial"
            )
            if self.result_status != expected:
                raise ValueError("Request event status must aggregate feature statuses")
        elif self.result_status != "failed":
            raise ValueError("Completed or partial request events require feature statuses")
        if self.result_status == "complete" and self.error_code is not None:
            raise ValueError("Completed request events cannot carry an error code")
        if self.result_status != "complete" and self.error_code is None:
            raise ValueError("Non-complete request events require a fixed error code")
        return self

    @model_serializer(mode="wrap")
    def serialize_without_nulls(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, object]:
        serialized = cast(dict[str, object], handler(self))
        return {key: value for key, value in serialized.items() if value is not None}


def _normalize_uuid4(value: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError:
        raise ValueError("Event id must be a lowercase UUIDv4") from None
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("Event id must be a lowercase UUIDv4")
    return value


def _validate_recorded_instant(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z", value):
        raise ValueError("Event time must be a UTC second or millisecond instant")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Event time must be a valid UTC instant") from None
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("Event time must use UTC")
    return value


LowercaseUuid4 = Annotated[
    str,
    StringConstraints(strict=True),
    AfterValidator(_normalize_uuid4),
]
RecordedInstant = Annotated[
    str,
    StringConstraints(strict=True),
    AfterValidator(_validate_recorded_instant),
]


class TextAnalysisEvent(ApiContract):
    """Carry one validated text-analysis occurrence in CloudEvents form."""

    specversion: Literal["1.0"]
    id: LowercaseUuid4
    source: Literal["/services/text-analysis"]
    type: EventType
    time: RecordedInstant
    datacontenttype: Literal["application/json"]
    traceparent: str
    tracestate: str | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_omit_default,
    )
    data: ServiceEventData | RequestEventData

    @model_validator(mode="before")
    @classmethod
    def refuse_null_tracestate(cls, value: object) -> object:
        if isinstance(value, Mapping) and value.get("tracestate", ...) is None:
            raise ValueError("Omit absent tracestate instead of supplying null")
        return value

    @model_validator(mode="after")
    def require_valid_trace_and_data(self) -> Self:
        carrier = {"traceparent": self.traceparent}
        if self.tracestate is not None:
            carrier["tracestate"] = self.tracestate
        operation = read_trace_context(Headers(carrier))
        if operation is None:
            raise ValueError("traceparent must carry valid W3C context")
        if self.tracestate is not None and operation.trace_state != self.tracestate:
            raise ValueError("tracestate must use canonical W3C serialization")
        service_type = self.type.startswith("text-analysis.service.")
        if service_type != isinstance(self.data, ServiceEventData):
            raise ValueError("Event type must match its service or request data")
        if isinstance(self.data, ServiceEventData):
            expected_type = {
                "starting": "text-analysis.service.started",
                "disabled": "text-analysis.service.started",
                "ready": "text-analysis.service.ready",
                "stopped": "text-analysis.service.stopped",
                "failed": "text-analysis.service.failed",
            }.get(self.data.status)
        else:
            expected_type = {
                "complete": "text-analysis.request.completed",
                "partial": "text-analysis.request.partial",
                "failed": "text-analysis.request.failed",
            }[self.data.result_status]
        if self.type != expected_type:
            raise ValueError("Event type must match its declared outcome")
        return self

    @model_serializer(mode="wrap")
    def serialize_without_nulls(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, object]:
        serialized = cast(dict[str, object], handler(self))
        return {key: value for key, value in serialized.items() if value is not None}
