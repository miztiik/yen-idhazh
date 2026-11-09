"""Do real native API calls preserve application contracts and safe failure boundaries?"""

import asyncio
import io
import json
import logging
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from local_api_host.compose_applications import compose_applications
from local_api_host.contracts import HostSettings, ListenerSettings
from pydantic import ValidationError
from serve_apis import create_app as create_shared_app
from text_analysis.load_service_settings import load_service_settings

from gliner_api.configure_native_diagnostics import (
    NativeDiagnosticError,
    configure_native_diagnostics,
    filter_encoder_deprecation,
    native_operation,
)
from gliner_api.create_api_component import create_app
from gliner_api.declare_analysis_contracts import AnalyzeTextRequest
from gliner_api.declare_api_contracts import (
    ANALYZE_TEXT_PATH,
    API_VERSION,
    APPLICATION_TITLE,
    HEALTH_PATH,
    SCHEMA_PATH,
    ErrorResult,
    GlinerHealth,
    ResultValidationError,
)
from gliner_api.declare_event_contracts import GlinerEvent
from gliner_api.load_settings import GlinerSettings, load_settings
from gliner_api.run_model import ModelRuntime
from gliner_api.validate_analysis_results import validate_analysis_results

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def anyio_backend() -> str:
    """Use the event loop that owns the provider's asyncio tasks and locks."""
    return "asyncio"


@asynccontextmanager
async def _open_api_client(app: FastAPI, transport: HostSettings) -> AsyncIterator[AsyncClient]:
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=_base_url(transport)) as client,
    ):
        yield client


def _transport() -> HostSettings:
    existing = load_service_settings(ROOT).listener
    return HostSettings(
        title=APPLICATION_TITLE,
        schema_version=API_VERSION,
        health_path=HEALTH_PATH,
        schema_path=SCHEMA_PATH,
        listener=ListenerSettings(
            host=existing.host,
            port=existing.port,
            max_body_bytes=existing.max_body_bytes,
            body_read_timeout_ms=existing.body_read_timeout_ms,
        ),
        shutdown_timeout_ms=existing.shutdown_timeout_ms,
        propagate_trace_context=True,
    )


def _base_url(transport: HostSettings) -> str:
    return f"http://{transport.listener.host}:{transport.listener.port}"


def test_strict_settings_and_requests() -> None:
    settings = load_settings(ROOT)
    raw = settings.model_dump()
    with pytest.raises(ValidationError):
        GlinerSettings.model_validate(raw | {"model": raw["model"] | {"revision": "main"}})
    with pytest.raises(ValidationError):
        GlinerSettings.model_validate(raw | {"model": raw["model"] | {"repo": "bare-model"}})
    with pytest.raises(ValidationError):
        GlinerSettings.model_validate(
            raw | {"model": raw["model"] | {"base_url": "https://user:secret@example.invalid"}}
        )
    for body in (
        {"text": " ", "schema": {"entities": ["mention"]}},
        {"text": "a", "schema": {"entities": ["mention"]}, "model": "caller-selector"},
        {"text": "a", "schema": {"classifications": [{"task": "task", "labels": {"id": " "}}]}},
        {"text": "a", "schema": {"structures": {"entities": {"fields": [{"name": "actor"}]}}}},
        {
            "text": "a",
            "schema": {
                "relations": ["task"],
                "classifications": [{"task": "task", "labels": ["id"]}],
            },
        },
        {
            "text": "a",
            "schema": {"structures": {"event": {"fields": [{"name": "a"}, {"name": "a"}]}}},
        },
        {
            "text": "a",
            "schema": {
                "classifications": [{"task": "task", "labels": ["id"], "multi_label": 1}]
            },
        },
    ):
        with pytest.raises(ValidationError):
            AnalyzeTextRequest.model_validate_json(json.dumps(body), strict=True)
    request = AnalyzeTextRequest.model_validate_json(
        json.dumps(
            {
                "text": " a ",
                "schema": {"classifications": [{"task": "task", "labels": {"id": "definition"}}]},
            }
        )
    )
    assert request.text == " a "
    assert request.analysis_schema.to_native_schema().to_dict()["classifications"][0]["labels"] == {
        "id": "definition"
    }


def test_native_result_boundaries() -> None:
    request = AnalyzeTextRequest.model_validate_json(
        json.dumps(
            {
                "text": "a \u00e9 a",
                "schema": {
                    "entities": ["mention"],
                    "classifications": [{"task": "task", "labels": {"id": "definition"}}],
                    "structures": {
                        "event": {
                            "fields": [
                                {"name": "actor", "dtype": "str"},
                                {"name": "kind", "dtype": "str", "choices": ["selected"]},
                                {"name": "optional", "dtype": "str"},
                            ]
                        }
                    },
                    "relations": ["links"],
                },
            }
        ),
        strict=True,
    )
    mention = {"text": "a", "start": 0, "end": 1, "confidence": 1.0}
    unicode_mention = {"text": "\u00e9", "start": 2, "end": 3, "confidence": 0.8}
    selection = {"label": "id", "confidence": 1.0}
    record = {
        "actor": unicode_mention,
        "kind": {"text": "selected", "confidence": 0.5},
        "optional": None,
    }
    native = {
        "entities": {"mention": [mention, mention | {"start": 4, "end": 5}]},
        "task": selection,
        "event": [record],
        "relation_extraction": {"links": [{"head": mention, "tail": unicode_mention}]},
    }
    assert validate_analysis_results(native, request).model_dump() == {"result": native}
    empty = {"entities": {}, "task": [], "event": [], "relation_extraction": {"links": []}}
    assert validate_analysis_results(empty, request).model_dump() == {"result": empty}
    for prediction in (
        native | {"invented": []},
        {name: value for name, value in native.items() if name != "task"},
        native | {"entities": {"invented": [mention]}},
        native | {"entities": {"mention": [mention | {"end": 8}]}},
        native | {"entities": {"mention": [mention | {"text": "b"}]}},
        native | {"entities": {"mention": [mention | {"confidence": float("nan")}]}},
        native | {"task": selection | {"label": "invented"}},
        native | {"task": [selection, selection]},
        native | {"event": [record | {"kind": {"text": "invented", "confidence": 0.5}}]},
        native | {"event": [record | {"invented": None}]},
        native | {"relation_extraction": {"links": [{"head": mention, "tail": None}]}},
    ):
        with pytest.raises(ResultValidationError):
            validate_analysis_results(prediction, request)


@pytest.mark.anyio
async def test_unready_api_guards_schema_and_disabled_state(tmp_path: Path) -> None:
    settings = load_settings(ROOT)
    transport = _transport()
    events = io.StringIO()
    cold = create_app(settings, transport, root=tmp_path, stream=events)
    async with _open_api_client(cold, transport) as client:
        health = await client.get(HEALTH_PATH)
        assert health.status_code == 503
        assert GlinerHealth.model_validate_json(health.content).status == "failed"
        unavailable = await client.post(
            ANALYZE_TEXT_PATH, json={"text": "a", "schema": {"entities": ["mention"]}}
        )
        assert unavailable.status_code == 503
        assert (
            ErrorResult.model_validate_json(unavailable.content).error.code
            == "MODEL_UNAVAILABLE"
        )
        invalid = await client.post(
            ANALYZE_TEXT_PATH, json={"text": "unpublished-note", "schema": {}}
        )
        assert invalid.status_code == 422
        assert ErrorResult.model_validate_json(invalid.content).error.code == "INVALID_REQUEST"
        schema = (await client.get(SCHEMA_PATH)).json()
        assert schema["info"]["version"] == API_VERSION
        assert ANALYZE_TEXT_PATH in schema["paths"]
    assert "unpublished-note" not in events.getvalue()
    for line in events.getvalue().splitlines():
        GlinerEvent.model_validate_json(line)

    disabled = create_app(
        settings.model_copy(update={"enabled": False}),
        transport,
        root=tmp_path,
        stream=io.StringIO(),
    )
    async with _open_api_client(disabled, transport) as client:
        health = await client.get(HEALTH_PATH)
        assert health.status_code == 503
        assert GlinerHealth.model_validate_json(health.content).status == "disabled"
        refusal = await client.post(
            ANALYZE_TEXT_PATH, json={"text": "a", "schema": {"entities": ["mention"]}}
        )
        assert refusal.status_code == 503
        assert ErrorResult.model_validate_json(refusal.content).error.code == "SERVICE_DISABLED"


def test_composition_rejects_invalid_applications_and_shared_bounds() -> None:
    aggregate = create_shared_app(ROOT, stream=io.StringIO())
    spacy, gliner = aggregate.application_bindings
    settings = load_settings(ROOT)
    collision = create_app(
        settings, gliner.host_settings, root=ROOT, stream=io.StringIO()
    )
    different_listener = gliner.host_settings.model_copy(
        update={
            "listener": gliner.host_settings.listener.model_copy(
                update={
                    "max_body_bytes": gliner.host_settings.listener.max_body_bytes + 1
                }
            )
        }
    )
    mismatch = create_app(settings, different_listener, root=ROOT, stream=io.StringIO())

    async def close_events() -> None:
        for app in (spacy.app, gliner.app, collision, mismatch):
            await app.state.host_events.aclose()

    try:
        with pytest.raises(ValueError, match="At least one"):
            compose_applications(())
        with pytest.raises(TypeError, match="complete native"):
            compose_applications((FastAPI(),))
        with pytest.raises(ValueError, match="exactly once"):
            compose_applications((spacy.app, spacy.app))
        with pytest.raises(ValueError, match="must not collide"):
            compose_applications((gliner.app, collision))
        with pytest.raises(ValueError, match="share listener"):
            compose_applications((spacy.app, mismatch))
    finally:
        asyncio.run(close_events())


def test_native_diagnostic_refusal_survives_a_caught_exception() -> None:
    configure_native_diagnostics()
    handler_count = len(logging.getLogger("gliner2").handlers)
    configure_native_diagnostics()
    assert len(logging.getLogger("gliner2").handlers) == handler_count
    with (
        pytest.raises(NativeDiagnosticError),
        native_operation(),
        suppress(NativeDiagnosticError),
    ):
        logging.getLogger("gliner2.processor").warning("unpublished-native-diagnostic")
    with native_operation():
        logging.getLogger("gliner2.processor").info("discarded-native-info")
    deprecation = "`torch.jit.script` is deprecated. Please switch to `torch.compile`."
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        with filter_encoder_deprecation():
            warnings.warn_explicit(
                deprecation,
                FutureWarning,
                filename="torch/jit/_script.py",
                lineno=1,
                module="torch.jit._script",
            )
            warnings.warn_explicit(
                "unrelated-native-warning",
                FutureWarning,
                filename="torch/jit/_script.py",
                lineno=2,
                module="torch.jit._script",
            )
            warnings.warn_explicit(
                deprecation,
                FutureWarning,
                filename="unrelated_library.py",
                lineno=1,
                module="unrelated_library",
            )
            warnings.warn_explicit(
                deprecation,
                UserWarning,
                filename="torch/jit/_script.py",
                lineno=3,
                module="torch.jit._script",
            )
        warnings.warn_explicit(
            deprecation,
            FutureWarning,
            filename="torch/jit/_script.py",
            lineno=3,
            module="torch.jit._script",
        )
    assert [(type(item.message), str(item.message)) for item in observed] == [
        (FutureWarning, "unrelated-native-warning"),
        (FutureWarning, deprecation),
        (UserWarning, deprecation),
        (FutureWarning, deprecation),
    ]


def test_shutdown_preserves_latched_failure() -> None:
    runtime = ModelRuntime(load_settings(ROOT), ROOT, _transport().shutdown_timeout_ms)
    runtime.mark_failed("INVALID_RESULT")
    asyncio.run(runtime.shutdown())
    health = runtime.observe_health()
    assert health.status == "failed"
    assert health.error is not None
    assert health.error.code == "INVALID_RESULT"
