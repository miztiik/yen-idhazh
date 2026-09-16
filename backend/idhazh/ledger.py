"""Read and append the committed ledgers under `state/`.

Every file here is written by CI and read by a later run. All but one are
append-only; the exception is named below. They exist because the pipeline has
no memory of its own: every run starts on a fresh machine with a fresh
checkout, so anything one run needs to tell the next has to be committed
(Guardrail #1).

A ledger partitions only when the read that consumes it carries a time window.
A window lets the reader name the files it wants and skip the rest; without one,
every file is opened anyway and splitting the ledger buys nothing. The rule is
in `docs/architecture/contracts/schemas.md`. `state/visual-prunes/` is the one
exception here, and the paragraph that describes it says what it bought instead.

`state/seen/<YYYY>/<MM>/<DD>.csv` answers "how old is this?" for an article
whose feed carried no date. Read through `collect.seen_window_days`. It files by
day, because a run writes one day and taking a day back is one `rm`. It has no
published mirror at all, so unlike the two health ledgers there is no second
grain anywhere near it.

`state/published/YYYY/MM/DD.csv` answers "have we already run this?" It is the
grain the published tree itself uses, and a run appends to the day its own rows
name and to nothing else. Its read carries `collect.published_window_days`, and
the committed config sets that to `-1` - so today every day file is opened and
the answer is every address ever published. The day grain is what makes a finite
cover possible at all: it names the days in range and opens those files and no
others. Until one is set the grain buys a small merge surface and a removal that
is one `rm`, and not a faster read. Size it from the ceiling, not from today: a
run plans at most `run.safety_ceiling_per_run` items, which the committed config
sets to 80, and the schedule fires five times a day - so a day writes at most 400
rows and a year at most about 146,000. Measured 2026-09-08 on an Intel Core
i7-1265U over the 7,600 committed rows, header included: 106.9 B a row, so a
year of that ceiling is 15.6 MB on disk. The 16 committed days average 475 rows
a day, which is above the ceiling arithmetic because they were written under
three different ceilings - 200 until 2026-08-26, 160 until 2026-09-07, 80 since
- and the newest full day wrote 357. Reading the whole file took a median
32.7 ms over fifteen consecutive runs, best 30.1 and worst 37.5, a spread of
7.4 ms - and as slow as 68.6 ms while other jobs shared the box, which is the
number to remember before reading any wall clock here as a property of the file.
See
`docs/reference/measurements.md`.

`state/feed-health/<YYYY>/<MM>/<DD>.csv` answers "is this source still
working?" One row per feed per run, read through `HEALTH_WINDOW_DAYS`. It files
by day, because a run writes one day and taking a day back is one `rm`. The
console reads these day files directly at build time; there is no published
mirror, and the one that existed until 2026-09-16 was never fetched.

`state/item-health/<YYYY>/<MM>/<DD>.csv` answers "what did every planned item
do?" One row per planned item per run - the fastest-growing of the four. It
files by day, because a run writes one day and taking a day back is one `rm`.
The console reads it a month at a time through the published projection, which
stays monthly: `public_telemetry.publish` folds a month from that month's day
files.

`state/runtime-counters.csv` answers "what did the model server itself count?"
One row per model-server job per shard per run - the `work` job files one for
each of its shards and the `visuals` job files one for the planner it served,
and the `job` cell is what tells them apart. Read one run at a time by an audit
that carries no time window, so it is one file. It is also the slowest-growing:
eight shards times five runs a day, plus one visuals row a run, is 45 rows, and
a year is about 16,400.

`state/telemetry-aggregate/<YYYY-MM>.csv` is what is left of an item-health
month once `observability.item_health_full_grain_months` has passed: one row per
(date, stage), folded by `retention.fold_month`. It files by month because it
summarises a month - a day file of a month's totals is a shape nothing consumes.
It is the one file here that is rewritten rather than appended, because every row
in it is derived from the days it summarises.

`state/feed-retirements.csv` answers "is this address gone for good?" One row
per retired feed endpoint, read whole because a retirement has no time bound -
so it is one file. It is also the smallest: a row is written only when a server
has reported one address permanently gone on five distinct runs.

`state/visual-prunes/YYYY/MM/DD.csv` answers "is the picture backlog
shrinking?" One row per cleanup run, read whole because the question carries no
time bound - and it files by day even so. That is the exception named above: the
read will never carry a window, so the layout buys this ledger no read time at
all. What it buys is the two things it buys for `state/published/` - two runs
collide on a file only when they are the same day, and taking a day back off the
record is one `rm` rather than an edit inside a shared file, which `merge=union`
cannot express. Five rows a day for ever is a collection that grows, and a
collection that grows here takes the layout every other growing one has. A row
is written on every run, including the runs where the policy is switched off and
there is nothing to clean, because a report of "nothing to do" is what makes the
day the policy starts working visible.

No reader fails on a missing file. A fresh clone has no history, and a run with
no history is a run where nothing was seen, nothing was published and no feed
has a record yet - which is exactly what an empty result says.

Callers pass the state directory and never the file name. The layout is one
fact, and it lives here.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Collection, Iterable, Iterator, Sequence
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Final, NamedTuple, Protocol

from idhazh import day_partition, month_partition
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.feed_health import FeedHealthRow, supersedes
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import RETIRED_CELLS, ItemHealthRow, ItemOutcome
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow
from idhazh.contracts.visual_prune import VisualPruneRow

STATE_DIRNAME: Final = "state"
SEEN_DIRNAME: Final = "seen"
HEALTH_DIRNAME: Final = "feed-health"
ITEM_HEALTH_DIRNAME: Final = "item-health"
HOST_FINGERPRINT_DIRNAME: Final = "host-fingerprint"
TELEMETRY_AGGREGATE_DIRNAME: Final = "telemetry-aggregate"
SPAN_ROLLUP_DIRNAME: Final = "span-rollup"
PUBLISHED_DIRNAME: Final = "published"
VISUAL_PRUNES_DIRNAME: Final = "visual-prunes"
COUNTERFACTUAL_SCORES_DIRNAME: Final = "counterfactual-scores"
RUNTIME_COUNTERS_FILENAME: Final = "runtime-counters.csv"
FEED_RETIREMENTS_FILENAME: Final = "feed-retirements.csv"

#: What makes two feed-health rows the same record. One feed, read once, in one
#: run. The ledger always meant that - `docs/architecture/sources/health.md`
#: opens on it - but nothing enforced it, so a second attempt at a run wrote a
#: second verdict for every feed and `discover.resting` counted one failure
#: twice.
#:
#: This is the one key here whose repeated rows can disagree, so it is the one
#: that cannot settle by keeping whichever row arrived first. `FEED_HEALTH_RULE`
#: is how it settles.
FEED_HEALTH_KEY: Final = ("run_id", "feed_id")

#: What makes two item-health rows the same record. One row per planned item per
#: run, which is what the ledger has always meant - written down here because two
#: stages now write it. The worker commits a row as soon as its item settles, and
#: assemble writes the whole day's census afterwards, so both see the same item
#: under the same run and the second one has nothing new to say.
ITEM_HEALTH_KEY: Final = ("date", "run_id", "item_id")

#: What makes two runtime-counter rows the same record. One job's server, one
#: shard, one run. The counters are cumulative for a server process, so a re-run
#: of a failed job would append a second row for the same shard and a run-level
#: sum would count that shard twice. The first row wins, which matches
#: `ITEM_HEALTH_KEY`: a re-run's items are skipped there too, so the two files
#: stay describing the same attempt.
#:
#: `job` is in the key because two jobs write this file from 2026-09-12, and both
#: spell shard 0 of the same run - the `visuals` job runs one server rather than
#: a fan-out. Without it the visual planner's row is dropped as a repeat of the
#: summarizer's, which is silent: the append filter returns a count, not a fault.
RUNTIME_COUNTERS_KEY: Final = ("date", "run_id", "job", "shard")

#: One machine a job, so the same four cells that identify a counter snapshot
#: identify the host that produced it.
HOST_FINGERPRINT_KEY: Final = ("date", "run_id", "job", "shard")

#: What makes two span-rollup rows the same record. One shard's fold of one span
#: name, in one run. The row is derived from the shard's spans, so a re-run of a
#: failed shard recomputes the same fold and a second row would add a count to
#: itself rather than record a new fact. The first row wins, which matches
#: `RUNTIME_COUNTERS_KEY`: a re-run's items are skipped there too, so the two
#: files stay describing the same attempt.
SPAN_ROLLUP_KEY: Final = ("date", "run_id", "shard", "span_name")

#: What makes two cleanup rows the same record. One cleanup pass per run, so a
#: second row under one run id is a second attempt at one execution rather than
#: a second cleanup. Both attempts walked the same tree and would report the
#: same counts, so the first row wins and there is nothing for a preference rule
#: to choose between.
VISUAL_PRUNE_KEY: Final = ("date", "run_id")

#: What makes two counterfactual rows the same record. One run scores one
#: address on one desk once, so a second row under the same four cells is a
#: second attempt at one execution rather than a second answer. Both attempts
#: score the same candidates against the same committed weights and produce the
#: same pair of numbers, so the first row wins and there is nothing for a
#: preference rule to choose between. `vertical` is in the key because a desk is
#: planned on its own: the same address on two desks is two scores, and dropping
#: one of them as a repeat would lose a fact.
COUNTERFACTUAL_SCORE_KEY: Final = ("date", "run_id", "vertical", "url_key")

#: What makes two retirement rows the same record. The address and nothing else:
#: a retirement is permanent for one endpoint key, so a second row for it says
#: nothing the first did not. `feed_id` is deliberately absent - renaming a feed
#: in curated config must not make its dead address eligible again, and editing
#: that feed's URL already produces a different key.
FEED_RETIREMENT_KEY: Final = ("endpoint_key",)

#: How far back a health read looks. Not a policy - just enough history to reach
#: into last month's shard, so a quarantine decided on the first of the month can
#: still see the failures that caused it.
HEALTH_WINDOW_DAYS: Final = 31

#: Which of two rows holding one key survives the settlement. `True` means the
#: later row replaces the one already kept. A key with no rule keeps the first
#: row it saw, which is what every ledger but one wants: there a repeat is the
#: same attempt written twice and the two rows agree.
Preference = Callable[[dict[str, str], dict[str, str]], bool]


class CsvRecord(Protocol):
    """A contract that knows how to write itself as one row of a `state/` file.

    Every ledger here takes one of these rather than a `dict[str, str]`. A dict
    is not a contract - anything can build one and nothing validates it - so a
    caller assembling cells by hand could reach a committed file without a model
    having seen them. Declared as a protocol rather than as a base class because
    these contracts share a shape, not an ancestor: `Contract` is the base for
    every persisted document, and most of those are JSON and have no row.
    """

    def csv_row(self) -> dict[str, str]:
        """Every cell a string, keyed by column name."""
        ...


class CsvContract(Protocol):
    """The class side of `CsvRecord`: the columns, and the reader for an old row."""

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The row's columns, in the row's own order."""
        ...

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> CsvRecord:
        """One row read back, under any heading this ledger has ever carried."""
        ...


class KeyedLedger(NamedTuple):
    """One committed file, what makes two of its rows the same record, and the
    contract that can read a row of it.

    The three travel together because the settlement needs all three and looking
    any of them up a second time is how the file list and the reader list drift
    apart. `carried` names the headings this contract's reader still places after
    the column they belong to was retired; only one shape here has ever retired
    one, and the rest declare nothing.
    """

    path: Path
    key: tuple[str, ...]
    model: type[CsvContract]
    carried: frozenset[str] = frozenset()


def _key_of(row: CsvRecord, key: tuple[str, ...]) -> tuple[str, ...]:
    """The cells that make this row's record, as the file spells them.

    Read off `csv_row` rather than off the attributes, so a filter compares what
    is on disk against what is about to be written rather than against a Python
    value that has still to be rendered.
    """
    cells = row.csv_row()
    return tuple(cells[name] for name in key)


def _feed_health_rule(later: dict[str, str], kept: dict[str, str]) -> bool:
    """`contracts.feed_health.supersedes`, over the two lines as they were read.

    Parsed here rather than compared cell by cell so the rule is written once,
    in the contract that owns what a feed result means. A row that no longer
    parses keeps whatever is already on record - the same choice `load_health`
    makes, and for the same reason: this ledger is diagnostic, and refusing
    would cost a run the whole commit step this pass was called from.
    """
    try:
        return supersedes(FeedHealthRow.from_csv_row(later), FeedHealthRow.from_csv_row(kept))
    except (KeyError, ValueError):
        return False


#: The keys whose repeats can disagree, and how each one picks a winner.
FEED_HEALTH_RULE: Final[Preference] = _feed_health_rule
_PREFERENCES: Final[dict[tuple[str, ...], Preference]] = {FEED_HEALTH_KEY: FEED_HEALTH_RULE}


def seen_relpath(date: str) -> str:
    """`state/seen/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line or a manifest."""
    return f"{STATE_DIRNAME}/{SEEN_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def seen_path(state_dir: Path, date: str) -> Path:
    """The day file a run on this date appends to.

    A day rather than a month, for the reason `published_path` gives: a run
    writes one day, two runs collide on a file only when they are the same day,
    and taking a day back is one `rm` rather than an edit inside a shared shard,
    which `merge=union` cannot express. The caller hands the run's own digest
    date, so `first_seen_run[:10]` names this file for every row inside it - see
    `docs/concepts/partitions.md`.
    """
    return state_dir / SEEN_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def health_relpath(date: str) -> str:
    """`state/feed-health/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{HEALTH_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def health_path(state_dir: Path, date: str) -> Path:
    """The day file a run on this date appends to.

    A day rather than a month, for the reason `item_health_path` gives: a run
    writes one day, two runs collide on a file only when they are the same day,
    and taking a day back is one `rm` rather than an edit inside a shared shard,
    which `merge=union` cannot express. Nothing mirrors this store into
    `frontend/public/`.
    """
    return state_dir / HEALTH_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def item_health_relpath(date: str) -> str:
    """`state/item-health/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{ITEM_HEALTH_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def item_health_path(state_dir: Path, date: str) -> Path:
    """The day file a run on this date appends to.

    A day rather than a month, for the reason `published_path` gives: a run
    writes one day, two runs collide on a file only when they are the same day,
    and taking a day back is one `rm` rather than an edit inside a shared shard,
    which `merge=union` cannot express. The mirror under
    `frontend/public/telemetry/` stays monthly, because its grain follows what a
    browser fetches - see `docs/concepts/partitions.md`.
    """
    return state_dir / ITEM_HEALTH_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def host_fingerprint_relpath(date: str) -> str:
    """`state/host-fingerprint/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{HOST_FINGERPRINT_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def host_fingerprint_path(state_dir: Path, date: str) -> Path:
    """The day file a run on this date records its machines in.

    A day rather than a flat file, for the reason `item_health_path` gives, and
    with a second reason of its own: this collection only earns its keep when
    somebody counts across it, and a day tree is the shape a bounded window can
    read (Guardrail #12).
    """
    return state_dir / HOST_FINGERPRINT_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def telemetry_aggregate_relpath(month: str) -> str:
    """`state/telemetry-aggregate/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{TELEMETRY_AGGREGATE_DIRNAME}/{month}.csv"


def telemetry_aggregate_path(state_dir: Path, month: str) -> Path:
    """Where the folded summary of one item-health month lives.

    Its own directory rather than a second name inside `item-health/`, because
    `day_partition.day_files` refuses anything that is not a `<YYYY>/<MM>/<DD>.csv`
    - a month file beside the day tree would stop every read of the store rather
    than be skipped. The shape differs too: the aggregate is a fold, not a census
    row.
    """
    return state_dir / TELEMETRY_AGGREGATE_DIRNAME / f"{month}.csv"


def span_rollup_relpath(month: str) -> str:
    """`state/span-rollup/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{SPAN_ROLLUP_DIRNAME}/{month}.csv"


def span_rollup_path(state_dir: Path, month: str) -> Path:
    """Where one month's folded span counts live.

    Its own directory rather than a filename beside another store's shards, for
    the reason `telemetry_aggregate_path` gives: a reader that walks a directory
    reads every file it finds as that directory's shape, and the rollup is a
    different shape from a census row.
    """
    return state_dir / SPAN_ROLLUP_DIRNAME / f"{month}.csv"


def published_relpath(date: str) -> str:
    """`state/published/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{PUBLISHED_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def published_path(state_dir: Path, date: str) -> Path:
    """The day file a run on this date appends to.

    A day rather than a month, because this ledger mirrors
    `frontend/public/digest/YYYY/MM/DD/` and every row in it is derived from one
    of those days. Two runs collide on a file only when they are the same day,
    and taking a day back off the site is one `rm` rather than an edit inside a
    shared shard - which `merge=union` cannot express.
    """
    return state_dir / PUBLISHED_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def runtime_counters_relpath() -> str:
    """`state/runtime-counters.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{RUNTIME_COUNTERS_FILENAME}"


def runtime_counters_path(state_dir: Path) -> Path:
    return state_dir / RUNTIME_COUNTERS_FILENAME


def feed_retirements_relpath() -> str:
    """`state/feed-retirements.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{FEED_RETIREMENTS_FILENAME}"


def feed_retirements_path(state_dir: Path) -> Path:
    return state_dir / FEED_RETIREMENTS_FILENAME


def visual_prunes_relpath(date: str) -> str:
    """`state/visual-prunes/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{VISUAL_PRUNES_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def visual_prunes_path(state_dir: Path, date: str) -> Path:
    """The day file a cleanup pass on this date appends its row to.

    A day rather than a month, and not because the read asked for it - the read
    is the whole series and always will be. The grain is here because two runs
    then collide on a file only when they are the same day, and because a day
    taken back off the record is one `rm`. The module docstring states the
    exception this makes to the partition rule.
    """
    return state_dir / VISUAL_PRUNES_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def counterfactual_scores_relpath(date: str) -> str:
    """`state/counterfactual-scores/<YYYY>/<MM>/<DD>.csv` - POSIX, for a log line."""
    stem = f"{date[:4]}/{date[5:7]}/{date[8:10]}.csv"
    return f"{STATE_DIRNAME}/{COUNTERFACTUAL_SCORES_DIRNAME}/{stem}"


def counterfactual_scores_path(state_dir: Path, date: str) -> Path:
    """The day file this date's runs write their two scores per candidate into.

    A day, and here the read asked for it as well as the writer: the only reader
    of this ledger opens a trailing window of days (`lens_weights.window_days`),
    and the retention pass deletes by day. A month file would make both of those
    read or delete weeks nobody asked for.
    """
    return state_dir / COUNTERFACTUAL_SCORES_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def shards_in_window(today: str, within_days: int) -> list[str]:
    """The month stems a window of days can touch, newest first.

    **No ledger is read with this any more.** Every windowed read in this
    repository files by day and takes `day_partition.days_in_window` -
    `drift.read_windows` was the last month-grained one and moved on 2026-09-13
    with `state/scores/`.

    What it still answers is the question the `keep_months` knobs are sized
    against: how many month-shaped buckets a day-counted window reaches. That is
    why `observability.item_health_full_grain_months` is 14 and not 13 against a
    366-day `console.max_window_days`, and `contracts.app_config` states the
    rule while `tests/contracts/` and `tests/retention/` drive it. A grain change
    does not touch it, because both knobs are still counted in months.

    Walking days rather than subtracting months keeps the arithmetic honest
    across a year boundary and needs no calendar table.
    """
    end = date_type.fromisoformat(today)
    stems: list[str] = []
    for offset in range(within_days + 1):
        stem = (end - timedelta(days=offset)).isoformat()[:7]
        if stem not in stems:
            stems.append(stem)
    return stems


def read_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(next(csv.reader(handle), []))


def require_matching_header(path: Path, columns: tuple[str, ...]) -> None:
    header = read_header(path)
    if header and header != columns:
        raise ValueError(
            f"{path.name} has {len(header)} columns and the contract has "
            f"{len(columns)}. Migrate the ledger before appending to it."
        )


def _csv_line(columns: tuple[str, ...], payload: dict[str, str]) -> str:
    """One row, written the way `_append` writes one.

    A re-filed row and an appended row have to be the same bytes, or the file a
    migration leaves behind is a file the next append disagrees with.
    """
    buffer = io.StringIO()
    csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n").writerow(
        {name: payload[name] for name in columns}
    )
    return buffer.getvalue()


def refiler(model: type[CsvContract]) -> Callable[[dict[str, str]], dict[str, str]]:
    """The contract's own reader, as a row-to-row migration.

    `from_csv_row` reads a row under any heading its ledger has ever carried and
    `csv_row` writes it under the heading it carries now, so the map between the
    two lives once, in the contract, rather than in whatever is re-filing the
    file this time.
    """

    def read(raw: dict[str, str]) -> dict[str, str]:
        return model.from_csv_row(raw).csv_row()

    return read


def _headings(lines: list[str], first_column: str) -> set[str]:
    """Every column name the file names anywhere, header blocks included.

    A `merge=union` resolve can leave two header lines in one file, and the
    second one is the only place the other side's column names appear. Reading
    line 1 alone would therefore miss exactly the generation this is asked about.
    """
    sentinel = first_column + ","
    names = set(next(csv.reader(lines[:1]), []))
    for line in lines[1:]:
        if line.startswith(sentinel):
            names.update(next(csv.reader([line]), []))
    return names


def _unplaceable(
    lines: list[str], columns: tuple[str, ...], carried: Collection[str]
) -> list[str]:
    """The headings in this file the current contract cannot read a cell into.

    This is the direction test, and it is put as a question about cells rather
    than about dates: re-filing under `columns` writes the columns the contract
    names and drops everything else, so a heading that is neither a current
    column nor one the reader carries forward names a cell that would be lost.

    The harm it stops is a scheduled run on a checkout that predates a widening.
    That run holds the narrower column list, so re-filing a wide file under it
    would throw away every column the widening added - exit 0, no diagnostic, and
    the cells simply gone.
    """
    return sorted(_headings(lines, columns[0]) - set(columns) - set(carried))


def _refile(
    lines: list[str],
    columns: tuple[str, ...],
    read: Callable[[dict[str, str]], dict[str, str]],
) -> tuple[list[str], int, list[str]]:
    """Every line under one header: the lines to write, how many moved, and a
    complaint for each line no reader could place.

    A line already under the right header and at the right width is kept as the
    bytes that were read and never parsed, so a pass with nothing to do returns
    the list it was handed and its caller writes nothing. Not parsing it is the
    point as well as the saving: this repairs a shape, and asking whether every
    committed cell still parses would be a scan of the archive wearing a repair's
    clothes. A line that has to move and cannot be read is kept too, and named in
    the complaints - dropping it would lose a fact to fix a shape.
    """
    sentinel = columns[0] + ","
    kept = [",".join(columns) + "\n"]
    block = tuple(next(csv.reader(lines[:1]), []))
    moved = 0
    refused: list[str] = []
    for number, line in enumerate(lines[1:], start=2):
        if line.startswith(sentinel):
            block = tuple(next(csv.reader([line]), []))
            continue
        if not line.strip():
            continue
        cells = next(csv.reader([line]), [])
        if block == columns and len(cells) == len(columns):
            kept.append(line if line.endswith("\n") else line + "\n")
            continue
        try:
            kept.append(_csv_line(columns, read(dict(zip(block, cells, strict=False)))))
        except (KeyError, ValueError) as exc:
            refused.append(f"line {number} has {len(cells)} cells and cannot be read: {exc}")
            kept.append(line if line.endswith("\n") else line + "\n")
            continue
        moved += 1
    return kept, moved, refused


def migrate_header(
    path: Path,
    columns: tuple[str, ...],
    read: Callable[[dict[str, str]], dict[str, str]],
    *,
    carried: Collection[str] = (),
) -> int:
    """Re-file every row of `path` under `columns`, and say how many rows moved.

    **It reads line 1 and stops there when the header is already the
    contract's**, whatever the file's size. That is the ordinary case on every
    append, and it is complete rather than optimistic: `_append` writes rows into
    a file that exists and a header only into one that does not, so an append
    cannot put a second header in a file. The only thing that can is a
    `merge=union` resolve, which happens after this run's appends rather than
    before them, and `stages.dedupe_ledgers` settles it there.

    This is the half of a widening `require_matching_header` cannot give. A
    schema change ships a read-side migration, so a file an earlier run wrote
    stays readable; it does not stay appendable, because the header on disk no
    longer names the columns the writer holds. The next run to append would raise
    and lose the whole commit step, every ledger staged beside this one included.

    **It widens, and it refuses to narrow.** `carried` names the headings the
    contract's reader still places - the retired ones - and a file naming
    anything outside that and `columns` is left byte-identical while the call
    raises. That case is a scheduled run on a checkout older than the file: it
    holds the narrower column list, and re-filing under it would drop every cell
    the widening added, with exit 0 and nothing printed. A refusal costs that run
    its commit step, which is the cheaper of the two and the one a person sees.

    `read` is the contract's own reader, which `refiler` builds. `from_csv_row`
    knows every heading the file has ever carried and `csv_row` writes the one it
    carries now, so the map between the two is never written down a second time.

    **What this does not cover.** A rename of the FIRST column, because that name
    is how a header line is told from a row - every contract here opens on
    `version`, whose values are date stamps and never the word.

    Rewriting the file makes the next union merge repeat rows rather than
    headers, and a repeated row is a question this ledger already answers:
    `drop_repeated_rows` settles it after the merge, from the commit step, first
    row winning. Trading a shape nothing settles for a shape something does is
    the whole of what this buys.
    """
    if not path.exists():
        return 0
    header = read_header(path)
    if not header or header == columns:
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        lines = handle.readlines()
    unplaceable = _unplaceable(lines, columns, carried)
    if unplaceable:
        raise ValueError(
            f"{path.name} carries {len(unplaceable)} heading(s) this build cannot place "
            f"({', '.join(unplaceable[:5])}), so re-filing it would drop those cells. "
            "The file is newer than this checkout; run the step again on a build that "
            "names them."
        )
    kept, moved, refused = _refile(lines, columns, read)
    if refused:
        raise ValueError(f"{path.name} holds a row no reader could place: {refused[0]}")
    if kept != lines:
        path.write_text("".join(kept), encoding="utf-8", newline="")
    return moved


def settle_header(
    path: Path,
    columns: tuple[str, ...],
    read: Callable[[dict[str, str]], dict[str, str]],
    *,
    carried: Collection[str] = (),
) -> tuple[int, list[str]]:
    """Fold a file carrying more than one header back onto one. Never raises.

    The scan `migrate_header` stopped doing, moved to the one place that can see
    what it is looking for. `state/**/*.csv` is `merge=union`, which resolves one
    physical line at a time: two runs appending different rows merge correctly,
    and two runs appending under different headings leave both header blocks in
    the file while git calls the merge clean. Measured on this repository
    2026-09-15, `state/item-health/2026/09/14.csv` held 394 rows under the
    current header and 71 under the one before it.

    A merge is the only thing that can make that shape, so this runs after the
    merge, over the files this run wrote. A row whose width does not match its
    own header block is repaired here too: the contract's reader fills what a
    short row left out, and an empty cell is what an absent optional already
    means.

    **It never raises and it never drops a line.** An abort here would cost the
    run every ledger row staged beside the file it was fixing, and a line it
    cannot read is kept as it was and named in what comes back. A file it cannot
    place at all - one carrying headings this contract's reader does not know -
    is left byte-identical and reported, which is the refusal `migrate_header`
    makes and for the same reason.

    Returns how many rows were re-filed, and a complaint for each line the caller
    should print.
    """
    if not path.exists():
        return 0, []
    with path.open("r", encoding="utf-8", newline="") as handle:
        lines = handle.readlines()
    if not lines:
        return 0, []
    unplaceable = _unplaceable(lines, columns, carried)
    if unplaceable:
        return 0, [
            f"{path.name} carries {len(unplaceable)} heading(s) this build cannot place "
            f"({', '.join(unplaceable[:5])}); it was left as it was"
        ]
    kept, moved, refused = _refile(lines, columns, read)
    if kept != lines:
        path.write_text("".join(kept), encoding="utf-8", newline="")
    return moved, refused


def _append(path: Path, columns: tuple[str, ...], rows: Sequence[CsvRecord]) -> int:
    """Write every row it is handed. This path does not deduplicate, on purpose.

    `evals.writer.append` does, against its `OBSERVATION_KEY`, and the reason the
    two differ is what a row means. There a row is a measurement, so re-measuring
    an item nothing changed about has nothing new to say. Here a row is a fact
    about a run - this feed answered at this hour, this item finished - and a run
    that runs twice did happen twice. Collapsing those would turn a count of runs
    into a count of days.

    So each caller owns its own repeats, and each one is named here because the
    guarantee does not live in this file:

    - **seen** - `stages.plan.stage_plan` builds its rows from `_first_sights`, which
      subtracts what `load_seen` already holds. A sight older than the window is
      outside that subtraction, and `load_seen` keeps the earliest of two, so the
      repeat costs bytes and never moves an age.
    - **published** - `stages.assemble._published_rows` joins the day against this run's plan,
      and `rank.plan_vertical` has already dropped every address `load_published`
      returned. Measured on this checkout 2026-08-27: 2,097 rows and 2,097
      distinct addresses. `load_published` keeps the earliest date, so a repeat
      costs bytes and never moves a publication date.
    - **feed-health** - one row per feed per run. A repeat needs a run to be run
      twice under one `run_id`. Two runs cannot compute one any more - a run id
      now carries the identity of the execution that made it (`stages.plan.stage_plan`)
      - but a second attempt at the same execution still can, and this is the
      one caller whose two rows can disagree: the first attempt may have failed
      where the second succeeded. `append_health` settles the shard against
      `FEED_HEALTH_KEY` after the append, so the winner is picked by the rule in
      `contracts.feed_health.supersedes` rather than by which line landed first.
    - **item-health** - two stages write it, so it cannot rely on a caller's own
      guarantee. `append_item_health` filters against `ITEM_HEALTH_KEY` instead.
    - **runtime-counters** - one writer, but the row is a cumulative total rather
      than an event, so a re-run of a failed shard would make a run-level sum
      count that shard twice. `append_runtime_counters` filters against
      `RUNTIME_COUNTERS_KEY`.

    Both filters read the file the job checked out, which is frozen at the
    commit its run was triggered at, so neither can see a row a second attempt
    pushed afterwards. `drop_repeated_rows` settles that after the merge.

    **It takes contracts and renders them here.** A `dict[str, str]` is not a
    contract: anything can build one, nothing validates it, and a caller that
    assembled the cells by hand would reach a committed file without a model ever
    having seen them. Taking the row itself puts every `state/` file behind its
    own contract, and the rendering happens once, in this function, rather than
    at each of the nine call sites.
    """
    if not rows:
        return 0
    payloads = [row.csv_row() for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    if exists:
        require_matching_header(path, columns)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        if not exists:
            writer.writeheader()
        for payload in payloads:
            writer.writerow({name: payload[name] for name in columns})
    return len(payloads)


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _stream_rows(path: Path) -> Iterator[dict[str, str]]:
    """Row by row, for a reader that reduces rather than keeps.

    `_read_rows` materialises the whole file first, which costs the caller its
    entire size in peak memory before the first row is looked at. Measured
    2026-09-07 on an Intel Core i7-1265U over the flat `state/published.csv`
    this ledger has since moved off: 500.9 B of peak per row against a stored
    row of 106.9 B. A reduction never needs the list, so it should not pay for
    one.
    """
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def append_seen(state_dir: Path, date: str, rows: Iterable[SeenRow]) -> int:
    """Append first sights. Returns how many landed, so a caller can log the count."""
    return _append(seen_path(state_dir, date), SeenRow.csv_columns(), list(rows))


def append_published(state_dir: Path, date: str, rows: Iterable[PublishedRow]) -> int:
    """Append what a committed digest actually carried, into that day's own file.

    The caller hands the date, so the caller decides: a date inside a day that
    has already closed performs a correction to that day, which is the one
    rewrite the freeze rule permits and the same choice `append_seen` gives its
    caller. See `docs/concepts/partitions.md`.
    """
    return _append(published_path(state_dir, date), PublishedRow.csv_columns(), list(rows))


def load_seen(state_dir: Path, *, today: str, within_days: int) -> dict[str, str]:
    """Address -> the timestamp we first saw it, over the window only.

    Older days stay committed and stay readable; they are simply not consulted,
    because an address first seen four months ago is not evidence about today.
    The earliest sight wins when two days disagree, which is what "first" means.

    `day_partition.days_in_window` names both ends, so a cover of `n` days opens
    at most `n + 1` files and reads exactly those days - where the month shards
    it replaced could hold up to 120 days of rows behind a 90-day cover. A day
    the ledger never recorded has no file, which is not a fault: a run that met
    no new address that day wrote nothing that day.
    """
    first_seen: dict[str, str] = {}
    for day in day_partition.days_in_window(today, within_days):
        for row in _read_rows(seen_path(state_dir, day)):
            url_key, at = row["url_key"], row["first_seen_at"]
            if url_key not in first_seen or at < first_seen[url_key]:
                first_seen[url_key] = at
    return first_seen


def load_published(state_dir: Path, *, today: str | None, within_days: int) -> dict[str, str]:
    """Address -> the digest date it ran on, over the cover the config sets.

    `within_days` is `collect.published_window_days`. The committed config sets
    it to `UNBOUNDED_WINDOW`, so the shipping answer is every address ever
    published - the guarantee the guard has always given. Two paths, because the
    two questions are not the same question:

    - **Unbounded.** Walk `state/published/`, naming every entry it meets and
      refusing one it cannot place. `today` is not read on this path, and a
      caller with no cover passes `None` to say so.
    - **Finite.** Ask for the dates in range and open those files and no others.
      A day outside the cover is never opened, so an address only that day holds
      is forgotten and can be planned again. That is the point of a cover, and
      it is why `CollectConfig` refuses a value that is not wider than
      `collect.seen_window_days`.

    Neither path globs. The unbounded one has to account for every file it
    finds, and the bounded one only opens files it named itself. A named day
    with nothing published has no file, which is not a fault - a run that
    published nothing that day wrote nothing that day.

    Streamed rather than materialised, because this is the read over the ledger
    with no natural bound - so its peak would otherwise be the whole tree, and
    the tree is what grows. Only the day paths are listed, and a day is a file
    rather than a row.
    """
    if within_days == UNBOUNDED_WINDOW:
        paths: Iterable[Path] = day_partition.day_files(state_dir / PUBLISHED_DIRNAME)
    elif today is None:
        raise ValueError(
            f"a published cover of {within_days} days needs the day it is anchored on. "
            f"Pass today, or {UNBOUNDED_WINDOW} to read every day file."
        )
    else:
        paths = (
            published_path(state_dir, on)
            for on in day_partition.days_in_window(today, within_days)
        )

    published: dict[str, str] = {}
    for path in paths:
        for row in _stream_rows(path):
            url_key, on = row["url_key"], row["published_on"]
            if url_key not in published or on < published[url_key]:
                published[url_key] = on
    return published


def load_settled_failures(state_dir: Path, date: str, *, codes: Collection[str]) -> set[str]:
    """Addresses that failed today for a reason today cannot change.

    The published ledger stops a repeat of a *success*. It cannot stop a repeat
    of a failure, because a failure is never published - so every later run of
    the same day planned the same paywall again and got the same paywall.
    Measured over 2026-08-24 to 2026-08-29, 403 such repeats bought 2 items.

    Only `date` is read, and only the codes the caller names. A rate limit or a
    reset connection is a different answer at 18:20 than it was at 02:20, so
    those codes are left out of the config list and their addresses come back.

    An empty `codes` returns nothing, which is exactly the behaviour this
    replaced - a run configured that way plans a failed address again.
    """
    if not codes:
        return set()
    wanted = set(codes)
    return {
        row["url_key"]
        for row in _read_rows(item_health_path(state_dir, date))
        if row["date"] == date and row["outcome"] != ItemOutcome.OK and row["code"] in wanted
    }


def load_source_counts(state_dir: Path, date: str) -> dict[str, int]:
    """Feed -> how many of today's items it has already put in front of a reader.

    The count a day-wide source ceiling reads. Only rows that reached the
    digest are counted: a feed whose page was behind a paywall spent a slot,
    but it did not fill any of the day, and the ceiling is about what a reader
    sees.

    Keyed on the address rather than the row, because one item settles once but
    can be written by more than one job, and a re-run of the same day writes it
    again. Counting rows would charge a feed twice for one story.
    """
    carried: dict[str, str] = {}
    for row in _read_rows(item_health_path(state_dir, date)):
        if row["date"] != date or row["outcome"] != ItemOutcome.OK:
            continue
        carried[row["url_key"]] = row["source_id"]
    counts: dict[str, int] = {}
    for source_id in carried.values():
        counts[source_id] = counts.get(source_id, 0) + 1
    return counts


def append_health(state_dir: Path, date: str, rows: Iterable[FeedHealthRow]) -> int:
    """Append this run's verdict on every feed it tried, one verdict per feed.

    Settled against `FEED_HEALTH_KEY` straight after the write rather than
    filtered before it, because this is the one ledger here where the row
    arriving second can be the better account: a second attempt at a run that
    failed the first time is exactly the case worth keeping. Filtering first
    would throw the recovery away and leave the failure on record.

    Returns how many rows the shard gained, so a caller can log the count. A row
    that only replaced an earlier account of the same event is not a gain.
    """
    path = health_path(state_dir, date)
    landed = _append(path, FeedHealthRow.csv_columns(), list(rows))
    return landed - drop_repeated_rows(path, FEED_HEALTH_KEY)

def _as_item_health_row(raw: dict[str, str]) -> dict[str, str]:
    """The contract's own reader, used as a row-to-row migration."""
    return refiler(ItemHealthRow)(raw)


#: The headings a day file an earlier run wrote still carries that the current
#: row no longer names. `from_csv_row` reads each one into the column that
#: replaced it, so a file carrying them is still a file this build can re-file.
ITEM_HEALTH_CARRIED: Final[frozenset[str]] = frozenset(RETIRED_CELLS)


def _header_and_keys(
    path: Path, key: tuple[str, ...]
) -> tuple[tuple[str, ...], set[tuple[str, ...]]]:
    """The file's own header and every record it already holds, in one pass.

    One `csv.reader` rather than a `DictReader`, and one open rather than two.
    `DictReader` builds a dict of every column for each row, which is 113 keys on
    an item-health shard to read three cells; the positions are taken off the
    header once and the cells are read by index after that.

    A file with no header, or one that does not name every cell of `key`, holds
    no record this key can match - which is what a day with no history has.
    """
    if not path.exists():
        return (), set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = tuple(next(reader, []))
        if any(name not in header for name in key):
            return header, set()
        at = [header.index(name) for name in key]
        widest = max(at)
        return header, {
            tuple(cells[index] for index in at) for cells in reader if len(cells) > widest
        }


def append_item_health(state_dir: Path, date: str, rows: Iterable[ItemHealthRow]) -> int:
    """Append this run's verdict on every planned item it has not already recorded.

    The only ledger here that filters, because it is the only one with two
    writers. The `work` job commits a row the moment its item settles, so the
    rows survive a run that dies before it publishes; `stage_assemble` then
    writes the whole day's census, which covers the same items again. A repeat is
    not free: `public_telemetry` copies every row into the file the console
    reads, so one duplicated row is one item counted twice on the dashboard.

    `merge=union` on the shard cannot help - it keeps the lines from both sides,
    which is right for two runs appending different rows and exactly wrong for
    two writers appending the same one. The filter runs before the write, on the
    committed file each writer can see.

    **The day file is read once.** That one pass answers both questions this
    needs - which header the file carries, and which items it already records -
    and the header answer is what says whether the rare second branch is needed
    at all. `migrate_header` re-files the file when it was written under a
    different generation of this row; it is the one contract here that has
    retired a heading, so it is the one whose day file can arrive carrying a
    generation this writer does not name.

    Returns how many landed, so a caller can log the count.
    """
    path = item_health_path(state_dir, date)
    columns = ItemHealthRow.csv_columns()
    header, already = _header_and_keys(path, ITEM_HEALTH_KEY)
    if header and header != columns:
        migrate_header(path, columns, _as_item_health_row, carried=ITEM_HEALTH_CARRIED)
        _, already = _header_and_keys(path, ITEM_HEALTH_KEY)
    landing = []
    for row in rows:
        key = _key_of(row, ITEM_HEALTH_KEY)
        if key in already:
            continue
        already.add(key)
        landing.append(row)
    return _append(path, columns, landing)


def recorded_item_health(path: Path) -> set[tuple[str, ...]]:
    """Every planned item this day's file already has a verdict for.

    A missing file is a day with no history, which is what the first run of a
    day has.
    """
    return _header_and_keys(path, ITEM_HEALTH_KEY)[1]


def append_retirements(state_dir: Path, rows: Iterable[FeedRetirementRow]) -> int:
    """Append the addresses this run decided are permanently gone.

    Settled against `FEED_RETIREMENT_KEY` straight after the write, the way
    `append_health` is, because the two runs that can write one address are two
    stale checkouts rather than two decisions: each reads the same five `410`
    results, each files the same row, and `merge=union` keeps both lines. The
    first row wins - there is nothing for a preference rule to choose between,
    because a retirement is permanent and a second row for one address says
    nothing the first did not.

    Returns how many rows the file gained, so a caller can log the count. A row
    that only repeated one already on record is not a gain.
    """
    path = feed_retirements_path(state_dir)
    landed = _append(path, FeedRetirementRow.csv_columns(), list(rows))
    return landed - drop_repeated_rows(path, FEED_RETIREMENT_KEY)


def load_retirements(state_dir: Path) -> list[FeedRetirementRow]:
    """Every retired address, in file order. Never windowed: retirement is forever.

    A row that no longer parses is skipped rather than fatal, and the direction
    of that failure is the safe one: an unreadable retirement costs one request
    to an address that is probably still gone, and the next run reads the same
    evidence and files it again. Refusing to start would cost the reader the day.

    Cover: -1, unbounded on purpose. A retirement is permanent, so any cover in
    days would forget the oldest ones and the run would ask a dead server again.
    """
    rows: list[FeedRetirementRow] = []
    for raw in _read_rows(feed_retirements_path(state_dir)):
        try:
            rows.append(FeedRetirementRow.from_csv_row(raw))
        except (KeyError, ValueError):
            continue
    return rows


def append_runtime_counters(state_dir: Path, rows: Iterable[RuntimeCountersRow]) -> int:
    """Append what each job's model server counted. Never windowed.

    Filters against `RUNTIME_COUNTERS_KEY` because the cells are cumulative
    totals rather than events: a second row for a shard is not a second fact, it
    is the same shard's tokens added to themselves by whatever pools the run.

    Returns how many landed, so a caller can log the count.
    """
    path = runtime_counters_path(state_dir)
    already = recorded_runtime_counters(path)
    landing = []
    for row in rows:
        key = _key_of(row, RUNTIME_COUNTERS_KEY)
        if key in already:
            continue
        already.add(key)
        landing.append(row)
    return _append(path, RuntimeCountersRow.csv_columns(), landing)


def recorded_runtime_counters(path: Path) -> set[tuple[str, ...]]:
    """Every shard the file already carries a snapshot for."""
    return {tuple(row[name] for name in RUNTIME_COUNTERS_KEY) for row in _read_rows(path)}


def append_host_fingerprint(state_dir: Path, date: str, rows: Iterable[HostFingerprintRow]) -> int:
    """Append what machine each job drew. One row a job, so a re-read is not a second fact.

    Filters on the same key as the counter snapshot: a job runs on one machine,
    so a second row for that job is the same machine written twice, and counting
    a fingerprint twice is exactly what would make the distribution lie.

    Returns how many landed, so a caller can log the count.
    """
    path = host_fingerprint_path(state_dir, date)
    _, already = _header_and_keys(path, HOST_FINGERPRINT_KEY)
    landing = []
    for row in rows:
        key = _key_of(row, HOST_FINGERPRINT_KEY)
        if key in already:
            continue
        already.add(key)
        landing.append(row)
    return _append(path, HostFingerprintRow.csv_columns(), landing)


def append_span_rollup(state_dir: Path, date: str, rows: Iterable[SpanRollupRow]) -> int:
    """Append one shard's folded span counts to the month shard. Never windowed here.

    Filters against `SPAN_ROLLUP_KEY` the way `append_runtime_counters` does. The
    row is a fold of a shard's spans, so a re-run of a failed shard recomputes the
    same numbers and a second row would double a count rather than add a fact. The
    first row wins.

    Returns how many landed, so a caller can log the count.
    """
    path = span_rollup_path(state_dir, date[:7])
    already = recorded_span_rollup(path)
    landing = []
    for row in rows:
        key = _key_of(row, SPAN_ROLLUP_KEY)
        if key in already:
            continue
        already.add(key)
        landing.append(row)
    return _append(path, SpanRollupRow.csv_columns(), landing)


def recorded_span_rollup(path: Path) -> set[tuple[str, ...]]:
    """Every (date, run, shard, span) the month's shard already carries a fold for."""
    return {tuple(row[name] for name in SPAN_ROLLUP_KEY) for row in _read_rows(path)}


def append_visual_prunes(state_dir: Path, date: str, rows: Iterable[VisualPruneRow]) -> int:
    """Append what each cleanup pass found and took, into that day's own file.

    The caller hands the date, the way `append_published` takes one and for the
    same reason: the caller decides which day a pass belongs to, and a pass run
    against a date that has already closed writes its row there.

    Settled against `VISUAL_PRUNE_KEY` straight after the write, the way
    `append_retirements` is, because the two writers that can produce one key are
    two attempts at one execution rather than two cleanups. Each walks the same
    tree and reports the same counts, so the first row wins and there is nothing
    to choose between them. Settling the day file is enough: the key opens with
    `date`, so a repeat can only ever be inside the one day's file.

    Returns how many rows the file gained, so a caller can log the count.
    """
    path = visual_prunes_path(state_dir, date)
    landed = _append(path, VisualPruneRow.csv_columns(), list(rows))
    return landed - drop_repeated_rows(path, VISUAL_PRUNE_KEY)


def append_counterfactual_scores(
    state_dir: Path, date: str, rows: Iterable[CounterfactualScoreRow]
) -> int:
    """Append a run's two-scores-per-candidate rows into that day's own file.

    Settled against `COUNTERFACTUAL_SCORE_KEY` straight after the write, the way
    `append_visual_prunes` is and for the same reason: the only writer that can
    produce one key twice is a second attempt at one execution, and both
    attempts scored the same candidates against the same committed weights. The
    first row wins and there is nothing to choose between them.

    **The day file is created even when the run has no rows for it.** `_append`
    writes nothing for an empty list, which is right everywhere else and wrong
    here: the plan job's commit step names this directory, `git add` runs under
    `set -euo pipefail`, and a path missing from the working tree aborts the
    whole step and costs the three ledgers committed beside it. A header with no
    rows under it is also the honest record - the run scored nothing worth
    asking about, which is a different statement from the run not having run.

    Returns how many rows the file gained, so a caller can log the count.
    """
    path = counterfactual_scores_path(state_dir, date)
    columns = CounterfactualScoreRow.csv_columns()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(",".join(columns) + "\n", encoding="utf-8", newline="")
    landed = _append(path, columns, list(rows))
    return landed - drop_repeated_rows(path, COUNTERFACTUAL_SCORE_KEY)


def load_visual_prunes(state_dir: Path) -> list[VisualPruneRow]:
    """Every cleanup pass on record, oldest day first. Never windowed.

    The question is whether the backlog is shrinking, which is about the whole
    series - so this opens every day file the tree holds and the layout saves it
    nothing. That is the trade `visual_prunes_path` states.

    A row that no longer parses is skipped rather than fatal, for the reason
    `load_retirements` gives: this ledger is a report, and refusing to start
    because an old report cannot be read would cost a reader the day. A file the
    walk cannot place is a different thing and still stops the read - a report
    that quietly drops a day is a report of the wrong series.
    """
    rows: list[VisualPruneRow] = []
    for path in day_partition.day_files(state_dir / VISUAL_PRUNES_DIRNAME):
        for raw in _read_rows(path):
            try:
                rows.append(VisualPruneRow.from_csv_row(raw))
            except (KeyError, ValueError):
                continue
    return rows


def keyed_paths(state_dir: Path, *, date: str | None) -> list[KeyedLedger]:
    """Every ledger here that says what makes two of its rows the same record.

    Each one arrives with its key AND with the contract that can read one of its
    rows, because the post-merge settlement needs both: it drops a repeated key
    and it folds a file that came back from the merge carrying two headers, and
    the second of those is a job only the contract's own reader can do.

    `date` says which files. A run appends only to the shard its own date routes
    to, so a repeat the union merge left behind can only be in a file that run
    wrote - and every dated ledger here contributes one file whatever the archive
    holds. `date=None` is the operator's full pass and names every file; it is
    the only cover that costs more every day, and Guardrail #12 is why a person
    has to ask for it by name.

    Nothing here is a clock. An older day is skipped because this run did not
    write it, not because it is old, so the bound does not weaken as a run gets
    slower or crosses midnight.

    The two flat ledgers are named on both covers. They are one file each, so
    settling them costs the same on a fresh clone and on a five-year archive.

    `state/seen/` is the one that is deliberately absent. It has no key at all:
    `load_seen` folds a second sight by keeping the earliest, so a repeat costs
    bytes and never moves an age.

    `state/feed-health/` was absent too until 2026-09-02, on the reading that two
    runs are entitled to write a verdict each. They are - and they get different
    run ids, so they never repeat this key. What repeats it is one run written
    down twice, which is one event with two accounts (`FEED_HEALTH_KEY`). It
    moved to a day tree on 2026-09-13 and the cover above did not move with it:
    a run wrote only its own day before and only its own day now, so the full
    pass names one file a recorded day where it named one a month.

    `state/feed-retirements.csv` is listed before anything writes it, because the
    settlement runs over whatever it finds and a missing file settles to nothing.
    Registering it with the shape rather than with its first writer is what stops
    two stale checkouts leaving one address retired twice.

    `state/visual-prunes/` is listed for the same reason and needs it more: the
    step that writes it commits through a call that names no settlement command,
    so the pass that settles it is a later run's, over the merged file. It moved
    to a day tree on 2026-09-08 and moved with it from the flat set to the dated
    one, which is the cover this whole docstring already describes - a run wrote
    only its own day, so only its own day can hold the repeat. What that costs is
    stated rather than implied: a repeat the last run of a day leaves behind is
    now settled by the operator's full pass rather than by tomorrow's first run.

    `state/counterfactual-scores/` joined the dated cover on 2026-09-14. Its
    writer is the plan stage, whose commit step DOES name a settlement command,
    so its repeats are settled by the run that made them - the same position
    `state/feed-health/` is in.

    `state/host-fingerprint/` and `state/span-rollup/` joined on 2026-09-16, and
    they were absent for the same reason rather than for a reason of their own:
    nothing staged the fingerprint at all, so there was no committed file for a
    repeat to be in, and the rollup was staged on 2026-09-15 without anyone
    walking this list. Both declare a key and both are written by a work shard,
    whose commit step names a settlement command - so a second attempt at one
    shard is settled by the run that made it, the same position
    `state/feed-health/` is in. Neither key can disagree with itself: a job runs
    on one machine, and a re-run of a shard folds the same spans again.

    `state/span-rollup/` is the one month file in the set, so the full pass names
    one file a recorded month where every dated entry beside it names one a day.
    The run's own cover is a month file too, and it is still one file: a run
    appends under one date, and one date is in one month.
    """
    flat: list[KeyedLedger] = [
        KeyedLedger(runtime_counters_path(state_dir), RUNTIME_COUNTERS_KEY, RuntimeCountersRow),
        KeyedLedger(feed_retirements_path(state_dir), FEED_RETIREMENT_KEY, FeedRetirementRow),
    ]
    if date is not None:
        return [
            *flat,
            KeyedLedger(visual_prunes_path(state_dir, date), VISUAL_PRUNE_KEY, VisualPruneRow),
            KeyedLedger(
                counterfactual_scores_path(state_dir, date),
                COUNTERFACTUAL_SCORE_KEY,
                CounterfactualScoreRow,
            ),
            KeyedLedger(health_path(state_dir, date), FEED_HEALTH_KEY, FeedHealthRow),
            KeyedLedger(
                item_health_path(state_dir, date),
                ITEM_HEALTH_KEY,
                ItemHealthRow,
                ITEM_HEALTH_CARRIED,
            ),
            KeyedLedger(
                host_fingerprint_path(state_dir, date),
                HOST_FINGERPRINT_KEY,
                HostFingerprintRow,
            ),
            KeyedLedger(
                span_rollup_path(state_dir, date[:7]), SPAN_ROLLUP_KEY, SpanRollupRow
            ),
        ]
    return [
        *flat,
        *(
            KeyedLedger(path, VISUAL_PRUNE_KEY, VisualPruneRow)
            for path in day_partition.day_files(state_dir / VISUAL_PRUNES_DIRNAME)
        ),
        *(
            KeyedLedger(path, COUNTERFACTUAL_SCORE_KEY, CounterfactualScoreRow)
            for path in day_partition.day_files(state_dir / COUNTERFACTUAL_SCORES_DIRNAME)
        ),
        *(
            KeyedLedger(path, FEED_HEALTH_KEY, FeedHealthRow)
            for path in day_partition.day_files(state_dir / HEALTH_DIRNAME)
        ),
        *(
            KeyedLedger(path, ITEM_HEALTH_KEY, ItemHealthRow, ITEM_HEALTH_CARRIED)
            for path in day_partition.day_files(state_dir / ITEM_HEALTH_DIRNAME)
        ),
        *(
            KeyedLedger(path, HOST_FINGERPRINT_KEY, HostFingerprintRow)
            for path in day_partition.day_files(state_dir / HOST_FINGERPRINT_DIRNAME)
        ),
        *(
            KeyedLedger(path, SPAN_ROLLUP_KEY, SpanRollupRow)
            for path in month_partition.month_files(state_dir / SPAN_ROLLUP_DIRNAME, ".csv")
        ),
    ]


def drop_repeated_rows(path: Path, key: tuple[str, ...]) -> int:
    """Rewrite the file without any row repeating a key an earlier row holds.

    This is the half of the guarantee `_append`'s filter cannot give. That filter
    reads the committed file the job checked out, and `actions/checkout` pins a
    job to the commit its run was triggered at - so a second execution of the
    same work cannot see rows the first one pushed after that commit. Its append
    lands them again, and `merge=union` then concatenates both sides line by
    line, which is the right answer for two runs writing different rows and
    exactly the wrong one for two attempts writing the same row. Measured on this
    repository 2026-08-31: run `2026-08-29-3` holds six counter rows for four
    shards and 44 repeated `(date, run_id, item_id)` item-health keys.

    So the file has to be settled once more after the merge, which is the only
    moment both sides have ever been in one place.

    Rows are matched and rewritten as whole lines rather than re-serialized, so
    a kept row is byte-identical to the row that was read and a pass that drops
    nothing leaves no diff. Reading by line is safe for the same reason the merge
    is: every free-text cell in these contracts is pinned to printable ASCII on
    one line, so no cell can carry a newline.

    The first row wins unless the key declares otherwise in `_PREFERENCES`. Only
    `FEED_HEALTH_KEY` does, because it is the only key here whose repeats can
    disagree: two attempts at one run really did read the address twice and may
    have got different answers. Everywhere else a repeat is one attempt written
    down twice, so the rows agree and picking between them would be theatre.
    The rule travels with the key rather than with the caller, so the workflow
    step, the CLI stage and a test harness that spells the key out all settle the
    same file the same way.

    Returns how many rows were dropped, so a caller can log the count.
    """
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        lines = handle.readlines()
    if not lines:
        return 0
    header = next(csv.reader(lines[:1]), [])
    if any(name not in header for name in key):
        # A shard written before the key existed cannot be checked against it,
        # and refusing would cost a run its whole commit over an old file.
        return 0
    prefer = _PREFERENCES.get(key)
    columns = [header.index(name) for name in key]
    seen: dict[tuple[str, ...], tuple[int, dict[str, str]]] = {}
    kept = [lines[0]]
    dropped = 0
    for line in lines[1:]:
        cells = next(csv.reader([line]), [])
        if len(cells) <= max(columns):
            kept.append(line)
            continue
        found = tuple(cells[index] for index in columns)
        held = seen.get(found)
        if held is not None:
            dropped += 1
            if prefer is not None:
                where, incumbent = held
                challenger = dict(zip(header, cells, strict=False))
                if prefer(challenger, incumbent):
                    kept[where] = line
                    seen[found] = (where, challenger)
            continue
        seen[found] = (len(kept), dict(zip(header, cells, strict=False)))
        kept.append(line)
    if dropped:
        path.write_text("".join(kept), encoding="utf-8", newline="")
    return dropped


def repeated_keys(path: Path, key: tuple[str, ...]) -> dict[tuple[str, ...], int]:
    """Every key the file holds more than one row for, and how many. Empty is clean."""
    counts: dict[tuple[str, ...], int] = {}
    for row in _read_rows(path):
        if any(name not in row for name in key):
            continue
        found = tuple(row[name] or "" for name in key)
        counts[found] = counts.get(found, 0) + 1
    return {found: count for found, count in counts.items() if count > 1}


def load_item_health_shard(path: Path) -> list[ItemHealthRow]:
    """Every row of one full-grain partition. Empty for a day never written."""
    return [ItemHealthRow.from_csv_row(row) for row in _read_rows(path)]


def load_span_rollup_shard(path: Path) -> list[SpanRollupRow]:
    """Every row of one month's span rollup. Empty for a month never written.

    A month rather than a day, because that is the grain the rollup is sharded
    at. A caller asking about one date filters on `date` after reading.
    """
    return [SpanRollupRow.from_csv_row(row) for row in _read_rows(path)]


def load_item_health(state_dir: Path, *, today: str, within_days: int) -> list[ItemHealthRow]:
    """Every item-health row in the window, oldest day first.

    Bounded for the same reason `load_health` is (Guardrail #12): this is the
    fastest-growing ledger in the repository and a run appends to it five times
    a day, so a reader that walked every partition would cost more every run for
    an answer about the last few weeks. `day_partition.days_in_window` names both
    ends, so a cover of `n` days opens at most `n + 1` files and reads exactly
    those days - where the month shards it replaced could hold up to 120 days of
    rows behind a 90-day cover.

    A day the ledger never recorded has no file, which is not a fault: a run that
    planned nothing that day wrote nothing that day.

    A row that no longer parses is fatal here rather than skipped, which is the
    opposite of `load_health` and deliberate: a census divides by these rows, so
    a silently dropped one moves a ratio instead of costing a decision some
    evidence.
    """
    rows: list[ItemHealthRow] = []
    for day in reversed(day_partition.days_in_window(today, within_days)):
        rows.extend(load_item_health_shard(item_health_path(state_dir, day)))
    return rows


def write_telemetry_aggregate(path: Path, rows: list[TelemetryAggregateRow]) -> int:
    """Write one month's folded summary whole, replacing whatever was there.

    The only writer here that rewrites rather than appends, and the reason is
    that this file is derived: every row is a function of the shard it was folded
    from, so writing it twice writes the same bytes twice. Appending would double
    a month whenever the fold ran again over a shard a lost race had restored,
    and `merge=union` could not tell the copy from the original.

    Returns how many rows landed, so a caller can log the count.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = TelemetryAggregateRow.csv_columns()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.csv_row())
    return len(rows)


def load_telemetry_aggregate(path: Path) -> list[TelemetryAggregateRow]:
    """Every folded row of one month. Empty for a month never folded."""
    return [TelemetryAggregateRow.from_csv_row(row) for row in _read_rows(path)]


def load_runtime_counters(state_dir: Path, *, run_id: str) -> list[RuntimeCountersRow]:
    """Every shard's snapshot for one run, in shard order.

    One run at a time, because the question this file answers is about one run.
    A caller that wants a trend reads several runs and says so.

    Cover: one run. Bounded by construction rather than by a clock - a run id
    already names its date, so the answer is a handful of shard rows however
    long the file gets. Streamed rather than materialised, so the read costs
    that answer instead of the file.

    Nothing is partitioned, and that is the point: a declared cover can be one
    run. Measured 2026-09-08: 209 rows over 12 days in 35,950 B, gaining 20 rows
    on each of the last eight days, so a layout over it would buy an answer the
    cover already gives (Guardrail #12).
    """
    rows = [
        RuntimeCountersRow.from_csv_row(row)
        for row in _stream_rows(runtime_counters_path(state_dir))
        if row["run_id"] == run_id
    ]
    return sorted(rows, key=lambda row: (row.job, row.shard))


def load_health(state_dir: Path, *, today: str, within_days: int) -> list[FeedHealthRow]:
    """Every health row in the window, oldest run first.

    Sorted by run rather than by file order so a caller can talk about "the last
    N runs" without knowing that the file is append-ordered - which it is today,
    and which a rebased CI push could stop being tomorrow.

    A row that no longer parses is skipped rather than fatal. This ledger is
    diagnostic: losing a stale row costs a quarantine decision some evidence,
    and refusing to start costs the reader the whole day.

    `day_partition.days_in_window` names both ends, so a cover of `n` days opens
    at most `n + 1` files and reads exactly those days - where the month shards
    it replaced could hold up to 62 days of rows behind a 31-day cover. A day the
    ledger never recorded has no file, which is not a fault.
    """
    rows: list[FeedHealthRow] = []
    for day in reversed(day_partition.days_in_window(today, within_days)):
        for raw in _read_rows(health_path(state_dir, day)):
            try:
                rows.append(FeedHealthRow.from_csv_row(raw))
            except (KeyError, ValueError):
                continue
    rows.sort(key=lambda row: (row.date, _run_n(row.run_id)))
    return rows


def _run_n(run_id: str) -> int:
    """The execution number out of `<date>-<execution>`, so a later run sorts last.

    The trailing field is the GitHub run id on anything CI produced and a small
    ordinal on anything a developer machine did, and both increase with time, so
    the sort is chronological across the change and on either side of it.
    """
    return int(run_id.rsplit("-", 1)[1])


def feed_reliability(rows: Iterable[FeedHealthRow], *, floor: float) -> float:
    """How often one feed's reads carried entries, over the rows given.

    Evidence-bearing is every read that did not preserve the streak, so a rest
    and a robots answer are set aside - neither asked the feed whether it works.
    Everything else counts: a read that came back with entries, a read that
    parsed to nothing, and an address we could not reach. Productive is the read
    that came back with entries. The reliability is productive over
    evidence-bearing, clamped so it never rises above 1.0 and never falls below
    `floor`. A feed with no evidence-bearing read in the window scores 1.0 -
    unknown is not the same as bad, and a rested or politely-refused feed is not
    penalised for being asked to wait.
    """
    evidence = [row for row in rows if not row.preserves]
    if not evidence:
        return 1.0
    productive = sum(1 for row in evidence if row.answered)
    return max(floor, min(1.0, productive / len(evidence)))


def reliability(state_dir: Path, *, today: str, within_days: int, floor: float) -> dict[str, float]:
    """Each feed's reliability over the trailing window, keyed by feed id.

    Reads the same health shards `load_health` reads, groups them by feed, and
    reduces each feed's rows through `feed_reliability`. The read is bounded by
    `within_days` (Guardrail #12): it is the feeds' recent record, never the whole
    ledger. A feed absent from the map had no evidence-bearing read in the
    window, so a caller reads a miss as 1.0.
    """
    grouped: dict[str, list[FeedHealthRow]] = {}
    for row in load_health(state_dir, today=today, within_days=within_days):
        grouped.setdefault(row.feed_id, []).append(row)
    return {feed_id: feed_reliability(rows, floor=floor) for feed_id, rows in grouped.items()}
