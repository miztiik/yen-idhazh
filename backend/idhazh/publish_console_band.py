"""Write the verdict band the console reads before anything else.

`frontend/public/console/band.json` answers three questions above every console
route - did it work, what is worst, how much room is left - plus the list of
months the console may ask for. It is derived once here, at publication, from
the ledgers and the payloads this run has already written.

**It is a move, not a second copy.** `frontend/src/lib/server/console-shell.ts`
derives the same band at build time and serialises it into three prerendered
documents; row 10 of the plan-doc deletes that derivation and the console
fetches this file instead. Until it does, the two exist side by side and the
sentences here are ported from there deliberately word for word - a band that
said something different after the cutover would look like a pipeline change
rather than a plumbing one.

**Where each fact comes from, and why.** A number is taken from the store that
owns it, never re-derived from a wider one:

- the runs, the site size and the day's article count come from the run-day
  shards this run just wrote, because re-reducing five months of day payloads is
  exactly the walk those shards exist to remove (Rule #12);
- the feed trouble comes from `state/feed-health/` through `discover.settled`,
  `discover.streak` and `discover.resting`, because those are the reducers the
  pipeline itself rested a feed by, and a page that ran its own would contradict
  the run that produced it;
- the model facts come from one day's item-health shard and that day's own
  day-metrics record, each keyed to the newest day the manifests hold;
- the machine facts come from `state/runtime-counters.csv`, whose growing read
  `publish_machine` declares.

Every read is covered by the widest span `console.window_presets` offers, which
is the furthest back any panel on any route can draw. The span comes from
config rather than a literal, so raising the widest preset widens the read with
it (Rule #6).
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import (
    discover,
    ledger,
    publish_console,
    publish_day_metrics,
    publish_feed_health,
    publish_machine,
    publish_run_days,
    publish_scores,
    publish_span_rollup,
    publish_telemetry,
)
from idhazh.contracts.app_config import (
    CollectConfig,
    ConsoleConfig,
    RunConfig,
    months_a_window_can_touch,
)
from idhazh.contracts.console_band import (
    BandRun,
    BandSize,
    BandVerdict,
    BandWorst,
    ConsoleBand,
    ConsoleRoute,
    Health,
    RouteId,
)
from idhazh.contracts.day_metrics import DayMetrics
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.public_run_day import PublicRunDay, PublicRunRecord
from idhazh.month_partition import month_files

#: The 1 GB Pages ceiling (`CLAUDE.md` Rule #2). A constant and not a knob, for
#: the reason `retention.py` gives for its own copy: it is a property of the
#: host, and a knob would invite raising it instead of shrinking the site.
PAGES_CAP_BYTES: Final = 1024 * 1024 * 1024

#: Squares the band draws before it starts counting instead. The schedule fires
#: five runs a day, so twelve covers every day on record with room to spare.
#: Past that a row of squares stops being a row and becomes a chart, and the
#: band is not where a chart goes.
BAND_RUN_SQUARES: Final = 12

#: How loud a route's worst state is. Ranked rather than coloured - the strip
#: never takes the health ramp, because a route is a noun.
BROKEN: Final = 3
WORTH_A_LOOK: Final = 2
WORTH_KNOWING: Final = 1
CLEAR: Final = 0

#: The same three words the run strip 800 px below prints.
VERDICT_WORD: Final[dict[Health, str]] = {
    Health.GREEN: "ran clean",
    Health.AMBER: "is worth a look",
    Health.RED: "failed",
}

#: The strip's word for each route, its address, and the line under it. The
#: labels are the owner's own, taken verbatim on 2026-08-30 and 2026-08-31; the
#: ids and the addresses did not move with them.
ROUTES: Final[tuple[tuple[RouteId, str, str, str], ...]] = (
    (
        RouteId.PIPELINES,
        "Pipelines",
        "/console/",
        "Did the runs work, which feeds broke, and what each stage cost.",
    ),
    (
        RouteId.MODEL,
        "Summaries",
        "/console/model/",
        "What the model wrote, how long it took, and what it got wrong.",
    ),
    (
        RouteId.MACHINE,
        "Hardware",
        "/console/machine/",
        "The hardware the model ran on, and how much it varied between runs.",
    ),
)

__all__ = [
    "BAND_RELPATH",
    "BAND_RUN_SQUARES",
    "PAGES_CAP_BYTES",
    "band_path",
    "build",
    "publish",
    "read_band",
]

BAND_RELPATH: Final = publish_console.relpath(
    publish_console.CONSOLE_DIRNAME, publish_console.BAND_FILENAME
)


def band_path(digest_root: Path) -> Path:
    """`frontend/public/console/band.json`, derived from the digest root."""
    return (
        publish_console.console_root(digest_root)
        / publish_console.CONSOLE_DIRNAME
        / publish_console.BAND_FILENAME
    )


def read_band(path: Path) -> ConsoleBand:
    """Load the published band back through the contract that wrote it."""
    return ConsoleBand.read(path)


# --- words -------------------------------------------------------------------


def plural(count: int, one: str, many: str) -> str:
    """A count with its noun, singular where it is one."""
    return f"{count} {one if count == 1 else many}"


def clock(ms: int | None) -> str | None:
    """Hours and minutes, or the honest absence of a measurement.

    Never a decimal hour: an operator reads a clock, and `4.2 h` is a number he
    has to convert before it means anything. A total that rounds to nothing
    still ran, so it prints `<1 m` rather than `0 m`.
    """
    if ms is None or ms <= 0:
        return None
    minutes = round(ms / 60_000)
    if minutes == 0:
        return "<1 m"
    hours = minutes // 60
    return f"{minutes} m" if hours == 0 else f"{hours} h {minutes % 60} m"


def _mb(byte_count: int) -> str:
    """Megabytes, to one decimal."""
    return f"{byte_count / 1024 / 1024:.1f} MB"


def roughly(value: float) -> str:
    """A count at the precision its basis supports.

    The rate under the runway is a median whose spread is near a fifth of
    itself, so the trailing digits of a six-figure answer are noise. Three
    significant figures leaves a small answer exact and stops a large one
    claiming a hundred articles of accuracy nothing measured (Rule #10).
    """
    if value <= 0:
        return "0"
    scale = 10 ** max(0, math.floor(math.log10(value)) - 2)
    return f"{round(value / scale) * scale:,}"


# --- arithmetic --------------------------------------------------------------


def middle_of(values: Sequence[float]) -> float | None:
    """The middle value, or None where there is nothing to take a middle of.

    The median and not the mean everywhere on this band: one pathological day
    would otherwise decide a figure the operator reads as typical.
    """
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def site_cost(days: Sequence[PublicRunDay]) -> tuple[float | None, int]:
    """What one more published article costs, as a median over the record.

    A day's cost is its own bytes minus the previous day's, over the articles it
    published. A day that published nothing has no rate - zero here would say
    its articles were free, and there were none.

    Returns the median and the number of days it was measured over, which is
    what the band prints beside it (Rule #10).
    """
    ordered = sorted(days, key=lambda row: row.date)
    measured: list[float] = []
    for index in range(1, len(ordered)):
        day = ordered[index]
        if day.published_items <= 0:
            continue
        measured.append(
            (day.site_bytes - ordered[index - 1].site_bytes) / day.published_items
        )
    return middle_of(measured), len(measured)


def articles_to_cap(site_bytes: int, bytes_per_item: float | None) -> float | None:
    """Published articles of room left, at the cost the record measured.

    Articles and not days, because nothing here has ever measured a daily rate.
    None where there is no rate to divide by: a tree that never grew over an
    article it published has no runway, and printing one anyway is the defect
    this replaced.
    """
    if bytes_per_item is None or bytes_per_item <= 0:
        return None
    return (PAGES_CAP_BYTES - site_bytes) / bytes_per_item


# --- the pieces --------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """One thing wrong on one route: the strip's fragment and the band's line."""

    #: Short enough to sit beside a label.
    text: str
    #: What the state costs rather than what it is called. The strip has room
    #: for two words and the band has room for a sentence.
    sentence: str
    severity: int


def worst_of(candidates: Sequence[Candidate]) -> Candidate | None:
    """The loudest candidate, or None when every one of them is clear.

    A stable sort, so the order the caller built the list in decides a tie.
    """
    ranked = sorted(candidates, key=lambda candidate: -candidate.severity)
    return ranked[0] if ranked else None


def run_health(run: PublicRunRecord, floor_pct: float) -> Health:
    """The same rule the run strip colours a square by, and the same floor CI
    opens an issue on - so a red square, an open issue and this sentence agree."""
    if run.status == "failed":
        return Health.RED
    attempted = run.succeeded + run.failed
    if attempted == 0:
        return Health.AMBER
    if (run.succeeded / attempted) * 100 < floor_pct:
        return Health.RED
    if run.failed > 0 or run.status != "completed" or run.source_list_stale:
        return Health.AMBER
    return Health.GREEN


@dataclass(frozen=True)
class FeedTrouble:
    """How many feeds are resting, failing and unread, and over how many runs."""

    rested: int
    failed: int
    unread: int
    runs: int


def feed_trouble(rows: Sequence[FeedHealthRow], quarantine_after: int) -> FeedTrouble:
    """What the feed ledger says is wrong, over the span the caller handed in.

    `discover.settled` first, so a second attempt at a run cannot count a feed
    twice. Then the pipeline's own rules: `discover.resting` decides a rest and
    `FeedHealthRow.failing` decides a failure.

    The third number is the one that used to be missing. A feed whose every row
    is a robots answer was not read at all, so it is neither working nor broken -
    and until 2026-09-03 it was counted as a feed that did not fail.
    """
    ordered = sorted(discover.settled(rows), key=lambda row: (row.date, row.run_id))
    by_feed: dict[str, list[FeedHealthRow]] = defaultdict(list)
    for row in ordered:
        by_feed[row.feed_id].append(row)
    rested = discover.resting(ordered, after_failures=quarantine_after)
    failed = 0
    unread = 0
    for feed_id, group in by_feed.items():
        asked = [row for row in group if row.attempted and not row.preserves]
        # Counted over every feed and not only the ones still being asked, the
        # way the reliability record counts it: a rest and a robots answer are
        # both absent from the denominator, because neither one asked the feed
        # whether it still works.
        if not asked:
            unread += 1
        if feed_id in rested:
            continue
        if any(row.failing for row in asked):
            failed += 1
    return FeedTrouble(
        rested=len(rested),
        failed=failed,
        unread=unread,
        runs=len({row.run_id for row in ordered}),
    )


def pipelines_candidates(
    newest: PublicRunDay | None,
    feeds: FeedTrouble,
    *,
    floor_pct: float,
    quarantine_after: int,
) -> list[Candidate]:
    """What is wrong on Pipelines, loudest kind first.

    The runs come before the feeds and the order is load-bearing: a resting feed
    and a failed run both rank BROKEN, `worst_of` sorts stably, and a rest clears
    itself after `availability_strikes_before_rest` skips while a failed run does
    not. Listing the feeds first handed every tie to the state that fixes itself.
    """
    found: list[Candidate] = []
    if newest is not None:
        verdicts = [run_health(run, floor_pct) for run in newest.runs]
        red = sum(1 for verdict in verdicts if verdict is Health.RED)
        amber = sum(1 for verdict in verdicts if verdict is Health.AMBER)
        if red > 0:
            found.append(
                Candidate(
                    text=f"{plural(red, 'run', 'runs')} failed",
                    sentence=(
                        f"{plural(red, 'run', 'runs')} failed, so the items "
                        f"{'it' if red == 1 else 'they'} planned are not in the day."
                    ),
                    severity=BROKEN,
                )
            )
        if amber > 0:
            found.append(
                Candidate(
                    text=f"{plural(amber, 'run', 'runs')} worth a look",
                    sentence=(
                        f"{plural(amber, 'run', 'runs')} finished but not cleanly, so the "
                        "day may hold fewer items than it planned."
                    ),
                    severity=WORTH_A_LOOK,
                )
            )
    if feeds.rested > 0:
        # The retry count comes from `availability_strikes_before_rest`, never a
        # literal: an operator who moves the knob would otherwise be reading
        # yesterday's rule in today's sentence.
        carry = (
            "1 feed is resting, so nothing it carries reaches the digest."
            if feeds.rested == 1
            else f"{feeds.rested} feeds are resting, so nothing they carry reaches the digest."
        )
        found.append(
            Candidate(
                text=f"{plural(feeds.rested, 'feed', 'feeds')} resting",
                sentence=f"{carry} Each is asked again after {quarantine_after} runs.",
                severity=BROKEN,
            )
        )
    if feeds.failed > 0:
        carries = "it carries" if feeds.failed == 1 else "they carry"
        answers = "it answers" if feeds.failed == 1 else "they answer"
        found.append(
            Candidate(
                text=f"{plural(feeds.failed, 'feed', 'feeds')} failing",
                sentence=(
                    f"{plural(feeds.failed, 'feed', 'feeds')} failed on the last ask, so the "
                    f"digest is short of what {carries} until {answers} again."
                ),
                severity=WORTH_A_LOOK,
            )
        )
    if feeds.unread > 0:
        # The lowest rank on purpose. Nobody can act on a publisher's own rules,
        # so this must never outrank a run that failed - but a desk short of a
        # source is worth knowing. The run count is in the sentence because the
        # ledger read behind it is bounded: "has never been read" would claim a
        # span nothing here opened.
        n = feeds.unread
        found.append(
            Candidate(
                text=f"{plural(n, 'feed', 'feeds')} unread",
                sentence=(
                    f"{plural(n, 'feed', 'feeds')} {'was' if n == 1 else 'were'} not read in "
                    f"the last {plural(feeds.runs, 'run', 'runs')} - a rest or the site's own "
                    f"rules held {'it' if n == 1 else 'them'} back on every one - so the "
                    f"digest carried nothing from {'it' if n == 1 else 'them'}."
                ),
                severity=WORTH_KNOWING,
            )
        )
    return found


@dataclass(frozen=True)
class BandModel:
    """The one day's model facts the band draws, each from its own home.

    `failed`, `refused_for_length` and `total_ms` are the newest day's own
    item-health rows. `not_sure` and `read_in_part` are the run's settled
    published-set counts from the day-metrics record: the score ledger keeps a
    row per measurement, so a re-scored item counts twice and a scored-then-
    dropped item counts at all, where the record counts the published set once.
    None is preserved as "unmeasured" throughout - no health rows means no
    health fact, no record means no published-set count, and neither reads as a
    zero.
    """

    failed: int | None
    refused_for_length: int | None
    not_sure: int | None
    read_in_part: int | None
    total_ms: int | None


def band_model(
    health_rows: Sequence[Mapping[str, str]], record: DayMetrics | None
) -> BandModel:
    """The band's model facts for one day, from its bounded rows and record."""
    times = [
        value
        for value in (_number(row.get("summarize_ms")) for row in health_rows)
        if value is not None and value > 0
    ]
    return BandModel(
        failed=(
            None
            if not health_rows
            else sum(1 for row in health_rows if row.get("outcome") == "failed")
        ),
        refused_for_length=(
            None
            if not health_rows
            else sum(1 for row in health_rows if row.get("code") == "context_exceeded")
        ),
        total_ms=None if not times else int(sum(times)),
        not_sure=None if record is None else record.bands.low,
        read_in_part=None if record is None else record.items_truncated,
    )


def model_candidates(day: BandModel | None) -> list[Candidate]:
    """What the Summaries route's own panels would make an operator look at."""
    if day is None:
        return []
    found: list[Candidate] = []
    if day.failed is not None and day.failed > 0:
        n = day.failed
        found.append(
            Candidate(
                text=f"{plural(n, 'item', 'items')} failed",
                sentence=(
                    f"{plural(n, 'item', 'items')} failed, so "
                    f"{'it is' if n == 1 else 'they are'} not in the day the digest published."
                ),
                severity=BROKEN,
            )
        )
    # Zero is the expected reading here: at the cap in force no prompt can reach
    # the window, so anything above zero says the cap moved past what fits.
    if day.refused_for_length is not None and day.refused_for_length > 0:
        n = day.refused_for_length
        found.append(
            Candidate(
                text=f"{plural(n, 'item', 'items')} too long to send",
                sentence=(
                    f"{plural(n, 'item', 'items')} {'was' if n == 1 else 'were'} too long to "
                    f"send, so the model did not see {'it' if n == 1 else 'them'} and the "
                    "truncation cap is past what fits."
                ),
                severity=WORTH_A_LOOK,
            )
        )
    if day.not_sure is not None and day.not_sure > 0:
        n = day.not_sure
        found.append(
            Candidate(
                text=f'{n} marked "not sure"',
                sentence=(
                    f"{n} {'summary is' if n == 1 else 'summaries are'} marked \"not sure\", "
                    f"so the checker could not hold {'it' if n == 1 else 'them'} against the "
                    "article."
                ),
                severity=WORTH_A_LOOK,
            )
        )
    if day.read_in_part is not None and day.read_in_part > 0:
        n = day.read_in_part
        found.append(
            Candidate(
                text=f"{plural(n, 'article', 'articles')} read only in part",
                sentence=(
                    f"{plural(n, 'article', 'articles')} {'was' if n == 1 else 'were'} read "
                    "only in part, so the summary was written from less than the whole piece."
                ),
                severity=WORTH_KNOWING,
            )
        )
    return found


@dataclass(frozen=True)
class MachineFacts:
    """The band's slice of the machine counters, and only that slice.

    `frontend/src/lib/server/runtime-counters.ts` builds the whole picture for
    the Hardware route and keeps doing so - it will read the published machine
    shards after row 10. What the band needs is three numbers, so three are
    derived here rather than the twenty the route draws.
    """

    refused: int
    shards: int
    reported: int
    read_spread: float | None


def machine_facts(rows: Sequence[Mapping[str, str]]) -> MachineFacts:
    """Refused runs, and the newest run's shard count, answers and read spread.

    A run is refused whole when its rows cannot be made into one run: two
    servers answered for one shard and neither can be added to the other, or a
    row does not say which shard it came from. Refusing is never silent - a page
    that prints half a reconcilable run is worse than one that says which run it
    cannot read.
    """
    by_run: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        run_id = row.get("run_id") or ""
        if run_id:
            by_run[run_id].append(row)
    refused = 0
    newest: MachineFacts | None = None
    # Run ids are `<date>-<n>`, so a plain string sort orders a day's runs
    # correctly and orders the days too.
    for run_id in sorted(by_run, reverse=True):
        run_rows = by_run[run_id]
        facts = _one_run(run_rows)
        if facts is None:
            refused += 1
            continue
        if newest is None:
            newest = facts
    if newest is None:
        return MachineFacts(refused=refused, shards=0, reported=0, read_spread=None)
    return MachineFacts(
        refused=refused,
        shards=newest.shards,
        reported=newest.reported,
        read_spread=newest.read_spread,
    )


#: Every counter cell. Two rows for one shard are the same scrape only if all of
#: these match; a difference means two servers, and two servers cannot be added
#: or picked between.
_COUNTER_CELLS: Final[tuple[str, ...]] = (
    "scraped_at",
    "prompt_tokens_total",
    "prompt_tokens_cached_total",
    "prompt_seconds_total",
    "tokens_predicted_total",
    "tokens_predicted_seconds_total",
    "n_decode_total",
    "n_tokens_max",
    "n_busy_slots_per_decode",
    "job_seconds",
    "cpu_model",
    "cpu_busy_pct",
    "peak_rss_bytes",
    "model_load_ms",
)


def _one_run(rows: Sequence[Mapping[str, str]]) -> MachineFacts | None:
    """One run's rows as one run, or None when they cannot be."""
    if len({(row.get("date", ""), row.get("shards", "")) for row in rows}) > 1:
        return None
    by_shard: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        key = row.get("shard", "")
        if _number(key) is None:
            return None
        by_shard[key].append(row)
    kept: list[Mapping[str, str]] = []
    for same_shard in by_shard.values():
        scrapes = {tuple(row.get(cell, "") for cell in _COUNTER_CELLS) for row in same_shard}
        if len(scrapes) > 1:
            return None
        kept.append(same_shard[0])
    shards = _number(rows[0].get("shards"))
    if shards is None or shards < 1 or len(kept) > shards:
        return None
    if any((_number(row.get("shard")) or 0) >= shards for row in kept):
        return None
    rates = [
        rate
        for rate in (
            _rate(_number(row.get("prompt_tokens_total")), _number(row.get("prompt_seconds_total")))
            for row in kept
        )
        if rate is not None
    ]
    # One shard cannot spread against itself, so a run of one reports nothing
    # rather than 1.00x, which would read as "the hosts agreed".
    spread = None if len(rates) < 2 else max(rates) / min(rates)
    return MachineFacts(
        refused=0, shards=int(shards), reported=len(kept), read_spread=spread
    )


def machine_candidates(facts: MachineFacts) -> list[Candidate]:
    """What the Hardware route's own panels would make an operator look at.

    The read spread is reported as a FACT and not as a verdict: nobody has
    agreed how far apart two shards of one run may read before it is a problem,
    and a severity that invented one would publish a threshold this project has
    not taken.
    """
    found: list[Candidate] = []
    if facts.refused > 0:
        n = facts.refused
        found.append(
            Candidate(
                text=f"{plural(n, 'run', 'runs')} cannot be read",
                sentence=(
                    f"{plural(n, 'run', 'runs')} cannot be read, so no figure on the Hardware "
                    f"route counts {'it' if n == 1 else 'them'}."
                ),
                severity=WORTH_A_LOOK,
            )
        )
    silent = facts.shards - facts.reported
    if facts.shards > 0 and silent > 0:
        found.append(
            Candidate(
                text=f"{plural(silent, 'shard', 'shards')} reported nothing",
                sentence=(
                    f"{plural(silent, 'shard', 'shards')} of the newest run reported nothing, "
                    f"so the run's totals are short by whatever "
                    f"{'it' if silent == 1 else 'they'} did."
                ),
                severity=WORTH_A_LOOK,
            )
        )
    if facts.read_spread is not None:
        found.append(
            Candidate(
                text=f"shards read {facts.read_spread:.2f}x apart",
                sentence=(
                    f"The newest run's shards read {facts.read_spread:.2f}x apart, so a rate "
                    "taken over the whole run hides how slow the slowest of them was."
                ),
                severity=WORTH_KNOWING,
            )
        )
    return found


@dataclass(frozen=True)
class ReadSpread:
    """How far apart one day's runs read, fastest over slowest."""

    runs: int
    ratio: float


def read_spread_of(
    date_stamp: str | None, rows: Sequence[Mapping[str, str]]
) -> ReadSpread | None:
    """The read rate and not the write rate.

    Measured over the committed ledger the write rate barely moves and the read
    rate is where the host lottery bites, so a spread taken on writing would
    report a steady machine on a day that was anything but. Cached prompt tokens
    come out of the count - the machine did not read them.
    """
    if date_stamp is None:
        return None
    per_run: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in rows:
        if (row.get("date") or "") != date_stamp:
            continue
        prefill_ms = _number(row.get("prefill_ms"))
        prompt = _number(row.get("input_tokens"))
        cell = row.get("cached_tokens") or ""
        cached = 0.0 if cell == "" else _number(cell)
        if prefill_ms is None or prompt is None or cached is None:
            continue
        evaluated = prompt - cached
        if prefill_ms <= 0 or evaluated <= 0:
            continue
        bucket = per_run[row.get("run_id") or ""]
        bucket[0] += evaluated
        bucket[1] += prefill_ms
    rates = [tokens / (ms / 1000) for tokens, ms in per_run.values()]
    if not rates:
        return None
    slowest = min(rates)
    if slowest <= 0:
        return None
    return ReadSpread(runs=len(rates), ratio=max(rates) / slowest)


def _number(cell: str | None) -> float | None:
    """A cell that reads as a finite number, or None. An empty cell is None."""
    if cell is None or cell == "":
        return None
    try:
        value = float(cell)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _rate(tokens: float | None, seconds: float | None) -> float | None:
    """Tokens over seconds. None where either is unknown or no time was spent."""
    if tokens is None or seconds is None or seconds <= 0:
        return None
    return tokens / seconds


# --- the band ----------------------------------------------------------------


def build(
    *,
    generated_at: str,
    days: Sequence[PublicRunDay],
    feeds: Sequence[FeedHealthRow],
    health_rows: Sequence[Mapping[str, str]],
    record: DayMetrics | None,
    counters: Sequence[Mapping[str, str]],
    months: Sequence[str],
    run: RunConfig,
    collect: CollectConfig,
) -> ConsoleBand:
    """The whole band, from rows a caller read. Pure, so a fixture drives it.

    `days` is newest last, the order the run-day shards hold. Everything the
    band says about "the newest day" is keyed to the newest of these, so the
    verdict, the size, the worst fact and the carries cannot name two different
    days.
    """
    ordered = sorted(days, key=lambda row: row.date)
    newest = ordered[-1] if ordered else None
    floor_pct = run.success_floor_pct
    quarantine_after = collect.availability_strikes_before_rest
    trouble = feed_trouble(feeds, quarantine_after)
    newest_model = None if newest is None else band_model(health_rows, record)

    verdict = _verdict(newest, floor_pct)
    worst_pipelines = worst_of(
        pipelines_candidates(
            newest, trouble, floor_pct=floor_pct, quarantine_after=quarantine_after
        )
    )
    worst_model = worst_of(model_candidates(newest_model))
    worst_machine = worst_of(machine_candidates(machine_facts(counters)))
    found = {
        RouteId.PIPELINES: worst_pipelines,
        RouteId.MODEL: worst_model,
        RouteId.MACHINE: worst_machine,
    }
    carries = _carries(newest, newest_model, health_rows)
    routes: list[ConsoleRoute] = []
    for route_id, label, href, description in ROUTES:
        candidate = found[route_id]
        routes.append(
            ConsoleRoute(
                id=route_id,
                label=label,
                href=href,
                description=description,
                worst=None if candidate is None else candidate.text,
                severity=CLEAR if candidate is None else candidate.severity,
                carries=carries[route_id],
            )
        )
    loudest = max(
        (route for route in routes if route.worst is not None),
        key=lambda route: route.severity,
        default=None,
    )
    worst = None
    if loudest is not None:
        candidate = found[loudest.id]
        if candidate is not None:
            worst = BandWorst(
                id=loudest.id,
                label=loudest.label,
                href=loudest.href,
                sentence=candidate.sentence,
            )
    return ConsoleBand(
        version=ConsoleBand.schema_version(),
        generated_at=generated_at,
        verdict=verdict,
        worst=worst,
        size=_size(ordered, newest),
        routes=routes,
        months=list(months),
    )


def _verdict(newest: PublicRunDay | None, floor_pct: float) -> BandVerdict:
    """Counts first, then what is wrong with them.

    An operator who reads only the first clause still knows whether the day
    published.
    """
    if newest is None:
        return BandVerdict(
            date=None,
            sentence="No run has recorded a manifest yet, so there is nothing to report on.",
            health=Health.AMBER,
            runs=[],
            more_runs=0,
        )
    planned = sum(run.planned for run in newest.runs)
    succeeded = sum(run.succeeded for run in newest.runs)
    failed = sum(run.failed for run in newest.runs)
    verdicts = [run_health(run, floor_pct) for run in newest.runs]
    if Health.RED in verdicts:
        health = Health.RED
    elif Health.AMBER in verdicts:
        health = Health.AMBER
    else:
        health = Health.GREEN
    squares = [
        BandRun(health=value, label=f"Run {index + 1} {VERDICT_WORD[value]}")
        for index, value in enumerate(verdicts)
    ]
    head = (
        f"{newest.date} ran {plural(len(newest.runs), 'run', 'runs')} and published "
        f"{succeeded} of {planned} planned items."
    )
    if health is Health.GREEN:
        tail = "Every run finished clean."
    elif failed > 0:
        tail = f"{plural(failed, 'item', 'items')} failed."
    else:
        tail = "One or more runs is worth a look."
    return BandVerdict(
        date=newest.date,
        sentence=f"{head} {tail}",
        health=health,
        runs=squares[:BAND_RUN_SQUARES],
        more_runs=max(0, len(squares) - BAND_RUN_SQUARES),
    )


def _size(
    ordered: Sequence[PublicRunDay],
    newest: PublicRunDay | None,
) -> BandSize:
    """The committed tree against the 1 GB Pages cap.

    Not windowed by the control below it, and that is the difference between
    this and the panel on Pipelines. The band stands on all three routes, so a
    figure that moved when a control on one route moved would read as three
    different sites.
    """
    if newest is None:
        return BandSize(
            bytes=None,
            cap_fraction=None,
            left_mb=None,
            articles_to_cap=None,
            measured_days=0,
            sentence=(
                "No run has recorded a size yet, so there is nothing to hold against the "
                "1 GB limit."
            ),
        )
    median, measured_days = site_cost(ordered)
    room = articles_to_cap(newest.site_bytes, median)
    # One line. The rate this divides by, the days it was measured over and the
    # clause about which tree the cap measures all live on the Pipelines panel
    # that owns them - a band that repeated them spent sixty of its hundred
    # words on a caveat.
    if room is None:
        sentence = (
            f"{_mb(newest.site_bytes)} of the 1 GB limit - no published day has grown it "
            "over an article yet, so there is no room figure."
        )
    else:
        sentence = (
            f"{_mb(newest.site_bytes)} of the 1 GB limit - room for about {roughly(room)} "
            "more articles."
        )
    return BandSize(
        bytes=newest.site_bytes,
        cap_fraction=newest.site_bytes / PAGES_CAP_BYTES,
        left_mb=(PAGES_CAP_BYTES - newest.site_bytes) / 1024 / 1024,
        articles_to_cap=None if room is None else max(0, int(room)),
        measured_days=measured_days,
        sentence=sentence,
    )


def _carries(
    newest: PublicRunDay | None,
    model: BandModel | None,
    health_rows: Sequence[Mapping[str, str]],
) -> dict[RouteId, str]:
    """One sentence per route pointing at the panel another route owns.

    No chart. They are what stops a route hiding the panel that explains
    another, and every number in them is derived rather than stated: a carry
    quoting a figure nobody measured is worse than no carry.
    """
    model_clock = clock(None if model is None else model.total_ms)
    spread = read_spread_of(None if newest is None else newest.date, health_rows)
    return {
        RouteId.PIPELINES: (
            "Nothing on this day recorded how long the model spent."
            if model_clock is None
            else f"The model spent {model_clock} of this."
        ),
        RouteId.MODEL: (
            "No run on this day recorded a read speed, so there is no spread to compare."
            if spread is None
            else (
                "This day ran as one run, so there is nothing to compare it against."
                if spread.runs < 2
                else f"This day ran in {spread.runs} runs, {spread.ratio:.2f}x apart on read speed."
            )
        ),
        RouteId.MACHINE: (
            "No article is on record for this day."
            if newest is None
            else f"{plural(newest.published_items, 'article', 'articles')} on this day."
        ),
    }


def publish(
    *,
    state_root: Path,
    digest_root: Path,
    generated_at: str,
    today: date,
    console: ConsoleConfig,
    run: RunConfig,
    collect: CollectConfig,
    telemetry_root: Path | None = None,
) -> Path | None:
    """Read the covered span, derive the band and write it if its bytes moved.

    Returns the path when the band changed and None when it did not. The reads
    are:

    - the newest `shard_months(widest)` run-day shards, for the runs, the size
      and the article counts;
    - `state/feed-health/` over the widest span, through `ledger.load_health`;
    - the newest day's item-health shard and its day-metrics record, one file
      each;
    - the counters for the months the widest span reaches.

    `widest` is the largest of `console.window_presets`, which is the furthest
    back any panel on any route can draw. Nothing here opens a day payload.
    """
    widest = max(console.window_presets)
    months = months_a_window_can_touch(widest)
    day_root = publish_console.series_root(digest_root, publish_run_days.DIRNAME)
    available = publish_console.published_months(
        digest_root, publish_run_days.DIRNAME, publish_run_days.SUFFIX
    )
    days: list[PublicRunDay] = []
    for month in available[-months:]:
        days.extend(publish_run_days.read_shard(day_root / f"{month}{publish_run_days.SUFFIX}"))
    days.sort(key=lambda row: row.date)
    newest_date = days[-1].date if days else None
    # The window is anchored on the newest day found and never on today: a clock
    # anchor answers with nothing at all for a corpus that stopped publishing
    # three months ago.
    anchor = newest_date or today.isoformat()
    feeds = ledger.load_health(state_root, today=anchor, within_days=widest)
    health_rows = (
        []
        if newest_date is None
        else publish_day_metrics.read_health_rows(state_root, newest_date)
    )
    record = None
    if newest_date is not None:
        record_path = publish_day_metrics.day_metrics_path(state_root, newest_date)
        if record_path.is_file():
            record = DayMetrics.read(record_path)
    counters = _counter_rows(state_root, months=months, anchor=anchor)
    band = build(
        generated_at=generated_at,
        days=[row for row in days if _within(row.date, anchor, widest)],
        feeds=feeds,
        health_rows=health_rows,
        record=record,
        counters=counters,
        months=fetchable_months(digest_root, telemetry_root),
        run=run,
        collect=collect,
    )
    target = band_path(digest_root)
    payload = band.to_json().encode("utf-8")
    return target if publish_console.write_if_changed(target, payload) else None


def _within(day: str, anchor: str, window_days: int) -> bool:
    """Is this date inside the window, counting the anchor as day one?"""
    return (
        date.fromisoformat(anchor) - date.fromisoformat(day)
    ).days < window_days and day <= anchor


#: Every month series the console asks for by name, as (directory, suffix).
#:
#: Telemetry is not here. It predates `publish_console` and owns its own root,
#: which the canary keeps under `state/` rather than beside these six - so it is
#: a parameter of `fetchable_months` instead of a row of this table.
FETCHED_SERIES: Final[tuple[tuple[str, str], ...]] = (
    (publish_scores.DIRNAME, publish_scores.SUFFIX),
    (publish_feed_health.DIRNAME, publish_feed_health.SUFFIX),
    (publish_run_days.DIRNAME, publish_run_days.SUFFIX),
    (publish_day_metrics.PUBLIC_DIRNAME, publish_day_metrics.PUBLIC_SUFFIX),
    (publish_machine.DIRNAME, publish_machine.SUFFIX),
    (publish_span_rollup.DIRNAME, publish_span_rollup.SUFFIX),
)


def fetchable_months(digest_root: Path, telemetry_root: Path | None = None) -> list[str]:
    """Every month a shard the console fetches exists for, oldest first.

    The union across all seven series and not the run-day months alone. A
    console that took one series for the list would never ask for a month the
    others hold on their own - and they can differ, because each is pruned by
    its own `observability.public_*_keep_months` and the canary's telemetry is
    projected over a wider span than its run-days.

    Telemetry is the one that matters most: the console holds no row until a
    telemetry shard lands, so a month missing from this list is a month of the
    page that never fills. It is a parameter because it predates
    `publish_console` and owns its own root - the canary keeps it under
    `state/`. Unnamed, it is looked for beside the digest root like the other
    six, which is where the real tree has it. It is never taken from
    `publish_telemetry`'s module default: a tree under test would then answer
    with the repository's own months.

    Seven directory listings and no file opened, and each directory is bounded
    by its own retention knob, so this costs the same on any size of archive
    (`CLAUDE.md` Rule #12).
    """
    found: set[str] = set()
    for dirname, suffix in FETCHED_SERIES:
        found.update(publish_console.published_months(digest_root, dirname, suffix))
    shards = telemetry_root or publish_console.series_root(
        digest_root, publish_telemetry.PUBLIC_TELEMETRY_DIRNAME
    )
    found.update(path.stem for path in month_files(shards, ".csv"))
    return sorted(found)


def _counter_rows(
    state_root: Path, *, months: int, anchor: str
) -> list[Mapping[str, str]]:
    """The counter rows the widest span reaches, as raw cells.

    Raw rather than through `RuntimeCountersRow`, because refusing a run is the
    band's whole point here: a row that will not validate is one of the two
    servers this has to notice, and validating it away would silently drop the
    evidence. The growing read behind it is `publish_machine`'s and is declared
    there.
    """
    source = ledger.runtime_counters_path(state_root)
    if not source.is_file():
        return []
    oldest = publish_console.oldest_month_kept(date.fromisoformat(anchor), months)
    with source.open("r", encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if (row.get("date") or "")[:7] >= oldest]
