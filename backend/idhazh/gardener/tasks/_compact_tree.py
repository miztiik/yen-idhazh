"""What one ledger's compact periods hold as a compaction pass finds them, and what it changes.

A pass reads the three watermarks, the three period indexes and the names of the
raw day folders once, then decides period by period what to write and what to
delete. File decisions are `Change` records; indexes and watermarks stay
pending until `finish` serializes each final value once. The resulting order
is data, indexes from coarsest to finest, deletions, then watermarks.
Nothing touches the disk until
`apply`, which a dry run never calls. So a dry run and a live run make the same
decisions from the same reads, and the list a dry run reports is the list a
live run carries out, file for file. A file a monthly window would delete while
that window only reports is no change at all: the pass names it with `spare`,
so the record can count it, and keeps it.

**Names come from the task's listing, and content is fetched before it is
read.** The raw day folders, which compact files exist and what
each weighs are all read off the listing. The watermarks and the indexes are
fetched once, before they are read, and each step fetches the day or month
folders it opens before it opens one. The drop, year, month and day steps
choose their periods as they run, so each names what it reads of them first,
through `name_drops`, `name_years`, `name_months` and `name_days`, and the
listing then answers for them from the same commit. A day step with no mark
looks back over months no step has named yet, and the pass names those through
`name_raw_months` before it chooses.

**No pass writes a path it deletes, or deletes a path it writes.** The shard
that lands the pass refuses a path on both lists, so one pass that did either
would stall every later wake. `write` and `delete` refuse it at the moment it
would happen, naming the path, and the pass then fails before anything lands.

**A file the pass cannot read is moved aside, never deleted.** `read_raw_day`
reads one day's raw files oldest first and names each one whose envelope or
rows this build cannot read; `set_aside` moves such a file, or a packed file
that cannot be read when its month or year closes, to
`state/raw/<ledger>/set-aside/` under its path, and the period that set it
aside counts it. A move keeps the same bytes in git, so its delete frees
nothing and is weighed at 0. A day holding more raw files than one period is
built from gives its oldest, and the rest wait in its folder for the next wake.

**A step takes only what fits the shard's download budget.** `fit_to_budget`
gives the longest run of a step's periods, oldest first, whose fetch fits what
is left of it, read off the listing's own sizes, and `fetch` fetches that run
in one download. The first period that does not fit stops the step
(`stop_over_budget`): `ceiling` when a later wake has room for it, `failed` by
name when the period alone is larger than the whole budget, which only a person
can raise.

The watermarks and the indexes are read by `ledger_marks`, which stops the pass
on one this build cannot trust, rather than read it as absent, and says why.

**A ledger's three indexes exist together.** Whatever writes one writes each of
the others the ledger has none of yet, and those are empty: a period with no
watermark was never packed, so an empty list is the truth about it. A reader
that finds `index/daily.json` can then tell a lost `index/monthly.json` or
`index/yearly.json` from a period never packed, and asks for no file that is not
there.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple, assert_never

from idhazh import atomic_write, day_partition, ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import ledger_marks, named_trees
from idhazh.gardener.file_listing import FileListing, OverBudgetError
from idhazh.ledger import StoredRow
from idhazh.site_weight import BYTES_PER_MB

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Change:
    """One file a pass writes whole, or deletes."""

    path: Path
    #: The bytes to write, or None to delete the file.
    data: bytes | None
    #: What a write writes, or what a delete frees, in bytes.
    size: int


@dataclass(frozen=True, slots=True)
class Stop:
    """Why one step of a pass stopped short, and the period the next pass starts at.

    A step that did everything it had returns no `Stop` at all.
    """

    because: StopReason
    #: The day, month or year the next pass takes first.
    resume_from: str


class PeriodFetch(NamedTuple):
    """What fetching one period downloads: whole folders, and files whose folder-mates come too."""

    folders: tuple[Path, ...] = ()
    beside: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class RawDay[C: Contract]:
    """One raw day as a pass reads it, before it decides anything about the day."""

    #: Each file the day is built from, oldest first, beside its rows.
    taken: list[tuple[Path, list[StoredRow[C]]]]
    #: Each file this build cannot read, beside why, for the pass to move aside.
    unreadable: list[tuple[Path, str]]
    #: How many readable files wait in the folder, past the most one period is built from.
    carried: int


def stop_over_budget(which: LedgerName, covers: str, *, needed: int, budget: int) -> Stop:
    """Where a period whose download does not fit stops its step, said once by name.

    `needed` is what fetching the period alone downloads, and `budget` the
    shard's whole budget, both in bytes. `ceiling` when a later wake, with its
    whole budget, has room for the period; `failed` when the period alone is
    larger than the whole budget, because no wake could ever take it and only a
    person can raise `max_downloaded_mb`.
    """
    if needed > budget:
        logger.error(
            "a period is larger than the shard's whole download budget, so no wake can take "
            "it ledger=%s period=%s bytes=%s max_downloaded_mb=%s",
            which.value,
            covers,
            needed,
            budget // BYTES_PER_MB,
        )
        return Stop(StopReason.FAILED, covers)
    logger.info(
        "a period waits for a wake with room in the shard's download budget "
        "ledger=%s period=%s bytes=%s",
        which.value,
        covers,
        needed,
    )
    return Stop(StopReason.CEILING, covers)


@dataclass(slots=True)
class CompactTree:
    """One ledger's compact state as a pass sees it, and every change the pass has decided on."""

    state_dir: Path
    ledger: LedgerName
    #: The files under the folders the compaction owns, which is where every
    #: name the pass decides from comes from.
    listing: FileListing
    #: The newest day, month and year compacted, or None when that period never has been.
    daily_through: str | None
    monthly_through: str | None
    yearly_through: str | None
    #: Each period's index, by what each entry covers.
    daily: dict[str, CompactEntry]
    monthly: dict[str, CompactEntry]
    yearly: dict[str, CompactEntry]
    #: Every UTC day with a raw folder that holds something, oldest first.
    raw_days: list[str]
    #: How many raw day folders the pass listed, before any step set a day aside.
    listed: int = 0
    #: The periods whose index the pass found on disk.
    indexed: frozenset[Period] = frozenset()
    changes: list[Change] = field(default_factory=list)
    #: Every file the pass read or weighed.
    looked: set[Path] = field(default_factory=set)
    #: Every file a live monthly window would delete that the pass keeps, because
    #: the window only reports. It is not a change, so `apply` never sees it.
    spares: list[Path] = field(default_factory=list)
    pending_indexes: set[Period] = field(default_factory=set)
    pending_watermarks: dict[Period, Watermark] = field(default_factory=dict)

    @classmethod
    def read(cls, state_dir: Path, ledger_name: LedgerName, listing: FileListing) -> CompactTree:
        """The three watermarks, the three indexes and the raw day folder names, read once."""
        marks = ledger_marks.read_marks(state_dir, ledger_name, listing)
        # A wake names no raw folder: each step names the raw folders it reads.
        raw_days = (
            named_trees.raw_days(listing, state_dir, ledger_name)
            if listing.saw_any_of(ledger.raw_root(state_dir, ledger_name))
            else []
        )
        return cls(
            state_dir=state_dir,
            ledger=ledger_name,
            listing=listing,
            daily_through=marks.through[Period.DAILY],
            monthly_through=marks.through[Period.MONTHLY],
            yearly_through=marks.through[Period.YEARLY],
            daily=dict(marks.entries[Period.DAILY]),
            monthly=dict(marks.entries[Period.MONTHLY]),
            yearly=dict(marks.entries[Period.YEARLY]),
            raw_days=raw_days,
            listed=len(raw_days),
            indexed=marks.indexed,
        )

    def raw_day_folder(self, day: str) -> Path:
        """The raw folder one UTC day's writer files sit in."""
        return ledger.raw_root(self.state_dir, self.ledger).joinpath(day[:4], day[5:7], day[8:10])

    def raw_month_folder(self, month: str) -> Path:
        """The raw folder a `YYYY-MM` month's day folders sit in."""
        return ledger.raw_root(self.state_dir, self.ledger).joinpath(month[:4], month[5:7])

    def name_drops(self, months: Sequence[str]) -> None:
        """Name what the drop steps read of these months: each one's month file and raw folder.

        Each month file, whichever format wrote it, and each raw month folder are
        listed from the commit now, and the raw days found there are taken in:
        the drop step chose the months as it ran. A drop deletes by these names
        and opens nothing, so nothing here is fetched.
        """
        self._name(
            [
                ledger.compact_path(self.state_dir, self.ledger, Period.MONTHLY, month, fmt=fmt)
                for month in months
                for fmt in Format
            ],
            months=months,
        )

    def name_years(self, years: Sequence[str]) -> None:
        """Name what the year step reads of these years: each one's month files and its own file.

        Each year's monthly folder, and its year file whichever format wrote it,
        are listed from the commit now: the year step chose them as it ran.
        """
        self._name(
            [
                path
                for year in years
                for path in (
                    self.monthly_year_folder(year),
                    *(
                        ledger.compact_path(
                            self.state_dir, self.ledger, Period.YEARLY, year, fmt=fmt
                        )
                        for fmt in Format
                    ),
                )
            ]
        )

    def name_months(self, months: Sequence[str]) -> None:
        """Name what a step reads of these months, and take in their raw days.

        Each month's daily folder, raw folder and month file, whichever format
        wrote it, are listed from the commit now: the step chose them as it
        ran.
        """
        self._name(
            [
                path
                for month in months
                for path in (
                    self.daily_month_folder(month),
                    *(
                        ledger.compact_path(
                            self.state_dir, self.ledger, Period.MONTHLY, month, fmt=fmt
                        )
                        for fmt in Format
                    ),
                )
            ],
            months=months,
        )

    def name_raw_months(self, months: Sequence[str]) -> None:
        """Name these months' raw folders alone, and take in their raw days.

        A day step with no mark looks back over them for its oldest raw day.
        """
        self._name([], months=months)

    def name_days(self, days: Sequence[str]) -> None:
        """Name what the day step reads of these days, and take in each that holds raw files.

        Each day's raw folder and its day file, whichever format wrote it, are
        listed from the commit now: the day step chose them as it ran.
        """
        self._name(
            [
                ledger.compact_path(self.state_dir, self.ledger, Period.DAILY, day, fmt=fmt)
                for day in days
                for fmt in Format
            ],
            days=days,
        )

    def _name(
        self, paths: Sequence[Path], *, months: Sequence[str] = (), days: Sequence[str] = ()
    ) -> None:
        """Name these paths and these raw folders in one listing call, and take in raw days.

        Only the raw days of a folder no step had named are taken in: a folder
        named before was read then, so a day a drop took from it earlier in this
        pass does not come back.
        """
        fresh_months = [
            month
            for month in months
            if not self.listing.answers_for(self.raw_month_folder(month))
        ]
        fresh_days = [day for day in days if not self.listing.answers_for(self.raw_day_folder(day))]
        self.listing = self.listing.name(
            [
                *(self.raw_month_folder(month) for month in months),
                *(self.raw_day_folder(day) for day in days),
                *paths,
            ]
        )
        found = {
            *named_trees.raw_days(self.listing, self.state_dir, self.ledger, months=fresh_months),
            *(day for day in fresh_days if self.listing.files_under(self.raw_day_folder(day))),
        }
        self.raw_days = sorted({*self.raw_days, *found})
        self.listed += len(found)

    def daily_month_folder(self, month: str) -> Path:
        """The folder a `YYYY-MM` month's daily compact files sit in."""
        first = ledger.compact_path(self.state_dir, self.ledger, Period.DAILY, f"{month}-01")
        return first.parent

    def monthly_year_folder(self, year: str) -> Path:
        """The folder a `YYYY` year's monthly compact files sit in."""
        first = ledger.compact_path(self.state_dir, self.ledger, Period.MONTHLY, f"{year}-01")
        return first.parent

    def load[C: Contract](self, path: Path, *, model: type[C]) -> list[StoredRow[C]]:
        """One ledger file's rows beside their identity, read as the pass decides."""
        self.looked.add(path)
        return ledger.load_stored([path], model=model)

    def read_raw_day[C: Contract](self, day: str, *, most: int, model: type[C]) -> RawDay[C]:
        """One day's raw files read for packing, oldest first; nothing about the day is decided.

        A file whose envelope or rows this build cannot read is named for the
        pass to move aside, and the rest of the day is read. A day holding more
        than `most` readable files gives the oldest `most`, the order settling
        relies on, and the rest wait in its folder: the next wake takes them as
        it takes a re-run. An entry of the folder that is not a file at all is
        refused with `ValueError`, because there is no file to move aside.
        """
        folder = ledger.read_day_folder(self.state_dir, self.ledger, day)
        for path, _why in folder.unreadable:
            if not path.is_file():
                raise ValueError(
                    f"{path.name} in the raw folder of {day} is not a file, so it cannot be "
                    "moved aside"
                )
        unreadable = list(folder.unreadable)
        taken: list[tuple[Path, list[StoredRow[C]]]] = []
        for held in folder.files[:most]:
            try:
                taken.append((held.path, self.load(held.path, model=model)))
            except ValueError as refusal:
                unreadable.append((held.path, str(refusal)))
        return RawDay(taken=taken, unreadable=unreadable, carried=len(folder.files[most:]))

    def set_aside(self, path: Path, covers: str, why: str) -> None:
        """Move one file the pass cannot read to the ledger's set-aside folder, and say why.

        The move is a write of its bytes at `ledger.set_aside_path` and a delete
        of its old path, which frees nothing, so the delete weighs 0 and
        `bytes_freed` stays what the deletes free. `covers` is the period whose
        packing set the file aside.
        """
        self.looked.add(path)
        self.write(ledger.set_aside_path(self.state_dir, self.ledger, path), path.read_bytes())
        self._drop(path, 0)
        logger.warning(
            "a file is moved aside unread ledger=%s period=%s path=%s/%s reason=%s",
            self.ledger.value,
            covers,
            ledger.STATE_DIRNAME,
            path.relative_to(self.state_dir).as_posix(),
            why,
        )

    def fit_to_budget(
        self, periods: Sequence[str], fetching: Callable[[str], PeriodFetch]
    ) -> tuple[list[str], Stop | None]:
        """The longest run of these periods, oldest first, whose fetch fits the budget left.

        Read off the listing's own sizes, so nothing is downloaded to decide, and
        a file two periods share counts once. The first period that does not
        fit ends the run, and the stop it makes comes back beside it
        (`stop_over_budget`). A listing with no budget fits every period.
        """
        room, budget = self.listing.room(), self.listing.budget
        if room is None or budget is None:
            return list(periods), None
        folders: list[Path] = []
        beside: list[Path] = []
        for position, covers in enumerate(periods):
            more = fetching(covers)
            needed = self.listing.cost([*folders, *more.folders], beside=[*beside, *more.beside])
            if needed and needed > room:
                alone = self.listing.cost(more.folders, beside=more.beside)
                return list(periods[:position]), self.stop_over_budget(
                    covers, needed=alone, budget=budget
                )
            folders.extend(more.folders)
            beside.extend(more.beside)
        return list(periods), None

    def fetch(self, fetches: Iterable[PeriodFetch]) -> None:
        """Fetch these periods in one download, inside what is left of the shard's budget.

        A run `fit_to_budget` gave always fits; anything else past the budget
        raises `OverBudgetError` before it downloads.
        """
        held = list(fetches)
        self.listing.fetch_within_budget(
            [folder for each in held for folder in each.folders],
            beside=[path for each in held for path in each.beside],
        )

    def stop_over_budget(self, covers: str, *, needed: int, budget: int) -> Stop:
        """Where a period of this ledger whose download does not fit stops its step."""
        return stop_over_budget(self.ledger, covers, needed=needed, budget=budget)

    def stop_spent(self, covers: str, spent: OverBudgetError) -> Stop:
        """Where a period stops when one of its own fetches found the budget spent."""
        return self.stop_over_budget(covers, needed=spent.needed, budget=spent.budget)

    def write(self, path: Path, data: bytes) -> None:
        """Decide to write one file whole."""
        if any(change.path == path and change.data is None for change in self.changes):
            raise ValueError(f"{path.name} was deleted earlier in this pass and may not be written")
        self.changes.append(Change(path=path, data=data, size=len(data)))

    def delete(self, path: Path) -> None:
        """Decide to delete one file, weighing it by the listing now."""
        self.looked.add(path)
        self._drop(path, self.listing.size_of(path))

    def _drop(self, path: Path, size: int) -> None:
        """Decide to delete one file that frees `size` bytes, unless this pass wrote it."""
        if any(change.path == path and change.data is not None for change in self.changes):
            raise ValueError(f"{path.name} was written earlier in this pass and may not be deleted")
        self.changes.append(Change(path=path, data=None, size=size))

    def spare(self, path: Path) -> None:
        """Keep one file a live monthly window would delete, and name it for the record."""
        self.looked.add(path)
        self.spares.append(path)

    def note_recovery(self, note: RecoveryNote, covers: str) -> None:
        """Say once what the pass recovered instead of stopping, and the period it is about."""
        logger.warning(
            "a period was recovered ledger=%s period=%s note=%s", self.ledger.value, covers, note
        )

    def entries(self, period: Period) -> dict[str, CompactEntry]:
        """One period's index as the pass holds it now, by what each entry covers."""
        match period:
            case Period.DAILY:
                return self.daily
            case Period.MONTHLY:
                return self.monthly
            case Period.YEARLY:
                return self.yearly
            case _:
                assert_never(period)

    def mark_index(self, period: Period) -> None:
        """Request one final index write after every stage has decided its entries.

        Each other period's index is written with it when the ledger has none yet
        so a ledger never holds one index
        without the others. A period with no index has no watermark either -
        `read_marks` refuses that pair - so what the pass holds for it is nothing,
        and the index says so.
        """
        self.pending_indexes.add(period)
        self.pending_indexes.update(set(Period) - self.indexed)

    def write_index(self, period: Period) -> None:
        """Serialize one final index after all stages have decided its entries."""
        held = self.entries(period)
        index = CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=self.ledger,
            period=period,
            entries=[held[covers] for covers in sorted(held)],
        )
        path = ledger.compact_index_path(self.state_dir, self.ledger, period)
        self.write(path, index.to_json().encode("ascii"))

    def write_watermark(
        self, period: Period, *, through: str, advanced_at: str, run_id: str
    ) -> None:
        """Keep the final watermark for one write after indexes and source deletions."""
        mark = Watermark(
            version=Watermark.schema_version(),
            ledger=self.ledger,
            period=period,
            through=through,
            advanced_at=advanced_at,
            run_id=run_id,
        )
        self.pending_watermarks[period] = mark

    def finish(self) -> None:
        """Plan data, final indexes, source deletions, then final watermarks, once per pass."""
        writes = [change for change in self.changes if change.data is not None]
        deletes = [change for change in self.changes if change.data is None]
        indexes_start = len(self.changes)
        for period in (Period.YEARLY, Period.MONTHLY, Period.DAILY):
            if period in self.pending_indexes:
                self.write_index(period)
        watermarks_start = len(self.changes)
        for period, mark in self.pending_watermarks.items():
            path = ledger.watermark_path(self.state_dir, self.ledger, period)
            self.write(path, mark.to_json().encode("ascii"))
        self.changes = [
            *writes,
            *self.changes[indexes_start:watermarks_start],
            *deletes,
            *self.changes[watermarks_start:],
        ]
        self.pending_indexes.clear()
        self.pending_watermarks.clear()

    def apply(self) -> None:
        """Carry out every change in the order it was decided. A dry run never calls this.

        A deleted file takes any date folder it leaves empty with it, so the next
        listing of the raw tree does not meet a day that holds nothing. A file
        deleted by its name alone - a month file or a raw file the drop steps
        take - may never have been downloaded, and its deletion lands from the
        name.
        """
        for change in self.changes:
            if change.data is None:
                change.path.unlink(missing_ok=True)
                day_partition.drop_empty_day_dirs(change.path)
            else:
                atomic_write.write_atomic_bytes(change.path, change.data)

    def _paths(self, *, deleted: bool, shown: Callable[[Path], str]) -> tuple[str, ...]:
        """The paths one side of the changes names, each once, in the order first decided."""
        seen: dict[str, None] = {}
        for change in self.changes:
            if (change.data is None) is deleted:
                seen.setdefault(shown(change.path), None)
        return tuple(seen)

    def written(self, shown: Callable[[Path], str]) -> tuple[str, ...]:
        return self._paths(deleted=False, shown=shown)

    def taken(self, shown: Callable[[Path], str]) -> tuple[str, ...]:
        return self._paths(deleted=True, shown=shown)

    def spared(self, shown: Callable[[Path], str]) -> tuple[str, ...]:
        """Every file the pass kept that a live monthly window would delete, each once.

        A file the pass deleted anyway is not one of them: a raw day past the
        window is packed like any other, and its raw files go once their rows are
        in its day file.
        """
        deleted = set(self.taken(shown))
        seen: dict[str, None] = {}
        for path in self.spares:
            named = shown(path)
            if named not in deleted:
                seen.setdefault(named, None)
        return tuple(seen)

    def freed(self) -> int:
        """Every byte the deletes free, never netted against what the pass writes.

        A file moved aside keeps its bytes in git, so it frees none.
        """
        return sum(change.size for change in self.changes if change.data is None)

    def seen(self) -> int:
        """Every raw day folder listed, and every file read or weighed."""
        return self.listed + len(self.looked)
