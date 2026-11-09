"""Do real native API calls preserve application contracts and safe failure boundaries?"""

import asyncio
import io
import json
import logging
import os
import sys
import warnings
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager, suppress
from pathlib import Path
from threading import Event, getprofile, setprofile_all_threads
from types import FrameType
from typing import Protocol, cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from local_api_host.compose_applications import compose_applications
from local_api_host.contracts import HostSettings, ListenerSettings
from local_api_host.propagate_trace_context import create_root_operation
from pydantic import ValidationError
from serve_apis import create_app as create_shared_app
from text_analysis.declare_api_contracts import (
    ANALYZE_TEXT_PATH as SPACY_NER_PATH,
)
from text_analysis.declare_api_contracts import (
    API_SCHEMA_VERSION as SPACY_SCHEMA_VERSION,
)
from text_analysis.declare_api_contracts import (
    HEALTH_PATH as SPACY_HEALTH_PATH,
)
from text_analysis.declare_api_contracts import (
    SCHEMA_PATH as SPACY_SCHEMA_PATH,
)
from text_analysis.declare_api_contracts import (
    AnalysisResult,
    AnalyzeTextRequest,
    TextAnalysisEvent,
    TextAnalysisHealth,
)
from text_analysis.declare_api_contracts import (
    ErrorResult as SpacyErrorResult,
)
from text_analysis.load_service_settings import load_service_settings

from gliner_api.classify_text import normalize_classifications
from gliner_api.configure_native_diagnostics import (
    NativeDiagnosticError,
    configure_native_diagnostics,
    filter_encoder_deprecation,
    native_operation,
)
from gliner_api.create_api_component import create_app
from gliner_api.declare_api_contracts import (
    API_VERSION,
    APPLICATION_TITLE,
    CLASSIFY_PATH,
    HEALTH_PATH,
    NER_PATH,
    SCHEMA_PATH,
    ClassificationRequest,
    ClassificationResult,
    ErrorResult,
    GlinerHealth,
    NerRequest,
    NerResult,
    ResultValidationError,
)
from gliner_api.declare_event_contracts import GlinerEvent, RequestEventData
from gliner_api.emit_events import EventEmitter
from gliner_api.extract_entities import extract_entities, normalize_entities
from gliner_api.load_model import NativeModel
from gliner_api.load_settings import GlinerSettings, load_settings
from gliner_api.run_model import ModelRuntime, OperationError

ROOT = Path(__file__).resolve().parents[4]


class _NativeProcessor(Protocol):
    def collate_fn_inference(self, batch: list[tuple[str, object]]) -> object: ...


class _NativeProcessingModel(NativeModel, Protocol):
    processor: _NativeProcessor


@pytest.fixture
def anyio_backend() -> str:
    """Use the event loop that owns the provider's asyncio tasks and locks."""
    return "asyncio"


@contextmanager
def _trace_warning_calls() -> Iterator[list[list[str]]]:
    calls: list[list[str]] = []
    previous_threads = getprofile()
    previous_current = sys.getprofile()

    def observe(frame: FrameType, event: str, value: object) -> None:
        if event != "c_call" or value is not warnings.warn:
            return
        stack: list[str] = []
        cursor: FrameType | None = frame
        while cursor is not None and len(stack) < 32:
            module = cursor.f_globals.get("__name__")
            if isinstance(module, str):
                stack.append(f"{module}.{cursor.f_code.co_qualname}:{cursor.f_lineno}")
            cursor = cursor.f_back
        calls.append(stack)

    setprofile_all_threads(observe)
    try:
        yield calls
    finally:
        setprofile_all_threads(previous_threads)
        sys.setprofile(previous_current)


@asynccontextmanager
async def _open_api_client(app: FastAPI, transport: HostSettings) -> AsyncIterator[AsyncClient]:
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=_base_url(transport)) as client,
    ):
        yield client


async def _verify_cancelled_native_ownership(
    runtime: ModelRuntime, request: NerRequest, settings: GlinerSettings
) -> None:
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    release = Event()
    first_finished = Event()
    second_entered = Event()
    events = io.StringIO()
    emitter = EventEmitter(settings.logging, events)
    unhandled: list[dict[str, object]] = []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: unhandled.append(context))

    def cancelled_operation(native: NativeModel) -> NerResult:
        loop.call_soon_threadsafe(entered.set)
        try:
            release.wait()
            processor = cast(_NativeProcessingModel, native).processor
            processor.collate_fn_inference([("x", None)])
            return extract_entities(native, request)
        finally:
            first_finished.set()

    def next_operation(native: NativeModel) -> NerResult:
        second_entered.set()
        return extract_entities(native, request)

    async def terminal(outcome: NerResult | OperationError) -> None:
        await emitter.emit(
            create_root_operation(),
            "gliner.request.failed"
            if isinstance(outcome, OperationError)
            else "gliner.request.completed",
            RequestEventData(
                operation="run-ner-gliner",
                status="failed" if isinstance(outcome, OperationError) else "complete",
                error_code=outcome.code if isinstance(outcome, OperationError) else None,
            ),
        )

    first = asyncio.create_task(runtime.execute(cancelled_operation, terminal=terminal))
    second: asyncio.Task[NerResult] | None = None
    shutdown: asyncio.Task[None] | None = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=runtime.shutdown_timeout_ms / 1000)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert runtime.lock.locked()
        assert not first_finished.is_set()
        second = asyncio.create_task(runtime.execute(next_operation, terminal=terminal))
        await asyncio.sleep(0)
        assert not second_entered.is_set()
        shutdown = asyncio.create_task(runtime.shutdown())
        await asyncio.sleep(0)
        assert not shutdown.done()
        assert runtime.model is not None
        release.set()
        await shutdown
        result = await second
        assert result.entities
        await asyncio.sleep(0)
        assert first_finished.is_set()
        assert second_entered.is_set()
        assert runtime.model is None
        records = [
            GlinerEvent.model_validate_json(line) for line in events.getvalue().splitlines()
        ]
        assert [record.type for record in records] == [
            "gliner.request.failed",
            "gliner.request.completed",
        ]
        assert isinstance(records[0].data, RequestEventData)
        assert records[0].data.error_code == "INPUT_UNSUPPORTED"
        assert not unhandled
    finally:
        release.set()
        if second is not None:
            await asyncio.gather(second, return_exceptions=True)
        if shutdown is not None:
            await shutdown
        else:
            await runtime.shutdown()
        loop.set_exception_handler(previous_handler)
        await emitter.aclose()


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
        {"text": " ", "labels": ["mention"]},
        {"text": "a", "labels": ["mention", "mention"]},
        {"text": "a", "labels": []},
        {"text": "a", "labels": ["mention"], "model": "caller-selector"},
    ):
        with pytest.raises(ValidationError):
            NerRequest.model_validate(body)
    with pytest.raises(ValidationError):
        ClassificationRequest.model_validate(
            {"text": "a", "tasks": {"task": {"labels": {"id": "definition"}, "multi_label": 1}}}
        )
    request = NerRequest(text=" a ", labels=["mention"])
    assert request.text == " a "


def test_native_result_boundaries() -> None:
    request = NerRequest(text="a", labels=["mention"])
    mention = {"text": "a", "start": 0, "end": 1, "confidence": 1.0}
    result = normalize_entities({"entities": {"mention": [mention]}}, request)
    assert set(result.model_dump()) == {"entities"}
    assert normalize_entities({"entities": {}}, request).entities == []
    for prediction in (
        {"entities": {"invented": [mention]}},
        {"entities": {"mention": [mention | {"end": 2}]}},
        {"entities": {"mention": [mention | {"text": "b"}]}},
        {"entities": {"mention": [mention | {"confidence": float("nan")}]}},
    ):
        with pytest.raises(ResultValidationError):
            normalize_entities(prediction, request)
    classification = ClassificationRequest.model_validate(
        {"text": "a", "tasks": {"task": {"labels": {"id": "definition"}, "multi_label": False}}}
    )
    selection = {"label": "id", "confidence": 1.0}
    normalized = normalize_classifications({"task": selection}, classification)
    assert set(normalized.model_dump()) == {"classifications"}
    for classification_prediction in (
        {},
        {"task": selection | {"label": "invented"}},
        {"task": [selection, selection]},
        {"task": selection | {"confidence": float("inf")}},
    ):
        with pytest.raises(ResultValidationError):
            normalize_classifications(classification_prediction, classification)


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
        unavailable = await client.post(NER_PATH, json={"text": "a", "labels": ["mention"]})
        assert unavailable.status_code == 503
        assert (
            ErrorResult.model_validate_json(unavailable.content).error.code
            == "MODEL_UNAVAILABLE"
        )
        invalid = await client.post(
            CLASSIFY_PATH, json={"text": "unpublished-note", "tasks": {}}
        )
        assert invalid.status_code == 422
        assert ErrorResult.model_validate_json(invalid.content).error.code == "INVALID_REQUEST"
        schema = (await client.get(SCHEMA_PATH)).json()
        assert schema["info"]["version"] == API_VERSION
        assert {NER_PATH, CLASSIFY_PATH, HEALTH_PATH, SCHEMA_PATH}.issuperset(schema["paths"])
        assert {"NerRequest", "ClassificationRequest"} <= schema["components"]["schemas"].keys()
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
            filename="torch/jit/_script.py",
            lineno=3,
            module="torch.jit._script",
        )
    assert [str(item.message) for item in observed] == [
        "unrelated-native-warning",
        deprecation,
    ]


def test_shutdown_preserves_latched_failure() -> None:
    runtime = ModelRuntime(load_settings(ROOT), ROOT, _transport().shutdown_timeout_ms)
    runtime.mark_failed("INVALID_RESULT")
    asyncio.run(runtime.shutdown())
    health = runtime.observe_health()
    assert health.status == "failed"
    assert health.error is not None
    assert health.error.code == "INVALID_RESULT"


@pytest.mark.anyio
async def test_real_prepared_model_api(capsys: pytest.CaptureFixture[str]) -> None:
    settings = load_settings(ROOT)
    transport = _transport()
    events = io.StringIO()
    app = create_shared_app(ROOT, stream=events)
    text = " \U0001f4f0 A research team announced a new language model in London. "
    ner_request = NerRequest(text=text, labels=["location", "technology"])
    spacy_request = AnalyzeTextRequest.model_validate(
        {
            "text": text,
            "language": os.environ["TEXT_ANALYSIS_LANGUAGE"],
            "model_profile": os.environ["TEXT_ANALYSIS_PROFILE"],
        }
    )
    taxonomy = json.loads((ROOT / "config" / "taxonomy.json").read_bytes())
    tasks = {
        name: {
            "labels": {
                entry["id"]: entry["definition"]
                for entry in taxonomy[group]
                if entry["status"] == "active"
            },
            "multi_label": multi_label,
        }
        for name, group, multi_label in (
            ("desk", "verticals", False),
            ("lenses", "lenses", True),
            ("events", "events", True),
        )
    }
    classification_request = ClassificationRequest.model_validate({"text": text, "tasks": tasks})
    carrier = {
        "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
        "tracestate": "test=one",
    }
    with _trace_warning_calls() as warning_calls:
        async with _open_api_client(app, transport) as client:
            health = await client.get(HEALTH_PATH)
            assert health.status_code == 200, (
                "Prepare the configured model before running this test."
            )
            assert GlinerHealth.model_validate_json(health.content).status == "ready"
            spacy_health_response = await client.get(SPACY_HEALTH_PATH)
            assert spacy_health_response.status_code == 200
            spacy_health = TextAnalysisHealth.model_validate_json(spacy_health_response.content)
            assert spacy_health.status == "ready"
            capability = next(
                item for item in spacy_health.languages if item.language == spacy_request.language
            )
            existing = load_service_settings(ROOT)
            assert capability.default_features == existing.resolve_default_features(
                spacy_request.language
            )
            assert capability.important_terms_limit == (
                existing.important_terms.max_results
                if "important_terms" in capability.supported_features
                else None
            )
            spacy_response = await client.post(
                SPACY_NER_PATH,
                json=spacy_request.model_dump(mode="json", exclude_none=True),
                headers=carrier,
            )
            assert spacy_response.status_code == 200
            spacy_result = AnalysisResult.model_validate_json(spacy_response.content)
            assert set(spacy_response.json()) == set(AnalysisResult.model_fields)
            assert (
                tuple(item.feature for item in spacy_result.features)
                == capability.default_features
            )
            assert all(item.status == "complete" for item in spacy_result.features)
            assert spacy_result.language == spacy_request.language
            assert spacy_result.model.profile == spacy_request.model_profile
            for path, error_model in (
                (NER_PATH, ErrorResult),
                (SPACY_NER_PATH, SpacyErrorResult),
            ):
                for headers, code in (
                    ({"origin": "https://example.invalid"}, "ORIGIN_FORBIDDEN"),
                    ({"host": "example.invalid"}, "HOST_FORBIDDEN"),
                ):
                    refusal = await client.post(path, content=b"\xff", headers=headers)
                    assert refusal.status_code == 403
                    assert error_model.model_validate_json(refusal.content).error.code == code
                    assert "traceparent" in refusal.headers
                too_large = await client.post(
                    path,
                    content=b" ",
                    headers={
                        "content-type": "application/json",
                        "content-length": str(transport.listener.max_body_bytes + 1),
                    },
                )
                assert too_large.status_code == 413
                wrong_method = await client.get(path)
                assert wrong_method.status_code == 405
                assert wrong_method.headers["allow"] == "POST"
                assert "traceparent" in wrong_method.headers
                wrong_path = await client.get(path + "/")
                assert wrong_path.status_code == 404
                assert "traceparent" in wrong_path.headers
                if path == NER_PATH:
                    assert (
                        ErrorResult.model_validate_json(wrong_path.content).error.code
                        == "NOT_FOUND"
                    )
            gliner_schema = (await client.get(SCHEMA_PATH)).json()
            spacy_schema = (await client.get(SPACY_SCHEMA_PATH)).json()
            assert gliner_schema["info"]["version"] == API_VERSION
            assert spacy_schema["info"]["version"] == SPACY_SCHEMA_VERSION
            assert {NER_PATH, CLASSIFY_PATH, HEALTH_PATH}.issubset(gliner_schema["paths"])
            assert {SPACY_NER_PATH, SPACY_HEALTH_PATH}.issubset(spacy_schema["paths"])
            assert SPACY_NER_PATH not in gliner_schema["paths"]
            assert NER_PATH not in spacy_schema["paths"]
            assert {"NerRequest", "ClassificationRequest"} <= (
                gliner_schema["components"]["schemas"].keys()
            )
            assert "AnalyzeTextRequest" in spacy_schema["components"]["schemas"]
            assert {"default_features", "important_terms_limit"} <= (
                spacy_schema["components"]["schemas"]["LanguageCapability"]["properties"].keys()
            )
            ner_response = await client.post(
                NER_PATH, json=ner_request.model_dump(), headers=carrier
            )
            assert ner_response.status_code == 200
            ner_result = NerResult.model_validate_json(ner_response.content)
            assert set(ner_response.json()) == {"entities"}
            assert ner_result.entities
            for mention in ner_result.entities:
                assert text[mention.start_char : mention.end_char] == mention.text
                assert mention.label in ner_request.labels
            native_gliner = next(
                binding.app
                for binding in app.application_bindings
                if binding.host_settings.health_path == HEALTH_PATH
            )
            runtime = cast(ModelRuntime, native_gliner.state.component.state)

            def refuse_native_record(native: NativeModel) -> object:
                processor = cast(_NativeProcessingModel, native).processor
                return processor.collate_fn_inference([("x", None)])

            with pytest.raises(OperationError) as refused:
                await runtime.execute(refuse_native_record)
            assert refused.value.code == "INPUT_UNSUPPORTED"
            classification_response = await client.post(
                CLASSIFY_PATH, json=classification_request.model_dump(), headers=carrier
            )
            assert classification_response.status_code == 200
            result = ClassificationResult.model_validate_json(classification_response.content)
            assert set(classification_response.json()) == {"classifications"}
            assert result.classifications.keys() == classification_request.tasks.keys()
            assert len(result.classifications["desk"]) == 1
            for name, selected in result.classifications.items():
                assert all(
                    label.id in classification_request.tasks[name].labels for label in selected
                )
            assert (await client.get(HEALTH_PATH)).status_code == 200
            await _verify_cancelled_native_ownership(runtime, ner_request, settings)
            assert (await client.get(HEALTH_PATH)).status_code == 503
            assert (await client.get(SPACY_HEALTH_PATH)).status_code == 200
    records = [GlinerEvent.model_validate_json(line) for line in events.getvalue().splitlines()]
    assert any(record.type == "gliner.service.ready" for record in records)
    completed = [record for record in records if record.type == "gliner.request.completed"]
    assert [record.traceparent for record in completed] == [
        ner_response.headers["traceparent"],
        classification_response.headers["traceparent"],
    ]
    assert all(record.tracestate == carrier["tracestate"] for record in completed)
    spacy_events = capsys.readouterr().err
    spacy_records = [
        TextAnalysisEvent.model_validate_json(line) for line in spacy_events.splitlines()
    ]
    assert any(record.type == "text-analysis.service.ready" for record in spacy_records)
    assert any(record.type == "text-analysis.service.stopped" for record in spacy_records)
    spacy_completed = [
        record for record in spacy_records if record.type == "text-analysis.request.completed"
    ]
    assert [record.traceparent for record in spacy_completed] == [
        spacy_response.headers["traceparent"]
    ]
    assert all(record.tracestate == carrier["tracestate"] for record in spacy_completed)
    assert text not in spacy_events
    assert text not in events.getvalue()
    assert all(
        definition not in events.getvalue()
        for task in classification_request.tasks.values()
        for definition in task.labels.values()
    )
    with capsys.disabled():
        print(json.dumps({"native_warning_calls": warning_calls}))
