"""One picture, one story - held by the producer that writes the day.

Contract tier (CLAUDE.md section 13). The rule itself is
`idhazh.cli._picture_faults`, and it runs inside `idhazh validate-days`, which
`ci.yml` runs on every change and `digest.yml` runs before every publish. That
function's docstring carries the defect it exists for.

**It used to be one test per committed day, and that is what changed.** A day
already published is frozen: no later run rewrites its payload or redraws its
pictures. Re-checking all of them added a case every day the pipeline ran and
re-answered a question settled when the day was written (Rule #12). The day that
can still be wrong is the one being written, and the producer is standing there
when it is.

So the trees below are built here: one correct, and one for each way a payload
and its directory can disagree. A built tree can also carry a fault the archive
has never produced, which is the other half of why it is the better instrument.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh import cli

pytestmark = [pytest.mark.contract, pytest.mark.visual]

#: The day every case starts from, and the directory its pictures share with it.
FIXTURE = CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"
DAY: dict[str, Any] = json.loads(read_text(FIXTURE))
DATE: str = DAY["date"]
TEMPLATE: dict[str, Any] = DAY["items"][0]


def story_id(index: int) -> str:
    """The fixture's own story at that position."""
    return str(DAY["items"][index]["item_id"])


def picture(index: int) -> str:
    """Where `asset_relpath` would put that story's drawing, relative to public."""
    year, month, day = DATE.split("-")
    return f"digest/{year}/{month}/{day}/{story_id(index)}.svg"


def day_dir(public_root: Path) -> Path:
    year, month, day = DATE.split("-")
    return public_root / "digest" / year / month / day


def a_day_naming(public_root: Path, paths: list[str | None]) -> None:
    """The fixture day with its pictures replaced, one entry per story.

    Only the visuals move. A day composed from scratch drifts from the one the
    pipeline writes, and its own runs declare how many stories each added - so
    rebuilding the item list means rebuilding bookkeeping this test has no
    business having an opinion about.
    """
    payload: dict[str, Any] = json.loads(read_text(FIXTURE))
    # The fixture's own visual, so this file never has to restate its shape.
    drawn: dict[str, Any] = json.loads(json.dumps(TEMPLATE["visual"]))
    wanted = paths + [None] * (len(payload["items"]) - len(paths))
    for item, path in zip(payload["items"], wanted, strict=True):
        item["visual"] = None if path is None else {**drawn, "path": path}
    payload["leads"] = []

    day_dir(public_root).mkdir(parents=True, exist_ok=True)
    (day_dir(public_root) / "digest.json").write_text(json.dumps(payload), encoding="utf-8")


def draw(public_root: Path, path: str) -> None:
    file = public_root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")


def faults_for(public_root: Path) -> list[str]:
    return cli._day_faults(day_dir(public_root) / "digest.json", public_root)


def test_a_day_whose_pictures_line_up_reports_nothing(tmp_path: Path) -> None:
    """The denominator.

    A checker that passes everything reads exactly like one that passes a correct
    tree, so a correct tree is asserted on its own before any fault is.
    """
    a_day_naming(tmp_path, [picture(0), None])
    draw(tmp_path, picture(0))

    assert faults_for(tmp_path) == []


def test_two_stories_on_one_picture_is_refused(tmp_path: Path) -> None:
    """The 2026-08-24 defect itself: one of the two shows the other's chart."""
    a_day_naming(tmp_path, [picture(0), picture(0)])
    draw(tmp_path, picture(0))

    faults = faults_for(tmp_path)
    assert any("one picture on two stories" in fault for fault in faults), faults

def test_a_named_picture_that_is_not_there_is_refused(tmp_path: Path) -> None:
    """A broken image for the reader, and nothing else in the day is wrong."""
    a_day_naming(tmp_path, [picture(0)])

    faults = faults_for(tmp_path)
    assert any("not there" in fault for fault in faults), faults


def test_a_picture_no_story_names_is_refused(tmp_path: Path) -> None:
    """Weight against the 1 GB Pages cap that renders nowhere, and what a
    repaired collision leaves behind."""
    a_day_naming(tmp_path, [None])
    draw(tmp_path, picture(2))

    faults = faults_for(tmp_path)
    assert any("no story names" in fault for fault in faults), faults


def test_the_stage_stops_the_publish_rather_than_logging_and_passing(tmp_path: Path) -> None:
    """A rule that only writes a log line is not a gate."""
    a_day_naming(tmp_path, [picture(0), picture(0)])
    draw(tmp_path, picture(0))

    assert cli.stage_validate_days(tmp_path / "digest") == 1
