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
folders it opens before it opens one.

**No pass writes a path it deletes, or deletes a path it writes.** The shard
that lands the pass refuses a path on both lists, so one pass that did either
would stall every later wake. `write` and `delete` refuse it at the moment it
would happen, naming the path, and the pass then fails before anything lands.

A watermark or index this build cannot read stops the pass rather than being
read as absent: a compaction that guessed where it had got to would rewrite, or
delete, a period it had already finished. So does an index that is not there
while its period's watermark says the period was packed - the `index-missing`
fault - because a pass that read it as empty would write a list that forgets
every period packed before.

**A ledger's three indexes exist together.** Whatever writes one writes each of
the others the ledger has none of yet, and those are empty: a period with no
watermark was never packed, so an empty list is the truth about it. A reader
that finds `index/daily.json` can then tell a lost `index/monthly.json` or
`index/yearly.json` from a period never packed, and asks for no file that is not
there.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import assert_never

from idhazh import atomic_write, day_partition, ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import named_trees
from idhazh.gardener.file_listing import FileListing
from idhazh.ledger import StoredRow


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


def _read[M: Contract](model: type[M], path: Path, ledger_name: LedgerName, period: Period) -> M:
    """One small file of this ledger's, or a refusal naming it."""
    held = model.read(path)
    if (getattr(held, "ledger", None), getattr(held, "period", None)) != (ledger_name, period):
        raise ValueError(
            f"{path.name} does not describe the {ledger_name.value} {period.value} period"
        )
    return held


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
    months: frozenset[str] | None = None
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
    def read(
        cls,
        state_dir: Path,
        ledger_name: LedgerName,
        listing: FileListing,
        *,
        months: frozenset[str] | None = None,
    ) -> CompactTree:
        """The three watermarks, the three indexes and the raw day folder names, read once.

        The indexes' folder and each watermark's own folder are fetched first,
        and a watermark is fetched without the day, month or year folders beside it.
        """
        marks = {period: ledger.watermark_path(state_dir, ledger_name, period) for period in Period}
        indexes = {
            period: ledger.compact_index_path(state_dir, ledger_name, period) for period in Period
        }
        listing.fetch(
            {index.parent for index in indexes.values()},
            beside=[mark for mark in marks.values() if listing.holds(mark)],
        )
        through: dict[Period, str | None] = {}
        entries: dict[Period, dict[str, CompactEntry]] = {}
        indexed: set[Period] = set()
        for period in Period:
            mark = marks[period]
            through[period] = (
                _read(Watermark, mark, ledger_name, period).through if listing.holds(mark) else None
            )
            index = indexes[period]
            present = listing.holds(index)
            if not present and through[period] is not None:
                shown = f"{ledger.STATE_DIRNAME}/{index.relative_to(state_dir).as_posix()}"
                raise ValueError(
                    f"{ledger.LedgerFault.INDEX_MISSING}: {shown} is not there, and "
                    f"{mark.name} says the {period.value} period is packed through "
                    f"{through[period]}. Restore {index.name} from git history before the next "
                    "wake; an empty one would forget every period packed before"
                )
            if present:
                indexed.add(period)
            held = _read(CompactIndex, index, ledger_name, period) if present else None
            entries[period] = {entry.covers: entry for entry in held.entries} if held else {}
        raw_days = named_trees.raw_days(listing, state_dir, ledger_name)
        return cls(
            state_dir=state_dir,
            ledger=ledger_name,
            listing=listing,
            months=months,
            daily_through=through[Period.DAILY],
            monthly_through=through[Period.MONTHLY],
            yearly_through=through[Period.YEARLY],
            daily=entries[Period.DAILY],
            monthly=entries[Period.MONTHLY],
            yearly=entries[Period.YEARLY],
            raw_days=raw_days,
            listed=len(raw_days),
            indexed=frozenset(indexed),
        )

    def raw_day_folder(self, day: str) -> Path:
        """The raw folder one UTC day's writer files sit in."""
        return ledger.raw_root(self.state_dir, self.ledger).joinpath(day[:4], day[5:7], day[8:10])

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

    def write(self, path: Path, data: bytes) -> None:
        """Decide to write one file whole."""
        if any(change.path == path and change.data is None for change in self.changes):
            raise ValueError(f"{path.name} was deleted earlier in this pass and may not be written")
        self.changes.append(Change(path=path, data=data, size=len(data)))

    def delete(self, path: Path) -> None:
        """Decide to delete one file, weighing it by the listing now."""
        if any(change.path == path and change.data is not None for change in self.changes):
            raise ValueError(f"{path.name} was written earlier in this pass and may not be deleted")
        self.looked.add(path)
        self.changes.append(Change(path=path, data=None, size=self.listing.size_of(path)))

    def spare(self, path: Path) -> None:
        """Keep one file a live monthly window would delete, and name it for the record."""
        self.looked.add(path)
        self.spares.append(path)

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
        `read` refuses that pair - so what the pass holds for it is nothing, and
        the index says so.
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
        deleted by its name alone - a month file the monthly window drops - may never have
        been downloaded, and its deletion lands from the name.
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
        """Every byte the deletes free, never netted against what the pass writes."""
        return sum(change.size for change in self.changes if change.data is None)

    def seen(self) -> int:
        """Every raw day folder listed, and every file read or weighed."""
        return self.listed + len(self.looked)
