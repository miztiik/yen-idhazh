"""Which validated settings select the text-analysis runtime and its capabilities?"""

from collections.abc import Mapping
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue, SkipJsonSchema

SETTINGS_VERSION = "2026-11-09"
SettingsVersion = Literal["2026-11-07", "2026-11-08", "2026-11-09"]
RawFeatureName = Literal[
    "entities",
    "sentences",
    "relations",
    "noun_phrases",
    "linguistic_tokens",
    "document_metrics",
]
FeatureName = RawFeatureName | Literal["named_entities", "important_terms"]
LanguageCode = Literal["en", "zh", "ta"]
EnabledLanguage = Literal["en", "zh"]
ModelProfile = Literal["sm", "md", "lg"]
LoggingLevel = Literal["INFO", "WARNING", "ERROR"]

ALL_FEATURES: tuple[FeatureName, ...] = (
    "entities",
    "sentences",
    "relations",
    "noun_phrases",
    "linguistic_tokens",
    "document_metrics",
    "named_entities",
    "important_terms",
)
MODEL_PROFILES: tuple[ModelProfile, ...] = ("sm", "md", "lg")


def _normalize_json_tuple(value: object, info: ValidationInfo) -> object:
    return tuple(value) if info.mode == "json" and isinstance(value, list) else value


def _omit_default(schema: JsonSchemaValue) -> None:
    schema.pop("default", None)


FeatureSequence = Annotated[
    tuple[FeatureName, ...],
    BeforeValidator(_normalize_json_tuple),
]
TextSequence = Annotated[
    tuple[str, ...],
    BeforeValidator(_normalize_json_tuple),
]


class SettingsContract(BaseModel):
    """Reject undeclared or coercible production settings."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
    )


class SettingsChange(SettingsContract):
    """Describe one current settings-shape change."""

    version: SettingsVersion
    change: str = Field(min_length=1)


class ListenerSettings(SettingsContract):
    """Bind the one loopback listener and all request/lifespan bounds."""

    host: Literal["127.0.0.1"]
    port: int = Field(ge=1, le=65535)
    max_body_bytes: int = Field(gt=0)
    body_read_timeout_ms: int = Field(gt=0)
    shutdown_timeout_ms: int = Field(gt=0)


class ModelProfileSettings(SettingsContract):
    """Pin one installable spaCy model to its committed wheel destination."""

    package: str = Field(pattern=r"^(?:en|zh)_core_web_(?:sm|md|lg)$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    url: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_exact_model_wheel(self) -> Self:
        expected = (
            "https://github.com/explosion/spacy-models/releases/download/"
            f"{self.package}-{self.version}/{self.package}-{self.version}-py3-none-any.whl"
        )
        parsed = urlsplit(self.url)
        if (
            self.url != expected
            or parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Model URL must be the exact committed HTTPS wheel destination")
        return self


class LanguageSettings(SettingsContract):
    """Declare one language's enabled profiles and feature capabilities."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": SETTINGS_VERSION,
            "changelog": [
                {
                    "version": SETTINGS_VERSION,
                    "change": "Add optional per-language feature defaults.",
                }
            ],
        }
    )

    enabled: StrictBool
    default_profile: ModelProfile | None
    supported_features: FeatureSequence
    profiles: dict[ModelProfile, ModelProfileSettings]
    default_features: FeatureSequence | SkipJsonSchema[None] = Field(
        default=None,
        exclude_if=lambda value: value is None,
        json_schema_extra=_omit_default,
    )

    @model_validator(mode="before")
    @classmethod
    def refuse_null_default_features(cls, value: object) -> object:
        if isinstance(value, Mapping) and value.get("default_features", ...) is None:
            raise ValueError("Omit inherited default features instead of supplying null")
        return value

    @field_validator("default_features")
    @classmethod
    def require_distinct_default_features(
        cls, value: tuple[FeatureName, ...] | None
    ) -> tuple[FeatureName, ...] | None:
        if value is not None and (not value or len(set(value)) != len(value)):
            raise ValueError("Language default features must be nonempty and distinct")
        return value

    @field_validator("supported_features")
    @classmethod
    def require_distinct_supported_features(
        cls, value: tuple[FeatureName, ...]
    ) -> tuple[FeatureName, ...]:
        if len(set(value)) != len(value):
            raise ValueError("supported_features must be distinct")
        return value

    @model_validator(mode="after")
    def require_enabled_language_profiles(self) -> Self:
        if self.enabled:
            if self.default_profile is None or self.default_profile not in self.profiles:
                raise ValueError("Enabled languages require a configured default profile")
            if set(self.profiles) != set(MODEL_PROFILES):
                raise ValueError("Enabled languages must declare sm, md and lg profiles")
        elif (
            self.default_profile is not None
            or self.supported_features
            or self.profiles
            or self.default_features is not None
        ):
            raise ValueError("Disabled languages must not declare profiles or features")
        return self


class LanguageCatalog(SettingsContract):
    """Keep the exact language vocabulary explicit and ordered."""

    en: LanguageSettings
    zh: LanguageSettings
    ta: LanguageSettings

    def select(self, language: LanguageCode) -> LanguageSettings:
        return getattr(self, language)


class RelationRuleOverride(SettingsContract):
    """Override only named relation rules for one configured language."""

    action_pos: TextSequence | None = None
    actor_dependencies: TextSequence | None = None
    agent_dependency: str | None = None
    agent_object_dependency: str | None = None
    object_dependencies: TextSequence | None = None
    conjunction_dependency: str | None = None
    time_entity_labels: TextSequence | None = None
    place_entity_labels: TextSequence | None = None

    @model_validator(mode="before")
    @classmethod
    def refuse_explicit_nulls(cls, value: object) -> object:
        if isinstance(value, Mapping) and any(item is None for item in value.values()):
            raise ValueError("Omit absent relation overrides instead of supplying null")
        return value


class RelationPolicy(SettingsContract):
    """Hold the effective dependency and entity rules used by extraction."""

    action_pos: TextSequence
    actor_dependencies: TextSequence
    agent_dependency: str
    agent_object_dependency: str
    object_dependencies: TextSequence
    conjunction_dependency: str
    time_entity_labels: TextSequence
    place_entity_labels: TextSequence

    @model_validator(mode="after")
    def require_nonempty_distinct_rules(self) -> Self:
        sequences = (
            self.action_pos,
            self.actor_dependencies,
            self.object_dependencies,
            self.time_entity_labels,
            self.place_entity_labels,
        )
        if any(not values or len(set(values)) != len(values) for values in sequences):
            raise ValueError("Relation rule lists must be nonempty and distinct")
        if not self.agent_dependency or not self.agent_object_dependency:
            raise ValueError("Agent relation rules must be nonblank")
        if not self.conjunction_dependency:
            raise ValueError("The conjunction relation rule must be nonblank")
        return self


class RelationRules(RelationPolicy):
    """Apply one common relation policy with optional language-specific values."""

    language_overrides: dict[EnabledLanguage, RelationRuleOverride]

    def resolve(self, language: EnabledLanguage) -> RelationPolicy:
        override = self.language_overrides.get(language)
        if override is None:
            return RelationPolicy.model_validate(
                self.model_dump(exclude={"language_overrides"})
            )
        common = self.model_dump(exclude={"language_overrides"})
        common.update(override.model_dump(exclude_none=True))
        return RelationPolicy.model_validate(common)


class LoggingSettings(SettingsContract):
    """Bound validated stderr CloudEvents without declaring a file sink."""

    level: LoggingLevel
    max_event_bytes: int = Field(gt=0)


class NamedEntitiesSettings(SettingsContract):
    """Configure document-local name grouping and native-label presentation."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": SETTINGS_VERSION,
            "changelog": [
                {
                    "version": SETTINGS_VERSION,
                    "change": "Declare case normalization and named-entity label mapping.",
                }
            ],
        }
    )

    ignore_case: StrictBool = True
    label_map: dict[str, str] = Field(
        default_factory=lambda: {
            "PERSON": "person",
            "ORG": "organization",
            "GPE": "location",
            "LOC": "location",
        }
    )

    @field_validator("label_map")
    @classmethod
    def require_nonblank_mapping(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not label.strip() or not kind.strip() for label, kind in value.items()):
            raise ValueError("Named-entity labels and presentation types must be nonblank")
        return value


class ImportantTermsSettings(SettingsContract):
    """Configure English statistical phrase ranking without another model."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": SETTINGS_VERSION,
            "changelog": [
                {
                    "version": SETTINGS_VERSION,
                    "change": "Declare YAKE ranking, result limits and English stopwords.",
                }
            ],
        }
    )

    max_results: int = Field(default=25, ge=0)
    max_phrase_words: int = Field(default=3, ge=1)
    deduplication_threshold: float = Field(default=0.9, ge=0, le=1)
    deduplication_method: Literal["seqm", "jaro", "levs"] = "seqm"
    window_size: int = Field(default=1, ge=1)
    stopwords: TextSequence | None = None

    @field_validator("stopwords")
    @classmethod
    def require_distinct_stopwords(
        cls, value: tuple[str, ...] | None
    ) -> tuple[str, ...] | None:
        if value is not None and (
            not value
            or any(not word.strip() for word in value)
            or len({word.casefold() for word in value}) != len(value)
        ):
            raise ValueError("Custom English stopwords must be nonempty and distinct")
        return value


class ServiceSettings(SettingsContract):
    """Own the complete production configuration for text analysis."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
        json_schema_extra={
            "version": SETTINGS_VERSION,
            "changelog": [
                {
                    "version": SETTINGS_VERSION,
                    "change": "Add compact English feature settings and language defaults.",
                },
                {
                    "version": "2026-11-07",
                    "change": "Declare multilingual model, feature and runtime settings.",
                },
            ],
        },
    )

    version: SettingsVersion
    changelog: Annotated[
        tuple[SettingsChange, ...],
        BeforeValidator(_normalize_json_tuple),
    ]
    enabled: StrictBool = True
    listener: ListenerSettings
    max_concurrent_requests: int = Field(ge=1, le=2)
    spacy_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    default_features: FeatureSequence
    allowed_features: FeatureSequence
    languages: LanguageCatalog
    relation_rules: RelationRules
    named_entities: NamedEntitiesSettings = Field(default_factory=NamedEntitiesSettings)
    important_terms: ImportantTermsSettings = Field(default_factory=ImportantTermsSettings)
    logging: LoggingSettings

    def resolve_default_features(self, language: LanguageCode) -> tuple[FeatureName, ...]:
        """Inherit the recorded global order only when no language override exists."""
        override = self.languages.select(language).default_features
        return self.default_features if override is None else override

    @model_validator(mode="after")
    def require_current_complete_configuration(self) -> Self:
        if (
            not self.changelog
            or self.changelog[0].version != self.version
            or len({entry.version for entry in self.changelog}) != len(self.changelog)
            or len(self.changelog) > 5
        ):
            raise ValueError("Settings changelog must start at the current distinct version")
        if (
            not self.allowed_features
            or len(set(self.allowed_features)) != len(self.allowed_features)
        ):
            raise ValueError("allowed_features must be nonempty and distinct")
        if (
            not self.default_features
            or len(set(self.default_features)) != len(self.default_features)
            or not set(self.default_features).issubset(self.allowed_features)
        ):
            raise ValueError("default_features must be a nonempty distinct allowed subset")
        if not self.languages.en.enabled or not self.languages.zh.enabled:
            raise ValueError("English and Chinese must remain enabled")
        if self.languages.ta.enabled:
            raise ValueError("Tamil remains declared but unavailable")
        for language, settings in (
            ("en", self.languages.en),
            ("zh", self.languages.zh),
        ):
            if not set(settings.supported_features).issubset(self.allowed_features):
                raise ValueError(f"{language} features must be globally allowed")
            if settings.default_features is not None and not set(
                settings.default_features
            ).issubset(settings.supported_features):
                raise ValueError("Language defaults must be a supported feature subset")
            if language != "en" and set(settings.supported_features).intersection(
                {"named_entities", "important_terms"}
            ):
                raise ValueError("Compact entity and term features support English only")
            for profile, model in settings.profiles.items():
                expected_package = f"{language}_core_web_{profile}"
                if model.package != expected_package:
                    raise ValueError("Model package must match its language and profile")
        return self
