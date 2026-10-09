"""Which ledgers a CSV settlement covers, and which rows of a committed file repeat a key.

A second attempt at one execution could land the same row twice, and the union
merge that stacked two pushes could not tell that from two runs writing
different rows. Every ledger that was settled here has moved under `state/raw/`,
where each write is a file of its own, so the registry below names none and
nothing rewrites a file after a merge any more.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from idhazh.ledger.csv_file import CsvContract, _read_rows


class KeyedLedger(NamedTuple):
    """One committed file, what makes two of its rows the same record, and the
    contract that can read a row of it.

    The three travel together because the settlement needs all three and looking
    any of them up a second time is how the file list and the reader list drift
    apart. `carried` names the headings this contract's reader still places after
    the column they belong to was retired; only one shape here has ever retired
    one, and the rest declare nothing.
    """

    path: Path
    key: tuple[str, ...]
    model: type[CsvContract]
    carried: frozenset[str] = frozenset()


def keyed_paths(state_dir: Path, *, date: str | None) -> list[KeyedLedger]:
    """Every ledger here that says what makes two of its rows the same record.

    Each one arrives with its key AND with the contract that can read one of its
    rows, because the post-merge settlement needed both: it dropped a repeated
    key and it folded a file that came back from the merge carrying two headers,
    and the second of those is a job only the contract's own reader can do.

    `date` says which files. A run appends only to the shard its own date routes
    to, so a repeat the union merge left behind can only be in a file that run
    wrote - and every dated ledger here contributes one file whatever the archive
    holds. `date=None` is the operator's full pass and names every file; it is
    the only cover that costs more every day, and Guardrail #12 is why a person
    has to ask for it by name.

    Nothing here is a clock. An older day is skipped because this run did not
    write it, not because it is old, so the bound does not weaken as a run gets
    slower or crosses midnight.

    `state/feed-health/`, `state/item-health/`, `state/host-fingerprint/`,
    and `state/counterfactual-scores/` were all here until
    2026-09-22 and none of them is now. Each became a day directory where every
    writer holds its own file, so a merge has nothing to stack: two files that
    no one else can write do not need a settlement to tell them apart, and the
    repeat this pass existed to drop is a repeat those trees can no longer make.
    What settles two rows of a day tree at read time is
    `day_shards.settled_rows`, which is where it always decided - this pass only
    ever rewrote the file.

    The feed retirements and the visual cleanup record left for the same reason
    when they moved under `state/raw/`, and item-health, host-fingerprint, the
    counterfactual scores and feed health have moved there since: every writer
    holds its own file there too, and their readers keep one row per key as they
    read
    (`ledger/raw_files.py`).

    **No ledger is left here.** The judge's scored pairs left when they moved
    under `state/raw/`, and its fitted line, the last, followed them for the
    reason the trees above did. The answer is empty whatever `state_dir` and
    `date` name.
    """
    return []


def repeated_keys(path: Path, key: tuple[str, ...]) -> dict[tuple[str, ...], int]:
    """Every key the file holds more than one row for, and how many. Empty is clean."""
    counts: dict[tuple[str, ...], int] = {}
    for row in _read_rows(path):
        if any(name not in row for name in key):
            continue
        found = tuple(row[name] or "" for name in key)
        counts[found] = counts.get(found, 0) + 1
    return {found: count for found, count in counts.items() if count > 1}
