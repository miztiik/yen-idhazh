"""What one writer's file under `state/` is called, and how that name reads back.

Every name under `state/` is minted here and read back here, and nowhere else. A
producer hands the ledger its rows and its writer identity, and the ledger
decides what the file is called. A caller that builds a name is a caller that
will disagree with the parser the next time either one changes.

Minting and parsing sit together because they are one question asked in two
directions, and two files would let the pattern and its reader drift apart.

**A file the ledger door writes carries two identifiers, because it answers two
questions.** `unit_id` says which work unit the file records and is identical
for every attempt at that unit, so a union keeps the highest attempt per unit.
`file_id` is the file's name and differs for every file ever written, so no two
writers take one path. `attempt` goes only into `file_id` and `producer` only
into `unit_id`: put `attempt` into `unit_id` and two attempts at one unit would
both survive the union, which is the duplicate the union exists to remove.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Final, NamedTuple

from idhazh.contracts.base import RUN_ID_PATTERN, ServerJob
from idhazh.ledger.paths import STATE_DIRNAME

#: The namespace every `unit_id` is minted under. A protocol constant rather
#: than a knob: change it and every `unit_id` ever written stops matching the
#: ones minted after, so a union could no longer collapse a re-run onto its
#: original.
NAMESPACE: Final = uuid.uuid5(uuid.NAMESPACE_URL, "github.com/miztiik/yen-idhazh")

#: The field widths RFC 9562 fixes for a version 8 UUID.
_CLOCK_BITS: Final = 48
_RAND_A_BITS: Final = 12
_RAND_B_BITS: Final = 62


class SegmentName(NamedTuple):
    """A writer's filename read back: who wrote it, and on which try.

    `attempt` is the cell that is in the name and in no column. GitHub keeps the
    run id stable across a re-run, so without it a second attempt writes the
    path the first one took.
    """

    run_id: str
    attempt: int
    job: ServerJob
    shard: int


#: `<run_id>-<attempt>-<job>-<shard>.csv`. The run id is spelled from the
#: contract's own pattern and the jobs from the enum, so neither is a second
#: list to keep in step. `re.ASCII` because a `\\d` in a `str` pattern otherwise
#: takes another script's numerals, and `int` takes them too - the name would
#: then carry a digit no later glob matches.
#:
#: Private, because this pattern is the ledger's own. `idhazh.path_classes`
#: answers whether a committed path has exactly one writer, and it has to ask
#: this pattern rather than carry a copy - so it imports the private name
#: directly, and ruff's PLC2701 (import-private-name) refuses a second module
#: that does the same.
_SEGMENT_NAME: Final = re.compile(
    rf"(?P<run_id>{RUN_ID_PATTERN[1:-1]})"
    r"-(?P<attempt>[0-9]+)"
    rf"-(?P<job>{'|'.join(job.value for job in ServerJob)})"
    r"-(?P<shard>[0-9]{2})",
    re.ASCII,
)


_SEGMENT_SUFFIX: Final = ".csv"


#: What the migration calls the bytes a committed head already held. A head is
#: many runs already merged, so it carries no writer identity to stamp and a
#: synthetic one would claim a run that never wrote it.
#:
#: **Removal condition: it goes when the oldest committed day is newer than the
#: migration date**, because after that no committed day predates identity.
BEFORE_PARTITION_NAME: Final = "before-partition.csv"


#: What a committed trace was called before writes carried identity:
#: `<ordinal>-<shard>.jsonl`, where the ordinal is the run id's last segment
#: alone. A trace line carries `attributes, duration_ms, kind, name, parent_id,
#: span_id, started_at, trace_id` and no job and no attempt, so those two
#: elements are not recoverable and the bytes keep the name they were written
#: under.
#:
#: **Removal condition: it goes when the traces task's window has aged out
#: every file written before the migration.** That is self-clearing and needs no
#: later row - a trace is never folded, and the gardener's `traces` task deletes
#: whole files on that window.
PRE_IDENTITY_TRACE: Final = re.compile(r"[0-9]+-[0-9]{2}", re.ASCII)


#: What an operator's repair is called: `repair-<YYYYMMDDTHHMMSSZ>.csv`. A
#: repair is one add by a person at one instant, so it carries no run and no
#: job to spell, and the instant is what keeps two repairs apart.
#:
#: **Removal condition: it goes when no operator command adds rows to a day a
#: run already wrote.** `evals.writer.rebuild_index` is the only one today.
#: Private, same reason as `_SEGMENT_NAME` above.
_REPAIR_NAME: Final = re.compile(r"repair-[0-9]{8}T[0-9]{6}Z", re.ASCII)


#: The stamp format `_REPAIR_NAME` spells, for the caller that mints one. Private,
#: same reason as `_SEGMENT_NAME` above.
_REPAIR_STAMP: Final = "%Y%m%dT%H%M%SZ"


def repair_name(minted_at: datetime) -> str:
    """What an operator's one add into a committed day directory is called."""
    return f"repair-{minted_at.strftime(_REPAIR_STAMP)}{_SEGMENT_SUFFIX}"


def is_repair(name: str) -> bool:
    """Whether this filename is an operator's one add rather than a writer's file.

    Asked by the reader that orders a day's files and by the one that asks
    whether a committed path has a single writer, so it is spelled here once.
    """
    stem, _, suffix = name.rpartition(".")
    return suffix == _SEGMENT_SUFFIX[1:] and _REPAIR_NAME.fullmatch(stem) is not None


def segment_name(
    *, run_id: str, attempt: int, job: ServerJob, shard: int, suffix: str = _SEGMENT_SUFFIX
) -> str:
    """The identity grammar, spelled once, so two trees cannot spell it two ways.

    `suffix` is here because one tree's writer files are not CSV. A committed
    trace is JSON lines, and one spelling of identity across every tree is worth
    more than a signature nothing ever passes a second argument to: a second
    speller is a second grammar, and a reader that knew only one would walk past
    the other tree's files without saying so.
    """
    return f"{run_id}-{attempt}-{job.value}-{shard:02d}{suffix}"


def parse_segment_name(path: Path, *, suffix: str = _SEGMENT_SUFFIX) -> SegmentName:
    """A writer's filename read back, or a refusal naming the file.

    A name this cannot place is not skipped. A day directory holds one kind of
    file written by one kind of writer, so a name outside the grammar means
    something else is writing there - and a walk that passed over it would leave
    those rows in the tree unread and unmentioned, which is how a ledger starts
    losing rows with nobody noticing.

    `suffix` is the tree's own, for `segment_name`'s reason.
    """
    match = _SEGMENT_NAME.fullmatch(path.stem) if path.suffix == suffix else None
    if match is None:
        raise ValueError(
            f"{path.name} is not a writer's name. A writer's file is "
            f"<run_id>-<attempt>-<job>-<shard>{suffix}, and a file inside a day "
            f"directory under {STATE_DIRNAME}/ that is not one was written by "
            "something nobody here declared."
        )
    return SegmentName(
        run_id=match["run_id"],
        attempt=int(match["attempt"]),
        job=ServerJob(match["job"]),
        shard=int(match["shard"]),
    )


def fragment_name(run_id: str) -> str:
    """What one run's block of a published day is called: the run's own id.

    No two runs of a date share an id, so no two runs reach for one file and git
    has nothing to merge - which is the reason a day is filed as blocks at all.
    The id already opens on the date, so the name needs nothing else.
    """
    return f"{run_id}.json"


def unit_id(
    *, ledger: str, covers: str, run_id: str, job: str, shard: int, producer: str
) -> uuid.UUID:
    """Which work unit this file records. Identical for every attempt at that unit.

    A version 5 UUID with no clock and no attempt in it, so a re-run of a failed
    job, which GitHub files under the original run id, mints the same value and
    the union keeps only its newest attempt.
    """
    return uuid.uuid5(NAMESPACE, f"{ledger}|{covers}|{run_id}|{job}|{shard}|{producer}")


def file_id(*, unit: uuid.UUID, attempt: int, written_at_ms: int) -> uuid.UUID:
    """The name of one file. Minted once, when the file is written, and then kept.

    A version 8 UUID, clock first, so a listing sorts by time across
    milliseconds. Within one millisecond the order is arbitrary, because the bits
    after the clock are a hash. The instant is handed in rather than read here,
    so the function stays pure and its test needs no clock.
    """
    digest = hashlib.sha256(f"{unit}|{attempt}|{written_at_ms}".encode()).digest()
    return _pack_v8(
        written_at_ms & ((1 << _CLOCK_BITS) - 1),
        int.from_bytes(digest[0:2], "big") & ((1 << _RAND_A_BITS) - 1),
        int.from_bytes(digest[2:10], "big") & ((1 << _RAND_B_BITS) - 1),
    )


def _pack_v8(unix_ms: int, rand_a: int, rand_b: int) -> uuid.UUID:
    """Pack RFC 9562 version 8: 48 bits of clock, 12 free bits, 62 free bits.

    Written here because `uuid.uuid8` arrived in Python 3.14 and this project
    supports 3.12; the layout is fixed by the RFC, so packing it costs less than
    raising the floor.
    """
    return uuid.UUID(
        int=(unix_ms & ((1 << _CLOCK_BITS) - 1)) << 80
        | 0x8 << 76
        | (rand_a & ((1 << _RAND_A_BITS) - 1)) << 64
        | 0b10 << 62
        | rand_b & ((1 << _RAND_B_BITS) - 1)
    )
