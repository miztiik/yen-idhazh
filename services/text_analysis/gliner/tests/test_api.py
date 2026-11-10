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
from load_caller_settings import CallerAnalysisSettings, load_caller_settings
from local_api_host.compose_applications import compose_applications
from local_api_host.contracts import HostSettings, ListenerSettings
from project_gliner_analysis import EVENT_FIELDS, event_structure, project_entity_request
from pydantic import TypeAdapter, ValidationError
from serve_apis import create_app as create_shared_app
from text_analysis.load_service_settings import load_service_settings

from gliner_api.configure_native_diagnostics import (
    NativeDiagnosticError,
    configure_native_diagnostics,
    filter_encoder_deprecation,
    native_operation,
)
from gliner_api.create_api_component import create_app
from gliner_api.declare_analysis_contracts import AnalysisSchema, AnalyzeTextRequest
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
from gliner_api.load_model import require_record_capability
from gliner_api.load_settings import SETTINGS_VERSION, GlinerSettings, load_settings
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
    assert not request.include_confidence
    assert not request.include_spans
    for field in ("include_confidence", "include_spans"):
        for invalid_flag in (1, "true", None):
            with pytest.raises(ValidationError):
                AnalyzeTextRequest.model_validate(
                    {"text": "a", "schema": {"entities": ["mention"]}, field: invalid_flag}
                )
    for invalid_threshold in (-0.1, 1.1, True, "0.8", None, float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            GlinerSettings.model_validate(raw | {"entity_confidence_threshold": invalid_threshold})
    for policy in ("disallow", "flat", "allow"):
        configured = GlinerSettings.model_validate(raw | {"overlap_policy": policy})
        assert configured.overlap_policy == policy
    for invalid_policy in (None, True, "unknown"):
        with pytest.raises(ValidationError):
            GlinerSettings.model_validate(raw | {"overlap_policy": invalid_policy})
    previous = {
        key: value for key, value in raw.items()
        if key not in {"entity_confidence_threshold", "overlap_policy"}
    } | {
        "version": API_VERSION,
        "changelog": [{"version": API_VERSION, "change": "Initial settings."}],
    }
    historical = GlinerSettings.model_validate(previous)
    assert historical.entity_confidence_threshold == 0.5
    assert historical.overlap_policy is None
    for malformed in (
        previous | {"entity_confidence_threshold": 0.8},
        previous | {"overlap_policy": "disallow"},
        raw | {"version": "2026-11-07"},
        raw | {"changelog": [{"version": API_VERSION, "change": "Wrong shape."}]},
    ):
        with pytest.raises(ValidationError):
            GlinerSettings.model_validate(malformed)
    assert settings.version == SETTINGS_VERSION


def test_native_entity_defaults_preserve_overrides_and_other_tasks() -> None:
    schema = AnalysisSchema.model_validate(
        {
            "entities": {
                "default": "Named people.",
                "nullable": {"threshold": None, "dtype": "str"},
                "zero": {"threshold": 0.0, "description": "Specific places."},
                "explicit": {"threshold": 0.2},
            },
            "classifications": [{"task": "task", "labels": ["id"]}],
            "structures": {"item": {"fields": [{"name": "actor", "threshold": 0.3}]}},
        }
    )
    before = schema.model_dump()
    native = schema.to_native_schema(0.8).to_dict()
    assert list(native["entities"]) == ["default", "nullable", "zero", "explicit"]
    assert native["entities"]["default"] == {"description": "Named people.", "threshold": 0.8}
    assert native["entities"]["nullable"] == {"dtype": "str", "threshold": 0.8}
    assert native["entities"]["zero"]["threshold"] == 0.0
    assert native["entities"]["explicit"]["threshold"] == 0.2
    assert native["structures"]["item"]["fields"][0]["threshold"] == 0.3
    assert schema.to_native_schema().to_dict()["classifications"] == native["classifications"]
    assert AnalysisSchema(entities=["a", "b"]).to_native_schema(0.8).to_dict()["entities"] == {
        "a": {"threshold": 0.8}, "b": {"threshold": 0.8},
    }
    assert schema.model_dump() == before


def test_caller_configuration_uses_native_schema_and_the_ordered_presentation_offering() -> None:
    labels = list(dict.fromkeys(load_service_settings(ROOT).named_entities.label_map.values()))
    caller = load_caller_settings(ROOT, labels)
    assert list(caller.analysis_schema.entities or []) == labels
    assert caller.include_confidence
    assert caller.include_spans
    request = AnalyzeTextRequest.model_validate({
        "text": "a",
        "schema": caller.analysis_schema.model_dump(exclude_none=True),
        "include_confidence": caller.include_confidence,
        "include_spans": caller.include_spans,
    })
    wire = request.model_dump(by_alias=True, exclude_none=True)
    assert project_entity_request(wire)["labels"] == labels
    assert event_structure(wire) is not None
    structures = request.analysis_schema.structures
    assert structures is not None
    assert [field.name for field in structures["events"].fields] == list(EVENT_FIELDS)
    with pytest.raises(ValueError, match="presentation offering"):
        load_caller_settings(ROOT, list(reversed(labels)))
    raw = TypeAdapter(CallerAnalysisSettings).dump_python(caller, by_alias=True, exclude_none=True)
    entity_only = raw | {
        "schema": {"entities": raw["schema"]["entities"]},
        "include_confidence": False, "include_spans": False,
    }
    compact = TypeAdapter(CallerAnalysisSettings).validate_json(
        json.dumps(entity_only), strict=True
    )
    assert compact.analysis_schema.structures is None
    assert not compact.include_confidence
    assert not compact.include_spans
    for malformed in (
        raw | {"version": API_VERSION},
        raw | {"include_confidence": 1},
        raw | {"include_spans": "true"},
        raw | {"extra": True},
        raw | {"schema": {"entities": ["person"]}},
    ):
        with pytest.raises(ValidationError):
            TypeAdapter(CallerAnalysisSettings).validate_json(json.dumps(malformed), strict=True)


def test_native_result_boundaries() -> None:
    request = AnalyzeTextRequest.model_validate_json(
        json.dumps(
            {
                "text": "a \u00e9 a",
                "include_confidence": True,
                "include_spans": True,
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


@pytest.mark.parametrize("include_confidence", [False, True])
@pytest.mark.parametrize("include_spans", [False, True])
def test_native_leaf_profiles_preserve_all_task_families(
    include_confidence: bool, include_spans: bool
) -> None:
    def leaf(text: str, start: int) -> object:
        value: dict[str, object] = {"text": text}
        if include_confidence:
            value["confidence"] = 0.6
        if include_spans:
            value |= {"start": start, "end": start + len(text)}
        return value if include_confidence or include_spans else text

    request = AnalyzeTextRequest.model_validate(
        {
            "text": "a b",
            "include_confidence": include_confidence,
            "include_spans": include_spans,
            "schema": {
                "entities": {"mention": {"dtype": "str"}, "missing": {"dtype": "str"}},
                "entity_attributes": {
                    "kind": {"labels": ["id"], "applies_to": ["mention"]},
                },
                "classifications": [{"task": "task", "labels": ["id"]}],
                "structures": {
                    "item": {
                        "fields": [
                            {"name": "actor", "dtype": "str"},
                            {"name": "related", "dtype": "list"},
                            {"name": "choice", "dtype": "list", "choices": ["selected"]},
                            {"name": "optional", "dtype": "str"},
                        ]
                    }
                },
                "relations": ["links"],
            },
        }
    )
    entity = leaf("a", 0)
    entity = entity if isinstance(entity, dict) else {"text": entity}
    choice: object = {"text": "selected", "confidence": 0.6} if include_confidence else "selected"
    record = {
        "actor": leaf("a", 0),
        "related": [leaf("b", 2)],
        "choice": [choice],
        "optional": None,
    }
    native = {
        "entities": {
            "mention": entity | {"kind": {"label": "id", "confidence": 0.7}},
            "missing": None,
        },
        "task": {"label": "id", "confidence": 0.7} if include_confidence else "id",
        "item": [record],
        "relation_extraction": {
            "links": [{"head": leaf("a", 0), "tail": leaf("b", 2), "confidence": 0.9}],
        },
    }
    assert validate_analysis_results(native, request).model_dump() == {"result": native}
    malformed = native | {"task": "unknown"}
    with pytest.raises(ResultValidationError):
        validate_analysis_results(malformed, request)
    for malformed_record in (
        record | {"choice": [choice, choice]},
        record | {"actor": leaf("absent", 0)},
    ):
        with pytest.raises(ResultValidationError):
            validate_analysis_results(native | {"item": [malformed_record]}, request)
    with pytest.raises(ResultValidationError):
        validate_analysis_results(
            native | {"relation_extraction": {"links": [["a", "b"]]}}, request
        )


def test_native_records_keep_aggregate_scores_omission_and_compact_repetitions() -> None:
    structure = {
        "mode": "natural",
        "anchor": "action",
        "fields": [
            {"name": "action", "dtype": "str", "cardinality": "required_one"},
            {"name": "actors", "dtype": "list", "cardinality": "zero_or_more"},
        ],
    }
    request = AnalyzeTextRequest.model_validate(
        {"text": "a a", "schema": {"entities": ["mention"], "structures": {"event": structure}}}
    )
    record = {"action": "a", "actors": ["a", "a"], "confidence": 0.7}
    native: dict[str, object] = {"entities": {"mention": ["a", "a"]}, "event": [record, record]}
    assert validate_analysis_results(native, request).model_dump() == {"result": native}
    omitted: dict[str, object] = {"entities": {}}
    assert validate_analysis_results(omitted, request).model_dump() == {"result": omitted}
    malformed_results: tuple[dict[str, object], ...] = (
        native | {"event": [record | {"confidence": True}]},
        native | {"event": [record | {"confidence": float("inf")}]},
        native | {"event": [record | {"confidence": -0.1}]},
        native | {"event": [record | {"confidence": 1.1}]},
        native | {"event": [record | {"confidence": "0.7"}]},
        native | {"event": [record | {"extra": []}]},
        native | {"event": [record | {"action": None}]},
        {"event": []},
        omitted | {"unknown": []},
    )
    for malformed in malformed_results:
        with pytest.raises(ResultValidationError):
            validate_analysis_results(malformed, request)
    rich_request = AnalyzeTextRequest.model_validate(
        request.model_dump(by_alias=True) | {"include_confidence": True, "include_spans": True}
    )
    first = {"text": "a", "start": 0, "end": 1, "confidence": 0.6}
    second = first | {"start": 2, "end": 3}
    first_record = {"action": first, "actors": [second], "confidence": 0.7}
    second_record = {"action": second, "actors": [first], "confidence": 0.8}
    rich = {
        "entities": {"mention": [first, second]}, "event": [first_record, second_record],
    }
    assert validate_analysis_results(rich, rich_request).model_dump() == {"result": rich}
    for duplicate in (
        rich | {"entities": {"mention": [first, first]}},
        rich | {"event": [first_record, first_record]},
    ):
        with pytest.raises(ResultValidationError):
            validate_analysis_results(duplicate, rich_request)
    exclusive_structure = structure | {
        "fields": [
            {"name": "action", "dtype": "str", "cardinality": "required_one"},
            {"name": "actors", "dtype": "list", "cardinality": "zero_or_more", "exclusive": True},
        ],
    }
    exclusive_request = AnalyzeTextRequest.model_validate(
        rich_request.model_dump(by_alias=True) | {
            "schema": {"entities": ["mention"], "structures": {"event": exclusive_structure}},
        }
    )
    with pytest.raises(ResultValidationError):
        validate_analysis_results(rich, exclusive_request)
    for name in ("confidence", "label", "text"):
        field = {"name": name, "dtype": "str"}
        with pytest.raises(ValidationError):
            AnalysisSchema.model_validate(
                {"structures": {"record": {"mode": "natural", "fields": [field]}}}
            )
        AnalysisSchema.model_validate({"structures": {"ordinary": {"fields": [field]}}})
    ordinary = AnalyzeTextRequest.model_validate(
        {"text": "a", "schema": {"structures": {"item": {"fields": [{"name": "value"}]}}}}
    )
    with pytest.raises(ResultValidationError):
        validate_analysis_results({}, ordinary)
    with pytest.raises(ValueError, match="does not support records"):
        require_record_capability(object())


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
