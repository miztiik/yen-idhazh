"""Who writes each ledger, and which commit label's job stages it.

Both facts used to be derived: walked out of the package's own source with
`ast`/`inspect` so a hand-written list could not drift from the code. The walk
cost grew with the package (OWNER RULING 2026-10-03, "no read may grow with the
repository") and two of its tests ran to several seconds each on CI. A writer
joins this package in the same change that gives a ledger its first row
(CLAUDE.md Guardrail #3), so the fact is already known the day the code is
written; this module writes it down instead of re-deriving it on every test
run.

A row here is a fact about one `LedgerName`, so it is written once and read by
`backend/tests/workflows/test_ledger_staging.py` and
`backend/tests/workflows/test_ledger_door_jobs.py`. Nothing here is a persisted
payload: it ships inside this package and is replaced the day the code it
describes changes, so CLAUDE.md section 11's versioning does not apply to it -
that section is scoped to a file a later run reads back, and nothing writes
this one at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain

from . import paths


@dataclass(frozen=True)
class LedgerStaging:
    """One ledger's writer, and the commit labels whose job must stage it.

    `writer` is read by a person: what fills the ledger, in prose, and why if
    there is nothing to follow in Python. `symbol` is the same fact read by
    `test_every_store_is_filled_by_a_writer_this_test_can_follow`, which
    resolves it with `importlib` - a renamed or deleted writer fails that test
    rather than going unchecked. `symbol` is `None` only where there is no
    single resolvable attribute to point at: a person's own run, or a
    capability still ahead of its writer (Guardrail #3). The two fields can
    disagree in only one direction - `symbol` is `None` only when `writer`
    says there is nothing to follow - so a filled-in `symbol` always has a
    `writer` to match.

    `job_labels` is the subset of `{"plan", "work", "assemble"}` - the three
    `digest.yml` commit labels `_harness.COMMIT_STAGED_PATHS` covers - whose
    job must stage this ledger's path, checked by
    `test_every_store_is_staged_by_the_job_whose_stage_writes_it`. Empty means
    no `digest.yml` commit job writes it today: a council tenant resolved from
    config, a gardener task (its own workflow, not a commit label here), or a
    person's own run. `job_labels` and `symbol` are independent facts - a
    ledger can be written by resolvable Python and still carry no job label,
    because the module that calls it is reached only through a tenant or a
    gardener task rather than through a `digest.yml` job.
    """

    writer: str
    symbol: str | None
    job_labels: frozenset[str]


#: Every `LedgerName`, and the two facts above for each. Declared by hand
#: (Guardrail #3) rather than derived, so a ledger joins this table in the
#: same commit that gives it a writer - never before, and never silently
#: after.
REGISTRY: Final[dict[LedgerName, LedgerStaging]] = {
    LedgerName.SEEN: LedgerStaging(
        writer="idhazh.ledger.rows.append_seen, called by `python -m idhazh plan`",
        symbol="idhazh.ledger.rows.append_seen",
        job_labels=frozenset({"plan"}),
    ),
    LedgerName.FEED_HEALTH: LedgerStaging(
        writer=(
            "idhazh.ledger.persist, called by idhazh.stages.plan.stage_plan and the canary"
        ),
        symbol="idhazh.ledger.persist",
        job_labels=frozenset({"plan"}),
    ),
    LedgerName.ITEM_HEALTH: LedgerStaging(
        writer=(
            "idhazh.stages.record.stage_record, and idhazh.stages.assemble.stage_assemble "
            "over the day's catch-up, both through the ledger door"
        ),
        symbol="idhazh.stages.record.stage_record",
        job_labels=frozenset({"work", "assemble"}),
    ),
    LedgerName.HOST_FINGERPRINT: LedgerStaging(
        writer=(
            "idhazh.telemetry.silicon.stage_fingerprint and .stage_job_clock, run once "
            "per job by every `python -m idhazh <verb>` that carries the probe"
        ),
        symbol="idhazh.telemetry.silicon.stage_fingerprint",
        job_labels=frozenset({"plan", "work", "assemble"}),
    ),
    LedgerName.SUMMARY_QUALITY_EVALS: LedgerStaging(
        writer=(
            "idhazh.evals.writer.file_measurements, called by a work shard as each item "
            "settles and by assemble over the whole day afterwards"
        ),
        symbol="idhazh.evals.writer.file_measurements",
        job_labels=frozenset({"work", "assemble"}),
    ),
    LedgerName.CANDIDATE_MODELS: LedgerStaging(
        writer=(
            "idhazh.stages.decide.stage_decide and idhazh.stages.qualify_decide."
            "stage_qualify_decide, under `python -m idhazh decide` / `qualify-decide`. "
            "Neither verb runs inside a `digest.yml` commit job"
        ),
        symbol="idhazh.stages.decide.stage_decide",
        job_labels=frozenset(),
    ),
    LedgerName.ITEM_HEALTH_SUMMARY: LedgerStaging(
        writer=(
            "idhazh.ledger.rows.write_item_health_summary, called by the gardener's "
            "monthly roll-up (idhazh.gardener.tasks.telemetry_aggregate) - its own "
            "workflow, not a `digest.yml` commit job"
        ),
        symbol="idhazh.ledger.rows.write_item_health_summary",
        job_labels=frozenset(),
    ),
    LedgerName.PUBLISHED: LedgerStaging(
        writer="idhazh.ledger.rows.append_published, called by `python -m idhazh assemble`",
        symbol="idhazh.ledger.rows.append_published",
        job_labels=frozenset({"assemble"}),
    ),
    LedgerName.FEED_RETIREMENTS: LedgerStaging(
        writer=(
            "idhazh.telemetry.source_health.file_retirements, called from both the plan "
            "stage's five `410 Gone` answers and the assemble stage's low-yield fold"
        ),
        symbol="idhazh.telemetry.source_health.file_retirements",
        job_labels=frozenset({"plan", "assemble"}),
    ),
    LedgerName.VISUAL_PRUNES: LedgerStaging(
        writer=(
            "idhazh.gardener.tasks.visual_prune.run, the gardener's own task - its own "
            "workflow, not a `digest.yml` commit job"
        ),
        symbol="idhazh.gardener.tasks.visual_prune.run",
        job_labels=frozenset(),
    ),
    LedgerName.COUNTERFACTUAL_SCORES: LedgerStaging(
        writer="idhazh.stages.plan.stage_plan, through the ledger door",
        symbol="idhazh.stages.plan.stage_plan",
        job_labels=frozenset({"plan"}),
    ),
    LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS: LedgerStaging(
        writer=(
            "idhazh.ledger.rows.append_story_similarity_pairs, called from the "
            "council's tenant module, resolved from config at call time rather than "
            "dispatched from a `digest.yml` job"
        ),
        symbol="idhazh.ledger.rows.append_story_similarity_pairs",
        job_labels=frozenset(),
    ),
    LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS: LedgerStaging(
        writer=(
            "idhazh.ledger.rows.append_fitted_thresholds, called by "
            "idhazh.stages.set_merge_line - the content-similarity judge's tenant "
            "module, resolved from config rather than dispatched from a `digest.yml` job"
        ),
        symbol="idhazh.ledger.rows.append_fitted_thresholds",
        job_labels=frozenset(),
    ),
    LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS: LedgerStaging(
        writer=(
            "a person, typing the marks, or the labelling loop in "
            "backend/utilities/sample_sheet.py harvesting them back - no job stages it "
            "because no job writes it"
        ),
        symbol=None,
        job_labels=frozenset(),
    ),
    LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION: LedgerStaging(
        writer=(
            "the council's shipping capability, through idhazh.similarity.tenant and "
            "idhazh.stages.count_verdicts: both write the record straight to its "
            "address rather than calling a ledger writer"
        ),
        symbol=None,
        job_labels=frozenset(),
    ),
    LedgerName.CONTENT_SIMILARITY_JUDGE_ARCHIVE: LedgerStaging(
        writer="the fold, on the day a stamp under the record moves - nothing fills it yet",
        symbol=None,
        job_labels=frozenset(),
    ),
    LedgerName.LLM_COUNCIL_SHARD_OUTCOMES: LedgerStaging(
        writer=(
            "idhazh.ledger.rows.append_council_shard_outcomes, called from the "
            "council's tenant module, resolved from config at call time rather than "
            "dispatched from a `digest.yml` job"
        ),
        symbol="idhazh.ledger.rows.append_council_shard_outcomes",
        job_labels=frozenset(),
    ),
    LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS: LedgerStaging(
        writer=(
            "the council's shipping capability, which renders a tenant's row rather "
            "than calling a ledger writer - nothing fills it yet"
        ),
        symbol=None,
        job_labels=frozenset(),
    ),
    LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES: LedgerStaging(
        writer=(
            "a person, running `python -m idhazh score-merge-line-holdout`. The marked "
            "file changes when somebody labels more pairs rather than when a day "
            "publishes, so nothing in the daily pipeline calls it and no job stages it"
        ),
        symbol=None,
        job_labels=frozenset(),
    ),
    LedgerName.TRACES: LedgerStaging(
        writer=(
            "idhazh.stages.work.trace_sink opens a file sink on its own path helper "
            "for a work shard that has tracing enabled"
        ),
        symbol="idhazh.stages.work.trace_sink",
        job_labels=frozenset({"work"}),
    ),
    LedgerName.DAY_METRICS: LedgerStaging(
        writer=(
            "idhazh.telemetry.publish.day_metrics.write, one JSON record per published "
            "day, called by `python -m idhazh assemble`"
        ),
        symbol="idhazh.telemetry.publish.day_metrics.write",
        job_labels=frozenset({"assemble"}),
    ),
    LedgerName.DIGEST_FRAGMENTS: LedgerStaging(
        writer=(
            "idhazh.stages.assemble.stage_assemble, writing one JSON block per run of a "
            "date through the path idhazh.assemble.fragment_path names, called by "
            "`python -m idhazh assemble`"
        ),
        symbol="idhazh.assemble.fragment_path",
        job_labels=frozenset({"assemble"}),
    ),
    LedgerName.GARDENER: LedgerStaging(
        writer=(
            "idhazh.gardener.runner._record, the gardener's own ledger of its own "
            "shard - its own workflow, not a `digest.yml` commit job"
        ),
        symbol="idhazh.gardener.runner._record",
        job_labels=frozenset(),
    ),
}


def staged_path(ledger: LedgerName) -> str:
    """Where `ledger` sits under `state/`, relative and POSIX, for a parity check.

    Dispatches on the registry's own grain (`backend/idhazh/contracts/ledgers.py`),
    the same fact `backend/idhazh/ledger/paths.py` dispatches on, so the two
    cannot name two different addresses for one ledger. O(1): one dict lookup
    and one string join, never a read of `state/` itself.
    """
    held = paths.entry(ledger)
    if held.grain is Grain.RAW_AND_COMPACT:
        return paths.raw_root(Path(paths.STATE_DIRNAME), ledger).as_posix()
    if held.grain is Grain.FLAT:
        return paths.relpath(ledger)
    return paths.tree_relpath(ledger)
