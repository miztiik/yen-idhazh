"""Append to the committed eval ledger, one file a day.

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
cannot express. The index follows the ledger rather than keeping a grain of its own,
because `refresh_index` fills a partition with no index from the rows beside it
and two grains in one relationship is a mapping somebody has to maintain
(`docs/concepts/partitions.md`).

Nothing is forgotten and there is no clock. `OBSERVATION_KEY` carries no date on
purpose - re-measuring an article a year later is the same measurement - so a
window would be the wrong shape here as well as a cheaper one
(`idhazh.contracts.observation_index`).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Final, NamedTuple

from idhazh import day_partition, day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.observation_index import ObservationIndexRow
from idhazh.evals import archive
from idhazh.ledger import read_header as _read_header
from idhazh.ledger import require_matching_header

#: The store, its POSIX prefix, and where one date's rows go. All four are
#: `idhazh.ledger`'s, spelled once there: the compaction's head table has to name
#: the file a segment drains into, and that table cannot import this module
#: without a cycle. The names below are this module's own vocabulary for them.
LEDGER_DIRNAME: Final = ledger.SCORES_DIRNAME
LEDGER_RELDIR: Final = f"{ledger.STATE_DIRNAME}/{LEDGER_DIRNAME}"
ledger_relpath = ledger.scores_relpath
ledger_path = ledger.scores_path

INDEX_DIRNAME: Final = ledger.SCORE_INDEX_DIRNAME
INDEX_RELDIR: Final = f"{ledger.STATE_DIRNAME}/{INDEX_DIRNAME}"
index_relpath = ledger.score_index_relpath
index_path = ledger.score_index_path

#: What makes two rows the same measurement. `idhazh.ledger.OBSERVATION_KEY` is
#: the definition and this is the name this module has always called it; the
#: compaction settles a day's segments on the same tuple.
OBSERVATION_KEY: Final = ledger.OBSERVATION_KEY


def ledger_days(state_dir: Path) -> list[Path]:
    """Every committed shard of the ledger, oldest day first.

    Anything that is not a day of this store is left alone:
    `retention.prune_scores` archives and then deletes out of this directory, so
    it names what it recognises rather than acting on what it does not. What
    counts as a day is `day_shards.shard_files` and nothing local - this
    directory is the one where getting that wrong deletes a file. That walk
    reads a `<DD>.csv` day file and a `<DD>/` day directory of writer-owned
    files alike, so nothing here moves when the store changes shape.

    The daily settlement was the caller that made this a cost, and it is gone. A
    run appends to the one day file `ledger_path` names, so that file is the only
    place a repeat can be, and walking the rest charged every run for every day on
    record (Guardrail #12). The operator's full pass still comes here, and it is
    unbounded because every one of its callers has to see the whole ledger.
    """
    return list(
        day_shards.shard_files(state_dir / LEDGER_DIRNAME, days=UNBOUNDED_WINDOW)
    )


def records(state_dir: Path) -> Iterator[dict[str, str]]:
    """Every committed row, oldest day first, as the CSV spells it.

    One sequence over many files, so a reader that wants the whole ledger reads
    it the way it always did and a reader that wants a window can skip whole days
    instead.
    """
    for shard in ledger_days(state_dir):
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
    day files are unlinked, and the summary keeps this digest rather than the four
    values it came from - `state/score-archive/` is a fixed-width index instead
    of a second copy of the addresses.
    """
    return archive.digest_of(observation(payload))


def recorded_observations(state_dir: Path) -> set[str]:
    """Every measurement the ledger already holds, live months and archived months alike.

    Deliberately not scoped to the day being written. An observation is the
    same measurement whichever month it is re-taken in, and a dedupe that only
    looked at the current day would let a January row come back in February -
    which would turn a count over the ledger into a count of times the pipeline
    looked, and that is the one thing this ledger promises it is not.

    **The archived half is what makes deleting a day safe.** A month older
    than the full-grain window has no rows left to read, so a dedupe over the
    rows alone would call every measurement in it new the day it was deleted.
    `state/score-archive/<YYYY-MM>.json` carries those digests for exactly this
    union, and it is why the archive stores them sorted (`docs/concepts/
    evaluation.md`).

    **Neither half reads a score row.** Both are fixed-width digest records, so
    what this costs follows the measurements the ledger holds rather than the
    bytes it spent describing them - 76 bytes an observation against a measured
    819.6. The cover is still every observation, with nothing forgotten.

    A missing directory on either side is a ledger with no history, which is
    what a fresh clone has.
    """
    refresh_index(state_dir)
    return indexed_observations(state_dir) | archive.archived_observations(state_dir)


def index_days(state_dir: Path) -> list[Path]:
    """Every committed shard of the index, oldest day first.

    `day_shards.shard_files` for the reason `ledger_days` gives, and unbounded
    for the reason it gives: every caller here needs the whole index.
    """
    return list(day_shards.shard_files(state_dir / INDEX_DIRNAME, days=UNBOUNDED_WINDOW))


def index_columns() -> tuple[str, ...]:
    """One definition, so a writer and a reader cannot disagree about the shape."""
    return ObservationIndexRow.csv_columns()


def indexed_observations(state_dir: Path) -> set[str]:
    """The digests the live index holds. A raw read of the cell, not a row build.

    **This opens one file a recorded day and it is declared rather than hidden**
    (Guardrail #12, `docs/concepts/growing-reads.md`). It was one file a month
    until 2026-09-13, when the grain change turned 2 opens into 23, and it gains
    about 365 a year. The store bound is what answers it: a day past
    `observability.scores_full_grain_months` is folded into one
    `state/score-archive/<YYYY-MM>.json` and its index day is dropped, so the
    live index holds at most fourteen months of days. **`--dry-run` is on the
    workflow step today, so nothing prunes and the count grows until that is
    flipped** (`docs/architecture/publishing/retention.md`).

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


def refresh_index(state_dir: Path) -> int:
    """Fill a day with no index, drop one the archive replaced. Returns digests written.

    Two jobs, and both are about a partition the index does not describe at all.

    **A day with no index is filled from its rows, once.** That is the
    read-side migration: the first run after this landed meets a ledger written
    before the index existed, and it has to refuse exactly what it refuses
    today. It pays one read of the rows to never read them again.

    **An index whose month became an archive is dropped.** The archive carries
    those digests for ever, so a live copy beside it is a second record of one
    month and would double what this index costs. The boundary is a month
    because the archive's is; the files it takes are days, the same arithmetic
    `retention.prune_scores` does on the ledger. The guard is the one that
    matters: the drop happens only when the archive is on disk, so nothing here
    can remove the last record of a measurement. A day that went without an
    archive - deleted by hand, or by a prune whose archive would not reconcile -
    leaves the index standing as the only thing that remembers it.

    **A day whose index exists is never compared against its rows, and that
    is the trade rather than an omission.** Asking whether an index is behind
    the rows beside it means reading those rows, which is the bill this index
    exists to remove. So the two files are kept in step by the writer instead:
    `append` writes the rows and the digests it minted in one call, and every
    writer of `state/scores/` in this repository goes through it. A day file that
    grew behind the index's back - rows appended by something that never knew
    the index existed, which is what a long-lived branch meets when it merges a
    `main` older than this file - is repaired by `rebuild_index`, which an
    operator runs against the days it names and which checks its own result.

    A partial fill is safe in the direction that matters. It under-reports, so a
    measurement lands twice and the compaction settles the two against
    `OBSERVATION_KEY` when it folds them. Over-reporting is the one that cannot be
    repaired, and nothing here can produce it.
    """
    live = _by_day(ledger_days(state_dir))
    written = 0
    for date, shards in sorted(live.items()):
        path = index_path(state_dir, date)
        if path.exists():
            continue
        written += _fill_index(shards, path)

    archived = {path.stem for path in archive.archive_files(state_dir)}
    for path in index_days(state_dir):
        date = day_shards.date_of(path)
        if date not in live and date[:7] in archived:
            path.unlink()
            day_partition.drop_empty_day_dirs(path)
    return written


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
    """Drop each named day's index, write it again from the rows, and name what was wrong.

    The repair `refresh_index` has no path to. That function fills a partition
    with **no** index and never compares one that exists against the rows beside
    it, because comparing means reading the rows and reading the rows is the bill
    the index exists to remove. So an index that drifted - a fill a crash cut
    short, a day file that grew behind its back - stands for ever, and
    the next dedupe silently admits a measurement the ledger already holds.

    Dropping the file is the recipe `refresh_index` has always described. What
    this adds is the assertion: the rewritten index is read back and compared
    against the rows in **both** directions, and a disagreement raises instead
    of returning a count. One direction passes on an index that only ever grows.

    **It writes the file the partition rule names today, and it removes no
    other.** A file at a grain no reader recognises is ignored rather than
    refused (`day_partition.day_files`), so it is invisible to the comparison as
    well - which is the whole of why a grain change has to take its old files
    away itself. That is the path this ledger took on 2026-09-13: the two month
    indexes were deleted by the commit that moved the grain, and this rebuilt
    every day beside the migrated rows.

    Returns what each named day had wrong **before** it was rewritten, so a
    repair reports the drift rather than hiding it. Two empty sets for a day
    is an answer, not a no-op: it says that index was telling the truth.

    **An operator command, and no stage calls it.** It opens every row of every
    day it is given - the read the index exists to avoid - so the cover is the
    days the caller names and there is no default (Guardrail #12,
    `stages.rebuild_score_index.stage_rebuild_score_index`). A day with no committed rows is refused
    by name rather than skipped: a typo must not read as a clean pass over
    nothing.
    """
    live = _by_day(ledger_days(state_dir))
    named = sorted({day[:10] for day in days})
    if not named:
        raise ValueError("rebuild_index was given no day, and a pass over none repairs none")
    absent = [date for date in named if date not in live]
    if absent:
        raise FileNotFoundError(f"{LEDGER_RELDIR} holds no rows for {absent}")

    found: dict[str, IndexDrift] = {}
    for date in named:
        path = index_path(state_dir, date)
        produced = _digests_of_day(live[date])
        found[date] = _drift(_digests_of_index(path), produced)
        path.unlink(missing_ok=True)
        _fill_index(live[date], path)
        after = _drift(_digests_of_index(path), produced)
        if after.extra or after.missing:
            raise RuntimeError(
                f"{index_relpath(date)} still disagrees with the rows beside it after a "
                f"rebuild: {len(after.extra)} digests it holds that the rows cannot produce, "
                f"{len(after.missing)} the rows produce that it does not hold"
            )
    return found


def _drift(held: frozenset[str], produced: frozenset[str]) -> IndexDrift:
    """Both directions at once, so no call site can ask for only one."""
    return IndexDrift(extra=held - produced, missing=produced - held)


def _by_day(shards: Iterable[Path]) -> dict[str, list[Path]]:
    """The shards of each recorded day, keyed by the day they are filed under.

    A day is one file today and a directory of writer-owned files after the
    store changes shape, so a caller that asks about a date gets every file that
    date holds rather than whichever one the walk named last.
    """
    by_day: dict[str, list[Path]] = {}
    for shard in shards:
        by_day.setdefault(day_shards.date_of(shard), []).append(shard)
    return by_day


def _fill_index(shards: Sequence[Path], path: Path) -> int:
    """Write one day's index from the rows beside it. The one place that does.

    Both callers come here: `refresh_index` for a day that has no index, and
    `rebuild_index` for one it has just dropped. A second implementation is how
    the two would come to disagree about what a digest is.
    """
    return _append_index(path, _distinct(_observations_of(shards)))


def _observations_of(shards: Sequence[Path]) -> Iterator[str]:
    """Every row's observation digest, across one day's shards, in file order."""
    for shard in shards:
        if not shard.exists():
            continue
        with shard.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                yield observation_digest(row)


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


def _digests_of_day(shards: Sequence[Path]) -> frozenset[str]:
    """The distinct observations one day's rows produce, read from the rows.

    The one read here that opens a score row on purpose, which is why only
    `rebuild_index` calls it and why that is a command a person types.
    """
    return frozenset(_observations_of(shards))


def _distinct(digests: Iterable[str]) -> list[str]:
    """The digests in the order they were first seen, each one once.

    A day file can hold the same observation twice between the two segments that
    carried it and the compaction that folds them. The index is a set, so it
    records the identity once and the repeat costs nothing.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for digest in digests:
        if digest in seen:
            continue
        seen.add(digest)
        ordered.append(digest)
    return ordered


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


def append(state_dir: Path, rows: Iterable[EvalRow]) -> int:
    """Append the measurements this run made, writing each day file's header once.

    Returns how many landed, so a caller can log the count rather than re-read
    the files to find out. A row the ledger already holds is not one of them.

    Rows are filed by their own `date`, so a run that publishes either side of
    midnight writes two day files and neither is wrong. Within one call the
    header check and the write happen per day.

    A header that no longer matches the contract stops the run. A day file is
    append-only and its header is written once, so a new column would otherwise
    put more cells on a row than the header names, and every reader that maps by
    position would silently read one column under another column's name. Failing
    here is what makes adding a column a migration instead of a corruption.
    """
    pending = list(rows)
    if not pending:
        return 0

    # Before the dedupe, not after it. A day file whose header no longer matches
    # the contract is corrupt whatever this call had to say, and the dedupe would
    # otherwise return 0 and never reach the check - which is how a stale header
    # survives a run that appeared to do nothing wrong.
    #
    # The cover is the days this call writes, which is one or two, and not every
    # committed day. It used to be every one, and that was affordable while the
    # ledger filed by month and held two files; at day grain it would have been a
    # read that costs one more open every day the pipeline runs, on the hot path
    # of every append (Guardrail #12). The narrower cover is also the exact one:
    # a file this call does not append to is a file this call cannot corrupt, and
    # a back-dated run is covered because the rows' own dates are what name the
    # files. What it gives up is noticing a stale header on a day nothing is
    # writing to - which no run can create and which the first reader of that day
    # refuses through its own contract.
    for date in sorted({str(row.date)[:10] for row in pending}):
        day = ledger_path(state_dir, date)
        if day.exists():
            require_matching_header(day, columns())

    already = recorded_observations(state_dir)
    fresh: dict[str, list[dict[str, object]]] = {}
    minted: dict[str, list[str]] = {}
    for row, digest in _unrecorded(pending, already):
        payload = row.model_dump(mode="json")
        date = str(payload["date"])[:10]
        fresh.setdefault(date, []).append(payload)
        minted.setdefault(date, []).append(digest)
    if not fresh:
        return 0

    landed = 0
    for date, payloads in sorted(fresh.items()):
        path = ledger_path(state_dir, date)
        path.parent.mkdir(parents=True, exist_ok=True)
        exists = path.exists()
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns(), lineterminator="\n")
            if not exists:
                writer.writeheader()
            for payload in payloads:
                writer.writerow({name: payload[name] for name in columns()})
        # The rows first, then the index, and the order is the whole argument. A
        # crash between the two leaves a measurement recorded and not indexed,
        # which the next run appends a second time and the compaction settles
        # against `OBSERVATION_KEY`. The other order leaves a digest whose row
        # was never written - a measurement nothing will ever take again, and
        # nothing on disk that says it is missing.
        _append_index(index_path(state_dir, date), minted[date])
        landed += len(payloads)
    return landed


def _unrecorded(rows: Sequence[EvalRow], already: set[str]) -> list[tuple[EvalRow, str]]:
    """The measurements the ledger does not already hold, each with its digest.

    One filter for both writers, so the head and the segment admit exactly the
    same rows. `already` is added to as it goes, because a run can hand the same
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


def append_segment(
    state_dir: Path,
    rows: Iterable[EvalRow],
    *,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
) -> int:
    """Put this writer's measurements in its own segment, for the compaction to fold.

    Two jobs of one run measure items - a work shard as each item settles, and
    assemble over the whole day afterwards - so neither may open the day file.
    Each writes `state/segments/scores/<run>-<attempt>-<job>-<shard>.csv` and the
    index beside it, and `stage_compact` folds both into the heads. Two writers
    never share a path, so a lost push race costs a merge rather than the rows,
    and a re-run's second attempt corrects its first try instead of colliding
    with it.

    **The dedupe still reads the heads, and what it cannot see is settled later.**
    A measurement already in a committed day is skipped here exactly as it is on
    the head path. A measurement this run's other writer put in a segment
    minutes ago is invisible - the segment is not a head and nothing reads one
    but the compaction - so both writers mint it, and the fold settles the pair
    against `OBSERVATION_KEY`. That is the same answer by a later route, which is
    what makes it safe to run a second time.

    **Nothing here checks a head's header.** The head path fails early on a
    header the contract no longer names, because it is about to append under it.
    This writes no head; the compaction reads one, and it re-files a stale header
    through `ledger.settle_header` before it merges a row into it.

    Returns how many measurements went into the segment, so a caller can log the
    count.
    """
    pending = list(rows)
    if not pending:
        return 0
    fresh = _unrecorded(pending, recorded_observations(state_dir))
    if not fresh:
        return 0
    stamp = ObservationIndexRow.schema_version()
    written = ledger.write_segment(
        state_dir,
        ledger.SegmentLedger.SCORES,
        [row for row, _ in fresh],
        run_id=run_id,
        attempt=attempt,
        job=job,
        shard=shard,
    )
    # The rows first, then the index, for the reason `append` gives: a crash
    # between the two leaves a measurement recorded and not indexed, which the
    # next run mints again and the fold settles. The other order leaves a digest
    # whose row was never written.
    ledger.write_segment(
        state_dir,
        ledger.SegmentLedger.SCORE_INDEX,
        [
            ObservationIndexRow.model_validate({"version": stamp, "observation_digest": digest})
            for _, digest in fresh
        ],
        run_id=run_id,
        attempt=attempt,
        job=job,
        shard=shard,
    )
    return written
