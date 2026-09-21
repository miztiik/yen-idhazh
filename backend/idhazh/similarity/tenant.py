"""What does this judge present to the council that hosts it?

One object with the seven members the venue's protocol asks for, each bound to a
stage this judge already has. It imports the protocol and the shipping
capability from the council, and the council imports nothing of this: a tenant
knows where it runs, a venue knows nobody. Registration is a slug in
`config/idhazh.json` and this module answering to it.

**This file routes and it ships. It judges nothing.** Every unit of work is a
stage in its own module, which is what lets one be run on its own with a file in
and a file out (CLAUDE.md section 1a).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from idhazh import config, ledger
from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_shard_outcome import ShardOutcome
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.contracts.story_similarity_pair import ContentSimilarityJudgeId
from idhazh.council import metrics_sink, session
from idhazh.council.tenancy import ShardResult
from idhazh.similarity.budget import refuse_a_night_this_tenant_cannot_finish
from idhazh.stages import (
    common,
    count_verdicts,
    judge_item_pairs,
    pick_item_pairs,
    set_merge_line,
)
from idhazh.stages.common import LOG

#: This judge's own slug, narrowed to the one member it can be. The closed set
#: is declared once beside the column that holds it, and named here because this
#: is the module the council reads it off - a second spelling of the string is a
#: second thing to keep in step with the store's directory name.
JUDGE_ID: Final[ContentSimilarityJudgeId] = "content-similarity-judge"

#: Everything this judge's own work commits, as one prefix. Every store it fills
#: hangs off its slug, so naming the prefix stages the pairs, the record, the
#: fitted line and the instrument rows in one go - and a store it gains later is
#: staged the day it is written rather than the day somebody remembers this list.
COMMITTED_PATHS: Final = (f"{ledger.STATE_DIRNAME}/{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}",)

__all__ = ["JUDGE_ID", "TENANT", "refuse_a_night_this_tenant_cannot_finish"]


class ContentSimilarityJudge:
    """The content-similarity judge, as the council sees it.

    Stateless. Every member reads the committed config when it runs, so an
    operator who moves a knob does not also have to think about when this object
    was built.
    """

    @property
    def judge_id(self) -> ContentSimilarityJudgeId:
        return JUDGE_ID

    @property
    def shard_count(self) -> int:
        """How many ways this judge's work splits: the width the draw is dealt at.

        The selection deals every drawn pair a shard number, and a unit reads the
        pairs carrying its own. Answering anything else here would leave the
        difference unread, with every unit reporting success.
        """
        return config.load().app.council.shards

    @property
    def committed_paths(self) -> tuple[str, ...]:
        return COMMITTED_PATHS

    def nights_outstanding(
        self, *, window: tuple[DateStamp, ...], state_dir: Path | None = None
    ) -> tuple[DateStamp, ...]:
        """Which nights inside the council's window this judge has never read.

        The record is one file of a fixed size and the window is handed in, so
        this costs the same on the thousandth night as on the first (CLAUDE.md
        Guardrail #12). No day file is opened and no directory is listed.

        **A night is outstanding when the record has no memory of it at all.**
        `judged_dates` holds every date this judge has ever counted, including
        the ones an instrument move archived the counts for, so a date the record
        once read is never named again. That is deliberate: the counts for it are
        gone and a re-judge would not bring them back, because the record refuses
        to count a date twice. Naming it would buy a runner-night of work that
        cannot land.

        **What it does name is the night that died.** A run that lost a shard
        appended every row the surviving shards judged and left the date out of
        both lists, because a partial day cannot be counted and cannot be
        repaired later. That date is in neither list, so it comes back here and
        the next council night dispatches it.

        **No record yet means nothing has been read.** The first run after this
        judge moves in has no file to open, and the council's own floor is what
        keeps the answer from reaching back to the venue's birth.

        `state_dir` is this judge's own test seam and the council never passes
        it. The default is the root the counting verb writes to, so the reader
        and the writer cannot drift apart.
        """
        state = state_dir if state_dir is not None else config.REPO_ROOT / ledger.STATE_DIRNAME
        record_path = ledger.score_distribution_path(state)
        if not record_path.exists():
            return ()
        record = StorySimilarityDistribution.from_json(
            record_path.read_text(encoding="utf-8")
        )
        read = set(record.judged_dates)
        return tuple(night for night in window if night not in read)

    def prepare(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        """Score the day's cross-source pairs again and deal the draw.

        No model and no socket, so the venue's cost cells stay empty: this judge
        knows it ran no call, and a zero there would read as a call that cost
        nothing.
        """
        drawn = pick_item_pairs.stage_pick_item_pairs(
            date, run_id=run_id, settings=config.load()
        )
        return ShardResult(
            outcome=ShardOutcome.COMPLETED if drawn.taken else ShardOutcome.NOTHING_TO_DO
        )

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
    ) -> ShardResult:
        """Judge the pairs this unit owns, then ship what the instrument read.

        The row goes out through the venue's own capability, which writes it
        under the columns its contract names - so a cell this judge declares and
        this unit did not fill fails on this runner rather than arriving in a
        committed store as an empty string.
        """
        report = judge_item_pairs.stage_judge_item_pairs(
            date,
            run_id=run_id,
            shard=shard,
            shards=shards,
            settings=config.load(),
            digest_root=common.PUBLIC_ROOT,
            run_dir=common.JUDGE_ROOT / date,
            deadline=deadline,
        )
        shipped = metrics_sink.ship_judge_metrics(
            report.metrics, judge_id=JUDGE_ID, shard=shard, out_dir=_shipping_dir(date)
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
        )

    def settle(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        """Count what the units judged, collect what they measured, fit the line.

        The fit runs on a counted day and on a held one. A line that moves itself
        has to leave a row on the days it stayed put, or a reader cannot tell a
        day the evidence refused from a day nothing ran.
        """
        settings = config.load()
        counted = count_verdicts.stage_count_verdicts(
            date,
            run_id=run_id,
            judge_id=JUDGE_ID,
            shipped_root=_shipping_dir(date),
            settings=settings,
        )
        set_merge_line.stage_set_merge_line(date, run_id=run_id, settings=settings)
        return ShardResult(
            outcome=ShardOutcome.COMPLETED if counted.counted else ShardOutcome.NOTHING_TO_DO
        )


def _shipping_dir(date: DateStamp) -> Path:
    """Where this judge's units leave their rows for the collecting job.

    Under the venue's own scratch root, because the venue is what carries a
    directory between two jobs as an artifact. What goes inside it is this
    judge's business and the venue reads no file in it.
    """
    return session.scratch_root(date) / session.METRICS_DIRNAME


TENANT: Final = ContentSimilarityJudge()
