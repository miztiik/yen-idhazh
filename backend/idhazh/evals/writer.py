"""Append to the committed eval ledger, one file a month.

Append-only, in the column order the contract defines, and never recomputed at
read time. Committing the scores rather than deriving them is what makes a
claim about last quarter a lookup instead of a re-run against a model that has
since moved.

The ledger records measurements, not runs. A run that re-observes an item it
already measured - same address, same inputs, same words, same scorer - has
nothing new to say, so it writes nothing. That is the promise in
`docs/concepts/evaluation.md`, and it is what keeps a count over the ledger a
count of items rather than a count of times the pipeline looked at them.

A month past `observability.scores_full_grain_months` stops being rows and
becomes `state/score-archive/<YYYY-MM>.json` (`idhazh.evals.archive`). That is
why `recorded_observations` reads two places: the promise above has to hold for
a month whose rows are gone, and the archive's sorted digest index is the only
thing that can still answer it.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Final

from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.validation_row import ValidationRow
from idhazh.evals import archive
from idhazh.ledger import STATE_DIRNAME, require_matching_header
from idhazh.ledger import read_header as _read_header

LEDGER_DIRNAME: Final = "scores"
LEDGER_RELDIR: Final = f"{STATE_DIRNAME}/{LEDGER_DIRNAME}"

#: What makes two rows the same measurement. The address says which article, the
#: fingerprint says which inputs produced it, the digest says which words came
#: out, and the scorer version says which instrument read them. Change any one
#: and the row is a new measurement worth keeping. `item_id` is deliberately
#: absent: it is a slot on a page, not an identity.
OBSERVATION_KEY: Final = ("url_key", "pipeline_fingerprint", "output_digest", "scorer_version")


def ledger_relpath(date: str) -> str:
    """`state/scores/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return f"{LEDGER_RELDIR}/{date[:7]}.csv"


def ledger_path(state_dir: Path, date: str) -> Path:
    """The shard one date's rows belong in, the way `ledger.py` locates its own files.

    A caller passes the directory and the date and never the file name, so a
    second writer - the canary fixture builder is one - cannot spell the layout
    differently from the pipeline and have both be right.
    """
    return state_dir / LEDGER_DIRNAME / f"{date[:7]}.csv"


def ledger_shards(state_dir: Path) -> list[Path]:
    """Every committed month of the ledger, oldest first.

    Anything that is not a `<YYYY-MM>.csv` is left alone: `retention.prune_scores`
    archives and then deletes out of this directory, so it names what it
    recognises rather than acting on what it does not.
    """
    directory = state_dir / LEDGER_DIRNAME
    if not directory.is_dir():
        return []
    found = [
        path
        for path in directory.glob("*.csv")
        if len(path.stem) == 7 and path.stem[4] == "-" and path.stem.replace("-", "").isdigit()
    ]
    return sorted(found, key=lambda path: path.stem)


def records(state_dir: Path) -> Iterator[dict[str, str]]:
    """Every committed row, oldest shard first, as the CSV spells it.

    One sequence over many files, so a reader that wants the whole ledger reads
    it the way it always did and a reader that wants a window can skip whole
    shards instead.
    """
    for shard in ledger_shards(state_dir):
        with shard.open("r", encoding="utf-8", newline="") as handle:
            yield from csv.DictReader(handle)


def columns() -> tuple[str, ...]:
    """One definition, so a writer and a reader cannot disagree about the shape."""
    return EvalRow.csv_columns()


def read_header(path: Path) -> tuple[str, ...]:
    return _read_header(path)


def observation(payload: Mapping[str, object]) -> tuple[str, ...]:
    """The identity of one measurement, read from a row or from a CSV record."""
    return tuple(str(payload[name]) for name in OBSERVATION_KEY)


def observation_digest(payload: Mapping[str, object]) -> str:
    """The same identity as one hash, which is the form that survives a deletion.

    A month past `observability.scores_full_grain_months` is summarised and its
    shard is unlinked, and the summary keeps this digest rather than the four
    values it came from - `state/score-archive/` is a fixed-width index instead
    of a second copy of the addresses.
    """
    return archive.digest_of(observation(payload))


def recorded_observations(state_dir: Path) -> set[str]:
    """Every measurement the ledger already holds, live rows and archived months alike.

    Deliberately not scoped to the shard being written. An observation is the
    same measurement whichever month it is re-taken in, and a dedupe that only
    looked at the current month would let a January row come back in February -
    which would turn a count over the ledger into a count of times the pipeline
    looked, and that is the one thing this ledger promises it is not.

    **The archived half is what makes deleting a shard safe.** A month older
    than the full-grain window has no rows left to read, so a dedupe over the
    rows alone would call every measurement in it new the day it was deleted.
    `state/score-archive/<YYYY-MM>.json` carries those digests for exactly this
    union, and it is why the archive stores them sorted (`docs/concepts/
    evaluation.md`).

    A missing directory on either side is a ledger with no history, which is
    what a fresh clone has.
    """
    return {observation_digest(record) for record in records(state_dir)} | (
        archive.archived_observations(state_dir)
    )


def append(state_dir: Path, rows: Iterable[EvalRow]) -> int:
    """Append the measurements this run made, writing each shard's header once.

    Returns how many landed, so a caller can log the count rather than re-read
    the files to find out. A row the ledger already holds is not one of them.

    Rows are filed by their own `date`, so a run that publishes either side of
    midnight writes two shards and neither is wrong. Within one call the header
    check and the write happen per shard.

    A header that no longer matches the contract stops the run. A shard is
    append-only and its header is written once, so a new column would otherwise
    put more cells on a row than the header names, and every reader that maps by
    position would silently read one column under another column's name. Failing
    here is what makes adding a column a migration instead of a corruption.
    """
    pending = list(rows)
    if not pending:
        return 0

    # Before the dedupe, not after it. A shard whose header no longer matches the
    # contract is corrupt whatever this call had to say, and the dedupe would
    # otherwise return 0 and never reach the check - which is how a stale header
    # survives a run that appeared to do nothing wrong.
    for shard in ledger_shards(state_dir):
        require_matching_header(shard, columns())

    already = recorded_observations(state_dir)
    fresh: dict[str, list[dict[str, object]]] = {}
    for row in pending:
        payload = row.model_dump(mode="json")
        key = observation_digest(payload)
        if key in already:
            continue
        already.add(key)
        fresh.setdefault(str(payload["date"])[:7], []).append(payload)
    if not fresh:
        return 0

    landed = 0
    for month, payloads in sorted(fresh.items()):
        path = ledger_path(state_dir, month)
        path.parent.mkdir(parents=True, exist_ok=True)
        exists = path.exists()
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns(), lineterminator="\n")
            if not exists:
                writer.writeheader()
            for payload in payloads:
                writer.writerow({name: payload[name] for name in columns()})
        landed += len(payloads)
    return landed


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
