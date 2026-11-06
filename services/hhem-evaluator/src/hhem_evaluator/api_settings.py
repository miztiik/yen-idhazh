"""How is the one named shared API configuration loaded without environment overrides?"""

from pathlib import Path

from pydantic import ValidationError

from hhem_evaluator.contracts.api_settings import ApiSettings


class ApiSettingsLoadError(ValueError):
    """Name an invalid shared setting without disclosing local paths or input."""


def load_api_settings(path: Path) -> ApiSettings:
    try:
        return ApiSettings.model_validate_json(path.read_bytes())
    except OSError:
        raise ApiSettingsLoadError("Could not read config/fastapi-server.json.") from None
    except ValidationError as error:
        failure = error.errors(include_input=False, include_context=False, include_url=False)[0]
        location = ".".join(str(part) for part in failure["loc"]) or "settings"
        raise ApiSettingsLoadError(f"Invalid summary evaluator setting {location}.") from None
