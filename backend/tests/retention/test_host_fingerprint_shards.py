"""What does the contract refuse of the host-fingerprint window, and does the stage reach it?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import REPO_ROOT, read_text

from idhazh import ledger
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.retention import oldest_month_kept
from idhazh.stages.prune_state import stage_prune_state

from ._trees import (
    TODAY,
    host_fingerprint_history,
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
        commit_sha="a" * 40,
        run_id="2026-08-30-1",
        today=TODAY,
        state_dir=state,
        dry_run=False,
    )

    assert code == 0
    assert not ledger.path(state, LedgerName.HOST_FINGERPRINT, expired_day).exists()
    assert ledger.path(state, LedgerName.HOST_FINGERPRINT, kept_day).exists()
