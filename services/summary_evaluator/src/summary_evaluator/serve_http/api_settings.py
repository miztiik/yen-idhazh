"""How is one scorer's committed API configuration resolved without destination overrides?"""

from pathlib import Path
from typing import Annotated

from pydantic import Field, RootModel, ValidationError

from summary_evaluator.serve_http.contracts.api_deployment_settings import ApiDeploymentSettings
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent, ApiSettings


class ApiSettingsLoadError(ValueError):
    """Name an invalid shared setting without disclosing local paths or input."""


class ApiConfiguration(
    RootModel[
        Annotated[ApiDeploymentSettings | ApiSettings, Field(union_mode="left_to_right")]
    ]
):
    pass


def load_api_configuration(path: Path) -> ApiDeploymentSettings | ApiSettings:
    try:
        return ApiConfiguration.model_validate_json(path.read_bytes()).root
    except OSError:
        raise ApiSettingsLoadError("Could not read the named scorer API configuration.") from None
    except ValidationError:
        raise ApiSettingsLoadError("Invalid scorer API configuration.") from None


def resolve_scorer_api_settings(
    configuration: ApiDeploymentSettings | ApiSettings, scorer: ApiComponent
) -> ApiSettings:
    if isinstance(configuration, ApiSettings):
        return ApiSettings.model_validate_json(
            configuration.model_copy(update={"enabled_routes": (scorer,)}).model_dump_json()
        )
    return ApiSettings(
        version=configuration.version,
        listener=configuration.listeners[scorer],
        enabled_routes=(scorer,),
        logging=configuration.logging,
        log_directory=configuration.log_directory,
        shutdown_timeout_ms=configuration.shutdown_timeout_ms,
    )


def load_scorer_api_settings(path: Path, scorer: ApiComponent) -> ApiSettings:
    return resolve_scorer_api_settings(load_api_configuration(path), scorer)


def load_selected_api_settings(
    path: Path, routes: tuple[ApiComponent, ...] | None
) -> ApiSettings:
    return resolve_selected_api_settings(load_api_configuration(path), routes)


def resolve_selected_api_settings(
    configuration: ApiDeploymentSettings | ApiSettings,
    routes: tuple[ApiComponent, ...] | None,
) -> ApiSettings:
    if routes is None and isinstance(configuration, ApiSettings):
        routes = configuration.enabled_routes
    if routes is None or len(routes) != 1:
        raise ApiSettingsLoadError("Select exactly one scorer with --routes.")
    return resolve_scorer_api_settings(configuration, routes[0])


def load_api_settings(path: Path) -> ApiSettings:
    """Read a legacy effective snapshot; modern callers must explicitly name their scorer."""
    try:
        return ApiSettings.model_validate_json(path.read_bytes())
    except OSError:
        raise ApiSettingsLoadError("Could not read config/summary-evals/api.json.") from None
    except ValidationError as error:
        failure = error.errors(include_input=False, include_context=False, include_url=False)[0]
        location = ".".join(str(part) for part in failure["loc"]) or "settings"
        raise ApiSettingsLoadError(f"Invalid summary evaluator setting {location}.") from None
