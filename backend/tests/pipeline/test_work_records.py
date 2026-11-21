"""What does a work shard say while it is still running?

A 5x model-time regression ran for six days because a 200-minute shard printed
nothing during it, and the one per-item line that did fire fired only for items
that passed. These tests read the stage's own log, over a real run of the work
stage against captured pages and recorded replies - no network and nothing
mocked (Guardrail #7).

Runs use one fixture item, or two when ordering and shard totals need siblings.
Their cost does not move when the archive grows (Guardrail #12).
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

from pytest import LogCaptureFixture, MonkeyPatch
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR
from support.prompts import WIND_TEXT, chart_data_over
from test_classify import a_reply

from idhazh import config
from idhazh.contracts.article import Article
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    NoneReason,
    VisualDecision,
    VisualKind,
)
from idhazh.fetch import FetchResult, FetchTimings
from idhazh.llm.server import Completion
from idhazh.stages.summarize_one_item import _decide_the_visual, _silent_recorder
from idhazh.telemetry.record import persist, recorded_row

from ._builders import (
    _work_stage,
    captured_article_fetch,
    declining_wind_reply,
    drawable_article_fetch,
    finding_the_wind_countries,
    plan,
    publish_worker_items,
)

#: Two items prove ordering and totals across siblings.
PLANNED_ITEMS: Final = 2

SUMMARIZE_AND_PLAN_REPLY: Final = (
    FIXTURES_DIR / "completions" / "summarize-and-plan" / "summary-and-plan.json"
)

#: The recorded reply the output budget really cut, part-way through the plan.
#: `length` is what the server wrote, so nothing is edited in to drive it.
CUT_IN_THE_PLAN_REPLY: Final = (
    FIXTURES_DIR / "completions" / "summarize-and-plan" / "cut-in-the-plan.json"
)

#: How long the recorded server is held before it answers a request. Long enough
#: that a millisecond clock cannot round it away.
HELD_S: Final = 0.05


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
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    caplog: LogCaptureFixture,
    *,
    item_count: int = 1,
) -> RunPlan:
    """One real work stage, with its log captured."""
    caplog.set_level(logging.INFO, logger="idhazh")
    run_plan, _, _ = _work_stage(
        tmp_path,
        monkeypatch,
        replies=(SUMMARIZE_AND_PLAN_REPLY.read_bytes(),),
        run_plan=plan(item_count=item_count),
    )
    return run_plan


def test_every_item_says_it_started_before_anything_can_kill_it(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """A shard killed on its timeout names the item it died on."""
    run_a_shard(tmp_path, monkeypatch, caplog, item_count=PLANNED_ITEMS)

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
            for cell in ("fetch_ms", "extract_ms", "analyze_ms", "summarize_ms", "faithfulness_ms")
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


def test_the_model_call_says_what_it_was_sent_without_carrying_the_text(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """The digest survives both capture flags being off; the prompt does not."""
    run_a_shard(tmp_path, monkeypatch, caplog)

    calls_made = [
        record for record in named(caplog, "stage.done") if record.get("call") is not None
    ]

    assert {record["call"] for record in calls_made} == {"summary"}
    for record in calls_made:
        assert len(record["prompt_sha256"]) == 64
        assert record["prompt_chars"] > 0
        assert "prompt" not in record


def test_the_shard_record_totals_the_run_and_names_its_slowest_item(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """One line at the end, which is what a person reads first on a bad day."""
    run_a_shard(tmp_path, monkeypatch, caplog, item_count=PLANNED_ITEMS)

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
    caplog.set_level(logging.INFO, logger="idhazh")
    with finding_the_wind_countries(config.load(CONFIG_DIR)) as settings:
        run_plan, items, server = _work_stage(
            tmp_path / "worker", monkeypatch,
            replies=(declining_wind_reply(),),
            fetcher=drawable_article_fetch,
            run_plan=plan(item_count=1),
            settings=settings,
        )
    item_id = run_plan.items[0].item_id
    decision = VisualDecision.read(items / f"{item_id}{PAYLOAD_SUFFIX}")
    recorded = recorded_row(items, item_id)
    assert server.served == 1
    assert decision.kind is VisualKind.NONE
    assert decision.none_reason is NoneReason.MODEL_DECLINED
    assert decision.rationale == (
        "The summary already gives the approvals; another display would repeat it."
    )
    assert decision.asked_the_model is True
    assert decision.data_path is None
    assert recorded is not None
    assert recorded.outcome.value == "ok" and recorded.detail is None
    assert recorded.failed_field is None and recorded.failed_rule is None
    done = named(caplog, "item.done")
    assert len(done) == 1
    assert done[0]["outcome"] == "ok" and done[0]["detail"] is None
    day = publish_worker_items(run_plan, items, tmp_path / "publisher", monkeypatch)
    assert len(day.items) == 1
    assert day.items[0].item_id == item_id
    assert day.items[0].visual is None


def test_a_malformed_chart_answer_keeps_shape_diagnostics_off_the_success_detail(
    tmp_path: Path, caplog: LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="idhazh")
    settings = config.load(CONFIG_DIR)
    article = Article.read(CONTRACT_FIXTURES_DIR / "article" / "ok.json")
    summary = Summary.read(CONTRACT_FIXTURES_DIR / "summary" / "ok.json")
    table, data = chart_data_over(article, WIND_TEXT)
    recorder = _silent_recorder()
    recorder.note(**ItemHealthRow.read(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json"
    ).model_dump(mode="json"))

    decision = _decide_the_visual(
        summary,
        Completion(
            content=a_reply(title=None, caption="model-only words"), finish_reason="stop"
        ),
        table,
        data=data, text=WIND_TEXT,
        settings=settings, date="2026-08-21",
        stamp={
            "version": VisualDecision.schema_version(), "model_id": "fixture-model",
            "decided_at": "2026-08-21T12:00:00Z",
        },
        run_id="2026-08-21-1", recorder=recorder,
    )
    row = ItemHealthRow.read(persist(tmp_path, recorder.close()))

    assert summary.status is SummaryStatus.OK and summary.summary
    assert row.outcome.value == "ok" and row.detail is None
    assert row.failed_field == "visual.title"
    assert row.failed_rule == "visual_choice_title_required"
    assert decision.rationale and row.failed_field in decision.rationale
    assert row.failed_rule in decision.rationale
    assert "model-only words" not in caplog.text
    assert "input_value" not in caplog.text


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
        replies=(SUMMARIZE_AND_PLAN_REPLY.read_bytes(),),
        fetcher=reader,
        run_plan=plan(item_count=1),
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
    """Every item record whose model call answered.

    An item that died before the request carries an empty call slot, and a
    test about what a call recorded has nothing to say about one.
    """
    made = [record for record in named(caplog, "item.done") if record["summary_kind"] is not None]
    assert made, "no item in the shard got a reply, so there is no call to read"
    return made


def test_a_reply_that_named_no_reason_leaves_the_column_empty_and_a_cut_one_says_length(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """A missing `finish_reason` is recorded as missing, over a real run and recorded replies.

    The first reply is the recorded one with its `finish_reason` deleted, which
    is what a runtime that reports none looks like on the wire. Until this was
    fixed that absence was read as `stop` - so the census said the decode ended
    cleanly on the strength of a field nobody had sent, and no reader could ever
    tell the two apart afterwards.

    The second is the recorded one the output budget really cut, so `length` is
    what the server wrote rather than what a test edited in.
    """
    caplog.set_level(logging.INFO, logger="idhazh")
    unreported = json.loads(SUMMARIZE_AND_PLAN_REPLY.read_text(encoding="utf-8"))
    del unreported["choices"][0]["finish_reason"]
    _work_stage(
        tmp_path / "unreported",
        monkeypatch,
        replies=(json.dumps(unreported).encode("utf-8"),),
        run_plan=plan(item_count=1),
    )
    reasons = [record["summary_finish_reason"] for record in served_calls(caplog)]
    caplog.clear()
    _work_stage(
        tmp_path / "cut",
        monkeypatch,
        replies=(CUT_IN_THE_PLAN_REPLY.read_bytes(),),
        run_plan=plan(item_count=1),
    )
    reasons += [record["summary_finish_reason"] for record in served_calls(caplog)]

    assert reasons == [None, "length"]


def test_a_call_that_waited_is_clocked_at_more_than_the_server_claimed(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """The other half: `summary_ms` is a stopwatch, not a sum.

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
        replies=(SUMMARIZE_AND_PLAN_REPLY.read_bytes(),),
        hold_s=HELD_S,
        run_plan=plan(item_count=1),
    )

    for record in served_calls(caplog):
        claimed = record["summary_prefill_ms"] + record["summary_decode_ms"]
        assert record["summary_ms"] > claimed
        assert record["summary_ms"] >= int(HELD_S * 1000)


def test_the_captures_land_beside_the_items_and_never_inside_them(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """`items/` is downloaded whole by assemble and has a different retention window.

    A rendered prompt carries the article body inside it, so the directory it
    lands in decides who ends up holding that text, and an article body is never
    republished to a reader.
    """
    run_plan = run_a_shard(tmp_path, monkeypatch, caplog)

    run_dir = tmp_path / "run" / run_plan.date
    captured = sorted(path.name for path in (run_dir / "captures").glob("*.json"))

    assert captured
    assert [
        path.name
        for path in (run_dir / "items").glob("*.json")
        if "reply_sha256" in path.read_text(encoding="utf-8")
    ] == []
