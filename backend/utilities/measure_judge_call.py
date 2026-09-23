"""What does one judge call cost on the machine that will write the verdicts?

Every seconds figure the same-story judging rests on is derived rather than
measured. `SimilarityThresholdConfig.SECONDS_A_CALL` is 764 read tokens divided
by a read rate taken on the summarizer, on a different prompt at a different
length. Three load-bearing numbers sit on it: how many pairs a day may be
judged, how long a judging shard may run, and the ruling that the judging cannot
live inside the daily digest job. This is the run that replaces the derivation
with a reading.

**It times the warm path, not one call.** The first call faults the weights in
and opens a cold slot; a shard pays that once and pays the warm path ninety-nine
times. So call 1 is reported by name and held out of every statistic, and the
figure a bound is sized off is the median of what came after it.

**It reads three instruments and says when they disagree.** The server's own
`prompt_ms` and `predicted_ms`, the server's claim about how much of the prompt
it reused, and a stopwatch around the request. The stopwatch is what a shard's
budget is actually spent in, and it is the tiebreak: `cached_tokens` is a claim
and a clock is a measurement.

It is an operator tool and never a test. It needs a multi-gigabyte GGUF that
`backend/models/` does not commit, and it runs a real model for hours
(`CLAUDE.md` section 13). Nothing in CI calls it on a schedule. The arithmetic
it prints is tested from built readings and a recorded reply in
`backend/tests/test_measure_judge_call.py`.

    python backend/utilities/measure_judge_call.py \
        --day frontend/public/data/days/2026/09/14/digest.json \
        --readings backend/var/judge-bench/calls.jsonl \
        --page backend/var/judge-bench/what-a-judge-call-costs.md
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from functools import partial
from itertools import combinations
from pathlib import Path
from typing import Any, Final, TextIO

from idhazh import config
from idhazh.contracts.base import derive_text_digest, derive_url_key
from idhazh.contracts.digest_day import DigestDay, DigestItem
from idhazh.contracts.knobs.placement import SECONDS_A_CALL
from idhazh.llm.server import (
    Completion,
    TurnMarkers,
    completion_url,
    derive_turn_markers,
    post,
    request_timeout_seconds,
    resolve_endpoint,
    token_pieces,
)
from idhazh.similarity import judge, prompt
from idhazh.telemetry import silicon

#: How many calls one run takes: 50 pairs, each read twice. Twenty would give a
#: median and nothing about the tail, and a shard bound has to be sized off the
#: tail. A hundred puts ten readings in the top decile, which is thin and is a
#: reading rather than a guess.
DEFAULT_CALLS: Final = 100

#: What one run may spend before it stops, in minutes, whichever comes first
#: with the call count. 100 calls at the derived SECONDS_A_CALL is 2 h 09 m; at
#: the slowest read rate this project has recorded - 8.25 tokens a second
#: against the 9.85 median that derivation uses, which is 19 percent slower -
#: the same 100 calls are 2 h 34 m. This is that worst case plus a fifth.
#:
#: **A clock the count cannot reach is the failure, not the safeguard.** At 90
#: minutes the run would stop at about 58 calls every time and report a top
#: decile of 6 readings while promising 10, and nothing in its output would say
#: the promise had been quietly halved.
DEFAULT_BUDGET_MINUTES: Final = 185

#: Where the run writes, line by line as each call returns. Beside the judging
#: shard's own tree rather than inside it: a shard's draw and verdicts are pipeline
#: output and this is a measurement of the machine. Neither is committed.
BENCH_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "judge-bench"
CALLS_FILENAME: Final = "calls.jsonl"

#: The two ways one pair is read. They are positions rather than identities, the
#: same reason `prompt.FIRST_LABEL` gives.
ORDER_FILE: Final = "file"
ORDER_SWAPPED: Final = "swapped"

#: The two blocks of the run, and what each one asks.
#:
#: `same-prompt` is the stopwatch half of the prefix-cache question: one pair,
#: twice, back to back, nothing in between. If the second call's prefill is not
#: far below the first's then no prefix is being reused, whatever the server's
#: own `cached_tokens` says.
#:
#: `different-pairs` is the real workload: the same system turn in front of a
#: different user turn every time, which is the only prefix two judge calls in a
#: shard ever share.
BLOCK_SAME_PROMPT: Final = "same-prompt"
BLOCK_DIFFERENT_PAIRS: Final = "different-pairs"

#: What the p90 is taken at. Named rather than spelled inline: it appears in the
#: statistic and again in the sentence that says how many readings stood behind
#: it.
P90: Final = 0.9


class StopReason(StrEnum):
    """What ended the run. A run that stopped early has to read as partial.

    Three reasons rather than two, because a day that could not offer enough
    pairs is not a slow machine and must not be read as one.
    """

    COUNT = "count"
    CLOCK = "clock"
    PAIRS = "pairs"

    @property
    def sentence(self) -> str:
        """What the record page says ended the run."""
        return {
            StopReason.COUNT: "the call count",
            StopReason.CLOCK: "the clock",
            StopReason.PAIRS: "the day running out of pairs",
        }[self]


@dataclass(frozen=True, slots=True)
class PairToJudge:
    """Two published items and the key that names the pair they make."""

    pair_key: str
    left: DigestItem
    right: DigestItem


@dataclass(frozen=True, slots=True)
class CallReading:
    """One call, as the clock and the server each saw it.

    `prefill_ms`, `decode_ms` and `cached_tokens` are nullable because a server
    that reported no `timings` block reported nothing, and a zero there would
    enter a median as a call that cost nothing.
    """

    index: int
    block: str
    pair_key: str
    order: str
    prompt_tokens: int
    cached_tokens: int | None
    prefill_ms: float | None
    decode_ms: float | None
    wall_ms: float
    completion_tokens: int
    verdict: str
    first_token_margin: float | None

    @property
    def tokens_read(self) -> int | None:
        """How much of the prompt this call actually prefilled.

        `prompt_tokens` is the whole prompt and `cached_tokens` is the part the
        slot handed back, so their difference is the part that was read. It is
        legitimately zero on a repeat of the same prompt, which is why the
        prefill rate below refuses that case rather than dividing by it.
        """
        if self.cached_tokens is None:
            return None
        return max(self.prompt_tokens - self.cached_tokens, 0)

    @property
    def prefill_ms_a_token(self) -> float | None:
        """Milliseconds a token over the tokens actually read.

        This is the honest prefill rate. Dividing by `prompt_tokens` would
        credit the run with reading tokens the slot handed over for free, and
        would report a cache that is working as a machine that is fast.
        """
        read = self.tokens_read
        if self.prefill_ms is None or read is None or read <= 0:
            return None
        return self.prefill_ms / read


@dataclass(frozen=True, slots=True)
class Series:
    """One quantity over the warm calls: what it usually is, and what its tail is.

    No mean anywhere. One call on a descheduled runner moves a mean and does not
    move a median, and the whole point is to size a bound against the typical
    call and then read the tail separately.
    """

    name: str
    unit: str
    count: int
    median: float | None
    p90: float | None
    lowest: float | None
    highest: float | None


@dataclass(frozen=True, slots=True)
class WarmPrefix:
    """Is the shared system turn read once a shard, or once a call?

    Two instruments and a verdict. `repeat_saving` is the stopwatch: what share
    of the first call's prefill the immediate repeat did not pay. `cached_tokens`
    is the server's own claim over the different-pairs block. Where they
    disagree the clock wins, and `agreed` is what says a disagreement happened.
    """

    first_prefill_ms: float | None
    repeat_prefill_ms: float | None
    repeat_saving: float | None
    cached_tokens_median: float | None
    tokens_read_median: float | None
    clock_says_reused: bool | None
    server_says_reused: bool | None
    agreed: bool | None


@dataclass(frozen=True, slots=True)
class Summary:
    """Everything one run has to say, with the cold call held out by name."""

    calls: int
    pairs: int
    stopped_by: StopReason
    cold: CallReading | None
    prefill: Series
    decode: Series
    wall: Series
    prompt_tokens: Series
    cached_tokens: Series
    prefill_rate: Series
    margin: Series
    warm_prefix: WarmPrefix
    derived_seconds_a_call: float

    @property
    def partial(self) -> bool:
        """Did anything but the call count end this run?

        A run that returned less than it promised has to read that way. The
        failure being refused is a bench that quietly hands back 63 calls where
        the method says 100 and reports a top decile of six readings.
        """
        return self.stopped_by is not StopReason.COUNT


# --- Reading one call --------------------------------------------------------


def the_reply_was_timed(reply: Completion) -> bool:
    """Did this reply carry the server's own `timings` block at all?

    Read off the decode figure, which is the one that cannot legitimately be
    zero: every reply here writes at least one token and no vocabulary writes
    one in under half a millisecond. `parse_completion` rounds an absent block
    to 0 on both figures, so without this question an untimed reply enters a
    median as a call that cost nothing.
    """
    return reply.completion_tokens > 0 and reply.decode_ms > 0


def reading_of(
    reply: Completion,
    *,
    index: int,
    block: str,
    pair_key: str,
    order: str,
    wall_ms: float,
    verdict: str,
    first_token_margin: float | None,
) -> CallReading:
    """One envelope and one stopwatch, as a row of the line file.

    `cached_tokens` follows `prefix_reused`, which `parse_completion` sets to
    None exactly when the reply carried no `cache_n`. That keeps the count and
    the boolean from disagreeing about one reply, and it keeps a server that
    does not report reuse out of the cache arithmetic entirely.
    """
    timed = the_reply_was_timed(reply)
    return CallReading(
        index=index,
        block=block,
        pair_key=pair_key,
        order=order,
        prompt_tokens=reply.prompt_tokens,
        cached_tokens=reply.cached_tokens if reply.prefix_reused is not None else None,
        prefill_ms=float(reply.prefill_ms) if timed else None,
        decode_ms=float(reply.decode_ms) if timed else None,
        wall_ms=wall_ms,
        completion_tokens=reply.completion_tokens,
        verdict=verdict,
        first_token_margin=first_token_margin,
    )


class KeepsTheEnvelope:
    """Hands the judge its reply and keeps a copy of it.

    The judge returns a verdict and a margin. The numbers this run is about -
    prefill, decode, the token counts, what the slot held - are on the envelope
    it read them from. Wrapping the client is what lets the measurement drive
    the shipped call path rather than a second copy of it, which would measure a
    prompt no shard will ever send.
    """

    def __init__(self, inner: judge.Client) -> None:
        self._inner = inner
        self.last: Completion | None = None

    def __call__(self, payload: dict[str, Any]) -> Completion:
        self.last = self._inner(payload)
        return self.last


def judge_calls(
    pairs: Sequence[PairToJudge],
    *,
    settings: config.Settings,
    base_url: str | None = None,
    limit: int = DEFAULT_CALLS,
    budget_seconds: float = DEFAULT_BUDGET_MINUTES * 60.0,
) -> Iterator[CallReading]:
    """One reading a call, yielded as it is taken.

    Yielded rather than returned, so the caller can write each line as it
    arrives. A summary written only at the end puts the whole run behind its
    last call, and a run that stops on the clock would then have nothing to
    show for the two hours it did spend.

    The first pair is read twice in file order, back to back. Every pair after
    it is read once in each order, which is what a judging shard does.

    The vocabulary check runs once before any pair, exactly as the shard runs it.
    A verdict no returned token can be attributed to takes none of the window's
    mass, so `first_token_margin` reports a gap between the other two, and a
    measurement taken through a broken instrument is worse than none.
    """
    # Resolved here rather than deeper: the client below binds a derived route
    # inside a `partial`, so an unresolved address would raise there instead.
    base_url = base_url or resolve_endpoint(settings.app.model_server.base_url)
    entry = judge.entry_of(settings)
    timeout = request_timeout_seconds(entry.request)
    prompt.first_token_openings(partial(token_pieces, base_url, timeout=timeout))
    markers = derive_turn_markers(base_url, entry=entry, timeout=timeout)
    client = partial(post, endpoint=completion_url(base_url), timeout=timeout)

    started = time.monotonic()
    index = 0
    for position, pair in enumerate(pairs):
        block = BLOCK_SAME_PROMPT if position == 0 else BLOCK_DIFFERENT_PAIRS
        orders = (ORDER_FILE, ORDER_FILE) if position == 0 else (ORDER_FILE, ORDER_SWAPPED)
        for order in orders:
            if index >= limit or time.monotonic() - started >= budget_seconds:
                return
            yield one_call(
                pair,
                order=order,
                index=index,
                block=block,
                client=client,
                settings=settings,
                markers=markers,
            )
            index += 1


def one_call(
    pair: PairToJudge,
    *,
    order: str,
    index: int,
    block: str,
    client: judge.Client,
    settings: config.Settings,
    markers: TurnMarkers,
) -> CallReading:
    """The shipped judge call, with its envelope kept.

    The stopwatch is `judge.read_once`'s own, taken around the request and
    returned as `Reading.decode_seconds` - a name that belongs to the column it
    fills on a judged row, where it is the pair's whole wall clock. A second
    stopwatch here would be a second answer to what one call took.
    """
    left, right = (pair.left, pair.right) if order == ORDER_FILE else (pair.right, pair.left)
    kept = KeepsTheEnvelope(client)
    read = judge.read_once(left, right, client=kept, settings=settings, markers=markers)
    if kept.last is None:
        raise RuntimeError("the judge returned without a reply, so there is nothing to read")
    return reading_of(
        kept.last,
        index=index,
        block=block,
        pair_key=pair.pair_key,
        order=order,
        wall_ms=read.decode_seconds * 1000.0,
        # Empty where the grammar did not hold. `read_once` records that rather
        # than raising, so this instrument keeps the timings of a call it was
        # asked to measure instead of losing a whole block to one bad reply.
        verdict=read.verdict.value if read.verdict is not None else "",
        first_token_margin=read.first_token_margin,
    )


# --- The pairs ---------------------------------------------------------------


def pairs_from_day(day: DigestDay, *, limit: int) -> list[PairToJudge]:
    """Every cross-source pair one published day holds, in content-hash order.

    **One named day in, a bounded list out** (Guardrail #12). Cost goes as the
    square of that day's items and not at all with how many days the archive has
    accumulated, so the thousandth run costs what the third did.

    Content-hash order and no seed, which is the rule the judging draw follows:
    a seed is a knob somebody can turn until the answer looks nice.

    **Cross-source only**, because two items from one masthead are the case the
    same-story pass never asks about.

    What this cannot reproduce is the band filter - the draw keeps pairs scoring
    0.88 and above, and scoring them is the scoring stage's job. It changes
    WHICH summaries are read and not HOW LONG they are, and the length is what a
    call costs: the judge never sees the score. `prompt_tokens` is reported for
    exactly that reason, so a later run over a real draw can be set beside this
    one instead of guessed at.
    """
    items = {derive_url_key(item.source_url): item for item in day.items}
    built = [
        PairToJudge(
            pair_key=derive_text_digest(left + right),
            left=items[left],
            right=items[right],
        )
        for left, right in combinations(sorted(items), 2)
        if items[left].source_id != items[right].source_id
    ]
    built.sort(key=lambda pair: pair.pair_key)
    return built[:limit]


# --- The line file -----------------------------------------------------------


def write_reading(handle: TextIO, reading: CallReading) -> None:
    """One call, one line, flushed.

    Flushed rather than buffered: a run killed at the job timeout has to leave
    behind every call it did take, and a buffer is the one place those readings
    would be when the process dies.
    """
    handle.write(json.dumps(asdict(reading), sort_keys=True) + "\n")
    handle.flush()


def read_readings(path: Path) -> list[CallReading]:
    """The line file back as readings, for a re-render that calls no model."""
    with path.open("r", encoding="utf-8") as handle:
        return [CallReading(**json.loads(line)) for line in handle if line.strip()]


# --- The statistics ----------------------------------------------------------


def percentile(values: Sequence[float], share: float) -> float | None:
    """The nearest-rank percentile: a reading that was taken, never one between two.

    An interpolated percentile invents a value that sits between two readings
    and prints it in the same shape as a measurement. Over the ten readings the
    top decile of a hundred calls affords, that invention is most of the answer.
    """
    if not values:
        return None
    ranked = sorted(values)
    return ranked[math.ceil(share * len(ranked)) - 1]


def as_floats(values: Iterable[int | float | None]) -> list[float | None]:
    """Optional counts as optional floats, so one series builder answers for all of them.

    The None survives the conversion. A count the server never reported is not a
    count of zero, and this is the one place the two could be folded together.
    """
    return [None if value is None else float(value) for value in values]


def series_of(name: str, unit: str, values: Sequence[float | None]) -> Series:
    """One quantity, with its spread beside it, over the readings that carry it.

    A None is dropped rather than counted as zero, and `count` is what says how
    many readings the figures below it actually stood on.
    """
    present = [value for value in values if value is not None]
    return Series(
        name=name,
        unit=unit,
        count=len(present),
        median=statistics.median(present) if present else None,
        p90=percentile(present, P90),
        lowest=min(present) if present else None,
        highest=max(present) if present else None,
    )


def warm_prefix_of(readings: Sequence[CallReading]) -> WarmPrefix:
    """What the stopwatch and the server each said about prefix reuse.

    The stopwatch reads the first two calls, which are one prompt sent twice
    with nothing in between. The server's claim is read over the different-pairs
    block, where the longest prefix any two calls share is the system turn.

    `agreed` is the finding. A server reporting a cache it is not using looks
    exactly like a working one on every field it reports; the only thing that
    catches it is a clock that did not get faster.
    """
    first = readings[0] if readings else None
    repeat = readings[1] if len(readings) > 1 else None
    spread = [row for row in readings if row.block == BLOCK_DIFFERENT_PAIRS]

    saving: float | None = None
    clock_says: bool | None = None
    if first is not None and repeat is not None:
        if first.prefill_ms is not None and repeat.prefill_ms is not None and first.prefill_ms > 0:
            saving = (first.prefill_ms - repeat.prefill_ms) / first.prefill_ms
            # Half the prefill gone is a cache that is doing something; anything
            # smaller is inside the run-to-run spread of one machine and says
            # nothing. The repeat sends the identical prompt, so a live cache has
            # nothing left to read and the saving should be near the whole of it.
            clock_says = saving >= 0.5

    cached = series_of("cached tokens", "tokens", as_floats(row.cached_tokens for row in spread))
    read = series_of("tokens read", "tokens", as_floats(row.tokens_read for row in spread))
    server_says = None if cached.median is None else cached.median > 0
    agreed = None if clock_says is None or server_says is None else clock_says == server_says
    return WarmPrefix(
        first_prefill_ms=None if first is None else first.prefill_ms,
        repeat_prefill_ms=None if repeat is None else repeat.prefill_ms,
        repeat_saving=saving,
        cached_tokens_median=cached.median,
        tokens_read_median=read.median,
        clock_says_reused=clock_says,
        server_says_reused=server_says,
        agreed=agreed,
    )


def summarise(
    readings: Sequence[CallReading], *, stopped_by: StopReason = StopReason.COUNT
) -> Summary:
    """The statistics, with call 1 named and held out of every one of them.

    Call 1 is the cold path: an empty slot, a cold page cache, and the weights
    being faulted in off disk. A shard pays it once and pays the warm path
    ninety-nine times, so averaging it in would size a bound off a call that
    happens once.
    """
    warm = readings[1:]
    return Summary(
        calls=len(readings),
        pairs=len({row.pair_key for row in readings}),
        stopped_by=stopped_by,
        cold=readings[0] if readings else None,
        prefill=series_of("prefill", "ms", [row.prefill_ms for row in warm]),
        decode=series_of("decode", "ms", [row.decode_ms for row in warm]),
        wall=series_of("wall clock", "ms", [row.wall_ms for row in warm]),
        prompt_tokens=series_of(
            "prompt tokens", "tokens", as_floats(row.prompt_tokens for row in warm)
        ),
        cached_tokens=series_of(
            "cached tokens", "tokens", as_floats(row.cached_tokens for row in warm)
        ),
        prefill_rate=series_of(
            "prefill", "ms a token read", [row.prefill_ms_a_token for row in warm]
        ),
        margin=series_of(
            "first-token margin", "probability", [row.first_token_margin for row in warm]
        ),
        warm_prefix=warm_prefix_of(readings),
        derived_seconds_a_call=SECONDS_A_CALL,
    )


# --- The record page ---------------------------------------------------------


def number(value: float | None, *, places: int = 1) -> str:
    """One figure, or a dash where no reading carries it."""
    return "-" if value is None else f"{value:,.{places}f}"


def seconds_and_minutes(milliseconds: float | None) -> str:
    """A duration said twice, because neither spelling answers on its own.

    Seconds is what a call costs and minutes is what a shard costs, and the whole
    question here is the second one.
    """
    if milliseconds is None:
        return "-"
    seconds = milliseconds / 1000.0
    return f"{seconds:,.1f} s ({seconds / 60.0:,.1f} min)"


def render_series(series: Series) -> str:
    """One row of the figures table, spread included (Guardrail #10)."""
    return (
        f"| {series.name} | {series.unit} | {series.count} | {number(series.median)} "
        f"| {number(series.p90)} | {number(series.lowest)} | {number(series.highest)} |"
    )


def render(summary: Summary, *, conditions: Mapping[str, str]) -> str:
    """The record page body, with every figure already in place.

    Rendered rather than transcribed for the reason `measure_budgets.py` renders
    its own: a figure typed by hand into a doc is a figure that can differ from
    the run that produced it, and nothing afterwards can tell which one is
    right.
    """
    prefix = summary.warm_prefix
    saving = None if prefix.repeat_saving is None else prefix.repeat_saving * 100.0
    lines = ["## Conditions", "", "| | |", "| --- | --- |"]
    lines += [f"| {name} | {value} |" for name, value in conditions.items()]
    lines += [
        "",
        "**The processor is part of the reading.** Prefill varies up to 3.9 times across the",
        "machines GitHub hands this repository, on these exact weights",
        "([the-processor-lottery.md](the-processor-lottery.md)), so a bound sized off one",
        "draw is several times wrong on another. The row above names the draw this run got.",
        "",
        "## What the run did",
        "",
        f"- **{summary.calls} calls over {summary.pairs} pairs.** Stopped by "
        f"{summary.stopped_by.sentence}"
        f"{', so this reading is partial' if summary.partial else ''}.",
        "- **Call 1 is the cold call** and is reported below rather than averaged in.",
        f"- Every figure below stands on the {max(summary.calls - 1, 0)} warm calls after it.",
        "",
        "## The figures",
        "",
        "| Series | Unit | Readings | Median | p90 | Lowest | Highest |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        render_series(summary.wall),
        render_series(summary.prefill),
        render_series(summary.decode),
        render_series(summary.prompt_tokens),
        render_series(summary.cached_tokens),
        render_series(summary.prefill_rate),
        render_series(summary.margin),
        "",
        f"**A typical call costs {seconds_and_minutes(summary.wall.median)} of wall clock, and "
        f"the slowest tenth cost {seconds_and_minutes(summary.wall.p90)} or more.** The "
        f"derivation this replaces said {summary.derived_seconds_a_call} s a call.",
        "",
        f"**The cold call.** {_cold_call(summary.cold)}",
        "",
        "## Is the instruction block read once a shard or once a call?",
        "",
        f"- **The stopwatch.** The first call prefilled in "
        f"{number(prefix.first_prefill_ms)} ms and the immediate repeat of the same prompt "
        f"in {number(prefix.repeat_prefill_ms)} ms, a saving of {number(saving)} percent.",
        f"- **The server's own claim.** Over the different-pairs block it reported a median "
        f"{number(prefix.cached_tokens_median)} tokens reused and "
        f"{number(prefix.tokens_read_median)} tokens actually read.",
        f"- **Do they agree?** {_agreement(prefix)}",
        "",
    ]
    return "\n".join(lines) + "\n"


def _cold_call(cold: CallReading | None) -> str:
    """The one call that is named rather than counted."""
    if cold is None:
        return "No call was taken."
    return (
        f"Wall clock {seconds_and_minutes(cold.wall_ms)}, prefill "
        f"{number(cold.prefill_ms)} ms, decode {number(cold.decode_ms)} ms, over "
        f"{cold.prompt_tokens} prompt tokens."
    )


def _agreement(prefix: WarmPrefix) -> str:
    """One sentence, and it says which instrument to believe when they differ."""
    if prefix.agreed is None:
        return "One of the two said nothing, so this run settles it neither way."
    if prefix.agreed and prefix.clock_says_reused:
        return "Yes. Both say the prefix is reused, so the instruction block is read once a shard."
    if prefix.agreed:
        return "Yes. Both say nothing is reused, so every call pays the whole prompt."
    return (
        "**No.** The clock wins: `cached_tokens` is what the server claims and prefill is "
        "what it spent. Treat the reused tokens as not reused until a run shows the clock "
        "moving."
    )


# --- The command line --------------------------------------------------------


def conditions_of(
    args: argparse.Namespace, settings: config.Settings, *, pairs: int
) -> dict[str, str]:
    """What this reading is a reading OF, in the shape a record page carries.

    The processor first, because it is the covariate worth more than any
    difference between our candidate models. It reads None off a machine with no
    `/proc/cpuinfo`, and the page then says so rather than printing a blank.
    """
    entry = settings.models.summarize
    return {
        "Processor": silicon.host_cpu_model() or "not reported by this host",
        "Runner": args.runner,
        "Weights": f"`{entry.file}`, id `{entry.id}`",
        "Declared for": entry.declared_for or "unset",
        "Judge prompt": f"sha256 `{prompt.prompt_digest()[:16]}`",
        "Grammar": f"`{prompt.grammar()}`, sha256 `{prompt.grammar_digest()[:16]}`",
        "Day the pairs came from": f"`{args.day}`" if args.day else "re-rendered, not recorded",
        "Pairs available": str(pairs),
        "Calls asked for": str(args.calls),
        "Clock": f"{args.budget_minutes} minutes",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--day",
        type=Path,
        help="a published day's digest.json; the pairs come from it in content-hash order",
    )
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)
    parser.add_argument("--calls", type=int, default=DEFAULT_CALLS)
    parser.add_argument("--budget-minutes", type=float, default=DEFAULT_BUDGET_MINUTES)
    parser.add_argument("--readings", type=Path, default=BENCH_ROOT / CALLS_FILENAME)
    parser.add_argument("--page", type=Path, default=None, help="write the record body here")
    parser.add_argument("--runner", default="a developer machine", help="what took this reading")
    parser.add_argument(
        "--report",
        action="store_true",
        help="re-render from an existing readings file without calling the model",
    )
    return parser.parse_args(argv)


def take_the_readings(args: argparse.Namespace, settings: config.Settings) -> Summary:
    """Run the calls, writing each one as it returns, and say what stopped it.

    Three things can stop a run and each is named. A run that ran out of pairs
    is not a slow machine; a run that ran out of clock is not a small day; and
    only a run that reached its call count took the sample the method promises.
    """
    day = DigestDay.from_json(args.day.read_text(encoding="utf-8"))
    # One call reads one pair, and the first pair is read twice, so the pairs a
    # run needs are half its calls rounded up.
    wanted = math.ceil(args.calls / 2)
    available = pairs_from_day(day, limit=wanted)
    budget_seconds = args.budget_minutes * 60.0
    args.readings.parent.mkdir(parents=True, exist_ok=True)

    readings: list[CallReading] = []
    started = time.monotonic()
    with args.readings.open("w", encoding="utf-8", newline="\n") as handle:
        for reading in judge_calls(
            available,
            settings=settings,
            base_url=args.base,
            limit=args.calls,
            budget_seconds=budget_seconds,
        ):
            write_reading(handle, reading)
            readings.append(reading)
            print(
                f"call {reading.index + 1} {reading.block} {reading.order} "
                f"{reading.wall_ms / 1000.0:,.1f} s",
                flush=True,
            )

    if len(readings) >= args.calls:
        stopped_by = StopReason.COUNT
    elif time.monotonic() - started >= budget_seconds:
        stopped_by = StopReason.CLOCK
    else:
        stopped_by = StopReason.PAIRS
    return summarise(readings, stopped_by=stopped_by)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = config.load(args.config)

    if args.report:
        summary = summarise(read_readings(args.readings))
    elif args.day is None:
        print("--day names the published day the pairs come from", file=sys.stderr)
        return 2
    else:
        summary = take_the_readings(args, settings)

    body = render(summary, conditions=conditions_of(args, settings, pairs=summary.pairs))
    print(body)
    if args.page is not None:
        args.page.parent.mkdir(parents=True, exist_ok=True)
        args.page.write_text(body, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
