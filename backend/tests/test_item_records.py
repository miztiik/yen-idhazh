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
from conftest import CONFIG_DIR, FIXTURES_DIR
from pydantic import ValidationError

from idhazh import capture, config, telemetry
from idhazh.contracts.article import Article
from idhazh.contracts.call_cost import CallCost, CallKind
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome, ItemStage, TimeSource
from idhazh.contracts.run_plan import PlannedItem
from idhazh.telemetry import events, host
from idhazh.telemetry.record import NAMED_STAGE_MS, Flags, ItemRecorder, shard_done


def recorder(handler: logging.Handler | None = None, **flags: object) -> ItemRecorder:
    """One recorder on a logger of the test's own, with a clock it owns."""
    log = logging.getLogger(f"test.record.{id(handler)}")
    log.handlers = [handler] if handler is not None else []
    log.setLevel(logging.INFO)
    log.propagate = False
    return ItemRecorder(
        run_id="2026-09-15-1",
        flags=Flags(**flags),  # type: ignore[arg-type]
        now=lambda: "2026-09-15T06:00:00Z",
        log=log,
    )


def settled(subject: ItemRecorder, **cells: object) -> ItemRecorder:
    """Note the cells no census row can be built without, plus the test's own.

    Nine identity columns and the two that say how the item ended. `close`
    returns the row itself now, so a recorder that was never told which item
    stopped where has nothing to return - which is the point, and is why a test
    about the clock still has to say this much.
    """
    subject.note(
        **{
            "date": "2026-09-15",
            "run_id": "2026-09-15-1",
            "item_id": "ai-01",
            "url_key": "f" * 64,
            "canonical_url": "https://example.com/one",
            "vertical": "ai",
            "source_id": "example",
            "stage": ItemStage.PUBLISH.value,
            "outcome": ItemOutcome.OK.value,
            **cells,
        }
    )
    return subject


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
    subject = settled(
        recorder(lines), fetch_ms=900, extract_ms=120, summarize_ms=475890, shard=0
    )

    subject.done()

    record = lines.parsed()[-1]
    for column in ItemHealthRow.csv_columns():
        assert column in record, f"the record does not carry {column}"
    assert record["name"] == "item.done"
    assert record["run"] == "2026-09-15-1"


def _planned(article: Article) -> PlannedItem:
    """The plan entry the ranker would have written for this article.

    Built from the article rather than restated, so the two cannot disagree
    about which item this is, and every ranking term carries a distinct value -
    a term left at its default proves nothing about the term beside it.
    """
    return PlannedItem(
        item_id=article.item_id,
        url_key=article.url_key,
        source_url=article.source_url,
        canonical_url=article.canonical_url,
        source_id=article.source_id,
        tier=article.tier,
        source_form=article.source_form,
        vertical=article.vertical,
        title=article.title,
        published_at=article.fetched_at,
        time_source=TimeSource.FEED,
        carried_by=3,
        watchlist_hit=True,
        on_front_page=True,
        rank_score=0.71,
        authority_score=0.62,
        tier_score=0.90,
        feed_weight=0.55,
        feed_reliability=0.97,
        carriage_step=0.12,
        watchlist_bonus=0.08,
        lens_bonus=0.04,
        recency_bonus=0.31,
    )


def test_every_cell_the_stage_hands_over_arrives_on_the_row() -> None:
    """Nothing a stage records is dropped between the cell and the column.

    One item, driven from a canary article this test builds - fixed in size,
    and carrying injected text no committed row may ever have produced
    (`CLAUDE.md` section 13, Guardrail #12). The cells are the work stage's own
    three builders rather than a list restated here, so a cell added there is
    covered the same day it lands.

    **It cannot settle whether a cell is right.** Only that every cell handed to
    the recorder reaches the row equal to what went in - which is the property
    that was missing while `close` returned a mapping: about 53 of these were
    computed on every item and dropped with nothing raising anywhere.
    """
    from idhazh.stages import work
    from utilities import build_canary_day

    settings = config.load(CONFIG_DIR)
    canary = build_canary_day.canaries(FIXTURES_DIR / "canaries")[0]
    article = build_canary_day.article_for(0, canary, build_canary_day.SCORED[0])
    handed: dict[str, object] = {
        "date": "2026-09-15",
        "run_id": "2026-09-15-1",
        "item_started_at": "2026-09-15T06:00:00Z",
        **work._shard_cells(
            settings,
            shard=2,
            shard_item_count=8,
            facts=host.HostFacts(
                cpu_model="Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz",
                runner_name="ubuntu-4core-3",
                cgroup_peak_bytes=15_032_385_536,
            ),
        ),
        **work._planned_cells(_planned(article), index=0),
        **work._article_cells(article),
        "stage": ItemStage.PUBLISH.value,
        "outcome": ItemOutcome.OK.value,
    }
    subject = recorder()
    subject.note(**handed)

    row = subject.close()

    lost = [
        name for name, given in handed.items() if given is not None and getattr(row, name) is None
    ]
    assert lost == [], f"the row dropped a cell it was handed: {lost}"
    # `model_quantisation` is the one cell that cannot arrive as it was handed:
    # the config spells it `Q4_K_M` and the column takes a lowercase token, so
    # the column folds it on the way in. That is the column working rather than
    # a cell lost - and naming it here is what keeps a second one from joining
    # it unnoticed.
    changed = [name for name, given in handed.items() if getattr(row, name) != given]
    assert changed == ["model_quantisation"]
    assert row.model_quantisation == str(handed["model_quantisation"]).lower()
    assert len(handed) > 40, "the stage hands over more than a handful, and this proves it"


def test_a_call_slot_with_numbers_and_no_kind_is_half_a_call() -> None:
    """The test that would have caught the absent cell the pair could not be built without.

    `ItemHealthRow` holds a slot to filling whole or not at all, so five numbers
    under `label_*` and no `label_kind` is a row nothing can build - and while
    `close` handed back a mapping, that was a row nobody tried to build. Both
    calls are driven through the work stage's own cell builder.
    """
    from idhazh.llm.server import Completion
    from idhazh.stages.two_calls import _call_cells

    label = Completion(
        content="{}", prompt_tokens=1497, completion_tokens=205,
        prefill_ms=214122, decode_ms=88795, cached_tokens=0,
    )
    answer = Completion(
        content="{}", prompt_tokens=2389, completion_tokens=567,
        prefill_ms=186750, decode_ms=292626, cached_tokens=1493,
    )
    pair = _call_cells("label", CallKind.LABEL, label, wall_ms=303_004) | _call_cells(
        "summary", CallKind.SUMMARIZE_AND_PLAN, answer, wall_ms=479_500
    )

    row = settled(
        recorder(),
        model_calls=2,
        prefill_ms=label.prefill_ms + answer.prefill_ms,
        decode_ms=label.decode_ms + answer.decode_ms,
        input_tokens=label.prompt_tokens + answer.prompt_tokens,
        output_tokens=label.completion_tokens + answer.completion_tokens,
        cached_tokens=label.cached_tokens + answer.cached_tokens,
        **pair,
    ).close()

    assert row.label_kind is CallKind.LABEL
    assert row.summary_kind is CallKind.SUMMARIZE_AND_PLAN
    assert row.summary_cache_pct == 62.49, "the second call reuses what the first read cold"

    without_the_kind = {name: value for name, value in pair.items() if name != "label_kind"}
    with pytest.raises(ValidationError, match="recorded whole or not at all"):
        settled(recorder(), model_calls=2, **without_the_kind).close()


def test_a_calls_clock_is_the_stopwatch_and_not_the_two_cells_beside_it() -> None:
    """`label_ms` used to be `label_prefill_ms + label_decode_ms`.

    That is a column which agrees with its two neighbours by construction, so
    subtracting them gave zero on every row ever written and a server that made
    an item queue read exactly like one that answered at once. Driven from a
    reply a server really sent, so the five minutes it claims for itself are its
    own number and not a figure this test chose (Guardrail #7).
    """
    from idhazh.llm.server import parse_completion
    from idhazh.stages.two_calls import _call_cells

    reply = parse_completion(
        (FIXTURES_DIR / "completions" / "rendered" / "label.json").read_text(encoding="utf-8")
    )
    claimed = reply.prefill_ms + reply.decode_ms

    cells = _call_cells("label", CallKind.LABEL, reply, wall_ms=claimed + 1_234)

    assert claimed == 299_178, "the recorded reply claims this much for itself"
    assert cells["label_prefill_ms"] + cells["label_decode_ms"] == claimed
    assert cells["label_ms"] == claimed + 1_234
    assert cells["label_finish_reason"] == "length"


def test_the_gap_is_the_item_minus_the_stages_that_named_themselves() -> None:
    """`stage_gap_ms` is the only cell that can catch a step nobody thought to time.

    Signed on purpose, and the arithmetic is asserted rather than described: the
    four named stages are subtracted from the item's own wall clock and what is
    left is whatever the stage did between them.
    """
    subject = settled(
        recorder(), fetch_ms=900, extract_ms=120, summarize_ms=475890, faithfulness_ms=1400
    )

    row = subject.close()

    total = row.item_total_ms
    assert isinstance(total, int)
    named = 900 + 120 + 475890 + 1400
    assert row.stage_gap_ms == total - named


def test_the_split_of_the_model_stage_is_not_subtracted_twice() -> None:
    """`label_ms` and `summary_ms` decompose `summarize_ms` and are not named stages.

    Counting them as well would charge the model stage twice and drive the gap
    hundreds of thousands of milliseconds negative on every ordinary item.
    """
    assert "label_ms" not in NAMED_STAGE_MS
    assert "summary_ms" not in NAMED_STAGE_MS

    subject = settled(recorder(), summarize_ms=475890, label_ms=97879, summary_ms=378011)

    row = subject.close()

    total = row.item_total_ms
    assert isinstance(total, int)
    assert row.stage_gap_ms == total - 475890


def test_a_cell_name_no_column_declares_is_refused_at_the_call_site() -> None:
    """A typo fails the run rather than minting a field nobody reads."""
    subject = recorder()

    with pytest.raises(ValueError, match="names no column"):
        subject.note(summarise_ms=475890)


def test_a_nested_event_name_cannot_be_written_as_a_flat_record() -> None:
    """Two shapes, one vocabulary, and the name decides which - checkably."""
    with pytest.raises(ValueError, match="nested event"):
        events.record(
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
    subject = settled(recorder(lines, item_lines=False, stage_lines=False), fetch_ms=900)

    row = subject.done()

    assert lines.said == []
    assert isinstance(row.item_total_ms, int)


def test_the_shard_record_counts_failures_by_code_and_names_one_item() -> None:
    """The question asked of a finished shard is which code moved, not which items."""
    lines = Lines()
    log = logging.getLogger("test.record.shard")
    log.handlers = [lines]
    log.setLevel(logging.INFO)
    log.propagate = False

    shard_done(
        run_id="2026-09-15-1",
        shard=1,
        flags=Flags(),
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

    def costing(item_id: str, ms: int, url: str, source: str) -> ItemHealthRow:
        """One finished row at a stated cost - the recorder's own clock cannot be told."""
        row = settled(recorder(), item_id=item_id, canonical_url=url, source_id=source).close()
        return row.model_copy(update={"item_total_ms": ms})

    worst = _slowest(
        [
            costing("ai-01", 900, "https://a/1", "a"),
            costing("ai-07", 475890, "https://b/7", "b"),
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
    subject = settled(
        recorder(lines),
        stage=ItemStage.SUMMARIZE.value,
        outcome=ItemOutcome.FAILED.value,
        code="bad_shape",
        detail="the reply did not hold its shape\nand said so over two lines",
    )

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
        about=capture.About(
            canonical_url="https://example.org/wind-farm",
            source_id="dna-india",
            title="A wind farm starts sending power",
        ),
    )

    payload = json.loads(written[0])
    assert payload["cost"]["kind"] == "summarize_and_plan"
    assert payload["cost"]["cached_tokens"] == 3886
    assert payload["decode_split"]["plan_ms"] == 1178
    assert payload["finish_reason"] == "length"
    assert payload["about"]["canonical_url"] == "https://example.org/wind-farm"
    assert payload["about"]["source_id"] == "dna-india"


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
    assert payload["about"] is None
