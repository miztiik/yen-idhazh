"""Where on disk does one shard's committed trace live?

Where a raw trace lands once it is committed rather than left under gitignored
`backend/var/`. The rollup is the record of a run; a raw trace is evidence with a
short life, kept only so an operator can open a recent run. The gardener's
`traces` task deletes whole files past its window, because a trace is a lookup
and a fold of it would invent a total nobody reads (`docs/concepts/telemetry.md`).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import LedgerName

#: A trace is JSON lines, one file a writer inside a day folder, named for that
#: writer rather than minted by the ledger door.
TRACE_SUFFIX: Final = ".jsonl"


def _trace_day(run_id: str) -> str:
    """The day a run id names: `2026-08-21-1` -> `2026-08-21`.

    A `RunId` is `<YYYY>-<MM>-<DD>-<ordinal>` and the ordinal carries no dash, so
    a plain split gives exactly four parts. A trace carries no date cell of its
    own, so the run id is what says which day the file belongs under.
    """
    parts = run_id.split("-")
    if len(parts) != 4:
        raise ValueError(f"run id {run_id!r} is not <YYYY>-<MM>-<DD>-<ordinal>")
    return "-".join(parts[:3])


def committed_trace_relpath(
    *, run_id: str, attempt: int, job: ServerJob, shard: int
) -> str:
    """The POSIX relpath one writer's committed trace is filed under.

    `state/traces/<YYYY>/<MM>/<DD>/<run_id>-<attempt>-<job>-<shard>.jsonl`
    (section 2: relative, POSIX, minimal). The day is a directory and the file
    carries the four elements that make it this writer's own -
    `ledger.segment_name` spells them, so every name written this way names
    one writer one way. The day directory is the registry's `traces` entry.
    """
    name = ledger.segment_name(
        run_id=run_id, attempt=attempt, job=job, shard=shard, suffix=TRACE_SUFFIX
    )
    return f"{ledger.relpath(LedgerName.TRACES, _trace_day(run_id))}/{name}"


def committed_trace_path(
    state_dir: Path, *, run_id: str, attempt: int, job: ServerJob, shard: int
) -> Path:
    """The file one writer's committed trace is written to and pruned from."""
    name = ledger.segment_name(
        run_id=run_id, attempt=attempt, job=job, shard=shard, suffix=TRACE_SUFFIX
    )
    return ledger.path(state_dir, LedgerName.TRACES, _trace_day(run_id)) / name


def trace_date(path: Path, traces_root: Path) -> date | None:
    """The published day a committed trace path encodes, or None if it is not one.

    The reverse of `committed_trace_path`: all three parts come from the
    `<YYYY>/<MM>/<DD>/` directories, so the file name says nothing about the day
    and a trace written before traces carried identity is read by exactly the
    same rule as one written after. None for a path the shape does not
    recognise, so a stray file under the tree is left alone rather than deleted.
    """
    try:
        rel = path.relative_to(traces_root)
    except ValueError:
        return None
    if len(rel.parts) != 4:
        return None
    year, month, day, _ = rel.parts
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None
