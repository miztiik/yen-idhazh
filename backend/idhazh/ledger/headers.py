"""How a file written under an older header is read, and re-filed under this one.

A schema change ships a read-side migration, so a file an earlier run wrote stays
readable. It does not stay appendable: the header on disk no longer names the
columns the writer holds, and the next append would raise and lose the whole
commit step. This is the half of a widening a header check cannot give.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Collection
from pathlib import Path

from idhazh.ledger.csv_file import CsvContract, _csv_line, read_header


def refiler(model: type[CsvContract]) -> Callable[[dict[str, str]], dict[str, str]]:
    """The contract's own reader, as a row-to-row migration.

    `from_csv_row` reads a row under any heading its ledger has ever carried and
    `csv_row` writes it under the heading it carries now, so the map between the
    two lives once, in the contract, rather than in whatever is re-filing the
    file this time.
    """

    def read(raw: dict[str, str]) -> dict[str, str]:
        return model.from_csv_row(raw).csv_row()

    return read


def _headings(lines: list[str], first_column: str) -> set[str]:
    """Every column name the file names anywhere, header blocks included.

    A file that two appends were stacked into carries two header lines, and the
    second one is the only place the other side's column names appear. Reading
    line 1 alone would therefore miss exactly the generation this is asked about.
    """
    sentinel = first_column + ","
    names = set(next(csv.reader(lines[:1]), []))
    for line in lines[1:]:
        if line.startswith(sentinel):
            names.update(next(csv.reader([line]), []))
    return names


def _unplaceable(
    lines: list[str], columns: tuple[str, ...], carried: Collection[str]
) -> list[str]:
    """The headings in this file the current contract cannot read a cell into.

    This is the direction test, and it is put as a question about cells rather
    than about dates: re-filing under `columns` writes the columns the contract
    names and drops everything else, so a heading that is neither a current
    column nor one the reader carries forward names a cell that would be lost.

    The harm it stops is a scheduled run on a checkout that predates a widening.
    That run holds the narrower column list, so re-filing a wide file under it
    would throw away every column the widening added - exit 0, no diagnostic, and
    the cells simply gone.
    """
    return sorted(_headings(lines, columns[0]) - set(columns) - set(carried))


def _refile(
    lines: list[str],
    columns: tuple[str, ...],
    read: Callable[[dict[str, str]], dict[str, str]],
) -> tuple[list[str], int, list[str]]:
    """Every line under one header: the lines to write, how many moved, and a
    complaint for each line no reader could place.

    A line already under the right header and at the right width is kept as the
    bytes that were read and never parsed, so a pass with nothing to do returns
    the list it was handed and its caller writes nothing. Not parsing it is the
    point as well as the saving: this repairs a shape, and asking whether every
    committed cell still parses would be a scan of the archive wearing a repair's
    clothes. A line that has to move and cannot be read is kept too, and named in
    the complaints - dropping it would lose a fact to fix a shape.
    """
    sentinel = columns[0] + ","
    kept = [",".join(columns) + "\n"]
    block = tuple(next(csv.reader(lines[:1]), []))
    moved = 0
    refused: list[str] = []
    for number, line in enumerate(lines[1:], start=2):
        if line.startswith(sentinel):
            block = tuple(next(csv.reader([line]), []))
            continue
        if not line.strip():
            continue
        cells = next(csv.reader([line]), [])
        if block == columns and len(cells) == len(columns):
            kept.append(line if line.endswith("\n") else line + "\n")
            continue
        try:
            kept.append(_csv_line(columns, read(dict(zip(block, cells, strict=False)))))
        except (KeyError, ValueError) as exc:
            refused.append(f"line {number} has {len(cells)} cells and cannot be read: {exc}")
            kept.append(line if line.endswith("\n") else line + "\n")
            continue
        moved += 1
    return kept, moved, refused


def migrate_header(
    path: Path,
    columns: tuple[str, ...],
    read: Callable[[dict[str, str]], dict[str, str]],
    *,
    carried: Collection[str] = (),
) -> int:
    """Re-file every row of `path` under `columns`, and say how many rows moved.

    **It reads line 1 and stops there when the header is already the
    contract's**, whatever the file's size. That is the ordinary case on every
    append, and it is complete rather than optimistic: a CSV append writes rows into
    a file that exists and a header only into one that does not, so an append
    cannot put a second header in a file. A union merge resolve could, and every
    day file under `state/` carried that driver until 2026-09-19; the files it
    already made are committed, and the migration to day directories carried
    their bytes over as they stood.

    This is the half of a widening `require_matching_header` cannot give. A
    schema change ships a read-side migration, so a file an earlier run wrote
    stays readable; it does not stay appendable, because the header on disk no
    longer names the columns the writer holds. The next run to append would raise
    and lose the whole commit step, every ledger staged beside this one included.

    **It widens, and it refuses to narrow.** `carried` names the headings the
    contract's reader still places - the retired ones - and a file naming
    anything outside that and `columns` is left byte-identical while the call
    raises. That case is a scheduled run on a checkout older than the file: it
    holds the narrower column list, and re-filing under it would drop every cell
    the widening added, with exit 0 and nothing printed. A refusal costs that run
    its commit step, which is the cheaper of the two and the one a person sees.

    `read` is the contract's own reader, which `refiler` builds. `from_csv_row`
    knows every heading the file has ever carried and `csv_row` writes the one it
    carries now, so the map between the two is never written down a second time.

    **What this does not cover.** A rename of the FIRST column, because that name
    is how a header line is told from a row - every contract here opens on
    `version`, whose values are date stamps and never the word.

    Rewriting the file made the next union merge repeat rows rather than
    headers, and a repeated row was a question the post-merge settlement
    answered, first row winning. Trading a shape nothing settles for a shape
    something does was the whole of what this bought. No tree under `state/`
    keeps a union driver now, so neither shape can arrive by a merge.
    """
    if not path.exists():
        return 0
    header = read_header(path)
    if not header or header == columns:
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        lines = handle.readlines()
    unplaceable = _unplaceable(lines, columns, carried)
    if unplaceable:
        raise ValueError(
            f"{path.name} carries {len(unplaceable)} heading(s) this build cannot place "
            f"({', '.join(unplaceable[:5])}), so re-filing it would drop those cells. "
            "The file is newer than this checkout; run the step again on a build that "
            "names them."
        )
    kept, moved, refused = _refile(lines, columns, read)
    if refused:
        raise ValueError(f"{path.name} holds a row no reader could place: {refused[0]}")
    if kept != lines:
        path.write_text("".join(kept), encoding="utf-8", newline="")
    return moved
