"""What does this judge present to the council that hosts it?

One object with the seven members the venue's protocol asks for, each bound to a
stage this judge already has. It imports the protocol and the shipping
capability from the council, and the council imports nothing of this: a tenant
knows where it runs, a venue knows nobody. Registration is a slug in
`judge_names` in `config/llm_council.json` and this module answering to it.

**This file routes and it ships. It judges nothing.** Every unit of work is a
stage in its own module, which is what lets one be run on its own with a file in
and a file out (CLAUDE.md section 1a).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Final

from idhazh import config, ledger
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge.ledger_reads import (
    load_pair_verdicts,
    load_pair_verdicts_filed_on,
    review_days,
)
from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_invocation import (
    JudgeSchedule,
    PreparationReceipt,
    ScheduleRequest,
    ShardReport,
)
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.council import metrics_sink, session
from idhazh.council.tenancy import ShardResult
from idhazh.ledger import staging
from idhazh.ledger.window_inputs import inputs_of_days
from idhazh.similarity.budget import refuse_a_night_this_tenant_cannot_finish

#: This judge's own slug, named here because this is the module the council reads
#: it off: a second spelling of the string is a second thing to keep in step with
#: the registration in `config/llm_council.json`.
JUDGE_ID: Final = "content-similarity-judge"

#: Every ledger this judge's own work writes: the judged pairs, and the two thresholds
#: each night's pairs put them at.
WRITTEN_LEDGERS: Final = (
    LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS,
    LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY,
)

#: Where each of those ledgers sits, as the collecting job stages it. Read off
#: the registry rather than spelled, so a ledger that moves onto the ledger door
#: is staged under `state/raw/` in the change that moves it, and no path a
#: ledger left behind is staged for ever after.
COMMITTED_PATHS: Final = tuple(staging.staged_path(which) for which in WRITTEN_LEDGERS)

#: The slot this judge's units leave their verdicts in, beside the slots the
#: venue names for itself. A slot of its own rather than the venue's selection
#: one: the workflow uploads the selection once from the job that picked the
#: work and excludes it from every unit's own upload, so a verdict written there
#: would never reach the job that counts it.
VERDICTS_DIRNAME: Final = "verdicts"

__all__ = ["JUDGE_ID", "TENANT", "refuse_a_night_this_tenant_cannot_finish"]


class ContentSimilarityJudge:
    """The content-similarity judge, as the council sees it.

    Stateless. Every member reads the committed config when it runs, so an
    operator who moves a knob does not also have to think about when this object
    was built.
    """

    @property
    def judge_id(self) -> str:
        return JUDGE_ID

    @property
    def shard_count(self) -> int:
        """How many ways this judge's work splits: the width the draw is dealt at.

        The selection deals every drawn pair a shard number, and a unit reads the
        pairs carrying its own. Answering anything else here would leave the
        difference unread, with every unit reporting success.
        """
        return config.load_council().shards

    @property
    def committed_paths(self) -> tuple[str, ...]:
        return COMMITTED_PATHS

    def publication_inputs(self, *, date: str) -> tuple[str, ...]:
        """The ledger files the night's review reads, named from the days it reads.

        The collecting job reads from a sparse checkout, and the review reads the last
        nights of `pair-verdicts` and the history of `threshold-history`. `review_days` names
        those days for the stage and for this declaration alike, and
        `idhazh.ledger.window_inputs` turns them into the raw folders, compact files and
        indexes that reading them could open. The loaders do not fail on a file that is not
        there; they read a shorter window, which is why the review also checks the history it
        read against the thresholds the draw followed.

        One config read and date arithmetic, because a declaration that raises costs the
        night its rows: it runs before the night is settled.
        """
        days = review_days(date, config=judge_settings.load())
        return tuple(
            sorted(
                {
                    *inputs_of_days(
                        LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS, days.pair_verdicts
                    ),
                    *inputs_of_days(
                        LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY,
                        days.threshold_history,
                    ),
                }
            )
        )

    def nights_outstanding(
        self, *, window: tuple[DateStamp, ...], state_dir: Path | None = None
    ) -> tuple[DateStamp, ...]:
        """Which nights inside the council's window have no pair-verdict row.

        The window is handed in and is a handful of nights, so this reads the same few
        days on the thousandth night as on the first (CLAUDE.md Guardrail #12): the ledger
        is asked for exactly those days and never walked.

        **A night is outstanding when nothing has been filed for it.** Any one row
        settles it: a night that lost a unit and filed the rows of the others is not
        named again, since a repeat judges the whole night over and the evidence for
        the thresholds counts each pair once. What it does name is a night that died
        before it filed anything, and a night that drew nothing, which stays named
        until it leaves the window.

        **A night the gardener recorded as quiet and the judge has repaired since is
        filed too.** The ledger door serves such a day from the record and never opens
        the raw files filed after it, so each window day's raw files are read as well.
        Without that, a repaired night would be named every night until the next
        compaction packed it.

        **An empty ledger names every night of the window.** A judge that has filed
        nothing is behind on all of them, and the council's repair budget lets only a few
        through a night, so the window fills over a few nights rather than at once.

        `state_dir` is this judge's own test seam and the council never passes it. The
        default is the root the collecting job files under, so the reader and the writer
        cannot drift apart.
        """
        state = state_dir if state_dir is not None else config.REPO_ROOT / ledger.STATE_DIRNAME
        filed = {row.date for row in load_pair_verdicts(state, window)}
        filed |= {night for night in window if load_pair_verdicts_filed_on(state, night)}
        return tuple(night for night in window if night not in filed)

    def schedule(self, *, request: ScheduleRequest) -> JudgeSchedule:
        """Choose the anchor, then the newest unread dates within both budgets."""
        dates = [request.anchor_date]
        older = sorted(
            (
                night
                for night in self.nights_outstanding(window=request.window)
                if night < request.anchor_date
            ),
            reverse=True,
        )
        dates.extend(older[: min(request.max_older_dates, max(0, request.max_dates - len(dates)))])
        return JudgeSchedule(dates=tuple(dates))

    def prepare(self, *, date: DateStamp, run_id: RunId, shards: int) -> ShardResult:
        """Score the day's cross-source pairs again and deal the draw.

        No model and no socket, so the venue's cost cells stay empty: this judge
        knows it ran no call, and a zero there would read as a call that cost
        nothing.
        """
        from idhazh.stages import common, pick_item_pairs

        settings = config.load()
        settings = replace(settings, council=settings.council.model_copy(update={"shards": shards}))
        drawn = pick_item_pairs.stage_pick_item_pairs(
            date,
            run_id=run_id,
            settings=settings,
            draw_path=_draw_path(date),
            digest_root=common.PUBLIC_ROOT,
            state_dir=common.STATE_ROOT,
        )
        return ShardResult(
            outcome=ShardOutcome.COMPLETED if drawn.taken else ShardOutcome.NOTHING_TO_DO,
            files=(session.artifact_path(_draw_path(date)),),
        )

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
        prepared: PreparationReceipt,
    ) -> ShardResult:
        """Judge the pairs this unit owns, then ship what the instrument read.

        The known-answer pairs come from config and are handed to the stage, which judges the
        ones this unit was dealt before its own pairs and puts their answers on the reading.

        The row goes out through the venue's own capability, which writes it
        under the columns its contract names - so a cell this judge declares and
        this unit did not fill fails on this runner rather than arriving in a
        committed ledger as an empty string.
        """
        from idhazh.stages import common, judge_item_pairs
        from idhazh.stages.common import LOG

        settings = config.load()
        report = judge_item_pairs.stage_judge_item_pairs(
            date,
            run_id=run_id,
            shard=shard,
            shards=shards,
            settings=settings,
            digest_root=common.PUBLIC_ROOT,
            draw_path=_draw_path(date),
            verdict_path=_verdict_path(date, shard=shard),
            deadline=deadline,
            canary_pairs=judge_settings.load_canaries(settings.config_dir).pairs,
        )
        shipped = metrics_sink.ship_judge_metrics(
            report.metrics, judge_id=JUDGE_ID, name=str(shard), out_dir=_shipping_dir(date)
        )
        LOG.info(
            "content-similarity-judge shipped its reading of shard=%s date=%s to %s",
            shard,
            date,
            shipped.name,
        )
        return ShardResult(
            outcome=report.outcome,
            model_calls=report.model_calls,
            tokens_in=report.tokens_in,
            tokens_out=report.tokens_out,
            model_seconds=report.model_seconds,
            files=(
                session.artifact_path(_verdict_path(date, shard=shard)),
                session.artifact_path(shipped),
            ),
        )

    def settle(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        state_dir: Path,
        identity: WriterIdentity,
        prepared: PreparationReceipt,
        reports: tuple[ShardReport, ...],
    ) -> ShardResult:
        """File what the units judged, then where the night's pairs put both thresholds.

        A night files whatever its units returned, so the reports say nothing the
        files do not: a unit that died left no file, or a file of the pairs it had
        finished, and either way the rows that exist are the rows that are filed.
        The thresholds are reviewed from the ledger afterwards. The sample readings
        instead use only the exact batch this attempt filed.

        The stages write under the state root the council handed over, and file
        their rows through the ledger door under the council's writer identity,
        each naming itself as the producer.
        """
        from idhazh.stages import file_pair_verdicts, review_thresholds

        filed = file_pair_verdicts.stage_file_pair_verdicts(
            date,
            run_id=run_id,
            judge_id=JUDGE_ID,
            shipped_root=_shipping_dir(date),
            verdicts_dir=_verdicts_dir(date),
            identity=identity,
            expected_shards=prepared.shards,
            state_dir=state_dir,
        )
        reviewed = review_thresholds.stage_review_thresholds(
            date,
            run_id=run_id,
            judge_id=JUDGE_ID,
            shipped_root=_shipping_dir(date),
            draw_path=_draw_path(date),
            filed_rows=filed.filed_rows,
            identity=identity,
            expected_shards=prepared.shards,
            state_dir=state_dir,
            config_dir=config.DEFAULT_CONFIG_DIR,
        )
        return ShardResult(
            outcome=(
                ShardOutcome.COMPLETED
                if filed.rows_filed or reviewed.filed
                else ShardOutcome.NOTHING_TO_DO
            )
        )


def _draw_path(date: DateStamp) -> Path:
    """The one file this judge's selection unit writes and every judging unit reads.

    Asked of the venue rather than spelled here, because the draw crosses two
    jobs: it is written on the runner that picks the work and read on eight
    others that never met it. Only a path inside the root the council carries
    makes that trip.
    """
    return session.unit_file(date, slot=session.SELECTION_DIRNAME, judge_id=JUDGE_ID)


def _verdict_path(date: DateStamp, *, shard: int) -> Path:
    """Where one judging unit writes what it judged, for the job that counts it."""
    return session.unit_file(date, slot=VERDICTS_DIRNAME, judge_id=JUDGE_ID, shard=shard)


def _verdicts_dir(date: DateStamp) -> Path:
    """Where the settling unit looks for what every judging unit left.

    The parent of what `_verdict_path` writes, derived rather than spelled again:
    a reader and a writer that each name a directory are a reader and a writer
    that can end up in different ones, which is how a night comes back counting
    nothing and reporting success.
    """
    return session.unit_dir(date, slot=VERDICTS_DIRNAME, judge_id=JUDGE_ID)


def _shipping_dir(date: DateStamp) -> Path:
    """Where this judge's units leave their rows for the collecting job.

    Under the venue's own scratch root, because the venue is what carries a
    directory between two jobs as an artifact. What goes inside it is this
    judge's business and the venue reads no file in it.
    """
    return session.scratch_root(date) / session.METRICS_DIRNAME


TENANT: Final = ContentSimilarityJudge()
