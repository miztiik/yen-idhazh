"""Append to the committed eval ledger.

Append-only, in the column order the contract defines, and never recomputed at
read time. Committing the scores rather than deriving them is what makes a
claim about last quarter a lookup instead of a re-run against a model that has
since moved.

The ledger records measurements, not runs. A run that re-observes an item it
already measured - same address, same inputs, same words, same scorer - has
nothing new to say, so it writes nothing. That is the promise in
`docs/concepts/evaluation.md`, and it is what keeps a count over the ledger a
count of items rather than a count of times the pipeline looked at them.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final

from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.validation_row import ValidationRow
from idhazh.ledger import STATE_DIRNAME, require_matching_header
from idhazh.ledger import read_header as _read_header

LEDGER_FILENAME: Final = "scores.csv"
LEDGER_RELPATH: Final = f"{STATE_DIRNAME}/{LEDGER_FILENAME}"

#: What makes two rows the same measurement. The address says which article, the
#: fingerprint says which inputs produced it, the digest says which words came
#: out, and the scorer version says which instrument read them. Change any one
#: and the row is a new measurement worth keeping. `item_id` is deliberately
#: absent: it is a slot on a page, not an identity.
OBSERVATION_KEY: Final = ("url_key", "pipeline_fingerprint", "output_digest", "scorer_version")


def ledger_path(state_dir: Path) -> Path:
    """The ledger inside a state directory, the way `ledger.py` locates its own files.

    A caller passes the directory and never the file name, so a second writer -
    the canary fixture builder is one - cannot spell the layout differently from
    the pipeline and have both be right.
    """
    return state_dir / LEDGER_FILENAME


def columns() -> tuple[str, ...]:
    """One definition, so a writer and a reader cannot disagree about the shape."""
    return EvalRow.csv_columns()


def read_header(path: Path) -> tuple[str, ...]:
    return _read_header(path)


def observation(payload: Mapping[str, object]) -> tuple[str, ...]:
    """The identity of one measurement, read from a row or from a CSV record."""
    return tuple(str(payload[name]) for name in OBSERVATION_KEY)


def recorded_observations(path: Path) -> set[tuple[str, ...]]:
    """Every measurement the committed ledger already holds.

    A missing file is a ledger with no history, which is what a fresh clone has.
    """
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {observation(record) for record in csv.DictReader(handle)}


def append(path: Path, rows: Iterable[EvalRow]) -> int:
    """Append the measurements this run made, writing the header only when new.

    Returns how many landed, so a caller can log the count rather than re-read
    the file to find out. A row the ledger already holds is not one of them.

    A header that no longer matches the contract stops the run. The file is
    append-only and its header is written once, so a new column would otherwise
    put more cells on a row than the header names, and every reader that maps by
    position would silently read one column under another column's name. Failing
    here is what makes adding a column a migration instead of a corruption.
    """
    pending = list(rows)
    if not pending:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    if exists:
        require_matching_header(path, columns())

    already = recorded_observations(path)
    fresh: list[dict[str, object]] = []
    for row in pending:
        payload = row.model_dump(mode="json")
        key = observation(payload)
        if key in already:
            continue
        already.add(key)
        fresh.append(payload)
    if not fresh:
        return 0

    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns(), lineterminator="\n")
        if not exists:
            writer.writeheader()
        for payload in fresh:
            writer.writerow({name: payload[name] for name in columns()})
    return len(fresh)


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
