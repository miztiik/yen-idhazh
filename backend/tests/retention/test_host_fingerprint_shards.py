"""When is a host-fingerprint month deleted, and what does the default do?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import REPO_ROOT, read_text

from idhazh import day_shards, ledger
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW, CollectConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.retention import oldest_month_kept, prune_host_fingerprint
from idhazh.stages.prune_state import stage_prune_state

from ._trees import (
    HISTORY_MONTHS,
    TODAY,
    host_fingerprint_history,
    host_fingerprint_months,
    months_back,
)


def committed_window() -> int:
    """The window `config/idhazh.json` names, read rather than restated.

    A number spelled here could disagree with the knob it is checking, and the
    day it did the test would pass against a window nothing runs.
    """
    months = AppConfig.from_json(
        read_text(REPO_ROOT / "config" / "idhazh.json")
    ).observability.host_fingerprint_keep_months
    assert months is not None, "config/idhazh.json names no host-fingerprint window"
    return months


def host_fingerprint_days(state_dir: Path) -> list[Path]:
    """Every host-fingerprint file, oldest first, through the pipeline's own walk."""
    return list(
        day_shards.shard_files(state_dir / ledger.HOST_FINGERPRINT_DIRNAME, days=UNBOUNDED_WINDOW)
    )


def the_file_the_fixture_wrote(date: str) -> str:
    """Where the fixture's one plan job filed the machine it ran on for `date`.

    Built from the identity grammar rather than typed, so a change to how a
    writer names its file fails here with the grammar rather than passing on a
    string this test froze.
    """
    name = ledger.segment_name(run_id=f"{date}-1", attempt=1, job=ServerJob.PLAN, shard=0)
    return f"{ledger.host_fingerprint_relpath(date)}/{name}"


def test_the_host_fingerprint_prune_takes_the_expired_day_and_keeps_the_day_beside_it(
    tmp_path: Path,
) -> None:
    """One day inside the window and one day outside it - exactly one goes.

    The assertion is two-sided on purpose. "Nothing failed", or "`deleted` is a
    tuple", passes on an EMPTY result, and an empty result is what a prune that
    never fires returns - so the store would silently stop being pruned and
    nothing would go red.
    """
    state = tmp_path / "state"
    keep = committed_window()
    config = ObservabilityConfig(host_fingerprint_keep_months=keep)
    boundary = oldest_month_kept(TODAY, keep)
    expired_day = f"{months_back(TODAY, keep + 1)[0]}-09"
    kept_day = f"{boundary}-09"
    assert expired_day[:7] < boundary <= kept_day[:7], "the fixture must straddle the boundary"
    host_fingerprint_history(state, [expired_day[:7], kept_day[:7]], day_of_month=9)
    expired_path = ledger.host_fingerprint_path(state, expired_day)
    kept_path = ledger.host_fingerprint_path(state, kept_day)
    assert expired_path.exists() and kept_path.exists()

    result = prune_host_fingerprint(state, config, TODAY, dry_run=False)

    assert not expired_path.exists(), "the expired day is still there, so nothing was pruned"
    assert kept_path.exists(), "the day inside the window was deleted"
    assert list(result.deleted) == [expired_day[:7]]
    assert list(result.days_removed) == [the_file_the_fixture_wrote(expired_day)]
    assert host_fingerprint_months(state) == [kept_day[:7]]
    assert result.bytes_freed > 0, "a deleted day file weighed nothing, so nothing was measured"
    # The emptied month and day directories go with their files, for the reason
    # the feed-health prune gives: the walk reads every directory it finds.
    assert not expired_path.parent.exists()


def test_a_dry_run_names_the_same_day_it_would_have_removed(tmp_path: Path) -> None:
    """The list a dry run prints has to be the list a live run removes, file for file."""
    state = tmp_path / "state"
    config = ObservabilityConfig(host_fingerprint_keep_months=committed_window())
    host_fingerprint_history(state, months_back(TODAY, HISTORY_MONTHS))
    before = host_fingerprint_days(state)

    dry = prune_host_fingerprint(state, config, TODAY, dry_run=True)

    assert dry.dry_run is True
    assert dry.days_removed, "the dry run named nothing, so the window never fired"
    assert host_fingerprint_days(state) == before, "a dry run deleted a file"

    live = prune_host_fingerprint(state, config, TODAY, dry_run=False)

    assert live.days_removed == dry.days_removed
    assert live.deleted == dry.deleted


def test_the_default_window_is_null_and_deletes_nothing(tmp_path: Path) -> None:
    """A clone that configures nothing keeps every month it has ever written.

    `RetentionConfig`'s rule - a default is a promise, not a placeholder - and
    null is the spelling `ObservabilityConfig` already uses for never.
    """
    state = tmp_path / "state"
    config = ObservabilityConfig()
    assert config.host_fingerprint_keep_months is None
    months = months_back(TODAY, HISTORY_MONTHS)
    host_fingerprint_history(state, months)

    result = prune_host_fingerprint(state, config, TODAY, dry_run=False)

    assert not result.changed
    assert host_fingerprint_months(state) == months


def test_a_window_below_the_published_copy_is_refused() -> None:
    """The published machine shard is folded from this ledger, so it may not outlive it."""
    with pytest.raises(ValueError, match="host_fingerprint_keep_months"):
        ObservabilityConfig(host_fingerprint_keep_months=13, public_machine_keep_months=14)


def test_the_prune_stage_reaches_the_host_fingerprint_tree(tmp_path: Path) -> None:
    """The helper is wired in, not merely written.

    Driven through `stage_prune_state` rather than through the function, because
    a prune nothing calls removes nothing however well it is tested. Its own
    `state_dir` is passed, so neither the committed ledgers nor the published
    tree is a candidate.
    """
    state = tmp_path / "state"
    keep = committed_window()
    expired_day = f"{months_back(TODAY, keep + 1)[0]}-09"
    kept_day = f"{oldest_month_kept(TODAY, keep)}-09"
    host_fingerprint_history(state, [expired_day[:7], kept_day[:7]], day_of_month=9)

    code = stage_prune_state(
        observability=ObservabilityConfig(host_fingerprint_keep_months=keep),
        collect=CollectConfig(),
        retention_config=RetentionConfig(),
        run_id="2026-08-30-1",
        today=TODAY,
        state_dir=state,
        dry_run=False,
    )

    assert code == 0
    assert not ledger.host_fingerprint_path(state, expired_day).exists()
    assert ledger.host_fingerprint_path(state, kept_day).exists()
