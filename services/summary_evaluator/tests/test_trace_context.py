"""Prove shared trace metadata and saved scorer carriers preserve native identities."""

import json
import shutil
import subprocess
from typing import NotRequired, TypedDict
from uuid import UUID

import pytest
from local_api_host.propagate_trace_context import (
    OperationLink,
    OperationMetadata,
    create_child_operation,
    create_root_operation,
    read_trace_context,
    write_trace_context,
)
from opentelemetry.context import Context, attach, detach
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, set_span_in_context
from pydantic import TypeAdapter, ValidationError
from pydantic.json_schema import JsonSchemaValue
from starlette.datastructures import Headers
from summary_evaluator_cases.contract_examples import REPOSITORY, example_event

from summary_evaluator.hhem.contracts.evaluation_event import EvaluationEvent
from summary_evaluator.hhem.resolve_ids import create_event_id
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData, ServerEvent
from summary_evaluator.shared.bound_operation_metadata import maximum_worker_operation_metadata

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN_ID = "00f067aa0ba902b7"
PARENT_SPAN_ID = "1111111111111111"
TRACEPARENT = f"00-{TRACE_ID}-{SPAN_ID}-00"


class MetadataVector(TypedDict):
    name: str
    value: dict[str, object]


class CarrierVector(TypedDict):
    name: str
    value: dict[str, str | list[str]]


class TraceVectors(TypedDict):
    metadata: list[MetadataVector]
    carriers: list[CarrierVector]
    factoryParent: dict[str, object]


class MetadataResult(TypedDict):
    name: str
    accepted: bool
    value: NotRequired[dict[str, object]]
    carrier: NotRequired[dict[str, str]]


class CarrierResult(TypedDict):
    name: str
    value: dict[str, object] | None
    carrier: dict[str, str] | None


class FactoryResult(TypedDict):
    root: dict[str, object]
    child: dict[str, object]


class TraceBindingResult(TypedDict):
    schema: JsonSchemaValue
    metadata: list[MetadataResult]
    carriers: list[CarrierResult]
    factories: list[FactoryResult]


def _metadata_vectors() -> list[MetadataVector]:
    root: dict[str, object] = {"traceId": TRACE_ID, "spanId": SPAN_ID, "links": []}
    linked: dict[str, object] = {
        **root,
        "parentSpanId": PARENT_SPAN_ID,
        "links": [{"traceId": "2" * 32, "spanId": "3" * 16}],
        "traceState": "first=value,second=other",
    }
    patches: list[tuple[str, dict[str, object]]] = [
        ("zero trace", {"traceId": "0" * 32}),
        ("zero span", {"spanId": "0" * 16}),
        ("short trace", {"traceId": "a" * 31}),
        ("long span", {"spanId": "a" * 17}),
        ("uppercase trace", {"traceId": TRACE_ID.upper()}),
        ("uppercase span", {"spanId": SPAN_ID.upper()}),
        ("non-string trace", {"traceId": 1}),
        ("null parent", {"parentSpanId": None}),
        ("zero parent", {"parentSpanId": "0" * 16}),
        ("self parent", {"parentSpanId": SPAN_ID}),
        ("short parent", {"parentSpanId": "1" * 15}),
        ("null links", {"links": None}),
        ("non-array links", {"links": {}}),
        ("missing link span", {"links": [{"traceId": TRACE_ID}]}),
        ("zero link trace", {"links": [{"traceId": "0" * 32, "spanId": SPAN_ID}]}),
        ("zero link span", {"links": [{"traceId": TRACE_ID, "spanId": "0" * 16}]}),
        ("extra link field", {"links": [{"traceId": TRACE_ID, "spanId": SPAN_ID, "extra": 1}]}),
        ("null state", {"traceState": None}),
        ("empty state", {"traceState": ""}),
        ("invalid state", {"traceState": "not-valid-state"}),
        ("noncanonical state", {"traceState": "first=value, second=other"}),
        ("duplicate state key", {"traceState": "first=value,first=other"}),
        ("state over total limit", {"traceState": "a=" + "x" * 256 + ",b=" + "y" * 256}),
        ("extra metadata", {"extra": True}),
    ]
    native_root = create_root_operation(
        links=(OperationLink(trace_id="2" * 32, span_id="3" * 16),),
        trace_state="first=value,second=other",
    )
    native_child = create_child_operation(native_root, links=native_root.links)
    vectors: list[MetadataVector] = [
        {"name": "root", "value": root},
        {"name": "linked child", "value": linked},
        {
            "name": "maximum escaped native state",
            "value": maximum_worker_operation_metadata().model_dump(mode="json"),
        },
        {"name": "missing links", "value": {"traceId": TRACE_ID, "spanId": SPAN_ID}},
    ]
    for name, patch in patches:
        vectors.append({"name": name, "value": {**root, **patch}})
    vectors.extend(
        [
            {"name": "native root factory", "value": native_root.model_dump(mode="json")},
            {"name": "native child factory", "value": native_child.model_dump(mode="json")},
            {
                "name": "native default root",
                "value": create_root_operation().model_dump(mode="json"),
            },
        ]
    )
    return vectors


def _carrier_vectors() -> list[CarrierVector]:
    invalid = [
        "",
        "not-a-context",
        f"00-{'0' * 32}-{SPAN_ID}-00",
        f"00-{TRACE_ID}-{'0' * 16}-00",
        f"00-{TRACE_ID.upper()}-{SPAN_ID}-00",
        f"00-{TRACE_ID}-{SPAN_ID.upper()}-00",
        f"00-{TRACE_ID}-{SPAN_ID}-00-extra",
        f"ff-{TRACE_ID}-{SPAN_ID}-00",
        f"00-{TRACE_ID}-{SPAN_ID}-zz",
    ]
    vectors: list[CarrierVector] = [
        {"name": "absent", "value": {}},
        {"name": "orphan state", "value": {"tracestate": "first=value"}},
        {"name": "unsampled", "value": {"traceparent": TRACEPARENT}},
        {
            "name": "sampled with state",
            "value": {
                "traceparent": f"00-{TRACE_ID}-{SPAN_ID}-01",
                "tracestate": "first=value",
            },
        },
        {
            "name": "separate state headers",
            "value": {"traceparent": TRACEPARENT, "tracestate": ["first=value", "second=other"]},
        },
        {
            "name": "invalid optional state",
            "value": {"traceparent": TRACEPARENT, "tracestate": "not-valid-state"},
        },
    ]
    for index, parent in enumerate(invalid):
        vectors.append({"name": f"invalid parent {index}", "value": {"traceparent": parent}})
    return vectors


@pytest.fixture(scope="module")
def trace_binding() -> tuple[TraceVectors, TraceBindingResult]:
    bun = shutil.which("bun")
    dependency = REPOSITORY / "packages" / "common-contracts" / "node_modules" / "zod"
    if bun is None or not (dependency / "package.json").is_file():
        pytest.fail(
            "The real trace binding requires Bun and the common library's locked dependencies. "
            "Run bun install --frozen-lockfile --cwd packages/common-contracts."
        )
    metadata = _metadata_vectors()
    vectors: TraceVectors = {
        "metadata": metadata,
        "carriers": _carrier_vectors(),
        "factoryParent": metadata[1]["value"],
    }
    bridge = REPOSITORY / "services" / "summary_evaluator" / "tests" / "check_trace_context.ts"
    completed = subprocess.run(
        [bun, "run", "--no-install", str(bridge)],
        input=json.dumps(vectors),
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, (
        "The actual TypeScript trace binding failed: " + completed.stderr
    )
    return vectors, TypeAdapter(TraceBindingResult).validate_json(completed.stdout, strict=True)


def test_native_metadata_schema_matches_the_typescript_authority(
    trace_binding: tuple[TraceVectors, TraceBindingResult],
) -> None:
    _, result = trace_binding
    native = OperationMetadata.model_json_schema()
    shared = result["schema"]
    for name in ("version", "changelog", "additionalProperties"):
        assert native[name] == shared[name]
    assert native["version"] == "2026-11-03"
    assert set(native["required"]) == set(shared["required"])
    assert set(native["properties"]) == set(shared["properties"])
    for name, field in shared["properties"].items():
        counterpart = native["properties"][name]
        assert "null" not in json.dumps(counterpart), name
        assert "default" not in counterpart, name
        assert counterpart["type"] == field["type"], name
        for constraint in ("pattern", "minLength"):
            assert counterpart.get(constraint) == field.get(constraint), name
    native_link = native["$defs"]["OperationLink"]
    shared_link = shared["properties"]["links"]["items"]
    assert native_link["additionalProperties"] is shared_link["additionalProperties"] is False
    assert set(native_link["required"]) == set(shared_link["required"])
    assert set(native_link["properties"]) == set(shared_link["properties"])
    for name, field in shared_link["properties"].items():
        assert native_link["properties"][name]["type"] == field["type"]
        assert native_link["properties"][name]["pattern"] == field["pattern"]


def test_native_metadata_values_and_factories_match_the_typescript_authority(
    trace_binding: tuple[TraceVectors, TraceBindingResult],
) -> None:
    vectors, result = trace_binding
    observed: list[MetadataResult] = []
    for vector in vectors["metadata"]:
        try:
            operation = OperationMetadata.model_validate_json(json.dumps(vector["value"]))
        except ValidationError:
            observed.append({"name": vector["name"], "accepted": False})
        else:
            assert isinstance(operation.links, tuple)
            assert all(isinstance(link, OperationLink) for link in operation.links)
            observed.append(
                {
                    "name": vector["name"],
                    "accepted": True,
                    "value": operation.model_dump(mode="json"),
                    "carrier": write_trace_context(operation),
                }
            )
    assert observed == result["metadata"]
    for pair in result["factories"]:
        root = OperationMetadata.model_validate_json(json.dumps(pair["root"]))
        child = OperationMetadata.model_validate_json(json.dumps(pair["child"]))
        assert root.parent_span_id is None
        assert child.trace_id == root.trace_id
        assert child.span_id != root.span_id and child.parent_span_id == root.span_id
        assert child.trace_state == root.trace_state and child.links == root.links
        assert write_trace_context(child)["traceparent"] == f"00-{root.trace_id}-{child.span_id}-00"
    assert result["factories"][0]["root"]["links"] == []
    assert result["factories"][0]["child"]["links"] == []
    assert "parentSpanId" not in result["factories"][0]["root"]
    assert "traceState" not in result["factories"][0]["root"]


def test_native_w3c_codec_matches_the_typescript_authority(
    trace_binding: tuple[TraceVectors, TraceBindingResult],
) -> None:
    vectors, result = trace_binding
    observed: list[CarrierResult] = []
    for vector in vectors["carriers"]:
        headers = Headers(
            raw=[
                (name.encode("ascii"), part.encode("ascii"))
                for name, value in vector["value"].items()
                for part in ([value] if isinstance(value, str) else value)
            ]
        )
        operation = read_trace_context(headers)
        observed.append(
            {
                "name": vector["name"],
                "value": None if operation is None else operation.model_dump(mode="json"),
                "carrier": None if operation is None else write_trace_context(operation),
            }
        )
    assert observed == result["carriers"]


def test_invalid_optional_parent_never_adopts_an_ambient_operation() -> None:
    ambient = SpanContext(
        trace_id=int(TRACE_ID, 16),
        span_id=int(SPAN_ID, 16),
        is_remote=False,
        trace_flags=TraceFlags(0),
    )
    token = attach(set_span_in_context(NonRecordingSpan(ambient), Context()))
    try:
        assert read_trace_context(Headers()) is None
        assert read_trace_context(Headers({"traceparent": "not-a-context"})) is None
    finally:
        detach(token)


@pytest.mark.parametrize("traceparent", [TRACEPARENT, f"00-{TRACE_ID}-{SPAN_ID}-01"])
def test_saved_traced_hhem_event_retains_the_native_occurrence(traceparent: str) -> None:
    native = example_event().model_dump(mode="json")
    native.update(
        sequence=2,
        event_id=create_event_id(native["execution_id"], 2),
        caused_by_event_id=native["event_id"],
        phase="completed",
        request_id=str(native["request_id"]).upper(),
        correlation_id=str(native["correlation_id"]).upper(),
    )
    envelope = ServerEvent.from_evaluation(EvaluationEvent.model_validate_json(json.dumps(native)))
    saved = {
        **envelope.model_dump(mode="json"),
        "traceparent": traceparent,
        "tracestate": "first=value",
    }
    observed = ServerEvent.model_validate_json(json.dumps(saved))
    assert UUID(observed.id).version == 5
    assert observed.model_dump(mode="json") == saved
    assert observed.data.model_dump(mode="json") == native
    assert list(observed.model_dump(mode="json")["data"]) == list(native)
    encoded = (observed.model_dump_json() + "\n").encode("utf-8")
    assert ServerEvent.model_validate_json(encoded) == observed
    assert observed.encode_json_line(len(encoded)) == encoded
    with pytest.raises(ValueError, match="max_event_bytes"):
        observed.encode_json_line(len(encoded) - 1)


@pytest.mark.parametrize("component", ["api", "unieval", "coverage", "log"])
def test_saved_traced_diagnostic_preserves_its_uuid4_occurrence(component: str) -> None:
    data = ApiDiagnosticData.model_validate(
        {"component": component, "action": "ready", "level": "INFO"}
    )
    original = ServerEvent.diagnostic(data).model_dump(mode="json")
    saved = {**original, "traceparent": TRACEPARENT}
    observed = ServerEvent.model_validate_json(json.dumps(saved))
    assert UUID(observed.id).version == 4
    assert observed.model_dump(mode="json") == saved
    assert "tracestate" not in observed.model_dump(mode="json")


@pytest.mark.parametrize(
    "patch",
    [
        {"traceparent": None},
        {"traceparent": False},
        {"traceparent": ""},
        {"traceparent": "not-a-context"},
        {"traceparent": f"00-{'0' * 32}-{SPAN_ID}-00"},
        {"traceparent": f"00-{TRACE_ID}-{'0' * 16}-00"},
        {"traceparent": f"ff-{TRACE_ID}-{SPAN_ID}-00"},
        {"traceparent": TRACEPARENT, "tracestate": None},
        {"traceparent": TRACEPARENT, "tracestate": ["first=value"]},
        {"traceparent": TRACEPARENT, "tracestate": ""},
        {"traceparent": TRACEPARENT, "tracestate": "not-valid-state"},
        {"traceparent": TRACEPARENT, "tracestate": "first=value, first=other"},
        {"tracestate": None},
        {"tracestate": "first=value"},
    ],
)
def test_saved_invalid_or_orphan_carriers_are_rejected(patch: dict[str, object]) -> None:
    saved = ServerEvent.from_evaluation(example_event()).model_dump(mode="json")
    with pytest.raises(ValidationError):
        ServerEvent.model_validate_json(json.dumps({**saved, **patch}))
