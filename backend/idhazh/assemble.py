"""Collect whatever finished into the published day.

Assemble always runs and always publishes. A run with failures publishes a
digest that says it was partial, because a run that publishes nothing on a bad
day is a run whose bad days are invisible.

A later run appends and never reorders. `introduced_by_run` is a global fact -
true for every reader, asserted without any storage - which is what lets a
returning reader see what is new without the page knowing anything about them.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

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
from idhazh.contracts.sources import SourceForm, Sources
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import SourceKind, Taxonomy
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, Embedder, text_for, to_base64

LOG: Final = logging.getLogger("idhazh")

PUBLIC_ROOT: Final = Path("frontend/public/digest")
_UNTITLED: Final = "Untitled item"
_ABSTRACT_NOTE: Final = "This is a summary of the paper's abstract. The full paper is a PDF."
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


def reader_note(article: Article) -> str | None:
    if article.source_form is SourceForm.ABSTRACT:
        return _ABSTRACT_NOTE
    if article.truncated:
        return _TRUNCATED_NOTE
    return None


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
