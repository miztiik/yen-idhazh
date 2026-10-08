"""What makes two rows of one ledger the same record, and which contract reads one.

A key is a fact about a ledger, so it is written once and read by every pass that
settles one: the append that runs from the commit step, the fold a reader takes
over a day directory, and the compaction. A second copy of a key is how two
readers start disagreeing about what one file holds.

One table pairs a key with the contract that reads a row: the ledgers the door
in `ledger/persist.py` files under `state/raw/` and `state/compact/`. It also
holds each ledger still on CSV that is ready to move, so moving one is a switch
of its registry grain.

Where a ledger's file lives is a different question with its own home, which is
why `paths` imports nothing from here and this module imports nothing from it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, NamedTuple

from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import CollectionPruneRow
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.council_run_record import CouncilRunRecord
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, supersedes
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.fitted_similarity_threshold import (
    DROPPED_CELLS as DROPPED_FIT_CELLS,
)
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.item_health_summary import ItemHealthSummaryRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.story_similarity_pair import (
    DROPPED_CELLS as DROPPED_PAIR_CELLS,
)
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.contracts.validation_row import ValidationRow
from idhazh.contracts.visual_prune import VisualPruneRow

#: The column the door files a dated row under, read out of the row's own cells.
#: Named once here because a second spelling of it would file a row under a day
#: nobody can find it in.
DATE_CELL: Final = "date"


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


#: What makes two item-health summary rows the same record. One folded month
#: keeps one total for one UTC day and one pipeline stage.
ITEM_HEALTH_SUMMARY_KEY: Final = ("date", "stage")


#: One machine a job, so four cells identify the host a job drew.
HOST_FINGERPRINT_KEY: Final = ("date", "run_id", "job", "shard")


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
#: `work_part_index` follows `run_id`, because a judge row about one part of the
#: split is keyed on its part: two parts of one run never settle into one record.
#:
#: `judged_by_run_id` is in it because `run_id` names the DIGEST run that
#: published the day, so two judging runs over one date write the identical
#: string there. Without this cell the settlement would keep the row already in
#: the checked-out file and discard every fresh verdict, while the record
#: counted the fresh ones - two descriptions of one day with nothing able to
#: tell them apart.
STORY_SIMILARITY_PAIR_KEY: Final = (
    "date",
    "run_id",
    "work_part_index",
    "pair_key",
    "judged_by_run_id",
)


#: What makes two metrics rows the same record: one part of one council run's
#: night, for one judged date.
CONTENT_SIMILARITY_JUDGE_METRICS_KEY: Final = ("date", "run_id", "work_part_index")


#: What makes two retirement rows the same record. The address and nothing else:
#: a retirement is permanent for one endpoint key, so a second row for it says
#: nothing the first did not. `feed_id` is deliberately absent - renaming a feed
#: in curated config must not make its dead address eligible again, and editing
#: that feed's URL already produces a different key.
FEED_RETIREMENT_KEY: Final = ("endpoint_key",)


#: What makes two gardener rows the same record. One task, one wake, one row: in
#: one run a task runs in exactly one job and one shard, so neither cell is in
#: the key - with them, a shard split that ran one task twice would keep both
#: rows. A re-run's first attempt is already gone by then, through its work unit.
COLLECTION_PRUNE_KEY: Final = ("date", "run_id", "task")


# What makes two rows of one council step the same record. A once-a-date step
# has an empty part index; a repeated attempt at the same key is settled by the
# door's writer identity, which keeps the highest attempt.
COUNCIL_RUN_RECORD_KEY: Final = (
    "date",
    "run_id",
    "judge_id",
    "evaluation_step",
    "work_part_index",
)


# One plan is the settled planning answer for one execution of one UTC day.
RUN_PLAN_KEY: Final = ("date", "run_id")


#: What makes two eval rows the same measurement. The address says which article,
#: the digest says which words came out, and the scorer version says which
#: instrument read them. Change any one and the row is a new measurement worth
#: keeping. `item_id` is deliberately absent: it is a slot on a page, not an
#: identity. It carries no date either, so a read of named days keeps one row
#: per measurement each day, and a read of the whole ledger keeps the first row
#: across every day.
OBSERVATION_KEY: Final = ("url_key", "output_digest", "scorer_version")


#: What makes two validation rows the same record. One candidate, judged once,
#: by one execution. `run_id` is in the key because two dispatches of one model
#: on one day are two verdicts about two trees, and the committed ledger held
#: exactly that pair - drop it and the settlement would keep whichever was filed
#: first. `model_id` is in it because a dispatch judges one candidate and the
#: golden set judges several, so a date and a run alone would collapse them.
VALIDATION_KEY: Final = ("date", "run_id", "model_id")


#: What makes two first-sight rows the same record. One address, first seen by
#: one run. The plan stage files an address once, in the run that first sees it,
#: so a second row holding both cells is that sighting written twice, cell for
#: cell. The first row wins, and there is nothing for a preference to choose
#: between.
SEEN_KEY: Final = ("url_key", "first_seen_run")


#: What makes two published rows the same record. One address, run on one digest
#: day as one item. A second row holding all three cells is that item filed
#: again, cell for cell, so the first row wins and there is nothing for a
#: preference to choose between.
PUBLISHED_KEY: Final = ("url_key", "published_on", "item_id")


#: Which of two rows holding one key survives the settlement. `True` means the
#: later row replaces the one already kept. A key with no rule keeps the first
#: row it saw, which is what every ledger but one wants: there a repeat is the
#: same attempt written twice and the two rows agree.
Preference = Callable[[dict[str, str], dict[str, str]], bool]


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
    """A row that names the machine which ran the item beats one that does not.

    `ITEM_HEALTH_KEY` carries no machine cell, and two jobs write a row for the
    same item: a work shard as the item settles, and assemble over the whole day
    afterwards. For an item a shard sealed a record for the two rows agree cell
    for cell (`telemetry.census_row` prefers the sealed row on both sides), so
    this decides nothing. For an item no shard sealed one, the shard's rebuild
    carries `machine_job` and `machine_shard` - the one moment either is known -
    and assemble's rebuild leaves both empty, because it runs once for the whole
    day on a machine that read none of the items.

    Until 2026-09-18 that was settled by arrival order: the work job committed
    first and the append kept the first row for a key. A reader that sorts files
    by name puts `assemble` before `work`, so the order would have silently
    reversed. The preference says out loud what the order used to decide.

    It beats attempt order too. A later attempt that reached no item leaves
    `machine_job` empty, and a row carrying the machine is better evidence than
    a row that does not, whichever run wrote it.
    """
    return bool(later.get("machine_job")) and not kept.get("machine_job")


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


#: The headings a day file an earlier run wrote still carries that the current
#: judged-pair row no longer names. A dropped heading has no replacement - the
#: file still re-files, and the cell goes, which is the point of dropping it. One
#: column has left this row and none has moved, so there is no retired half:
#: `from_csv_row` reads a day file by the names the contract holds now and the
#: dropped heading simply goes.
STORY_SIMILARITY_PAIR_CARRIED: Final[frozenset[str]] = DROPPED_PAIR_CELLS


#: The same again, for the fitted line's day files.
FITTED_SIMILARITY_THRESHOLD_CARRIED: Final[frozenset[str]] = DROPPED_FIT_CELLS


class _DoorShape(NamedTuple):
    """One door ledger's answer to "what settles two of its rows, and who reads one"."""

    key: tuple[str, ...]
    model: type[Contract]


#: What settles two rows of each ledger the door files under the two roots, and
#: the contract that reads one. The compaction settles a period by it and the
#: reader in `ledger/ledger_files.py` settles a whole ledger by it, so the two
#: cannot disagree about which row of a key survives.
#:
#: A ledger still on CSV has its row here before it moves. Nothing asks the door
#: about a ledger before the registry files it under the two roots, so a row here
#: changes nothing until then, and the change that moves the ledger switches its
#: registry grain rather than writing its key a second time.
_DOOR_SHAPES: Final[dict[LedgerName, _DoorShape]] = {
    LedgerName.GARDENER: _DoorShape(COLLECTION_PRUNE_KEY, CollectionPruneRow),
    LedgerName.VISUAL_PRUNES: _DoorShape(VISUAL_PRUNE_KEY, VisualPruneRow),
    LedgerName.FEED_RETIREMENTS: _DoorShape(FEED_RETIREMENT_KEY, FeedRetirementRow),
    LedgerName.ITEM_HEALTH: _DoorShape(ITEM_HEALTH_KEY, ItemHealthRow),
    LedgerName.ITEM_HEALTH_SUMMARY: _DoorShape(ITEM_HEALTH_SUMMARY_KEY, ItemHealthSummaryRow),
    LedgerName.SUMMARY_QUALITY_EVALS: _DoorShape(OBSERVATION_KEY, EvalRow),
    LedgerName.HOST_FINGERPRINT: _DoorShape(HOST_FINGERPRINT_KEY, HostFingerprintRow),
    LedgerName.COUNTERFACTUAL_SCORES: _DoorShape(COUNTERFACTUAL_SCORE_KEY, CounterfactualScoreRow),
    LedgerName.CANDIDATE_MODELS: _DoorShape(VALIDATION_KEY, ValidationRow),
    LedgerName.FEED_HEALTH: _DoorShape(FEED_HEALTH_KEY, FeedHealthRow),
    LedgerName.SEEN: _DoorShape(SEEN_KEY, SeenRow),
    LedgerName.PUBLISHED: _DoorShape(PUBLISHED_KEY, PublishedRow),
    LedgerName.RUN_PLAN: _DoorShape(RUN_PLAN_KEY, RunPlan),
    LedgerName.COUNCIL_RUN_RECORDS: _DoorShape(
        COUNCIL_RUN_RECORD_KEY, CouncilRunRecord
    ),
    LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS: _DoorShape(
        STORY_SIMILARITY_PAIR_KEY, StorySimilarityPair
    ),
    LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS: _DoorShape(
        CONTENT_SIMILARITY_JUDGE_METRICS_KEY, ContentSimilarityJudgeMetrics
    ),
}


def _door_shape(ledger: LedgerName) -> _DoorShape:
    """This ledger's row of the door table, or a refusal naming it."""
    held = _DOOR_SHAPES.get(ledger)
    if held is None:
        raise ValueError(
            f"{ledger.value} has no key and no row contract in the door table in "
            "idhazh/ledger/keys.py, so nothing can settle or read its files"
        )
    return held


def door_contract(ledger: LedgerName) -> type[Contract]:
    """The contract one row of this door ledger is read by."""
    return _door_shape(ledger).model


def door_key(ledger: LedgerName) -> tuple[str, ...]:
    """What makes two rows of this door ledger the same record."""
    return _door_shape(ledger).key
