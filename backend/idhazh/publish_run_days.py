"""Publish what each day's runs did, a month at a time.

The console opens every day's `run.json` and every day's `digest.json` and
reduces both to counts. A day payload is hundreds of kilobytes and the console
wants two integers out of it, so this writes those integers once, at
publication, into `frontend/public/run-days/<YYYY-MM>.json`.

The shape is `PublicRunDay` and the month file is a JSON array of them, newest
day last. Three console reads answer off this one row - `loadManifests`,
`publishedItems` and `publishedCharts` - because they share a key, a window and
a producer.

**One month costs one month, for ever.** A month holds at most 31 days whatever
the archive grows to, so re-reading the month a run wrote into is constant cost
rather than a growing one (Rule #12). It is re-read rather than merged into the
published file because a correction can land on any day of the open month, and a
merge would have to trust the published copy to still describe a day the
correction just changed.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Iterator
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import assemble, publish_console
from idhazh.contracts.base import canonical_json
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.public_run_day import PublicRunDay, PublicRunRecord
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.visual_decision import VisualKind, VisualState

DIRNAME: Final = publish_console.RUN_DAYS_DIRNAME
SUFFIX: Final = ".json"

__all__ = [
    "DIRNAME",
    "SUFFIX",
    "build_day",
    "days_in_month",
    "months_published",
    "publish",
    "read_shard",
    "shard_path",
    "shard_relpath",
]


def shard_path(digest_root: Path, month: str) -> Path:
    """The browser's copy of one month of day rows."""
    return publish_console.month_path(digest_root, DIRNAME, month, SUFFIX)


def shard_relpath(month: str) -> str:
    """`frontend/public/run-days/<YYYY-MM>.json` - the POSIX form, for a log line."""
    return publish_console.relpath(DIRNAME, f"{month}{SUFFIX}")


def months_published(digest_root: Path) -> list[str]:
    """Every `<YYYY-MM>` the committed day tree holds, oldest first.

    Two directory listings a year and one a month - never a day payload opened -
    so learning which months exist costs the tree's shape rather than its
    contents. It does grow: one entry a month, for ever, and there is no cheaper
    way to answer "which months are there" than to look (Rule #12).
    """
    found: list[str] = []
    if not digest_root.is_dir():
        return found
    for year in sorted(entry for entry in digest_root.iterdir() if entry.is_dir()):
        if len(year.name) != 4 or not year.name.isascii() or not year.name.isdigit():
            continue
        for month in sorted(entry for entry in year.iterdir() if entry.is_dir()):
            if len(month.name) != 2 or not month.name.isascii() or not month.name.isdigit():
                continue
            found.append(f"{year.name}-{month.name}")
    return found


def days_in_month(digest_root: Path, month: str) -> Iterator[str]:
    """Every published date in one month, oldest first.

    One directory listing. A month holds at most 31 entries however long the
    project runs, which is why this producer's cost does not rise with the
    archive.
    """
    root = digest_root / month[:4] / month[5:7]
    if not root.is_dir():
        return
    for entry in sorted(item for item in root.iterdir() if item.is_dir()):
        if len(entry.name) == 2 and entry.name.isascii() and entry.name.isdigit():
            yield f"{month}-{entry.name}"


def build_day(digest_root: Path, date_stamp: str) -> PublicRunDay | None:
    """One published day reduced to the counts the console draws.

    Null when the day has no manifest. A day payload that will not parse costs
    the console its two counts and never the whole month, which is the view
    `payload.ts loadManifests` and `scripts/copy-visuals.mjs` both take of the
    same file.
    """
    day_root = assemble.day_dir(digest_root, date_stamp)
    manifest_path = day_root / "run.json"
    if not manifest_path.is_file():
        return None
    manifest = RunManifest.read(manifest_path)
    records = [
        PublicRunRecord(
            run_id=run.run_id,
            n=run.n,
            status=run.status.value,
            planned=run.items_planned,
            succeeded=run.items_succeeded,
            failed=run.items_failed,
            skipped=run.items_skipped,
            started_at=run.started_at,
            source_list_stale=run.source_list_stale,
            decided=run.items_decided,
            prefiltered=run.items_prefiltered,
            charts_drafted=run.charts_drafted,
            decision_ms=run.decision_ms,
        )
        for run in manifest.runs
    ]
    models: list[str] = []
    for run in manifest.runs:
        for use in run.models:
            if use.model_ref.id not in models:
                models.append(use.model_ref.id)
    last = manifest.runs[-1]
    items, charts = _page_counts(day_root / "digest.json")
    return PublicRunDay(
        version=PublicRunDay.schema_version(),
        date=date_stamp,
        runs=records,
        site_bytes=last.site_bytes,
        site_files=last.site_files,
        models=models,
        published_items=items,
        published_charts=charts,
    )


def _page_counts(payload: Path) -> tuple[int, int]:
    """Articles the day carries, and the charts a reader can actually see.

    Counted from the day payload rather than from the manifest: the manifest
    records what the planner decided and this records what survived to the page,
    and the site bytes beside them measure this same tree.
    """
    if not payload.is_file():
        return 0, 0
    day = DigestDay.read(payload)
    charts = sum(
        1
        for item in day.items
        if item.visual is not None
        and item.visual.kind is VisualKind.CHART
        and item.visual.state is VisualState.RENDERED
    )
    return len(day.items), charts


def read_shard(path: Path) -> list[PublicRunDay]:
    """Load a published month back through the contract that wrote it."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path.as_posix()} is not a list of day rows")
    return [PublicRunDay.model_validate(row) for row in payload]


def publish(
    *,
    digest_root: Path,
    keep_months: int,
    today: date,
    months: Collection[str] | None = None,
    ensure_month: str | None = None,
) -> list[Path]:
    """Write a published run-day month for each month of days that changed."""

    def encode(month: str) -> bytes:
        built = (build_day(digest_root, stamp) for stamp in days_in_month(digest_root, month))
        rows = [row for row in built if row is not None]
        text = canonical_json([row.model_dump(mode="json") for row in rows])
        return text.encode("utf-8")

    return publish_console.publish_series(
        digest_root=digest_root,
        dirname=DIRNAME,
        suffix=SUFFIX,
        available=months_published(digest_root),
        encode=encode,
        keep_months=keep_months,
        today=today,
        months=months,
        ensure_month=ensure_month,
    )
