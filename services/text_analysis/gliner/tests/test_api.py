"""Do real native API calls preserve application contracts and safe failure boundaries?"""

import io
import json
import logging
from contextlib import suppress
from pathlib import Path
from typing import Protocol, cast

import pytest
from fastapi.testclient import TestClient
from local_api_host.contracts import HostSettings, ListenerSettings
from pydantic import ValidationError

from gliner_api.classify_text import normalize_classifications
from gliner_api.configure_native_diagnostics import (
    NativeDiagnosticError,
    configure_native_diagnostics,
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
from gliner_api.declare_event_contracts import GlinerEvent
from gliner_api.extract_entities import normalize_entities
from gliner_api.load_model import NativeModel
from gliner_api.load_settings import GlinerSettings, load_settings
from gliner_api.run_model import ModelRuntime, OperationError
from text_analysis.load_service_settings import load_service_settings

ROOT = Path(__file__).resolve().parents[4]


class _NativeProcessor(Protocol):
    def collate_fn_inference(self, batch: list[tuple[str, object]]) -> object: ...


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
    for prediction in (
        {},
        {"task": selection | {"label": "invented"}},
        {"task": [selection, selection]},
        {"task": selection | {"confidence": float("inf")}},
    ):
        with pytest.raises(ResultValidationError):
            normalize_classifications(prediction, classification)


def test_unready_api_guards_schema_and_disabled_state(tmp_path: Path) -> None:
    settings = load_settings(ROOT)
    transport = _transport()
    events = io.StringIO()
    cold = create_app(settings, transport, root=tmp_path, stream=events)
    with TestClient(cold, base_url=_base_url(transport)) as client:
        health = client.get(HEALTH_PATH)
        assert health.status_code == 503
        assert GlinerHealth.model_validate_json(health.content).status == "failed"
        unavailable = client.post(NER_PATH, json={"text": "a", "labels": ["mention"]})
        assert unavailable.status_code == 503
        assert (
            ErrorResult.model_validate_json(unavailable.content).error.code
            == "MODEL_UNAVAILABLE"
        )
        invalid = client.post(
            CLASSIFY_PATH, json={"text": "unpublished-note", "tasks": {}}
        )
        assert invalid.status_code == 422
        assert ErrorResult.model_validate_json(invalid.content).error.code == "INVALID_REQUEST"
        for headers, code in (
            ({"origin": "https://example.invalid"}, "ORIGIN_FORBIDDEN"),
            ({"host": "example.invalid"}, "HOST_FORBIDDEN"),
        ):
            refusal = client.post(NER_PATH, content=b"\xff", headers=headers)
            assert refusal.status_code == 403
            assert ErrorResult.model_validate_json(refusal.content).error.code == code
        too_large = client.post(
            NER_PATH,
            content=b" ",
            headers={
                "content-type": "application/json",
                "content-length": str(transport.listener.max_body_bytes + 1),
            },
        )
        assert too_large.status_code == 413
        wrong_method = client.get(NER_PATH)
        assert wrong_method.status_code == 405
        assert wrong_method.headers["allow"] == "POST"
        assert client.get(NER_PATH + "/").status_code == 404
        schema = client.get(SCHEMA_PATH).json()
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
    with TestClient(disabled, base_url=_base_url(transport)) as client:
        health = client.get(HEALTH_PATH)
        assert health.status_code == 503
        assert GlinerHealth.model_validate_json(health.content).status == "disabled"


def test_native_diagnostic_refusal_survives_a_caught_exception() -> None:
    configure_native_diagnostics()
    handler_count = len(logging.getLogger("gliner2").handlers)
    configure_native_diagnostics()
    assert len(logging.getLogger("gliner2").handlers) == handler_count
    with pytest.raises(NativeDiagnosticError), native_operation():
        with suppress(NativeDiagnosticError):
            logging.getLogger("gliner2.processor").warning("unpublished-native-diagnostic")
    with native_operation():
        logging.getLogger("gliner2.processor").info("discarded-native-info")


def test_real_prepared_model_api() -> None:
    settings = load_settings(ROOT)
    transport = _transport()
    events = io.StringIO()
    app = create_app(settings, transport, root=ROOT, stream=events)
    text = " \U0001f4f0 A research team announced a new language model in London. "
    ner_request = NerRequest(text=text, labels=["location", "technology"])
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
    with TestClient(app, base_url=_base_url(transport)) as client:
        health = client.get(HEALTH_PATH)
        assert health.status_code == 200, "Prepare the configured model before running this test."
        assert GlinerHealth.model_validate_json(health.content).status == "ready"
        ner_response = client.post(NER_PATH, json=ner_request.model_dump(), headers=carrier)
        assert ner_response.status_code == 200
        ner_result = NerResult.model_validate_json(ner_response.content)
        assert set(ner_response.json()) == {"entities"}
        assert ner_result.entities
        for mention in ner_result.entities:
            assert text[mention.start_char : mention.end_char] == mention.text
            assert mention.label in ner_request.labels
        runtime = cast(ModelRuntime, app.state.component.state)

        def refuse_native_record(native: NativeModel) -> object:
            processor = cast(_NativeProcessor, getattr(native, "processor"))
            return processor.collate_fn_inference([("x", None)])

        assert client.portal is not None
        with pytest.raises(OperationError) as refused:
            client.portal.call(runtime.execute, refuse_native_record)
        assert refused.value.code == "INPUT_UNSUPPORTED"
        classification_response = client.post(
            CLASSIFY_PATH, json=classification_request.model_dump(), headers=carrier
        )
        assert classification_response.status_code == 200
        result = ClassificationResult.model_validate_json(classification_response.content)
        assert set(classification_response.json()) == {"classifications"}
        assert result.classifications.keys() == classification_request.tasks.keys()
        assert len(result.classifications["desk"]) == 1
        for name, selected in result.classifications.items():
            assert all(label.id in classification_request.tasks[name].labels for label in selected)
        assert client.get(HEALTH_PATH).status_code == 200
    records = [GlinerEvent.model_validate_json(line) for line in events.getvalue().splitlines()]
    assert any(record.type == "gliner.service.ready" for record in records)
    completed = [record for record in records if record.type == "gliner.request.completed"]
    assert [record.traceparent for record in completed] == [
        ner_response.headers["traceparent"],
        classification_response.headers["traceparent"],
    ]
    assert all(record.tracestate == carrier["tracestate"] for record in completed)
    assert text not in events.getvalue()
    assert all(
        definition not in events.getvalue()
        for task in classification_request.tasks.values()
        for definition in task.labels.values()
    )
