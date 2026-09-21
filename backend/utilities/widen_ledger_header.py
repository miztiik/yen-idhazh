"""Re-file every committed day of one store under the column list its contract holds now.

`ledger.require_matching_header` compares the committed header to the contract's
columns and raises rather than append, so a column added to a row shape leaves
its store unappendable until the files on disk carry the new header. The next run
to append then loses its whole commit step and every ledger staged beside it. The
contract change and this pass are therefore one commit
(`docs/architecture/contracts/schemas.md`).

**Nothing in the repository could do this from a command line before.**
`ledger.migrate_header` is the engine and it is only ever reached from the
compaction verb, which folds a segment into a head and has no store argument.
This is the operator's door onto it.

The store is named from the prune verb's own word list, so one set of words means
one set of stores wherever an operator types one - and that list is taken whole,
including the two words the prune verb refuses by name. Those two are refused
there because a store that forgets cannot be the guard it exists to be, and
re-filing a header forgets nothing. The contract that reads a row comes off
`ledger.keyed_paths`, the registry that already pairs a committed file with its
reader. Neither list is restated here, so neither can drift from this one. A word
outside the vocabulary and a store no reader is registered for are two different
refusals, and each says which it is.

**The dry run is the default, as it is for the prune verb.** Writing takes a word
nobody types by accident. Both modes migrate a copy in a temporary directory and
compare the bytes, so the report a dry run prints is the report a live run
prints, file for file - one measurement rather than two arithmetics that agree
until they do not.

**Run it twice and the second pass writes nothing.** `migrate_header` reads line
one, sees the contract's own header and returns without opening the rest of the
file, so a file already wide is byte-identical afterwards and is reported
unchanged.

What this checks and what it leaves to the engine: it checks that the row count
did not move, because that is the one failure the engine cannot see from inside a
single file. Everything else is already the engine's - `migrate_header` refuses a
heading this build cannot place, keeps a row no reader could place and raises,
and re-files through the contract's own reader rather than cell by cell.

    python backend/utilities/widen_ledger_header.py --target story-similarity-scored-pairs
    python backend/utilities/widen_ledger_header.py --target <store> --no-dry-run

Exit code 1 when a file could not be re-filed, so a shell can gate on it.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from idhazh import config, ledger
from idhazh.ledger import CsvContract
from idhazh.telemetry import prune

DEFAULT_STATE_DIR: Final = config.REPO_ROOT / ledger.STATE_DIRNAME

#: Which stores this can re-file, as a path under `state/`. The prune verb's
#: whole word list, INCLUDING the two words it refuses by name: `published` and
#: `seen` are refused there because a store that forgets cannot be the guard it
#: exists to be, and re-filing a header forgets nothing. One vocabulary, two
#: commands, and each one says its own no.
STORES: Final[Mapping[str, str]] = MappingProxyType(
    dict(sorted({**prune.TARGETS, **{name: name for name in prune.REFUSED}}.items()))
)


@dataclass(frozen=True, slots=True)
class Refiled:
    """One day file: where it is, how wide it was, how wide it is now, and what moved.

    `path` is the POSIX form relative to the state directory (CLAUDE.md section
    2), which is the minimal reconstructable form once `--target` has named the
    store. It is the same string on both sides of `dry_run` - named before
    anything is written, so the list a dry run prints is the list a live run
    rewrites.
    """

    path: str
    columns_before: int
    columns_after: int
    rows: int
    moved: int
    changed: bool


def _data_rows(text: str, first_column: str) -> int:
    """How many rows the file holds, header blocks and blank lines excluded.

    A union merge can stack a second header into a file, which is why a header
    line is recognised by its opening cell rather than by its position. Every
    contract here opens on `version`, whose values are date stamps and never the
    word, so the test cannot mistake a row for a heading.
    """
    sentinel = first_column + ","
    return sum(
        1 for line in text.splitlines()[1:] if line.strip() and not line.startswith(sentinel)
    )


def _refile(path: Path, model: type[CsvContract], *, root: Path) -> tuple[bytes, Refiled]:
    """The file as this contract would write it, and what that moved.

    Always done on a copy. A dry run wants the answer without the write, and a
    live run wants the answer it is about to commit to - taking both off one pass
    is what stops the printed report and the written file being two claims.
    """
    columns = model.csv_columns()
    before = path.read_bytes()
    with tempfile.TemporaryDirectory() as scratch:
        spool = Path(scratch) / path.name
        spool.write_bytes(before)
        moved = ledger.migrate_header(spool, columns, ledger.refiler(model))
        after = spool.read_bytes()

    was = ledger.read_header(path)
    before_text = before.decode("utf-8")
    after_text = after.decode("utf-8")
    rows = _data_rows(before_text, was[0] if was else columns[0])
    if rows != _data_rows(after_text, columns[0]):
        raise ValueError(
            f"{path.name} holds {rows} rows and re-filing it produced "
            f"{_data_rows(after_text, columns[0])}. A widening adds cells and never rows."
        )
    return after, Refiled(
        path=path.relative_to(root).as_posix(),
        columns_before=len(was),
        columns_after=len(columns),
        rows=rows,
        moved=moved,
        changed=after != before,
    )


def _reader_for(root: Path, state_dir: Path) -> type[CsvContract]:
    """The contract that reads one row of this store.

    Taken from `ledger.keyed_paths`, which is where a committed file is already
    paired with the contract that can read it - so the pairing is never written
    down a second time here. A store whose files that registry names no reader
    for is refused with the reason rather than skipped: an operator who typed it
    is holding a real question, and "nothing happened" is not the answer to it.
    """
    for entry in ledger.keyed_paths(state_dir, date=None):
        if root == entry.path.parent or root in entry.path.parents:
            return entry.model
    raise ValueError(
        f"{root.name} holds files that `ledger.keyed_paths` names no reader for, so "
        "nothing here knows which contract writes its header. Register the shape "
        "there, or re-file the store from the code that owns it."
    )


def widen(
    target: str, *, state_dir: Path = DEFAULT_STATE_DIR, write: bool = False
) -> list[Refiled]:
    """Every day file of one store, oldest first, and what re-filing each one moved.

    A store with no file yet reports nothing and raises nothing. There is no
    header on disk to disagree with the contract, so there is nothing to re-file
    - and every store in the vocabulary is named before its first writer lands.
    """
    if target not in STORES:
        raise ValueError(
            f"this re-files a store, and {target!r} is not the name of one. A path is "
            f"never a name here. It knows {', '.join(STORES)}"
        )
    root = state_dir / STORES[target]
    paths = sorted(root.rglob("*.csv"))
    if not paths:
        return []
    model = _reader_for(root, state_dir)
    report: list[Refiled] = []
    for path in paths:
        refiled, entry = _refile(path, model, root=state_dir)
        if entry.changed and write:
            spool = path.with_suffix(".csv.tmp")
            spool.write_bytes(refiled)
            spool.replace(path)
        report.append(entry)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        metavar="STORE",
        help="Which store to re-file. One of " + ", ".join(STORES) + ".",
    )
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    args = parser.parse_args(argv)

    try:
        report = widen(args.target, state_dir=args.state_dir, write=not args.dry_run)
    except ValueError as refusal:
        print(f"refused: {refusal}")
        return 1

    moved = [entry for entry in report if entry.changed]
    for entry in moved:
        print(
            f"  {entry.path}: {entry.rows} rows, "
            f"{entry.columns_before} -> {entry.columns_after} columns, "
            f"{entry.moved} re-filed"
        )
    verb = "would rewrite" if args.dry_run else "rewrote"
    print(f"{args.target}: {verb} {len(moved)} of {len(report)} day files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
