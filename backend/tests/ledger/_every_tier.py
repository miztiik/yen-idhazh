"""How does a test build a census whose rows sit in every kind of file the ledger door keeps?

Through the door and the shipped compaction, never by hand. Rows are filed the
way a run files them, through `conftest.seed_item_health`, and the shipped
`compact-item-health` task then runs live over the tree, found the way the
runner finds it. So every file a test reads - raw, daily, monthly and yearly -
is a file a wake would have left.

The knobs that decide which file a day ends up in are written out here rather
than read from the committed declaration, so a change to that declaration
cannot move a day to another kind of file under a test: a month is absorbed 31
days after it ends, months are kept for ever, and a finished year is packed 63
days after it ends. These are the smallest waits the contract allows. A first
pass looks back four months from March, so it starts at the oldest filed day,
in November. Two months in the year prove that removing all rows of one month
removes one row group.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Final

from conftest import seed_item_health
from gardener.tasks._task import run_task
from retention._trees import health_row

from idhazh import ledger
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.ledger_name import LedgerName

CENSUS: Final = LedgerName.ITEM_HEALTH
TASK: Final = "compact-item-health"

#: The earliest wake with all four tiers at the minimum waits: 63 days after
#: 2025 ended. It takes days up to March 3, absorbs January, and packs 2025.
TODAY: Final = date(2026, 3, 5)

KNOBS: Final[dict[str, Any]] = {
    "daily_keep_days": 31,
    "monthly_window": {"unit": "forever"},
    "monthly_keep_days": 63,
    "compact_after_days": 1,
    "max_periods_per_run": 400,
    "lookback": 4,
}

#: The days rows are filed under, by the kind of file each one sits in once the
#: passes have run. 2025 is packed from two months, so its file holds two row
#: groups.
YEAR_DAYS: Final = ("2025-11-14", "2025-12-05", "2025-12-20")
MONTH_DAYS: Final = ("2026-01-08", "2026-01-22")
DAILY_DAYS: Final = ("2026-02-10", "2026-03-03")
RAW_DAYS: Final = ("2026-03-04", "2026-03-05")
FILED_DAYS: Final = (*YEAR_DAYS, *MONTH_DAYS, *DAILY_DAYS, *RAW_DAYS)

#: How many census rows each of those days holds.
ROWS_A_DAY: Final = 2

#: A day between two filed days that the daily index names with no row.
QUIET_DAY: Final = "2026-02-11"

#: How many passes leave the tree as described: the days, then the months, then the year.
PASSES: Final = 3


def a_census_in_every_tier(root: Path) -> Path:
    """File the census under `root/state`, run the compaction until it rests, and return state.

    Each pass has to finish its work, or the tree is not the one the names above
    describe and every test that reads it would be checking something else.
    """
    state = root / ledger.STATE_DIRNAME
    for number, day in enumerate(FILED_DAYS):
        seed_item_health(
            state,
            day,
            [
                health_row(
                    day=day, run=1, number=number * ROWS_A_DAY + row, stage=ItemStage.PUBLISH
                )
                for row in range(ROWS_A_DAY)
            ],
        )
    for _ in range(PASSES):
        outcome = run_task(TASK, root, today=TODAY, dry_run=False, **KNOBS)
        assert outcome.stopped_because is StopReason.EXHAUSTED, outcome
    return state
