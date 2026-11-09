"""How is the one committed text-analysis configuration loaded without overrides?"""

from pathlib import Path

from pydantic import ValidationError

from text_analysis.declare_service_settings import ServiceSettings

SETTINGS_PATH = Path("config") / "text-analysis" / "settings.json"


class ServiceSettingsLoadError(ValueError):
    """Name an unreadable or invalid configuration without exposing its path."""


def load_service_settings(root: Path) -> ServiceSettings:
    """Read current or previous settings without changing their recorded defaults."""
    try:
        return ServiceSettings.model_validate_json((root / SETTINGS_PATH).read_bytes())
    except OSError:
        raise ServiceSettingsLoadError(
            "Could not read the text-analysis configuration."
        ) from None
    except ValidationError:
        raise ServiceSettingsLoadError(
            "The text-analysis configuration is invalid."
        ) from None
