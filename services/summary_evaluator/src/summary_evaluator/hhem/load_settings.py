"""How is HHEM scoring configured with an already resolved listener snapshot?"""

import json
from pathlib import Path

from pydantic import JsonValue, TypeAdapter, ValidationError

from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.shared.contracts.service_settings import ListenerSettings, LoggingSettings


class SettingsLoadError(ValueError):
    """Report a settings failure without exposing a filesystem path."""


def load_settings(
    path: Path, listener: ListenerSettings, logging: LoggingSettings, *, enabled: bool
) -> ServiceSettings:
    """Compose two named files into the unchanged private worker snapshot."""
    try:
        content = path.read_bytes()
    except OSError:
        raise SettingsLoadError("Could not read the service settings file.") from None
    try:
        authored = TypeAdapter(dict[str, JsonValue]).validate_json(content)
        for field in ("enabled", "listener", "logging"):
            if field in authored:
                raise SettingsLoadError(
                    f"Service setting {field} belongs in config/summary-evals/api.json."
                )
        return ServiceSettings.model_validate_json(
            json.dumps(
                {
                    **authored,
                    "enabled": enabled,
                    "listener": listener.model_dump(),
                    "logging": logging.model_dump(),
                }
            )
        )
    except ValidationError as error:
        failure = error.errors(include_input=False, include_context=False, include_url=False)[0]
        location = ".".join(str(part) for part in failure["loc"]) or "settings"
        raise SettingsLoadError(f"Invalid service setting {location}: {failure['msg']}") from None
