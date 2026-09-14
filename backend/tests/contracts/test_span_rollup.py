"""Does the span rollup restate a measurement some ledger already holds?"""

from __future__ import annotations

import pytest

from idhazh.contracts.base import Contract
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.score_archive import ScoreArchive
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.contracts.visual_decision import VisualDecision

pytestmark = pytest.mark.contract


#
# Guardrail #12 and the telemetry doctrine: the committed span rollup holds a count
# and a duration that no ledger already holds. The check is on column names,
# outside the key, against every committed ledger a span could restate. Item-
# health alone is not enough - the timing a span most resembles is `decision_ms`
# on the visual decision, and the committed-five was chosen around that collision.

#: The key and the stamp a rollup row shares with the ledgers by design - the
#: grain it is filed at, plus the version every contract carries. A shared name
#: here is not a restated measurement, so it is set aside before the check.
_ROLLUP_KEY_AND_STAMP: frozenset[str] = frozenset(
    {"version", "date", "run_id", "shard", "span_name"}
)

#: Every committed ledger a span-rollup row could restate a measurement of, and
#: where it lives. `state/scores/` holds the raw eval rows and, once a month is
#: folded, the archive - a rollup must not restate either.
_LEDGERS_A_ROLLUP_MUST_NOT_RESTATE: dict[str, type[Contract]] = {
    "state/item-health": ItemHealthRow,
    "state/runtime-counters.csv": RuntimeCountersRow,
    "state/scores (raw rows)": EvalRow,
    "state/scores (archived)": ScoreArchive,
    "state/visuals": VisualDecision,
}


def _column_names(contract: type[Contract]) -> frozenset[str]:
    """Every column or field name a ledger spells.

    A CSV ledger row spells its columns in `csv_columns`; a JSON payload like the
    visual decision or the score archive has no CSV form, so its field names are
    what a collision would be measured against.
    """
    columns = getattr(contract, "csv_columns", None)
    if callable(columns):
        return frozenset(columns())
    return frozenset(contract.model_fields)


def _rollup_value_columns() -> frozenset[str]:
    return frozenset(SpanRollupRow.csv_columns()) - _ROLLUP_KEY_AND_STAMP


def test_the_rollup_holds_only_what_no_ledger_holds() -> None:
    value_columns = _rollup_value_columns()
    assert value_columns, "the rollup must carry at least one measurement of its own"
    for where, row_model in _LEDGERS_A_ROLLUP_MUST_NOT_RESTATE.items():
        collision = value_columns & _column_names(row_model)
        assert not collision, f"span-rollup restates {sorted(collision)}, already held by {where}"


def test_the_disjointness_check_catches_a_collision_outside_item_health() -> None:
    """A real collision must turn the Oracle above red, and not only against
    item-health. `decision_ms` is the visual decision's own timing and is absent
    from item-health, so a rollup that named its duration that would be caught
    only by testing state/visuals - which is why the fold commits five span names
    and not the six a naive reading would."""
    assert "decision_ms" in _column_names(VisualDecision)
    assert "decision_ms" not in _column_names(ItemHealthRow)
    pretend_value_columns = _rollup_value_columns() | {"decision_ms"}
    caught = {
        where: sorted(pretend_value_columns & _column_names(row_model))
        for where, row_model in _LEDGERS_A_ROLLUP_MUST_NOT_RESTATE.items()
        if pretend_value_columns & _column_names(row_model)
    }
    assert caught == {"state/visuals": ["decision_ms"]}
