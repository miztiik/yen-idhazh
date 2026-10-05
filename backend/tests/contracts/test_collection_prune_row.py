"""Does a gardener record row refuse every cross-field lie a hand-written row could tell?

Built from the committed sample, so each case changes one cell of a row that
loads and asserts the refusal names the rule it broke.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.collection_prune import CollectionPruneRow

pytestmark = pytest.mark.contract


def a_row(**changes: Any) -> CollectionPruneRow:
    sample = json.loads(read_text(CONTRACT_FIXTURES_DIR / "collection-prune-row" / "ceiling-reached.json"))
    return CollectionPruneRow.model_validate(sample | changes)


def test_the_sample_loads() -> None:
    assert a_row().task == "workflow-artifacts"


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [
        ({"job": "work"}, "runs no task"),
        ({"stopped_because": "exhausted"}, "nothing left to resume from"),
        ({"resume_from": None}, "names where the next one begins"),
        ({"deleted": 51, "max_deletes_per_run": 50}, "must not exceed the ceiling"),
        ({"work_ended_at": "2026-09-27T00:47:12+00:00"}, "work_ended_at"),
        ({"attempt": 0}, "attempt"),
    ],
)
def test_a_row_that_lies_is_refused(changes: dict[str, Any], refusal: str) -> None:
    with pytest.raises(ValidationError, match=refusal):
        a_row(**changes)


def test_a_failed_pass_names_where_it_failed_only_when_it_reached_a_member() -> None:
    assert a_row(stopped_because="failed").resume_from == "4529182755"
    assert a_row(stopped_because="failed", resume_from=None).resume_from is None


def test_a_row_may_carry_no_ceiling_at_all() -> None:
    assert a_row(max_deletes_per_run=None).max_deletes_per_run is None


def test_a_shards_weight_is_whole_bytes_and_a_row_from_before_it_reads_as_not_weighed() -> None:
    """`cone_bytes` is additive: a row written before it existed reads, and says it was not read."""
    assert a_row().cone_bytes == 15_672_361
    with pytest.raises(ValidationError, match="cone_bytes"):
        a_row(cone_bytes=-1)
    sample = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "collection-prune-row" / "ceiling-reached.json")
    )
    sample.pop("cone_bytes")
    older = CollectionPruneRow.model_validate(sample | {"version": "2026-09-27"})
    assert older.cone_bytes is None


def test_what_a_shard_downloaded_is_whole_bytes_and_an_older_row_reads_as_not_counted() -> None:
    """`downloaded_bytes` is additive: a row written before it existed reads, and says so."""
    assert a_row().downloaded_bytes == 0
    with pytest.raises(ValidationError, match="downloaded_bytes"):
        a_row(downloaded_bytes=-1)
    sample = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "collection-prune-row" / "ceiling-reached.json")
    )
    sample.pop("downloaded_bytes")
    older = CollectionPruneRow.model_validate(sample | {"version": "2026-09-28T22:07"})
    assert older.downloaded_bytes is None


def a_folding_row(**changes: Any) -> CollectionPruneRow:
    sample = json.loads(
        read_text(
            CONTRACT_FIXTURES_DIR / "collection-prune-row" / "a-live-fold-beside-a-dry-window.json"
        )
    )
    return CollectionPruneRow.model_validate(sample | changes)


def test_a_fold_is_said_on_the_task_s_own_row_on_its_own_switch() -> None:
    """The window is dry and the fold is live, and one row says both."""
    row = a_folding_row()
    assert (row.dry_run, row.fold_dry_run) == (True, False)
    assert (row.folded_days, row.folded_files) == (6, 770)


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [
        ({"folded_days": None}, "or none of them"),
        ({"fold_dry_run": None}, "or none of them"),
        ({"folded_files": 5}, "at least one file"),
        ({"folded_files": -1}, "folded_files"),
    ],
)
def test_a_fold_that_lies_is_refused(changes: dict[str, Any], refusal: str) -> None:
    with pytest.raises(ValidationError, match=refusal):
        a_folding_row(**changes)


def test_a_row_from_before_the_fold_reads_as_a_task_that_did_not_fold() -> None:
    """The three fold cells are additive: a row written before them reads, and says no fold ran."""
    sample = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "collection-prune-row" / "ceiling-reached.json")
    )
    for key in ("fold_dry_run", "folded_days", "folded_files", "folded_months"):
        sample.pop(key)
    older = CollectionPruneRow.model_validate(sample | {"version": "2026-09-28"})
    assert (older.fold_dry_run, older.folded_days, older.folded_files) == (None, None, None)
    assert older.folded_months is None


def test_a_fold_that_settled_a_month_says_how_many_beside_its_days() -> None:
    """A month is counted with its own cell, and the files it replaced join the fold's count."""
    assert a_folding_row().folded_months == 0
    row = a_folding_row(folded_months=1)
    assert (row.folded_days, row.folded_months, row.folded_files) == (6, 1, 770)


def test_a_row_from_before_a_fold_could_settle_a_month_reads_as_none_counted() -> None:
    """`folded_months` is additive: a folding row written before it existed still reads."""
    sample = json.loads(
        read_text(
            CONTRACT_FIXTURES_DIR / "collection-prune-row" / "a-live-fold-beside-a-dry-window.json"
        )
    )
    sample.pop("folded_months")
    older = CollectionPruneRow.model_validate(sample | {"version": "2026-09-30"})
    assert (older.folded_days, older.folded_files, older.folded_months) == (6, 770, None)


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [
        ({"folded_months": -1}, "folded_months"),
        ({"folded_months": 2, "folded_files": 7}, "at least one file"),
    ],
)
def test_a_month_count_that_lies_is_refused(changes: dict[str, Any], refusal: str) -> None:
    with pytest.raises(ValidationError, match=refusal):
        a_folding_row(**changes)


def test_a_month_count_on_a_row_whose_task_did_not_fold_is_refused() -> None:
    """A month settled by no fold is a cell nobody could have filled honestly."""
    with pytest.raises(ValidationError, match="folded_months only beside them"):
        a_row(folded_months=0)


def a_walking_row(**changes: Any) -> CollectionPruneRow:
    sample = json.loads(
        read_text(
            CONTRACT_FIXTURES_DIR
            / "collection-prune-row"
            / "a-dry-walk-that-counted-past-its-ceiling.json"
        )
    )
    return CollectionPruneRow.model_validate(sample | changes)


def test_a_walk_says_the_day_it_handled_through_beside_where_a_live_pass_would_stop() -> None:
    """A dry walk past its ceiling counted the rest of 2026-08-25, so its mark is that day."""
    row = a_walking_row()
    assert (row.task, row.dry_run, row.stopped_because) == ("workflow-runs", True, "ceiling")
    assert (row.handled_through, row.resume_from) == ("2026-08-25", "32869125768")


def test_a_row_from_before_the_mark_reads_as_a_task_that_keeps_none() -> None:
    """`handled_through` is additive: every row written before it reads, and names no mark."""
    sample = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "collection-prune-row" / "ceiling-reached.json")
    )
    sample.pop("handled_through")
    older = CollectionPruneRow.model_validate(sample | {"version": "2026-10-03T18:00"})
    assert older.handled_through is None


@pytest.mark.parametrize(
    ("handled_through", "refusal"),
    [
        pytest.param("2026-11-23", "on or after the day the pass ran", id="the-day-it-ran"),
        pytest.param("2026-11-24", "on or after the day the pass ran", id="a-day-to-come"),
        pytest.param("2026-8-25", "string_pattern_mismatch", id="not-a-day"),
    ],
)
def test_a_mark_no_pass_could_have_written_is_refused(handled_through: str, refusal: str) -> None:
    """A window keeps at least the day a pass runs, so its mark is always before that day.

    A mark in the future would stop every later walk, which is why the row
    refuses one rather than the reader quietly passing it over.
    """
    with pytest.raises(ValidationError, match=refusal):
        a_walking_row(handled_through=handled_through)
