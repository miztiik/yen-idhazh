"""The committed digest tree against the picture files it names.

Contract tier (CLAUDE.md section 13): a published day is a persisted surface,
and this holds every one of them against the directory it sits in. No mocks and
no network (Rule #7) - the input is the real committed tree.

The defect this exists for shipped on 2026-08-24. A per-process counter that
restarted at 1 made a later run of the day overwrite an earlier run's
`india-01.svg` while the payload still named both items, so 32 declared visuals
sat over 18 files and 14 files were each claimed by two stories. 28 readers saw
a picture, and 14 of those pictures were drawn from another article's numbers,
under alt text describing figures that were not in the image. Nothing failed:
every file existed, every item validated, and the page rendered.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.digest_day import DigestDay
from idhazh.render.write import assets_in_day

pytestmark = [pytest.mark.contract, pytest.mark.visual]

PUBLIC_ROOT = REPO_ROOT / "frontend" / "public"
DIGEST_ROOT = PUBLIC_ROOT / "digest"


def committed_days() -> list[Path]:
    return sorted(DIGEST_ROOT.glob("*/*/*/digest.json"))


def day_id(path: Path) -> str:
    return "-".join(path.parent.parts[-3:])


def test_the_published_tree_holds_days_to_check() -> None:
    """The guard below is parametrized, so an empty tree would check nothing.

    A parametrized test over an empty list is one skip in a long pass list, and
    a scan that finds no input reports the same "no problems" as a scan that
    finds none. This is the denominator, asserted on its own.
    """
    days = committed_days()
    assert days, f"no digest.json under {DIGEST_ROOT.relative_to(REPO_ROOT).as_posix()}"


@pytest.mark.parametrize("path", committed_days(), ids=day_id)
def test_every_published_picture_belongs_to_exactly_one_item(path: Path) -> None:
    """One file, one story, and no bytes nobody renders.

    Three ways the payload and the directory disagree, and each one is a
    different fault. Two items on one path means one of them shows the other's
    chart. A path with no file means a reader gets a broken image. A file no
    item names is weight against the 1 GB Pages cap (Rule #2) that renders
    nowhere - and it is what a repaired collision leaves behind.
    """
    day = DigestDay.from_json(read_text(path))
    declared: list[str] = []
    for item in day.items:
        if item.visual is not None and item.visual.path is not None:
            declared.append(item.visual.path)

    shared = sorted(name for name, claims in Counter(declared).items() if claims > 1)
    assert not shared, f"{day.date}: one picture, two stories - {shared}"

    absent = sorted(name for name in declared if not (PUBLIC_ROOT / name).is_file())
    assert not absent, f"{day.date}: the payload names a file that is not there - {absent}"

    orphans = sorted(assets_in_day(PUBLIC_ROOT, day.date) - set(declared))
    assert not orphans, f"{day.date}: files no item names - {orphans}"
