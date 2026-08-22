"""Collect whatever finished into the published day.

Assemble always runs and always publishes. A run with failures publishes a
digest that says it was partial, because a run that publishes nothing on a bad
day is a run whose bad days are invisible.

A later run appends and never reorders. `introduced_by_run` is a global fact -
true for every reader, asserted without any storage - which is what lets a
returning reader see what is new without the page knowing anything about them.
"""

from __future__ import annotations

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
from idhazh.contracts.eval_row import ConfidenceBand
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
from idhazh.contracts.sources import Sources
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import SourceKind, Taxonomy
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, Embedder, text_for, to_base64

PUBLIC_ROOT: Final = Path("frontend/public/digest")
_UNTITLED: Final = "Untitled item"


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
) -> DigestItem:
    """One finished item as a reader consumes it. The link is a first-class element."""
    return DigestItem(
        item_id=summary.item_id,
        vertical=article.vertical,
        title=article.title or _UNTITLED,
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
        truncated=article.truncated,
        introduced_by_run=run_n,
        visual=to_digest_visual(route),
    )


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
    return {feed.id: feed.title for feed in sources.feeds}


def source_kinds(sources: Sources) -> dict[str, SourceKind]:
    return {feed.id: feed.kind for feed in sources.feeds}


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
    """
    if not items or not embedder.available:
        return None
    try:
        embedder.load()
        vectors: dict[str, str] = {}
        for start in range(0, len(items), batch):
            window = items[start : start + batch]
            for item, vector in zip(
                window, embedder.encode([text_for(i) for i in window]), strict=True
            ):
                vectors[item.item_id] = to_base64(vector)
    except (OSError, RuntimeError, ValueError, ImportError):
        return None
    return DigestEmbeddings(
        model_id=EMBEDDER_ID, dimensions=DIMENSIONS, dtype=DTYPE, vectors=vectors
    )


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
) -> DigestDay:
    """Append this run's items to whatever the day already carried.

    An item already published keeps its place. That is not politeness: the
    order is part of what a shared link shows, so moving it would change what
    the recipient sees relative to the sender.
    """
    already = {item.item_id for item in (previous.items if previous else [])}
    fresh = [item for item in items if item.item_id not in already]
    combined = [*(previous.items if previous else []), *fresh]

    runs = list(previous.runs) if previous else []
    runs = [run for run in runs if run.n != run_n]
    runs.append(DigestRunRef(n=run_n, at=generated_at, items_added=len(fresh)))
    runs.sort(key=lambda run: run.n)

    names = vertical_names(taxonomy)
    present = sorted({item.vertical for item in combined})
    published = len(combined)
    failed = max(len(plan.items) - published, 0)

    return DigestDay(
        version=DigestDay.schema_version(),
        date=plan.date,
        generated_at=generated_at,
        partial=failed > 0,
        items_planned=max(len(plan.items), published),
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
        embeddings=embeddings,
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
) -> RunManifest:
    """What ran, against which model, at which commit - appended, never rewritten."""
    run_n = (previous.runs[-1].n + 1) if previous else 1
    succeeded = sum(1 for summary in summaries if summary.status is SummaryStatus.OK)
    skipped = sum(1 for summary in summaries if summary.status is SummaryStatus.SKIPPED)
    planned = max(len(plan.items), len(summaries))
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
        items_failed=planned - succeeded - skipped,
        items_skipped=skipped,
        verticals=[
            VerticalCount(
                id=vertical.id,
                planned=vertical.planned,
                published=sum(1 for item in day.items if item.vertical == vertical.id),
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


def low_confidence(day: DigestDay) -> int:
    return sum(1 for item in day.items if item.band is ConfidenceBand.LOW)


def site_size(root: Path) -> tuple[int, int]:
    """Measured every run from the first one, long before any retention policy exists."""
    if not root.exists():
        return (0, 0)
    files = [path for path in root.rglob("*") if path.is_file()]
    return (sum(path.stat().st_size for path in files), len(files))
