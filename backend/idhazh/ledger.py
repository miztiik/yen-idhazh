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
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final, NamedTuple, Protocol

from idhazh import day_partition
from idhazh.contracts.base import RUN_ID_PATTERN, ServerJob
from idhazh.contracts.council_shard_outcome import CouncilShardOutcome
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.day_validation import DayValidationReceipt
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
from idhazh.contracts.story_similarity_pair import (
    DROPPED_CELLS as DROPPED_PAIR_CELLS,
)
from idhazh.contracts.story_similarity_pair import (
    StorySimilarityPair,
)
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

#: Which frozen days have passed a validation, and against what. A day tree
#: rather than the one flat `day-validations.csv` it was until 2026-09-22: four
#: validators can judge one day at once, a flat file gave them all one path, and
#: a receipt lost to a merge reads exactly like a day nobody has validated.
DAY_VALIDATIONS_DIRNAME: Final = "day-validations"

#: The column every day tree except the score index routes a row by. Named once
#: here because the router reads it out of a contract's own cells, and a second
#: spelling of it would file a row under a day nobody can find it in.
DATE_CELL: Final = "date"

#: Every directory under `state/` this module owns a store in. `prune-state`
#: subtracts it, and the few stores other modules own, from the children of
#: `state/`; what is left is a trial run's tree, and that is how the prune finds
#: a tree to empty without being told its name.
#:
#: Built from the constants above rather than from their text, so a store added
#: through its own constant joins this set in the same commit. A name missing
#: here reads as a trial root, which is why the subtraction is spelled out
#: rather than guessed at.
#:
#: The nested names are deliberately absent: `shard-outcomes` and the judge's
#: five are one level further down, inside a prefix already named here.
STORE_DIRNAMES: Final[frozenset[str]] = frozenset(
    {
        SEEN_DIRNAME,
        HEALTH_DIRNAME,
        ITEM_HEALTH_DIRNAME,
        HOST_FINGERPRINT_DIRNAME,
        TELEMETRY_AGGREGATE_DIRNAME,
        SPAN_ROLLUP_DIRNAME,
        PUBLISHED_DIRNAME,
        VISUAL_PRUNES_DIRNAME,
        COUNTERFACTUAL_SCORES_DIRNAME,
        VALIDATION_DIRNAME,
        SCORES_DIRNAME,
        SCORE_INDEX_DIRNAME,
        COUNCIL_DIRNAME,
        CONTENT_SIMILARITY_JUDGE_DIRNAME,
    }
)

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

#: What makes two merge-line holdout rows the same record. One run scores one
#: line against one marked file on one date, so a second row under those two
#: cells is a second attempt at one execution rather than a second answer. The
#: marks are hand-written and the day payloads are committed, so two attempts
#: count the same cells and the first row wins.
#:
#: Spelled here as four strings and nothing else. The shape they name is
#: `idhazh.contracts.merge_line_holdout_score`, and this module may not import
#: it: a council verb reaches this module for its own row types, and a judge
#: contract arriving through it would put a judge in the council's import
#: closure (`backend/tests/council/test_council_runs_without_a_judge.py`).
MERGE_LINE_HOLDOUT_SCORE_KEY: Final = ("date", "run_id")

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

#: What makes two day-validation receipts the same record. The day, and nothing
#: else. A receipt says a frozen day passed the rules as they stood, so two
#: receipts for one day are one answer written twice - and when the rules move,
#: the newer receipt is the one that is true (`DAY_VALIDATION_RULE`).
DAY_VALIDATION_KEY: Final = ("date",)

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

    It beats attempt order too. A later attempt that reached no item leaves
    `job` empty, and a row carrying the identity is better evidence than a row
    that does not, whichever run wrote it.
    """
    return bool(later.get("job")) and not kept.get("job")


def _day_validation_rule(later: dict[str, str], kept: dict[str, str]) -> bool:
    """The newer receipt wins, always.

    A receipt says a frozen day passed the rules as they stood. When the rules
    move, every day is re-judged and writes a fresh receipt, and the answer that
    is true is the one taken under the rules in force. Keeping the first would
    pin a day to a rule set nobody runs any more.

    Both arguments are read and neither is compared, because the ordering has
    already decided: `day_shards.settled_rows` walks a day's files oldest first,
    so `later` is later.
    """
    return bool(later) or not kept


#: The keys whose repeats can disagree, and how each one picks a winner.
FEED_HEALTH_RULE: Final[Preference] = _feed_health_rule
ITEM_HEALTH_RULE: Final[Preference] = _item_health_rule
DAY_VALIDATION_RULE: Final[Preference] = _day_validation_rule
_PREFERENCES: Final[dict[tuple[str, ...], Preference]] = {
    FEED_HEALTH_KEY: FEED_HEALTH_RULE,
    ITEM_HEALTH_KEY: ITEM_HEALTH_RULE,
    DAY_VALIDATION_KEY: DAY_VALIDATION_RULE,
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
    """`state/feed-health/<YYYY>/<MM>/<DD>` - the day directory, POSIX form."""
    return f"{STATE_DIRNAME}/{HEALTH_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}"


def health_path(state_dir: Path, date: str) -> Path:
    """The day directory a run on this date files its verdicts in.

    A day rather than a month, for the reason `item_health_path` gives: taking a
    day back is one `rm` rather than an edit inside a shared shard, which an
    append-only ledger cannot express. Nothing mirrors this store into
    `frontend/public/`.

    A directory rather than a file, because two `plan` jobs of one night both
    have a verdict on every feed and a shared file gave them one path. They
    conflicted, the conflict killed the job, and `assemble` never ran.
    """
    return state_dir / HEALTH_DIRNAME / date[:4] / date[5:7] / date[8:10]


def item_health_relpath(date: str) -> str:
    """`state/item-health/<YYYY>/<MM>/<DD>` - the day directory, POSIX form."""
    return f"{STATE_DIRNAME}/{ITEM_HEALTH_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}"


def item_health_path(state_dir: Path, date: str) -> Path:
    """The day directory a run on this date files its item outcomes in.

    A day rather than a month, for the reason `published_path` gives: taking a
    day back is one `rm` rather than an edit inside a shared shard, which an
    append-only ledger cannot express. The mirror under
    `frontend/public/telemetry/` stays monthly, because its grain follows what a
    browser fetches - see `docs/concepts/partitions.md`.

    A directory rather than a file, because twenty work shards write this day
    and each one gets its own file inside it. Nothing here is shared, so nothing
    here can conflict.
    """
    return state_dir / ITEM_HEALTH_DIRNAME / date[:4] / date[5:7] / date[8:10]


def host_fingerprint_relpath(date: str) -> str:
    """`state/host-fingerprint/<YYYY>/<MM>/<DD>` - the day directory, POSIX form."""
    return f"{STATE_DIRNAME}/{HOST_FINGERPRINT_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}"


def host_fingerprint_path(state_dir: Path, date: str) -> Path:
    """The day directory this date's machines land in, one file per job.

    A day rather than a flat file, for the reason `item_health_path` gives, and
    with a second reason of its own: this collection only earns its keep when
    somebody counts across it, and a day tree is the shape a bounded window can
    read (Guardrail #12).

    Twenty-five jobs of one run each record the machine they drew, and each one
    writes its own file here. None of them opens a file another job holds, which
    is what stops a lost push race emptying the day - `2026-09-16` is
    header-only because that is what happened under the old shared shard.
    """
    return state_dir / HOST_FINGERPRINT_DIRNAME / date[:4] / date[5:7] / date[8:10]


def scores_relpath(date: str) -> str:
    """`state/scores/<YYYY>/<MM>/<DD>` - the day directory, POSIX form."""
    return f"{STATE_DIRNAME}/{SCORES_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}"


def scores_path(state_dir: Path, date: str) -> Path:
    """The day directory one date's measurements land in, one file per writer.

    A day rather than a month, for the reason `published_path` gives: taking a
    day back is one `rm` rather than an edit inside a shared shard, which an
    append-only ledger cannot express. Nothing mirrors this store into
    `frontend/public/`.

    Two jobs of one run measure items - a work shard as each item settles, and
    assemble over the whole day afterwards - and each writes its own file here,
    which is what stops a lost push race costing the rows rather than a merge.
    """
    return state_dir / SCORES_DIRNAME / date[:4] / date[5:7] / date[8:10]


def score_index_relpath(date: str) -> str:
    """`state/score-index/<YYYY>/<MM>/<DD>` - the day directory, POSIX form."""
    return f"{STATE_DIRNAME}/{SCORE_INDEX_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}"


def score_index_path(state_dir: Path, date: str) -> Path:
    """The record of what one day's measurements are, beside the rows themselves.

    The same grain as `scores_path` and filed by the same date. An index row
    carries no date column of its own, so its writer names the day: the first
    ten characters of the run id, which is the date the eval rows beside it
    carry.
    """
    return state_dir / SCORE_INDEX_DIRNAME / date[:4] / date[5:7] / date[8:10]


def validation_relpath(date: str) -> str:
    """`state/validation/<YYYY>/<MM>/<DD>` - the day directory, POSIX form."""
    return f"{STATE_DIRNAME}/{VALIDATION_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}"


def validation_path(state_dir: Path, date: str) -> Path:
    """The day directory this date's verdicts land in, one file per dispatch.

    A day tree rather than `validation-<date>.csv` at the top of `state/`, for
    the reason `item_health_path` gives and with one of its own: the old name was
    built from the repository root, so no config could move it and a candidate
    qualified on a trial state root still wrote the production tree. The state
    root a dispatch is handed is what decides where this lands, which is how a
    pipeline-tests run writes under `state/pipeline-tests/` instead.

    Two candidates can be dispatched at once and both judge the same day, so
    each writes its own file here - the filename is what keeps the pair apart.
    """
    return state_dir / VALIDATION_DIRNAME / date[:4] / date[5:7] / date[8:10]


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


def span_rollup_relpath(date: str) -> str:
    """`state/span-rollup/<YYYY>/<MM>/<DD>` - the day directory, POSIX form."""
    return f"{STATE_DIRNAME}/{SPAN_ROLLUP_DIRNAME}/{date[:4]}/{date[5:7]}/{date[8:10]}"


def span_rollup_path(state_dir: Path, date: str) -> Path:
    """The day directory this date's folded spans land in, one file per writer.

    A day rather than the month this was until 2026-09-22. The month grain was
    the last thing in `state/` asking a reader to hold two grains at once, and it
    bought nothing a day does not: twenty writers a day each file their own
    rows, so the question a month answered - how do twenty writers share one
    file - stopped being a question.
    """
    return state_dir / SPAN_ROLLUP_DIRNAME / date[:4] / date[5:7] / date[8:10]


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
    """`state/counterfactual-scores/<YYYY>/<MM>/<DD>` - the day directory, POSIX form."""
    stem = f"{date[:4]}/{date[5:7]}/{date[8:10]}"
    return f"{STATE_DIRNAME}/{COUNTERFACTUAL_SCORES_DIRNAME}/{stem}"


def counterfactual_scores_path(state_dir: Path, date: str) -> Path:
    """The day file this date's runs write their two scores per candidate into.

    A day, and here the read asked for it as well as the writer: the only reader
    of this ledger opens a trailing window of days (`lens_weights.window_days`),
    and the retention pass deletes by day. A month file would make both of those
    read or delete weeks nobody asked for.
    """
    return state_dir / COUNTERFACTUAL_SCORES_DIRNAME / date[:4] / date[5:7] / date[8:10]


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

    Beside `_csv_line` because a file the compaction rewrites whole and a row an
    append adds have to be the same bytes. Written two ways, a file the
    compaction touched would read as changed line by line the next time anything
    diffed it.

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
    day file under `state/` carried that driver until 2026-09-19; the files it
    already made are committed, and the migration to day directories carried
    their bytes over as they stood.

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
      where the second succeeded. `day_shards.settled_rows` settles the day
      against `FEED_HEALTH_KEY` at read time, so the winner is picked by the rule
      in `contracts.feed_health.supersedes` rather than by which line landed
      first.
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
    from idhazh import day_shards

    wanted = set(codes)
    return {
        row["url_key"]
        for row in day_shards.settled_day(
            state_dir / ITEM_HEALTH_DIRNAME, date, ITEM_HEALTH_KEY, ItemHealthRow
        )
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
    from idhazh import day_shards

    carried: dict[str, str] = {}
    for row in day_shards.settled_day(
        state_dir / ITEM_HEALTH_DIRNAME, date, ITEM_HEALTH_KEY, ItemHealthRow
    ):
        if row["date"] != date or row["outcome"] != ItemOutcome.OK:
            continue
        carried[row["url_key"]] = row["source_id"]
    counts: dict[str, int] = {}
    for source_id in carried.values():
        counts[source_id] = counts.get(source_id, 0) + 1
    return counts


def _as_item_health_row(raw: dict[str, str]) -> dict[str, str]:
    """The contract's own reader, used as a row-to-row migration."""
    return refiler(ItemHealthRow)(raw)


#: The headings a day file an earlier run wrote still carries that the current
#: row no longer names. Two kinds, and the difference is what happens to the
#: cell: `from_csv_row` reads a RETIRED heading into the column that replaced
#: it, and a DROPPED heading has no replacement - the file still re-files, and
#: the cell goes, which is the point of dropping it.
ITEM_HEALTH_CARRIED: Final[frozenset[str]] = frozenset(RETIRED_CELLS) | DROPPED_CELLS

#: The same, for the judged-pair store. One column has left this row and none has
#: moved, so there is no retired half: `from_csv_row` reads a day file by the
#: names the contract holds now and the dropped heading simply goes.
STORY_SIMILARITY_PAIR_CARRIED: Final[frozenset[str]] = DROPPED_PAIR_CELLS


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

    Settled against `FEED_RETIREMENT_KEY` straight after the write, because the
    two runs that can write one address are two
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
    """Every (date, run, shard, span) one span-rollup file already carries a fold for.

    A reader and no longer half of a writer. A work shard folds its spans into
    its own file in the day directory and nothing else opens that path, so the
    question this answers is what a settled file already holds rather than what
    an append is about to skip.
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


def append_story_similarity_pairs(
    state_dir: Path, date: str, rows: Iterable[StorySimilarityPair]
) -> int:
    """Append a day's judged pairs into that day's own file.

    Settled against `STORY_SIMILARITY_PAIR_KEY` straight after the write, the
    way `append_visual_prunes` is. The key carries `run_id`, so a second
    RUN of one date keeps its own rows and only a second attempt at one
    execution is collapsed - both attempts judged the same pair under the same
    prompt against the same day, so the first row wins and there is nothing to
    choose between them. Which of two runs the record counts is decided over the
    whole day when the day is folded, never line by line here.

    **The day file is created even when the day judged nothing.** The commit step
    names this directory,
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
    ran. The empty-file half is the same reason `append_story_similarity_pairs`
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
    """Which day tree a writer's file belongs to. A closed set, and that is the point.

    A directory under `state/` naming something outside this set is a writer that
    arrived without anyone choosing it. Every value is the tree's own `*_DIRNAME`
    constant rather than a string repeated here, so the directory a writer fills
    and the directory a reader walks cannot be spelled two different ways.

    A ledger joins this set in the row that moves its writer, never before it.
    """

    ITEM_HEALTH = ITEM_HEALTH_DIRNAME
    HOST_FINGERPRINT = HOST_FINGERPRINT_DIRNAME
    SPAN_ROLLUP = SPAN_ROLLUP_DIRNAME
    SCORES = SCORES_DIRNAME
    SCORE_INDEX = SCORE_INDEX_DIRNAME
    VALIDATION = VALIDATION_DIRNAME
    HEALTH = HEALTH_DIRNAME
    COUNTERFACTUAL_SCORES = COUNTERFACTUAL_SCORES_DIRNAME
    DAY_VALIDATIONS = DAY_VALIDATIONS_DIRNAME


class SegmentName(NamedTuple):
    """A writer's filename read back: who wrote it, and on which try.

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
#:
#: Public because `idhazh.paths` answers whether a committed path has exactly
#: one writer, and it has to ask this pattern rather than carry a copy of it.
SEGMENT_NAME: Final = re.compile(
    rf"(?P<run_id>{RUN_ID_PATTERN[1:-1]})"
    r"-(?P<attempt>[0-9]+)"
    rf"-(?P<job>{'|'.join(job.value for job in ServerJob)})"
    r"-(?P<shard>[0-9]{2})",
    re.ASCII,
)

SEGMENT_SUFFIX: Final = ".csv"

#: What the migration calls the bytes a committed head already held. A head is
#: many runs already merged, so it carries no writer identity to stamp and a
#: synthetic one would claim a run that never wrote it.
#:
#: **Removal condition: it goes when the oldest committed day is newer than the
#: migration date**, because after that no committed day predates identity.
BEFORE_PARTITION_NAME: Final = "before-partition.csv"

#: What a committed trace was called before writes carried identity:
#: `<ordinal>-<shard>.jsonl`, where the ordinal is the run id's last segment
#: alone. A trace line carries `attributes, duration_ms, kind, name, parent_id,
#: span_id, started_at, trace_id` and no job and no attempt, so those two
#: elements are not recoverable and the bytes keep the name they were written
#: under.
#:
#: **Removal condition: it goes when `observability.trace_window_days` has aged
#: out every file written before the migration.** That is self-clearing and
#: needs no later row - a trace is never folded, and `stages/prune_state.py`
#: deletes whole files on that window.
PRE_IDENTITY_TRACE: Final = re.compile(r"[0-9]+-[0-9]{2}", re.ASCII)

#: What an operator's repair is called: `repair-<YYYYMMDDTHHMMSSZ>.csv`. A
#: repair is one add by a person at one instant, so it carries no run and no
#: job to spell, and the instant is what keeps two repairs apart.
#:
#: **Removal condition: it goes when no operator command adds rows to a day a
#: run already wrote.** `evals.writer.rebuild_index` is the only one today.
REPAIR_NAME: Final = re.compile(r"repair-[0-9]{8}T[0-9]{6}Z", re.ASCII)

#: The stamp format `REPAIR_NAME` spells, for the caller that mints one.
REPAIR_STAMP: Final = "%Y%m%dT%H%M%SZ"


def repair_name(minted_at: datetime) -> str:
    """What an operator's one add into a committed day directory is called."""
    return f"repair-{minted_at.strftime(REPAIR_STAMP)}{SEGMENT_SUFFIX}"


def is_repair(name: str) -> bool:
    """Whether this filename is an operator's one add rather than a writer's file.

    Asked by the reader that orders a day's files and by the one that asks
    whether a committed path has a single writer, so it is spelled here once.
    """
    stem, _, suffix = name.rpartition(".")
    return suffix == SEGMENT_SUFFIX[1:] and REPAIR_NAME.fullmatch(stem) is not None


class _TreeShape(NamedTuple):
    """One day tree's answer to "what settles two of its rows, and who reads one"."""

    key: tuple[str, ...]
    model: type[CsvContract]
    carried: frozenset[str] = frozenset()


#: What settles two rows of one day tree, and the contract that reads one. A
#: declared table rather than a rule a reader re-derives: the key is a fact about
#: the ledger and a second copy of it is how two readers start disagreeing.
_TREE_SHAPES: Final[dict[SegmentLedger, _TreeShape]] = {
    SegmentLedger.ITEM_HEALTH: _TreeShape(ITEM_HEALTH_KEY, ItemHealthRow, ITEM_HEALTH_CARRIED),
    SegmentLedger.HOST_FINGERPRINT: _TreeShape(HOST_FINGERPRINT_KEY, HostFingerprintRow),
    SegmentLedger.SPAN_ROLLUP: _TreeShape(SPAN_ROLLUP_KEY, SpanRollupRow),
    SegmentLedger.SCORES: _TreeShape(OBSERVATION_KEY, EvalRow),
    SegmentLedger.SCORE_INDEX: _TreeShape(OBSERVATION_INDEX_KEY, ObservationIndexRow),
    SegmentLedger.VALIDATION: _TreeShape(VALIDATION_KEY, ValidationRow),
    SegmentLedger.HEALTH: _TreeShape(FEED_HEALTH_KEY, FeedHealthRow),
    SegmentLedger.COUNTERFACTUAL_SCORES: _TreeShape(
        COUNTERFACTUAL_SCORE_KEY, CounterfactualScoreRow
    ),
    SegmentLedger.DAY_VALIDATIONS: _TreeShape(DAY_VALIDATION_KEY, DayValidationReceipt),
}


def segment_contract(ledger: SegmentLedger) -> type[CsvContract]:
    """The model that reads one of this ledger's rows.

    Asked before a file is named, because a file is named for the writer and a
    row is routed by its own date cell - and a date cell is only a date once the
    contract has read it. Naming a file from an unread cell is how a path is
    built out of something nobody validated.
    """
    return _TREE_SHAPES[ledger].model


def segment_key(ledger: SegmentLedger) -> tuple[str, ...]:
    """What makes two of this ledger's rows the same record."""
    return _TREE_SHAPES[ledger].key


def segment_carried(ledger: SegmentLedger) -> frozenset[str]:
    """The retired headings this ledger's reader can still place."""
    return _TREE_SHAPES[ledger].carried


def segment_name(
    *, run_id: str, attempt: int, job: ServerJob, shard: int, suffix: str = SEGMENT_SUFFIX
) -> str:
    """The identity grammar, spelled once, so two trees cannot spell it two ways.

    `suffix` is here because one tree's writer files are not CSV. A committed
    trace is JSON lines, and one spelling of identity across every tree is worth
    more than a signature nothing ever passes a second argument to: a second
    speller is a second grammar, and a reader that knew only one would walk past
    the other tree's files without saying so.
    """
    return f"{run_id}-{attempt}-{job.value}-{shard:02d}{suffix}"


def day_shard_path(
    state_dir: Path,
    ledger: SegmentLedger,
    *,
    date: str,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
) -> Path:
    """Where this writer puts this date's rows. Nobody else writes this path.

    `state/<tree>/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.csv`. The
    date supplies the three directory segments, the way every sibling helper in
    this module takes one; the four identity elements are what make the file
    this writer's own. Two jobs of one run cannot collide, and neither can two
    attempts - which is the difference between a lost push race costing a merge
    and costing the rows.

    The day comes off the row rather than off the clock, so rows a run left
    behind three days ago land under that day rather than under today.
    """
    name = segment_name(run_id=run_id, attempt=attempt, job=job, shard=shard)
    return state_dir / ledger.value / date[:4] / date[5:7] / date[8:10] / name


def day_shard_relpath(
    ledger: SegmentLedger,
    *,
    date: str,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
) -> str:
    """The POSIX form of `day_shard_path`, for a log line (CLAUDE.md section 2)."""
    name = segment_name(run_id=run_id, attempt=attempt, job=job, shard=shard)
    return f"{STATE_DIRNAME}/{ledger.value}/{date[:4]}/{date[5:7]}/{date[8:10]}/{name}"


def _dated_rows(
    ledger: SegmentLedger, rows: Sequence[CsvRecord], date: str | None
) -> dict[str, list[dict[str, str]]]:
    """This writer's rows, grouped by the day each one belongs under.

    `date` is for the one tree whose rows carry no date cell. The score index is
    a stamp and a digest - the record of what the rows beside it are - so it is
    filed beside them rather than dated itself, and its writer already knows the
    day because it is the first ten characters of the run id. Every other tree
    routes each row by its own `date` cell, so a writer holding two days' rows
    writes two files.
    """
    columns = _TREE_SHAPES[ledger].model.csv_columns()
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        cells = row.csv_row()
        day = date if date is not None else cells[DATE_CELL]
        grouped.setdefault(day, []).append({name: cells.get(name, "") for name in columns})
    return grouped


def write_segment(
    state_dir: Path,
    ledger: SegmentLedger,
    rows: Sequence[CsvRecord],
    *,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
    date: str | None = None,
) -> int:
    """This writer's slice of one ledger, written whole. Nobody else writes these paths.

    Whole rather than appended, because each file is this writer's alone: there
    is no earlier row in it to keep and no header to agree with. That is what the
    day directory buys - two jobs of one run, and two attempts at one job, never
    open one file, so a lost push race costs a merge rather than the rows.

    One file a day. The rows carry the tree's own columns and the tree's own
    contract; a writer file gets no shape of its own, because a second shape for
    the same rows is the thing that drifts.

    Written through a temp file and a rename, so a writer killed mid-write leaves
    nothing rather than half a row for a reader to refuse. The temp file sits at
    the tree's own top rather than inside the day directory, which every reader
    walks and refuses a name it cannot place.

    Returns how many rows it wrote, so a caller can log the count.
    """
    if not rows:
        return 0
    columns = _TREE_SHAPES[ledger].model.csv_columns()
    written = 0
    for day, cells in _dated_rows(ledger, rows, date).items():
        path = day_shard_path(
            state_dir, ledger, date=day, run_id=run_id, attempt=attempt, job=job, shard=shard
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        scratch = state_dir / ledger.value / f"{path.stem}.{day}.{os.getpid()}.tmp"
        scratch.write_text(render_file(columns, cells), encoding="utf-8", newline="")
        scratch.replace(path)
        written += len(cells)
    return written


def extend_segment(
    state_dir: Path,
    ledger: SegmentLedger,
    rows: Sequence[CsvRecord],
    *,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
    date: str | None = None,
) -> int:
    """Add rows to this writer's own files, keeping the ones it wrote earlier.

    `write_segment` is for a step that has everything its job will ever say. This
    is for a job that learns something later: the machine probe runs before the
    heaviest step because the bandwidth reading wants an idle host, and the job's
    own clock is only known once the job is over. Two steps, one writer, one file
    a day - the grammar in `day_shard_path` names the job and not the step, so a
    second file is not something this tree can express.

    The earlier rows are read and written back unchanged. Nothing is edited and
    nothing is settled here: the arriving row carries the cells it has, the
    earlier row keeps the cells it had, and `day_shards.settled_rows` is the one
    place that decides what two rows of one key mean.

    Returns how many rows it added, so a caller can log the count.
    """
    if not rows:
        return 0
    columns = _TREE_SHAPES[ledger].model.csv_columns()
    added = 0
    for day, cells in _dated_rows(ledger, rows, date).items():
        path = day_shard_path(
            state_dir, ledger, date=day, run_id=run_id, attempt=attempt, job=job, shard=shard
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        held = [{name: row.get(name, "") for name in columns} for row in _read_rows(path)]
        scratch = state_dir / ledger.value / f"{path.stem}.{day}.{os.getpid()}.tmp"
        scratch.write_text(render_file(columns, held + cells), encoding="utf-8", newline="")
        scratch.replace(path)
        added += len(cells)
    return added


def parse_segment_name(path: Path, *, suffix: str = SEGMENT_SUFFIX) -> SegmentName:
    """A writer's filename read back, or a refusal naming the file.

    A name this cannot place is not skipped. A day directory holds one kind of
    file written by one kind of writer, so a name outside the grammar means
    something else is writing there - and a walk that passed over it would leave
    those rows in the tree unread and unmentioned, which is how a ledger starts
    losing rows with nobody noticing.

    `suffix` is the tree's own, for `segment_name`'s reason.
    """
    match = SEGMENT_NAME.fullmatch(path.stem) if path.suffix == suffix else None
    if match is None:
        raise ValueError(
            f"{path.name} is not a writer's name. A writer's file is "
            f"<run_id>-<attempt>-<job>-<shard>{suffix}, and a file inside a day "
            f"directory under {STATE_DIRNAME}/ that is not one was written by "
            "something nobody here declared."
        )
    return SegmentName(
        run_id=match["run_id"],
        attempt=int(match["attempt"]),
        job=ServerJob(match["job"]),
        shard=int(match["shard"]),
    )


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

    `state/feed-health/`, `state/item-health/`, `state/host-fingerprint/`,
    `state/span-rollup/` and `state/counterfactual-scores/` were all here until
    2026-09-22 and none of them is now. Each became a day directory where every
    writer holds its own file, so a merge has nothing to stack: two files that
    no one else can write do not need a settlement to tell them apart, and the
    repeat this pass existed to drop is a repeat those trees can no longer make.
    What settles two of their rows at read time is `day_shards.settled_rows`,
    which is where it always decided - this pass only ever rewrote the file.

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
                fitted_thresholds_path(state_dir, date),
                STORY_SIMILARITY_THRESHOLD_KEY,
                FittedSimilarityThreshold,
            ),
            KeyedLedger(
                scored_pairs_path(state_dir, date),
                STORY_SIMILARITY_PAIR_KEY,
                StorySimilarityPair,
                STORY_SIMILARITY_PAIR_CARRIED,
            ),
            KeyedLedger(
                council_shard_outcomes_path(state_dir, date),
                COUNCIL_SHARD_OUTCOME_KEY,
                CouncilShardOutcome,
            ),
        ]
    return [
        *flat,
        *(
            KeyedLedger(path, VISUAL_PRUNE_KEY, VisualPruneRow)
            for path in day_partition.day_files(state_dir / VISUAL_PRUNES_DIRNAME)
        ),
        *(
            KeyedLedger(path, STORY_SIMILARITY_THRESHOLD_KEY, FittedSimilarityThreshold)
            for path in day_partition.day_files(
                state_dir / CONTENT_SIMILARITY_JUDGE_DIRNAME / FITTED_THRESHOLDS_DIRNAME
            )
        ),
        *(
            KeyedLedger(
                path,
                STORY_SIMILARITY_PAIR_KEY,
                StorySimilarityPair,
                STORY_SIMILARITY_PAIR_CARRIED,
            )
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
    fastest-growing ledger in the repository and twenty work shards file into it
    every day, so a reader that walked every day would cost more every run for
    an answer about the last few weeks. `day_shards.settled_rows` names both the
    cover and the settlement, so a cover of `n` days reads the newest `n`
    RECORDED days and returns one row per planned item per run.

    A day the ledger never recorded has no entry, which is not a fault: a run
    that planned nothing that day wrote nothing that day.

    A row that no longer parses stops the read, which is what every day-shard
    read does: a census divides by these rows, so a silently dropped one moves a
    ratio instead of costing a decision some evidence.
    """
    from idhazh import day_shards

    return [
        ItemHealthRow.from_csv_row(row)
        for row in day_shards.settled_rows(
            state_dir / ITEM_HEALTH_DIRNAME, ITEM_HEALTH_KEY, ItemHealthRow, days=within_days
        )
    ]


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

    A row that no longer parses stops the read rather than being skipped. Each
    file is written whole by one writer from the contract's own columns, so a
    row that will not read means the writer and this reader disagree about the
    shape - `day_shards.parsed` says at length why that is the one ledger read
    that does not degrade.

    `day_shards.settled_rows` names both the cover and the settlement, so a
    cover of `n` days reads the newest `n` RECORDED days and returns one row per
    feed per run rather than one per write. A day the ledger never recorded has
    no entry, which is not a fault.
    """
    from idhazh import day_shards

    rows = [
        FeedHealthRow.from_csv_row(raw)
        for raw in day_shards.settled_rows(
            state_dir / HEALTH_DIRNAME, FEED_HEALTH_KEY, FeedHealthRow, days=within_days
        )
    ]
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
