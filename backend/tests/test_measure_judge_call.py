"""What does the judge-call bench report, and what does it refuse to report?

The statistics and the parsing are pure, so they are driven from built readings
and from one recorded llama-server envelope under `tests/fixtures/`. No mock, no
network, and no live server (Guardrail #7).

**Nothing here walks committed pipeline data.** The pairs come from the
committed digest-day contract fixture, which is fixed in size, and every fixture
is opened inside the test that owns it rather than at module scope.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from conftest import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.knobs.placement import SECONDS_A_CALL
from idhazh.llm.server import parse_completion
from utilities import measure_judge_call as bench

JUDGE_REPLIES: Final = FIXTURES_DIR / "completions" / "judge"


def a_reading(
    index: int,
    *,
    wall_ms: float,
    prefill_ms: float | None = 1_000.0,
    decode_ms: float | None = 100.0,
    prompt_tokens: int = 764,
    cached_tokens: int | None = 0,
    block: str = bench.BLOCK_DIFFERENT_PAIRS,
    order: str = bench.ORDER_FILE,
    margin: float | None = 0.8,
) -> bench.CallReading:
    """One reading, built rather than recorded, for the arithmetic to chew on."""
    return bench.CallReading(
        index=index,
        block=block,
        pair_key=f"{index:064x}",
        order=order,
        prompt_tokens=prompt_tokens,
        cached_tokens=cached_tokens,
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
        wall_ms=wall_ms,
        completion_tokens=1,
        verdict="NO",
        first_token_margin=margin,
    )


def test_the_cold_call_is_reported_rather_than_dropped() -> None:
    """Call 1 is named on the summary and is in none of the figures.

    It is the only call that faults the weights in off disk, and a shard pays it
    once against ninety-nine warm calls. Dropped, it becomes invisible; averaged
    in, it moves the number a bound is sized off.
    """
    readings = [a_reading(0, wall_ms=90_000.0)] + [
        a_reading(index, wall_ms=1_000.0) for index in range(1, 10)
    ]

    summary = bench.summarise(readings)

    assert summary.cold is not None
    assert summary.cold.index == 0
    assert summary.cold.wall_ms == 90_000.0
    assert summary.wall.count == 9, "the cold call is held out of every figure"
    assert summary.wall.median == 1_000.0
    assert summary.wall.highest == 1_000.0, "nothing carries the cold call's 90 s"


def test_a_run_stopped_on_the_clock_reports_what_it_got() -> None:
    """A partial run says so, and still reports the calls it did take.

    The failure this refuses is a measurement job that quietly returns less than
    it promised: 37 calls read exactly like 100 unless the run says which number
    ended it.
    """
    readings = [a_reading(index, wall_ms=float(index + 1)) for index in range(37)]

    summary = bench.summarise(readings, stopped_by=bench.StopReason.CLOCK)

    assert summary.partial
    assert summary.calls == 37
    assert summary.wall.count == 36
    assert "the clock" in bench.render(summary, conditions={})
    assert "partial" in bench.render(summary, conditions={})


def test_a_call_the_server_did_not_time_is_absent_rather_than_zero() -> None:
    """A reply with no `timings` block carries no duration, not a duration of 0.

    `parse_completion` rounds an absent block to 0 on both figures, so without
    this the untimed call joins the median as a call that cost nothing - and a
    median pulled towards zero is the one wrong answer that looks like good news.
    """
    reply = parse_completion(read_text(JUDGE_REPLIES / "the-server-timed-nothing.json"))

    reading = bench.reading_of(
        reply,
        index=4,
        block=bench.BLOCK_DIFFERENT_PAIRS,
        pair_key="a" * 64,
        order=bench.ORDER_FILE,
        wall_ms=81_000.0,
        verdict="NO",
        first_token_margin=None,
    )

    assert not bench.the_reply_was_timed(reply)
    assert reading.prefill_ms is None
    assert reading.decode_ms is None
    assert reading.cached_tokens is None, "no cache_n means the server did not say"
    assert reading.prompt_tokens == 764
    assert reading.wall_ms == 81_000.0, "the stopwatch still answers when the server does not"

    summary = bench.summarise([a_reading(0, wall_ms=90_000.0), reading])
    assert summary.prefill.count == 0
    assert summary.prefill.median is None
    assert summary.wall.count == 1, "the clock is the series that survives an untimed reply"


def test_a_timed_reply_keeps_both_of_the_servers_own_figures() -> None:
    """The recorded warm reply is read as a timing, so the check above is not vacuous."""
    reply = parse_completion(read_text(JUDGE_REPLIES / "one-event.json"))

    reading = bench.reading_of(
        reply,
        index=1,
        block=bench.BLOCK_DIFFERENT_PAIRS,
        pair_key="b" * 64,
        order=bench.ORDER_FILE,
        wall_ms=4_300.0,
        verdict="YES",
        first_token_margin=0.9,
    )

    assert bench.the_reply_was_timed(reply)
    assert reading.prefill_ms == 4_121.0
    assert reading.decode_ms == 101.0
    assert reading.cached_tokens == 402
    assert reading.tokens_read == 362, "764 read minus the 402 the slot handed back"


def test_the_prefill_rate_is_taken_over_the_tokens_actually_read() -> None:
    """The denominator is the prompt minus what the slot handed back.

    Dividing by the whole prompt would credit the run with reading tokens it was
    given for free, and would report a cache that is working as a machine that
    is fast.
    """
    reading = a_reading(1, wall_ms=800.0, prefill_ms=724.0, prompt_tokens=764, cached_tokens=400)

    assert reading.tokens_read == 364
    assert reading.prefill_ms_a_token is not None
    assert round(reading.prefill_ms_a_token, 6) == round(724.0 / 364, 6)

    whole_prompt_cached = a_reading(2, wall_ms=50.0, prefill_ms=10.0, cached_tokens=764)
    assert whole_prompt_cached.tokens_read == 0
    assert whole_prompt_cached.prefill_ms_a_token is None, "no division by a read of nothing"

    server_said_nothing = a_reading(3, wall_ms=800.0, cached_tokens=None)
    assert server_said_nothing.tokens_read is None
    assert server_said_nothing.prefill_ms_a_token is None


def test_the_readings_round_trip_through_the_line_file(tmp_path: Path) -> None:
    """One call, one line, and the same reading comes back.

    The line file is what a run killed on the job clock leaves behind, so every
    field a summary needs has to survive the trip.
    """
    written = a_reading(0, wall_ms=77_600.0, prefill_ms=76_900.0, cached_tokens=None, margin=None)
    path = tmp_path / "calls.jsonl"

    with path.open("w", encoding="utf-8") as handle:
        bench.write_reading(handle, written)

    assert json.loads(path.read_text(encoding="utf-8"))["wall_ms"] == 77_600.0
    assert bench.read_readings(path) == [written]


def test_the_summary_carries_a_spread_beside_every_figure() -> None:
    """Guardrail #10: a figure with no spread beside it is not a reading."""
    readings = [a_reading(index, wall_ms=float(1_000 + index * 10)) for index in range(20)]

    summary = bench.summarise(readings)

    for series in (summary.wall, summary.prefill, summary.decode):
        assert series.count == 19, series.name
        assert series.lowest is not None, series.name
        assert series.highest is not None, series.name
        assert series.median is not None, series.name
        assert series.p90 is not None, series.name

    body = bench.render(summary, conditions={"Processor": "AMD EPYC 7763 64-Core"})
    assert "| Lowest | Highest |" in body
    assert "AMD EPYC 7763 64-Core" in body


def test_the_percentile_names_a_reading_that_was_taken() -> None:
    """Nearest rank, never an interpolation between two readings.

    Over the ten readings the top decile of a hundred calls affords, an
    interpolated value is mostly invention printed in the shape of a
    measurement.
    """
    taken = [float(value) for value in range(1, 11)]

    assert bench.percentile(taken, bench.P90) == 9.0
    assert bench.percentile(taken, bench.P90) in taken
    assert bench.percentile([], bench.P90) is None


def test_the_stopwatch_overrules_the_servers_cache_claim() -> None:
    """A reported cache that buys no time is a claim, and the clock is the measurement.

    This is the case the whole two-block shape exists to catch: every field the
    server reports looks healthy, and the prefill never moves.
    """
    readings = [
        a_reading(0, wall_ms=80_000.0, prefill_ms=79_000.0, block=bench.BLOCK_SAME_PROMPT),
        a_reading(1, wall_ms=80_000.0, prefill_ms=78_800.0, block=bench.BLOCK_SAME_PROMPT),
    ] + [a_reading(index, wall_ms=79_000.0, prefill_ms=78_000.0, cached_tokens=100) for index in range(2, 12)]

    prefix = bench.summarise(readings).warm_prefix

    assert prefix.clock_says_reused is False, "the repeat saved under half the prefill"
    assert prefix.server_says_reused is True, "a median 100 tokens reported reused"
    assert prefix.agreed is False
    assert "clock wins" in bench.render(bench.summarise(readings), conditions={})


def test_a_repeat_that_really_is_free_reads_as_agreement() -> None:
    """The other side of the same question, so the check above is not one-sided."""
    readings = [
        a_reading(0, wall_ms=80_000.0, prefill_ms=79_000.0, block=bench.BLOCK_SAME_PROMPT),
        a_reading(1, wall_ms=1_200.0, prefill_ms=300.0, block=bench.BLOCK_SAME_PROMPT),
    ] + [a_reading(index, wall_ms=70_000.0, prefill_ms=69_000.0, cached_tokens=100) for index in range(2, 12)]

    prefix = bench.summarise(readings).warm_prefix

    assert prefix.clock_says_reused is True
    assert prefix.server_says_reused is True
    assert prefix.agreed is True
    assert prefix.repeat_saving is not None and prefix.repeat_saving > 0.99


def test_the_pairs_are_cross_source_and_ordered_by_their_own_contents() -> None:
    """One named day in, a bounded list of real pairs out (Guardrail #12).

    Cross-source only, because two items from one masthead are the case the
    same-story pass never asks about. Ordered by the pair's own sha256, so a
    re-run reads the same pairs in the same order and nothing carries a seed.
    """
    path = next((CONTRACT_FIXTURES_DIR / "digest-day").glob("*.json"))
    day = DigestDay.from_json(read_text(path))

    pairs = bench.pairs_from_day(day, limit=50)

    assert len(pairs) == 3, "three items from three mastheads make three cross-source pairs"
    assert [pair.pair_key for pair in pairs] == sorted(pair.pair_key for pair in pairs)
    assert all(pair.left.source_id != pair.right.source_id for pair in pairs)
    assert bench.pairs_from_day(day, limit=2) == pairs[:2], "the cap takes a prefix of the order"


def test_the_clock_is_sized_so_the_call_count_can_be_reached() -> None:
    """The default bound has to admit the sample the run promises.

    A clock the count cannot reach turns a hundred-call run into a sixty-call
    one and reports a top decile of six readings while promising ten. The
    arithmetic: the slowest read rate this project has recorded is 19 percent
    below the median the derived seconds-a-call was taken at, so the worst run
    of a hundred calls is `SECONDS_A_CALL * 9.85 / 8.25 * 100`.
    """
    worst_case_seconds = SECONDS_A_CALL * (9.85 / 8.25) * bench.DEFAULT_CALLS

    assert bench.DEFAULT_BUDGET_MINUTES * 60.0 > worst_case_seconds
    assert round(worst_case_seconds / 60.0) == 154, "2 h 34 m for a hundred calls at the worst rate"
