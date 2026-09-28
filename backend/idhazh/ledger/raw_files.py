"""Which raw files hold one ledger's current rows, and what those rows are.

A raw ledger is many small files under `state/raw/<ledger>/<YYYY>/<MM>/<DD>/`,
one per writer per day, each written once by the door in `ledger/persist.py`.
Two attempts at one work unit leave two files carrying one `unit_id`, and only
the higher attempt is current: GitHub re-runs a failed job into the same run id,
so the re-run replaces its first try rather than adding to it. The door writes
both files and removes neither, and it says that choosing between them is a
reader's job. This module is that job, done once, so no reader invents its own
version of it.

**Oldest first, and the order is written down rather than inherited.** Files
sort by the day they cover, then by the instant they were written, then by
their `file_id`, all read from each file's own envelope. A directory listing
happens to agree today, because a `file_id` starts with its clock; a reader that
leaned on that would change its answer the day the name grammar did.

**The walk reads every day a ledger has a folder for, and that is deliberate
(Guardrail #12).** The two ledgers that read through here ask about their whole
history: a retirement is permanent, so a window would forget the oldest ones
and ask a dead server again, and the cleanup record is about whether a backlog
is shrinking, which has no time bound. What it costs grows with the files: one
per day of retirements and one per cleanup pass, and a parquet file's envelope
is read from its footer without its rows.
`docs/concepts/growing-reads.md` lists both reads.

**A file this build cannot read is skipped, with one warning that names it.** A
file under a newer row shape, a row today's model refuses, a file that is not a
ledger file at all, or one filed in the wrong folder is a `ValueError`, and a
reader that stopped on it would cost the run its day to protect one row. Only
`ValueError` is caught. A missing parquet engine raises `ImportError`, and that
must stop the run: skipping every file for it would read as a ledger with no
history.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import NamedTuple

from idhazh import day_partition
from idhazh.contracts.base import Contract
from idhazh.contracts.file_envelope import FileEnvelope, Tier
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths
from idhazh.ledger.keys import preference_for
from idhazh.ledger.persist import load, read_envelope

logger = logging.getLogger(__name__)


class RawFile(NamedTuple):
    """One raw file, and the envelope that says what it holds."""

    path: Path
    envelope: FileEnvelope


def _shown(state_dir: Path, path: Path) -> str:
    """A path as it may leave the process: under `state/`, POSIX (CLAUDE.md section 2)."""
    return f"{paths.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}"


def _skip(state_dir: Path, path: Path, reason: object) -> None:
    """Say which file a read left out, and why, in the one line a person will look for."""
    logger.warning("skipped a raw file path=%s reason=%s", _shown(state_dir, path), reason)


def _day_folders(state_dir: Path, root: Path) -> list[tuple[str, Path]]:
    """Every `<YYYY>/<MM>/<DD>` folder under one ledger's raw root, with the day it names.

    The index listings sit beside the years, in `index/`, and are not rows, so
    that one name is passed over in silence. Anything else that is not a day
    folder is named in a warning and left alone.
    """
    if not root.is_dir():
        return []
    found: list[tuple[str, Path]] = []
    for year in sorted(root.iterdir()):
        if year.name == paths.INDEX_DIRNAME and year.is_dir():
            continue
        if not (year.is_dir() and day_partition.is_segment(year.name, day_partition.YEAR_WIDTH)):
            _skip(state_dir, year, "not a YYYY folder")
            continue
        for month in sorted(year.iterdir()):
            if not (
                month.is_dir()
                and day_partition.is_segment(month.name, day_partition.SEGMENT_WIDTH)
            ):
                _skip(state_dir, month, "not an MM folder")
                continue
            for day in sorted(month.iterdir()):
                if not (
                    day.is_dir() and day_partition.is_segment(day.name, day_partition.SEGMENT_WIDTH)
                ):
                    _skip(state_dir, day, "not a DD folder")
                    continue
                found.append((f"{year.name}-{month.name}-{day.name}", day))
    return found


def _order(held: RawFile) -> tuple[str, int, str]:
    """Oldest first: the day covered, then the write instant, then the file's own id."""
    return (held.envelope.covers, held.envelope.written_at_ms, str(held.envelope.file_id))


def list_raw_files(state_dir: Path, ledger: LedgerName) -> list[RawFile]:
    """Every raw file of this ledger whose envelope this build can read, oldest first.

    Every file in a day folder is read, whatever its suffix, because
    `ledger.format` may be JSON lines as well as parquet. A file whose envelope
    names another ledger, another tier or another day than the folder it sits in
    was filed by something other than the door, and is skipped as unreadable.
    """
    found: list[RawFile] = []
    for covers, folder in _day_folders(state_dir, paths.raw_root(state_dir, ledger)):
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                _skip(state_dir, path, "not a file")
                continue
            try:
                envelope = read_envelope(path)
                if (envelope.ledger, envelope.tier, envelope.covers) != (ledger, Tier.RAW, covers):
                    raise ValueError(
                        f"its envelope says {envelope.tier.value} {envelope.ledger.value} "
                        f"{envelope.covers}, and it sits in the raw {ledger.value} folder "
                        f"for {covers}"
                    )
            except ValueError as refusal:
                _skip(state_dir, path, refusal)
                continue
            found.append(RawFile(path, envelope))
    return sorted(found, key=_order)


def _rank(held: RawFile) -> tuple[int, int, str]:
    """Which of two files for one work unit is current: the higher attempt, then the later write."""
    return (held.envelope.identity.attempt, held.envelope.written_at_ms, str(held.envelope.file_id))


def pick_current_files(state_dir: Path, ledger: LedgerName) -> list[RawFile]:
    """For each work unit, the file its highest attempt wrote, oldest first.

    Two files at one attempt for one unit would be one attempt writing twice,
    which the door never does; the later write is kept, so the answer is still
    one file and still the same file on every read.
    """
    best: dict[uuid.UUID, RawFile] = {}
    for held in list_raw_files(state_dir, ledger):
        kept = best.get(held.envelope.unit_id)
        if kept is None or _rank(held) > _rank(kept):
            best[held.envelope.unit_id] = held
    return sorted(best.values(), key=_order)


def load_current_rows[C: Contract](
    state_dir: Path, ledger: LedgerName, *, model: type[C], key: tuple[str, ...]
) -> list[C]:
    """This ledger's current rows, oldest first, and the first row of each `key` only.

    Two writers that are not attempts at one unit - two runs, say, reading the
    same evidence from two stale checkouts - can each file a row for one key.
    The first one filed is kept, which is the rule `ledger/keys.py` gives a key
    that declares no preference of its own. A key that does declare one is
    refused here, because this reader would apply the wrong rule to it.

    Each file is read on its own, so one file this build cannot read costs the
    rows in it and never the rows in the files beside it.
    """
    if preference_for(key) is not None:
        raise ValueError(
            f"{ledger.value} settles on {key}, which declares a preference, and this "
            "reader keeps the first row per key"
        )
    kept: dict[tuple[str, ...], C] = {}
    for held in pick_current_files(state_dir, ledger):
        try:
            rows = load([held.path], model=model)
        except ValueError as refusal:
            _skip(state_dir, held.path, refusal)
            continue
        for row in rows:
            kept.setdefault(tuple(str(getattr(row, name)) for name in key), row)
    return list(kept.values())
