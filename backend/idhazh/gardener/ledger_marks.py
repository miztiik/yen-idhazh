"""What a ledger's marks say: which packed files exist and how far each step has packed.

A ledger's marks are six small files under `state/compact/<ledger>/`. The three
indexes, `index/daily.json`, `index/monthly.json` and `index/yearly.json`, list
every packed day, month and year file. The three watermarks,
`<period>/watermark.json`, each name the newest day, month or year its step has
packed. `name_marks` says where the six sit. Code that builds a pass's listing
path by path names the marks through it, so the pass never asks for a mark its
listing left out. `read_marks` reads them.

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

**A packed file no entry names is adopted, never recorded lost.** An index
restored from an older commit can lose an entry while the period's own file is
still at its named path. Before a pass records a period `empty` or `lost`, it
asks `adopt` for that path: a file there becomes the period's `packed` entry,
its bytes from the listing and its rows and envelope from its footer. A file
whose envelope names another ledger, period or day is refused by name and
never adopted, because adopting it would put another period's rows under this
one.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.file_envelope import Period, Tier
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import named_trees
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


@dataclass(frozen=True, slots=True)
class Adopted:
    """A period's own packed file that no index entry named, and the entry it earns."""

    path: Path
    entry: CompactEntry


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


def adopt(
    listing: FileListing, state_dir: Path, ledger_name: LedgerName, period: Period, covers: str
) -> Adopted | None:
    """A period's own file, when no entry names it, and the `packed` entry it earns; else None.

    The file is fetched with the files beside it, then read from its footer
    alone. A file whose envelope names another ledger, period or day is refused
    by name.
    """
    found = named_trees.compact_file(listing, state_dir, ledger_name, period, covers)
    if found is None:
        return None
    listing.fetch(beside=[found])
    footer = ledger.read_footer(found)
    said = footer.envelope
    if (said.tier, said.ledger, said.period, said.covers) != (
        Tier.COMPACT,
        ledger_name,
        period,
        covers,
    ):
        raise ValueError(
            f"{found.name} sits where the {ledger_name.value} {period.value} file for {covers} "
            f"goes, and its envelope says {said.tier.value} {said.ledger.value} "
            f"{said.period.value if said.period else 'raw'} {said.covers}, so it is not adopted"
        )
    return Adopted(
        path=found,
        entry=CompactEntry(covers=covers, rows=footer.rows, bytes=listing.size_of(found)),
    )
