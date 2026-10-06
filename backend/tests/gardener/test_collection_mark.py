"""Does a collection task find the day its last walk handled through, in its own record?

Every record here is filed through the ledger door into the gardener's ledger
under `tmp_path`, the way the runner files a shard's record. It is read back
through a listing that names nothing until the read names its own days, which
is the listing a shard hands a task before the task names what it reads.
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh.contracts.knobs.gardener import CollectionTaskPolicy
from idhazh.gardener import collection_mark
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing

from ._records import file_a_record
from .tasks._task import context_for

pytestmark = pytest.mark.contract

#: The wake every case reads from. Its look-back is this day and the six before it.
TODAY: Final = date(2026, 10, 4)


#: The cells of a row whose pass failed before its walk began, so it carries no mark.
NO_MARK: Final[dict[str, Any]] = {
    "handled_through": None,
    "stopped_because": "failed",
    "resume_from": None,
    "candidates_seen": 0,
    "selected": 0,
    "deleted": 0,
}


def the_task(root: Path, **changed: Any) -> TaskContext:
    """The runs task's context over `root`, its listing naming nothing until a read names it."""
    context = context_for("workflow-runs", root, today=TODAY, **changed)
    return dataclasses.replace(
        context, listing=FileListing.from_disk(root, context.listing.folders, paths=())
    )


def mark_of(context: TaskContext) -> str | None:
    policy = context.policy
    assert isinstance(policy, CollectionTaskPolicy)
    return collection_mark.last_mark(context, policy)


def test_the_mark_is_the_latest_day_a_pass_with_the_same_dry_run_handled_through(
    tmp_path: Path,
) -> None:
    """The latest day, not the newest row's: a day stays true once a pass has written it."""
    state = tmp_path / "state"
    file_a_record(state, on="2026-10-01", handled_through="2026-06-30")
    file_a_record(state, on="2026-10-02", handled_through="2026-06-29")
    file_a_record(state, on="2026-10-03", handled_through="2026-07-03", dry_run=False)
    file_a_record(state, on="2026-10-03", run=2, handled_through="2026-07-05", task="workflow-artifacts")

    assert mark_of(the_task(tmp_path)) == "2026-06-30"
    assert mark_of(the_task(tmp_path, dry_run=False)) == "2026-07-03"


def test_a_row_that_carries_no_mark_is_passed_over(tmp_path: Path) -> None:
    """A pass that failed before its walk began says nothing of where the walk stands."""
    state = tmp_path / "state"
    file_a_record(state, on="2026-10-01", handled_through="2026-06-30")
    file_a_record(state, on="2026-10-03", **NO_MARK)

    assert mark_of(the_task(tmp_path)) == "2026-06-30"


@pytest.mark.parametrize(
    ("look_back", "found"),
    [
        pytest.param(7, None, id="a-week-ends-the-day-after-it"),
        pytest.param(8, "2026-06-30", id="a-day-more-reaches-it"),
    ],
)
def test_a_record_older_than_the_look_back_is_not_read(
    tmp_path: Path, look_back: int, found: str | None
) -> None:
    """Seven UTC days ending 2026-10-04 start on 2026-09-28, so a record of 2026-09-27 is past them."""
    file_a_record(tmp_path / "state", on="2026-09-27", handled_through="2026-06-30")

    assert mark_of(the_task(tmp_path, mark_lookback_days=look_back)) == found


def test_the_read_names_only_its_own_days(tmp_path: Path) -> None:
    """The listing names the look-back's day folders and no other, so no other record is listed."""
    state = tmp_path / "state"
    file_a_record(state, on="2026-09-27", handled_through="2026-06-28")
    inside = file_a_record(state, on="2026-10-02", handled_through="2026-06-30")
    context = the_task(tmp_path)

    assert mark_of(context) == "2026-06-30"

    named_days = sorted(
        path
        for path in context.listing.checkout.named_later
        if path.startswith("state/raw/gardener/")
    )
    assert named_days == [
        f"state/raw/gardener/{(TODAY - timedelta(days=back)):%Y/%m/%d}" for back in range(6, -1, -1)
    ]
    listed = sorted(context.listing.checkout.listed_later)
    assert [Path(path).parent.as_posix() for path in listed] == [
        f"state/raw/gardener/{inside.date.replace('-', '/')}"
    ]


def test_a_task_that_reads_no_gardener_folder_is_refused_by_name(tmp_path: Path) -> None:
    """The record is read only through folders the declaration names under `reads`."""
    with pytest.raises(ValueError, match="not under a folder this task owns or reads"):
        mark_of(the_task(tmp_path, reads=[]))
