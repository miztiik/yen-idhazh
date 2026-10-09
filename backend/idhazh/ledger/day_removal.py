"""Which door files hold a range of days, and each one rebuilt without them.

A ledger the door files keeps one day's rows in one of four kinds of file as
the day ages: the raw files its writers left under `state/raw/<ledger>/`, the
day's compact file, its month's file, and - where the ledger packs years - its
year's file (`ledger/ledger_files.py`). A day taken out of such a ledger is
taken out of every file that holds a row of it, so this module answers the two
questions a prune asks first, and writes nothing:

- `find_holding_files` names every file that holds a row filed under one of
  the days. A raw file holds its own day. A compact file holds the days its
  index entry covers, and none at all when that entry counts no row.
- `rebuild_without` builds one compact file again with those days' rows left
  out. A file whose every row goes is built as an empty file rather than left
  out, so the index that names it keeps no hole. A year file is built one
  month a row group, as the compaction builds it, so a reader that filters on
  a date still skips the other months.

A raw file is never rebuilt: it holds one writer's rows of one day, so a day
taken out takes it whole.

**Every row knows the day it was first filed under.** Its `covers` identity
cell is the day of the raw file that first held it, and a compact file keeps
that cell as it was (`contracts/file_envelope.py`), so a month or a year file
gives up exactly the rows of the days asked for and keeps every other row, its
cells and its identity unchanged.

**An index or a file this build cannot read is refused, never read as absent.**
A reader skips one and serves what it can (`ledger/ledger_files.py`). A prune
that did the same would leave that period's rows behind while it reported the
days gone, so here it is a `ValueError` naming the file, before anything is
built.

**What it reads (Guardrail #12).** The three compact indexes, whole: they grow
by one entry a packed day, month or year, and they are the read `held_days`
makes and `docs/concepts/growing-reads.md` declares. Beside them, only what the
days a caller names bound - their raw folders and the envelope of each raw
file in them - and, in `rebuild_without`, the one file it rebuilds.

Every day, month and year here is a UTC one (CLAUDE.md section 2).
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import NamedTuple

from idhazh.contracts.base import Contract, StalePayloadError
from idhazh.contracts.file_envelope import Period, Tier, WriterIdentity, covers_fits
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths, raw_files
from idhazh.ledger.keys import door_contract
from idhazh.ledger.ledger_files import compact_file
from idhazh.ledger.persist import (
    PeriodFile,
    StoredRow,
    load_stored,
    read_envelope,
    render_grouped_period,
    render_period,
)


class HeldFile(NamedTuple):
    """One door file that holds rows filed under some of the days asked about."""

    path: Path
    #: `raw` for one writer's file, `compact` for a daily, monthly or yearly one.
    tier: Tier
    #: A compact file's period, or None for a raw file.
    period: Period | None
    #: The UTC day, month or year the file covers.
    covers: str
    #: The days asked about that this file covers, oldest first. An index counts
    #: a file's rows and not a day's, so a month or a year file names every day
    #: of it asked about, whether or not that day filed a row.
    days: tuple[str, ...]


def _inside(day: str, covers: str) -> bool:
    """Whether a UTC day falls in what a file covers: that day, or a day of its month or year."""
    return day == covers or day.startswith(f"{covers}-")


def _index(state_dir: Path, ledger: LedgerName, period: Period) -> CompactIndex | None:
    """One period's index, None when there is none, or a refusal when it cannot be read."""
    path = paths.compact_index_path(state_dir, ledger, period)
    if not path.is_file():
        return None
    try:
        index = CompactIndex.read(path)
    except (ValueError, StalePayloadError) as refusal:
        raise ValueError(
            f"{paths.shown(state_dir, path)} cannot be read, so which files hold the "
            f"days is not known and nothing is taken: {refusal}"
        ) from refusal
    if (index.ledger, index.period) != (ledger, period):
        raise ValueError(
            f"{paths.shown(state_dir, path)} describes the {index.ledger.value} "
            f"{index.period.value} period, and it sits where the {ledger.value} "
            f"{period.value} index goes"
        )
    return index


def find_holding_files(
    state_dir: Path, ledger: LedgerName, days: Collection[str]
) -> list[HeldFile]:
    """Every file of this ledger that holds a row filed under one of these UTC days.

    Raw files first, then the daily, monthly and yearly files, each kind oldest
    first. A compact file is named by its index and never opened; a raw file is
    read only as far as its envelope, to know it is one of its day's. A file
    that cannot be read, or an index entry whose file is not there, is refused
    by name rather than passed over.
    """
    wanted = sorted(set(days))
    strays = [day for day in wanted if not covers_fits(day, tier=Tier.RAW, period=None)]
    if strays:
        raise ValueError(f"{', '.join(strays)} is not a YYYY-MM-DD UTC day")
    held = [
        HeldFile(path=found.path, tier=Tier.RAW, period=None, covers=day, days=(day,))
        for day in wanted
        for found in raw_files.read_day_files(state_dir, ledger, day)
    ]
    for period in Period:
        index = _index(state_dir, ledger, period)
        if index is None:
            continue
        for entry in index.entries:
            covered = tuple(day for day in wanted if _inside(day, entry.covers))
            if not covered or not entry.rows:
                continue
            found = compact_file(state_dir, ledger, period, entry.covers)
            if found is None:
                where = paths.shown(state_dir, paths.compact_index_path(state_dir, ledger, period))
                raise ValueError(
                    f"{where} names {entry.covers} and no file holds it, so the rows of "
                    f"{', '.join(covered)} cannot be taken out of it"
                )
            held.append(
                HeldFile(
                    path=found,
                    tier=Tier.COMPACT,
                    period=period,
                    covers=entry.covers,
                    days=covered,
                )
            )
    return held


def rebuild_without(
    state_dir: Path, held: HeldFile, days: Collection[str], *, identity: WriterIdentity
) -> PeriodFile:
    """One compact file built again without the rows filed under these days, and written nowhere.

    Every other row keeps its cells, its identity and its order. `identity` goes
    in the envelope and says who rebuilt the file, and `built_from` is one: the
    file it was rebuilt from. A raw file is refused, because a day taken out
    takes it whole.
    """
    if held.period is None:
        raise ValueError(
            f"{paths.shown(state_dir, held.path)} is a raw file: it holds one writer's "
            "rows of one day, so a day taken out takes it whole rather than rebuilt"
        )
    envelope = read_envelope(held.path)
    if (envelope.tier, envelope.period, envelope.covers) != (
        Tier.COMPACT,
        held.period,
        held.covers,
    ):
        raise ValueError(
            f"{paths.shown(state_dir, held.path)} says it is a {envelope.tier.value} "
            f"file covering {envelope.covers}, and it was asked for as the "
            f"{held.period.value} file covering {held.covers}"
        )
    model = door_contract(envelope.ledger)
    gone = set(days)
    kept = [
        stored
        for stored in load_stored([held.path], model=model)
        if stored.identity.covers not in gone
    ]
    if held.period is Period.YEARLY:
        months: dict[str, list[StoredRow[Contract]]] = {}
        for stored in kept:
            months.setdefault(stored.identity.covers[:7], []).append(stored)
        return render_grouped_period(
            state_dir,
            [months[month] for month in sorted(months)],
            model=model,
            ledger=envelope.ledger,
            period=held.period,
            covers=held.covers,
            identity=identity,
            built_from=1,
        )
    return render_period(
        state_dir,
        kept,
        model=model,
        ledger=envelope.ledger,
        period=held.period,
        covers=held.covers,
        identity=identity,
        built_from=1,
    )
