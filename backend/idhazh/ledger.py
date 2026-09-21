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
`docs/reference/pipeline-cost.md`.

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

`state/telemetry-aggregate/<YYYY-MM>.csv` is what is left of an item-health
month once `observability.item_health_full_grain_months` has passed: one row per
(date, stage), folded by `retention.compact_month`. It files by month because it
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
record is one `rm` rather than an edit inside a shared file, which an
append-only ledger cannot express. Five rows a day for ever is a collection that grows, and a
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
import os
import re
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from datetime import date as date_type
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final, NamedTuple, Protocol

from idhazh import day_partition, month_partition
from idhazh.contracts.base import RUN_ID_PATTERN, ServerJob
from idhazh.contracts.council_shard_outcome import CouncilShardOutcome
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, supersedes
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import (
    DROPPED_CELLS,
    RETIRED_CELLS,
    ItemHealthRow,
    ItemOutcome,
)
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.observation_index import ObservationIndexRow
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow
from idhazh.contracts.validation_row import ValidationRow
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

#: What a qualification dispatch leaves behind. It sat at the top of `state/` as
#: `validation-<date>.csv` until 2026-09-18, built off the repository root, so no
#: config could move it and a trial run wrote production state.
VALIDATION_DIRNAME: Final = "validation"

#: The eval ledger and the record of what is in it. Both are spelled here rather
#: than in `evals.writer`, which is where they were until 2026-09-18: the head
#: table below has to name the file a segment drains into, and `evals.writer`
#: imports this module. One definition, and the direction of the import decides
#: which end it lives at. `evals.writer` still exports its own names for them.
SCORES_DIRNAME: Final = "scores"
SCORE_INDEX_DIRNAME: Final = "score-index"

#: The council's own prefix, and the one store under it that records how a night
#: went. Nested for the reason the judge's prefix below is: everything the venue
#: writes about itself hangs off one word, so a commit step stages one prefix and
#: a reader sees the whole footprint in one place.
#:
#: Two directory levels under `state/` and no more. The day inventory globs one
#: level and two, so a third would be invisible to it and the miss would be
#: silent.
COUNCIL_DIRNAME: Final = "llm-council"
SHARD_OUTCOMES_DIRNAME: Final = "shard-outcomes"

#: The content-similarity judge's own prefix, and every store under it. The judge
#: slug is the group, so everything that judge produces hangs off one word: the
#: pairs it scored, the line fitted from them, the record those pairs are folded
#: into, the hand-marked holdout the line is measured against, how its instrument
#: behaved over a unit of work, and how the line stands against that holdout.
#: They are the judge's rather than the council's, because what a reading is
#: ABOUT decides where it is filed and never what executed it - and a reader of
#: the commit step sees the whole footprint in one prefix.
#:
#: Two directory levels and no more, for the reason the council's prefix carries:
#: the day inventory globs one level and two, so a third would be invisible to it
#: and the miss would be silent.
CONTENT_SIMILARITY_JUDGE_DIRNAME: Final = "content-similarity-judge"
JUDGE_METRICS_DIRNAME: Final = "metrics"
MERGE_LINE_HOLDOUT_SCORES_DIRNAME: Final = "merge-line-holdout-scores"
SCORED_PAIRS_DIRNAME: Final = "scored-pairs"
FITTED_THRESHOLDS_DIRNAME: Final = "fitted-thresholds"
SIMILARITY_HOLDOUT_FILENAME: Final = "holdout-pairs.csv"
SCORE_DISTRIBUTION_FILENAME: Final = "score-distribution.json"

#: Where a record goes when the inputs under it moved. It ships with a
#: `.gitkeep`, because the commit step stages this directory on every run and an
#: archive is written only on the rare day a stamp changed - `git add` on a path
#: the checkout does not hold aborts the whole step.
SCORE_ARCHIVE_DIRNAME: Final = "archive"

FEED_RETIREMENTS_FILENAME: Final = "feed-retirements.csv"

#: Where a writer puts its rows before a compaction folds them into a head. Not
#: a ledger of its own: nothing reads a segment except the compaction, and a
#: segment the compaction has read is deleted. It sits outside every ledger root
#: on purpose - a day tree refuses a name it cannot place, and a skip clause in
#: the one walk whose value is that it skips nothing is how a new writer arrives
#: unnoticed.
SEGMENTS_DIRNAME: Final = "segments"

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

#: One machine a job, so four cells identify the host a job drew.
HOST_FINGERPRINT_KEY: Final = ("date", "run_id", "job", "shard")

#: What makes two span-rollup rows the same record. One shard's fold of one span
#: name, in one run. The row is derived from the shard's spans, so a re-run of a
#: failed shard recomputes the same fold and a second row would add a count to
#: itself rather than record a new fact. The first row wins, which matches
#: `ITEM_HEALTH_KEY`: a re-run's items are skipped there too, so the two files
#: stay describing the same attempt.
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

#: What makes two fitted-line rows the same record. One run fits one line for one
#: date, so a second row under those two cells is a second attempt at one
#: execution rather than a second answer. Both attempts read the same score
#: record and walk the same counts, so the first row wins and there is nothing
#: for a preference rule to choose between.
STORY_SIMILARITY_THRESHOLD_KEY: Final = ("date", "run_id")

#: What makes two judged-pair rows the same record. `run_id` is in the key
#: because two runs of one day judge the same pair against different articles,
#: and both readings are facts worth keeping. Drop it and the settlement would
#: keep whichever landed first, which is the opposite of what a re-run means -
#: the fold picks the newest run itself, over the whole day, rather than letting
#: a line-by-line rewrite decide.
#:
#: `judged_by_run_id` is in it because `run_id` names the DIGEST run that
#: published the day, so two judging runs over one date write the identical
#: string there. Without this cell the settlement would keep the row already in
#: the checked-out file and discard every fresh verdict, while the record
#: counted the fresh ones - two descriptions of one day with nothing able to
#: tell them apart.
STORY_SIMILARITY_PAIR_KEY: Final = ("date", "run_id", "pair_key", "judged_by_run_id")

#: What makes two retirement rows the same record. The address and nothing else:
#: a retirement is permanent for one endpoint key, so a second row for it says
#: nothing the first did not. `feed_id` is deliberately absent - renaming a feed
#: in curated config must not make its dead address eligible again, and editing
#: that feed's URL already produces a different key.
FEED_RETIREMENT_KEY: Final = ("endpoint_key",)

#: What makes two council rows the same record. `judge_id` is in the key and a
#: night running two tenants is why: one council run has one run id, so tenant
#: A's unit 0 and tenant B's unit 0 on one judged date carry the same date, the
#: same run and the same unit number. Without the slug the settlement would
#: delete the second as a repeat, and the night would read as half of what it
#: was. A repeat under all four cells is a second attempt at one unit, which did
#: the same work under the same clock, so the first row wins.
COUNCIL_SHARD_OUTCOME_KEY: Final = ("date", "run_id", "judge_id", "shard")

#: What makes two eval rows the same measurement. The address says which article,
#: the digest says which words came out, and the scorer version says which
#: instrument read them. Change any one and the row is a new measurement worth
#: keeping. `item_id` is deliberately absent: it is a slot on a page, not an
#: identity. It carries no date either - re-measuring an article a year later is
#: the same measurement - so it is the one key here that settles two rows of one
#: day file and leaves the cross-day question to `evals.writer.append_segment`.
OBSERVATION_KEY: Final = ("url_key", "output_digest", "scorer_version")

#: What makes two index rows the same record. The digest is the whole row apart
#: from the stamp, so two of them say one thing twice and the fold keeps one.
OBSERVATION_INDEX_KEY: Final = ("observation_digest",)

#: What makes two validation rows the same record. One candidate, judged once,
#: by one execution. `run_id` is in the key because two dispatches of one model
#: on one day are two verdicts about two trees, and the committed ledger held
#: exactly that pair - drop it and the fold would keep whichever landed first.
#: `model_id` is in it because a dispatch judges one candidate and the golden
#: set judges several, so a date and a run alone would collapse them.
VALIDATION_KEY: Final = ("date", "run_id", "model_id")

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


def _item_health_rule(later: dict[str, str], kept: dict[str, str]) -> bool:
    """A row that names the job which ran the item beats one that does not.

    `ITEM_HEALTH_KEY` carries no `job` cell, and two jobs write a row for the
    same item: a work shard as the item settles, and assemble over the whole day
    afterwards. For an item a shard sealed a record for the two rows agree cell
    for cell (`telemetry.census_row` prefers the sealed row on both sides), so
    this decides nothing. For an item no shard sealed one, the shard's rebuild
    carries `job` and `shard` - the one moment either is known - and assemble's
    rebuild leaves both empty, because it runs once for the whole day on a
    machine that read none of the items.

    Until 2026-09-18 that was settled by arrival order: the work job committed
    first and `append_item_health` kept the first row for a key. The compaction
    reads filenames in sorted order, where `assemble` comes before `work`, so
    the order would have silently reversed. The preference says out loud what
    the order used to decide.
    """
    return bool(later.get("job")) and not kept.get("job")


#: The keys whose repeats can disagree, and how each one picks a winner.
FEED_HEALTH_RULE: Final[Preference] = _feed_health_rule
ITEM_HEALTH_RULE: Final[Preference] = _item_health_rule
_PREFERENCES: Final[dict[tuple[str, ...], Preference]] = {
    FEED_HEALTH_KEY: FEED_HEALTH_RULE,
    ITEM_HEALTH_KEY: ITEM_HEALTH_RULE,
}


def preference_for(key: tuple[str, ...]) -> Preference | None:
    """How two rows holding one key settle, where the key declares it.

    One vocabulary for the question, not two: the post-merge settlement reads
    this table and so does the compaction, so a key whose repeats can disagree
    gives the same answer whichever pass reaches it first.
    """
    return _PREFERENCES.get(key)


def seen_relpath(date: str) -> str:
    """`state/seen/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line or a manifest."""
    return f"{STATE_DIRNAME}/{SEEN_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def seen_path(state_dir: Path, date: str) -> Path:
    """The day file a run on this date appends to.

    A day rather than a month, for the reason `published_path` gives: a run
    writes one day, two runs collide on a file only when they are the same day,
    and taking a day back is one `rm` rather than an edit inside a shared shard,
    which an append-only ledger cannot express. The caller hands the run's own digest
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
    which an append-only ledger cannot express. Nothing mirrors this store into
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
    which an append-only ledger cannot express. The mirror under
    `frontend/public/telemetry/` stays monthly, because its grain follows what a
    browser fetches - see `docs/concepts/partitions.md`.
    """
    return state_dir / ITEM_HEALTH_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def host_fingerprint_relpath(date: str) -> str:
    """`state/host-fingerprint/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{HOST_FINGERPRINT_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def host_fingerprint_path(state_dir: Path, date: str) -> Path:
    """The day file this date's machines land in, written only by the compaction.

    A day rather than a flat file, for the reason `item_health_path` gives, and
    with a second reason of its own: this collection only earns its keep when
    somebody counts across it, and a day tree is the shape a bounded window can
    read (Guardrail #12).

    Ten jobs of one run each record the machine they drew, so none of them opens
    this file. Each writes its own segment and the compaction folds them in, which
    is what stops a lost push race emptying the day - `2026-09-16` is header-only
    because that is what happened.
    """
    return state_dir / HOST_FINGERPRINT_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def scores_relpath(date: str) -> str:
    """`state/scores/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{SCORES_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def scores_path(state_dir: Path, date: str) -> Path:
    """The day file one date's measurements land in, written only by the compaction.

    A day rather than a month, for the reason `published_path` gives: a run
    writes one day, two runs collide on a file only when they are the same day,
    and taking a day back is one `rm` rather than an edit inside a shared shard,
    which an append-only ledger cannot express. Nothing mirrors this store into
    `frontend/public/`.

    Two jobs of one run measure items - a work shard as each item settles, and
    assemble over the whole day afterwards - so neither opens this file. Each
    writes its own segment and the compaction folds them in, which is what stops
    a lost push race costing the rows rather than a merge.
    """
    return state_dir / SCORES_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def score_index_relpath(date: str) -> str:
    """`state/score-index/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{SCORE_INDEX_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def score_index_path(state_dir: Path, date: str) -> Path:
    """The record of what one day's measurements are, beside the rows themselves.

    The same grain as `scores_path` and filed by the same date, because
    `evals.writer.refresh_index` fills a partition with no index from the
    partition beside it - two grains in one relationship would be a mapping
    somebody maintains.
    """
    return state_dir / SCORE_INDEX_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def validation_relpath(date: str) -> str:
    """`state/validation/<YYYY>/<MM>/<DD>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{VALIDATION_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}.csv"


def validation_path(state_dir: Path, date: str) -> Path:
    """The day file this date's verdicts land in, written only by the compaction.

    A day tree rather than `validation-<date>.csv` at the top of `state/`, for
    the reason `item_health_path` gives and with one of its own: the old name was
    built from the repository root, so no config could move it and a candidate
    qualified on a trial state root still wrote the production tree.

    Two candidates can be dispatched at once and both judge the same day, so
    neither opens this file. Each writes its own segment and the compaction folds
    them in - the filename is what keeps the pair apart, and before the segment
    store nothing else did.
    """
    return state_dir / VALIDATION_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


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
    shared shard - which an append-only ledger cannot express.
    """
    return state_dir / PUBLISHED_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"


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


def scored_pairs_relpath(date: str) -> str:
    """`state/content-similarity-judge/scored-pairs/<YYYY>/<MM>/<DD>.csv`.

    POSIX, for a log line.
    """
    stem = f"{date[:4]}/{date[5:7]}/{date[8:10]}.csv"
    return f"{STATE_DIRNAME}/{CONTENT_SIMILARITY_JUDGE_DIRNAME}/{SCORED_PAIRS_DIRNAME}/{stem}"


def scored_pairs_path(state_dir: Path, date: str) -> Path:
    """The day file this date's judged pairs are appended to.

    A day, and the read asks for it as well as the writer: a fold reads one
    date's pairs and then never opens that file again, and the retention pass
    deletes by day. A month file would make the fold read weeks it has already
    counted.
    """
    root = state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / SCORED_PAIRS_DIRNAME
    return root / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def fitted_thresholds_relpath(date: str) -> str:
    """`state/content-similarity-judge/fitted-thresholds/<YYYY>/<MM>/<DD>.csv`.

    POSIX, for a log line.
    """
    stem = f"{date[:4]}/{date[5:7]}/{date[8:10]}.csv"
    return f"{STATE_DIRNAME}/{CONTENT_SIMILARITY_JUDGE_DIRNAME}/{FITTED_THRESHOLDS_DIRNAME}/{stem}"


def fitted_thresholds_path(state_dir: Path, date: str) -> Path:
    """The day file this date's runs write their fitted line into.

    A day rather than a month for the reason the cleanup record files by day:
    two runs collide on a file only when they are the same day, and a day taken
    back off the record is one `rm`. The guard's own read is the last fourteen
    rows, which `day_partition` answers by walking days backwards.
    """
    root = state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / FITTED_THRESHOLDS_DIRNAME
    return root / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def similarity_holdout_relpath() -> str:
    """`state/content-similarity-judge/holdout-pairs.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{CONTENT_SIMILARITY_JUDGE_DIRNAME}/{SIMILARITY_HOLDOUT_FILENAME}"


def similarity_holdout_path(state_dir: Path) -> Path:
    """One flat file, and the read over it carries no clock.

    A person types this file and nothing else writes it, so there is no run to
    partition by and no date a reader would ask for. It grows with how many
    pairs somebody has sat down and marked, never with the archive (Guardrail
    #12).
    """
    return state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / SIMILARITY_HOLDOUT_FILENAME


def score_distribution_path(state_dir: Path) -> Path:
    """The one score record every fit reads, whole.

    Not a ledger: it is rewritten rather than appended to, and its size is fixed
    by the band and the slot width rather than by how many days have been folded
    into it. That is the whole point - the fit reads a file of a size that never
    changes instead of sorting every pair ever judged (Guardrail #12).
    """
    return state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / SCORE_DISTRIBUTION_FILENAME


def score_distribution_archive_relpath(stamp: str) -> str:
    """`state/content-similarity-judge/archive/<stamp>.json` - POSIX, for a log line."""
    return (
        f"{STATE_DIRNAME}/{CONTENT_SIMILARITY_JUDGE_DIRNAME}/"
        f"{SCORE_ARCHIVE_DIRNAME}/{stamp}.json"
    )


def score_distribution_archive_path(state_dir: Path, stamp: str) -> Path:
    """Where the record is put down when its own stamp no longer describes the run.

    Named by the stamp rather than by a date, because the stamp is what the
    counts inside it were taken under. Two archives from one day are two
    different questions and get two files; one input moved back to what it was
    and the archive it produces is the file already there.
    """
    root = state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / SCORE_ARCHIVE_DIRNAME
    return root / f"{stamp}.json"


def council_shard_outcomes_relpath(date: str) -> str:
    """`state/llm-council/shard-outcomes/<YYYY>/<MM>/<DD>.csv` - POSIX, for a log line."""
    stem = f"{date[:4]}/{date[5:7]}/{date[8:10]}.csv"
    return f"{STATE_DIRNAME}/{COUNCIL_DIRNAME}/{SHARD_OUTCOMES_DIRNAME}/{stem}"


def council_shard_outcomes_path(state_dir: Path, date: str) -> Path:
    """The day file this date's council run records its own units of work in.

    A day rather than a month, for the two things the grain buys every ledger
    beside it: two runs collide on a file only when they are the same day, and a
    night taken back off the record is one `rm`. The council runs once a night,
    so a day file holds one night of units and nothing else.

    The date is the digest date the run judged, which is what a reader asking
    "how did the night of the 20th go" means by the question.
    """
    root = state_dir / COUNCIL_DIRNAME / SHARD_OUTCOMES_DIRNAME
    return root / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def content_similarity_judge_metrics_relpath(date: str) -> str:
    """`state/content-similarity-judge/metrics/<YYYY>/<MM>/<DD>.csv` - POSIX, for a log line."""
    stem = f"{date[:4]}/{date[5:7]}/{date[8:10]}.csv"
    return f"{STATE_DIRNAME}/{CONTENT_SIMILARITY_JUDGE_DIRNAME}/{JUDGE_METRICS_DIRNAME}/{stem}"


def content_similarity_judge_metrics_path(state_dir: Path, date: str) -> Path:
    """The day file this date's shards record their own instrument in.

    A day rather than a month, for what the grain buys every ledger beside it:
    two runs collide on a file only when they are the same day, and a night taken
    back off the record is one `rm`.

    The date is the digest date the shard judged, which is the date the council's
    own record files by - so a reader holding one night's units against one
    night's readings opens one day file in each store.
    """
    root = state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / JUDGE_METRICS_DIRNAME
    return root / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def merge_line_holdout_scores_relpath(date: str) -> str:
    """`state/content-similarity-judge/merge-line-holdout-scores/<YYYY>/<MM>/<DD>.csv`."""
    stem = f"{date[:4]}/{date[5:7]}/{date[8:10]}.csv"
    root = f"{CONTENT_SIMILARITY_JUDGE_DIRNAME}/{MERGE_LINE_HOLDOUT_SCORES_DIRNAME}"
    return f"{STATE_DIRNAME}/{root}/{stem}"


def merge_line_holdout_scores_path(state_dir: Path, date: str) -> Path:
    """The day file this date's reading of the line against the holdout goes in.

    A day for the reason the fitted line beside it files by day: a row a day, a
    read that carries a window over the newest of them, and one `rm` to take a
    day's reading back off the record.

    The date is the day the line was scored, not a day either labelled item was
    published on - the holdout row names those two dates itself.
    """
    root = state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / MERGE_LINE_HOLDOUT_SCORES_DIRNAME
    return root / date[:4] / date[5:7] / f"{date[8:10]}.csv"


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
    """One row, written the way `extend_ledger_file` writes one.

    A re-filed row and an appended row have to be the same bytes, or the file a
    migration leaves behind is a file the next append disagrees with.
    """
    buffer = io.StringIO()
    csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n").writerow(
        {name: payload[name] for name in columns}
    )
    return buffer.getvalue()


def render_file(columns: tuple[str, ...], rows: Iterable[Mapping[str, str]]) -> str:
    """A whole ledger file as one document: the header, then every row.

    Beside `_csv_line` because a head the compaction rewrites and a row an append
    adds have to be the same bytes. Written two ways, a file the compaction
    touched would read as changed line by line the next time anything diffed it.

    Returned rather than written, so the caller owns the temp-file-plus-rename
    and this module keeps its rule that a row is rendered in exactly one place.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for payload in rows:
        writer.writerow({name: payload[name] for name in columns})
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

    A file that two appends were stacked into carries two header lines, and the
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
    append, and it is complete rather than optimistic: `extend_ledger_file` writes rows into
    a file that exists and a header only into one that does not, so an append
    cannot put a second header in a file. A union merge resolve could, and every
    head under `state/` carried that driver until 2026-09-19; the files it already
    made are committed, and `stages.compact` calls this on a head before it folds
    a segment into one.

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
    what it is looking for. Every head under `state/` carried a union merge
    driver until 2026-09-19 (`.gitattributes`), and that driver resolved one
    physical line at a time: two runs appending
    different rows merge correctly, and two runs appending under different
    headings leave both header blocks in the file while git calls the merge
    clean. Measured on this repository
    2026-09-15, `state/item-health/2026/09/14.csv` held 394 rows under the
    current header and 71 under the one before it.

    Nothing can make that shape now, and the files that already hold it are
    committed - so this runs on a head before the compaction folds a segment
    into it. A row whose width does not match its
    own header block is repaired here too: the contract's reader fills what a
    short row left out, and an empty cell is what an absent optional already
    means.

    **It never raises, and it writes all of the repair or none of it.** An abort
    here would cost the run every ledger row staged beside the file it was
    fixing, so a line it cannot read comes back as a complaint instead - and the
    file is left byte-identical, because a header written over a line that did
    not move is a header that lies about its own rows, and the next append reads
    that width as the one the contract asked for. A file carrying headings this
    contract's reader does not know is left alone for the same reason.
    `migrate_header` refuses on both conditions too; it raises where this
    returns.

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
    if refused:
        return 0, refused
    if kept != lines:
        path.write_text("".join(kept), encoding="utf-8", newline="")
    return moved, refused


def extend_ledger_file(path: Path, columns: tuple[str, ...], rows: Sequence[CsvRecord]) -> int:
    """Write every row it is handed. This path does not deduplicate, on purpose.

    **Public because a caller outside this module now writes a file this module
    does not name.** The council ships a tenant's rows to a store the tenant
    names, so there is no `<store>_relpath` helper here to hang an `append_*`
    writer off - and rewriting the append beside that caller would give one
    ledger two shapes.

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
    return extend_ledger_file(seen_path(state_dir, date), SeenRow.csv_columns(), list(rows))


def append_published(state_dir: Path, date: str, rows: Iterable[PublishedRow]) -> int:
    """Append what a committed digest actually carried, into that day's own file.

    The caller hands the date, so the caller decides: a date inside a day that
    has already closed performs a correction to that day, which is the one
    rewrite the freeze rule permits and the same choice `append_seen` gives its
    caller. See `docs/concepts/partitions.md`.
    """
    return extend_ledger_file(
        published_path(state_dir, date), PublishedRow.csv_columns(), list(rows)
    )


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
    landed = extend_ledger_file(path, FeedHealthRow.csv_columns(), list(rows))
    return landed - drop_repeated_rows(path, FEED_HEALTH_KEY)

def _as_item_health_row(raw: dict[str, str]) -> dict[str, str]:
    """The contract's own reader, used as a row-to-row migration."""
    return refiler(ItemHealthRow)(raw)


#: The headings a day file an earlier run wrote still carries that the current
#: row no longer names. Two kinds, and the difference is what happens to the
#: cell: `from_csv_row` reads a RETIRED heading into the column that replaced
#: it, and a DROPPED heading has no replacement - the file still re-files, and
#: the cell goes, which is the point of dropping it.
ITEM_HEALTH_CARRIED: Final[frozenset[str]] = frozenset(RETIRED_CELLS) | DROPPED_CELLS


def _header_and_keys(
    path: Path, key: tuple[str, ...]
) -> tuple[tuple[str, ...], set[tuple[str, ...]]]:
    """The file's own header and every record it already holds, in one pass.

    One `csv.reader` rather than a `DictReader`, and one open rather than two.
    `DictReader` builds a dict of every column for each row, which is 119 keys on
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
    results and each files the same row. The settle catches the repeat inside one
    checkout; a second attempt that races its own first stops at the rebase
    rather than landing a second line. The
    first row wins - there is nothing for a preference rule to choose between,
    because a retirement is permanent and a second row for one address says
    nothing the first did not.

    Returns how many rows the file gained, so a caller can log the count. A row
    that only repeated one already on record is not a gain.
    """
    path = feed_retirements_path(state_dir)
    landed = extend_ledger_file(path, FeedRetirementRow.csv_columns(), list(rows))
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


def recorded_span_rollup(path: Path) -> set[tuple[str, ...]]:
    """Every (date, run, shard, span) the month's shard already carries a fold for.

    A reader and no longer half of a writer. A work shard folds its spans into
    its own segment and `stage_compact` merges that into the month head, so the
    question this answers is what the head already holds rather than what an
    append is about to skip.
    """
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
    landed = extend_ledger_file(path, VisualPruneRow.csv_columns(), list(rows))
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

    **The day file is created even when the run has no rows for it.**
    `extend_ledger_file`
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
    landed = extend_ledger_file(path, columns, list(rows))
    return landed - drop_repeated_rows(path, COUNTERFACTUAL_SCORE_KEY)


def append_story_similarity_pairs(
    state_dir: Path, date: str, rows: Iterable[StorySimilarityPair]
) -> int:
    """Append a day's judged pairs into that day's own file.

    Settled against `STORY_SIMILARITY_PAIR_KEY` straight after the write, the
    way `append_counterfactual_scores` is. The key carries `run_id`, so a second
    RUN of one date keeps its own rows and only a second attempt at one
    execution is collapsed - both attempts judged the same pair under the same
    prompt against the same day, so the first row wins and there is nothing to
    choose between them. Which of two runs the record counts is decided over the
    whole day when the day is folded, never line by line here.

    **The day file is created even when the day judged nothing**, for the reason
    `append_counterfactual_scores` gives: the commit step names this directory,
    `git add` runs under `set -euo pipefail`, and a path missing from the working
    tree aborts the step and costs the ledgers staged beside it.

    Returns how many rows the file gained, so a caller can log the count.
    """
    path = scored_pairs_path(state_dir, date)
    columns = StorySimilarityPair.csv_columns()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(",".join(columns) + "\n", encoding="utf-8", newline="")
    landed = extend_ledger_file(path, columns, list(rows))
    return landed - drop_repeated_rows(path, STORY_SIMILARITY_PAIR_KEY)


def load_story_similarity_pairs(state_dir: Path, date: str) -> list[StorySimilarityPair]:
    """One named day's judged pairs, and never a second file.

    **Guardrail #12 declaration, and it is the whole point of this store's
    shape.** The fold counts one date into the record and the record is then the
    only thing the fit reads, so this opens the file the date names and stops.
    It costs the same on the thousandth day as on the third whatever the tree
    holds beside it.

    A row that no longer parses stops the read rather than being skipped. A
    report may drop a day it cannot read; this is evidence being counted into a
    record that is rewritten whole, and a silently short count is a record that
    cannot be told from a quiet day.
    """
    return [
        StorySimilarityPair.from_csv_row(raw)
        for raw in _read_rows(scored_pairs_path(state_dir, date))
    ]


def append_fitted_thresholds(
    state_dir: Path, date: str, rows: Iterable[FittedSimilarityThreshold]
) -> int:
    """Append a run's fitted row into that day's own file.

    Settled against `STORY_SIMILARITY_THRESHOLD_KEY` straight after the write,
    the way `append_story_similarity_pairs` is. The key is date and run, so a
    second RUN of one date keeps its own row - two runs fitted two records and
    both are facts - and only a second attempt at one execution is collapsed.

    **The day file is created even when the fit was held**, and a held day writes
    a row like any other: a line that moves itself has to leave a record on the
    days it stayed put, or a reader cannot tell a held day from a day nothing
    ran. The empty-file half is the same reason `append_counterfactual_scores`
    gives - the commit step names this directory and a missing path aborts it
    under `set -euo pipefail`.

    Returns how many rows the file gained, so a caller can log the count.
    """
    path = fitted_thresholds_path(state_dir, date)
    columns = FittedSimilarityThreshold.csv_columns()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(",".join(columns) + "\n", encoding="utf-8", newline="")
    landed = extend_ledger_file(path, columns, list(rows))
    return landed - drop_repeated_rows(path, STORY_SIMILARITY_THRESHOLD_KEY)


def append_council_shard_outcomes(
    state_dir: Path, date: str, rows: Iterable[CouncilShardOutcome]
) -> int:
    """Append a night's recorded units of council work into that date's own file.

    Settled against `COUNCIL_SHARD_OUTCOME_KEY` straight after the write, the
    way `append_fitted_thresholds` is. A repeat under all four cells is a second
    attempt at one unit, which ran the same work under the same clock, so the
    first row wins and there is nothing to choose between them.

    **A night with no unit to record writes no file**, which is the one place
    this writer differs from the three above it. A header with no rows under it
    is a real day file to the partition walker, so an empty write here would put
    a permanent day in the prune target and the day inventory that no council
    run ever had. The store's directory is kept in the checkout by its own
    `.gitkeep`, so the staged path is there whether or not tonight wrote to it.

    Returns how many rows the file gained, so a caller can log the count.
    """
    recorded = list(rows)
    if not recorded:
        return 0
    path = council_shard_outcomes_path(state_dir, date)
    landed = extend_ledger_file(path, CouncilShardOutcome.csv_columns(), recorded)
    return landed - drop_repeated_rows(path, COUNCIL_SHARD_OUTCOME_KEY)


def load_fitted_thresholds(
    state_dir: Path, *, today: str, within_days: int
) -> list[FittedSimilarityThreshold]:
    """Every fitted row in the window, oldest day first.

    **Guardrail #12 declaration.** `day_partition.days_in_window` names both
    ends, so a cover of `n` days opens at most `n + 1` files and reads exactly
    those days. The tree is never walked, so the read costs the same on the
    thousandth day as on the third.

    **The window is in days and the guard's median is in rows, and the caller is
    what reconciles them.** One missed run leaves thirteen rows inside a
    fourteen-day cover, the median returns nothing, and a guard that silently
    never fires is worse than one that fires too readily. The fit therefore asks
    for `max(settled_window_days, step_change_window_rows * 2)` days and takes the
    newest rows it finds - a bound set by two knobs rather than by the archive.

    A day the fit never ran has no file, which is not a fault. A row that no
    longer parses stops the read rather than being skipped: the guard takes a
    median over these rows, and a silently short list moves that median instead
    of costing a decision some evidence.
    """
    rows: list[FittedSimilarityThreshold] = []
    for day in reversed(day_partition.days_in_window(today, within_days)):
        rows.extend(
            FittedSimilarityThreshold.from_csv_row(raw)
            for raw in _read_rows(fitted_thresholds_path(state_dir, day))
        )
    return rows


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


class SegmentLedger(StrEnum):
    """Which head a segment belongs to. A closed set, and that is the whole point.

    A directory under `state/segments/` naming something outside this set is a
    writer that arrived without anyone choosing it, which is the failure the
    segment store exists to stop. Every value is the head's own `*_DIRNAME`
    constant rather than a string repeated here, so the transit directory and
    the file it drains into cannot be spelled two different ways.

    A ledger joins this set in the row that moves its writer, never before it.
    """

    ITEM_HEALTH = ITEM_HEALTH_DIRNAME
    HOST_FINGERPRINT = HOST_FINGERPRINT_DIRNAME
    SPAN_ROLLUP = SPAN_ROLLUP_DIRNAME
    SCORES = SCORES_DIRNAME
    SCORE_INDEX = SCORE_INDEX_DIRNAME
    VALIDATION = VALIDATION_DIRNAME


class SegmentName(NamedTuple):
    """A segment filename read back: who wrote it, and on which try.

    `attempt` is the cell that is in the name and in no column. GitHub keeps the
    run id stable across a re-run, so without it a second attempt writes the
    path the first one took.
    """

    run_id: str
    attempt: int
    job: ServerJob
    shard: int


#: `<run_id>-<attempt>-<job>-<shard>.csv`. The run id is spelled from the
#: contract's own pattern and the jobs from the enum, so neither is a second
#: list to keep in step. `re.ASCII` because a `\\d` in a `str` pattern otherwise
#: takes another script's numerals, and `int` takes them too - the name would
#: then carry a digit no later glob matches.
_SEGMENT_NAME: Final = re.compile(
    rf"(?P<run_id>{RUN_ID_PATTERN[1:-1]})"
    r"-(?P<attempt>[0-9]+)"
    rf"-(?P<job>{'|'.join(job.value for job in ServerJob)})"
    r"-(?P<shard>[0-9]{2})",
    re.ASCII,
)

SEGMENT_SUFFIX: Final = ".csv"


class SegmentHead(NamedTuple):
    """Where one ledger's rows of one date land, and what settles two of them.

    `KeyedLedger`'s three travel together here for the same reason, plus the
    POSIX form: the compaction reports what it wrote, and a report naming an
    absolute path is a report nobody can compare between two machines
    (CLAUDE.md section 2).
    """

    path: Path
    relpath: str
    key: tuple[str, ...]
    model: type[CsvContract]
    carried: frozenset[str] = frozenset()


def _span_rollup_head(state_dir: Path, date: str) -> Path:
    return span_rollup_path(state_dir, date[:7])


def _span_rollup_head_relpath(date: str) -> str:
    return span_rollup_relpath(date[:7])


class _HeadShape(NamedTuple):
    """One ledger's answer to "which file, and what settles two of its rows"."""

    path: Callable[[Path, str], Path]
    relpath: Callable[[str], str]
    key: tuple[str, ...]
    model: type[CsvContract]
    carried: frozenset[str] = frozenset()
    dates_from_run: bool = False


#: Which file a row of a given date belongs in, per ledger. A declared table
#: rather than a rule the compaction re-derives: a month head and a day head are
#: two shapes, and which one a ledger has is a fact about the ledger.
_SEGMENT_HEADS: Final[dict[SegmentLedger, _HeadShape]] = {
    SegmentLedger.ITEM_HEALTH: _HeadShape(
        item_health_path,
        item_health_relpath,
        ITEM_HEALTH_KEY,
        ItemHealthRow,
        ITEM_HEALTH_CARRIED,
    ),
    SegmentLedger.HOST_FINGERPRINT: _HeadShape(
        host_fingerprint_path,
        host_fingerprint_relpath,
        HOST_FINGERPRINT_KEY,
        HostFingerprintRow,
    ),
    SegmentLedger.SPAN_ROLLUP: _HeadShape(
        _span_rollup_head,
        _span_rollup_head_relpath,
        SPAN_ROLLUP_KEY,
        SpanRollupRow,
    ),
    SegmentLedger.SCORES: _HeadShape(
        scores_path,
        scores_relpath,
        OBSERVATION_KEY,
        EvalRow,
    ),
    SegmentLedger.SCORE_INDEX: _HeadShape(
        score_index_path,
        score_index_relpath,
        OBSERVATION_INDEX_KEY,
        ObservationIndexRow,
        dates_from_run=True,
    ),
    SegmentLedger.VALIDATION: _HeadShape(
        validation_path,
        validation_relpath,
        VALIDATION_KEY,
        ValidationRow,
    ),
}


def segment_dates_from_run(ledger: SegmentLedger) -> bool:
    """Whether this ledger's rows are dated by the segment rather than by a cell.

    True for exactly one ledger, and the reason is a column that is not there.
    `ObservationIndexRow` is a stamp and a digest: it is the record of what the
    rows beside it are, and it is filed beside them rather than dated itself.
    Giving it a date column to route by would move a persisted shape to answer a
    question the filename already answers - the only producer of an eval row
    stamps it with the run's own date, which is the first ten characters of the
    run id the segment is named for.

    Every other ledger here names its own day, which is what lets a segment a
    run left behind three days ago compact into that day rather than into today.
    """
    return _SEGMENT_HEADS[ledger].dates_from_run


def segment_head(state_dir: Path, ledger: SegmentLedger, date: str) -> SegmentHead:
    """The head a row of this date belongs in, with what settles two of its rows.

    The date comes off the row, never off the clock. A segment a run left behind
    three days ago compacts into that day's head, which is the whole of the
    recovery path.
    """
    shape = _SEGMENT_HEADS[ledger]
    return SegmentHead(
        shape.path(state_dir, date),
        shape.relpath(date),
        shape.key,
        shape.model,
        shape.carried,
    )


def segment_contract(ledger: SegmentLedger) -> type[CsvContract]:
    """The model that reads one of this ledger's rows.

    Asked before a head is named, because the head is chosen by a row's date
    cell and a date cell is only a date once the contract has read it. Naming a
    file from an unread cell is how a path is built out of something nobody
    validated.
    """
    return _SEGMENT_HEADS[ledger].model


def _segment_name(*, run_id: str, attempt: int, job: ServerJob, shard: int) -> str:
    """The grammar in 2.3, spelled once, so a path and its POSIX form cannot differ."""
    return f"{run_id}-{attempt}-{job.value}-{shard:02d}{SEGMENT_SUFFIX}"


def segment_path(
    state_dir: Path,
    ledger: SegmentLedger,
    *,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
) -> Path:
    """Where this writer puts its rows. Nobody else writes this path.

    The four elements are what make one writer's file its own: the run, the try
    at that run, the job, and the shard inside it. Two jobs of one run cannot
    collide, and neither can two attempts - which is the difference between a
    lost push race costing a merge and costing the rows.

    There is no date element. The run id opens on the date already, and the head
    a row lands in is chosen by the row's own date cell, so a second date here
    would be a cell a writer fills for nothing.
    """
    name = _segment_name(run_id=run_id, attempt=attempt, job=job, shard=shard)
    return state_dir / SEGMENTS_DIRNAME / ledger.value / name


def segment_relpath(
    ledger: SegmentLedger,
    *,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
) -> str:
    """`state/segments/<ledger>/<run_id>-<attempt>-<job>-<shard>.csv`, POSIX form.

    The same grammar as `segment_path`, for a log line and for anything that has
    to name the store a job fills without holding a state root (CLAUDE.md
    section 2).
    """
    name = _segment_name(run_id=run_id, attempt=attempt, job=job, shard=shard)
    return f"{STATE_DIRNAME}/{SEGMENTS_DIRNAME}/{ledger.value}/{name}"


def write_segment(
    state_dir: Path,
    ledger: SegmentLedger,
    rows: Sequence[CsvRecord],
    *,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
) -> int:
    """This writer's slice of one ledger, written whole. Nobody else writes this path.

    Whole rather than appended, because the file is this writer's alone: there is
    no earlier row in it to keep and no header to agree with. That is the whole
    of what the segment store buys - two jobs of one run, and two attempts at one
    job, never open one file, so a lost push race costs a merge rather than the
    rows.

    The rows carry the HEAD's columns and the head's contract. A segment gets no
    shape of its own on purpose: it holds the head's rows in transit, and a
    second shape for the same rows is the thing that drifts.

    Written through a temp file and a rename, so a writer killed mid-write leaves
    nothing rather than half a row for the compaction to refuse. The temp file
    sits at the store's own top rather than beside the target: `segment_files`
    reads every name inside a ledger's directory and refuses one it cannot place,
    so a scratch left there by a dead runner would stop every later compaction.
    The top of the store is the one place that already holds something which is
    not a segment.

    Returns how many rows it wrote, so a caller can log the count.
    """
    if not rows:
        return 0
    path = segment_path(state_dir, ledger, run_id=run_id, attempt=attempt, job=job, shard=shard)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = _SEGMENT_HEADS[ledger].model.csv_columns()
    scratch = state_dir / SEGMENTS_DIRNAME / f"{path.stem}.{os.getpid()}.tmp"
    scratch.write_text(
        render_file(columns, [row.csv_row() for row in rows]), encoding="utf-8", newline=""
    )
    scratch.replace(path)
    return len(rows)


def extend_segment(
    state_dir: Path,
    ledger: SegmentLedger,
    rows: Sequence[CsvRecord],
    *,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
) -> int:
    """Add rows to this writer's own segment, keeping the ones it wrote earlier.

    `write_segment` is for a step that has everything its job will ever say. This
    is for a job that learns something later: the machine probe runs before the
    heaviest step because the bandwidth reading wants an idle host, and the job's
    own clock is only known once the job is over. Two steps, one writer, one
    file - the grammar in `segment_path` names the job and not the step, so a
    second file is not something this store can express.

    The earlier rows are read and written back unchanged. Nothing is edited and
    nothing is settled here: the arriving row carries the cells it has, the
    earlier row keeps the cells it had, and `stages.compact` is the one place
    that decides what two rows of one key mean.

    Whole through a temp file and a rename for `write_segment`'s reason - a
    writer killed mid-write leaves the file it already had rather than half a
    row.

    Returns how many rows it added, so a caller can log the count.
    """
    if not rows:
        return 0
    path = segment_path(state_dir, ledger, run_id=run_id, attempt=attempt, job=job, shard=shard)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = _SEGMENT_HEADS[ledger].model.csv_columns()
    held = [{name: row.get(name, "") for name in columns} for row in _read_rows(path)]
    scratch = state_dir / SEGMENTS_DIRNAME / f"{path.stem}.{os.getpid()}.tmp"
    scratch.write_text(
        render_file(columns, held + [row.csv_row() for row in rows]),
        encoding="utf-8",
        newline="",
    )
    scratch.replace(path)
    return len(rows)


def parse_segment_name(path: Path) -> SegmentName:
    """A segment filename read back, or a refusal naming the file.

    A name this cannot place is not skipped. The store holds one kind of file
    written by one kind of writer, so a name outside the grammar means something
    else is writing there - and a glob that passed over it would leave those rows
    in the tree unread and unmentioned, which is how a ledger starts losing rows
    with nobody noticing.
    """
    match = _SEGMENT_NAME.fullmatch(path.stem) if path.suffix == SEGMENT_SUFFIX else None
    if match is None:
        raise ValueError(
            f"{path.name} is not a segment name. A segment is "
            "<run_id>-<attempt>-<job>-<shard>.csv, and a file under "
            f"{STATE_DIRNAME}/{SEGMENTS_DIRNAME}/ that is not one was written by "
            "something nobody here declared."
        )
    return SegmentName(
        run_id=match["run_id"],
        attempt=int(match["attempt"]),
        job=ServerJob(match["job"]),
        shard=int(match["shard"]),
    )


def _declared_ledger(directory: Path) -> SegmentLedger:
    try:
        return SegmentLedger(directory.name)
    except ValueError:
        declared = ", ".join(sorted(item.value for item in SegmentLedger))
        raise ValueError(
            f"{STATE_DIRNAME}/{SEGMENTS_DIRNAME}/{directory.name} names a ledger "
            f"nothing here declares. The declared set is {declared}. Every segment "
            "belongs to a head, so a directory outside that set is a writer that "
            "arrived without anyone choosing it."
        ) from None


def segment_files(state_dir: Path, ledger: SegmentLedger | None = None) -> list[Path]:
    """Every segment on disk, or one ledger's, oldest name first.

    The only listing there is, and its cost is what is waiting rather than what
    the project has written: on the normal path a compaction drained the store
    one run ago, so this reads an empty directory (Guardrail #12).

    **Nothing inside a ledger's directory is skipped**, for the reason
    `day_partition` gives. The store's own top is different and is allowed to
    hold something that is not a segment - `state/segments/.gitkeep` is what
    keeps the empty directory in the checkout at all.

    A missing directory lists nothing, because a fresh clone has no segments and
    that is not a fault.
    """
    root = state_dir / SEGMENTS_DIRNAME
    if not root.is_dir():
        return []
    found: list[Path] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        declared = _declared_ledger(entry)
        if ledger is not None and declared is not ledger:
            continue
        for candidate in sorted(entry.iterdir()):
            parse_segment_name(candidate)
            found.append(candidate)
    return found


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

    `state/content-similarity-judge/fitted-thresholds/` is registered before
    anything writes it, for the reason `state/feed-retirements.csv` was: the settlement
    runs over whatever it finds, a missing file settles to nothing, and
    registering the shape rather than its first writer is what stops two stale
    checkouts leaving one date fitted twice. Its sibling `scored-pairs/` joins on
    the same terms: `run_id` is in its key, so what settles there is a second
    attempt at one execution and never a second run of the day.

    `state/llm-council/shard-outcomes/` joined on 2026-09-21 with its writer. Its
    key carries `judge_id` as well as the run and the unit, because one council
    run has one run id and a night hosting two tenants would otherwise file two
    tenants' unit 0 under the same three cells.
    """
    flat: list[KeyedLedger] = [
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
                fitted_thresholds_path(state_dir, date),
                STORY_SIMILARITY_THRESHOLD_KEY,
                FittedSimilarityThreshold,
            ),
            KeyedLedger(
                scored_pairs_path(state_dir, date),
                STORY_SIMILARITY_PAIR_KEY,
                StorySimilarityPair,
            ),
            KeyedLedger(
                council_shard_outcomes_path(state_dir, date),
                COUNCIL_SHARD_OUTCOME_KEY,
                CouncilShardOutcome,
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
            KeyedLedger(path, STORY_SIMILARITY_THRESHOLD_KEY, FittedSimilarityThreshold)
            for path in day_partition.day_files(
                state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / FITTED_THRESHOLDS_DIRNAME
            )
        ),
        *(
            KeyedLedger(path, STORY_SIMILARITY_PAIR_KEY, StorySimilarityPair)
            for path in day_partition.day_files(
                state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / SCORED_PAIRS_DIRNAME
            )
        ),
        *(
            KeyedLedger(path, COUNCIL_SHARD_OUTCOME_KEY, CouncilShardOutcome)
            for path in day_partition.day_files(
                state_dir / COUNCIL_DIRNAME / SHARD_OUTCOMES_DIRNAME
            )
        ),
        *(
            KeyedLedger(path, SPAN_ROLLUP_KEY, SpanRollupRow)
            for path in month_partition.month_files(state_dir / SPAN_ROLLUP_DIRNAME, ".csv")
        ),
    ]


def drop_repeated_rows(path: Path, key: tuple[str, ...]) -> int:
    """Rewrite the file without any row repeating a key an earlier row holds.

    This is the half of the guarantee `extend_ledger_file`'s filter cannot give. That filter
    reads the committed file the job checked out, and `actions/checkout` pins a
    job to the commit its run was triggered at - so a second execution of the
    same work cannot see rows the first one pushed after that commit. Its append
    lands them again. On the two day trees that still carry a union merge driver
    - `state/published/` and `state/visual-prunes/` - git then concatenates both
    sides line by line, which is the right answer for two runs writing different
    rows and exactly the wrong one for two attempts writing the same row.
    Everywhere else under `state/` that driver went on 2026-09-19 and the second
    push conflicts at the rebase instead. Measured on this
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


def load_host_fingerprint_shard(path: Path) -> list[HostFingerprintRow]:
    """Every row of one day's host records. Empty for a day never written.

    A day and not a window, because the key opens with `date` and a run id
    already names its date - so a caller asking about one run opens one file
    however long the ledger gets (Guardrail #12).
    """
    return [HostFingerprintRow.from_csv_row(row) for row in _read_rows(path)]


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
    a month whenever the fold ran again over a shard a lost race had restored.

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
