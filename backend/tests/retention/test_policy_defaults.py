"""What does a fresh clone delete? Nothing, and this is where that is held."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.retention import cutoff, prune, visuals_older_than

from ._trees import (
    site,
)

pytestmark = pytest.mark.slow


def test_retention_is_off_by_default() -> None:
    """A default is a promise, not a placeholder."""
    config = RetentionConfig()
    assert config.image_months == -1
    assert config.dry_run is True
    assert cutoff(date(2026, 8, 21), config.image_months) is None


def test_a_disabled_policy_deletes_nothing(tmp_path: Path) -> None:
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.webp"]})
    result = prune(root, RetentionConfig(), date(2026, 8, 21))
    assert result.deleted == 0
    assert (root / "2020" / "01" / "01" / "old-0000000003.webp").exists()


#: A day inside the committed window and a day outside it, either side of the
#: cutoff the committed `retention.image_months` draws. Built here rather than
#: read off `frontend/public/digest/`, so what this costs never moves with what
#: the pipeline has published (Guardrail #12, `CLAUDE.md` section 13) - and so it
#: can carry the case the archive cannot yet produce. Nothing committed today is
#: old enough to be a candidate at any sane window: the oldest visual on disk is
#: three weeks old, so a run against the real tree would list nothing, and a dry
#: run that lists nothing proves nothing.
WINDOW_TODAY: Final = date(2026, 9, 13)


def committed_retention() -> RetentionConfig:
    """The `retention` block out of `config/idhazh.json` - one file, never a tree."""
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).retention


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
    config = committed_retention()
    assert config.image_months == 13, "the window this row gave a value"
    limit = cutoff(WINDOW_TODAY, config.image_months)
    assert limit is not None, "a window of -1 would make every assertion below vacuous"

    expired = limit - timedelta(days=1)
    inside = limit + timedelta(days=1)
    root = site(
        tmp_path,
        {
            expired.isoformat(): ["ai-01.svg", "ai-02.png"],
            inside.isoformat(): ["kept-0000000006.svg"],
            WINDOW_TODAY.isoformat(): ["today-0000000007.svg"],
        },
    )

    result = prune(root, config, WINDOW_TODAY)
    candidates = visuals_older_than(root, limit)
    print(f"candidates={len(candidates)} cutoff={limit.isoformat()}")

    assert len(candidates) == result.considered == 2, "an empty list proves nothing"
    for path in candidates:
        day, month, year = path.parent.name, path.parent.parent.name, path.parent.parent.parent.name
        assert re.match(ITEM_ID_PATTERN, path.stem), f"{path.name} is not named for an item"
        assert date(int(year), int(month), int(day)) < limit, f"{path} is inside the window"


def test_the_committed_window_still_deletes_nothing(tmp_path: Path) -> None:
    """The other half of the row: the window has a value and the fuse is still in.

    `dry_run` is what holds it, and it is the committed value rather than the
    step's flag - so a workflow that stopped passing `--dry-run` would still
    delete nothing until somebody edits `config/idhazh.json`.
    """
    config = committed_retention()
    assert config.dry_run is True
    limit = cutoff(WINDOW_TODAY, config.image_months)
    assert limit is not None
    root = site(tmp_path, {(limit - timedelta(days=1)).isoformat(): ["ai-01.svg"]})

    result = prune(root, config, WINDOW_TODAY)

    assert result.considered == 1
    assert result.deleted == 0
    assert result.dry_run
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
    config = committed_retention()
    limit = cutoff(WINDOW_TODAY, config.image_months)
    assert limit is not None
    heaviest = 43
    expired = (limit - timedelta(days=1)).isoformat()
    root = site(tmp_path, {expired: [f"p-{n:010d}.svg" for n in range(heaviest)]})

    result = prune(root, config, WINDOW_TODAY)

    assert result.considered == heaviest < config.max_deletes_per_run
    assert result.skipped_by_fuse == 0
    assert not result.fuse_tripped
