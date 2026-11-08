"""Which committed settings select the local GLiNER2 model and diagnostic bounds?"""

from datetime import date
from pathlib import Path
from typing import Final, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, field_validator, model_validator

from gliner_api.configure_native_diagnostics import (
    NativeDiagnosticError,
    require_safe_import_controls,
)
from gliner_api.declare_api_contracts import API_VERSION, ApiContract

SETTINGS_PATH: Final = Path("config") / "text-analysis" / "gliner" / "settings.json"
MODEL_CACHE_PATH: Final = Path("services") / "text_analysis" / "gliner" / "var" / "models"


class SettingsLoadError(ValueError):
    """Report invalid configuration without retaining its path or contents."""


class SettingsChange(ApiContract):
    """Describe one supported dated settings-shape change."""

    version: str
    change: str = Field(min_length=1)

    @field_validator("version")
    @classmethod
    def require_utc_date_stamp(cls, value: str) -> str:
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError
        except ValueError:
            raise ValueError("Settings versions must be YYYY-MM-DD UTC dates") from None
        return value


class ModelSettings(ApiContract):
    """Select one complete Hub repository from one reviewed download endpoint."""

    repo: str
    base_url: str

    @field_validator("repo")
    @classmethod
    def require_full_hub_identifier(cls, value: str) -> str:
        try:
            require_safe_import_controls()
        except NativeDiagnosticError:
            raise ValueError("Native library import controls are invalid") from None
        from huggingface_hub.utils import HFValidationError, validate_repo_id

        try:
            validate_repo_id(value)
        except HFValidationError:
            raise ValueError("Model repository must be a valid full Hub identifier") from None
        if value.count("/") != 1:
            raise ValueError("Model repository must include its namespace")
        return value

    @field_validator("base_url")
    @classmethod
    def require_reviewed_https_endpoint(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError:
            raise ValueError("Model endpoint must be a safe HTTPS base URL") from None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (port is not None and not 1 <= port <= 65535)
            or any(character.isspace() for character in value)
        ):
            raise ValueError("Model endpoint must be a safe HTTPS base URL")
        return value


class LoggingSettings(ApiContract):
    """Bound only the provider's validated stderr events."""

    level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    max_event_bytes: int = Field(default=4096, gt=0)


class GlinerSettings(ApiContract):
    """Read model identity independently of listener or taxonomy configuration."""

    version: str = Field(json_schema_extra={"const": API_VERSION})
    changelog: list[SettingsChange] = Field(min_length=1, max_length=5)
    enabled: bool = True
    model: ModelSettings
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @model_validator(mode="after")
    def require_current_settings_shape(self) -> Self:
        versions = [entry.version for entry in self.changelog]
        if (
            self.version != API_VERSION
            or versions[0] != self.version
            or versions != sorted(set(versions), reverse=True)
        ):
            raise ValueError("Settings require the current dated shape and ordered changelog")
        return self


def load_settings(root: Path) -> GlinerSettings:
    """Read one named configuration file without environment overrides."""
    try:
        return GlinerSettings.model_validate_json((root / SETTINGS_PATH).read_bytes())
    except OSError:
        raise SettingsLoadError("Could not read the GLiNER configuration.") from None
    except ValidationError:
        raise SettingsLoadError("The GLiNER configuration is invalid.") from None
