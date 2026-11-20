"""Does naming the days a read will open name every file it could open, and no other?

The names are pinned literally for a window that crosses a month and a year, so a change to the
compact folder layout, or to the way a day is spelled, fails here by name. The digest tool's
window is the same function over the days that end on its last day.

What this cannot settle is whether a given reader opens only these files: a tenant's own
declaration is held against its loaders in the tenant's tests.
"""

from __future__ import annotations

import pytest

from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.window_inputs import inputs_of_days
from utilities.publication_inputs import ledger_window

pytestmark = pytest.mark.contract

WHICH = LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS
RAW = "state/raw/content-similarity-judge/pair-verdicts"
COMPACT = "state/compact/content-similarity-judge/pair-verdicts"

INDEXES = tuple(f"{COMPACT}/index/{period}.json" for period in ("daily", "monthly", "yearly"))


def test_the_days_name_their_raw_folders_every_compact_file_that_could_serve_them_and_the_indexes() -> None:
    named = inputs_of_days(WHICH, ["2027-01-01", "2026-12-31"])

    assert named == (
        f"{COMPACT}/daily/2026/12/31.json",
        f"{COMPACT}/daily/2026/12/31.parquet",
        f"{COMPACT}/daily/2027/01/01.json",
        f"{COMPACT}/daily/2027/01/01.parquet",
        *INDEXES,
        f"{COMPACT}/monthly/2026/12.json",
        f"{COMPACT}/monthly/2026/12.parquet",
        f"{COMPACT}/monthly/2027/01.json",
        f"{COMPACT}/monthly/2027/01.parquet",
        f"{COMPACT}/yearly/2026/2026.json",
        f"{COMPACT}/yearly/2026/2026.parquet",
        f"{COMPACT}/yearly/2027/2027.json",
        f"{COMPACT}/yearly/2027/2027.parquet",
        f"{RAW}/2026/12/31",
        f"{RAW}/2027/01/01",
    )


def test_the_same_days_in_any_order_and_repeated_name_the_same_paths() -> None:
    days = ["2026-11-17", "2026-11-18", "2026-11-19"]

    assert (
        inputs_of_days(WHICH, days)
        == inputs_of_days(WHICH, reversed(days))
        == inputs_of_days(WHICH, [*days, *days])
    )


def test_no_days_name_only_the_three_indexes() -> None:
    assert inputs_of_days(WHICH, []) == INDEXES


def test_one_more_day_adds_its_own_files_and_nothing_else() -> None:
    before = set(inputs_of_days(WHICH, ["2026-11-17"]))
    after = set(inputs_of_days(WHICH, ["2026-11-17", "2026-11-18"]))

    assert after - before == {
        f"{COMPACT}/daily/2026/11/18.json",
        f"{COMPACT}/daily/2026/11/18.parquet",
        f"{RAW}/2026/11/18",
    }
    assert before <= after


@pytest.mark.parametrize("stamp", ["2026-11-1", "2026-13-01", "2026-02-30", "20261118", "2026-11"])
def test_a_stamp_that_is_not_a_day_is_refused(stamp: str) -> None:
    """A declaration naming a folder nothing reads would look complete and fetch the wrong files."""
    with pytest.raises(ValueError):
        inputs_of_days(WHICH, [stamp])


def test_the_digest_tools_window_is_the_days_that_end_on_its_last_day() -> None:
    assert ledger_window(WHICH, through="2027-01-01", days=2) == inputs_of_days(
        WHICH, ["2026-12-31", "2027-01-01"]
    )
    assert ledger_window(WHICH, through="2027-01-01", days=0) == INDEXES
