"""Are both model calls dispatched, and is the sequence walked one item at a time?"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, committed_markers, read_text
from pytest import MonkeyPatch

from idhazh import config, summarize
from idhazh.classify import calls, dag
from idhazh.contracts.call_cost import CallKind
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.item_health import FailureCode, ItemHealthRow
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    NoneReason,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.fingerprint import text_digest
from idhazh.render.write import asset_relpath
from idhazh.stages import common
from idhazh.stages.assemble import _recorded_inputs
from idhazh.telemetry.record import HEALTH_SUFFIX

from ._builders import (
    _work_stage,
    drawable_article_fetch,
    worked,
)

pytestmark = pytest.mark.slow


#: What a `Summary` carries that is a clock rather than a decision. Two runs of
#: one recorded reply agree on everything else, and these five are why "the same
#: bytes" is asserted after they come off rather than over the whole payload.
CLOCKS: Final = ("generated_at", "duration_ms", "fetch_ms", "extract_ms", "summarize_ms")

LABEL_REPLY: Final = FIXTURES_DIR / "completions" / "label" / "labelled.json"

SUMMARIZE_AND_PLAN_REPLY: Final = FIXTURES_DIR / "completions" / "summarize-and-plan" / "summary-and-plan.json"

#: The same shape, stopped by the output budget part-way through the plan. The
#: envelope says `length`, which is what the server really reports, so nothing
#: has to be edited into it to drive the cut path.
CUT_IN_THE_PLAN_REPLY: Final = FIXTURES_DIR / "completions" / "summarize-and-plan" / "cut-in-the-plan.json"


#: The recorded pair for the one article in the fixture set a bar can be drawn
#: from. Kept apart from the pair above because that pair's whole job is the
#: transport - two calls, two costs, one payload - and this pair's whole job is
#: the picture, which needs four figures in one unit to exist at all.
DRAWS_LABEL: Final = FIXTURES_DIR / "completions" / "label" / "wind-labelled.json"

DRAWS_SUMMARIZE_AND_PLAN: Final = FIXTURES_DIR / "completions" / "summarize-and-plan" / "wind-summary-and-plan.json"


def worked_requests(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    replies: tuple[bytes, ...],
) -> list[dict[str, Any]]:
    """Every request body the stage sent, in the order it sent them.

    The count answers how many calls an item took; only the bodies answer
    whether they were sent item-major, because a cycle of replies reads the same
    either way round.
    """
    _run_plan, _items, server = _work_stage(tmp_path, monkeypatch, replies=replies)
    return server.sent


def without_clocks(summary: Summary) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(summary.to_json())
    for field in CLOCKS:
        payload.pop(field, None)
    return payload


def recorded_inputs(items: Path) -> PipelineInputs:
    """What the shard recorded about its own run, named by itself.

    One name a run rather than one a shard: every shard observes the same
    configuration, so `INPUTS_PAYLOAD` settles by atomic rename and there is
    nothing to pick from.
    """
    recorded = _recorded_inputs(items)
    assert recorded is not None, "the shard summarized something and recorded no inputs"
    return recorded


class TestTheWorkStageDispatchesBothCalls:
    def test_two_requests_an_item_and_the_cost_is_split_between_them(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Trigger 1's instrument, end to end. `call_1` and `call_2` are what the
        ledger carries per call, and until something dispatched the pair the
        cells could only ever hold one call's numbers."""
        run_plan, items, served = worked(
            tmp_path,
            monkeypatch,
            replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        )

        assert served == 2 * len(run_plan.items), "the flag on is two calls an item"
        written = [
            Summary.from_json(read_text(items / f"{item.item_id}.summary.json"))
            for item in run_plan.items
        ]
        for summary in written:
            assert summary.call_1 is not None and summary.call_2 is not None
            assert summary.call_1.kind is CallKind.LABEL
            assert summary.call_2.kind is CallKind.SUMMARIZE_AND_PLAN

    def test_the_slot_columns_carry_the_first_call_and_not_whichever_ran_last(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Two calls land in a slot; the row has one set of columns for them.

        The row carries the FIRST call's, because that is the only one whose
        slot was last touched by the item before this one. The second call's
        prompt is the first one's extended by construction, so its `cache_n` is
        above zero on every row and says nothing about anything.

        Both replies are given slot facts here, and deliberately different ones,
        so a row built from whichever call happened to be last fails rather than
        passing on a coincidence. `id_slot` of 1 on the second call is a shape no
        `-np 1` server produces - that is the point of it.

        The numbers come off the recorded rendered reply and the 2026-09-15 probe
        (`docs/reference/pipeline-cost.md`); the fixtures these are written onto
        are shared by every test in this file and none of the others reads a
        count off them. The `usage` blocks are written here for the same reason
        and are what make the two cache counts mean anything - without them both
        prompts are zero tokens long and every cache count is zero by arithmetic.
        """
        label = json.loads(read_text(LABEL_REPLY)) | {"id_slot": 0, "tokens_cached": 1646}
        label["usage"] = {"prompt_tokens": 1646, "completion_tokens": 96}
        label["timings"] = {"prompt_ms": 1030.0, "predicted_ms": 611.0, "cache_n": 0}
        second = json.loads(read_text(SUMMARIZE_AND_PLAN_REPLY)) | {
            "id_slot": 1,
            "tokens_cached": 2731,
        }
        second["usage"] = {"prompt_tokens": 2731, "completion_tokens": 400}
        second["timings"] = {"prompt_ms": 60.0, "predicted_ms": 900.0, "cache_n": 1646}

        _run_plan, items, _served = worked(
            tmp_path,
            monkeypatch,
            replies=(json.dumps(label).encode("utf-8"), json.dumps(second).encode("utf-8")),
        )

        rows = [
            ItemHealthRow.from_json(read_text(path))
            for path in sorted(items.glob(f"*{HEALTH_SUFFIX}"))
        ]
        assert rows, "the stage sealed no row, so this asserts nothing"
        for row in rows:
            assert row.slot_id == 0, "the second call claimed slot 1 and does not own this column"
            assert row.kv_tokens_at_start == 1646
            assert row.prefix_shared_with_previous is False
            # The boolean and the count are one reading, off one `cache_n`. The
            # second call reused 1,646 tokens and would have made this True.
            assert row.label_cached_tokens == 0
            assert row.summary_cached_tokens == 1646

    def test_every_item_that_publishes_carries_a_decision(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The work stage decides the picture now, so the decision lands beside
        the summary rather than an hour later in another job on another model."""
        run_plan, items, _served = worked(
            tmp_path,
            monkeypatch,
            replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        )

        published = [
            item.item_id
            for item in run_plan.items
            if Summary.from_json(
                read_text(items / f"{item.item_id}.summary.json")
            ).status is SummaryStatus.OK
        ]
        assert published, "the recorded pair has to produce at least one publishable item"
        for item_id in published:
            decision = VisualDecision.from_json(read_text(items / f"{item_id}{PAYLOAD_SUFFIX}"))
            assert decision.item_id == item_id
            assert decision.asked_the_model, "the summarize-and-plan call was sent, whatever it answered"
            assert decision.decision_ms is not None

    def test_a_decided_item_leaves_a_drawn_chart_on_disk(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The reader's side of the retirement, and the only test that asks it.

        Deleting the small model takes its job and its prompt with it, and the
        two calls become the only thing that draws. Deleting it before the two
        calls drew was refused, because it takes the digest from
        17 charts a day to none. The sibling above proves an item carries a
        *decision*; a decision is not a picture, and every route to `none` also
        writes one. Nothing asserted that a file lands, so the whole of what
        stops that regression was a payload field that a refusal fills in too.

        So this reads the drawn bytes off disk at the path the payload names. It
        fails if the compiler stops compiling, if the renderer stops writing, or
        if the decision starts naming a path nothing wrote - which is the fault
        `stages.validate_days._picture_faults` catches a whole job later, on a
        day that has already published.
        """
        run_plan, items, _served = worked(
            tmp_path,
            monkeypatch,
            replies=(DRAWS_LABEL.read_bytes(), DRAWS_SUMMARIZE_AND_PLAN.read_bytes()),
            fetcher=drawable_article_fetch,
        )

        decisions = [
            VisualDecision.from_json(read_text(path))
            for path in sorted(items.glob(f"*{PAYLOAD_SUFFIX}"))
        ]
        drawn = [one for one in decisions if one.visual_state is VisualState.RENDERED]
        assert drawn, "the two calls drew nothing from the recorded pair - " + ", ".join(
            f"{one.item_id} {one.visual_state.value}"
            f"/{one.none_reason.value if one.none_reason else '-'}"
            f"/{one.failure_detail or '-'}"
            for one in decisions
        )

        public_root = common.PUBLIC_ROOT.parent
        for decision in drawn:
            assert decision.kind is VisualKind.CHART
            assert decision.data_path == asset_relpath(run_plan.date, decision.item_id), (
                "a published chart is filed under its own item id and nothing else"
            )
            asset = public_root / decision.data_path
            assert asset.is_file(), f"the payload names {decision.data_path} and nothing wrote it"
            published = VisualData.read(asset)
            named = [
                mark.text
                for mark in published.marks
                if mark.mark_id in published.encoding.category
            ]
            assert "Denmark" in named, (
                "the bars are named from the article's own entities, not from the plan's prose"
            )
            assert decision.alt_text, "a published chart carries the words a screen reader gets"
            assert decision.spec, "the chart's own spec travels with the decision"

    def test_the_stamp_digests_the_two_prompts_instead(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The two calls render their own bytes, so the turn markers decide what
        the model reads and nothing else in the record reaches them. A marker edit
        would move every reply while the record said the ask held still."""
        settings = config.load(CONFIG_DIR)

        _run_plan, items, _served = worked(
            tmp_path,
            monkeypatch,
            replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        )

        stamped = recorded_inputs(items).prompt_sha256
        assert stamped == text_digest(
            calls.prompt_inputs(settings.app.summarize, markers=committed_markers())
        )
        assert stamped != text_digest(summarize.prompt_inputs(settings.app.summarize))

    def test_a_labelling_reply_the_output_budget_cut_says_so(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Plan 11 row #3g. The cut is read off `finish_reason` before the parse.

        Until 2026-09-13 this landed as `bad_shape`, which is also what a reply
        that answered inside its budget and violated the schema records - so the
        one failure a budget can fix was hiding inside the one it cannot, and
        the only thing separating them was a sentence in a log line.
        """
        cut = json.loads(read_text(LABEL_REPLY))
        cut["choices"][0]["message"]["content"] = '{"labels": [{"element_id": "quan'
        cut["choices"][0]["finish_reason"] = "length"

        run_plan, items, served = worked(
            tmp_path,
            monkeypatch,
            replies=(json.dumps(cut).encode("utf-8"),),
        )

        assert served == len(run_plan.items), "the second call is never sent"
        written = [
            Summary.from_json(read_text(items / f"{item.item_id}.summary.json"))
            for item in run_plan.items
        ]
        assert {summary.status for summary in written} == {SummaryStatus.FAILED}
        assert {summary.failure_code for summary in written} == {FailureCode.LABELS_TRUNCATED}

    def test_a_labelling_reply_this_build_cannot_read_loses_the_item_loudly(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The other way a labelling reply is unusable: it finished, and it is wrong.

        The summarize-and-plan call's prompt replays the label call's reply verbatim and the reason that is
        safe is that the reply has been held to a closed schema - so a reply that
        did not parse stops the item rather than being sent unchecked. These
        bytes stop mid-string like a cut one and the server says `stop`, which is
        the case a budget cannot fix and a wider grammar can.
        """
        broken = json.loads(read_text(LABEL_REPLY))
        broken["choices"][0]["message"]["content"] = '{"labels": [{"element_id": "quan'

        run_plan, items, served = worked(
            tmp_path,
            monkeypatch,
            replies=(json.dumps(broken).encode("utf-8"),),
        )

        assert served == len(run_plan.items), "the second call is never sent"
        written = [
            Summary.from_json(read_text(items / f"{item.item_id}.summary.json"))
            for item in run_plan.items
        ]
        assert {summary.status for summary in written} == {SummaryStatus.FAILED}
        assert {summary.failure_code for summary in written} == {FailureCode.BAD_SHAPE}
        assert not list(items.glob(f"*{PAYLOAD_SUFFIX}")), "a lost item gets no decision"

    def test_an_item_lost_after_the_label_call_still_reports_what_it_spent(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Plan 11 row #3h. The expensive items are the ones that die here.

        Three of the four ways this item can be lost happen after the label call has
        answered and been paid for, and each used to write five zeros. A cut
        labelling reply is the worst of the three to lose: it decoded its whole
        output budget, and it was cut precisely because the article was long -
        so the day that costs the most reads as the day that cost nothing.

        Slot 2 stays empty rather than being stamped with zeros. The summarize-and-plan call was
        never sent, and an empty slot says that where a zeroed one would say it
        was free.

        The cost block is written here rather than into the fixture. The
        recorded reply is shared by every two-call test and none of the others
        reads a number off it, so a `usage` block committed there would be a
        value nothing checks - and a real llama-server reply carries one.
        """
        cut = json.loads(read_text(LABEL_REPLY))
        cut["choices"][0]["message"]["content"] = '{"labels": [{"element_id": "quan'
        cut["choices"][0]["finish_reason"] = "length"
        cut["usage"] = {"prompt_tokens": 2143, "completion_tokens": 6491}
        cut["timings"] = {"prompt_ms": 217_580.0, "predicted_ms": 659_020.0, "cache_n": 12}
        spent = cut["usage"]

        _run_plan, items, _served = worked(
            tmp_path,
            monkeypatch,
            replies=(json.dumps(cut).encode("utf-8"),),
        )

        written = [
            Summary.from_json(read_text(path)) for path in sorted(items.glob("*.summary.json"))
        ]
        assert written, "the stage summarized nothing, so this asserts nothing"
        for summary in written:
            assert summary.status is SummaryStatus.FAILED
            assert summary.call_1 is not None, "the label call ran and the ledger has to say so"
            assert summary.call_1.kind is CallKind.LABEL
            assert summary.call_1.input_tokens == spent["prompt_tokens"]
            assert summary.call_1.output_tokens == spent["completion_tokens"]
            assert summary.call_1.prefill_ms == 217_580
            assert summary.call_1.decode_ms == 659_020
            assert summary.call_2 is None, "the summarize-and-plan call was never sent"
            assert summary.input_tokens == spent["prompt_tokens"]
            assert summary.output_tokens == spent["completion_tokens"]


class TestAReplyTheBudgetCutKeepsItsSummary:
    """Row #9. The recovery had no production caller, so every cut item died whole.

    On run `34852763827` three items decoded exactly the summarize-and-plan
    budget, hit the cap, and lost their summaries - the half a reader came for -
    while `calls.recovered_completion` sat beside them tested and uncalled.

    Both cases run the real work stage over a captured page and a recorded reply
    played back by a loopback server, so what is asserted is what a shard writes
    to disk (Guardrail #7).
    """

    def test_a_cut_in_the_plan_publishes_the_summary_and_records_the_missing_picture(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Field order is decode order, and this is that guarantee spent.

        `summary` is declared before `visual`, so a reply the budget cuts is cut
        in the plan and the summary behind it is closed, balanced and readable.
        The item publishes; what it does not carry is a picture, and the decision
        says which of the two walls stopped the decode.
        """
        run_plan, items, served = worked(
            tmp_path,
            monkeypatch,
            replies=(LABEL_REPLY.read_bytes(), CUT_IN_THE_PLAN_REPLY.read_bytes()),
        )

        assert served == 2 * len(run_plan.items), "the cut is in the second call's reply"
        written = [
            Summary.from_json(read_text(items / f"{item.item_id}.summary.json"))
            for item in run_plan.items
        ]
        assert written, "the stage summarized nothing, so this asserts nothing"
        for summary in written:
            assert summary.status is SummaryStatus.OK
            assert summary.summary and "34 percent" in summary.summary
            assert summary.key_points
        for item in run_plan.items:
            decision = VisualDecision.from_json(read_text(items / f"{item.item_id}{PAYLOAD_SUFFIX}"))
            assert decision.kind is VisualKind.NONE
            assert decision.visual_state is VisualState.ABSENT
            assert decision.none_reason is NoneReason.OUTPUT_BUDGET_CUT
            assert decision.rationale and "output budget" in decision.rationale

    def test_a_cut_inside_the_summary_still_loses_the_item(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The conservative half. Half a sentence published is worse than no item.

        The same recorded reply, stopped before the summary object closes. There
        is nothing balanced to lift out, so the recovery hands back nothing and
        the item fails exactly as it did before the caller existed - typed, and
        with no partial words on the page.
        """
        body = json.loads(read_text(CUT_IN_THE_PLAN_REPLY))
        content = body["choices"][0]["message"]["content"]
        body["choices"][0]["message"]["content"] = content[: content.index('"key_points"')]

        run_plan, items, _served = worked(
            tmp_path,
            monkeypatch,
            replies=(LABEL_REPLY.read_bytes(), json.dumps(body).encode("utf-8")),
        )

        written = [
            Summary.from_json(read_text(items / f"{item.item_id}.summary.json"))
            for item in run_plan.items
        ]
        assert written, "the stage summarized nothing, so this asserts nothing"
        for summary in written:
            assert summary.status is SummaryStatus.FAILED
            assert summary.failure_code is FailureCode.OUTPUT_TRUNCATED
            assert not summary.summary, "a cut summary is never published in part"
        assert not list(items.glob(f"*{PAYLOAD_SUFFIX}")), "a lost item gets no decision"


def _both_replies() -> tuple[bytes, ...]:
    """One recorded pair, replayed in a cycle so every item gets both calls."""
    return (
        LABEL_REPLY.read_bytes(),
        SUMMARIZE_AND_PLAN_REPLY.read_bytes(),
    )


class TestTheSequenceIsWalkedItemMajor:
    """The order the calls go out in, asserted on the wire rather than read in the code.

    `classify.dag.NODES` declares the sequence and `dag.walk` runs it, but a
    declaration proves nothing about what a stage actually sent. These tests
    read the request bodies a real loopback server received, which is the only
    place the answer is not a restatement of the code under test.
    """

    def test_every_node_of_one_item_runs_before_the_next_items_first_node(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The whole prefix cache rests on this, and nothing else would catch it.

        the summarize entry pins `n_parallel` to 1, so the server holds
        one cache slot. Every label call first and every summarize-and-plan call afterwards would
        evict the prefix before it was reused - on every item, on an ordinary
        HTTP 200, with nothing in any log to say so. The run would get slower and
        stay correct, which is the failure nobody notices.

        The proof is adjacency rather than pairing: the summarize-and-plan call's prompt opens with
        the label call's prompt for the SAME article, so a request whose prompt does not
        extend the request before it is a request that was sent out of turn. A
        call-major run pairs up perfectly by index and fails here on the first
        two requests.
        """
        sent = worked_requests(tmp_path, monkeypatch, replies=_both_replies())

        assert sent, "the stage sent nothing, so this asserts nothing"
        assert len(sent) % len(dag.NODES) == 0, (
            f"{len(sent)} requests is not a whole number of {len(dag.NODES)}-call items"
        )
        for opened in range(0, len(sent), len(dag.NODES)):
            first, second = sent[opened], sent[opened + 1]
            assert first["n_predict"] == calls.LABEL_BUDGET_TOKENS, (
                f"request {opened} is not a labelling call, so the sequence went "
                "call-major and every prefix was evicted before it was reused"
            )
            assert str(second["prompt"]).startswith(str(first["prompt"])), (
                f"request {opened + 1} does not extend request {opened}, so the two "
                "calls of one item were not adjacent"
            )

    def test_both_calls_ask_the_server_to_hold_the_prefix(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Adjacency buys nothing if the request does not ask for the slot.

        Sending the calls in the right order and not asking to cache is the same
        run at the same cost, and it looks identical from the outside. This is
        the other half of the same property and it is one key.
        """
        sent = worked_requests(tmp_path, monkeypatch, replies=_both_replies())

        assert sent
        assert all(body.get("cache_prompt") is True for body in sent), (
            "a request went out without cache_prompt, so its prefill was paid again"
        )

    def test_the_shared_opening_is_the_same_bytes_at_the_same_offset_every_time(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Nothing that varies per item may sit in front of the shared turn.

        A prefix cache reuses the longest common prefix of the tokenised prompt,
        so one item-specific byte in front of the system turn ends the common
        prefix at byte zero and the whole turn prefills again on every item. The
        offset is asserted as well as the bytes because equal content at a moved
        position is exactly the failure: a title line or a date stamp inserted
        above the turn leaves every character of it intact and saves nothing.

        This is what the definition sentences inherit. When they move into
        this turn they are cached for the whole run on the strength of this
        property, and they cost one prefill each if it stops holding.
        """
        sent = worked_requests(tmp_path, monkeypatch, replies=_both_replies())

        assert sent
        opening = str(sent[0]["prompt"])[: len(calls.label_system_prompt())]
        assert opening.strip(), "the shared opening is empty, so this asserts nothing"
        for index, body in enumerate(sent):
            prompt = str(body["prompt"])
            assert prompt.startswith(opening), (
                f"request {index} does not open with the shared turn, so its prefix "
                "cache starts at byte zero"
            )
            assert prompt.index(opening) == 0, f"request {index} moved the shared turn"
