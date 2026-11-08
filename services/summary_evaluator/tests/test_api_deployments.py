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
from summary_evaluator.serve_http.contracts.api_settings import (
    API_SETTINGS_SCHEMA_VERSION,
    ApiComponent,
    ApiSettings,
)
from summary_evaluator.serve_http.contracts.previous_api_settings import (
    PreviousApiDeploymentSettings,
    PreviousApiSettings,
    PreviousTwoListenerApiDeploymentSettings,
)
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.worker_exit import WorkerExit


def deployment(*, previous: bool = False) -> dict[str, object]:
    return {
        "version": "2026-11-07" if previous else API_SETTINGS_SCHEMA_VERSION,
        "listeners": {
            scorer: {
                "host": "127.0.0.1",
                "port": port,
                "max_body_bytes": 1024,
                "body_read_timeout_ms": 1000,
            }
            for scorer, port in (
                (("hhem", 3010), ("unieval", 3011), ("coverage", 3012))
                if previous
                else (("hhem", 3010), ("unieval", 3011))
            )
        },
        "logging": {"level": "INFO", "max_event_bytes": 4096},
        "log_directory": "logs",
        "shutdown_timeout_ms": 15000,
        **({} if previous else {"propagate_trace_context": True}),
    }


def test_each_scorer_receives_only_its_declared_listener_and_route() -> None:
    configured = ApiDeploymentSettings.model_validate_json(json.dumps(deployment()))
    assert set(configured.listeners) == {"hhem", "unieval"}
    for scorer, listener in configured.listeners.items():
        selected = resolve_scorer_api_settings(configured, scorer)
        assert selected.listener == listener
        assert selected.enabled_routes == (scorer,)
        assert selected.logging == configured.logging
        assert selected.propagate_trace_context


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


def test_previous_three_listener_settings_resolve_only_authored_maintained_bindings() -> None:
    encoded = json.dumps(deployment(previous=True))
    with pytest.raises(ValidationError):
        ApiDeploymentSettings.model_validate_json(encoded)
    previous = ApiConfiguration.model_validate_json(encoded).root
    assert isinstance(previous, PreviousApiDeploymentSettings)
    scorers: tuple[ApiComponent, ...] = ("hhem", "unieval")
    for scorer in scorers:
        selected = resolve_scorer_api_settings(previous, scorer)
        assert selected.listener == previous.listeners[scorer]
        assert selected.enabled_routes == (scorer,)
        assert selected.logging == previous.logging
        assert selected.log_directory == previous.log_directory
        assert selected.shutdown_timeout_ms == previous.shutdown_timeout_ms
        assert not selected.propagate_trace_context


def test_previous_single_listener_selection_does_not_restore_coverage() -> None:
    configured = ApiDeploymentSettings.model_validate_json(json.dumps(deployment()))
    original = resolve_scorer_api_settings(configured, "hhem")
    payload = original.model_dump(mode="json")
    payload.update(version="2026-11-07", enabled_routes=["hhem", "unieval", "coverage"])
    del payload["propagate_trace_context"]
    previous = ApiConfiguration.model_validate_json(json.dumps(payload)).root
    assert isinstance(previous, PreviousApiSettings)
    selected = resolve_scorer_api_settings(previous, "unieval")
    assert selected.listener == original.listener
    assert selected.enabled_routes == ("unieval",)
    assert not selected.propagate_trace_context
    with pytest.raises(ApiSettingsLoadError, match="exactly one"):
        resolve_selected_api_settings(previous, None)
    coverage_only = previous.model_copy(update={"enabled_routes": ("coverage",)})
    with pytest.raises(ApiSettingsLoadError, match="maintained scorer"):
        resolve_selected_api_settings(coverage_only, None)


def test_single_listener_projection_revalidates_frozen_bounds() -> None:
    configured = ApiDeploymentSettings.model_validate_json(json.dumps(deployment()))
    single = resolve_scorer_api_settings(configured, "hhem")
    invalid = single.model_copy(update={"listener": single.listener.model_copy(update={"port": 0})})
    with pytest.raises(ValidationError):
        resolve_scorer_api_settings(invalid, "unieval")


@pytest.mark.parametrize("previous", [False, True])
@pytest.mark.parametrize("fault", ["missing", "unknown", "collision", "mixed", "version", "bound"])
def test_invalid_deployments_are_not_compatibility_fallbacks(previous: bool, fault: str) -> None:
    payload = deployment(previous=previous)
    listeners = payload["listeners"]
    assert isinstance(listeners, dict)
    if fault == "missing":
        del listeners["unieval"]
    elif fault == "unknown":
        listeners["unknown"] = listeners["hhem"]
    elif fault == "collision":
        listeners["coverage" if previous else "unieval"] = listeners["hhem"]
    elif fault == "mixed":
        payload["listener"] = listeners["hhem"]
    elif fault == "version":
        payload["version"] = "2026-11-05"
    else:
        listeners["coverage" if previous else "unieval"]["max_body_bytes"] = 0
    with pytest.raises(ValidationError):
        ApiConfiguration.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("previous", [False, True])
def test_retired_or_unknown_runtime_selection_cannot_choose_a_listener(previous: bool) -> None:
    configured = ApiConfiguration.model_validate_json(
        json.dumps(deployment(previous=previous))
    ).root
    selected = resolve_scorer_api_settings(configured, "hhem")
    for invalid in ("coverage", "unknown"):
        damaged = selected.model_copy(update={"enabled_routes": (invalid,)})
        with pytest.raises(ApiSettingsLoadError, match="maintained scorer"):
            resolve_selected_api_settings(configured, damaged.enabled_routes)


def test_modern_configuration_requires_an_explicit_singleton_selection() -> None:
    configured = ApiDeploymentSettings.model_validate_json(json.dumps(deployment()))
    with pytest.raises(ApiSettingsLoadError):
        resolve_selected_api_settings(configured, None)
    with pytest.raises(ApiSettingsLoadError):
        resolve_selected_api_settings(configured, ())
    with pytest.raises(ApiSettingsLoadError):
        resolve_selected_api_settings(configured, ("hhem", "unieval"))
    assert resolve_selected_api_settings(configured, ("unieval",)).enabled_routes == ("unieval",)


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
        ProcessIdentity(pid=1, start_ticks="1", pin_unavailable_reason="unsupported_platform")
    with pytest.raises(ValidationError):
        WorkerExit(pid=None, exit_code=None, confirmed=True)
    with pytest.raises(ValidationError):
        WorkerExit(pid=1, exit_code=0, confirmed=None)
    assert WorkerExit(pid=None, exit_code=None, confirmed=None).confirmed is None
    assert WorkerExit(pid=1, exit_code=-9, confirmed=True).exit_code == -9


def test_delivered_two_listener_settings_have_their_own_strict_frozen_reader() -> None:
    payload = deployment()
    payload["version"] = "2026-11-07"
    del payload["propagate_trace_context"]
    previous = ApiConfiguration.model_validate_json(json.dumps(payload)).root
    assert isinstance(previous, PreviousTwoListenerApiDeploymentSettings)
    with pytest.raises(ValidationError):
        PreviousApiDeploymentSettings.model_validate_json(json.dumps(payload))
    for scorer in ("hhem", "unieval"):
        selected = resolve_scorer_api_settings(previous, scorer)
        assert selected.version == API_SETTINGS_SCHEMA_VERSION
        assert not selected.propagate_trace_context
        assert selected.listener == previous.listeners[scorer]
    payload["propagate_trace_context"] = True
    with pytest.raises(ValidationError):
        ApiConfiguration.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("invalid", [None, 0, 1, "true", "false", [], {}])
def test_invalid_current_trace_modes_never_fall_back_to_frozen_settings(
    invalid: object,
) -> None:
    payload = deployment()
    payload["propagate_trace_context"] = invalid
    with pytest.raises(ValidationError):
        ApiConfiguration.model_validate_json(json.dumps(payload))
    del payload["propagate_trace_context"]
    with pytest.raises(ValidationError):
        ApiConfiguration.model_validate_json(json.dumps(payload))


def test_trace_mode_substitution_reaches_effective_and_host_settings() -> None:
    from summary_evaluator.serve_http.compose_api import create_host_settings

    for enabled in (True, False):
        payload = deployment()
        payload["propagate_trace_context"] = enabled
        configured = ApiConfiguration.model_validate_json(json.dumps(payload)).root
        selected = resolve_scorer_api_settings(configured, "hhem")
        assert selected.propagate_trace_context is enabled
        assert create_host_settings(selected).propagate_trace_context is enabled
