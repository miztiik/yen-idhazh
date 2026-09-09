"""Every dataset the console fetches, and what may not cross with it.

The console reads twelve datasets. Two were already published, one had a
projection, and the other nine were read out of `state/` at build time and
inlined - so the list of what the console needs lived nowhere, and a producer, a
consumer and a gate each had to work it out again. This module is that list, as
code rather than as prose, so a dataset added without a schema fails at import
instead of at review.

**It is an index and never a shape.** Nothing here is persisted and nothing here
is a `Contract`; the shapes live in the modules named beside each entry. What
this module owns is the pairing - dataset, published schema, forbidden cells -
and the import-time proof that no forbidden cell is on the shape it names.

`docs/architecture/publishing/console-payloads.md` is the page a person reads;
this is the copy a build reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from idhazh.contracts import (
    console_band,
    public_eval,
    public_feed_health,
    public_run_day,
    public_telemetry,
)
from idhazh.contracts.base import Contract
from idhazh.contracts.day_metrics import DayMetrics
from idhazh.contracts.public_telemetry import PublicTelemetryRow
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.source_health_view import SourceHealthView
from idhazh.contracts.span_rollup import SpanRollupRow


@dataclass(frozen=True)
class ConsolePayload:
    """One dataset the console fetches."""

    #: The reader in `frontend/src/lib/server/` this replaces, so a person can
    #: find the code that used to do it at build time.
    reader: str
    #: Where the pipeline writes the fetchable payload, relative to the repo.
    published_to: str
    #: The shape, which owns the schema stem and the version stamp.
    contract: type[Contract]
    #: Cells on the source ledger that may never reach a browser. Empty is a
    #: real answer for a shape that is not a projection of a wider row, and the
    #: contract's own module says why in each case.
    forbidden: frozenset[str]
    #: Why this dataset crosses at all, in one line.
    why: str


#: The twelve, in the order a cold load needs them.
#:
#: The band is first because every route carries it and nothing else can be
#: asked for until its months list has landed. The rest are month or day shards
#: the console asks for by name as the operator pans.
CONSOLE_PAYLOADS: Final[tuple[ConsolePayload, ...]] = (
    ConsolePayload(
        reader="console-shell.ts consoleShell()",
        published_to="frontend/public/console/band.json",
        contract=console_band.ConsoleBand,
        forbidden=console_band.FORBIDDEN_COLUMNS,
        why=(
            "The one thing an operator reads first: did it work, what is worst, how "
            "much room is left."
        ),
    ),
    ConsolePayload(
        reader="payload.ts telemetryRows()",
        published_to="frontend/public/telemetry/<YYYY-MM>.csv",
        contract=PublicTelemetryRow,
        forbidden=public_telemetry.FORBIDDEN_COLUMNS,
        why="One planned item per run: the stage that failed, and what each stage cost.",
    ),
    ConsolePayload(
        reader="payload.ts itemHealthRows() and itemHealthForDay()",
        published_to="frontend/public/telemetry/<YYYY-MM>.csv",
        contract=PublicTelemetryRow,
        forbidden=public_telemetry.FORBIDDEN_COLUMNS,
        why=(
            "The same census under a second reader. It resolves to the telemetry "
            "shard rather than a shape of its own, because a second projection of one "
            "ledger is two schemas for one row - and the two columns the console reads "
            "from the census and not from the projection, span_integrity and "
            "elements_found, arrive on the day-metrics payload instead."
        ),
    ),
    ConsolePayload(
        reader="payload.ts evalRows()",
        published_to="frontend/public/scores/<YYYY-MM>.csv",
        contract=public_eval.PublicEvalRow,
        forbidden=public_eval.FORBIDDEN_COLUMNS,
        why="One scored attempt: faithfulness, coverage, the counterweights and the band.",
    ),
    ConsolePayload(
        reader="payload.ts feedResults()",
        published_to="frontend/public/feed-health/<YYYY-MM>.csv",
        contract=public_feed_health.PublicFeedRow,
        forbidden=public_feed_health.FORBIDDEN_COLUMNS,
        why="One feed read per run: whether a source answered, and our own reason when it did not.",
    ),
    ConsolePayload(
        reader="payload.ts loadManifests()",
        published_to="frontend/public/run-days/<YYYY-MM>.json",
        contract=public_run_day.PublicRunDay,
        forbidden=public_run_day.FORBIDDEN_COLUMNS,
        why="What each run of a day did, and how big the site was when it finished.",
    ),
    ConsolePayload(
        reader="payload.ts publishedItems()",
        published_to="frontend/public/run-days/<YYYY-MM>.json",
        contract=public_run_day.PublicRunDay,
        forbidden=public_run_day.FORBIDDEN_COLUMNS,
        why=(
            "Articles a day published, the denominator of the per-article cost. It "
            "rides on the run-day row because the alternative is opening a "
            "hundred-kilobyte day payload to read one integer (Rule #12)."
        ),
    ),
    ConsolePayload(
        reader="payload.ts publishedCharts()",
        published_to="frontend/public/run-days/<YYYY-MM>.json",
        contract=public_run_day.PublicRunDay,
        forbidden=public_run_day.FORBIDDEN_COLUMNS,
        why="Charts a reader can actually see on a day, counted from the same payload.",
    ),
    ConsolePayload(
        reader="payload.ts dayMetrics()",
        published_to="frontend/public/day-metrics/<YYYY-MM>.json",
        contract=DayMetrics,
        forbidden=frozenset(),
        why=(
            "What a run settled about one day: the bands, the reasons, the throughput "
            "and the extraction census. Published as its own shape rather than as a "
            "projection - every cell on it is a count or a measurement of our own "
            "work, so a projection would be a second schema for an identical row."
        ),
    ),
    ConsolePayload(
        reader="runtime-counters.ts loadMachineCounters()",
        published_to="frontend/public/machine/<YYYY-MM>.csv",
        contract=RuntimeCountersRow,
        forbidden=frozenset(),
        why=(
            "What the hardware did while the model ran. Nothing on the row came from "
            "the open web: every cell is our own server's counter, our own job clock "
            "or the runner's CPU name, so the whole row crosses."
        ),
    ),
    ConsolePayload(
        reader="span-rollup.ts loadSpanRollup()",
        published_to="frontend/public/span-rollup/<YYYY-MM>.csv",
        contract=SpanRollupRow,
        forbidden=frozenset(),
        why=(
            "Where a shard's wall clock went. Five span names we chose, a count and "
            "two durations - no cell can hold anything fetched."
        ),
    ),
    ConsolePayload(
        reader="payload.ts sourceHealthView()",
        published_to="frontend/public/source-health.json",
        contract=SourceHealthView,
        forbidden=frozenset(),
        why=(
            "The source census, already published. It is on this list because a list "
            "that omitted what is already done would read as a list of what is left, "
            "and the next reader would have to work out which."
        ),
    ),
)


def payloads_by_stem() -> dict[str, ConsolePayload]:
    """One entry per schema file, so a caller can ask what a stem is for.

    Datasets outnumber schemas - three console reads answer off the run-day row
    and two off the telemetry shard - so the first entry for a stem wins and the
    rest are the same shape under another reader.
    """
    found: dict[str, ConsolePayload] = {}
    for payload in CONSOLE_PAYLOADS:
        found.setdefault(payload.contract.__schema_stem__, payload)
    return found


for _entry in CONSOLE_PAYLOADS:
    _crossed = _entry.forbidden & set(_entry.contract.model_fields)
    if _crossed:
        raise AssertionError(
            f"{_entry.reader} publishes {_entry.contract.__name__} carrying a cell a "
            f"reader may never receive: {sorted(_crossed)}"
        )
