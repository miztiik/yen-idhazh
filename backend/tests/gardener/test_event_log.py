"""Does every gardener log line come out as one line of ASCII JSON, stamped in UTC?

Every line the gardener logs is an event: `event` first, then `at`, the UTC
instant, then `level`, then the event's own fields in the order it declares
them, every None left out and a nested model kept nested. A record some other
module logs as text is wrapped the same way, and an exception on any record is
named by its type and its place in this package, never by what it said: its
text can carry a ledger row fetched from the open web (Guardrail #11).

The instant is pinned under a zone that is not UTC, so a stamp read off the
machine's local clock fails here wherever the test runs (CLAUDE.md section 2).
On GitHub the handler also writes the workflow commands around an event's line;
those are text by definition, so those tests read the lines. The tests that
start the gardener's own command-line setup do so in a fresh process, because
the handler goes on a root logger that pytest already holds.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, REPO_ROOT
from pydantic import BaseModel

from idhazh.contracts import gardener_events
from idhazh.contracts.base import Model
from idhazh.contracts.collection_prune import Recovery, StopReason
from idhazh.contracts.gardener_events import (
    DownloadOverBudget,
    LoggedText,
    PeriodsChosen,
    PeriodsTaken,
    TaskFinished,
    TaskOutcome,
    TaskPlanned,
)
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener import event_log
from idhazh.gardener.one_at_a_time import Window

pytestmark = pytest.mark.contract

#: A zone five and a half hours east of UTC, spelled the way both the C library
#: on Linux and the one on Windows read the `TZ` variable.
NOT_UTC: Final = "IST-05:30"

#: One instant, and how a line must stamp it.
AN_INSTANT: Final = datetime(2026, 10, 7, 9, 46, 0, 500000, tzinfo=UTC)
STAMPED: Final = "2026-10-07T09:46:00.500Z"

#: What a fetched page might say, planted in an exception's text.
FETCHED: Final = "Breaking: click https://example.invalid/now"


@pytest.fixture
def a_zone_that_is_not_utc(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The process clock in `NOT_UTC` while the test runs, where the platform can move it."""
    monkeypatch.setenv("TZ", NOT_UTC)
    if hasattr(time, "tzset"):
        time.tzset()
    yield
    monkeypatch.undo()
    if hasattr(time, "tzset"):
        time.tzset()


def finished() -> TaskFinished:
    """A compaction that packed one day, recovered one, and stopped at its ceiling."""
    return TaskFinished(
        task="compact-visual-prunes",
        outcome=TaskOutcome.CEILING,
        dry_run=False,
        seen=4,
        selected=2,
        taken=["state/raw/visual-prunes/2026/09/20/a.parquet"],
        written=["state/compact/visual-prunes/daily/2026/09/20.parquet"],
        bytes_freed=1200,
        stopped_because=StopReason.CEILING,
        resume_from="2026-09-21",
        recovered=[Recovery(note=RecoveryNote.CARRIED_OVER, subject="2026-09-20")],
        next="it stopped at its ceiling, and the next wake goes on from there",
        duration_ms=31,
        periods=PeriodsTaken(
            days_packed=["2026-09-20"],
            days_retaken=[],
            months_closed=[],
            years_packed=[],
            years_expired=[],
            months_dropped=[],
            raw_days_dropped=[],
            empty_periods=[],
            lost_days=[],
            set_aside_paths=[],
            daily_mark="2026-09-20",
            monthly_mark=None,
            yearly_mark=None,
        ),
    )


def line_of(record: logging.LogRecord) -> str:
    """What the gardener's handler writes for one record."""
    return event_log.OneJsonLine().format(record)


def emitted(caplog: pytest.LogCaptureFixture, event: Model) -> logging.LogRecord:
    """The one record emitting `event` makes."""
    with caplog.at_level(logging.INFO, logger=event_log.__name__):
        event_log.emit(event)
    (record,) = caplog.records
    return record


def test_an_event_is_one_line_of_ascii_json_named_first_with_every_none_left_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """THE ORACLE for the line: `event`, `at`, `level`, then the fields in order, nested kept nested."""
    event = finished()

    record = emitted(caplog, event)
    line = line_of(record)

    assert "\n" not in line and "\r" not in line
    assert line.isascii()
    said: dict[str, Any] = json.loads(line)
    declared = [name for name in TaskFinished.model_fields if getattr(event, name) is not None]
    assert list(said) == ["event", "at", "level", *declared]
    assert (said["event"], said["level"]) == ("task-finished", "info")
    assert "error" not in said and "where" not in said and "pages_read" not in said
    assert event.periods is not None
    assert said["periods"] == event.periods.model_dump(mode="json", exclude_none=True)
    assert "monthly_mark" not in said["periods"]
    assert said["recovered"] == [{"note": "carried-over", "subject": "2026-09-20"}]
    assert event_log.payload(record) is event, "the record carries the event whole"


def test_the_record_s_message_is_the_event_so_a_text_log_still_says_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A command that writes records as text prints the message: it is the event's own JSON."""
    record = emitted(caplog, finished())

    said = json.loads(record.getMessage())

    assert said["event"] == "task-finished"
    assert said["outcome"] == "ceiling"


def test_a_line_break_a_percent_and_a_letter_outside_ascii_stay_on_one_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A record some other module logged as text is the event `logged-text`, said exactly."""
    text = "first line\nsecond\r line, 100% done, caf\u00e9"
    with caplog.at_level(logging.WARNING, logger="idhazh.ledger.raw_files"):
        logging.getLogger("idhazh.ledger.raw_files").warning("%s", text)
    (record,) = caplog.records

    line = line_of(record)

    assert "\n" not in line and "\r" not in line and line.isascii()
    assert json.loads(line) == {
        "event": "logged-text",
        "at": event_log.instant(record),
        "level": "warning",
        "logger": "idhazh.ledger.raw_files",
        "message": text,
    }


def test_every_instant_is_utc_with_a_z_whatever_zone_the_machine_keeps(
    a_zone_that_is_not_utc: None,
) -> None:
    """Known defect 61: the default stamp read the machine's local clock and named no zone."""
    record = logging.LogRecord("idhazh.ledger", logging.INFO, __file__, 1, "said", None, None)
    record.created = AN_INSTANT.timestamp()
    if hasattr(time, "tzset"):
        assert time.localtime(record.created).tm_hour != AN_INSTANT.hour, "the zone did not move"

    said = json.loads(line_of(record))

    assert said["at"] == STAMPED


def test_an_exception_is_named_by_its_type_and_place_and_never_by_what_it_said(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The text a refused value carries never reaches a line; the line still says where to look."""
    with caplog.at_level(logging.ERROR, logger="idhazh.ledger.raw_files"):
        try:
            Window(since=FETCHED)
        except ValueError:
            logging.getLogger("idhazh.ledger.raw_files").exception("skipped a file")
    (record,) = caplog.records

    line = line_of(record)

    assert "example.invalid" not in line and "Breaking" not in line
    said = json.loads(line)
    assert said["error"] == "ValueError"
    assert said["where"].startswith("idhazh.gardener.one_at_a_time:")
    assert said["message"] == "skipped a file"


def test_the_cause_of_an_exception_is_its_type_and_the_deepest_line_of_this_package() -> None:
    def raised_here() -> None:
        raise KeyError(FETCHED)

    assert event_log.cause_of(None) == (None, None)
    try:
        Window(since=FETCHED)
    except ValueError as refusal:
        error, where = event_log.cause_of(refusal)
        assert error == "ValueError"
        assert where is not None and where.startswith("idhazh.gardener.one_at_a_time:")
        assert where.rpartition(":")[2].isdigit()
    try:
        raised_here()
    except KeyError as failure:
        assert event_log.cause_of(failure) == ("KeyError", None), "no frame here is idhazh's"


def test_an_event_takes_no_exception_text_even_when_handed_one() -> None:
    """The type and the place are code; anything else is refused before it reaches a line."""
    with pytest.raises(ValueError, match="error"):
        LoggedText(logger="x", message="y", error=FETCHED)
    with pytest.raises(ValueError, match="where"):
        LoggedText(logger="x", message="y", where=FETCHED)


def test_no_event_declares_a_field_its_line_already_writes() -> None:
    """`event`, `at` and `level` lead every line, so a field of the same name would be lost."""
    models = [
        held
        for held in vars(gardener_events).values()
        if isinstance(held, type)
        and issubclass(held, BaseModel)
        and held.__module__ == gardener_events.__name__
    ]

    assert TaskPlanned in models and LoggedText in models
    clashes = {
        model.__name__: sorted({"event", "at", "level"} & set(model.model_fields))
        for model in models
        if {"event", "at", "level"} & set(model.model_fields)
    }
    assert clashes == {}


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        (TaskPlanned, "task-planned"),
        (PeriodsChosen, "periods-chosen"),
        (DownloadOverBudget, "download-over-budget"),
        (LoggedText, "logged-text"),
    ],
)
def test_an_event_is_named_for_its_class_in_kebab_case(kind: type[Model], name: str) -> None:
    assert event_log.name_of(kind) == name


def test_a_declaration_with_no_ceiling_says_null_rather_than_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """None is left out of a line, but a knob that is null in its declaration is still a knob."""
    planned = TaskPlanned(
        task="old-days",
        kind=TaskKind.RETENTION,
        shard=0,
        run_id="2026-10-07-1",
        attempt=1,
        today="2026-10-07",
        operator_range=None,
        declared={"dry_run": True, "max_deletes_per_run": None},
        absent=[],
    )

    said = json.loads(line_of(emitted(caplog, planned)))

    assert said["declared"] == {"dry_run": True, "max_deletes_per_run": None}
    assert "operator_range" not in said


def test_on_github_the_handler_writes_the_commands_around_an_event_on_the_event_s_own_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A group opens before a task's first line and closes after its last; text stands alone.

    Under pytest `install` adds no handler, so the formatter is read directly.
    """
    planned = TaskPlanned(
        task="old-days",
        kind=TaskKind.RETENTION,
        shard=0,
        run_id="2026-10-07-1",
        attempt=1,
        today="2026-10-07",
        operator_range=None,
        declared={},
        absent=[],
    )
    with caplog.at_level(logging.INFO):
        event_log.emit(planned)
        event_log.emit(finished())
        logging.getLogger("idhazh.ledger").warning("said as text")
    opened, closed, text = caplog.records
    github = event_log.GitHubLines()

    assert github.format(opened).split("\n") == ["::group::old-days (retention)", line_of(opened)]
    assert github.format(closed).split("\n") == [line_of(closed), "::endgroup::"]
    assert github.format(text) == line_of(text)
    assert line_of(opened).startswith('{"event":"task-planned"'), "the plain line grew a command"


def test_the_gardener_command_lines_write_every_line_as_json_on_stderr_in_utc() -> None:
    """The handler `settings_or_none` installs, twice over, in a process whose clock is not UTC.

    One line a record means one handler; the second call added none.
    """
    script = textwrap.dedent(
        f"""
        import logging, sys
        from pathlib import Path
        from idhazh.contracts.gardener_events import RawFileSkipped
        from idhazh.gardener import cli, event_log
        for _ in range(2):
            assert cli.settings_or_none(Path(sys.argv[1])) is not None
        event_log.emit(RawFileSkipped(path="state/raw/x/notes.txt"), level=logging.WARNING)
        record = logging.LogRecord("idhazh.ledger", logging.WARNING, "x", 1, "said %s", ("so",), None)
        record.created = {AN_INSTANT.timestamp()!r}
        logging.getLogger().handle(record)
        """
    )
    environment = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "backend"),
        "TZ": NOT_UTC,
    }

    done = subprocess.run(
        [sys.executable, "-c", script, str(CONFIG_DIR)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout == ""
    first, second = (json.loads(line) for line in done.stderr.splitlines())
    assert (first["event"], first["level"], first["path"]) == (
        "raw-file-skipped",
        "warning",
        "state/raw/x/notes.txt",
    )
    assert first["at"].endswith("Z")
    assert second == {
        "event": "logged-text",
        "at": STAMPED,
        "level": "warning",
        "logger": "idhazh.ledger",
        "message": "said so",
    }


def test_on_github_the_command_line_folds_each_task_into_a_group_on_stderr() -> None:
    """`settings_or_none(..., github=True)`, in a fresh process: the commands ride the event lines.

    A task that failed closes its group and then adds its one error line, all on
    stderr, so nothing can print between a command and the event it belongs to.
    """
    script = textwrap.dedent(
        """
        import logging, sys
        from pathlib import Path
        from idhazh.contracts.collection_prune import StopReason
        from idhazh.contracts.gardener_events import TaskFinished, TaskOutcome, TaskPlanned
        from idhazh.contracts.gardener_fault import GardenerFault
        from idhazh.contracts.knobs.gardener import TaskKind
        from idhazh.gardener import cli, event_log
        assert cli.settings_or_none(Path(sys.argv[1]), github=True) is not None
        event_log.emit(TaskPlanned(
            task="defect", kind=TaskKind.RETENTION, shard=0, run_id="2026-10-07-1", attempt=1,
            today="2026-10-07", operator_range=None, declared={}, absent=[],
        ))
        event_log.emit(TaskFinished(
            task="defect", outcome=TaskOutcome.FAILED, dry_run=False, seen=0, selected=0,
            taken=[], written=[], bytes_freed=0, stopped_because=StopReason.FAILED,
            fault=GardenerFault.RAISED, error="KeyError", recovered=[],
            next="a code defect stopped it, and the log names the error", duration_ms=1,
        ), level=logging.ERROR)
        """
    )
    environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")}

    done = subprocess.run(
        [sys.executable, "-c", script, str(CONFIG_DIR)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout == ""
    said = [
        line if line.startswith("::") else json.loads(line)["event"]
        for line in done.stderr.splitlines()
    ]
    assert said == [
        "::group::defect (retention)",
        "task-planned",
        "task-finished",
        "::endgroup::",
        "::error title=defect::raised (KeyError): a code defect stopped it, and the log names "
        "the error",
    ]
