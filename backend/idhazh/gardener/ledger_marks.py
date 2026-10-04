"""What a ledger's marks say: which packed files exist and how far each step has packed.

A ledger's marks are six small files under `state/compact/<ledger>/`. The three
indexes, `index/daily.json`, `index/monthly.json` and `index/yearly.json`, list
every packed day, month and year file. The three watermarks,
`<period>/watermark.json`, each name the newest day, month or year its step has
packed. `name_marks` says where the six sit, so the listing a task is given
names the same files a compaction pass then reads with `read_marks`.

**A mark is fetched once, before it is read.** The index folder is fetched
whole, and each watermark by itself, without the day, month or year folders
beside it.

**A mark this build cannot trust stops the pass rather than being read as
absent.** A compaction that guessed where it had got to would rewrite, or
delete, a period it had already finished. So a mark that cannot be read, or
that describes another ledger or period, is refused by name. So is an index
that is not there while its period's watermark says the period was packed -
the `index-missing` fault - because a pass that read it as empty would write a
list that forgets every period packed before.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.file_listing import FileListing


@dataclass(frozen=True, slots=True)
class MarkPaths:
    """Where one ledger's three indexes and three watermarks sit, by period."""

    indexes: Mapping[Period, Path]
    watermarks: Mapping[Period, Path]

    def __iter__(self) -> Iterator[Path]:
        """All six paths: each index, then each watermark, in period order."""
        yield from self.indexes.values()
        yield from self.watermarks.values()


@dataclass(frozen=True, slots=True)
class LedgerMarks:
    """What one ledger's marks said when a pass read them."""

    #: The newest day, month and year packed, or None when that period never has been.
    through: Mapping[Period, str | None]
    #: Each period's index, by what each entry covers. Empty when there is no index.
    entries: Mapping[Period, Mapping[str, CompactEntry]]
    #: The periods whose index the listing holds.
    indexed: frozenset[Period]


def name_marks(state_dir: Path, ledger_name: LedgerName) -> MarkPaths:
    """Where one ledger's three indexes and three watermarks sit."""
    return MarkPaths(
        indexes={
            period: ledger.compact_index_path(state_dir, ledger_name, period) for period in Period
        },
        watermarks={
            period: ledger.watermark_path(state_dir, ledger_name, period) for period in Period
        },
    )


def _read_one[M: Contract](
    model: type[M], path: Path, ledger_name: LedgerName, period: Period
) -> M:
    """One of this ledger's marks, or a refusal naming it."""
    held = model.read(path)
    if (getattr(held, "ledger", None), getattr(held, "period", None)) != (ledger_name, period):
        raise ValueError(
            f"{path.name} does not describe the {ledger_name.value} {period.value} period"
        )
    return held


def read_marks(state_dir: Path, ledger_name: LedgerName, listing: FileListing) -> LedgerMarks:
    """The three watermarks and the three indexes, fetched and read once.

    A watermark whose index the listing does not hold is refused as `index-missing`.
    """
    named = name_marks(state_dir, ledger_name)
    listing.fetch(
        {index.parent for index in named.indexes.values()},
        beside=[mark for mark in named.watermarks.values() if listing.holds(mark)],
    )
    through: dict[Period, str | None] = {}
    entries: dict[Period, dict[str, CompactEntry]] = {}
    indexed: set[Period] = set()
    for period in Period:
        mark = named.watermarks[period]
        through[period] = (
            _read_one(Watermark, mark, ledger_name, period).through
            if listing.holds(mark)
            else None
        )
        index = named.indexes[period]
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
        held = _read_one(CompactIndex, index, ledger_name, period) if present else None
        entries[period] = {entry.covers: entry for entry in held.entries} if held else {}
    return LedgerMarks(through=through, entries=entries, indexed=frozenset(indexed))
