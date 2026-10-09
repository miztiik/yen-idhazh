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


def test_traces_segments_land_under_a_sibling_root_not_nested_inside_production() -> None:
    """`traces` takes a root of its own, `trial-traces`, sibling to `raw/` and
    `compact/` rather than nested inside production's own claim.

    Production's `state/traces` retention (`config/gardener/traces.json`, a
    7-day window) walks all of `state/traces`. Nesting a trial's traces at
    `state/traces/<segments>` would put that task's claim and the trial's own
    longer-lived trace retention (`config/gardener/trials.json`) one inside
    the other, which `config._refuse_overlapping_claims` exists to catch. Two
    folders that keep different retention windows cannot share or nest their
    claims, so a trial's traces sit at `state/trial-traces/<segments>` -
    a sibling root, never a child of either claim.
    """
    with use_registry(overlay_registry(("pipeline-tests", "no-visual-plan"))):
        assert tree_root(STATE, LedgerName.TRACES) == STATE / "trial-traces" / "pipeline-tests" / "no-visual-plan"
        assert relpath(LedgerName.TRACES, "2026-10-08") == (
            "state/trial-traces/pipeline-tests/no-visual-plan/2026/10/08"
        )
        assert tree_relpath(LedgerName.TRACES) == "state/trial-traces/pipeline-tests/no-visual-plan"


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


def test_two_threads_each_holding_their_own_trial_overlay_cannot_see_the_other() -> None:
    """The active override is a `ContextVar`, not a plain global.

    Nothing in this codebase runs two trial roots on two threads of the same
    process today - every pipeline-test case is its own CI matrix job, and the
    gardener compacts one root at a time (`gardener.runner._run_compaction_roots`).
    This test holds that apart anyway: if a future caller ever does share a
    process across trial roots, one thread's override must never leak into, or
    get clobbered by, another's.
    """
    import threading

    case_a = overlay_registry(("pipeline-tests", "case-a"))
    case_b = overlay_registry(("pipeline-tests", "case-b"))
    seen: dict[str, Path] = {}
    ready = threading.Barrier(2)

    def hold(label: str, registry: object) -> None:
        with use_registry(registry):  # type: ignore[arg-type]
            ready.wait()  # both threads are inside their own override before either reads
            seen[label] = raw_root(STATE, LedgerName.ITEM_HEALTH)

    threads = [
        threading.Thread(target=hold, args=("a", case_a)),
        threading.Thread(target=hold, args=("b", case_b)),
    ]
    for one in threads:
        one.start()
    for one in threads:
        one.join()

    assert seen["a"] == STATE / "raw" / "pipeline-tests" / "case-a" / "item-health"
    assert seen["b"] == STATE / "raw" / "pipeline-tests" / "case-b" / "item-health"
    assert raw_root(STATE, LedgerName.ITEM_HEALTH) == STATE / "raw" / "item-health"


def test_two_asyncio_tasks_each_holding_their_own_trial_overlay_cannot_see_the_other() -> None:
    """The same guarantee the thread test above proves, for `asyncio.Task` instead.

    A `ContextVar` copies its holder's context at the point a task is created,
    then the task's own writes to it are invisible to every sibling task and to
    whatever created it - unlike a thread, which starts with no inherited
    context at all. Both still need proving apart: a task that entered its
    override before the barrier releases its sibling, and read back after,
    would pass even if the two secretly shared one `ContextVar` cell. The
    barrier forces every task to be inside its own `with use_registry(...)`
    block before any of them reads, the same way the thread test's
    `threading.Barrier` does.
    """
    import asyncio

    case_a = overlay_registry(("pipeline-tests", "case-a"))
    case_b = overlay_registry(("pipeline-tests", "case-b"))

    async def hold(registry: object, barrier: asyncio.Barrier) -> Path:
        with use_registry(registry):  # type: ignore[arg-type]
            await barrier.wait()  # both tasks are inside their own override before either reads
            return raw_root(STATE, LedgerName.ITEM_HEALTH)

    async def run() -> tuple[Path, Path]:
        barrier = asyncio.Barrier(2)
        return await asyncio.gather(hold(case_a, barrier), hold(case_b, barrier))

    seen_a, seen_b = asyncio.run(run())

    assert seen_a == STATE / "raw" / "pipeline-tests" / "case-a" / "item-health"
    assert seen_b == STATE / "raw" / "pipeline-tests" / "case-b" / "item-health"
    assert raw_root(STATE, LedgerName.ITEM_HEALTH) == STATE / "raw" / "item-health"
