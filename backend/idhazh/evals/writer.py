"""Append to the committed eval ledger.

Append-only, in the column order the contract defines, and never recomputed at
read time. Committing the scores rather than deriving them is what makes a
claim about last quarter a lookup instead of a re-run against a model that has
since moved.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.validation_row import ValidationRow

LEDGER_RELPATH: Final = "state/scores.csv"


def columns() -> tuple[str, ...]:
    """One definition, so a writer and a reader cannot disagree about the shape."""
    return EvalRow.csv_columns()


def read_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(next(csv.reader(handle), []))


def append(path: Path, rows: Iterable[EvalRow]) -> int:
    """Append rows, writing the header only when the file is new.

    Returns how many landed, so a caller can log the count rather than re-read
    the file to find out.
    """
    pending = list(rows)
    if not pending:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns(), lineterminator="\n")
        if not exists:
            writer.writeheader()
        for row in pending:
            payload = row.model_dump(mode="json")
            writer.writerow({name: payload[name] for name in columns()})
    return len(pending)


def append_validation(path: Path, rows: Iterable[ValidationRow]) -> int:
    """The model-validation ledger, one file per validation date.

    Dated rather than appended to one file: a validation is a whole comparison,
    not an item, and mixing two of them in one table makes the denominator a
    question.
    """
    pending = list(rows)
    if not pending:
        return 0
    names = ValidationRow.csv_columns()
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        if not exists:
            writer.writeheader()
        for row in pending:
            payload = row.model_dump(mode="json")
            writer.writerow({name: payload[name] for name in names})
    return len(pending)
