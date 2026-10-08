"""Does a trial root's segments splice into every ledger's address, and restore cleanly?

A trial run writes the same ledgers production does, under a bench segment (and
a case segment inside it) spliced into every address. `overlay_registry` builds
the spliced registry and `use_registry` makes it the one every path builder
falls back to, for the span of one compaction root's pass
(`gardener.runner._run_compaction_roots`). Neither function is called by a
stage or a trial producer: both are the gardener's own plumbing, so this tests
them directly rather than through a pipeline run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import overlay_registry, use_registry
from idhazh.ledger.paths import (
    compact_folder,
    entry,
    raw_root,
    relpath,
    tree_relpath,
    tree_root,
)

pytestmark = pytest.mark.contract

STATE: Final = Path("state")


def test_a_door_ledgers_segments_land_before_its_own_prefix() -> None:
    """`item-health` is raw-and-compact: its address has no folder of its own
    under `state/` apart from the tier, so the trial segments sit right after it."""
    with use_registry(overlay_registry(("pipeline-tests", "no-visual-plan"))):
        assert raw_root(STATE, LedgerName.ITEM_HEALTH) == STATE / "raw" / "pipeline-tests" / "no-visual-plan" / "item-health"
        assert compact_folder(STATE, LedgerName.ITEM_HEALTH) == (
            STATE / "compact" / "pipeline-tests" / "no-visual-plan" / "item-health"
        )


def test_a_bench_level_door_ledger_takes_one_segment() -> None:
    """`host-fingerprint` and `candidate-models` trial runs have no case: one segment."""
    with use_registry(overlay_registry(("pipeline-tests",))):
        assert raw_root(STATE, LedgerName.HOST_FINGERPRINT) == STATE / "raw" / "pipeline-tests" / "host-fingerprint"


def test_a_tree_ledgers_segments_land_after_its_own_top_level_folder() -> None:
    """`traces` already owns `state/traces/`: the segments nest inside it, not before it."""
    with use_registry(overlay_registry(("pipeline-tests", "no-visual-plan"))):
        assert tree_root(STATE, LedgerName.TRACES) == STATE / "traces" / "pipeline-tests" / "no-visual-plan"
        assert relpath(LedgerName.TRACES, "2026-10-08") == "state/traces/pipeline-tests/no-visual-plan/2026/10/08"
        assert tree_relpath(LedgerName.TRACES) == "state/traces/pipeline-tests/no-visual-plan"


def test_the_overlay_leaves_every_other_field_of_the_entry_alone() -> None:
    held = entry(LedgerName.HOST_FINGERPRINT)
    overlaid = overlay_registry(("pipeline-tests",))[LedgerName.HOST_FINGERPRINT]
    assert overlaid.grain == held.grain
    assert overlaid.name == held.name
    assert overlaid.prefix == ("pipeline-tests", *held.prefix)


def test_outside_any_use_registry_block_the_committed_registry_answers() -> None:
    assert raw_root(STATE, LedgerName.ITEM_HEALTH) == STATE / "raw" / "item-health"


def test_a_block_restores_the_committed_registry_on_exit_even_after_an_error() -> None:
    with pytest.raises(ZeroDivisionError):
        with use_registry(overlay_registry(("pipeline-tests",))):
            assert raw_root(STATE, LedgerName.ITEM_HEALTH) != STATE / "raw" / "item-health"
            raise ZeroDivisionError
    assert raw_root(STATE, LedgerName.ITEM_HEALTH) == STATE / "raw" / "item-health"


def test_a_nested_block_restores_the_enclosing_override_not_none() -> None:
    bench = overlay_registry(("pipeline-tests",))
    case = overlay_registry(("pipeline-tests", "no-visual-plan"))
    with use_registry(bench):
        assert raw_root(STATE, LedgerName.ITEM_HEALTH) == STATE / "raw" / "pipeline-tests" / "item-health"
        with use_registry(case):
            assert raw_root(STATE, LedgerName.ITEM_HEALTH) == (
                STATE / "raw" / "pipeline-tests" / "no-visual-plan" / "item-health"
            )
        assert raw_root(STATE, LedgerName.ITEM_HEALTH) == STATE / "raw" / "pipeline-tests" / "item-health"
    assert raw_root(STATE, LedgerName.ITEM_HEALTH) == STATE / "raw" / "item-health"


def test_an_explicit_registry_argument_still_wins_over_the_active_override() -> None:
    """A fixture test that passes its own registry is not silently redirected by
    a trial pass that happens to be active around it."""
    from idhazh.ledger.paths import _REGISTRY  # the committed table, for an explicit pin

    with use_registry(overlay_registry(("pipeline-tests",))):
        assert raw_root(STATE, LedgerName.ITEM_HEALTH, registry=_REGISTRY) == STATE / "raw" / "item-health"


def test_a_compact_index_path_takes_the_trial_segments_too() -> None:
    from idhazh.ledger.paths import compact_index_path

    with use_registry(overlay_registry(("pipeline-tests",))):
        path = compact_index_path(STATE, LedgerName.HOST_FINGERPRINT, Period.DAILY)
    assert path == STATE / "compact" / "pipeline-tests" / "host-fingerprint" / "index" / "daily.json"
