"""Collect whatever finished into the published day.

Assemble always runs and always publishes. A run with failures publishes a
digest that says it was partial, because a run that publishes nothing on a bad
day is a run whose bad days are invisible.

A later run appends and never reorders. `introduced_by_run` is a global fact -
true for every reader, asserted without any storage - which is what lets a
returning reader see what is new without the page knowing anything about them.
"""

from __future__ import annotations

import base64
import binascii
import logging
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import (
    DigestDay,
    DigestEmbeddings,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
    DigestVisual,
)
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome
from idhazh.contracts.route import Route, VisualKind
from idhazh.contracts.run_manifest import (
    ConfigDigest,
    ModelUse,
    RunManifest,
    RunRecord,
    RunStatus,
    VerticalCount,
)
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.search_index import SearchIndex, SearchIndexEntry
from idhazh.contracts.sources import SourceForm, Sources
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import SourceKind, Taxonomy
from idhazh.embed import (
    DIMENSIONS,
    DTYPE,
    EMBEDDER_ID,
    VECTOR_SCALE,
    Embedder,
    text_for,
    to_base64,
)

LOG: Final = logging.getLogger("idhazh")

PUBLIC_ROOT: Final = Path("frontend/public/digest")
INDEX_ROOT: Final = Path("frontend/public/assist/index")
_UNTITLED: Final = "Untitled item"
_ABSTRACT_NOTE: Final = "This is a summary of the paper's abstract. The full paper is a PDF."
_SHARE_NOTE: Final = "We could only read the first {share} percent of this page."
#: The same fact with the scale dropped, for a page whose length before the cut is unknown.
_TRUNCATED_NOTE: Final = "We could only read the first part of this page."


def day_dir(root: Path, date: str) -> Path:
    """`<YYYY>/<MM>/<DD>` - readable, sortable, and free of any digest."""
    year, month, day = date.split("-")
    return root / year / month / day


def write_atomic(path: Path, text: str) -> None:
    """Temp-then-rename, so a file either exists complete or does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    )
    try:
        with handle:
            handle.write(text)
        Path(handle.name).replace(path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def write_atomic_bytes(path: Path, data: bytes) -> None:
    """The same guarantee for a file that is not text.

    The vector sibling is raw int8. Writing it through the text path would let a
    host's line-ending rules rewrite bytes inside a vector.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False)
    try:
        with handle:
            handle.write(data)
        Path(handle.name).replace(path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def utc_now() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_digest_item(
    *,
    article: Article,
    summary: Summary,
    band: ConfidenceBand,
    source_name: str,
    source_kind: SourceKind,
    run_n: int,
    route: Route | None = None,
    band_reason: BandReason | None = None,
) -> DigestItem:
    """One finished item as a reader consumes it. The link is a first-class element.

    The published title is ours when the summarizer wrote one, and the source's
    when it did not. The fallback runs on a real item whenever a drafted title
    missed the asked range, so it is the normal path and not the error path.
    """
    return DigestItem(
        item_id=summary.item_id,
        vertical=article.vertical,
        title=summary.title or article.title or _UNTITLED,
        source_url=article.canonical_url,
        source_id=article.source_id,
        source_name=source_name,
        source_kind=source_kind,
        published_at=article.published_at,
        summary=summary.summary or "",
        key_points=summary.key_points,
        lenses=article.lenses,
        events=article.events,
        entities=article.entities,
        band=band,
        band_reason=band_reason,
        source_form=article.source_form,
        reader_note=reader_note(article),
        truncated=article.truncated,
        introduced_by_run=run_n,
        visual=to_digest_visual(route),
    )


def read_share(article: Article) -> int | None:
    """How much of the page our summary was drawn from, as a whole percent.

    None where the length before the cut is unknown, or where the share rounds
    to all of it or none of it. A cut page that says "the first 100 percent" is
    worse than one that states no scale at all.
    """
    total = article.source_word_count
    if total is None or total <= 0:
        return None
    percent = round(100 * article.word_count / total)
    return percent if 1 <= percent <= 99 else None


def reader_note(article: Article) -> str | None:
    """Every source limit that would surprise the reader, in one paragraph.

    An abstract that was also cut carries both facts. Returning on the first
    one is the exact shape of a silent cut.

    The cut sentence names its scale, because one word cannot cover a page we
    read almost all of and a page we read a fifth of. Measured over the 22 cut
    items in `state/scores.csv` on 2026-08-29, the loss ran from 1.3 percent
    (25 words of 1,948) to 77.2 percent (6,519 of 8,442).
    """
    notes: list[str] = []
    if article.source_form is SourceForm.ABSTRACT:
        notes.append(_ABSTRACT_NOTE)
    if article.truncated:
        share = read_share(article)
        notes.append(_TRUNCATED_NOTE if share is None else _SHARE_NOTE.format(share=share))
    return " ".join(notes) or None


def to_digest_visual(route: Route | None) -> DigestVisual | None:
    """A routed-to-nothing item carries no visual object at all.

    The absence and the empty object would render identically today, and the
    absence is one fewer thing in every payload for the two items in three that
    correctly get no picture.
    """
    if route is None or route.kind is VisualKind.NONE:
        return None
    return DigestVisual(
        kind=route.kind,
        state=route.visual_state,
        path=route.asset_path,
        alt=route.alt_text,
    )


def source_names(sources: Sources) -> dict[str, str]:
    """Retired feeds included: a published id must still resolve to a name."""
    return {feed.id: feed.title for feed in sources.known_feeds()}


def source_kinds(sources: Sources) -> dict[str, SourceKind]:
    """Retired feeds included. Missing here means published as `reporting`."""
    return {feed.id: feed.kind for feed in sources.known_feeds()}


def vertical_names(taxonomy: Taxonomy) -> dict[str, str]:
    return {vertical.id: vertical.display_name for vertical in taxonomy.verticals}


def build_embeddings(
    items: Sequence[DigestItem], embedder: Embedder, *, batch: int = 16
) -> DigestEmbeddings | None:
    """Vectors for the day's items, or nothing at all.

    Returns `None` rather than raising when the encoder is missing or fails. A
    day that cannot be searched on a device is a day that still publishes; the
    search surface is secondary by construction and removing it must never cost
    a reader a single summary.

    An item the encoder cannot read is skipped rather than embedded, and the
    reason goes to the log the run keeps (section 1b). `vectors` is keyed by
    item id, so a skipped item is simply absent - the reader-side decoder
    already handles a day where not every item has one.
    """
    if not items or not embedder.available:
        return None
    try:
        embedder.load()
        vectors: dict[str, str] = {}
        for start in range(0, len(items), batch):
            window = []
            for item in items[start : start + batch]:
                if embedder.readable(text_for(item)):
                    window.append(item)
                else:
                    LOG.warning(
                        "item %s gets no vector: its text is not in the alphabet the "
                        "encoder was trained on, so any vector would be unretrievable",
                        item.item_id,
                    )
            for item, vector in zip(
                window, embedder.encode([text_for(i) for i in window]), strict=True
            ):
                vectors[item.item_id] = to_base64(vector)
    except (OSError, RuntimeError, ValueError, ImportError):
        return None
    return DigestEmbeddings(
        model_id=EMBEDDER_ID, dimensions=DIMENSIONS, dtype=DTYPE, vectors=vectors
    )


def merge_embeddings(
    previous: DigestEmbeddings | None, current: DigestEmbeddings | None
) -> DigestEmbeddings | None:
    """Carry the day's earlier vectors forward instead of replacing them.

    Each run only encodes the items it summarized, so a block that replaced its
    predecessor left a day searchable over its last run alone. The committed
    2026-08-24 day carried 145 vectors for 731 items.

    The newer vector wins a collision, because it was encoded from the newer
    text. A block that names another model, width or dtype is not merged at
    all: one map holding two widths is the failure the self-describing block
    exists to prevent, and the reader-side decoder cannot tell them apart.
    """
    if previous is None:
        return current
    if current is None:
        return previous
    if (previous.model_id, previous.dimensions, previous.dtype) != (
        current.model_id,
        current.dimensions,
        current.dtype,
    ):
        return current
    return current.model_copy(update={"vectors": {**previous.vectors, **current.vectors}})


def month_of(date: str) -> str:
    """`<YYYY-MM>` - the shard a published date belongs to."""
    return date[:7]


def days_in_month(digest_root: Path, month: str) -> list[DigestDay]:
    """Every committed day of one month, oldest first. A month with none gives none."""
    year, month_number = month.split("-")
    paths = sorted((digest_root / year / month_number).glob("*/digest.json"))
    return [DigestDay.from_json(path.read_text(encoding="utf-8")) for path in paths]


def _vector_bytes(encoded: str, dimensions: int) -> bytes | None:
    """The stored vector, or nothing when it is not the width this index names.

    A short vector is the one failure that must never be written: the offsets
    after it would all be wrong by its shortfall, every one of them would decode
    cleanly, and every score would be nonsense.
    """
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    return raw if len(raw) == dimensions else None


def build_search_index(month: str, days: Sequence[DigestDay]) -> tuple[SearchIndex, bytes]:
    """One month of published items, and the vector file its offsets point into.

    Built whole from the committed days every time. There is no incremental
    path, so there is no read-modify-write to race with itself across two runs
    of a day and no repair command for when it does. The cost is one pass over a
    month of payloads per assemble run, which is measured in
    `docs/reference/measurements.md`.

    **One index names one encoder.** The header is taken from the newest day
    that carries vectors. A day whose block names another model, width or dtype
    keeps its items in the index with no vector at all - browsable, not
    searchable - because two encoders in one space produce scores that look like
    scores and mean nothing. That is the rule `merge_embeddings` already applies
    inside a day, applied across the days of a month.
    """
    ordered = sorted(days, key=lambda day: day.date)

    model_id: str = EMBEDDER_ID
    dimensions: int = DIMENSIONS
    dtype: Literal["int8"] = DTYPE
    for day in reversed(ordered):
        newest = day.embeddings
        if newest is not None and newest.vectors:
            model_id, dimensions, dtype = newest.model_id, newest.dimensions, newest.dtype
            break

    entries: list[SearchIndexEntry] = []
    vectors = bytearray()
    for day in ordered:
        block = day.embeddings
        named = block is not None and (block.model_id, block.dimensions, block.dtype) == (
            model_id,
            dimensions,
            dtype,
        )
        if block is not None and not named:
            LOG.warning(
                "date=%s holds %s vectors from %s/%s/%s, and this index names %s/%s/%s - "
                "its items stay in the index without one",
                day.date,
                len(block.vectors),
                block.model_id,
                block.dimensions,
                block.dtype,
                model_id,
                dimensions,
                dtype,
            )
        for item in day.items:
            offset: int | None = None
            encoded = block.vectors.get(item.item_id) if named and block is not None else None
            if encoded is not None:
                raw = _vector_bytes(encoded, dimensions)
                if raw is None:
                    LOG.warning(
                        "item %s on %s stores a vector this index cannot lay out at %s "
                        "bytes, so it gets none",
                        item.item_id,
                        day.date,
                        dimensions,
                    )
                else:
                    offset = len(vectors)
                    vectors += raw
            entries.append(
                SearchIndexEntry(
                    date=day.date,
                    item_id=item.item_id,
                    title=item.title,
                    vertical=item.vertical,
                    vector=offset,
                )
            )

    index = SearchIndex(
        version=SearchIndex.schema_version(),
        month=month,
        model_id=model_id,
        dimensions=dimensions,
        dtype=dtype,
        scale=VECTOR_SCALE,
        entries=entries,
    )
    return index, bytes(vectors)


def rebuild_search_index(*, digest_root: Path, index_root: Path, month: str) -> SearchIndex:
    """Regenerate a month's index from the days that are committed right now.

    Every writer of a day payload owes this call. The shard is derived, so a
    deleted day needs no separate cleanup - the next assemble run simply writes
    a shard that no longer names it.
    """
    index, vectors = build_search_index(month, days_in_month(digest_root, month))
    write_atomic(index_root / f"{month}.json", index.to_json())
    write_atomic_bytes(index_root / f"{month}.bin", vectors)
    return index


def build_day(
    *,
    plan: RunPlan,
    items: Sequence[DigestItem],
    previous: DigestDay | None,
    taxonomy: Taxonomy,
    run_n: int,
    generated_at: str,
    retention_window_months: int,
    embeddings: DigestEmbeddings | None = None,
    item_health_rows: Sequence[ItemHealthRow] | None = None,
) -> DigestDay:
    """Append this run's items to whatever the day already carried.

    An item already published keeps its place. That is not politeness: the
    order is part of what a shared link shows, so moving it would change what
    the recipient sees relative to the sender.

    A run can come back as itself. `cli.stage_assemble` writes the day, then
    builds the manifest, then writes it, so a run that dies in that gap leaves a
    day holding its items and a manifest that never heard of it - and the next
    run reads the same number off the manifest. Replacing the reference rather
    than adding a second one is what makes that replay one run, and the count on
    it is every item the number introduced rather than what this attempt added,
    because that is what `DigestDay` validates it against.
    """
    already = {item.item_id for item in (previous.items if previous else [])}
    fresh = [item for item in items if item.item_id not in already]
    combined = [*(previous.items if previous else []), *fresh]

    runs = list(previous.runs) if previous else []
    runs = [run for run in runs if run.n != run_n]
    runs.append(
        DigestRunRef(
            n=run_n,
            at=generated_at,
            items_added=sum(1 for item in combined if item.introduced_by_run == run_n),
        )
    )
    runs.sort(key=lambda run: run.n)

    names = vertical_names(taxonomy)
    present = sorted({item.vertical for item in combined})
    published = len(combined)
    failed = (
        sum(1 for row in item_health_rows if row.outcome is ItemOutcome.FAILED)
        if item_health_rows is not None
        else max(len(plan.items) - published, 0)
    )
    planned = (
        max(len(plan.items), published + failed)
        if item_health_rows is not None
        else max(len(plan.items), published)
    )

    return DigestDay(
        version=DigestDay.schema_version(),
        date=plan.date,
        generated_at=generated_at,
        partial=failed > 0,
        items_planned=planned,
        items_failed=failed,
        retention_window_months=retention_window_months,
        runs=runs,
        verticals=[
            DigestVerticalRef(
                id=vertical_id,
                display_name=names.get(vertical_id, vertical_id),
                count=sum(1 for item in combined if item.vertical == vertical_id),
            )
            for vertical_id in present
        ],
        items=combined,
        embeddings=merge_embeddings(previous.embeddings if previous else None, embeddings),
    )


def build_manifest(
    *,
    plan: RunPlan,
    day: DigestDay,
    previous: RunManifest | None,
    summaries: Sequence[Summary],
    models: Sequence[ModelUse],
    commit_sha: str,
    runner: str,
    started_at: str,
    completed_at: str,
    config_digests: Sequence[ConfigDigest],
    site_bytes: int,
    site_files: int,
    determinism_violations: int = 0,
    note: str | None = None,
    item_health_rows: Sequence[ItemHealthRow] | None = None,
    routes: Sequence[Route] | None = None,
    evaluation_enabled: bool | None = None,
    evaluation_sample_rate: float | None = None,
    evaluation_sampled: bool | None = None,
    scorer_version: str | None = None,
) -> RunManifest:
    """What ran, against which model, at which commit - appended, never rewritten.

    This appends where `build_day` replaces, and the difference is not an
    oversight. `RunManifest` refuses a `runs` list that is not numbered from 1
    without gaps, so `runs[-1].n` is `len(runs)` and the next number cannot
    already be taken. A second record for one run is not a duplicate this
    function has to filter out - it is a payload the contract will not build.
    A guard here would be a branch nothing can reach.

    The day is the surface that needs the replace, because its items land on
    disk one write before this one does.
    """
    run_n = (previous.runs[-1].n + 1) if previous else 1
    if item_health_rows is not None:
        succeeded = sum(1 for row in item_health_rows if row.outcome is ItemOutcome.OK)
        failed = sum(1 for row in item_health_rows if row.outcome is ItemOutcome.FAILED)
        skipped = 0
        planned = len(item_health_rows)
    else:
        succeeded = sum(1 for summary in summaries if summary.status is SummaryStatus.OK)
        skipped = sum(1 for summary in summaries if summary.status is SummaryStatus.SKIPPED)
        planned = max(len(plan.items), len(summaries))
        failed = planned - succeeded - skipped
    # A router that never ran leaves no payloads, and a payload written before
    # the clock existed carries no number. Both are "nothing was measured", which
    # is null - not a zero that would read as "it took no time".
    timed = [route.route_ms for route in (routes or []) if route.route_ms is not None]
    prefiltered = sum(1 for route in (routes or []) if not route.asked_the_model)
    record = RunRecord(
        run_id=f"{plan.date}-{run_n}",
        n=run_n,
        started_at=started_at,
        completed_at=completed_at,
        status=RunStatus.COMPLETED if not day.partial else RunStatus.PARTIAL,
        commit_sha=commit_sha,
        runner=runner,
        source_list_stale=plan.stale,
        models=list(models),
        items_planned=planned,
        items_succeeded=succeeded,
        items_failed=failed,
        items_skipped=skipped,
        items_routed=len(routes or []),
        items_prefiltered=prefiltered,
        charts_drafted=sum(1 for route in (routes or []) if route.drafted_chart),
        route_ms=sum(timed) if timed else None,
        verticals=[
            VerticalCount(
                id=vertical.id,
                planned=vertical.planned,
                published=sum(
                    1
                    for item in day.items
                    if item.vertical == vertical.id and item.introduced_by_run == run_n
                ),
                below_feed_floor=vertical.below_feed_floor,
            )
            for vertical in plan.verticals
        ],
        pipeline_fingerprints=sorted({summary.pipeline_fingerprint for summary in summaries}),
        determinism_violations=determinism_violations,
        site_bytes=site_bytes,
        site_files=site_files,
        evaluation_enabled=evaluation_enabled,
        evaluation_sample_rate=evaluation_sample_rate,
        evaluation_sampled=evaluation_sampled,
        scorer_version=scorer_version,
        config_digests=list(config_digests),
        note=note,
    )
    runs = [*(previous.runs if previous else []), record]
    return RunManifest(version=RunManifest.schema_version(), date=plan.date, runs=runs)


def run_that_wrote(item: DigestItem) -> int:
    """Which run wrote the words this item now carries.

    The run manifest names the model per run, so this is the join anyone asking
    "which model wrote this summary" has to make. An item no run has revised was
    written by the run that introduced it. A revised one names its own run,
    because the alternative is a join that answers with the wrong run rather
    than with nothing.
    """
    return item.updated_by_run or item.introduced_by_run


def low_confidence(day: DigestDay) -> int:
    return sum(1 for item in day.items if item.band is ConfidenceBand.LOW)


def site_size(root: Path) -> tuple[int, int]:
    """Measured every run from the first one, long before any retention policy exists."""
    if not root.exists():
        return (0, 0)
    files = [path for path in root.rglob("*") if path.is_file()]
    return (sum(path.stat().st_size for path in files), len(files))
