"""Prove native forwarding contracts and committed configuration without a model or socket."""

import io
import json
import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from hhem_evaluator.api_settings import load_api_settings
from hhem_evaluator.contracts.api_health import ApiHealth
from hhem_evaluator.contracts.api_settings import ApiSettings
from hhem_evaluator.contracts.base import API_PREFIX, EVALUATE_PATH
from hhem_evaluator.contracts.llama_request import LlamaRequest
from hhem_evaluator.contracts.llama_result import LlamaErrorResult, LlamaHealth, LlamaResult
from hhem_evaluator.contracts.llama_settings import LlamaSettings
from hhem_evaluator.contracts.server_contract import SERVER_SCHEMA_VERSION, ServerContract
from hhem_evaluator.contracts.server_event import ServerEvent
from hhem_evaluator.emit_events import EventWriter
from hhem_evaluator.forward_llama import LLAMA_COMPLETIONS_PATH
from hhem_evaluator.load_llama_settings import load_llama_settings
from hhem_evaluator.load_settings import load_settings
from hhem_evaluator.serve_api import create_app

from .contract_examples import API_SETTINGS_FILE, REPOSITORY, SETTINGS_FILE
from .llama_cases import generation_body


@pytest.mark.parametrize(
    "contract",
    [
        ApiSettings,
        ApiHealth,
        LlamaRequest,
        LlamaResult,
        LlamaErrorResult,
        LlamaHealth,
        LlamaSettings,
        ServerEvent,
    ],
)
def test_shared_native_schemas_are_current_only_and_change_logged(
    contract: type[ServerContract],
) -> None:
    schema = contract.model_json_schema()
    assert schema["version"] == SERVER_SCHEMA_VERSION
    assert schema["changelog"][0]["version"] == SERVER_SCHEMA_VERSION
    assert all("\n" not in entry["change"] for entry in schema["changelog"])


def test_native_parameters_are_validated_as_json_and_not_rewritten() -> None:
    request = LlamaRequest.model_validate_json(generation_body())
    assert request.messages[1].content == " PrivateSourceCanary\nunchanged. "
    assert request.__pydantic_extra__ is not None
    assert request.__pydantic_extra__["temperature"] == 0.2
    assert request.__pydantic_extra__["chat_template_kwargs"] == {"enable_thinking": False}
    for stream in (True, 1, None, "false"):
        payload = json.loads(generation_body())
        payload["stream"] = stream
        with pytest.raises(ValidationError):
            LlamaRequest.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf])
def test_nonfinite_request_extensions_are_rejected_at_every_json_depth(number: float) -> None:
    for extension in (number, {"values": [{"sampling": number}]}):
        payload = json.loads(generation_body())
        payload["native_controls"] = extension
        with pytest.raises(ValidationError, match="finite"):
            LlamaRequest.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf])
def test_nonfinite_native_usage_is_not_a_valid_result(number: float) -> None:
    path = REPOSITORY / "tests" / "fixtures" / "completions" / "reasoning-channel.json"
    payload = json.loads(path.read_bytes())
    payload["usage"]["total_tokens"] = number
    with pytest.raises(ValidationError, match="finite"):
        LlamaResult.model_validate_json(json.dumps(payload))


def test_selected_configuration_is_the_only_native_address_and_deadline_source(
    tmp_path: Path,
) -> None:
    config = tmp_path / "idhazh.json"
    models = tmp_path / "models"
    models.mkdir()
    declaration = models / "selected.json"
    declaration.write_text(
        json.dumps({"summarizer": {"request_timeout_minutes": 2.5}}), encoding="utf-8"
    )
    config.write_text(
        json.dumps(
            {
                "model_server": {"base_url": "http://127.0.0.1:8082"},
                "models_file": "models/selected.json",
            }
        ),
        encoding="utf-8",
    )
    selected = load_llama_settings(config)
    assert selected.base_url == "http://127.0.0.1:8082"
    assert selected.request_timeout_ms == 150_000
    declaration.write_text(
        json.dumps({"summarizer": {"request_timeout_minutes": 3.0}}), encoding="utf-8"
    )
    assert selected.request_timeout_ms == 150_000
    assert load_llama_settings(config).request_timeout_ms == 180_000
    actual = load_llama_settings(REPOSITORY / "config" / "idhazh.json")
    assert actual.base_url == "http://127.0.0.1:8080"
    assert actual.request_timeout_ms > 0


@pytest.mark.parametrize(
    "address",
    [
        "https://127.0.0.1:8080",
        "http://outside.invalid:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:8080/path",
        "http://127.0.0.1:8080?destination=other",
        "http://127.0.0.1:8080#fragment",
        "http://name:secret@127.0.0.1:8080",
    ],
)
def test_native_address_cannot_name_another_host_path_or_credentials(address: str) -> None:
    with pytest.raises(ValidationError):
        LlamaSettings(base_url=address, request_timeout_ms=5000)


def test_open_native_socket_without_successful_model_health_is_not_ready() -> None:
    with pytest.raises(ValidationError):
        LlamaHealth(status="ready", http_status=503, failure_code=None)
    with pytest.raises(ValidationError):
        LlamaHealth(status="ready", http_status=200, failure_code="UPSTREAM_NOT_READY")


def test_actual_composed_openapi_has_resolvable_native_schemas_without_starting_clients() -> None:
    shared = load_api_settings(API_SETTINGS_FILE)
    api = ApiSettings.model_validate_json(
        shared.model_copy(update={"enabled_routes": ("hhem", "llama")}).model_dump_json()
    )
    app = create_app(
        api,
        load_settings(SETTINGS_FILE, api),
        REPOSITORY,
        writer=EventWriter(api.logging, io.StringIO()),
    )
    assert app.state.forwarder.client is None
    assert app.state.controller.worker.process is None
    schema = app.openapi()
    assert LLAMA_COMPLETIONS_PATH in schema["paths"] and EVALUATE_PATH in schema["paths"]
    assert f"{API_PREFIX}/evaluate" not in schema["paths"]
    assert "/health" in schema["paths"]

    def references(value: object) -> Iterator[str]:
        if isinstance(value, dict):
            for name, child in value.items():
                if name == "$ref":
                    assert isinstance(child, str)
                    yield child
                else:
                    yield from references(child)
        elif isinstance(value, list):
            for child in value:
                yield from references(child)

    for reference in references(schema):
        prefix = "#/components/schemas/"
        assert reference.startswith(prefix), reference
        assert reference[len(prefix) :] in schema["components"]["schemas"], reference


def test_composed_and_native_ports_cannot_conflict_before_lifespan() -> None:
    shared = load_api_settings(API_SETTINGS_FILE)
    api = ApiSettings.model_validate_json(
        shared.model_copy(update={"enabled_routes": ("llama",)}).model_dump_json()
    )
    with pytest.raises(ValueError, match="port"):
        create_app(
            api,
            None,
            REPOSITORY,
            llama_settings=LlamaSettings(
                base_url=f"http://127.0.0.1:{api.listener.port}",
                request_timeout_ms=5000,
            ),
            writer=EventWriter(api.logging, io.StringIO()),
        )


def test_llama_only_construction_needs_no_hhem_settings_or_model(tmp_path: Path) -> None:
    shared = load_api_settings(API_SETTINGS_FILE)
    api = ApiSettings.model_validate_json(
        shared.model_copy(update={"enabled_routes": ("llama",)}).model_dump_json()
    )
    app = create_app(
        api,
        None,
        tmp_path,
        llama_settings=load_llama_settings(REPOSITORY / "config" / "idhazh.json"),
        writer=EventWriter(api.logging, io.StringIO()),
    )
    assert app.state.controller is None
    assert app.state.forwarder.client is None
    assert EVALUATE_PATH not in app.openapi()["paths"]
    assert LLAMA_COMPLETIONS_PATH in app.openapi()["paths"]
