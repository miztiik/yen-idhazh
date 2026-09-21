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

    def nights_outstanding(self, *, window: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        """Which nights inside the council's window this judge has not counted.

        None yet. Naming a night here dispatches a repair job for it, and what
        this judge has counted is not read back by anything - so every answer but
        an empty one would spend a runner on work nobody can tell was needed.
        Tonight is planned whatever this returns, so saying nothing costs the
        night nothing.
        """
        return ()

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
