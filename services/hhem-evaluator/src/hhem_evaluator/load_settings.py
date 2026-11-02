"""How is one explicitly named settings file read and frozen at startup?"""

from pathlib import Path

from pydantic import ValidationError

from .contracts.service_settings import ServiceSettings


class SettingsLoadError(ValueError):
    """Report a settings failure without exposing a filesystem path."""


def load_settings(path: Path) -> ServiceSettings:
    """Read only the supplied file; use no environment or source defaults."""
    try:
        content = path.read_bytes()
    except OSError:
        raise SettingsLoadError("Could not read the service settings file.") from None
    try:
        return ServiceSettings.model_validate_json(content)
    except ValidationError as error:
        failure = error.errors(include_input=False, include_context=False, include_url=False)[0]
        location = ".".join(str(part) for part in failure["loc"]) or "settings"
        raise SettingsLoadError(f"Invalid service setting {location}: {failure['msg']}") from None
