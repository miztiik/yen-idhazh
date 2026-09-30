"""Which files - monthly, daily or raw - hold one ledger's current rows, and what those rows are.

A ledger the door files passes through three kinds of file as it ages: the raw
files its writers left under `state/raw/<ledger>/`, one compact file a day
under `state/compact/<ledger>/daily/`, and one compact file a month under
`state/compact/<ledger>/monthly/`. The compaction moves rows from each kind to
the next and deletes what it absorbed, so a reader that looked in one place
would lose the rows the other two hold. `ledger/raw_files.py` answers the same
question for the raw files alone; this module asks it of the whole ledger.

**Each date is read from exactly one file.** The two compact indexes say what
exists, and the rule is the one a browser will use: a date whose month
`index/monthly.json` names is read from that month's file; else a date
`index/daily.json` names is read from that day's file; else it is read from the
raw files of that day. A date both indexes name is read from its month, with a
warning, so a pass that stopped between writing a month and deleting its days
cannot count a row twice. The raw files of a day an index already names are
not read: they are a re-run's, waiting for the next compaction to take them.

**A hole is served and reported.** From the first day the compact periods cover
to the newest day `index/daily.json` names, every day must be named. One that
is not is a hole: its rows went somewhere no reader can find them. It is logged
by name, and any raw files it still has are read, which is the safe direction
for a retirement - an address read twice is still retired once.

**A missing file is named the way the query door names it** (`LedgerFault`):
a hole is `day-missing`, a file an index names that is not there is
`file-missing`, and a daily index with no monthly index beside it is
`index-missing`, because the compaction writes the two together. Each is a
warning naming the fault and the path, and the read goes on with what it can
find; a named file that is not there is never read as an empty one without a
word.

**What it reads, and how that grows (Guardrail #12).** Two small indexes, every
compact file they name - at most `monthly_window` month files and 45 to 76 day
files a ledger at the defaults - and the raw files of the days no index names.
While a ledger's compaction has not run live, that last part is every raw file
the ledger has, which is what a reader read before compaction existed.
`docs/concepts/growing-reads.md` lists the read.

**A file this build cannot read is skipped with a warning naming its path**,
for the reason `ledger/raw_files.py` gives. An index this build cannot read is
read as absent, with a warning naming it, so the reader serves every raw file it
can still find rather than nothing.

Every day and month here is a UTC day and month (CLAUDE.md section 2).
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from idhazh.contracts.base import Contract, StalePayloadError
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import keys, paths, raw_files
from idhazh.ledger.faults import LedgerFault
from idhazh.ledger.persist import StoredRow, load_stored

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Source:
    """Where one period of a ledger is read from: one compact file, or one raw day's files."""

    #: The UTC month (`YYYY-MM`) or day (`YYYY-MM-DD`) the source holds rows for.
    covers: str
    #: `monthly` or `daily` for a compact file, and None for a raw day.
    period: Period | None
    #: The one compact file, or the raw files of the day, oldest first.
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

    def source_of(self, day: str) -> Source | None:
        """The one source that serves this day, or None when nothing does."""
        return next((source for source in self.sources if source.holds(day)), None)


def _shown(state_dir: Path, path: Path) -> str:
    """A path as it may leave the process: under `state/`, POSIX (CLAUDE.md section 2)."""
    return f"{paths.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}"


def _index(state_dir: Path, ledger: LedgerName, period: Period) -> CompactIndex | None:
    """One period's index, or None when there is none or this build cannot read it."""
    path = paths.compact_index_path(state_dir, ledger, period)
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
    state_dir: Path, ledger: LedgerName
) -> tuple[CompactIndex | None, CompactIndex | None]:
    """The monthly and the daily index, each None when there is none or this build cannot read it.

    A daily index with no monthly index file beside it is `index-missing`, said
    once by name: the compaction writes the two together, so any month it packed
    is out of this read's sight.
    """
    monthly = _index(state_dir, ledger, Period.MONTHLY)
    daily = _index(state_dir, ledger, Period.DAILY)
    months = paths.compact_index_path(state_dir, ledger, Period.MONTHLY)
    if daily is not None and not months.is_file():
        logger.warning(
            "a daily index has no monthly index beside it fault=%s path=%s",
            LedgerFault.INDEX_MISSING,
            _shown(state_dir, months),
        )
    return monthly, daily


def compact_file(state_dir: Path, ledger: LedgerName, period: Period, covers: str) -> Path | None:
    """The compact file of one period, whichever format wrote it, or None when it is not there.

    An index entry names what a file covers and not its format, and the format
    is a knob that may change between two writes, so both addresses are asked.
    """
    for fmt in Format:
        found = paths.compact_path(state_dir, ledger, period, covers, fmt=fmt)
        if found.is_file():
            return found
    return None


def _last_day(month: str) -> str:
    """The last UTC day of a `YYYY-MM` month."""
    year, number = int(month[:4]), int(month[5:7])
    first_after = date(year + number // 12, number % 12 + 1, 1)
    return (first_after - timedelta(days=1)).isoformat()


def _holes(sources: list[Source], months: list[str], days: list[str]) -> tuple[str, ...]:
    """Every day from the first the compact periods cover to their edge that no compact file serves.

    The edge is the newest day the daily index names, or the last day of the
    newest month when that is later. Before the first day nothing was compacted,
    and after the edge nothing has been yet, so neither is a hole.
    """
    if not months and not days:
        return ()
    first = f"{months[0]}-01" if months else days[0]
    edges = ([days[-1]] if days else []) + ([_last_day(months[-1])] if months else [])
    compact = [source for source in sources if source.period is not None]
    missing: list[str] = []
    day, edge = date.fromisoformat(first), date.fromisoformat(max(edges))
    while day <= edge:
        stamp = day.isoformat()
        if not any(source.holds(stamp) for source in compact):
            missing.append(stamp)
        day += timedelta(days=1)
    return tuple(missing)


def list_ledger_files(state_dir: Path, ledger: LedgerName) -> LedgerFiles:
    """Every source this ledger is read from, oldest first, each date from exactly one."""
    monthly, daily = _indexes(state_dir, ledger)
    months = [entry.covers for entry in monthly.entries] if monthly else []
    days = [entry.covers for entry in daily.entries] if daily else []
    sources: list[Source] = []
    absorbed = set(months)
    for period, covered in ((Period.MONTHLY, months), (Period.DAILY, days)):
        for covers in covered:
            if period is Period.DAILY and covers[:7] in absorbed:
                logger.warning(
                    "both compact indexes name a day, and it is read from its month "
                    "ledger=%s day=%s",
                    ledger.value,
                    covers,
                )
                continue
            found = compact_file(state_dir, ledger, period, covers)
            if found is None:
                logger.warning(
                    "a compact index names a file that is not there fault=%s path=%s covers=%s",
                    LedgerFault.FILE_MISSING,
                    _shown(state_dir, paths.compact_index_path(state_dir, ledger, period)),
                    covers,
                )
                continue
            sources.append(Source(covers=covers, period=period, paths=(found,)))
    named = set(days)
    unnamed = {
        day
        for day in raw_files.raw_days(state_dir, ledger)
        if day not in named and day[:7] not in absorbed
    }
    by_day: dict[str, list[Path]] = {}
    for held in raw_files.list_raw_files(state_dir, ledger, days=unnamed):
        by_day.setdefault(held.envelope.covers, []).append(held.path)
    sources.extend(
        Source(covers=day, period=None, paths=tuple(held)) for day, held in by_day.items()
    )
    sources.sort(key=lambda source: source.covers)
    return LedgerFiles(sources=tuple(sources), holes=_holes(sources, months, days))


def load_ledger_rows[C: Contract](
    state_dir: Path, ledger: LedgerName, *, model: type[C]
) -> list[C]:
    """This ledger's current rows, oldest first, settled once across all three kinds of file.

    `model` must be the contract the door table in `ledger/keys.py` pairs with
    this ledger, and the key comes from the same row, so a reader cannot settle
    a ledger by another ledger's rule. Rows are settled by `raw_files.settle_rows`,
    each file on its own: one file's rows per work unit, the last file of its
    highest attempt, then the first row per key.
    """
    paired = keys.door_contract(ledger)
    if paired is not model:
        raise ValueError(
            f"{ledger.value} rows are {paired.__name__} in the door table in "
            f"idhazh/ledger/keys.py, and this read asked for {model.__name__}"
        )
    found = list_ledger_files(state_dir, ledger)
    if found.holes:
        logger.warning(
            "days no compact file holds are read from their raw files, if any are left "
            "fault=%s path=%s holes=%s",
            LedgerFault.DAY_MISSING,
            _shown(state_dir, paths.compact_index_path(state_dir, ledger, Period.DAILY)),
            ",".join(found.holes),
        )
    stored: list[list[StoredRow[C]]] = []
    for source in found.sources:
        for path in source.paths:
            try:
                stored.append(load_stored([path], model=model))
            except ValueError as refusal:
                logger.warning(
                    "skipped a ledger file path=%s reason=%s", _shown(state_dir, path), refusal
                )
    return [held.row for held in raw_files.settle_rows(stored, keys.door_key(ledger))]


def month_days(month: str) -> list[str]:
    """Every UTC day of a `YYYY-MM` month, first to last."""
    day, last = date.fromisoformat(f"{month}-01"), date.fromisoformat(_last_day(month))
    days: list[str] = []
    while day <= last:
        days.append(day.isoformat())
        day += timedelta(days=1)
    return days


def held_months(state_dir: Path, ledger: LedgerName) -> list[str]:
    """Every UTC month this ledger may hold a row in, oldest first, from names alone.

    The two indexes and the names of the raw day folders: no data file is
    opened, so it costs one listing and two small reads whatever the ledger
    holds. A month named here can still hold no row - a quiet day is a zero-row
    file with an index entry - and `load_days` over its days then returns none.
    """
    months: set[str] = set()
    for period in Period:
        index = _index(state_dir, ledger, period)
        if index is not None:
            months.update(entry.covers[:7] for entry in index.entries)
    months.update(day[:7] for day in raw_files.raw_days(state_dir, ledger))
    return sorted(months)


def held_days(state_dir: Path, ledger: LedgerName) -> list[str]:
    """Every UTC day this ledger holds a row for, oldest first, from names alone.

    A day the daily index names with rows, or a raw day folder that holds a
    file. A day the daily index names with none is a quiet day and is left out.
    A month file's index counts the month's rows and not its days, so every day
    of an absorbed month is named, and `load_days` returns nothing for the ones
    that held none. No data file is opened.
    """
    days: set[str] = set(raw_files.raw_days(state_dir, ledger))
    daily = _index(state_dir, ledger, Period.DAILY)
    if daily is not None:
        days.update(entry.covers for entry in daily.entries if entry.rows)
    monthly = _index(state_dir, ledger, Period.MONTHLY)
    if monthly is not None:
        for entry in monthly.entries:
            if entry.rows:
                days.update(month_days(entry.covers))
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
    state_dir: Path, ledger: LedgerName, period: Period, covers: str, *, model: type[C]
) -> list[StoredRow[C]]:
    """The rows of the compact file an index names, or none with a warning naming the fault."""
    found = compact_file(state_dir, ledger, period, covers)
    if found is None:
        logger.warning(
            "a compact index names a file that is not there fault=%s path=%s covers=%s",
            LedgerFault.FILE_MISSING,
            _shown(state_dir, paths.compact_index_path(state_dir, ledger, period)),
            covers,
        )
        return []
    return _stored_or_skipped(state_dir, found, model=model)


def load_days[C: Contract](
    state_dir: Path, ledger: LedgerName, days: Collection[str], *, model: type[C]
) -> list[C]:
    """These UTC days' current rows, each day settled on its own, oldest day first.

    The bounded read a caller asking about named days takes (Guardrail #12): the
    two indexes, the one compact file that serves each day, and the raw files of
    only the days no index names. A day is read from exactly one place by the
    rule `list_ledger_files` gives, and a month file serves only the rows its
    raw files first filed under that day.

    Each day is settled on its own, as `day_shards.settled_day` settled a CSV
    day: a key that carries no date - the eval ledger's - is one measurement
    within a day, and the question across days belongs to its writer.
    """
    paired = keys.door_contract(ledger)
    if paired is not model:
        raise ValueError(
            f"{ledger.value} rows are {paired.__name__} in the door table in "
            f"idhazh/ledger/keys.py, and this read asked for {model.__name__}"
        )
    key = keys.door_key(ledger)
    monthly, daily = _indexes(state_dir, ledger)
    months = {entry.covers for entry in monthly.entries} if monthly else set()
    compact_days = {entry.covers for entry in daily.entries} if daily else set()
    wanted = sorted(set(days))
    raw_wanted = {day for day in wanted if day[:7] not in months and day not in compact_days}
    raw_by_day: dict[str, list[Path]] = {}
    for held in raw_files.list_raw_files(state_dir, ledger, days=raw_wanted):
        raw_by_day.setdefault(held.envelope.covers, []).append(held.path)
    month_rows: dict[str, list[StoredRow[C]]] = {}
    rows: list[C] = []
    for day in wanted:
        files: list[list[StoredRow[C]]]
        if day[:7] in months:
            month = day[:7]
            if month not in month_rows:
                month_rows[month] = _compact_rows(
                    state_dir, ledger, Period.MONTHLY, month, model=model
                )
            files = [[held for held in month_rows[month] if held.identity.covers == day]]
        elif day in compact_days:
            files = [_compact_rows(state_dir, ledger, Period.DAILY, day, model=model)]
        else:
            files = [
                _stored_or_skipped(state_dir, path, model=model)
                for path in raw_by_day.get(day, [])
            ]
        rows.extend(held.row for held in raw_files.settle_rows(files, key))
    return rows
