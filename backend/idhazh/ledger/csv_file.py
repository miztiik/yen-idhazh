"""How one ledger's rows are read out of a CSV file and written back into it.

A row is rendered in exactly one place, so a row an append adds and a file the
compaction rewrites whole are the same bytes. Written two ways, a file one pass
touched would read as changed line by line the next time anything diffed it.

Nothing here knows which ledger it is reading. The file is handed in, so this
module can be driven by a caller that names a ledger nobody declared here.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Protocol


class CsvRecord(Protocol):
    """A contract that knows how to write itself as one row of a `state/` file.

    Every ledger here takes one of these rather than a `dict[str, str]`. A dict
    is not a contract - anything can build one and nothing validates it - so a
    caller assembling cells by hand could reach a committed file without a model
    having seen them. Declared as a protocol rather than as a base class because
    these contracts share a shape, not an ancestor: `Contract` is the base for
    every persisted document, and most of those are JSON and have no row.
    """

    def csv_row(self) -> dict[str, str]:
        """Every cell a string, keyed by column name."""
        ...


class CsvContract(Protocol):
    """The class side of `CsvRecord`: the columns, and the reader for an old row."""

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The row's columns, in the row's own order."""
        ...

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> CsvRecord:
        """One row read back, under any heading this ledger has ever carried."""
        ...


def read_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(next(csv.reader(handle), []))


def require_matching_header(path: Path, columns: tuple[str, ...]) -> None:
    header = read_header(path)
    if header and header != columns:
        raise ValueError(
            f"{path.name} has {len(header)} columns and the contract has "
            f"{len(columns)}. Migrate the ledger before appending to it."
        )


def _csv_line(columns: tuple[str, ...], payload: dict[str, str]) -> str:
    """One row, written the way `extend_ledger_file` writes one.

    A re-filed row and an appended row have to be the same bytes, or the file a
    migration leaves behind is a file the next append disagrees with.
    """
    buffer = io.StringIO()
    csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n").writerow(
        {name: payload[name] for name in columns}
    )
    return buffer.getvalue()


def render_file(columns: tuple[str, ...], rows: Iterable[Mapping[str, str]]) -> str:
    """A whole ledger file as one document: the header, then every row.

    Beside `_csv_line` because a file the compaction rewrites whole and a row an
    append adds have to be the same bytes. Written two ways, a file the
    compaction touched would read as changed line by line the next time anything
    diffed it.

    Returned rather than written, so the caller owns the temp-file-plus-rename
    and this module keeps its rule that a row is rendered in exactly one place.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for payload in rows:
        writer.writerow({name: payload[name] for name in columns})
    return buffer.getvalue()


def extend_ledger_file(path: Path, columns: tuple[str, ...], rows: Sequence[CsvRecord]) -> int:
    """Write every row it is handed. This path does not deduplicate, on purpose.

    **Public because a caller outside this module now writes a file this module
    does not name.** The council ships a tenant's rows to a ledger the tenant
    names, so there is no `<ledger>_relpath` helper here to hang an `append_*`
    writer off - and rewriting the append beside that caller would give one
    ledger two shapes.

    The eval ledger does, on read, one row per `OBSERVATION_KEY` a day, and the
    reason the two differ is what a row means. There a row is a measurement, so
    re-measuring an item nothing changed about has nothing new to say. Here a row
    is a fact about a run - this feed answered at this hour, this item finished -
    and a run that runs twice did happen twice. Collapsing those would turn a
    count of runs into a count of days.

    So each caller owns its own repeats, and each one is named here because the
    guarantee does not live in this file:

    - **feed-health** - one row per feed per run. A repeat needs a run to be run
      twice under one `run_id`. Two runs cannot compute one any more - a run id
      now carries the identity of the execution that made it (`stages.plan.stage_plan`)
      - but a second attempt at the same execution still can, and this is the
      one caller whose two rows can disagree: the first attempt may have failed
      where the second succeeded. `day_shards.settled_rows` settles the day
      against `FEED_HEALTH_KEY` at read time, so the winner is picked by the rule
      in `contracts.feed_health.supersedes` rather than by which line landed
      first.

    **It takes contracts and renders them here.** A `dict[str, str]` is not a
    contract: anything can build one, nothing validates it, and a caller that
    assembled the cells by hand would reach a committed file without a model ever
    having seen them. Taking the row itself puts every `state/` file behind its
    own contract, and the rendering happens once, in this function, rather than
    at each of the nine call sites.
    """
    if not rows:
        return 0
    payloads = [row.csv_row() for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    if exists:
        require_matching_header(path, columns)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        if not exists:
            writer.writeheader()
        for payload in payloads:
            writer.writerow({name: payload[name] for name in columns})
    return len(payloads)


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
