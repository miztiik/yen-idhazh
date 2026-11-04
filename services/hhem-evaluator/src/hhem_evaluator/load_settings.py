"""How is one explicitly named settings file read and frozen at startup?"""

import json
from pathlib import Path

from pydantic import JsonValue, TypeAdapter, ValidationError

from .api_settings import ApiSettingsLoadError, load_api_settings
from .contracts.api_settings import ApiSettings
from .contracts.service_settings import ServiceSettings


class SettingsLoadError(ValueError):
    """Report a settings failure without exposing a filesystem path."""


def load_settings(path: Path, api: ApiSettings | None = None) -> ServiceSettings:
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
                    f"Service setting {field} belongs in config/fastapi-server.json."
                )
        shared = api or load_api_settings(path.parent.parent / "fastapi-server.json")
        return ServiceSettings.model_validate_json(
            json.dumps(
                {
                    **authored,
                    "enabled": "hhem" in shared.enabled_routes,
                    "listener": shared.listener.model_dump(),
                    "logging": shared.logging.model_dump(),
                }
            )
        )
    except ApiSettingsLoadError:
        raise SettingsLoadError("Invalid shared settings in config/fastapi-server.json.") from None
    except ValidationError as error:
        failure = error.errors(include_input=False, include_context=False, include_url=False)[0]
        location = ".".join(str(part) for part in failure["loc"]) or "settings"
        raise SettingsLoadError(f"Invalid service setting {location}: {failure['msg']}") from None
