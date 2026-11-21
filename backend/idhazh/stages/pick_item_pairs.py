"""Which item pairs from one published day are worth judging, picked and written down.

One stage, one module. The router does not name it: the council reaches it
through the tenant that owns this judge (CLAUDE.md section 1a, "A router is the
sharpest case").

It calls no model and opens no socket. It reads the published days the pairs come
from, and this judge's own threshold history through the ledger door to learn which
two thresholds the night follows. Every verdict column it writes is empty: this step
says which pairs are worth a model's time, and the step that judges them fills the
rest in.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from idhazh import assemble, atomic_write, config, run_context
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge.ledger_reads import load_threshold_history
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.story_similarity_diagnostics import ScorePoolHistogram
from idhazh.contracts.story_similarity_pair_verdict import StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_score_pool import ContentSimilarityScorePool
from idhazh.embed import ENCODER_DIRECTORY
from idhazh.similarity import selection
from idhazh.similarity.score_pool_drift import pool_recipe_stamp, score_pool_histogram
from idhazh.similarity.stamps import ScorerStamp, scorer_inputs
from idhazh.similarity.thresholds_in_force import (
    ThresholdsInForce,
    lookback_days,
    thresholds_in_force,
)
from idhazh.stages.assemble import _earlier_days
from idhazh.stages.common import LOG, _load_day


@dataclass(frozen=True, slots=True)
class PickReport:
    draw: selection.Draw
    score_pool_written: bool


def _within_the_unit_range(value: float) -> float:
    """A cosine or a score is from -1 to 1, and a rounding error past either end is folded back.

    The contract snaps only noise of a billionth, and a dot product over two norms is
    exact to far less, so this is the one place a stray digit is made to fit.
    """
    return max(-1.0, min(1.0, value))


def _drawn_row(
    drawn: selection.DrawnPair,
    *,
    shard: int,
    date: str,
    run_id: str,
    address_of: Mapping[str, str],
    stamp: ScorerStamp,
    followed: ThresholdsInForce,
    versions: str,
) -> StorySimilarityPairVerdict:
    """One pair as the contract holds it, with nothing judged yet.

    The two item ids become address keys here and nowhere deeper. An id is
    minted per day, so a record keyed on one could not recognise the same pair
    tomorrow; the address is what survives, and `source_url` is the canonical
    URL the rest of the pipeline already keys on.

    The thresholds go on the row as the night followed them, unrounded. The slice
    edges are on a grid, so they say where the pair was filed and not which
    thresholds the draw was following.
    """
    pair = drawn.pair
    left, right = sorted((address_of[pair.left], address_of[pair.right]))
    return StorySimilarityPairVerdict(
        version=StorySimilarityPairVerdict.schema_version(),
        date=date,
        run_id=run_id,
        work_part_index=shard,
        pair_key=selection.pair_key(left, right),
        left_url_key=left,
        right_url_key=right,
        similarity_score=_within_the_unit_range(pair.score),
        cosine=_within_the_unit_range(pair.cosine),
        headline=pair.headline,
        scorer_model=stamp.scorer_model,
        cosine_weight=stamp.cosine_weight,
        bucket=drawn.slice.bucket,
        slice_low=drawn.slice.low,
        slice_high=drawn.slice.high,
        slice_pairs_available=drawn.slice_pairs_available,
        slice_pairs_judged=drawn.slice_pairs_judged,
        lower_threshold_in_force=followed.lower,
        upper_threshold_in_force=followed.upper,
        config_versions=versions,
    )


def _as_csv(rows: list[StorySimilarityPairVerdict]) -> str:
    """The draw as the file holds it: the contract's own columns, header first.

    A header goes down even on a day that drew nothing, so a shard that opens the
    file finds an empty draw rather than a missing one.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=StorySimilarityPairVerdict.csv_columns(), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(row.csv_row() for row in rows)
    return buffer.getvalue()


def _write_score_pool(
    path: Path, *, date: str, run_id: str, histogram: ScorePoolHistogram
) -> bool:
    payload = ContentSimilarityScorePool(
        version=ContentSimilarityScorePool.schema_version(),
        date=date,
        run_id=run_id,
        attempt=run_context.run_attempt(),
        histogram=histogram,
    )
    try:
        atomic_write.write_atomic(path, payload.to_json())
    except OSError as error:
        LOG.warning(
            "pick-item-pairs could not write the score pool date=%s run=%s reason=%s",
            date,
            run_id,
            type(error).__name__,
        )
        return False
    return True


def stage_pick_item_pairs(
    date: str,
    *,
    run_id: str,
    settings: config.Settings,
    draw_path: Path,
    digest_root: Path,
    state_dir: Path,
    score_pool_path: Path | None = None,
) -> PickReport:
    """Score one day's cross-source pairs, cut them into slices, deal the shards.

    **This is the day's second scoring pass and it is not free.** The same
    arithmetic inside `assemble` measures a median 22.9 s on the largest day
    with the window open, spread 22.4 to 34.2 s (developer machine, Python
    3.14.2, 2026-09-16, five alternating rounds). This stage runs in its own
    process, so the day pays the pass twice - once to publish and once to draw.
    That is a cost to state rather than one to fix: the alternative is the
    publishing run carrying a step whose output it never reads.

    **The read is bounded by the window and never by the archive** (Guardrail
    #12). One day payload and the `ceil(window / 24)` earlier days
    `_earlier_days` already declares - two at the 36-hour default - and the
    `thresholds_lookback_days` days of threshold history before the night.
    Nothing here walks a collection a run appends to.

    **Only pairs that hold one of the day's own stories are drawn.** The
    grouping pass never weighs two earlier-day stories against each other, so
    such a pair cannot change what publishes, and it already had its turn the
    night the later of the two was new. `assemble.cross_source_pairs` does not
    yield it, which leaves the budget to pairs that have not had theirs. **A pair
    of addresses is drawn once**, whatever number of items carry them. When asked
    for a histogram, tally this same distinct pool before cutting any slices.

    **Pairs at every score are drawn**, from -1 to 1. Which ones, and how many, is
    the slice rule in `idhazh.similarity.selection`: the budget goes mostly to
    the scores around the two thresholds, where the judge's answers decide where the
    thresholds sit, and lightly to the scores far from both. Each row names the slice
    that took it and how many pairs the slice held and gave, which is what lets the
    night's totals be weighed back up to everything the night held.

    **`run_id` is the council's own and is handed in.** The run that scored a
    pair is the run that drew it, which is what the pair row's own column says;
    reading it off the day's manifest filed these rows under a digest run that
    never opened this file. The council mints one name in its planning job and
    passes it here, so a night's rows cannot arrive under two addresses.

    A day that is not on disk writes an empty draw and says why. A missing day
    is nothing to judge rather than a run to fail.

    **`draw_path` is handed in and this stage names no root.** Where the draw
    lands decides whether the units that judge it can read it at all, and that is
    the council's answer rather than this stage's: a path outside the root the
    venue carries between jobs dies with the runner that wrote it.

    **`digest_root` and `state_dir` are handed in for the same reason it is on the
    judging stage.** A default bound here would be read when this module imported,
    so a caller that moved `common.PUBLIC_ROOT` afterwards would still be served
    the tree the import saw.
    """
    execution = judge_settings.load(settings.config_dir)
    draw = execution.draw
    same_story = settings.app.assemble.same_story
    shards = settings.council.shards
    window_hours = settings.app.assemble.same_story_window_hours
    stamp = scorer_inputs(settings)

    day = _load_day(assemble.day_dir(digest_root, date) / "digest.json")
    if day is None:
        LOG.warning(
            "pick-item-pairs found no published day to read date=%s out=%s",
            date,
            draw_path.name,
        )
        atomic_write.write_atomic(draw_path, _as_csv([]))
        return PickReport(
            draw=selection.Draw(taken=[], pairs_available=0), score_pool_written=False
        )

    earlier = _earlier_days(date, window_hours=window_hours)
    by_id: dict[str, DigestItem] = {item.item_id: item for item in day.items}
    for block in earlier:
        # Today's copy of an address that published twice wins, which is the
        # precedence the grouping pass applies to the same two blocks.
        by_id.update({one.item_id: one for one in block.items if one.item_id not in by_id})
    address_of = {item_id: derive_url_key(one.source_url) for item_id, one in by_id.items()}

    followed = thresholds_in_force(
        load_threshold_history(
            state_dir, lookback_days(date, within_days=draw.thresholds_lookback_days)
        ),
        night=date,
        within_days=draw.thresholds_lookback_days,
        lower_start=execution.thresholds.lower_start,
        upper_start=execution.thresholds.upper_start,
    )
    group_identical_titles = settings.app.assemble.group_identical_titles
    pool = selection.one_pair_a_key(
        assemble.cross_source_pairs(
            day.items,
            day.embeddings,
            same_story=same_story,
            group_identical_titles=group_identical_titles,
            window_hours=window_hours,
            earlier=earlier,
        ),
        address_of=address_of,
        own={item.item_id for item in day.items},
    )
    score_pool_written = False
    if score_pool_path is not None:
        histogram = score_pool_histogram(
            (_within_the_unit_range(pair.score) for pair in pool),
            bins=execution.diagnostics.score_bins,
            stamp=pool_recipe_stamp(
                stamp,
                encoder_revision=ENCODER_DIRECTORY,
                group_identical_titles=group_identical_titles,
                window_hours=window_hours,
            ),
        )
        score_pool_written = _write_score_pool(
            score_pool_path, date=date, run_id=run_id, histogram=histogram
        )
    drawn = selection.select(
        pool,
        lower=followed.lower,
        upper=followed.upper,
        draw=draw,
        date=date,
        stamp=stamp,
    )
    versions = judge_settings.config_versions(settings.config_dir)
    rows = [
        _drawn_row(
            one,
            shard=shard,
            date=date,
            run_id=run_id,
            address_of=address_of,
            stamp=stamp,
            followed=followed,
            versions=versions,
        )
        for shard, one in selection.assign_shards(drawn.taken, shards=shards)
    ]
    atomic_write.write_atomic(draw_path, _as_csv(rows))
    LOG.info(
        "pick-item-pairs date=%s run=%s available=%s drawn=%s budget=%s lower=%s upper=%s "
        "thresholds_set_on=%s by_bucket=%s shards=%s out=%s",
        date,
        run_id,
        drawn.pairs_available,
        len(rows),
        draw.pair_budget,
        followed.lower,
        followed.upper,
        followed.set_on or "the configured starts",
        dict(sorted(Counter(row.bucket.value for row in rows).items())),
        shards,
        draw_path.name,
    )
    return PickReport(draw=drawn, score_pool_written=score_pool_written)
