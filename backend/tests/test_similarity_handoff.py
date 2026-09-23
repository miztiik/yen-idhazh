"""Does what one job of a judging night wrote reach the job that has to read it?

The council carries one directory between its jobs and carries nothing else. A
path outside that directory is not slow and not wasteful - it is gone, thrown
away with the runner that wrote it, and every later job fails on a file nobody
uploaded.

Driven against two empty directories standing in for two runners. No published
day and no committed store is opened: what is asked is where a path lands, and a
day with pairs in it would answer that at the cost of a fixture (CLAUDE.md
section 13).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final

import pytest

from idhazh.council import session
from idhazh.similarity import tenant
from idhazh.stages import common, judge_item_pairs

#: A night these tests ask the tenant about. Any date would do - none of them
#: reads a published day.
A_NIGHT: Final = "2026-09-20"

A_RUN: Final = "2026-09-21-35534060762"


def _one_runner(tmp_path: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A bare checkout with the council's root inside it, and nothing else.

    Returned as the checkout rather than the root, so a path written anywhere
    else in the tree is visible to the caller instead of invisible above it.
    """
    checkout = tmp_path / name
    monkeypatch.setattr(session, "COUNCIL_ROOT", checkout / session.COUNCIL_ROOT_RELPATH)
    return checkout


def test_every_path_this_tenant_writes_for_a_later_job_is_inside_the_carried_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rule the whole night rests on, asked of the disk and not of the source.

    A tenant that finds a second way to spell a path fails here as readily as one
    that never asked the venue at all, because what is read back is every file
    the runner holds afterwards rather than the paths the tenant meant to write.
    """
    runner = _one_runner(tmp_path, "picked-the-work", monkeypatch)
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "no-day-was-published")

    tenant.TENANT.prepare(date=A_NIGHT, run_id=A_RUN)

    carried = runner / session.COUNCIL_ROOT_RELPATH
    written = sorted(path for path in runner.rglob("*") if path.is_file())
    stray = [path for path in written if not path.is_relative_to(carried)]

    assert written, (
        "the unit that picks the work left nothing on this runner at all, so it "
        "wrote somewhere the council never carries"
    )
    assert not stray, (
        f"{[path.relative_to(runner).as_posix() for path in stray]} is outside "
        f"{session.COUNCIL_ROOT_RELPATH}, which is the only directory the workflow "
        "uploads - so no later job can read it"
    )


def test_a_unit_on_a_second_runner_finds_the_work_the_first_one_picked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The trip a night really makes, with only the artifact in between.

    One runner picks the work. What crosses is the directory the workflow
    uploads, copied whole and by itself. A second runner then reads the draw the
    way a judging unit reads it.

    **The day has nothing published, and that is the case worth driving.** The
    selection writes a header either way, so an absent draw never means "nothing
    to judge" - which is what lets the shard refuse rather than return empty.
    """
    picked = _one_runner(tmp_path, "picked-the-work", monkeypatch)
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "no-day-was-published")
    tenant.TENANT.prepare(date=A_NIGHT, run_id=A_RUN)
    drawn = tenant._draw_path(A_NIGHT)

    judged = tmp_path / "judged-a-shard"
    shutil.copytree(
        picked / session.COUNCIL_ROOT_RELPATH, judged / session.COUNCIL_ROOT_RELPATH
    )
    monkeypatch.setattr(session, "COUNCIL_ROOT", judged / session.COUNCIL_ROOT_RELPATH)
    on_the_second_runner = tenant._draw_path(A_NIGHT)

    assert drawn.is_file(), "the unit that picks the work left no draw"
    assert on_the_second_runner.is_file(), (
        "the draw did not travel, so all eight units would die on a missing file"
    )
    assert (
        judge_item_pairs._rows_this_shard_owns(on_the_second_runner, shard=0, shards=8) == []
    )


def test_a_draw_that_did_not_travel_is_refused_and_says_why(tmp_path: Path) -> None:
    """A missing draw is an error, never an empty day, and the message has to say so.

    The selection writes a header on a day it drew nothing from, so the only
    thing an absent file can mean is that it never reached this runner. Two
    people read the old message and went looking at the ordering of the jobs.
    """
    with pytest.raises(FileNotFoundError, match="carries between jobs"):
        judge_item_pairs._rows_this_shard_owns(
            tmp_path / "nothing-was-downloaded.csv", shard=0, shards=8
        )


def test_the_place_a_unit_writes_its_verdicts_is_the_place_the_settle_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writer and reader, asked of the two functions the night really calls.

    These two ran on different runners and against different roots until
    2026-09-23: the units wrote where nothing was uploaded from and the settle
    listed an empty directory, so a night came back having counted nothing and
    reported success.
    """
    runner = _one_runner(tmp_path, "judged-a-shard", monkeypatch)

    written = [tenant._verdict_path(A_NIGHT, shard=unit) for unit in range(8)]
    read = tenant._verdicts_dir(A_NIGHT)

    assert {path.parent for path in written} == {read}
    assert len({path.name for path in written}) == 8, "eight units, eight names"
    assert read.is_relative_to(runner / session.COUNCIL_ROOT_RELPATH)
