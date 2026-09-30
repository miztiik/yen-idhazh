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
    for key in ("fold_dry_run", "folded_days", "folded_files"):
        sample.pop(key)
    older = CollectionPruneRow.model_validate(sample | {"version": "2026-09-28"})
    assert (older.fold_dry_run, older.folded_days, older.folded_files) == (None, None, None)
