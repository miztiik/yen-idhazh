"""What one ledger's compact periods hold as a compaction pass finds them, and what it changes.

A pass reads the three watermarks, the three period indexes and the names of the
raw day folders once, then decides period by period what to write and what to
delete. Each decision is a `Change`, kept here in the order it must happen -
data first, index next, watermark last - and nothing touches the disk until
`apply`, which a dry run never calls. So a dry run and a live run make the same
decisions from the same reads, and the list a dry run reports is the list a
live run carries out, file for file.

**No pass writes a path it deletes, or deletes a path it writes.** The shard
that lands the pass refuses a path on both lists, so one pass that did either
would stall every later wake. `write` and `delete` refuse it at the moment it
would happen, naming the path, and the pass then fails before anything lands.

A watermark or index this build cannot read stops the pass rather than being
read as absent: a compaction that guessed where it had got to would rewrite, or
delete, a period it had already finished.
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
    changes: list[Change] = field(default_factory=list)
    #: Every file the pass read or weighed.
    looked: set[Path] = field(default_factory=set)

    @classmethod
    def read(cls, state_dir: Path, ledger_name: LedgerName) -> CompactTree:
        """The three watermarks, the three indexes and the raw day folder names, read once."""
        marks: dict[Period, str | None] = {}
        entries: dict[Period, dict[str, CompactEntry]] = {}
        for period in Period:
            mark = ledger.watermark_path(state_dir, ledger_name, period)
            marks[period] = (
                _read(Watermark, mark, ledger_name, period).through if mark.is_file() else None
            )
            index = ledger.compact_index_path(state_dir, ledger_name, period)
            listed = _read(CompactIndex, index, ledger_name, period) if index.is_file() else None
            entries[period] = {entry.covers: entry for entry in listed.entries} if listed else {}
        raw_days = ledger.raw_days(state_dir, ledger_name)
        return cls(
            state_dir=state_dir,
            ledger=ledger_name,
            daily_through=marks[Period.DAILY],
            monthly_through=marks[Period.MONTHLY],
            yearly_through=marks[Period.YEARLY],
            daily=entries[Period.DAILY],
            monthly=entries[Period.MONTHLY],
            yearly=entries[Period.YEARLY],
            raw_days=raw_days,
            listed=len(raw_days),
        )

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
        """Decide to delete one file, weighing it now."""
        if any(change.path == path and change.data is not None for change in self.changes):
            raise ValueError(f"{path.name} was written earlier in this pass and may not be deleted")
        self.looked.add(path)
        self.changes.append(Change(path=path, data=None, size=path.stat().st_size))

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

    def write_index(self, period: Period) -> None:
        """Decide to rewrite one period's index from what the pass holds now."""
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
        """Decide to move one period's watermark. Called after that period's data, never before."""
        mark = Watermark(
            version=Watermark.schema_version(),
            ledger=self.ledger,
            period=period,
            through=through,
            advanced_at=advanced_at,
            run_id=run_id,
        )
        path = ledger.watermark_path(self.state_dir, self.ledger, period)
        self.write(path, mark.to_json().encode("ascii"))

    def apply(self) -> None:
        """Carry out every change in the order it was decided. A dry run never calls this.

        A deleted file takes any date folder it leaves empty with it, so the next
        listing of the raw tree does not meet a day that holds nothing.
        """
        for change in self.changes:
            if change.data is None:
                change.path.unlink()
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

    def freed(self) -> int:
        """Every byte the deletes free, never netted against what the pass writes."""
        return sum(change.size for change in self.changes if change.data is None)

    def seen(self) -> int:
        """Every raw day folder listed, and every file read or weighed."""
        return self.listed + len(self.looked)
