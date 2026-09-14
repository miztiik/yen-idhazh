"""Re-encode every closed day whose vectors are not the set its items earned.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from pathlib import Path

from idhazh import (
    assemble,
)
from idhazh.contracts.digest_day import DigestDay
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, ONNX_RELPATH, Embedder, text_for
from idhazh.stages.common import LOG, published_days


def is_closed(date: str, *, today: str) -> bool:
    """True when no scheduled run will append to this day again.

    The current UTC day is the one exclusion and this is why: the pipeline
    appends to it several times an hour, and a day payload is one JSON file
    with no union merge. Two producers writing it at once do not interleave -
    one of them wins whole, and the other one's run is gone.
    """
    return date < today


def earns_a_vector(day: DigestDay, embedder: Embedder) -> set[str]:
    """The item ids this day should carry a vector for, and no others.

    Not every item earns one. An item written in a script the encoder's
    vocabulary does not hold gets a well-formed vector about its characters
    rather than its story, which no query a reader types will ever retrieve, so
    `assist.min_readable_letter_share` excludes it. The count to compare a day
    against is therefore this set and not `len(day.items)`.
    """
    return {item.item_id for item in day.items if embedder.readable(text_for(item))}


def needs_backfill(day: DigestDay, embedder: Embedder) -> bool:
    """Whether this day's vectors are not exactly the set its items earned.

    Short and surplus are one question. A day is short where a run never
    encoded an item, and it is surplus where it carries a vector for an item
    that no longer earns one - and either way the block is not what this
    encoder would write today. A day that already matches answers `False`,
    which is what makes the command safe to dispatch twice.
    """
    block = day.embeddings
    if block is None:
        return bool(earns_a_vector(day, embedder))
    if (block.model_id, block.dimensions, block.dtype) != (EMBEDDER_ID, DIMENSIONS, DTYPE):
        return True
    return set(block.vectors) != earns_a_vector(day, embedder)


def stage_backfill_vectors(
    *, root: Path, index_root: Path, today: str, embedder: Embedder
) -> int:
    """Re-encode every closed day whose vectors are not the set its items earned.

    `build_day` replaced a day's embeddings block instead of merging it, so a
    day that ran five times kept the last run's vectors alone. That is fixed
    forward, and nothing revisits a closed day - a scheduled run only ever
    appends to the current one. The days already committed therefore stay part
    searchable until something goes back for them, which is this.

    **A short day is re-encoded whole rather than topped up**, and that is the
    one decision here worth the words. Measured 2026-08-26 over the 439 vectors
    the five closed days already carried: a re-encode reproduces them at a
    median cosine of 0.9936, not 1.0, and 413 of the 439 items get a different
    top-10 neighbour list. The same measurement against the day CI wrote hours
    earlier returns a median cosine of exactly 1.0 with 54 of 80 vectors
    byte-identical. So the gap is the code and not the machine: every closed day
    was written before `embed.encode` stopped padding and stopped batching, and
    its vectors carry an arithmetic the browser's query encoder no longer uses.
    Topping such a day up would leave one block holding two arithmetics, and a
    reader's query would then rank two populations it cannot compare fairly.
    One block, one encoder - the same rule `assemble.merge_embeddings` already
    applies across model ids.

    A day whose vectors already match is left untouched, so this is safe to
    dispatch twice. A day it does rewrite is written whole, which also lifts an
    older payload to the current schema shape.

    Rewriting a day makes its month's search index stale, so every month this
    touched is rebuilt before it returns. That is the same obligation assemble
    carries, and this is the only other writer of a committed day payload.

    This one fails rather than degrades. `build_embeddings` returns nothing
    when the encoder is missing because a day that cannot be searched still
    publishes; here there is no digest at risk and the vectors are the entire
    point, so a silent no-op would report success for work that did not happen.
    """
    if not embedder.available:
        LOG.error("no encoder at %s - nothing to backfill with", ONNX_RELPATH)
        return 1

    repaired = 0
    months: set[str] = set()
    for path in published_days(root):
        day = DigestDay.from_json(path.read_text(encoding="utf-8"))
        if not is_closed(day.date, today=today):
            LOG.info("skipped date=%s reason=open items=%s", day.date, len(day.items))
            continue
        earned = earns_a_vector(day, embedder)
        if not needs_backfill(day, embedder):
            LOG.info("skipped date=%s reason=complete vectors=%s", day.date, len(earned))
            continue

        before = len(day.embeddings.vectors) if day.embeddings else 0
        fresh = assemble.build_embeddings(day.items, embedder)
        if fresh is None or set(fresh.vectors) != earned:
            LOG.error(
                "date=%s the encoder answered for %s of the %s items that earned a vector",
                day.date,
                0 if fresh is None else len(fresh.vectors),
                len(earned),
            )
            return 1
        repaired_day = day.model_copy(
            update={"version": DigestDay.schema_version(), "embeddings": fresh}
        )
        assemble.write_atomic(path, repaired_day.to_json())
        repaired += 1
        months.add(assemble.month_of(day.date))
        LOG.info(
            "backfilled date=%s items=%s earned=%s vectors_before=%s vectors_after=%s",
            day.date,
            len(day.items),
            len(earned),
            before,
            len(fresh.vectors),
        )

    for month in sorted(months):
        index = assemble.rebuild_search_index(
            digest_root=root, index_root=index_root, month=month
        )
        LOG.info(
            "rebuilt search index month=%s entries=%s vectors=%s",
            month,
            len(index.entries),
            index.vector_bytes // index.dimensions,
        )

    LOG.info("backfill complete days_rewritten=%s", repaired)
    return 0
