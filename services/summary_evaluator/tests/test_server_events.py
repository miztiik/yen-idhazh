"""Prove current CloudEvents records and optional file-mirror failures with real files."""

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from summary_eval_pipeline.native_log import NativeDiagnosticData
from summary_evaluator_cases.contract_examples import SETTINGS_FILE, example_event

from summary_evaluator.hhem.contracts.evaluation_event import EventDetails
from summary_evaluator.hhem.emit_events import EventEmitter
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData, ServerEvent
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.shared.contracts.diagnostic_data import LifecycleFields
from summary_evaluator.shared.contracts.server_contract import SERVER_SCHEMA_VERSION
from summary_evaluator.shared.contracts.service_settings import StartupContext


def test_native_event_has_one_current_cloudevents_occurrence_and_no_legacy_reader() -> None:
    native = example_event()
    event = ServerEvent.from_evaluation(native)
    assert event.id == native.event_id and event.time == native.occurred_at
    assert event.source == "/fastapi-server" and event.specversion == "1.0"
    assert ServerEvent.model_validate_json(event.model_dump_json()) == event
    assert ServerEvent.model_json_schema()["version"] == SERVER_SCHEMA_VERSION
    with pytest.raises(ValidationError):
        ServerEvent.model_validate_json(native.model_dump_json())
    with pytest.raises(ValidationError):
        ServerEvent.model_validate({**event.model_dump(), "type": "fastapi-server.api.ready"})


def test_independent_lifecycle_logs_share_fields_but_not_component_ownership() -> None:
    fields = {
        "action": "failed",
        "level": "ERROR",
        "code": "STARTUP_FAILED",
        "duration_ms": 1.0,
    }
    common = LifecycleFields.model_validate(fields)
    native = NativeDiagnosticData.model_validate({**fields, "component": "llama"})
    api = ApiDiagnosticData.model_validate({**fields, "component": "unieval"})
    assert native.model_dump(exclude={"component"}) == common.model_dump()
    assert api.model_dump(exclude={"component"}) == common.model_dump()
    assert set(LifecycleFields.model_fields) == set(ApiDiagnosticData.model_fields) - {"component"}
    for component in ("api", "unieval"):
        with pytest.raises(ValidationError):
            NativeDiagnosticData.model_validate({**fields, "component": component})
    with pytest.raises(ValidationError):
        ApiDiagnosticData.model_validate({**fields, "component": "llama"})


def test_live_records_and_named_file_match_and_restarts_append(tmp_path: Path) -> None:
    stream = io.StringIO()
    settings = load_settings(SETTINGS_FILE).logging
    for _ in range(2):
        writer = EventWriter(
            settings,
            stream,
            directory=tmp_path,
            run_id="123456",
            attempt=2,
            started_at=datetime(2026, 11, 3, 23, 58, tzinfo=UTC),
        )
        writer.diagnostic(ApiDiagnosticData(component="api", action="started", level="INFO"))
        assert writer.log_available
        writer.close()
    expected = tmp_path / "fastapi-server_2026_11_03_123456_2.log"
    assert expected.read_text(encoding="utf-8") == stream.getvalue()
    assert len(stream.getvalue().splitlines()) == 2
    for line in stream.getvalue().splitlines():
        ServerEvent.model_validate_json(line)


def test_independent_scorer_logs_do_not_share_the_same_role_file(tmp_path: Path) -> None:
    settings = load_settings(SETTINGS_FILE).logging
    scorers: tuple[ApiComponent, ...] = ("hhem", "unieval", "coverage")
    for scorer in scorers:
        writer = EventWriter(
            settings, io.StringIO(), directory=tmp_path, run_id="123456", attempt=1,
            started_at=datetime(2026, 11, 7, tzinfo=UTC), scorer=scorer,
        )
        writer.diagnostic(ApiDiagnosticData(component="api", action="started", level="INFO"))
        assert writer.log_file == f"fastapi-server_{scorer}_2026_11_07_123456_1.log"
        assert writer.log_file is not None
        writer.close()
        assert (tmp_path / writer.log_file).is_file()


def test_an_unopenable_diagnostic_mirror_warns_without_failing_native_events(
    tmp_path: Path,
) -> None:
    occupied = tmp_path / "occupied"
    occupied.write_text("A real file cannot also be a log directory.", encoding="ascii")
    stream = io.StringIO()
    writer = EventWriter(load_settings(SETTINGS_FILE).logging, stream, directory=occupied)
    emitter = EventEmitter(writer.write, StartupContext(), writer.settings)
    event_id = emitter.emit("service", "started", EventDetails(status="disabled"))
    assert event_id == emitter.last_event_id and not emitter.logging_failed
    assert not writer.log_available
    records = [ServerEvent.model_validate_json(line) for line in stream.getvalue().splitlines()]
    assert isinstance(records[0].data, ApiDiagnosticData)
    assert records[0].data.code == "LOG_FILE_UNAVAILABLE"
    assert len(records) == 2
    assert str(tmp_path) not in stream.getvalue()
    writer.close()


def test_a_real_file_write_failure_does_not_drop_the_stderr_record(tmp_path: Path) -> None:
    stream = io.StringIO()
    writer = EventWriter(load_settings(SETTINGS_FILE).logging, stream, directory=tmp_path)
    assert writer.file_handler is not None
    read_only_path = tmp_path / "read-only.txt"
    read_only_path.write_text("Recorded file-write failure input.", encoding="ascii")
    with read_only_path.open("r", encoding="ascii") as read_only:
        previous = writer.file_handler.setStream(read_only)
        assert previous is not None
        previous.close()
        writer.diagnostic(ApiDiagnosticData(component="api", action="ready", level="INFO"))
        assert not writer.log_available
        writer.close()
    records = [ServerEvent.model_validate_json(line) for line in stream.getvalue().splitlines()]
    assert [record.type for record in records] == [
        "fastapi-server.api.ready",
        "fastapi-server.log.unavailable",
    ]


def test_closed_file_cleanup_is_an_unavailable_mirror_not_an_operation_failure(
    tmp_path: Path,
) -> None:
    stream = io.StringIO()
    writer = EventWriter(load_settings(SETTINGS_FILE).logging, stream, directory=tmp_path)
    assert writer.file_handler is not None and writer.file_handler.stream is not None
    writer.file_handler.stream.close()
    writer.close()
    assert not writer.log_available
    event = ServerEvent.model_validate_json(stream.getvalue())
    assert event.type == "fastapi-server.log.unavailable"
