"""How evaluation measurements are filed once and looked up by candidate identity.

`records` is an explicit whole-ledger read for operator passes. Filing and
duplicate checks read only the lookup entries for the supplied identities.
Measurements do not expire: `OBSERVATION_KEY` excludes the day and run.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.evals import observation_batches
from idhazh.evals.observation_lookup import ObservationLookup
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


def observation_digest(payload: Mapping[str, object]) -> str:
    """The same identity as one hash, which is the form the index keeps.

    A fixed-width record instead of a second copy of the addresses. Digested
    through the project's own canonical serialization rather than joined with a
    separator, so no value can contain the thing that separates two values -
    `scorer_version` carries semicolons, slashes and an at-sign, and a join is
    one grammar change away from two different keys digesting the same.
    """
    return derive_text_digest(canonical_json(list(observation(payload))))


def recorded_observations(state_dir: Path, candidates: Iterable[str]) -> set[str]:
    """The supplied observation digests already recorded, without reading eval rows.

    A missing lookup is an error. Existing history requires an explicit migration.
    """
    with ObservationLookup(observation_batches.lookup_root(state_dir)) as lookup:
        return lookup.recorded(candidates)


def file_measurements(
    state_dir: Path,
    rows: Iterable[EvalRow],
    *,
    identity: WriterIdentity,
) -> int:
    """File new measurements from an immutable batch and return the accepted count."""
    from idhazh.config import load_observation_lookup

    return observation_batches.file_batch(state_dir, rows, identity, load_observation_lookup())
