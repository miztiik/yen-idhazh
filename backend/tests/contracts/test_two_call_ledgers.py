"""Can one item's two model calls be told apart in every ledger that records them?"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import day_partition, ledger
from idhazh.contracts.call_cost import CallCost, CallKind
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.public_telemetry import PublicTelemetryRow
from idhazh.contracts.runtime_counters import RuntimeCountersRow
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
    for name in ItemHealthRow.csv_columns():
        if name.startswith("call_") or name == "model_calls":
            cells.pop(name)
    narrower = ItemHealthRow.from_csv_row(cells)
    assert narrower.model_calls is None and narrower.call_1_kind is None
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
    for slot, call in ((1, first), (2, second)):
        whole[f"call_{slot}_kind"] = call.kind
        for field in ("prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens"):
            whole[f"call_{slot}_{field}"] = getattr(call, field)
    totals = {
        field: getattr(first, field) + getattr(second, field)
        for field in ("prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens")
    }
    assert row.model_copy(update={**whole, **totals}).model_calls == 2

    with pytest.raises(ValidationError, match="sum over the recorded calls"):
        ItemHealthRow.model_validate({**row.model_dump(), **whole, **totals, "cached_tokens": 0})
    with pytest.raises(ValidationError, match="recorded whole or not at all"):
        ItemHealthRow.model_validate(
            {**row.model_dump(), **whole, **totals, "call_2_cached_tokens": None}
        )
    with pytest.raises(ValidationError, match="must equal the number of recorded calls"):
        ItemHealthRow.model_validate({**row.model_dump(), **whole, **totals, "model_calls": 1})

def test_the_published_projection_leaves_a_second_call_that_can_be_subtracted() -> None:
    """The browser derives the second call, so the cells have to leave it derivable.

    Publishing both calls would have cost more than the split is worth to a
    runtime fetch: measured 2026-09-12 on the two committed shards with every
    timed row populated, twelve cells cost 72.9 and 80.1 percent more gzipped
    against 35.3 and 40.8 for these seven.
    """
    first, second = _two_calls()
    row = PublicTelemetryRow.model_validate(
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "public-telemetry" / "published.json"))
    )
    fields = ("prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens")
    published = {
        "model_calls": 2,
        "call_1_kind": first.kind,
        **{f"call_1_{name}": getattr(first, name) for name in fields},
        **{name: getattr(first, name) + getattr(second, name) for name in fields},
    }
    split = row.model_copy(update=published)
    derived = {
        name: (getattr(split, name) or 0) - (getattr(split, f"call_1_{name}") or 0)
        for name in fields
    }
    assert derived == {name: getattr(second, name) for name in fields}, (
        "the remainder is the second call, exactly"
    )

    with pytest.raises(ValidationError, match="must leave a remainder inside"):
        PublicTelemetryRow.model_validate(
            {**row.model_dump(), **published, "prefill_ms": first.prefill_ms - 1}
        )
    with pytest.raises(ValidationError, match="whole or not at all"):
        PublicTelemetryRow.model_validate({**row.model_dump(), **published, "call_1_kind": None})

def test_the_canary_writes_every_column_the_counters_ledger_defines() -> None:
    """The same guard, over the second header the canary restates.

    The canary gained a `state/runtime-counters.csv` on 2026-08-31, because
    without one the Machine route draws every panel in its empty state and the
    browser suite can assert nothing else. That file is written by hand in
    JavaScript for the same reason the item-health one is, so it needs the same
    guard: a column added to `RuntimeCountersRow` and not to that array writes a
    canary whose cells sit one place to the left, and every backend gate stays
    green while the console reads the wrong number.
    """
    source = read_text(REPO_ROOT / "frontend" / "scripts" / "build-canary.mjs")
    declared = re.search(r"const COUNTER_COLUMNS = \[(.*?)\];", source, re.DOTALL)
    assert declared is not None, "build-canary.mjs no longer declares a COUNTER_COLUMNS array"
    assert tuple(re.findall(r"'([^']+)'", declared.group(1))) == RuntimeCountersRow.csv_columns()

def test_the_canary_writes_every_column_the_feed_health_ledger_defines(tmp_path: Path) -> None:
    """Every column filled by at least one canary feed, not merely present in the header.

    The browser suite runs against this ledger, so a column no canary row fills
    is a console state that suite cannot reach - which is how the five columns
    added on 2026-09-02 would ship drawn only in their empty state.

    The walk is over a tree this call just built - two day files - rather than
    over anything a run appends to (`CLAUDE.md` section 13).
    """
    build_canary_day.health(tmp_path)
    days = list(day_partition.day_files(tmp_path / ledger.HEALTH_DIRNAME))
    assert days, "the canary wrote no feed-health day file"
    rows: list[dict[str, str]] = []
    for path in days:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            assert tuple(reader.fieldnames or ()) == FeedHealthRow.csv_columns(), path.name
            rows.extend(reader)

    unfilled = [name for name in FeedHealthRow.csv_columns() if not any(row[name] for row in rows)]
    assert unfilled == [], "a canary column nothing fills is a console state no test can reach"
    assert {row["robots_outcome"] for row in rows} == {"allowed", "denied", "unreachable", ""}
