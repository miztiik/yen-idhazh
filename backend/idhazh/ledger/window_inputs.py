"""Which paths does reading these named days open, so a sparse checkout can fetch only them?

A reader of a ledger names the days it wants, and `ledger.load_days` opens the three compact
indexes, the one compact file that serves each day, and the raw files of the days no index
names (`ledger/ledger_files.py`). A job that works from a sparse checkout has to be told which
files those are before the read, and it cannot ask the indexes, because the indexes are among
the files it is fetching. So this names every file such a read could open, for those days and
no others: each day's raw folder, the daily, monthly and yearly compact file that could serve
it (the data file and its sidecar) and the three indexes.

The function takes the list of days and not a first and a last, because the readers take a
list: a declaration built from the very list a reader is handed cannot drift from what that
reader opens.

This module is imported by its own name and is not re-exported by `idhazh.ledger`. The council's
verbs load the door, and a name added to it joins what every verb imports; only a tenant's
declaration and the digest tool need this.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path

from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths


class CompactLayoutChangedError(ValueError):
    """The compact folder layout is no longer the one this naming was written against."""


def inputs_of_days(which: LedgerName, days: Iterable[str]) -> tuple[str, ...]:
    """Raw days, exact compact periods and three named indexes, never a ledger walk.

    **Guardrail #12 declaration.** The fixed-size input is the list of days the caller names,
    which is the number of nights a reader asks for and no more. The result is sorted, and
    the same days in any order and with repeats name the same paths.

    Every day must be a real UTC day, `YYYY-MM-DD`: a stamp that is not one would name a folder
    nothing reads, and the declaration would look complete while fetching the wrong files.
    """
    state = Path("state")
    raw = paths.raw_root(state, which)
    asked: set[str] = {
        paths.compact_index_path(state, which, period).as_posix() for period in Period
    }
    coverage: dict[Period, set[str]] = {period: set() for period in Period}
    for stamp in days:
        date.fromisoformat(stamp)
        asked.add((raw / stamp.replace("-", "/")).as_posix())
        for period, covers in (
            (Period.DAILY, stamp),
            (Period.MONTHLY, stamp[:7]),
            (Period.YEARLY, stamp[:4]),
        ):
            coverage[period].add(covers)
    for period, periods in coverage.items():
        if not periods:
            continue
        sample_date = min(periods)
        sample = paths.compact_path(state, which, period, sample_date)
        sample_parts = (
            sample_date.split("-")
            if period is not Period.YEARLY
            else [
                sample_date,
                sample_date,
            ]
        )
        if sample.with_suffix("").parts[-len(sample_parts) :] != tuple(sample_parts):
            raise CompactLayoutChangedError(
                "compact period layout changed; update the bounded input policy"
            )
        root = sample.parents[len(sample_parts) - 1]
        for covers in periods:
            parts = covers.split("-") if period is not Period.YEARLY else [covers, covers]
            held = root.joinpath(*parts)
            asked.update(held.with_suffix(suffix).as_posix() for suffix in (".parquet", ".json"))
    return tuple(sorted(asked))
