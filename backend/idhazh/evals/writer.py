"""How the eval ledger's measurements are filed, once each, and indexed.

Filed through the ledger door under `state/raw/scores/`, in the column order the
contract defines, and never recomputed at read time. Committing the scores rather
than deriving them is what makes a
claim about last quarter a lookup instead of a re-run against a model that has
since moved.

The ledger records measurements, not runs. A run that re-observes an item it
already measured - same address, same inputs, same words, same scorer - has
nothing new to say, so it writes nothing. That is the promise in
`docs/concepts/evaluation.md`, and it is what keeps a count over the ledger a
count of items rather than a count of times the pipeline looked at them.

`recorded_observations` reads the index described below and nothing else. Every
index day is kept, because every eval row is kept and nothing summarises a
month, so the dedupe read opens one more index day for every day recorded. That
read grows with what the ledger has piled up (Guardrail #12), and it is declared
in `docs/concepts/growing-reads.md`.

**The dedupe does not read the rows.** Answering "do we already hold this one?"
meant every run paid for every row it had ever written. Measured on this
repository on 2026-09-07: 7,636 rows over two shards, 6,111.8 KB, 819.6 bytes a
row, and about 173 MB once the ledger reaches steady state - a bill that rises
on a day nobody wrote any code, which is what Guardrail #12 refuses. The identity is
64 hex characters wide, so the ledger keeps a second record of exactly that:
`state/score-index/<YYYY>/<MM>/<DD>.csv`, 76 bytes an observation, beside the day
file it describes. Over the same 7,636 measurements that is 566.8 KB against
6,111.8 KB, so the read is 10.8 times smaller and 90.7 percent of it is gone.

**Both file by day, and they file by the same day.** A run writes one day, two
runs collide on a file only when they are the same day, and taking a day back is
one `rm` rather than an edit inside a shared shard - which an append-only ledger
cannot express. The index follows the ledger rather than keeping a grain of its
own, because an index row is the record of the row beside it and two grains in
one relationship is a mapping somebody has to maintain
(`docs/concepts/partitions.md`).

Nothing is forgotten and there is no clock. `OBSERVATION_KEY` carries no date on
purpose - re-measuring an article a year later is the same measurement - so a
window would be the wrong shape here as well as a cheaper one
(`idhazh.contracts.observation_index`).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, NamedTuple

from idhazh import day_shards, ledger
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.observation_index import ObservationIndexRow
from idhazh.ledger import read_header as _read_header
from idhazh.ledger import require_matching_header

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
    for row in ledger.load_ledger_rows(state_dir, LedgerName.SCORES, model=EvalRow):
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


def recorded_observations(state_dir: Path) -> set[str]:
    """Every measurement the ledger already holds, from every day the index has.

    Deliberately not scoped to the day being written. An observation is the
    same measurement whichever month it is re-taken in, and a dedupe that only
    looked at the current day would let a January row come back in February -
    which would turn a count over the ledger into a count of times the pipeline
    looked, and that is the one thing this ledger promises it is not.

    **It reads the index alone, and never a score row.** The index is a
    fixed-width digest record, so what this costs follows the measurements the
    ledger holds rather than the bytes it spent describing them - 76 bytes an
    observation against a measured 819.6. No index day is ever dropped, so the
    cover is every observation, with nothing forgotten
    (`docs/concepts/evaluation.md`).

    A missing directory is a ledger with no history, which is what a fresh
    clone has.
    """
    return indexed_observations(state_dir)


def index_days(state_dir: Path) -> list[Path]:
    """Every committed shard of the index, oldest day first.

    `day_shards.shard_files` decides what counts as a day. Unbounded because
    every caller here needs the whole index.
    """
    return list(
        day_shards.shard_files(
            ledger.tree_root(state_dir, LedgerName.SCORE_INDEX), days=UNBOUNDED_WINDOW
        )
    )


def index_columns() -> tuple[str, ...]:
    """One definition, so a writer and a reader cannot disagree about the shape."""
    return ObservationIndexRow.csv_columns()


def indexed_observations(state_dir: Path) -> set[str]:
    """The digests the index holds. A raw read of the cell, not a row build.

    **This opens one file a recorded day and it is declared rather than hidden**
    (Guardrail #12, `docs/concepts/growing-reads.md`). It was one file a month
    until 2026-09-13, when the grain change turned 2 opens into 23, and it gains
    about 365 a year. **Every index day is kept**, because every eval row is
    kept and nothing summarises a month, so the count of files grows with every
    recorded day.

    A cover was rejected rather than overlooked: a measurement re-taken outside
    a window would read as new, and a count over the ledger would become a count
    of times the pipeline looked. `recorded_observations` says why at length.

    The header is checked against the contract first, which is the same guard
    `append` puts on a day file and for the same reason: a file whose columns
    moved would otherwise be read one column under another column's name.
    """
    held: set[str] = set()
    for path in index_days(state_dir):
        held.update(_digests_of_index(path))
    return held


class IndexDrift(NamedTuple):
    """What one day's index and the rows beside it disagree about, both ways.

    `extra` is what the index holds that the rows cannot produce. `missing` is
    what the rows produce that the index does not hold. Two fields rather than
    one count, because a one-directional answer passes on an index that only
    ever grows - and an index that only grows is what a repeated dedupe over a
    re-scored item looks like.
    """

    extra: frozenset[str]
    missing: frozenset[str]


def rebuild_index(state_dir: Path, days: Iterable[str]) -> dict[str, IndexDrift]:
    """Add what each named day's rows produce and its index does not hold, and say what was wrong.

    The repair for an index that stopped describing the rows beside it - a write
    a crash cut short, or a day whose rows grew behind its back when a
    long-lived branch merged an older `main`. Nothing on the write path compares
    an index against its rows, because comparing means reading the rows and
    reading the rows is the bill the index exists to remove.

    **One add, never a rewrite.** The repair goes into the day directory as
    `repair-<YYYYMMDDTHHMMSSZ>.csv`, which is a name no run can take
    (`idhazh.path_classes.is_written_once`), so it collides with no writer's file and
    needs no merge. Rewriting a committed day would lose the race it is in:
    rebased onto a tip that appended, a commit that removed rows is a rebase git
    cannot apply, so the removal stops the push rather than landing half-done.

    **A digest the index holds that the rows cannot produce is reported and
    kept.** The index is a set of identities and a dedupe reads it as one, so an
    extra digest costs one measurement that is never re-taken - which is what
    the day's rows already say happened. Taking it out would mean a rewrite.

    Returns what each named day had wrong **before** the add, so a repair
    reports the drift rather than hiding it. Two empty sets for a day is an
    answer, not a no-op: it says that index was telling the truth.

    **An operator command, and no stage calls it.** It opens every row of every
    day it is given - the read the index exists to avoid - so the cover is the
    days the caller names and there is no default (Guardrail #12,
    `stages.rebuild_score_index.stage_rebuild_score_index`). A day with no committed rows is refused
    by name rather than skipped: a typo must not read as a clean pass over
    nothing.
    """
    live = _digests_by_day(state_dir, days)
    named = sorted({day[:10] for day in days})
    if not named:
        raise ValueError("rebuild_index was given no day, and a pass over none repairs none")
    absent = [date for date in named if date not in live]
    if absent:
        raise FileNotFoundError(f"the scores ledger holds no rows for {absent}")

    # One stamp for the whole pass, so every day this command repaired carries
    # the same name and an operator can see one repair rather than twenty.
    name = ledger.repair_name(datetime.now(UTC))
    found: dict[str, IndexDrift] = {}
    for date in named:
        produced = live[date]
        found[date] = _drift(_indexed_on(state_dir, date), produced)
        if found[date].missing:
            index = ledger.path(state_dir, LedgerName.SCORE_INDEX, date)
            _append_index(index / name, sorted(found[date].missing))
        after = _drift(_indexed_on(state_dir, date), produced)
        if after.missing:
            raise RuntimeError(
                f"{ledger.relpath(LedgerName.SCORE_INDEX, date)} still does not hold "
                f"{len(after.missing)} digests the rows beside it produce, after a repair "
                "that was meant to add them"
            )
    return found


def _indexed_on(state_dir: Path, date: str) -> frozenset[str]:
    """Every digest one day's index holds, across every file in that day.

    A day is a directory of writer-owned files, so the answer is the union of
    them - and a caller that read whichever file the walk named last would call
    a measurement new because another writer's file already held it.
    """
    held: set[str] = set()
    for path in day_shards.one_day(ledger.tree_root(state_dir, LedgerName.SCORE_INDEX), date):
        held.update(_digests_of_index(path))
    return frozenset(held)


def _drift(held: frozenset[str], produced: frozenset[str]) -> IndexDrift:
    """Both directions at once, so no call site can ask for only one."""
    return IndexDrift(extra=held - produced, missing=produced - held)


def _digests_by_day(state_dir: Path, days: Iterable[str]) -> dict[str, frozenset[str]]:
    """The distinct observations each named day's rows produce, read from the rows.

    The one read here that opens a score row on purpose, which is why only
    `rebuild_index` calls it and why that is a command a person types. A day
    with no row is absent from the answer rather than empty.
    """
    by_day: dict[str, set[str]] = {}
    named = {day[:10] for day in days}
    for row in ledger.load_days(state_dir, LedgerName.SCORES, named, model=EvalRow):
        by_day.setdefault(row.date, set()).add(observation_digest(row.model_dump(mode="json")))
    return {day: frozenset(held) for day, held in by_day.items()}


def _digests_of_index(path: Path) -> frozenset[str]:
    """The digests one index file holds. An absent file holds none.

    The header is checked against the contract first, which is the same guard
    `append` puts on a day file and for the same reason: a file whose columns moved
    would otherwise be read one column under another column's name.
    """
    if not path.exists():
        return frozenset()
    require_matching_header(path, index_columns())
    with path.open("r", encoding="utf-8", newline="") as handle:
        return frozenset(record["observation_digest"] for record in csv.DictReader(handle))


def _append_index(path: Path, digests: Iterable[str]) -> int:
    """Append digests to one day's index, writing the header once."""
    pending = list(digests)
    if not pending:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    if exists:
        require_matching_header(path, index_columns())
    stamp = ObservationIndexRow.schema_version()
    with path.open("a", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=index_columns(), lineterminator="\n")
        if not exists:
            out.writeheader()
        for digest in pending:
            row = ObservationIndexRow.model_validate(
                {"version": stamp, "observation_digest": digest}
            )
            out.writerow(row.csv_row())
    return len(pending)


def _unrecorded(rows: Sequence[EvalRow], already: set[str]) -> list[tuple[EvalRow, str]]:
    """The measurements the ledger does not already hold, each with its digest.

    `already` is added to as it goes, because a run can hand the same
    measurement in twice and the second one is not new either.
    """
    fresh: list[tuple[EvalRow, str]] = []
    for row in rows:
        digest = observation_digest(row.model_dump(mode="json"))
        if digest in already:
            continue
        already.add(digest)
        fresh.append((row, digest))
    return fresh


def file_measurements(
    state_dir: Path,
    rows: Iterable[EvalRow],
    *,
    identity: WriterIdentity,
) -> int:
    """File this writer's new measurements through the ledger door, and index them.

    Two jobs of one run measure items - a work shard as each item settles, and
    assemble over the whole day afterwards - and each files its own raw file
    under `state/raw/scores/`, named for the writer by the door. Two writers
    never share a path, so a lost push race costs a merge rather than the rows,
    and a re-run's second attempt replaces its first try instead of colliding
    with it.

    **The dedupe reads the committed index, and what it cannot see is settled
    later.** A measurement already recorded is skipped here. A measurement this
    run's other writer filed minutes ago is invisible - the dedupe reads the
    index and this run's index files are not in it yet - so both writers file
    it, and the settlement keeps one row per `OBSERVATION_KEY`. That is the same
    answer by a later route, which is what makes it safe to run a second time.

    Returns how many measurements were filed, so a caller can log the count.
    """
    pending = list(rows)
    if not pending:
        return 0
    fresh = _unrecorded(pending, recorded_observations(state_dir))
    if not fresh:
        return 0
    stamp = ObservationIndexRow.schema_version()
    if not ledger.persist(
        state_dir,
        [row for row, _ in fresh],
        ledger=LedgerName.SCORES,
        covers=identity.run_id[:10],
        identity=identity,
    ):
        return 0
    # The rows first, then the index, and the order is the whole argument. A
    # crash between the two leaves a measurement recorded and not indexed, which
    # the next run files again and the settlement keeps once. The other order
    # leaves a digest whose row was never written - a measurement nothing will
    # ever take again, and nothing on disk that says it is missing.
    #
    # `date=` because an index row is a stamp and a digest and carries no date
    # cell to be filed by. The day is the run's own, which is the day the eval
    # rows beside it carry.
    ledger.write_segment(
        state_dir,
        LedgerName.SCORE_INDEX,
        [
            ObservationIndexRow.model_validate({"version": stamp, "observation_digest": digest})
            for _, digest in fresh
        ],
        run_id=identity.run_id,
        attempt=identity.attempt,
        job=identity.job,
        shard=identity.shard,
        date=identity.run_id[:10],
    )
    return len(fresh)
