"""How evaluation measurements are filed, and what makes two rows one measurement.

Each job files the rows it holds as one raw file per UTC day through the ledger
door, as item health is filed, and reads nothing first. A work shard and the
assemble job may file one measurement for the same day; a read of named days
keeps one row per `OBSERVATION_KEY` each day, and a whole-ledger read keeps one
across every day. `records` is that whole-ledger read, for operator passes.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import read_header as _read_header

#: What makes two rows the same measurement. `idhazh.ledger.OBSERVATION_KEY` is
#: the definition and this is the name this module has always called it; the
#: compaction settles a day's segments on the same tuple.
OBSERVATION_KEY: Final = ledger.OBSERVATION_KEY


def records(state_dir: Path) -> Iterator[dict[str, str]]:
    """Every row the eval ledger holds now, oldest day first, as a CSV line spells it.

    The whole ledger, read through the door and settled once
    (`ledger.load_ledger_rows`). Unbounded on purpose and declared: every caller
    is an operator's pass that has to see every measurement
    (`docs/concepts/growing-reads.md`).
    """
    for row in ledger.load_ledger_rows(state_dir, LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow):
        yield row.csv_row()


def columns() -> tuple[str, ...]:
    """One definition, so a writer and a reader cannot disagree about the shape."""
    return EvalRow.csv_columns()


def read_header(path: Path) -> tuple[str, ...]:
    return _read_header(path)


def observation(payload: Mapping[str, object]) -> tuple[str, ...]:
    """The identity of one measurement, read from a row or from a CSV record."""
    return tuple(str(payload[name]) for name in OBSERVATION_KEY)


def file_measurements(
    state_dir: Path,
    rows: Iterable[EvalRow],
    *,
    identity: WriterIdentity,
) -> int:
    """File this job's rows as one raw file per UTC day and return how many it filed.

    Each row is filed under the day its own `date` names. A write into a paused
    family files nothing and returns 0.
    """
    filed = list(rows)
    written = ledger.persist(
        state_dir,
        filed,
        ledger=LedgerName.SUMMARY_QUALITY_EVALS,
        covers=identity.run_id[:10],
        identity=identity,
    )
    return len(filed) if written else 0
