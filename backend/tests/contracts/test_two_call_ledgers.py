"""Can one item's two model calls be told apart in every ledger that records them?"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh import ledger
from idhazh.contracts.call_cost import CallCost, CallKind
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.item_health import CALL_SLOTS, RETIRED_CELLS, ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.summary import Summary
from utilities import build_canary_day

pytestmark = pytest.mark.contract


#
# The five cost numbers are per request. Folded into one set they stop being
# readable, and `cached_tokens` is where that shows first: a call that reads its
# prompt cold and a call that is answered from the cache add to a figure that is
# neither of them.


def _two_calls() -> tuple[CallCost, CallCost]:
    """One item's two calls, at the shape the one measured two-call run had.

    Built rather than read off a published day. No run has dispatched both calls
    yet, so the state this contract exists for - a cold first slot - is not in
    the archive and could not be (`CLAUDE.md` Guardrail #12). The numbers are the
    2026-09-12 reading in `docs/architecture/summarize/throughput.md`.
    """
    return (
        CallCost(
            kind=CallKind.LABEL,
            prefill_ms=214122,
            decode_ms=88795,
            input_tokens=1497,
            output_tokens=205,
            cached_tokens=0,
        ),
        CallCost(
            kind=CallKind.SUMMARIZE_AND_PLAN,
            prefill_ms=186750,
            decode_ms=292626,
            input_tokens=2389,
            output_tokens=567,
            cached_tokens=1493,
        ),
    )


def _summary_of_two_calls() -> Summary:
    first, second = _two_calls()
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    payload["call_1"] = first.model_dump(mode="json")
    payload["call_2"] = second.model_dump(mode="json")
    for field in ("prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens"):
        payload[field] = getattr(first, field) + getattr(second, field)
    return Summary.model_validate(payload)


def test_one_item_carries_two_cache_figures_and_they_disagree() -> None:
    """The Oracle. One folded cell cannot say what two calls did.

    The first call reads the article on a cold slot and reuses nothing. The
    second replays it and is answered for almost all of it. Added together they
    make 1,493 reused of 3,886 asked for - 38 percent, which is neither call's
    0 percent nor its 62, and is the number the console printed as the item's.
    """
    summary = _summary_of_two_calls()
    assert summary.call_1 is not None and summary.call_2 is not None

    assert summary.call_1.cached_tokens == 0, "a cold slot reuses nothing"
    assert summary.call_2.cached_tokens == 1493
    assert summary.call_1.cached_tokens != summary.call_2.cached_tokens

    assert summary.cached_tokens == 1493, "the flat cell is their sum"
    folded = round(100 * summary.cached_tokens / summary.input_tokens)
    per_call = [
        round(100 * call.cached_tokens / call.input_tokens)
        for call in (summary.call_1, summary.call_2)
    ]
    assert folded == 38
    assert per_call == [0, 62]
    assert folded not in per_call, "the folded share is not either call's answer"


def test_a_payload_written_before_the_split_still_validates() -> None:
    """The read-side proof, taken by removing the keys rather than by waiting.

    A test that counted payloads still lacking the new keys would go red on the
    day the last one aged out, which is a date on the calendar rather than a
    change anybody made (`docs/reference/agent-notes.md`).
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    for key in ("call_1", "call_2"):
        payload.pop(key, None)
    older = Summary.model_validate(payload)
    assert older.call_1 is None and older.call_2 is None
    assert older.cached_tokens == payload["cached_tokens"], "the total still reads as it was written"

    row = json.loads(read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json"))
    cells = ItemHealthRow.model_validate(row).csv_row()
    for name in (*RETIRED_CELLS.values(), "model_calls"):
        cells.pop(name)
    narrower = ItemHealthRow.from_csv_row(cells)
    assert narrower.model_calls is None and narrower.label_kind is None
    assert narrower.cached_tokens == ItemHealthRow.model_validate(row).cached_tokens


def test_a_row_that_records_one_call_may_not_keep_the_other_call_s_total() -> None:
    """The rule that lets every pooled reader stay folded and stay correct.

    `reconcile_prefill` compares this ledger's summed tokens against the model
    server's own job totals inside 5 percent, and the server counts every call
    it answered. A row recording one call and leaving the total at that call's
    numbers would put it permanently red with nothing wrong.
    """
    first, second = _two_calls()
    row = ItemHealthRow.model_validate(
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json"))
    )
    whole: dict[str, object] = {"model_calls": 2}
    for slot, call in zip(CALL_SLOTS, (first, second), strict=True):
        whole[f"{slot}_kind"] = call.kind
        for field in ("prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens"):
            whole[f"{slot}_{field}"] = getattr(call, field)
    totals = {
        field: getattr(first, field) + getattr(second, field)
        for field in ("prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens")
    }
    assert row.model_copy(update={**whole, **totals}).model_calls == 2

    with pytest.raises(ValidationError, match="sum over the recorded calls"):
        ItemHealthRow.model_validate({**row.model_dump(), **whole, **totals, "cached_tokens": 0})
    with pytest.raises(ValidationError, match="recorded whole or not at all"):
        ItemHealthRow.model_validate(
            {**row.model_dump(), **whole, **totals, "summary_cached_tokens": None}
        )
    with pytest.raises(ValidationError, match="must equal the number of recorded calls"):
        ItemHealthRow.model_validate({**row.model_dump(), **whole, **totals, "model_calls": 1})


def test_a_shard_written_under_the_retired_headings_still_reads() -> None:
    """The read-side proof for the rename, taken by removing the new keys.

    Every day file and every month shard an earlier run wrote heads its per-call
    cells `call_1_*` and `call_2_*`. Those files are the archive, so a build that
    cannot open them has not migrated the ledger - it has abandoned it.

    The old spelling is put back on a built row rather than counted in the
    committed tree, because a test that counted rows still carrying it would go
    red on the day the last one aged out (`CLAUDE.md` section 13).
    """
    first, second = _two_calls()
    fields = ("prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens")
    split: dict[str, object] = {
        "model_calls": 2,
        **{name: getattr(first, name) + getattr(second, name) for name in fields},
    }
    for slot, call in zip(CALL_SLOTS, (first, second), strict=True):
        split[f"{slot}_kind"] = call.kind
        split |= {f"{slot}_{name}": getattr(call, name) for name in fields}
    row = ItemHealthRow.model_validate(
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json"))
    ).model_copy(update=split)
    assert row.label_kind is not None and row.summary_kind is not None

    retired = row.csv_row()
    historical_headings = {
        "call_1_kind": "label_kind",
        "call_1_prefill_ms": "label_prefill_ms",
        "call_1_decode_ms": "label_decode_ms",
        "call_1_input_tokens": "label_input_tokens",
        "call_1_output_tokens": "label_output_tokens",
        "call_1_cached_tokens": "label_cached_tokens",
        "call_2_kind": "summary_kind",
        "call_2_prefill_ms": "summary_prefill_ms",
        "call_2_decode_ms": "summary_decode_ms",
        "call_2_input_tokens": "summary_input_tokens",
        "call_2_output_tokens": "summary_output_tokens",
        "call_2_cached_tokens": "summary_cached_tokens",
        "job": "machine_job",
        "shard": "machine_shard",
    }
    for old, new in historical_headings.items():
        retired[old] = retired.pop(new)
    assert not set(retired) & {
        "label_kind",
        "label_prefill_ms",
        "label_decode_ms",
        "label_input_tokens",
        "label_output_tokens",
        "label_cached_tokens",
        "summary_kind",
        "summary_prefill_ms",
        "summary_decode_ms",
        "summary_input_tokens",
        "summary_output_tokens",
        "summary_cached_tokens",
        "machine_job",
        "machine_shard",
    }

    assert ItemHealthRow.from_csv_row(retired) == row

def test_the_canary_writes_every_column_the_feed_health_ledger_defines(tmp_path: Path) -> None:
    """Every health column is exercised, except an identity with no curated mapping.

    The browser suite runs against this ledger, so every health column needs an
    exercised state. Publisher identity may remain empty where the catalog has
    no reviewed mapping; this canary does not invent one.

    The read is over the raw files this call just filed - two days - rather
    than over anything a run appends to (`CLAUDE.md` section 13).
    """
    build_canary_day.health(tmp_path)
    days = ledger.held_days(tmp_path, LedgerName.FEED_HEALTH)
    assert days, "the canary filed no feed-health day"
    cells = [
        row.csv_row()
        for row in ledger.load_days(tmp_path, LedgerName.FEED_HEALTH, days, model=FeedHealthRow)
    ]

    unfilled = [name for name in FeedHealthRow.csv_columns() if not any(c[name] for c in cells)]
    assert unfilled in ([], ["publisher_id"]), "only an unknown publisher identity may stay empty"
    assert {c["robots_outcome"] for c in cells} == {"allowed", "denied", "unreachable", ""}
