"""Do explicit scorer selections resolve strict, independent, committed API listeners?"""

import json

import pytest
from pydantic import ValidationError

from summary_evaluator.serve_http.api_settings import (
    ApiConfiguration,
    ApiSettingsLoadError,
    resolve_scorer_api_settings,
    resolve_selected_api_settings,
)
from summary_evaluator.serve_http.contracts.api_deployment_settings import ApiDeploymentSettings
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.worker_exit import WorkerExit


def deployment() -> dict[str, object]:
    return {
        "version": "2026-11-07",
        "listeners": {
            scorer: {
                "host": "127.0.0.1",
                "port": port,
                "max_body_bytes": 1024,
                "body_read_timeout_ms": 1000,
            }
            for scorer, port in (("hhem", 3010), ("unieval", 3011), ("coverage", 3012))
        },
        "logging": {"level": "INFO", "max_event_bytes": 4096},
        "log_directory": "logs",
        "shutdown_timeout_ms": 15000,
    }


def test_each_scorer_receives_only_its_declared_listener_and_route() -> None:
    configured = ApiDeploymentSettings.model_validate_json(json.dumps(deployment()))
    for scorer, listener in configured.listeners.items():
        selected = resolve_scorer_api_settings(configured, scorer)
        assert selected.listener == listener
        assert selected.enabled_routes == (scorer,)
        assert selected.logging == configured.logging


def test_legacy_settings_are_explicitly_projected_without_new_destinations() -> None:
    configured = ApiDeploymentSettings.model_validate_json(json.dumps(deployment()))
    original = resolve_scorer_api_settings(configured, "hhem").model_copy(
        update={"enabled_routes": ("hhem", "unieval")}
    )
    legacy = ApiConfiguration.model_validate_json(original.model_dump_json()).root
    assert isinstance(legacy, ApiSettings)
    selected = resolve_scorer_api_settings(legacy, "unieval")
    assert selected.listener == original.listener
    assert selected.enabled_routes == ("unieval",)


def test_colliding_or_incomplete_deployments_are_not_legacy_fallbacks() -> None:
    configured = ApiDeploymentSettings.model_validate_json(json.dumps(deployment()))
    colliding = configured.model_copy(
        update={"listeners": {**configured.listeners, "unieval": configured.listeners["hhem"]}}
    )
    with pytest.raises(ValidationError):
        ApiConfiguration.model_validate_json(colliding.model_dump_json())
    incomplete = configured.model_copy(update={"listeners": {"hhem": configured.listeners["hhem"]}})
    with pytest.raises(ValidationError):
        ApiConfiguration.model_validate_json(incomplete.model_dump_json())
    mixed = deployment()
    mixed["listener"] = configured.listeners["hhem"].model_dump(mode="json")
    with pytest.raises(ValidationError):
        ApiConfiguration.model_validate_json(json.dumps(mixed))


def test_modern_configuration_requires_an_explicit_singleton_selection() -> None:
    configured = ApiDeploymentSettings.model_validate_json(json.dumps(deployment()))
    with pytest.raises(ApiSettingsLoadError):
        resolve_selected_api_settings(configured, None)
    with pytest.raises(ApiSettingsLoadError):
        resolve_selected_api_settings(configured, ())
    with pytest.raises(ApiSettingsLoadError):
        resolve_selected_api_settings(configured, ("hhem", "unieval"))
    assert resolve_selected_api_settings(configured, ("coverage",)).enabled_routes == ("coverage",)


def test_unambiguous_legacy_selection_remains_explicit_in_its_authored_settings() -> None:
    configured = ApiDeploymentSettings.model_validate_json(json.dumps(deployment()))
    single = resolve_scorer_api_settings(configured, "hhem")
    assert resolve_selected_api_settings(single, None) == single
    multiple = single.model_copy(update={"enabled_routes": ("hhem", "unieval")})
    with pytest.raises(ApiSettingsLoadError):
        resolve_selected_api_settings(multiple, None)
    chosen = resolve_selected_api_settings(multiple, ("unieval",))
    assert chosen.listener == single.listener and chosen.enabled_routes == ("unieval",)


def test_process_and_worker_exit_contracts_do_not_invent_observations() -> None:
    with pytest.raises(ValidationError):
        ProcessIdentity(pid=1, start_ticks=None, pin_unavailable_reason=None)
    with pytest.raises(ValidationError):
        ProcessIdentity(
            pid=1, start_ticks="1", pin_unavailable_reason="unsupported_platform"
        )
    with pytest.raises(ValidationError):
        WorkerExit(pid=None, exit_code=None, confirmed=True)
    with pytest.raises(ValidationError):
        WorkerExit(pid=1, exit_code=0, confirmed=None)
    assert WorkerExit(pid=None, exit_code=None, confirmed=None).confirmed is None
    assert WorkerExit(pid=1, exit_code=-9, confirmed=True).exit_code == -9
