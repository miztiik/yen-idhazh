"""What does a fresh clone delete? Nothing, and this is where that is held."""

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


#: A day inside the committed window and a day outside it, either side of the
#: first day the committed visual-prune declaration keeps. Built here rather than
#: read off `frontend/public/digest/`, so what this costs never moves with what
#: the pipeline has published (Guardrail #12, `CLAUDE.md` section 13) - and so it
#: can carry the case the archive cannot yet produce. Nothing committed today is
#: old enough to be a candidate at any sane window: the oldest visual on disk is
#: three weeks old, so a run against the real tree would list nothing, and a dry
#: run that lists nothing proves nothing.
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

    row = pruned(root, WINDOW_TODAY)
    candidates = visuals_older_than(root, [expired])
    print(f"candidates={len(candidates)} cutoff={limit.isoformat()}")

    assert len(candidates) == row.candidates_found == 2, "an empty list proves nothing"
    for path in candidates:
        day, month, year = path.parent.name, path.parent.parent.name, path.parent.parent.parent.name
        assert re.match(ITEM_ID_PATTERN, path.stem), f"{path.name} is not named for an item"
        assert date(int(year), int(month), int(day)) < limit, f"{path} is inside the window"


def test_the_committed_window_still_deletes_nothing(tmp_path: Path) -> None:
    """The other half of the row: the window has a value and the fuse is still in.

    `dry_run` is what holds it, and it is the committed value in the task's own
    declaration. No step flag sits beside it any more, so nothing but an edit to
    `config/gardener/visual-prune.json` makes this delete.
    """
    assert declared()[NAME].dry_run is True
    limit = committed_first_kept()
    root = published(tmp_path, {(limit - timedelta(days=1)).isoformat(): ["ai-01.svg"]})

    row = pruned(root, WINDOW_TODAY)

    assert row.candidates_found == 1
    assert row.deleted == 0
    assert row.dry_run
    assert len(list(root.rglob("*.svg"))) == 1


def test_one_run_can_clear_a_backlog_the_committed_window_would_open(tmp_path: Path) -> None:
    """The fuse is not the bound in steady state, and this says by how much.

    Measured 2026-09-13 over the 19 published days past the startup regime:
    25.5 visuals arrive a published day, so 25.5 age out a day once the window
    reaches back that far. The pipeline runs five times a day against a 200-file
    fuse, which is 1,000 deletes a day of capacity - and the heaviest single day
    on record is 43. The fuse only becomes interesting if the window is ever
    narrowed, which drops a whole span in at once rather than a day at a time.
    """
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
