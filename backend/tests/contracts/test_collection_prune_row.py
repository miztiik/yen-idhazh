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
