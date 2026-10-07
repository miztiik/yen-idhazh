"""Did every cleanup window leave `config/idhazh.json` with the value it had there?

`tests/fixtures/gardener/prune-oracle/windows.json` froze each knob the old state
cleanup read, key by key, before the ones that moved left for the declarations of
the tasks that read them. Each is read back here out of the declaration that took
it in the recorded pre-expiry config, and the three that stayed in
`config/idhazh.json` are read back from there as well. This checks the original
move, not the owner's later change to finite yearly retention.

A window whose declaration went when its ledger moved to the ledger door is read
from the migrator's table of how long each moved ledger's CSV was kept, which
`backend/tests/ledger_migration/test_csv_layouts.py` holds the ledger's compaction
to.
"""

from __future__ import annotations

import json
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text

from gardener._historical_config import PRE_YEARLY_CONFIG
from idhazh import config
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.gardener import (
    CompactionPolicy,
    DaysWindow,
    ForeverWindow,
    MonthsWindow,
    RetentionPolicy,
    TaskKind,
    TaskPolicy,
    Window,
)
from idhazh.contracts.ledger_name import LedgerName
from utilities.ledger_migration.csv_layouts import CSV_LEDGERS

pytestmark = pytest.mark.contract

#: What each window was in `config/idhazh.json` the day before it moved.
WINDOWS: Final = FIXTURES_DIR / "gardener" / "prune-oracle" / "windows.json"

#: Each window that changed on purpose after it moved, as its value then and now.
#: Every eval row is kept for ever and nothing summarises a month, so the rows'
#: fourteen months became forever.
CHANGED_ON_PURPOSE: Final[dict[str, tuple[Any, Any]]] = {
    "observability.scores_full_grain_months": (14, None),
}

#: The days one month of `retention.image_months` counts as.
DAYS_A_PICTURE_MONTH: Final = 30


def _days(window: Window) -> int:
    assert isinstance(window, DaysWindow), f"{window} is not a window of days"
    return window.value


def _months(window: Window) -> int | None:
    """A month knob's own spelling: a count of months, or null for never."""
    if isinstance(window, ForeverWindow):
        return None
    assert isinstance(window, MonthsWindow), f"{window} is not a window of months"
    return window.value


def _series(policy: TaskPolicy, name: str) -> Window:
    assert isinstance(policy, RetentionPolicy) and policy.series is not None
    return policy.series[name]


def test_every_window_left_the_app_config_with_the_value_it_had() -> None:
    frozen: dict[str, Any] = json.loads(WINDOWS.read_text(encoding="utf-8"))
    tasks = config.load_gardener(PRE_YEARLY_CONFIG).tasks
    folded, scores, machine, pictures = (
        tasks["telemetry-aggregate"],
        tasks["compact-summary-quality-evals"],
        tasks["compact-host-fingerprint"],
        tasks["visual-prune"],
    )
    assert isinstance(scores, CompactionPolicy)
    assert isinstance(machine, CompactionPolicy)
    now: dict[str, Any] = {
        "collect.seen_window_days": _days(CSV_LEDGERS[LedgerName.SEEN].old_window),
        "lens_weights.window_days": _days(
            CSV_LEDGERS[LedgerName.COUNTERFACTUAL_SCORES].old_window
        ),
        "observability.feed_health_keep_months": _months(
            CSV_LEDGERS[LedgerName.FEED_HEALTH].old_window
        ),
        "observability.host_fingerprint_keep_months": _months(machine.monthly_window),
        "observability.item_health_aggregate_keep_months": _months(_series(folded, "aggregate")),
        "observability.item_health_full_grain_months": _months(_series(folded, "full-grain")),
        "observability.public_telemetry_keep_months": _months(_series(folded, "public-copy")),
        "observability.score_archive_keep_months": _months(scores.monthly_window),
        "observability.scores_full_grain_months": _months(scores.monthly_window),
        "observability.trace_window_days": _days(tasks["traces"].window),
        "retention.dry_run": all(
            policy.dry_run for policy in tasks.values() if policy.kind is TaskKind.RETENTION
        ),
        "retention.image_months": _days(pictures.window) // DAYS_A_PICTURE_MONTH,
        "retention.max_deletes_per_run": pictures.max_deletes_per_run,
        "retention.trial_state_days": _days(tasks["trials"].window),
    }

    assert sorted(now) == sorted(frozen), "a frozen window has no reader here, or the reverse"
    changed = {key: (frozen[key], now[key]) for key in frozen if now[key] != frozen[key]}
    assert changed == CHANGED_ON_PURPOSE, "; ".join(
        f"{key} was {was} and is {moved} now"
        for key, (was, moved) in changed.items()
        if CHANGED_ON_PURPOSE.get(key) != (was, moved)
    )
    assert _days(pictures.window) % DAYS_A_PICTURE_MONTH == 0
    assert tasks["digest-fragments"].window == pictures.window, (
        "both picture-window tasks spent retention.image_months"
    )


def test_the_three_windows_that_stayed_still_read_what_they_did() -> None:
    frozen: dict[str, Any] = json.loads(WINDOWS.read_text(encoding="utf-8"))
    app = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    stayed = {
        "collect.seen_window_days": app.collect.seen_window_days,
        "lens_weights.window_days": app.lens_weights.window_days,
        "retention.image_months": app.retention.image_months,
    }

    assert {key: frozen[key] for key in stayed} == stayed
