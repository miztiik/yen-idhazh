"""What does one item's record say, and does it say it in the census row's own words?

The whole instrument rests on one property: a name on a log line and a column in
`state/item-health.csv` are the same name, derived from one place. These tests
drive that from a built recorder rather than from a run, so the awkward cases -
an item that skipped a stage, a cell nobody filled, a typo at a call site - are
present rather than waited for.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from idhazh import capture, itemrecord, telemetry
from idhazh.contracts.call_cost import CallCost, CallKind
from idhazh.contracts.item_health import ItemHealthRow, ItemStage


def recorder(
    handler: logging.Handler | None = None, **flags: object
) -> itemrecord.ItemRecorder:
    """One recorder on a logger of the test's own, with a clock it owns."""
    log = logging.getLogger(f"test.itemrecord.{id(handler)}")
    log.handlers = [handler] if handler is not None else []
    log.setLevel(logging.INFO)
    log.propagate = False
    return itemrecord.ItemRecorder(
        run_id="34852763827",
        flags=itemrecord.Flags(**flags),  # type: ignore[arg-type]
        now=lambda: "2026-09-15T06:00:00Z",
        log=log,
    )


class Lines(logging.Handler):
    """Every record the run emitted, as the strings a job log would hold."""

    def __init__(self) -> None:
        super().__init__()
        self.said: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.said.append(record.getMessage())

    def parsed(self) -> list[dict[str, object]]:
        return [json.loads(line) for line in self.said]


def test_a_completion_record_carries_every_column_the_census_row_declares() -> None:
    """The oracle. A field on the row and absent from the record is the drift this ends.

    Absent cells are present and null on purpose: a grep for one field across a
    shard has to find every item, and the item that skipped a stage is exactly
    the one worth finding.
    """
    lines = Lines()
    subject = recorder(lines)
    subject.note(item_id="ai-01", shard=0, fetch_ms=900, extract_ms=120, summarize_ms=475890)

    subject.done()

    record = lines.parsed()[-1]
    for column in ItemHealthRow.csv_columns():
        assert column in record, f"the record does not carry {column}"
    assert record["name"] == "item.done"
    assert record["run"] == "34852763827"


def test_the_gap_is_the_item_minus_the_stages_that_named_themselves() -> None:
    """`stage_gap_ms` is the only cell that can catch a step nobody thought to time.

    Signed on purpose, and the arithmetic is asserted rather than described: the
    four named stages are subtracted from the item's own wall clock and what is
    left is whatever the stage did between them.
    """
    subject = recorder()
    subject.note(fetch_ms=900, extract_ms=120, summarize_ms=475890, faithfulness_ms=1400)

    cells = subject.close()

    total = cells["item_total_ms"]
    assert isinstance(total, int)
    named = 900 + 120 + 475890 + 1400
    assert cells["stage_gap_ms"] == total - named


def test_the_split_of_the_model_stage_is_not_subtracted_twice() -> None:
    """`label_ms` and `summary_ms` decompose `summarize_ms` and are not named stages.

    Counting them as well would charge the model stage twice and drive the gap
    hundreds of thousands of milliseconds negative on every ordinary item.
    """
    assert "label_ms" not in itemrecord.NAMED_STAGE_MS
    assert "summary_ms" not in itemrecord.NAMED_STAGE_MS

    subject = recorder()
    subject.note(summarize_ms=475890, label_ms=97879, summary_ms=378011)

    cells = subject.close()

    total = cells["item_total_ms"]
    assert isinstance(total, int)
    assert cells["stage_gap_ms"] == total - 475890


def test_a_cell_name_no_column_declares_is_refused_at_the_call_site() -> None:
    """A typo fails the run rather than minting a field nobody reads."""
    subject = recorder()

    with pytest.raises(ValueError, match="names no column"):
        subject.note(summarise_ms=475890)


def test_a_nested_event_name_cannot_be_written_as_a_flat_record() -> None:
    """Two shapes, one vocabulary, and the name decides which - checkably."""
    with pytest.raises(ValueError, match="nested event"):
        telemetry.record(
            ts="2026-09-15T06:00:00Z",
            src=ItemStage.SUMMARIZE,
            run="r",
            name=telemetry.EventName.ITEM_SUMMARIZE_FAILED,
            cells={},
        )


def test_a_flat_record_name_cannot_be_written_as_a_nested_event() -> None:
    """The refusal runs both ways, or the split is a convention rather than a rule."""
    with pytest.raises(ValueError, match="flat record"):
        telemetry.event(
            ts="2026-09-15T06:00:00Z",
            src=ItemStage.SUMMARIZE,
            run="r",
            name=telemetry.EventName.ITEM_DONE,
            level=telemetry.EventLevel.WARNING,
            ctx={},
            data={},
        )


def test_an_item_that_starts_is_named_before_anything_can_kill_it() -> None:
    """A shard killed on its timeout has to name the item it died on."""
    lines = Lines()
    subject = recorder(lines)
    subject.note(item_id="ai-07", item_index=6, shard=2)

    subject.start()

    record = lines.parsed()[0]
    assert record["name"] == "item.start"
    assert record["item_id"] == "ai-07"
    assert record["item_index"] == 6


def test_turning_the_item_lines_off_stops_the_record_and_not_the_clock() -> None:
    """The flags choose which records exist; the cells are built either way.

    The stage reads `item_total_ms` back off the recorder, so a flag that
    stopped the arithmetic would change behaviour rather than volume.
    """
    lines = Lines()
    subject = recorder(lines, item_lines=False, stage_lines=False)
    subject.note(fetch_ms=900)

    cells = subject.done()

    assert lines.said == []
    assert isinstance(cells["item_total_ms"], int)


def test_the_shard_record_counts_failures_by_code_and_names_one_item() -> None:
    """The question asked of a finished shard is which code moved, not which items."""
    lines = Lines()
    log = logging.getLogger("test.itemrecord.shard")
    log.handlers = [lines]
    log.setLevel(logging.INFO)
    log.propagate = False

    itemrecord.shard_done(
        run_id="34852763827",
        shard=1,
        flags=itemrecord.Flags(),
        now=lambda: "2026-09-15T06:00:00Z",
        log=log,
        items=80,
        failures={"bad_shape": 3, "labels_truncated": 1},
        slowest={"item_id": "ai-07", "item_total_ms": 475890},
    )

    record = lines.parsed()[-1]
    assert record["name"] == "shard.done"
    assert record["items"] == 80
    assert record["failures"] == {"bad_shape": 3, "labels_truncated": 1}
    assert record["slowest"] == {"item_id": "ai-07", "item_total_ms": 475890}


def test_the_slowest_item_is_addressed_by_url_and_never_by_its_title() -> None:
    """A title is fetched text and a log line is read by a person (Guardrail #11)."""
    from idhazh.stages.work import _slowest

    worst = _slowest(
        [
            {"item_id": "ai-01", "item_total_ms": 900, "canonical_url": "https://a/1"},
            {
                "item_id": "ai-07",
                "item_total_ms": 475890,
                "canonical_url": "https://b/7",
                "source_id": "b",
            },
        ]
    )

    assert worst == {
        "item_id": "ai-07",
        "canonical_url": "https://b/7",
        "source_id": "b",
        "item_total_ms": 475890,
    }
    assert "title" not in (worst or {})


def test_a_record_is_one_line_whatever_the_text_it_carries() -> None:
    """A record that wrapped would need a multi-line parser to read one item back."""
    lines = Lines()
    subject = recorder(lines)
    subject.note(detail="the reply did not hold its shape\nand said so over two lines")

    subject.done()

    assert len(lines.said) == 1
    assert "\n" not in lines.said[0]


def test_the_capture_records_its_digest_with_both_flags_off(tmp_path: Path) -> None:
    """The cheap default still answers "did the prompt change between these runs?"."""
    written: list[str] = []

    kept = capture.of(
        root=tmp_path,
        item_id="ai-01",
        call="label",
        prompt="the rendered prompt",
        reply="the reply",
        keep_prompt=False,
        keep_reply=False,
        write=lambda path, text: written.append(text),
    )

    assert written == []
    assert kept.captured is False
    assert kept.prompt_chars == len("the rendered prompt")
    assert len(kept.prompt_sha256) == 64


def test_a_captured_call_keeps_only_the_half_its_flag_allows(tmp_path: Path) -> None:
    """Two flags because a reply is the longest text in the run and a prompt is not."""
    written: list[str] = []

    kept = capture.of(
        root=tmp_path,
        item_id="ai-01",
        call="summary",
        prompt="the rendered prompt",
        reply="the reply",
        keep_prompt=True,
        keep_reply=False,
        write=lambda path, text: written.append(text),
    )

    payload = json.loads(written[0])
    assert payload["prompt"] == "the rendered prompt"
    assert payload["reply"] is None
    assert payload["reply_chars"] == len("the reply")
    assert kept.captured is True


def test_a_capture_carries_what_its_own_call_cost(tmp_path: Path) -> None:
    """The artifact outlives the ledger row, so it says what the call cost itself."""
    written: list[str] = []

    capture.of(
        root=tmp_path,
        item_id="ai-01",
        call="summary",
        prompt="the rendered prompt",
        reply="the reply",
        keep_prompt=True,
        keep_reply=True,
        write=lambda path, text: written.append(text),
        cost=CallCost(
            kind=CallKind.SUMMARIZE_AND_PLAN,
            prefill_ms=6214,
            decode_ms=3188,
            input_tokens=4214,
            output_tokens=512,
            cached_tokens=3886,
        ),
        decode_split={"summary_ms": 2010, "plan_ms": 1178, "is_estimate": True},
        finish_reason="length",
    )

    payload = json.loads(written[0])
    assert payload["cost"]["kind"] == "summarize_and_plan"
    assert payload["cost"]["cached_tokens"] == 3886
    assert payload["decode_split"]["plan_ms"] == 1178
    assert payload["finish_reason"] == "length"


def test_a_capture_with_no_cost_still_names_the_key(tmp_path: Path) -> None:
    """An absent key and a zero cost are two findings, so they cannot look alike."""
    written: list[str] = []

    capture.of(
        root=tmp_path,
        item_id="ai-01",
        call="label",
        prompt="the rendered prompt",
        reply="",
        keep_prompt=True,
        keep_reply=False,
        write=lambda path, text: written.append(text),
    )

    payload = json.loads(written[0])
    assert payload["cost"] is None
    assert payload["decode_split"] is None
    assert payload["finish_reason"] == ""
