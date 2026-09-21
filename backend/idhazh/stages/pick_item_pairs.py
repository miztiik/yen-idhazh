"""Which item pairs from one published day are worth judging, picked and written down.

One stage, one module. The router does not name it: the council reaches it
through the tenant that owns this judge (CLAUDE.md section 1a, "A router is the
sharpest case").

It calls no model, opens no socket and reads nothing under `state/`. Every
verdict column it writes is empty: this step says which pairs are worth a
model's time, and the step that judges them fills the rest in.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path

from idhazh import assemble, config
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.similarity import selection
from idhazh.similarity.stamps import ScorerStamp, scorer_inputs
from idhazh.stages import common
from idhazh.stages.assemble import _earlier_days
from idhazh.stages.common import LOG, _load_day

#: What the shards read. One name per day, because a day has one draw.
DRAW_FILENAME = "draw.csv"


def draw_relpath(date: str) -> str:
    """`backend/var/judge/<date>/draw.csv` - POSIX, for a log line."""
    return f"{common.JUDGE_ROOT_RELPATH}/{date}/{DRAW_FILENAME}"


def _drawn_row(
    pair: assemble.ScoredPair,
    *,
    shard: int,
    date: str,
    run_id: str,
    by_id: Mapping[str, DigestItem],
    stamp: ScorerStamp,
) -> StorySimilarityPair:
    """One pair as the contract holds it, with nothing judged yet.

    The two item ids become address keys here and nowhere deeper. An id is
    minted per day, so a record keyed on one could not recognise the same pair
    tomorrow; the address is what survives, and `source_url` is the canonical
    URL the rest of the pipeline already keys on.
    """
    left, right = sorted(
        (
            derive_url_key(by_id[pair.left].source_url),
            derive_url_key(by_id[pair.right].source_url),
        )
    )
    return StorySimilarityPair(
        version=StorySimilarityPair.schema_version(),
        date=date,
        run_id=run_id,
        shard=shard,
        pair_key=selection.pair_key(left, right),
        left_url_key=left,
        right_url_key=right,
        composite_score=pair.score,
        cosine=pair.cosine,
        key_point=pair.key_points,
        headline=pair.headline,
        scorer_model=stamp.scorer_model,
        cosine_weight=stamp.cosine_weight,
        key_point_weight=stamp.key_point_weight,
    )


def _as_csv(rows: list[StorySimilarityPair]) -> str:
    """The draw as the file holds it: the contract's own columns, header first.

    A header goes down even on a day that drew nothing, so a shard that opens the
    file finds an empty draw rather than a missing one.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=StorySimilarityPair.csv_columns(), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(row.csv_row() for row in rows)
    return buffer.getvalue()


def stage_pick_item_pairs(
    date: str,
    *,
    run_id: str,
    settings: config.Settings,
    digest_root: Path = common.PUBLIC_ROOT,
    out_dir: Path = common.JUDGE_ROOT,
) -> selection.Draw:
    """Score one day's cross-source pairs, keep the borderline ones, deal the shards.

    **This is the day's second scoring pass and it is not free.** The same
    arithmetic inside `assemble` measures a median 22.9 s on the largest day
    with the window open, spread 22.4 to 34.2 s (developer machine, Python
    3.14.2, 2026-09-16, five alternating rounds). This stage runs in its own
    process, so the day pays the pass twice - once to publish and once to draw.
    That is a cost to state rather than one to fix: the alternative is the
    publishing run carrying a step whose output it never reads.

    **The read is bounded by the window and never by the archive** (Guardrail
    #12). One day payload and the `ceil(window / 24)` earlier days
    `_earlier_days` already declares - one at the 36-hour default. Nothing here
    walks a collection a run appends to.

    **The pairs at or above the line the day was built with are never cut.**
    Those are the merges a reader is already living with, so they are the whole
    of what a later precision figure can be read off; sampling them away would
    leave the run unable to say how many of its own merges were wrong.

    **`run_id` is the council's own and is handed in.** The run that scored a
    pair is the run that drew it, which is what the pair row's own column says;
    reading it off the day's manifest filed these rows under a digest run that
    never opened this file. The council mints one name in its planning job and
    passes it here, so a night's rows cannot arrive under two addresses.

    A day that is not on disk writes an empty draw and says why. A missing day
    is nothing to judge rather than a run to fail.
    """
    same_story = settings.app.assemble.same_story
    tuning = same_story.judging_knobs()
    shards = settings.app.council.shards
    window_hours = settings.app.assemble.same_story_window_hours
    stamp = scorer_inputs(settings)
    path = out_dir / date / DRAW_FILENAME

    day = _load_day(assemble.day_dir(digest_root, date) / "digest.json")
    if day is None:
        LOG.warning(
            "pick-item-pairs found no published day to read date=%s out=%s",
            date,
            draw_relpath(date),
        )
        assemble.write_atomic(path, _as_csv([]))
        return selection.Draw(taken=[], pairs_in_band=0)

    earlier = _earlier_days(date, window_hours=window_hours)
    by_id: dict[str, DigestItem] = {item.item_id: item for item in day.items}
    for block in earlier:
        # Today's copy of an address that published twice wins, which is the
        # precedence the grouping pass applies to the same two blocks.
        by_id.update({one.item_id: one for one in block.items if one.item_id not in by_id})

    banded = selection.in_band(
        assemble.cross_source_pairs(
            day.items,
            day.embeddings,
            same_story=same_story,
            group_identical_titles=settings.app.assemble.group_identical_titles,
            window_hours=window_hours,
            earlier=earlier,
        ),
        band_low=tuning.band_low,
        band_high=tuning.band_high,
    )
    # The line the day was actually grouped at, so a pair the day never merged is
    # never counted as one. A fitted line replaces this floor once a run writes one.
    drawn = selection.select(
        banded, line=same_story.floor_min, budget=tuning.pair_budget, date=date, stamp=stamp
    )
    rows = [
        _drawn_row(pair, shard=shard, date=date, run_id=run_id, by_id=by_id, stamp=stamp)
        for shard, pair in selection.assign_shards(drawn.taken, shards=shards)
    ]
    assemble.write_atomic(path, _as_csv(rows))
    LOG.info(
        "pick-item-pairs date=%s run=%s in_band=%s drawn=%s budget=%s shards=%s out=%s",
        date,
        run_id,
        drawn.pairs_in_band,
        len(rows),
        tuning.pair_budget,
        shards,
        draw_relpath(date),
    )
    return drawn
