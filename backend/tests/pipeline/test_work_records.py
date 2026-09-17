"""What does a work shard say while it is still running?

A 5x model-time regression ran for six days because a 200-minute shard printed
nothing during it, and the one per-item line that did fire fired only for items
that passed. These tests read the stage's own log, over a real run of the work
stage against captured pages and recorded replies - no network and nothing
mocked (Guardrail #7).

The day that run is driven from is the fixture plan's, so the volume is four
items and the cost does not move when the archive grows (Guardrail #12).
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import FIXTURES_DIR
from pytest import LogCaptureFixture, MonkeyPatch

from idhazh.contracts.item_health import ItemHealthRow
from idhazh.fetch import FetchResult, FetchTimings

from ._builders import _work_stage, captured_article_fetch

pytestmark = pytest.mark.slow

#: The fixture plan's size. Named once rather than repeated, so a sixth item
#: added to the plan moves one line here instead of three assertions.
PLANNED_ITEMS: Final = 5

LABEL_REPLY: Final = FIXTURES_DIR / "completions" / "label" / "labelled.json"

SUMMARIZE_AND_PLAN_REPLY: Final = (
    FIXTURES_DIR / "completions" / "summarize-and-plan" / "summary-and-plan.json"
)

#: The recorded reply the output budget really cut, part-way through the plan.
#: `length` is what the server wrote, so nothing is edited in to drive it.
CUT_IN_THE_PLAN_REPLY: Final = (
    FIXTURES_DIR / "completions" / "summarize-and-plan" / "cut-in-the-plan.json"
)

#: How long the recorded server is held before it answers a request. Long enough
#: that a millisecond clock cannot round it away, short enough that ten held
#: requests cost two seconds.
HELD_S: Final = 0.2


def records(caplog: LogCaptureFixture) -> list[dict[str, Any]]:
    """Every flat record the run emitted, parsed.

    The nested events share the logger and are not flat records, so they are
    dropped by shape rather than by name - a line that does not parse as one
    JSON object with a `name` key was never one of these.
    """
    found: list[dict[str, Any]] = []
    for line in caplog.messages:
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        if "ctx" not in payload:
            found.append(payload)
    return found


def named(caplog: LogCaptureFixture, name: str) -> list[dict[str, Any]]:
    return [record for record in records(caplog) if record.get("name") == name]


def run_a_shard(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """One real work stage, with its log captured."""
    caplog.set_level(logging.INFO, logger="idhazh")
    _work_stage(
        tmp_path,
        monkeypatch,
        replies=(
            LABEL_REPLY.read_bytes(),
            SUMMARIZE_AND_PLAN_REPLY.read_bytes(),
        ),
    )


def test_every_item_says_it_started_before_anything_can_kill_it(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """A shard killed on its timeout names the item it died on."""
    run_a_shard(tmp_path, monkeypatch, caplog)

    started = named(caplog, "item.start")

    assert len(started) == PLANNED_ITEMS
    assert all(record["item_id"] for record in started)
    assert [record["item_index"] for record in started] == list(range(PLANNED_ITEMS))


def test_the_completion_record_carries_every_census_column(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """The oracle, over a real run rather than a built recorder.

    A field declared on the row and absent from the record is the drift the
    whole instrument exists to end.
    """
    run_a_shard(tmp_path, monkeypatch, caplog)

    done = named(caplog, "item.done")

    assert done
    for column in ItemHealthRow.csv_columns():
        assert column in done[0], f"the record does not carry {column}"


def test_the_gap_is_the_item_minus_the_stages_that_named_themselves(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """`stage_gap_ms` plus the named stages is the item's own wall clock, to the ms."""
    run_a_shard(tmp_path, monkeypatch, caplog)

    for record in named(caplog, "item.done"):
        named_stages = sum(
            int(record[cell] or 0)
            for cell in ("fetch_ms", "extract_ms", "summarize_ms", "faithfulness_ms")
        )
        assert abs(record["item_total_ms"] - (named_stages + record["stage_gap_ms"])) <= 1


def test_an_item_that_failed_is_recorded_exactly_as_one_that_passed(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """This is the defect. The old line fired only for items that reached a band.

    The scorer is off in this run, so no item is scored and the old `item scored`
    line fires for none of them. Every item still gets a completion record.
    """
    run_a_shard(tmp_path, monkeypatch, caplog)

    assert len(named(caplog, "item.done")) == len(named(caplog, "item.start"))


def test_each_model_call_says_what_it_was_sent_without_carrying_the_text(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """The digest survives both capture flags being off; the prompt does not."""
    run_a_shard(tmp_path, monkeypatch, caplog)

    calls_made = [
        record for record in named(caplog, "stage.done") if record.get("call") is not None
    ]

    assert {record["call"] for record in calls_made} == {"label", "summary"}
    for record in calls_made:
        assert len(record["prompt_sha256"]) == 64
        assert record["prompt_chars"] > 0
        assert "prompt" not in record


def test_the_shard_record_totals_the_run_and_names_its_slowest_item(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """One line at the end, which is what a person reads first on a bad day."""
    run_a_shard(tmp_path, monkeypatch, caplog)

    shard = named(caplog, "shard.done")

    assert len(shard) == 1
    assert shard[0]["items"] == PLANNED_ITEMS
    assert isinstance(shard[0]["failures"], dict)
    assert shard[0]["slowest"] is not None
    assert "title" not in shard[0]["slowest"]


def test_the_three_cells_of_the_picture_split_move_together(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """`summary_ms` was the whole call and could not say which half moved.

    A reply with no plan half has nothing to apportion and reports nothing -
    which is correct, and is why the property asserted is that the three cells
    are filled together or empty together. A half-filled split is a row where
    somebody reads a millisecond count with no token count behind it.

    The arithmetic itself is checked in `test_decode_split.py`, against replies
    built to order rather than against whichever ones this fixture set holds.
    """
    run_a_shard(tmp_path, monkeypatch, caplog)

    done = named(caplog, "item.done")

    assert done
    for record in done:
        filled = {
            cell: record[cell] is not None
            for cell in (
                "visual_plan_ms",
                "visual_plan_ms_is_estimate",
                "visual_plan_tokens_written",
            )
        }
        assert len(set(filled.values())) == 1, filled
        if record["visual_plan_ms"] is not None:
            assert record["visual_plan_ms_is_estimate"] is True
            assert record["visual_plan_ms"] <= record["summary_ms"]


def test_a_passing_item_carries_no_failure_detail(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """`detail_cell("")` is the string "unspecified failure", and a row that
    carried it while its outcome said `ok` read as a failure nobody had.
    """
    run_a_shard(tmp_path, monkeypatch, caplog)

    for record in named(caplog, "item.done"):
        if record["outcome"] == "ok":
            assert record["detail"] is None


def test_the_fetch_split_the_socket_measured_reaches_the_record(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """Five cells were declared and nothing filled them, so a slow item was one number.

    The reader hands back a result carrying a split no arithmetic in the stage
    could invent, so a record that shows these values can only have carried
    them through from the read.
    """
    measured = FetchTimings(
        fetch_connect_ms=13, fetch_ttfb_ms=29, robots_ms=5, retry_count=2, retry_total_ms=310
    )

    def reader(url: str) -> FetchResult:
        return replace(captured_article_fetch(url), timings=measured)

    caplog.set_level(logging.INFO, logger="idhazh")
    _work_stage(
        tmp_path,
        monkeypatch,
        replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        fetcher=reader,
    )

    done = named(caplog, "item.done")

    assert done
    for record in done:
        assert {cell: record[cell] for cell in measured.cells()} == measured.cells()


def test_every_record_is_one_line_and_parses_as_one_object(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """A record that wrapped would need a multi-line parser to read one item back."""
    run_a_shard(tmp_path, monkeypatch, caplog)

    emitted = records(caplog)

    assert emitted
    for line in caplog.messages:
        assert "\n" not in line


def served_calls(caplog: LogCaptureFixture) -> list[dict[str, Any]]:
    """Every item record whose label call answered.

    An item that died before the first request carries empty call slots, and a
    test about what a call recorded has nothing to say about one.
    """
    made = [record for record in named(caplog, "item.done") if record["label_kind"] is not None]
    assert made, "no item in the shard got a reply, so there is no call to read"
    return made


def test_a_reply_that_named_no_reason_leaves_the_column_empty_and_a_cut_one_says_length(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """A missing `finish_reason` is recorded as missing, over a real run and two recorded replies.

    The label reply is the recorded one with its `finish_reason` deleted, which
    is what a runtime that reports none looks like on the wire. Until this was
    fixed that absence was read as `stop` - so the census said the decode ended
    cleanly on the strength of a field nobody had sent, and no reader could ever
    tell the two apart afterwards.

    The summarize-and-plan reply is the recorded one the output budget really
    cut, so `length` is what the server wrote rather than what a test edited in.
    """
    caplog.set_level(logging.INFO, logger="idhazh")
    unreported = json.loads(LABEL_REPLY.read_text(encoding="utf-8"))
    del unreported["choices"][0]["finish_reason"]
    _work_stage(
        tmp_path,
        monkeypatch,
        replies=(json.dumps(unreported).encode("utf-8"), CUT_IN_THE_PLAN_REPLY.read_bytes()),
    )

    for record in served_calls(caplog):
        assert record["label_finish_reason"] is None
        if record["summary_kind"] is not None:
            assert record["summary_finish_reason"] == "length"


def test_a_call_that_waited_is_clocked_at_more_than_the_server_claimed(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """The other half: `label_ms` is a stopwatch, not a sum.

    The server is held for `HELD_S` before it answers, which is a wait no field
    of the reply can report. The recorded replies carry no `timings` block at
    all, so the server claims nothing and the sum of the two cells beside this
    one is zero - which is exactly what the column used to hold, and is why a
    queue in front of the model was invisible in the census.
    """
    caplog.set_level(logging.INFO, logger="idhazh")
    _work_stage(
        tmp_path,
        monkeypatch,
        replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        hold_s=HELD_S,
    )

    for record in served_calls(caplog):
        claimed = record["label_prefill_ms"] + record["label_decode_ms"]
        assert record["label_ms"] > claimed
        assert record["label_ms"] >= int(HELD_S * 1000)


def test_the_captures_land_beside_the_items_and_never_inside_them(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """`items/` is downloaded whole by assemble and has a different retention window.

    A rendered prompt carries the article body inside it, so the directory it
    lands in decides who ends up holding that text (CLAUDE.md section 0a).
    """
    run_a_shard(tmp_path, monkeypatch, caplog)

    run_dir = tmp_path / "run" / "2026-08-21"
    captured = sorted(path.name for path in (run_dir / "captures").glob("*.json"))

    assert captured
    assert list((run_dir / "items").glob("*.label.json")) == []
