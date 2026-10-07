"""How does a named prune take a range of days out of a ledger the door files, and what changes?

`prune.py` decides which ledger and which days. This does the work for a
ledger whose files sit under `state/raw/` and `state/compact/`, where a day is
not one file: its rows sit in the raw files its writers left that day, or in
the day's compact file, or in its month's or its year's file
(`ledger/day_removal.py` says which).

**A member is a day.** The days a pass may take are the days of the range
that a raw file covers, or a compact file whose index counts a row, read from
names and indexes alone - so every day of the range in a month or a year file
that holds a row is one - and the ceiling takes the oldest first. `kept` is
every day the ledger holds outside the range, and `resume_from` is the first
day of the range a ceiling left.

**For the days it takes, a pass changes three kinds of file, in this order:**

1. it deletes the days' raw files;
2. it rebuilds each daily, monthly and yearly file that holds a row of them,
   once, without their rows - a file whose every row goes stays as an empty
   file, so no index has a hole;
3. it rewrites each index that names a rebuilt file, in the bytes the
   compaction writes an index in. The rebuilt file's entry takes the file's
   new row count and size and keeps every other field as it was, so the days
   it records lost and the files it counts set aside outlive the prune.

Deletes first, so a day the pass has not finished still holds a row in a
compact file, or its index still says it does, and the same command takes it
again; then each file before its index, as the compaction orders them. No
compaction mark moves: every index names the periods it named before.

**No file is ever half-written, and the same command finishes a pass that
stopped.** Each write is whole, through `atomic_write`, and each delete is one
`unlink`. A pass that a ceiling or a failure stopped is finished by running the
same command again: a deleted file is no longer listed, a rebuilt file no
longer holds the days and is rebuilt to the same rows, and each index is
rewritten from the files as they then stand. A failure part way raises
`PruneInterruptedError`, carrying what had already changed and, in its `fault`,
what the failure means as `error_cause` reads it.

**A dry run decides everything and changes nothing.** It reads the same files,
builds every rebuilt file in memory, and reports the paths a live pass would
delete and write, so the list a person reads before `--no-dry-run` is the list
the live pass carries out.

**What it reads (Guardrail #12).** The three compact indexes and the names of
the ledger's raw day folders, through `ledger.held_days`, to say how many days
lie outside the range: a names-only read of the whole ledger, the one
`docs/concepts/growing-reads.md` lists, and the CSV half's walk of a whole day
tree is the same question. Everything else is bounded by the range: the
envelope of each raw file in it, and each compact file that holds a day the pass
takes.

Every day is a UTC day (CLAUDE.md section 2).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from idhazh import atomic_write, day_partition, ledger
from idhazh.contracts.collection_prune import StopReason, stop_for
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import error_cause, one_at_a_time
from idhazh.ledger import HeldFile


@dataclass(frozen=True, slots=True)
class _Change:
    """One file a pass writes whole, or deletes, and what that frees."""

    path: Path
    #: The bytes to write, or None to delete the file.
    data: bytes | None
    #: A deleted file's size, or what a rewritten file shrank by.
    freed: int


def _shown(state_dir: Path, path: Path) -> str:
    """`state/...`, POSIX, whatever root a caller handed in (CLAUDE.md section 2)."""
    return f"{ledger.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}"


def _days(since: str, until: str) -> list[str]:
    """Every UTC day from `since` to `until`, both named."""
    first, last = date.fromisoformat(since), date.fromisoformat(until)
    return [(first + timedelta(days=step)).isoformat() for step in range((last - first).days + 1)]


def _shrank(path: Path, data: bytes) -> int:
    """What writing `data` over this file frees. A file that grows frees nothing."""
    return max(0, path.stat().st_size - len(data))


def _changes(
    state_dir: Path,
    name: LedgerName,
    held: Sequence[HeldFile],
    taken: set[str],
    *,
    identity: WriterIdentity,
) -> list[_Change]:
    """Every file the pass deletes and writes for the days it takes, in the order it acts."""
    deletes: list[_Change] = []
    for day in sorted(taken):
        deletes.extend(
            _Change(found.path, None, found.path.stat().st_size)
            for found in held
            if found.period is None and found.covers == day
        )
    rebuilt: list[_Change] = []
    entries: dict[Period, dict[str, CompactEntry]] = {}
    for found in held:
        days = tuple(day for day in found.days if day in taken)
        if not days or found.period is None:
            continue
        built = ledger.rebuild_without(state_dir, found, days, identity=identity)
        rebuilt.append(_Change(built.path, built.data, _shrank(found.path, built.data)))
        if built.path != found.path:
            rebuilt.append(_Change(found.path, None, 0))
        if found.period not in entries:
            index = CompactIndex.read(ledger.compact_index_path(state_dir, name, found.period))
            entries[found.period] = {entry.covers: entry for entry in index.entries}
        named = entries[found.period]
        named[found.covers] = named[found.covers].model_copy(
            update={"rows": built.rows, "bytes": len(built.data)}
        )
    indexes: list[_Change] = []
    for period, named in entries.items():
        path = ledger.compact_index_path(state_dir, name, period)
        index = CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=name,
            period=period,
            entries=[named[covers] for covers in sorted(named)],
        )
        data = index.to_json().encode("ascii")
        indexes.append(_Change(path, data, _shrank(path, data)))
    return [*deletes, *rebuilt, *indexes]


def _apply(change: _Change) -> None:
    """Write one file whole, or delete it and the date folders it leaves empty."""
    if change.data is None:
        change.path.unlink()
        day_partition.drop_empty_day_dirs(change.path)
    else:
        atomic_write.write_atomic_bytes(change.path, change.data)


def take_days(
    state_dir: Path,
    name: LedgerName,
    *,
    since: str,
    until: str,
    ceiling: int,
    dry_run: bool,
    identity: WriterIdentity,
) -> one_at_a_time.Pass:
    """Take up to `ceiling` days of the range out of this ledger, oldest first; say what changed.

    The record is the one the CSV half returns: `taken` is every file deleted,
    or that would be, and `written` every file rewritten. `identity` is the
    writer every rebuilt file's envelope names, on a dry run too, because a dry
    run builds each file it reports.
    """
    if ceiling < 0:
        raise ValueError(f"a ceiling is a count of days, not {ceiling}")
    held = ledger.find_holding_files(state_dir, name, _days(since, until))
    members = sorted({day for found in held for day in found.days})
    taken = set(members[:ceiling])
    resume_from = members[ceiling] if len(members) > ceiling else None
    outside = sum(1 for day in ledger.held_days(state_dir, name) if not since <= day <= until)
    changes = _changes(state_dir, name, held, taken, identity=identity)

    def record(
        done: Sequence[_Change],
        because: StopReason,
        resume: str | None,
        fault: GardenerFault | None = None,
    ) -> one_at_a_time.Pass:
        """The record of the changes made so far, built in one place for every exit."""
        return one_at_a_time.Pass(
            collection=name.value,
            since=since,
            until=until,
            ceiling=ceiling,
            dry_run=dry_run,
            seen=outside + len(members),
            selected=len(members),
            taken=tuple(
                _shown(state_dir, change.path) for change in done if change.data is None
            ),
            written=tuple(
                _shown(state_dir, change.path) for change in done if change.data is not None
            ),
            bytes_freed=sum(change.freed for change in done),
            stopped_because=because,
            resume_from=resume,
            fault=fault,
        )

    stopped = StopReason.EXHAUSTED if resume_from is None else StopReason.CEILING
    if dry_run:
        return record(changes, stopped, resume_from)
    done: list[_Change] = []
    for change in changes:
        try:
            _apply(change)
        except OSError as failure:
            first = min(taken) if taken else None
            fault = error_cause.fault_of(error_cause.classify(failure))
            raise one_at_a_time.PruneInterruptedError(
                record(done, stop_for(fault), first, fault)
            ) from failure
        done.append(change)
    return record(done, stopped, resume_from)
