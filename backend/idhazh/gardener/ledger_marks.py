"""What a ledger's marks say: which packed files exist and how far each step has packed.

A ledger's marks are its three indexes under `state/compact/<ledger>/index/`:
`daily.json`, `monthly.json` and `yearly.json` list every day, month and year a
compaction has packed or looked at, an `empty` or a `lost` one included.
`name_marks` says where the three sit. Code that builds a pass's listing path
by path names the marks through it, so the pass never asks for a mark its
listing left out. `read_marks` reads them.

**How far each period is packed is worked out from the indexes, in one place**
(`work_out_marks`). The yearly mark is the newest year the yearly index names.
The monthly mark is the newer of the newest month the monthly index names and
the December of the yearly mark. The daily mark is the newer of the newest day
the daily index names and the last day of the monthly mark. Every period a
step has looked at leaves an entry, so the indexes say how far each step got,
and there is no second record of it to disagree with them.

**The marks are fetched once, before they are read.** The index folder is
fetched whole, inside what is left of the shard's download budget: marks that
do not fit raise `OverBudgetError`, and the pass takes nothing until a later
wake.

**A mark this build cannot trust stops the pass rather than being read as
absent.** A compaction that guessed where it had got to would rewrite, or
delete, a period it had already finished. So an index that cannot be read, or
that describes another ledger or period, is refused by name. An index that is
not there names nothing; the pass rebuilds it from the files at its named
paths before any step runs (`tasks/_absent_indexes.py`).

**A packed file no entry names is adopted, never recorded lost.** An index
restored from an older commit can lose an entry while the period's own file is
still at its named path. Before a pass records a period `empty` or `lost`, it
asks `adopt` for that path: a file there becomes the period's `packed` entry,
its bytes from the listing and its rows and envelope from its footer. A file
whose envelope names another ledger, period or day is refused by name and
never adopted, because adopting it would put another period's rows under this
one. Reading the footer downloads the files beside it, and that counts against
the shard's download budget as a step's own periods do: past it, `adopt`
raises `OverBudgetError` and the step stops at the period for a later wake.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from idhazh import ledger, month_partition
from idhazh.contracts.file_envelope import Period, Tier
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import named_trees
from idhazh.gardener.file_listing import FileListing


@dataclass(frozen=True, slots=True)
class MarkPaths:
    """Where one ledger's three indexes sit, by period."""

    indexes: Mapping[Period, Path]

    def __iter__(self) -> Iterator[Path]:
        """The three paths, in period order."""
        yield from self.indexes.values()


@dataclass(frozen=True, slots=True)
class LedgerMarks:
    """What one ledger's marks said when a pass read them.

    How far each period is packed is not stored here: `work_out_marks` works it
    out from the entries, so there is one formula and one record.
    """

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
    """Where one ledger's three indexes sit."""
    return MarkPaths(
        indexes={
            period: ledger.compact_index_path(state_dir, ledger_name, period) for period in Period
        },
    )


def work_out_marks(covers: Mapping[Period, Collection[str]]) -> dict[Period, str | None]:
    """How far each period is packed, from what each index names: the newest day, month and year.

    The yearly mark is the newest year named; the monthly mark the newer of the
    newest month named and the December of the yearly mark; the daily mark the
    newer of the newest day named and the last day of the monthly mark. None
    where nothing of that period, or a coarser one, is named.
    """
    yearly = max(covers[Period.YEARLY], default=None)
    monthly = max(
        [*covers[Period.MONTHLY], *([] if yearly is None else [f"{yearly}-12"])], default=None
    )
    daily = max(
        [
            *covers[Period.DAILY],
            *([] if monthly is None else [month_partition.day_bounds(monthly, monthly)[1]]),
        ],
        default=None,
    )
    return {Period.DAILY: daily, Period.MONTHLY: monthly, Period.YEARLY: yearly}


def _read_index(path: Path, ledger_name: LedgerName, period: Period) -> CompactIndex:
    """One of this ledger's indexes, or a refusal naming it."""
    held = CompactIndex.read(path)
    if (held.ledger, held.period) != (ledger_name, period):
        raise ValueError(
            f"{path.name} does not describe the {ledger_name.value} {period.value} period"
        )
    return held


def read_marks(state_dir: Path, ledger_name: LedgerName, listing: FileListing) -> LedgerMarks:
    """The three indexes, fetched and read once.

    An index the listing does not hold names nothing. Marks that do not fit what
    is left of the shard's download budget raise `OverBudgetError` before
    anything is downloaded.
    """
    named = name_marks(state_dir, ledger_name)
    listing.fetch_within_budget({index.parent for index in named.indexes.values()})
    entries: dict[Period, dict[str, CompactEntry]] = {}
    indexed: set[Period] = set()
    for period in Period:
        index = named.indexes[period]
        held = _read_index(index, ledger_name, period) if listing.holds(index) else None
        if held is not None:
            indexed.add(period)
        entries[period] = {entry.covers: entry for entry in held.entries} if held else {}
    return LedgerMarks(entries=entries, indexed=frozenset(indexed))


def adopt(
    listing: FileListing, state_dir: Path, ledger_name: LedgerName, period: Period, covers: str
) -> Adopted | None:
    """A period's own file, when no entry names it, and the `packed` entry it earns; else None.

    The file is fetched with the files beside it, inside what is left of the
    shard's download budget, then read from its footer alone. A fetch past the
    budget raises `OverBudgetError`. A file whose envelope names another
    ledger, period or day is refused by name.
    """
    found = named_trees.compact_file(listing, state_dir, ledger_name, period, covers)
    if found is None:
        return None
    listing.fetch_within_budget(beside=[found])
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
