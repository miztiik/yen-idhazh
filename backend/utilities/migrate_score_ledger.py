"""Rewrite `state/scores.csv` so `source_word_count` means the whole article.

Until 2026-08-27 that column was documented as "The full article" and held
`metrics.word_count(article.text)` - a regex count of the **truncated** text.
The column beside it, `source_seen_word_count`, held `len(article.text.split())`
of the same string. Two counters over one string do not make a before-and-after
pair, and on 610 of 2,346 committed rows the seen count came out larger than the
full count, which is impossible if one is a cut of the other.

What this rewrite can and cannot recover:

- An article that was never truncated **is** the text the model saw, so its full
  length equals the recorded seen length exactly. `truncate_to_tokens` returns
  the body unchanged in that case, and `Article.word_count` is
  `len(text.split())` either way. Those rows get a real count, not a guess.
- An article that was truncated was cut to `SEEN_WORD_CAP` words and the pre-cap
  body was discarded at extract. Its true length exists nowhere. Those rows get
  an empty cell. Zero would be a measurement; empty is the fact.

One-shot, and committed rather than run by hand, so a fork or a stale branch can
reproduce the exact rewrite this repository ran (CLAUDE.md Rule #5). It is safe
to leave here after it has run: rows are selected by their own `version` stamp,
so a row written by the fixed pipeline is never touched, and a file with no
eligible row is refused rather than rewritten a second time.

Usage: `python backend/utilities/migrate_score_ledger.py [--state state]`,
from the root of a checkout.
"""

from __future__ import annotations

import argparse
import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.assemble import write_atomic
from idhazh.contracts.eval_row import EvalRow

#: Rows stamped before this were written by the code that conflated the two
#: counters. The stamp travels on the row, which is why a migrated row keeps the
#: one it was written with - it is the only marker of which rows predate a
#: change (`docs/architecture/contracts/schemas.md`).
FIXED_FROM: Final = "2026-08-27"

#: The post-cap word ceiling every eligible row was written under:
#: `int(extract.truncation_cap_tokens / extract.TOKENS_PER_WORD)` at a cap of
#: 2500 tokens, which is what every eligible row ran at. The cap became 5000 on
#: 2026-08-29 and this number did not follow it: it is history rather than a
#: knob, so it is spelled here and not read from `config/` - moving the cap
#: tomorrow must not change what yesterday's rows meant. The committed ledger
#: agrees: no eligible row exceeds it and 142 sit exactly on it.
SEEN_WORD_CAP: Final = 1923

#: The one cell this rewrite is allowed to move. Every other cell, on every row,
#: must come out byte-identical.
MIGRATED_COLUMN: Final = "source_word_count"


@dataclass(frozen=True, slots=True)
class Migration:
    """The rewritten file and the numbers a reviewer will ask for."""

    text: str
    rows_in: int
    rows_recovered: int
    rows_emptied: int

    @property
    def rows_untouched(self) -> int:
        return self.rows_in - self.rows_recovered - self.rows_emptied


def _rows(text: str) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    return tuple(reader.fieldnames or ()), list(reader)


def _elsewhere(rows: list[dict[str, str]], columns: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Every cell except the one being migrated, in order. The oracle reads this."""
    others = tuple(name for name in columns if name != MIGRATED_COLUMN)
    return [tuple(row[name] for name in others) for row in rows]


def honest(text: str) -> Migration:
    """The rewritten ledger, or a `ValueError` naming what stopped the rewrite."""
    columns = EvalRow.csv_columns()
    header, rows = _rows(text)
    if header != columns:
        raise ValueError(
            f"expected the header {','.join(columns)} and found {','.join(header)}"
        )
    for number, row in enumerate(rows, start=2):
        if None in row or any(row.get(name) is None for name in columns):
            raise ValueError(f"line {number} does not carry {len(columns)} cells")

    eligible = [row for row in rows if row["version"] < FIXED_FROM]
    if not eligible:
        raise ValueError(
            f"no row predates {FIXED_FROM}, so every count is already the whole article"
        )

    recovered = emptied = 0
    for row in eligible:
        seen = int(row["source_seen_word_count"])
        if seen < SEEN_WORD_CAP:
            row[MIGRATED_COLUMN] = str(seen)
            recovered += 1
        else:
            row[MIGRATED_COLUMN] = ""
            emptied += 1

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row[name] for name in columns})
    rewritten = out.getvalue()

    # The Oracle, in three parts. Same rows in the same order; every cell this
    # rewrite is not allowed to touch still holding its own bytes; and no row
    # left claiming the model read more words than the article holds - which is
    # the impossible direction this whole migration exists to remove.
    before_header, before_rows = _rows(text)
    after_header, after_rows = _rows(rewritten)
    if after_header != before_header or len(after_rows) != len(before_rows):
        raise ValueError("the rewrite changed the shape of the file, so nothing was written")
    if _elsewhere(after_rows, columns) != _elsewhere(before_rows, columns):
        raise ValueError("the rewrite moved a cell it does not own, so nothing was written")
    for number, row in enumerate(after_rows, start=2):
        full = row[MIGRATED_COLUMN]
        if full and int(row["source_seen_word_count"]) > int(full):
            raise ValueError(f"line {number} still reads more seen words than the article holds")

    return Migration(
        text=rewritten,
        rows_in=len(rows),
        rows_recovered=recovered,
        rows_emptied=emptied,
    )


def _relpath(path: Path) -> str:
    """POSIX and relative, because this string leaves the process (CLAUDE.md section 2)."""
    try:
        return path.resolve().relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="state", help="the state directory to migrate")
    args = parser.parse_args()

    path = Path(args.state) / "scores.csv"
    relpath = _relpath(path)
    if not path.is_file():
        raise SystemExit(f"{relpath} does not exist")

    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    try:
        report = honest(text)
    except ValueError as error:
        raise SystemExit(f"{relpath}: {error}") from error

    write_atomic(path, report.text)
    print(
        f"{relpath}: {report.rows_in} rows, {report.rows_recovered} given the article's own "
        f"length, {report.rows_emptied} emptied because the article was truncated and the "
        f"body is gone, {report.rows_untouched} already honest"
    )


if __name__ == "__main__":
    main()
