"""Where on disk does one shard's committed trace live?

Where a raw trace lands once it is committed rather than left under gitignored
`backend/var/`. The rollup is the record of a run; a raw trace is evidence with a
short life, kept only so an operator can open a recent run.
`retention.prune_traces` deletes whole files past
`observability.trace_window_days`, because a trace is a lookup and a fold of it
would invent a total nobody reads (`docs/concepts/telemetry.md`).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

from idhazh.ledger import STATE_DIRNAME

#: The committed trace tree, a child of `state/`.
TRACES_DIRNAME: Final = "traces"


def _trace_parts(run_id: str) -> tuple[str, str, str, str]:
    """Split a run id into its date and ordinal: `2026-08-21-1` -> (2026, 08, 21, 1).

    A `RunId` is `<YYYY>-<MM>-<DD>-<ordinal>` and the ordinal carries no dash, so
    a plain split gives exactly four parts. The date is spelled once in the path -
    as the `<YYYY>/<MM>/` directories and the `<DD>` filename prefix - so the run
    slot in the file name is the ordinal alone, not the whole id, which already
    spells the date.
    """
    parts = run_id.split("-")
    if len(parts) != 4:
        raise ValueError(f"run id {run_id!r} is not <YYYY>-<MM>-<DD>-<ordinal>")
    year, month, day, ordinal = parts
    return year, month, day, ordinal


def committed_trace_relpath(run_id: str, shard: int) -> str:
    """The POSIX relpath one shard's committed trace is filed under.

    `state/traces/<YYYY>/<MM>/<DD>-<ordinal>-<shard>.jsonl` (section 2: relative,
    POSIX, minimal). The shard is zero-padded to match the run's other per-shard
    file names.
    """
    year, month, day, ordinal = _trace_parts(run_id)
    return f"{STATE_DIRNAME}/{TRACES_DIRNAME}/{year}/{month}/{day}-{ordinal}-{shard:02d}.jsonl"


def committed_trace_path(state_dir: Path, run_id: str, shard: int) -> Path:
    """The file one shard's committed trace is written to and pruned from."""
    year, month, day, ordinal = _trace_parts(run_id)
    return state_dir / TRACES_DIRNAME / year / month / f"{day}-{ordinal}-{shard:02d}.jsonl"


def trace_date(path: Path, traces_root: Path) -> date | None:
    """The published day a committed trace path encodes, or None if it is not one.

    The reverse of `committed_trace_path`: the year and month come from the
    `<YYYY>/<MM>/` directories and the day from the `<DD>-...` file name. None for
    a path the shape does not recognise, so a stray file under the tree is left
    alone rather than deleted - the rule `retention.month_shards` keeps.
    """
    try:
        rel = path.relative_to(traces_root)
    except ValueError:
        return None
    if len(rel.parts) != 3:
        return None
    year, month, name = rel.parts
    day = name.split("-", 1)[0]
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None
