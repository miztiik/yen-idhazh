"""What does the committed visual-retention policy delete and preserve?"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from gardener.tasks._task import declared

from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.knobs.gardener import DaysWindow
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.retention import visuals_older_than

from ._visual_prune import NAME, pruned, published, window


def test_retention_is_off_by_default() -> None:
    """A default is a promise, not a placeholder."""
    assert RetentionConfig().image_months == -1


def test_a_disabled_policy_deletes_nothing(tmp_path: Path) -> None:
    root = published(tmp_path, {"2020-01-01": ["old-0000000003.webp"]})
    row = pruned(root, date(2026, 8, 21), window=window(-1), dry_run=False)
    assert row.deleted == 0
    assert (root / "2020" / "01" / "01" / "old-0000000003.webp").exists()


#: A fixed UTC day keeps generated expiry cases independent of the live archive.
WINDOW_TODAY: Final = date(2026, 9, 13)


def committed_first_kept() -> date:
    """The first day the committed declaration keeps, counted back from `WINDOW_TODAY`."""
    kept = declared()[NAME].window
    assert isinstance(kept, DaysWindow), "a window of forever makes every assertion vacuous"
    return WINDOW_TODAY - timedelta(days=kept.value)


def test_the_committed_window_selects_only_rendered_visuals_past_its_cutoff(
    tmp_path: Path,
) -> None:
    """The oracle for the window taking a value at all.

    Every path the dry run lists is a rendered visual under a dated directory
    older than the cutoff - asserted over the whole list by pattern rather than
    by naming the files, because the failure this guards is a prune that reached
    a day payload or a day inside the window, and neither is a file anybody
    would think to name.

    The length is printed and asserted non-empty on purpose. A dry run over an
    empty candidate list passes every assertion below while proving nothing, and
    that is what a run against the committed tree would do today.
    """
    assert declared()[NAME].window == DaysWindow(unit="days", value=390), (
        "thirteen thirty-day months, the window this row gave a value"
    )
    limit = committed_first_kept()

    expired = limit - timedelta(days=1)
    inside = limit + timedelta(days=1)
    root = published(
        tmp_path,
        {
            expired.isoformat(): ["ai-01.svg", "ai-02.png"],
            inside.isoformat(): ["kept-0000000006.svg"],
            WINDOW_TODAY.isoformat(): ["today-0000000007.svg"],
        },
    )

    row = pruned(root, WINDOW_TODAY, dry_run=True)
    candidates = visuals_older_than(root, [expired])
    print(f"candidates={len(candidates)} cutoff={limit.isoformat()}")

    assert len(candidates) == row.candidates_found == 2, "an empty list proves nothing"
    for path in candidates:
        day, month, year = path.parent.name, path.parent.parent.name, path.parent.parent.parent.name
        assert re.match(ITEM_ID_PATTERN, path.stem), f"{path.name} is not named for an item"
        assert date(int(year), int(month), int(day)) < limit, f"{path} is inside the window"


def test_the_committed_policy_deletes_only_expired_visuals(tmp_path: Path) -> None:
    """The shipped switch removes an expired chart, not the day or other records."""
    limit = committed_first_kept()
    expired = limit - timedelta(days=1)
    root = published(
        tmp_path,
        {
            expired.isoformat(): ["ai-0000000001.json", "notes.txt"],
            limit.isoformat(): ["ai-0000000002.json"],
        },
    )
    old_day = root / f"{expired:%Y}" / f"{expired:%m}" / f"{expired:%d}"
    kept_visual = root / f"{limit:%Y}" / f"{limit:%m}" / f"{limit:%d}" / "ai-0000000002.json"
    run = old_day / "run.json"
    run.write_text('{"n": 1}', encoding="utf-8")
    labels = tmp_path / "state" / "labels.csv"
    labels.parent.mkdir(parents=True, exist_ok=True)
    labels.write_text("item_id,label\nai-0000000001,keep\n", encoding="utf-8")
    protected = {
        path: path.read_bytes()
        for path in (old_day / "digest.json", run, old_day / "notes.txt", kept_visual, labels)
    }

    row = pruned(root, WINDOW_TODAY, wake=True)

    assert row.candidates_found == 1
    assert row.deleted == 1
    assert not row.dry_run
    assert row.skipped_by_fuse == 0
    assert not row.fuse_tripped
    assert row.bytes_reclaimed > 0
    assert not (old_day / "ai-0000000001.json").exists()
    assert {path: path.read_bytes() for path in protected} == protected


def test_the_committed_live_policy_reports_a_zero_candidate_pass(tmp_path: Path) -> None:
    """No expired chart is a measured no-op, not proof that deletion was exercised."""
    root = published(tmp_path, {WINDOW_TODAY.isoformat(): ["ai-0000000001.json"]})

    row = pruned(root, WINDOW_TODAY, wake=True)

    assert not row.dry_run
    assert (row.candidates_found, row.deleted, row.skipped_by_fuse, row.bytes_reclaimed) == (
        0,
        0,
        0,
        0,
    )
    assert not row.fuse_tripped
    assert row.payload_bytes_before == row.payload_bytes_after
    assert (root / f"{WINDOW_TODAY:%Y/%m/%d}" / "ai-0000000001.json").exists()


def test_the_committed_live_policy_stops_at_its_deletion_ceiling(tmp_path: Path) -> None:
    """A scheduled pass reports the backlog it cannot delete in this run."""
    ceiling = declared()[NAME].max_deletes_per_run
    assert ceiling is not None
    expired = committed_first_kept() - timedelta(days=1)
    root = published(
        tmp_path,
        {expired.isoformat(): [f"p-{n:010d}.json" for n in range(ceiling + 1)]},
    )

    row = pruned(root, WINDOW_TODAY, wake=True)

    assert not row.dry_run
    assert row.candidates_found == ceiling + 1
    assert row.deleted == ceiling
    assert row.skipped_by_fuse == 1
    assert row.fuse_tripped
    assert len(list(root.rglob("p-*.json"))) == 1


def test_one_run_can_clear_a_backlog_the_committed_window_would_open(tmp_path: Path) -> None:
    """One scheduled pass clears a generated batch smaller than the committed ceiling."""
    ceiling = declared()[NAME].max_deletes_per_run
    assert ceiling is not None, "the fuse is what this measures against"
    limit = committed_first_kept()
    heaviest = 43
    expired = (limit - timedelta(days=1)).isoformat()
    root = published(tmp_path, {expired: [f"p-{n:010d}.svg" for n in range(heaviest)]})

    row = pruned(root, WINDOW_TODAY)

    assert row.candidates_found == heaviest < ceiling
    assert row.skipped_by_fuse == 0
    assert not row.fuse_tripped
