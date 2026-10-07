"""Which rows of a committed file repeat a key, and what dropping them costs.

A second attempt at one execution can land the same row twice, and the union
merge that stacks two pushes cannot tell that from two runs writing different
rows. This is the pass that settles it after the merge, which is the one moment
both sides have been in the same place.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import NamedTuple

from idhazh import day_partition
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.ledger import paths
from idhazh.ledger.csv_file import CsvContract, _read_rows
from idhazh.ledger.keys import (
    _PREFERENCES,
    FITTED_SIMILARITY_THRESHOLD_CARRIED,
    STORY_SIMILARITY_PAIR_CARRIED,
    STORY_SIMILARITY_PAIR_KEY,
    STORY_SIMILARITY_THRESHOLD_KEY,
)


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
    rows, because the post-merge settlement needs both: it drops a repeated key
    and it folds a file that came back from the merge carrying two headers, and
    the second of those is a job only the contract's own reader can do.

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

    `state/content-similarity-judge/fitted-thresholds/` is registered before
    anything writes it: the settlement runs over whatever it finds, a missing
    file settles to nothing, and registering the shape rather than its first
    writer is what stops two stale checkouts leaving one date fitted twice. Its
    sibling `scored-pairs/` joins on the same terms: `run_id` is in its key, so
    what settles there is a second attempt at one execution and never a second
    run of the day.

    """
    if date is not None:
        return [
            KeyedLedger(
                paths.path(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS, date),
                STORY_SIMILARITY_THRESHOLD_KEY,
                FittedSimilarityThreshold,
                FITTED_SIMILARITY_THRESHOLD_CARRIED,
            ),
            KeyedLedger(
                paths.path(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS, date),
                STORY_SIMILARITY_PAIR_KEY,
                StorySimilarityPair,
                STORY_SIMILARITY_PAIR_CARRIED,
            ),
        ]
    return [
        *(
            KeyedLedger(
                file,
                STORY_SIMILARITY_THRESHOLD_KEY,
                FittedSimilarityThreshold,
                FITTED_SIMILARITY_THRESHOLD_CARRIED,
            )
            for file in day_partition.day_files(
                paths.tree_root(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS)
            )
        ),
        *(
            KeyedLedger(
                file,
                STORY_SIMILARITY_PAIR_KEY,
                StorySimilarityPair,
                STORY_SIMILARITY_PAIR_CARRIED,
            )
            for file in day_partition.day_files(
                paths.tree_root(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS)
            )
        ),
    ]


def drop_repeated_rows(path: Path, key: tuple[str, ...]) -> int:
    """Rewrite the file without any row repeating a key an earlier row holds.

    This is the half of the guarantee `extend_ledger_file`'s filter cannot give. That filter
    reads the committed file the job checked out, and `actions/checkout` pins a
    job to the commit its run was triggered at - so a second execution of the
    same work cannot see rows the first one pushed after that commit. Its append
    lands them again. On a tree that still carries a union merge driver -
    `path_classes.UNION_SAFE` lists them -
    git then concatenates both sides line by line, which is the right answer for
    two runs writing different rows and exactly the wrong one for two attempts
    writing the same row.
    Everywhere else under `state/` that driver went on 2026-09-19 and the second
    push conflicts at the rebase instead. Measured on this
    repository 2026-08-31: run `2026-08-29-3` holds six counter rows for four
    shards and 44 repeated `(date, run_id, item_id)` item-health keys.

    So the file has to be settled once more after the merge, which is the only
    moment both sides have ever been in one place.

    Rows are matched and rewritten as whole lines rather than re-serialized, so
    a kept row is byte-identical to the row that was read and a pass that drops
    nothing leaves no diff. Reading by line is safe for the same reason the merge
    is: every free-text cell in these contracts is pinned to printable ASCII on
    one line, so no cell can carry a newline.

    The first row wins unless the key declares otherwise in `_PREFERENCES`. Only
    `FEED_HEALTH_KEY` does, because it is the only key here whose repeats can
    disagree: two attempts at one run really did read the address twice and may
    have got different answers. Everywhere else a repeat is one attempt written
    down twice, so the rows agree and picking between them would be theatre.
    The rule travels with the key rather than with the caller, so the workflow
    step, the CLI stage and a test harness that spells the key out all settle the
    same file the same way.

    Returns how many rows were dropped, so a caller can log the count.
    """
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        lines = handle.readlines()
    if not lines:
        return 0
    header = next(csv.reader(lines[:1]), [])
    if any(name not in header for name in key):
        # A shard written before the key existed cannot be checked against it,
        # and refusing would cost a run its whole commit over an old file.
        return 0
    prefer = _PREFERENCES.get(key)
    columns = [header.index(name) for name in key]
    seen: dict[tuple[str, ...], tuple[int, dict[str, str]]] = {}
    kept = [lines[0]]
    dropped = 0
    for line in lines[1:]:
        cells = next(csv.reader([line]), [])
        if len(cells) <= max(columns):
            kept.append(line)
            continue
        found = tuple(cells[index] for index in columns)
        held = seen.get(found)
        if held is not None:
            dropped += 1
            if prefer is not None:
                where, incumbent = held
                challenger = dict(zip(header, cells, strict=False))
                if prefer(challenger, incumbent):
                    kept[where] = line
                    seen[found] = (where, challenger)
            continue
        seen[found] = (len(kept), dict(zip(header, cells, strict=False)))
        kept.append(line)
    if dropped:
        path.write_text("".join(kept), encoding="utf-8", newline="")
    return dropped


def repeated_keys(path: Path, key: tuple[str, ...]) -> dict[tuple[str, ...], int]:
    """Every key the file holds more than one row for, and how many. Empty is clean."""
    counts: dict[tuple[str, ...], int] = {}
    for row in _read_rows(path):
        if any(name not in row for name in key):
            continue
        found = tuple(row[name] or "" for name in key)
        counts[found] = counts.get(found, 0) + 1
    return {found: count for found, count in counts.items() if count > 1}
