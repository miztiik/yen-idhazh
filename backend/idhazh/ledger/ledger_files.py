"""Which files - yearly, monthly, daily or raw - hold one ledger's current rows, and what they are.

A ledger the door files passes through up to four kinds of file as it ages: the
raw files its writers left under `state/raw/<ledger>/`, one compact file a day
under `state/compact/<ledger>/daily/`, one compact file a month under
`state/compact/<ledger>/monthly/`, and - where its compaction packs years - one
compact file a year under `state/compact/<ledger>/yearly/`. The compaction moves
rows from each kind to the next and deletes what it absorbed, so a reader that
looked in one place would lose the rows the others hold. `ledger/raw_files.py`
answers the same question for the raw files alone; this module asks it of the
whole ledger.

**Each date is read from exactly one file.** The compact indexes say what
exists, and the rule is the one the browser uses: a date whose year
`index/yearly.json` names is read from that year's file; else a date whose month
`index/monthly.json` names is read from that month's file; else a date
`index/daily.json` names is read from that day's file; else it is read from the
raw files of that day. A date two indexes name is read from the coarser one,
with a warning, so a pass that stopped between writing a period and deleting
what it absorbed cannot count a row twice. The raw files of a day an index
already names are not read: they are a re-run's, waiting for the next
compaction to take them.

**A hole is served and reported.** From the first day the compact periods cover
to the newest day they reach, every day must be named. One that is not is a
hole: its rows went somewhere no reader can find them. It is logged by name,
and any raw files it still has are read, which is the safe direction for a
retirement - an address read twice is still retired once.

**An entry with no file serves its days with no rows.** An `empty` period held
no row and a `lost` day lost its rows, so neither has a file to look for, and
neither is a hole, because an index names it. A day an index records lost - a
daily entry `lost`, or a day a month or a year lists in its `lost_days` - is
reported once as a gap and never as a missing file: nothing is missing that a
re-pack could restore.

**A missing file is named the way the query door names it** (`LedgerFault`):
a hole is `day-missing`, a file a packed entry names that is not there is
`file-missing`, and a daily index with no monthly or yearly index beside it is
`index-missing`, because the compaction writes the three together. Each is a
warning naming the fault and the path, and the read goes on with what it can
find; a named file that is not there is never read as an empty one without a
word.

**What it reads, and how that grows (Guardrail #12).** Three small indexes,
every compact file they name - at most `monthly_window` month files and from
`daily_keep_days` to `daily_keep_days` plus 31 day files a ledger, or for a
ledger that packs years, one file a year kept for ever and at most about two
years of month files - and the raw files of the days no index names. While a
ledger's compaction has not run live, that last part is every raw file the
ledger has, which is what a reader read before compaction existed.
`docs/concepts/growing-reads.md` lists the read.

**A file this build cannot read is skipped with a warning naming its path**,
for the reason `ledger/raw_files.py` gives. An index this build cannot read is
read as absent, with a warning naming it, so the reader serves every raw file it
can still find rather than nothing.

Every day, month and year here is a UTC one (CLAUDE.md section 2).
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from idhazh.contracts.base import Contract, StalePayloadError
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_fault import LedgerFault
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import keys, paths, raw_files
from idhazh.ledger.persist import StoredRow, load_stored

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Source:
    """Where one period of a ledger is read from: one compact file, or one raw day's files."""

    #: The UTC year (`YYYY`), month (`YYYY-MM`) or day (`YYYY-MM-DD`) the source holds rows for.
    covers: str
    #: `yearly`, `monthly` or `daily` for a compact file, and None for a raw day.
    period: Period | None
    #: The one compact file, or the raw files of the day, oldest first. None for an
    #: entry with no file: an `empty` period or a `lost` day.
    paths: tuple[Path, ...]

    def holds(self, day: str) -> bool:
        """Whether this source serves the rows of one UTC day."""
        return day == self.covers or day.startswith(f"{self.covers}-")


@dataclass(frozen=True, slots=True)
class LedgerFiles:
    """Every source one ledger is read from, oldest first, and the days no compact file holds."""

    sources: tuple[Source, ...]
    #: Days inside the compact span that no compact file serves, oldest first.
    holes: tuple[str, ...]
    #: Days an index records lost, oldest first. Each has no row anywhere and no file.
    lost: tuple[str, ...]

    def source_of(self, day: str) -> Source | None:
        """The one source that serves this day, or None when nothing does."""
        return next((source for source in self.sources if source.holds(day)), None)


def _shown(state_dir: Path, path: Path) -> str:
    """A path as it may leave the process: under `state/`, POSIX (CLAUDE.md section 2)."""
    return f"{paths.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}"


def _days_lost(entry: CompactEntry) -> list[str]:
    """The UTC days an entry records lost: the day itself for a `lost` day, else its `lost_days`."""
    return [entry.covers] if entry.state is EntryState.LOST else list(entry.lost_days)


def _report_lost(ledger: LedgerName, lost: Collection[str]) -> None:
    """One warning for the days an index records lost: a gap, never a missing file."""
    if lost:
        logger.warning(
            "days an index records lost have no rows, and no file is read for them "
            "ledger=%s lost=%s",
            ledger.value,
            ",".join(sorted(lost)),
        )


def _index(
    state_dir: Path,
    ledger: LedgerName,
    period: Period,
    *,
    registry: paths.DoorRegistry | None = None,
) -> CompactIndex | None:
    """One period's index, or None when there is none or this build cannot read it."""
    path = paths.compact_index_path(state_dir, ledger, period, registry=registry)
    if not path.is_file():
        return None
    try:
        index = CompactIndex.read(path)
    except (ValueError, StalePayloadError) as refusal:
        logger.warning(
            "read a compact index as absent path=%s reason=%s", _shown(state_dir, path), refusal
        )
        return None
    if (index.ledger, index.period) != (ledger, period):
        logger.warning(
            "read a compact index as absent path=%s reason=it names %s %s",
            _shown(state_dir, path),
            index.ledger.value,
            index.period.value,
        )
        return None
    return index


def _indexes(
    state_dir: Path, ledger: LedgerName, *, registry: paths.DoorRegistry | None = None
) -> tuple[CompactIndex | None, CompactIndex | None, CompactIndex | None]:
    """The yearly, monthly and daily index, each None when absent or unreadable by this build.

    A daily index with no monthly or no yearly index file beside it is
    `index-missing`, said once by name for each: the compaction writes the three
    together, so any month or year it packed is out of this read's sight.
    """
    yearly = _index(state_dir, ledger, Period.YEARLY, registry=registry)
    monthly = _index(state_dir, ledger, Period.MONTHLY, registry=registry)
    daily = _index(state_dir, ledger, Period.DAILY, registry=registry)
    if daily is not None:
        for period in (Period.MONTHLY, Period.YEARLY):
            path = paths.compact_index_path(state_dir, ledger, period, registry=registry)
            if not path.is_file():
                logger.warning(
                    "a daily index has no %s index beside it fault=%s path=%s",
                    period.value,
                    LedgerFault.INDEX_MISSING,
                    _shown(state_dir, path),
                )
    return yearly, monthly, daily


def compact_file(
    state_dir: Path,
    ledger: LedgerName,
    period: Period,
    covers: str,
    *,
    registry: paths.DoorRegistry | None = None,
) -> Path | None:
    """The compact file of one period, whichever format wrote it, or None when it is not there.

    An index entry names what a file covers and not its format, and the format
    is a knob that may change between two writes, so both addresses are asked.
    """
    for fmt in Format:
        found = paths.compact_path(state_dir, ledger, period, covers, fmt=fmt, registry=registry)
        if found.is_file():
            return found
    return None


def _last_day(month: str) -> str:
    """The last UTC day of a `YYYY-MM` month."""
    year, number = int(month[:4]), int(month[5:7])
    first_after = date(year + number // 12, number % 12 + 1, 1)
    return (first_after - timedelta(days=1)).isoformat()


def _year_months(year: str) -> list[str]:
    """Every UTC month of a `YYYY` year, January first."""
    return [f"{year}-{number:02d}" for number in range(1, 13)]


def _holes(
    sources: list[Source], years: list[str], months: list[str], days: list[str]
) -> tuple[str, ...]:
    """Every day from the first the compact periods cover to their edge that no compact file serves.

    The edge is the newest day the daily index names, or the last day of the
    newest month or year when that is later. Before the first day nothing was
    compacted, and after the edge nothing has been yet, so neither is a hole.
    """
    if not years and not months and not days:
        return ()
    firsts = [f"{years[0]}-01-01"] if years else []
    firsts += [f"{months[0]}-01"] if months else []
    firsts += [days[0]] if days else []
    edges = [days[-1]] if days else []
    edges += [_last_day(months[-1])] if months else []
    edges += [f"{years[-1]}-12-31"] if years else []
    compact = [source for source in sources if source.period is not None]
    missing: list[str] = []
    day, edge = date.fromisoformat(min(firsts)), date.fromisoformat(max(edges))
    while day <= edge:
        stamp = day.isoformat()
        if not any(source.holds(stamp) for source in compact):
            missing.append(stamp)
        day += timedelta(days=1)
    return tuple(missing)


def _coarser(period: Period, covers: str, *, packed: set[str], absorbed: set[str]) -> Period | None:
    """The coarser period whose index already names what this entry covers, or None."""
    if period is not Period.YEARLY and covers[:4] in packed:
        return Period.YEARLY
    if period is Period.DAILY and covers[:7] in absorbed:
        return Period.MONTHLY
    return None


#: What a warning calls the stretch of time each period's file covers.
_STRETCH: Final[dict[Period, str]] = {
    Period.DAILY: "day",
    Period.MONTHLY: "month",
    Period.YEARLY: "year",
}


def list_ledger_files(
    state_dir: Path, ledger: LedgerName, *, registry: paths.DoorRegistry | None = None
) -> LedgerFiles:
    """Every source this ledger is read from, oldest first, each date from exactly one."""
    yearly, monthly, daily = _indexes(state_dir, ledger, registry=registry)
    named_by: dict[Period, list[CompactEntry]] = {
        Period.YEARLY: yearly.entries if yearly else [],
        Period.MONTHLY: monthly.entries if monthly else [],
        Period.DAILY: daily.entries if daily else [],
    }
    years = [entry.covers for entry in named_by[Period.YEARLY]]
    months = [entry.covers for entry in named_by[Period.MONTHLY]]
    days = [entry.covers for entry in named_by[Period.DAILY]]
    sources: list[Source] = []
    lost: list[str] = []
    packed, absorbed = set(years), set(months)
    for period, entries in named_by.items():
        for entry in entries:
            covers = entry.covers
            coarser = _coarser(period, covers, packed=packed, absorbed=absorbed)
            if coarser is not None:
                logger.warning(
                    "both compact indexes name a %s, and it is read from its %s "
                    "ledger=%s covers=%s",
                    _STRETCH[period],
                    _STRETCH[coarser],
                    ledger.value,
                    covers,
                )
                continue
            lost.extend(_days_lost(entry))
            if not entry.names_file:
                sources.append(Source(covers=covers, period=period, paths=()))
                continue
            found = compact_file(state_dir, ledger, period, covers, registry=registry)
            if found is None:
                logger.warning(
                    "a compact index names a file that is not there fault=%s path=%s covers=%s",
                    LedgerFault.FILE_MISSING,
                    _shown(
                        state_dir,
                        paths.compact_index_path(state_dir, ledger, period, registry=registry),
                    ),
                    covers,
                )
                continue
            sources.append(Source(covers=covers, period=period, paths=(found,)))
    named = set(days)
    unnamed = {
        day
        for day in raw_files.raw_days(state_dir, ledger, registry=registry)
        if day not in named and day[:7] not in absorbed and day[:4] not in packed
    }
    by_day: dict[str, list[Path]] = {}
    for held in raw_files.list_raw_files(state_dir, ledger, days=unnamed, registry=registry):
        by_day.setdefault(held.envelope.covers, []).append(held.path)
    sources.extend(
        Source(covers=day, period=None, paths=tuple(held)) for day, held in by_day.items()
    )
    sources.sort(key=lambda source: source.covers)
    return LedgerFiles(
        sources=tuple(sources),
        holes=_holes(sources, years, months, days),
        lost=tuple(sorted(lost)),
    )


def load_ledger_rows[C: Contract](
    state_dir: Path,
    ledger: LedgerName,
    *,
    model: type[C],
    key: tuple[str, ...] | None = None,
    registry: paths.DoorRegistry | None = None,
) -> list[C]:
    """This ledger's current rows, oldest first, settled once across every kind of file.

    `model` must be the contract the door table in `ledger/keys.py` pairs with
    this ledger, and the key comes from the same row, so a reader cannot settle
    a ledger by another ledger's rule. Rows are settled by `raw_files.settle_rows`,
    each file on its own: one file's rows per work unit, the last file of its
    highest attempt, then the first row per key.
    """
    if key is None:
        paired = keys.door_contract(ledger)
        if paired is not model:
            raise ValueError(
                f"{ledger.value} rows are {paired.__name__} in the door table in "
                f"idhazh/ledger/keys.py, and this read asked for {model.__name__}"
            )
        key = keys.door_key(ledger)
    found = list_ledger_files(state_dir, ledger, registry=registry)
    if found.holes:
        logger.warning(
            "days no compact file holds are read from their raw files, if any are left "
            "fault=%s path=%s holes=%s",
            LedgerFault.DAY_MISSING,
            _shown(
                state_dir,
                paths.compact_index_path(state_dir, ledger, Period.DAILY, registry=registry),
            ),
            ",".join(found.holes),
        )
    _report_lost(ledger, found.lost)
    stored: list[list[StoredRow[C]]] = []
    for source in found.sources:
        for path in source.paths:
            try:
                stored.append(load_stored([path], model=model))
            except ValueError as refusal:
                logger.warning(
                    "skipped a ledger file path=%s reason=%s", _shown(state_dir, path), refusal
                )
    return [held.row for held in raw_files.settle_rows(stored, key)]


def month_days(month: str) -> list[str]:
    """Every UTC day of a `YYYY-MM` month, first to last."""
    day, last = date.fromisoformat(f"{month}-01"), date.fromisoformat(_last_day(month))
    days: list[str] = []
    while day <= last:
        days.append(day.isoformat())
        day += timedelta(days=1)
    return days


def held_months(
    state_dir: Path, ledger: LedgerName, *, registry: paths.DoorRegistry | None = None
) -> list[str]:
    """Every UTC month this ledger may hold a row in, oldest first, from names alone.

    The three indexes and the names of the raw day folders: no data file is
    opened, so it costs one listing and three small reads whatever the ledger
    holds. A month named here can still hold no row - a quiet day is an index
    entry with no file, and a packed year names all twelve of its months -
    and `load_days` over its days then returns none.
    """
    months: set[str] = set()
    for period in Period:
        index = _index(state_dir, ledger, period, registry=registry)
        if index is None:
            continue
        for entry in index.entries:
            if period is Period.YEARLY:
                months.update(_year_months(entry.covers))
            else:
                months.add(entry.covers[:7])
    months.update(day[:7] for day in raw_files.raw_days(state_dir, ledger, registry=registry))
    return sorted(months)


def held_days(
    state_dir: Path, ledger: LedgerName, *, registry: paths.DoorRegistry | None = None
) -> list[str]:
    """Every UTC day this ledger holds a row for, oldest first, from names alone.

    A day the daily index names with rows, or a raw day folder that holds a
    file. A day the daily index names with none is a quiet day and is left out.
    A month or year file's index counts its rows and not its days, so every day
    of an absorbed month or a packed year is named, and `load_days` returns
    nothing for the ones that held none. No data file is opened.
    """
    days: set[str] = set(raw_files.raw_days(state_dir, ledger, registry=registry))
    daily = _index(state_dir, ledger, Period.DAILY, registry=registry)
    if daily is not None:
        days.update(entry.covers for entry in daily.entries if entry.rows)
    monthly = _index(state_dir, ledger, Period.MONTHLY, registry=registry)
    if monthly is not None:
        for entry in monthly.entries:
            if entry.rows:
                days.update(month_days(entry.covers))
    yearly = _index(state_dir, ledger, Period.YEARLY, registry=registry)
    if yearly is not None:
        for entry in yearly.entries:
            if entry.rows:
                for month in _year_months(entry.covers):
                    days.update(month_days(month))
    return sorted(days)


def _stored_or_skipped[C: Contract](
    state_dir: Path, path: Path, *, model: type[C]
) -> list[StoredRow[C]]:
    """One file's rows beside their identity, or none with a warning naming it."""
    try:
        return load_stored([path], model=model)
    except ValueError as refusal:
        logger.warning("skipped a ledger file path=%s reason=%s", _shown(state_dir, path), refusal)
        return []


def _compact_rows[C: Contract](
    state_dir: Path,
    ledger: LedgerName,
    period: Period,
    covers: str,
    *,
    model: type[C],
    registry: paths.DoorRegistry | None = None,
) -> list[StoredRow[C]]:
    """The rows of the file a packed entry names, or none with a warning naming the fault."""
    found = compact_file(state_dir, ledger, period, covers, registry=registry)
    if found is None:
        logger.warning(
            "a compact index names a file that is not there fault=%s path=%s covers=%s",
            LedgerFault.FILE_MISSING,
            _shown(
                state_dir, paths.compact_index_path(state_dir, ledger, period, registry=registry)
            ),
            covers,
        )
        return []
    return _stored_or_skipped(state_dir, found, model=model)


def load_days[C: Contract](
    state_dir: Path,
    ledger: LedgerName,
    days: Collection[str],
    *,
    model: type[C],
    registry: paths.DoorRegistry | None = None,
    key: tuple[str, ...] | None = None,
) -> list[C]:
    """These UTC days' current rows, each day settled on its own, oldest day first.

    The bounded read a caller asking about named days takes (Guardrail #12): the
    three indexes, the one compact file that serves each day, and the raw files
    of only the days no index names. A day is read from exactly one place by the
    rule `list_ledger_files` gives, and a month or year file serves only the rows
    its raw files first filed under that day. A day in a packed year opens the
    whole year's file once, whatever else is asked of that year.

    Each day is settled on its own, as `day_shards.settled_day` settled a CSV
    day: a key that carries no date - the eval ledger's - is one measurement
    within a day, so the same words filed on two days are kept under each.
    `load_ledger_rows` settles once across every day and keeps the first.
    """
    if key is None:
        paired = keys.door_contract(ledger)
        if paired is not model:
            raise ValueError(
                f"{ledger.value} rows are {paired.__name__} in the door table in "
                f"idhazh/ledger/keys.py, and this read asked for {model.__name__}"
            )
        key = keys.door_key(ledger)
    yearly, monthly, daily = _indexes(state_dir, ledger, registry=registry)
    years = {entry.covers: entry for entry in yearly.entries} if yearly else {}
    months = {entry.covers: entry for entry in monthly.entries} if monthly else {}
    compact_days = {entry.covers: entry for entry in daily.entries} if daily else {}
    wanted = sorted(set(days))
    raw_wanted = {
        day
        for day in wanted
        if day[:4] not in years and day[:7] not in months and day not in compact_days
    }
    raw_by_day: dict[str, list[Path]] = {}
    for held in raw_files.list_raw_files(state_dir, ledger, days=raw_wanted, registry=registry):
        raw_by_day.setdefault(held.envelope.covers, []).append(held.path)
    period_rows: dict[tuple[Period, str], list[StoredRow[C]]] = {}

    def rows_of(period: Period, entry: CompactEntry) -> list[StoredRow[C]]:
        """One period's rows, read once however many of its days are asked; none with no file."""
        if (period, entry.covers) not in period_rows:
            period_rows[period, entry.covers] = (
                _compact_rows(
                    state_dir, ledger, period, entry.covers, model=model, registry=registry
                )
                if entry.names_file
                else []
            )
        return period_rows[period, entry.covers]

    rows: list[C] = []
    lost: list[str] = []
    for day in wanted:
        files: list[list[StoredRow[C]]]
        if day[:4] in years:
            period, entry = Period.YEARLY, years[day[:4]]
        elif day[:7] in months:
            period, entry = Period.MONTHLY, months[day[:7]]
        elif day in compact_days:
            period, entry = Period.DAILY, compact_days[day]
        else:
            files = [
                _stored_or_skipped(state_dir, path, model=model) for path in raw_by_day.get(day, [])
            ]
            rows.extend(held.row for held in raw_files.settle_rows(files, key))
            continue
        if day in _days_lost(entry):
            lost.append(day)
        files = [[held for held in rows_of(period, entry) if held.identity.covers == day]]
        rows.extend(held.row for held in raw_files.settle_rows(files, key))
    _report_lost(ledger, lost)
    return rows
