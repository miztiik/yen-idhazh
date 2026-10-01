"""Move the eval ledger's files from the name `scores` to `summary-quality-evals`, and prove it.

Removal condition: delete on 2026-10-30, with the `scores` pin in
`migrate_to_parquet`, when GitHub's 30-day re-run window has closed on the last
run that could still file under the old names.

The eval ledger was `scores` and its ID folder `score-index`. Both are now named
for what they hold, and three folders move with whatever they hold when this
runs:

| From | To |
| --- | --- |
| `state/raw/scores/` | `state/raw/summary-quality-evals/` |
| `state/compact/scores/` | `state/compact/summary-quality-evals/` |
| `state/score-index/` | `state/summary-quality-evals-index/` |

    python backend/utilities/eval_ledger_rename.py --state-dir state [--check]

| Exit | Meaning |
| --- | --- |
| 0 | Every file moved and read back, or there was none. A second run writes nothing |
| 1 | Not proven, or `--check` found a file under an old name. No old file was deleted |

A run is not proven when a file will not read or read back, or when its new
address already holds other bytes.

**Every ledger file is rewritten, because no reader accepts the old name.** A
ledger file names its ledger in its envelope and in every row, and a day
listing, a compact index and a watermark name it too. Each is rewritten with
that name changed and nothing else (`ledger.render_renamed`): a ledger file
keeps every other envelope key, its `unit_id`, `file_id` and `written_at_ms`
among them, and every row keeps its identity cells, because a reader settles by
those cells. A compact index takes each file's new size. The ID files name no
ledger and move byte for byte, as does any other file the old folders hold.

**Nothing is deleted until everything is proven.** Four passes, each over every
file before the next starts: read every old file, write every new one, read
every new one back through this build's own readers, then delete the old ones.
The first read opens each container directly, because this build refuses the
old name. The read-back requires the same rows in the same order with every
cell equal but `ledger`; every envelope key equal but `ledger`,
`content_sha256` and `writer_version`; every listing, index and watermark equal
but its name and its sizes; the ledger's settled rows equal on every day an old
file served; and the dedupe's recorded measurements equal. A refusal in any
pass deletes no old file, a refusal in the first writes nothing, and a refusal
in the second or third gives a file rewritten where it lies its own bytes back.

**Running it again is safe, and is how a late file moves.** A new address that
already holds the same bytes is not written again, and one that holds other
bytes is refused before anything is written. A run that started before the
rename still files under the old names, and the next run of this moves what it
filed. With nothing left to move, a run writes nothing.

**A file git carried across is rewritten where it lies.** A merge or a rebase
that meets the rename moves a file added under an old folder into the new one,
and that file still names the old ledger, so no reader accepts it. Merge with
`git -c merge.directoryRenames=false` and it stays under the old name, where the
move above takes it. Merged any other way, it is found by its envelope or its
name field, rewritten in place under the new name, and never deleted.

**What it reads (Guardrail #12).** Every file under the old names, the envelope
of every ledger file under the new names and every listing, index and watermark
there, the ledger files under the new name for the days a moved file serves,
and the whole ID folder, which is what the dedupe reads on every run. It is run
by hand, and only until the removal date above.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from idhazh import atomic_write, day_shards, ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import FileEnvelope, Period, RowIdentity
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_index import CompactIndex, RawDayIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.evals import writer
from idhazh.ledger import json_lines, parquet

#: The names the ledger and its ID folder had, which no build declares now.
OLD_LEDGER: Final = "scores"
OLD_INDEX: Final = "score-index"

LEDGER: Final = LedgerName.SUMMARY_QUALITY_EVALS
INDEX: Final = LedgerName.SUMMARY_QUALITY_EVALS_INDEX

#: The envelope keys a rename changes: the name, the digest over the renamed
#: rows, and the engine that rendered them.
RENAMED_KEYS: Final = frozenset({b"ledger", b"content_sha256", b"writer_version"})

EXIT_MOVED: Final = 0
EXIT_NOT_PROVEN: Final = 1

type Rows = list[ledger.StoredRow[EvalRow]]
type Taker = Callable[[Path, tuple[str, ...]], None]


class NotProvenError(Exception):
    """A file would not read, did not read back, or would overwrite other bytes. Exit 1."""


@dataclass(frozen=True, slots=True)
class Refiled:
    """One raw or compact ledger file: what it held under the old name, and what it becomes."""

    old: Path
    metadata: dict[bytes, bytes]
    stored: list[dict[str, Any]]
    built: ledger.PeriodFile

    def renamed_cells(self) -> list[dict[str, Any]]:
        """Every row as the new file must hold it: the old cells, with the name changed."""
        return [{**cells, "ledger": LEDGER.value} for cells in self.stored]

    def renamed_envelope(self) -> FileEnvelope:
        """The old envelope with the name changed, which is what this build can read."""
        return FileEnvelope.from_metadata({**self.metadata, b"ledger": LEDGER.value.encode()})


@dataclass(frozen=True, slots=True)
class Move:
    """Any other file: where it sat, where it goes, and the bytes that go there."""

    old: Path
    new: Path
    data: bytes
    #: The listing, index or watermark it is now, or None for a file moved byte for byte.
    payload: Contract | None


@dataclass(frozen=True, slots=True)
class Opened:
    """One ledger file as a reader of the ledger meets it: its envelope and its rows."""

    envelope: FileEnvelope
    rows: Rows


@dataclass(slots=True)
class Plan:
    """Every old file, what each becomes, and what the ledger answered before the move."""

    refiled: list[Refiled] = field(default_factory=list)
    moves: list[Move] = field(default_factory=list)
    #: Every UTC day an old file serves rows for, oldest first, and their settled rows.
    days: list[str] = field(default_factory=list)
    settled: list[EvalRow] = field(default_factory=list)
    #: Every measurement the dedupe held.
    observations: set[str] = field(default_factory=set)
    #: The bytes of every file rewritten where it lies, put back if a later pass refuses.
    originals: dict[Path, bytes] = field(default_factory=dict)

    def targets(self) -> list[tuple[Path, Path, bytes]]:
        """Every old path, its new path, and the bytes that go there."""
        return [
            *((each.old, each.built.path, each.built.data) for each in self.refiled),
            *((each.old, each.new, each.data) for each in self.moves),
        ]


@dataclass(frozen=True, slots=True)
class Moved:
    """What one run did, in the numbers a reviewer asks for."""

    files: int = 0
    written: int = 0
    already: int = 0
    ledger_files: int = 0
    rows: int = 0
    days: int = 0
    settled_rows: int = 0
    observations: int = 0
    deleted: int = 0


def old_roots(state_dir: Path) -> tuple[Path, Path, Path]:
    """The three folders under their old names: raw rows, compact rows, and the IDs."""
    return (
        state_dir / ledger.paths.RAW_DIRNAME / OLD_LEDGER,
        state_dir / ledger.paths.COMPACT_DIRNAME / OLD_LEDGER,
        state_dir / OLD_INDEX,
    )


def _compact_root(state_dir: Path) -> Path:
    """`compact/<ledger>/` under the new name, found from the door's own address."""
    return ledger.compact_index_path(state_dir, LEDGER, Period.DAILY).parent.parent


def _files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file()) if root.is_dir() else []


def _names_the_old_ledger(path: Path, parts: tuple[str, ...]) -> bool:
    """Whether one file under a new folder still names the old ledger, read before any check."""
    try:
        if parts[0] == ledger.paths.INDEX_DIRNAME or parts[-1] == ledger.paths.WATERMARK_FILENAME:
            held = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(held, dict) and held.get("ledger") == OLD_LEDGER
        with path.open("rb") as handle:
            first = handle.readline() if handle.read(1) == json_lines.MAGIC else b""
        if first:
            envelope = json.loads(json_lines.MAGIC + first)
            return isinstance(envelope, dict) and envelope.get("ledger") == OLD_LEDGER
        return parquet.read_envelope(path).get(b"ledger") == OLD_LEDGER.encode()
    except ValueError:
        return False


def _strays(root: Path) -> list[Path]:
    """Every file under a new folder that still names the old ledger: one git carried there."""
    return [
        path for path in _files(root) if _names_the_old_ledger(path, path.relative_to(root).parts)
    ]


def _to_move(old: Path, new: Path) -> list[tuple[Path, Path]]:
    """Every file one folder has to move, beside the root its place is read from.

    The files under the old name, then the files under the new name that still
    name the old ledger, which are rewritten where they lie.
    """
    return [(old, path) for path in _files(old)] + [(new, path) for path in _strays(new)]


def left(state_dir: Path) -> list[Path]:
    """Every file still under an old name, or under a new one and still naming the old ledger."""
    raw, compact, ids = old_roots(state_dir)
    return [
        *(path for _, path in _to_move(raw, ledger.raw_root(state_dir, LEDGER))),
        *(path for _, path in _to_move(compact, _compact_root(state_dir))),
        *_files(ids),
    ]


def _shown(state_dir: Path, path: Path) -> str:
    """A path as it may leave the process: under `state/`, POSIX (CLAUDE.md section 2)."""
    return f"{ledger.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}"


def _container(data: bytes) -> tuple[dict[bytes, bytes], list[dict[str, Any]]]:
    """A ledger file's envelope and rows as its container holds them, before any check."""
    if data.startswith(b"PAR1"):
        return parquet.read(data)
    if data.startswith(json_lines.MAGIC):
        return json_lines.read(data)
    raise ValueError("it is neither a parquet nor a JSON-lines ledger file")


def _stored_row(cells: dict[str, Any]) -> ledger.StoredRow[EvalRow]:
    """One row as the door reads it: its identity cells beside the contract's own."""
    identity = {name: cells.get(name) for name in RowIdentity.model_fields}
    added = set(identity) - set(EvalRow.model_fields)
    own = {key: value for key, value in cells.items() if key not in added}
    return ledger.StoredRow(
        identity=RowIdentity.model_validate(identity), row=EvalRow.model_validate(own)
    )


def _refiled(state_dir: Path, path: Path, naive: Path) -> Refiled:
    """One old ledger file, read by its container and built again under the new name."""
    metadata, stored = _container(path.read_bytes())
    names = sorted({str(cells.get("ledger")) for cells in stored} - {OLD_LEDGER})
    if metadata.get(b"ledger") != OLD_LEDGER.encode() or names:
        raise ValueError(f"it names {metadata.get(b'ledger')!r}, and its rows name {names}")
    digest = hashlib.sha256(json_lines.rows_bytes(stored)).hexdigest()
    if metadata.get(b"content_sha256") != digest.encode():
        raise ValueError("its envelope's digest is not the digest of the rows it holds")
    built = ledger.render_renamed(state_dir, metadata, stored, model=EvalRow, ledger=LEDGER)
    if built.path != naive:
        raise ValueError(f"the door files it at {_shown(state_dir, built.path)}")
    return Refiled(old=path, metadata=metadata, stored=stored, built=built)


def _renamed[C: Contract](path: Path, contract: type[C]) -> C:
    """A listing, index or watermark with its ledger renamed, checked by its own contract."""
    held = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(held, dict) or held.get("ledger") != OLD_LEDGER:
        raise ValueError(f"it does not name the {OLD_LEDGER} ledger")
    return contract.model_validate(held | {"ledger": LEDGER.value})


def _named(old: Path, new: Path, payload: Contract) -> Move:
    return Move(old=old, new=new, data=payload.to_json().encode("ascii"), payload=payload)


def _copied(old: Path, new: Path) -> Move:
    return Move(old=old, new=new, data=old.read_bytes(), payload=None)


def _each_file(state_dir: Path, held: list[tuple[Path, Path]], take: Taker) -> None:
    """Hand every file to `take` with its place below its root; a refusal names the file."""
    for root, path in held:
        try:
            take(path, path.relative_to(root).parts)
        except ValueError as refusal:
            raise NotProvenError(f"{_shown(state_dir, path)}: {refusal}") from refusal


def _plan_raw(state_dir: Path, plan: Plan) -> None:
    """The raw folder: day files refiled, day listings renamed, anything else copied."""
    new_root = ledger.raw_root(state_dir, LEDGER)

    def take(path: Path, parts: tuple[str, ...]) -> None:
        if parts[0] == ledger.paths.INDEX_DIRNAME and len(parts) == 2:
            new = ledger.raw_index_path(state_dir, LEDGER, path.stem)
            plan.moves.append(_named(path, new, _renamed(path, RawDayIndex)))
        elif len(parts) == 4:
            plan.refiled.append(_refiled(state_dir, path, new_root.joinpath(*parts)))
        else:
            plan.moves.append(_copied(path, new_root.joinpath(*parts)))

    _each_file(state_dir, _to_move(old_roots(state_dir)[0], new_root), take)


def _plan_compact(state_dir: Path, plan: Plan) -> None:
    """The compact folder: period files refiled, watermarks and indexes renamed, the rest copied.

    An index is renamed last, because it takes the size of each file it names,
    and a size is known once that file is built.
    """
    new_root = _compact_root(state_dir)
    periods = {period.value: period for period in Period}
    indexes: list[tuple[Path, Period]] = []

    def take(path: Path, parts: tuple[str, ...]) -> None:
        if parts[0] == ledger.paths.INDEX_DIRNAME and len(parts) == 2 and path.stem in periods:
            indexes.append((path, periods[path.stem]))
        elif parts[0] in periods and parts[1:] == (ledger.paths.WATERMARK_FILENAME,):
            new = ledger.watermark_path(state_dir, LEDGER, periods[parts[0]])
            plan.moves.append(_named(path, new, _renamed(path, Watermark)))
        elif parts[0] in periods:
            plan.refiled.append(_refiled(state_dir, path, new_root.joinpath(*parts)))
        else:
            plan.moves.append(_copied(path, new_root.joinpath(*parts)))

    _each_file(state_dir, _to_move(old_roots(state_dir)[1], new_root), take)
    for path, period in indexes:
        try:
            new = ledger.compact_index_path(state_dir, LEDGER, period)
            plan.moves.append(_named(path, new, _resized(path, period, plan)))
        except ValueError as refusal:
            raise NotProvenError(f"{_shown(state_dir, path)}: {refusal}") from refusal


def _resized(path: Path, period: Period, plan: Plan) -> CompactIndex:
    """A compact index renamed, each entry carrying the size of the file it names now."""
    index = _renamed(path, CompactIndex)
    built = {
        (each.metadata.get(b"period"), each.metadata.get(b"covers")): each.built
        for each in plan.refiled
    }
    entries = []
    for entry in index.entries:
        found = built.get((period.value.encode(), entry.covers.encode()))
        if found is None or found.rows != entry.rows:
            held = "no file" if found is None else f"a file of {found.rows} rows"
            raise ValueError(f"it names {entry.rows} rows for {entry.covers}, and finds {held}")
        entries.append(entry.model_copy(update={"bytes": len(found.data)}))
    return index.model_copy(update={"entries": entries})


def _serves(envelope: FileEnvelope, days: set[str]) -> bool:
    """Whether a ledger file covers any of these UTC days."""
    return any(day == envelope.covers or day.startswith(f"{envelope.covers}-") for day in days)


def _opened(state_dir: Path, plan: Plan) -> tuple[list[Opened], list[str]]:
    """Every ledger file a reader met before the move on the days an old file serves.

    The old files as the first pass read them, renamed, and any file already
    under the new name for those days - one a run filed after the rename
    merged, read by this build's own reader. A day is one a row of an old file
    was first filed under, or the day an old raw or daily file covers.
    """
    old = [
        Opened(each.renamed_envelope(), [_stored_row(cells) for cells in each.renamed_cells()])
        for each in plan.refiled
    ]
    days = {held.identity.covers for opened in old for held in opened.rows}
    days |= {
        opened.envelope.covers
        for opened in old
        if opened.envelope.period in (None, Period.DAILY)
    }
    planned = {each.built.path for each in plan.refiled}
    found: list[Opened] = []
    for root in (ledger.raw_root(state_dir, LEDGER), _compact_root(state_dir)):
        for path in _files(root):
            parts = path.relative_to(root).parts
            if (
                path in planned
                or parts[0] == ledger.paths.INDEX_DIRNAME
                or parts[-1] == ledger.paths.WATERMARK_FILENAME
            ):
                continue
            envelope = ledger.read_envelope(path)
            if _serves(envelope, days):
                found.append(Opened(envelope, ledger.load_stored([path], model=EvalRow)))
    return old + found, sorted(days)


def _indexed(state_dir: Path, plan: Plan) -> dict[Period, set[str]]:
    """What each period's index named before the move: the old one renamed, else the new one."""
    named: dict[Period, set[str]] = {}
    for each in plan.moves:
        if isinstance(each.payload, CompactIndex):
            named[each.payload.period] = {entry.covers for entry in each.payload.entries}
    for period in Period:
        path = ledger.compact_index_path(state_dir, LEDGER, period)
        if period not in named and path.is_file():
            named[period] = {entry.covers for entry in CompactIndex.read(path).entries}
    return named


def _period_rows(opened: list[Opened], period: Period, covers: str) -> Rows:
    """The rows of the one compact file of a period, or none when it is not there."""
    return [
        held
        for each in opened
        if (each.envelope.period, each.envelope.covers) == (period, covers)
        for held in each.rows
    ]


def _served(day: str, indexed: dict[Period, set[str]], opened: list[Opened]) -> list[Rows]:
    """The files one day is read from, by the door's own rule, in the order it settles them.

    A day of a year or month an index names is read from that period's file,
    which serves only the rows first filed under the day. A day the daily index
    names is read from its whole file. Any other day is read from its raw
    files, oldest first.
    """
    for period, covers in ((Period.YEARLY, day[:4]), (Period.MONTHLY, day[:7])):
        if covers in indexed.get(period, set()):
            coarse = _period_rows(opened, period, covers)
            return [[held for held in coarse if held.identity.covers == day]]
    if day in indexed.get(Period.DAILY, set()):
        return [_period_rows(opened, Period.DAILY, day)]
    raw = [each for each in opened if each.envelope.period is None and each.envelope.covers == day]
    raw.sort(key=lambda each: (each.envelope.written_at_ms, str(each.envelope.file_id)))
    return [each.rows for each in raw]


def _settle(state_dir: Path, plan: Plan) -> None:
    """Each day an old file serves, settled as the ledger served it before the move."""
    opened, plan.days = _opened(state_dir, plan)
    indexed = _indexed(state_dir, plan)
    key = ledger.door_key(LEDGER)
    for day in plan.days:
        served = _served(day, indexed, opened)
        plan.settled.extend(held.row for held in ledger.settle_rows(served, key))


def _observations(root: Path) -> set[str]:
    """Every measurement one ID folder holds, read as the dedupe reads it."""
    held: set[str] = set()
    for path in day_shards.shard_files(root, days=UNBOUNDED_WINDOW) if root.is_dir() else []:
        ledger.require_matching_header(path, writer.index_columns())
        with path.open("r", encoding="utf-8", newline="") as handle:
            held.update(record["observation_digest"] for record in csv.DictReader(handle))
    return held


def plan_move(state_dir: Path) -> Plan:
    """Pass one: every old file read and built again in memory, and the ledger's answers taken.

    Nothing is written. Raises `NotProvenError` naming the first file that will
    not read, or a new address that already holds other bytes.
    """
    plan = Plan()
    _plan_raw(state_dir, plan)
    _plan_compact(state_dir, plan)
    old_index = old_roots(state_dir)[2]
    new_index = ledger.tree_root(state_dir, INDEX)
    for path in _files(old_index):
        plan.moves.append(_copied(path, new_index / path.relative_to(old_index)))
    try:
        _settle(state_dir, plan)
        plan.observations = _observations(old_index) | _observations(new_index)
    except ValueError as refusal:
        raise NotProvenError(f"the ledger before the move would not read: {refusal}") from refusal
    for old, new, data in plan.targets():
        if old == new:
            plan.originals[old] = old.read_bytes()
        elif new.is_file() and new.read_bytes() != data:
            raise NotProvenError(
                f"{_shown(state_dir, new)} already holds other bytes than "
                f"{_shown(state_dir, old)} becomes"
            )
    return plan


def write(plan: Plan) -> tuple[int, int]:
    """Pass two: every new file written whole, except one that already holds its bytes."""
    written = already = 0
    for _, new, data in plan.targets():
        if new.is_file() and new.read_bytes() == data:
            already += 1
            continue
        atomic_write.write_atomic_bytes(new, data)
        written += 1
    return written, already


def _unequal(state_dir: Path, path: Path, what: str) -> NotProvenError:
    return NotProvenError(f"{_shown(state_dir, path)} does not read back: {what}")


def _prove_refiled(state_dir: Path, each: Refiled) -> None:
    """One new ledger file holds the old rows and envelope, the name changed and nothing else."""
    path = each.built.path
    metadata, stored = _container(path.read_bytes())
    wanted = each.renamed_cells()
    if stored != wanted:
        pairs = zip(stored, wanted, strict=False)
        first = next((n for n, (got, cells) in enumerate(pairs) if got != cells), len(wanted))
        raise _unequal(state_dir, path, f"row {first} of {len(wanted)} differs")
    now = {key: value for key, value in metadata.items() if key not in RENAMED_KEYS}
    was = {key: value for key, value in each.metadata.items() if key not in RENAMED_KEYS}
    moved = sorted(key.decode() for key in now.keys() | was.keys() if now.get(key) != was.get(key))
    if moved or metadata.get(b"ledger") != LEDGER.value.encode():
        raise _unequal(state_dir, path, f"its envelope changed {moved or ['ledger']}")
    if len(ledger.load_stored([path], model=EvalRow)) != len(wanted):
        raise _unequal(state_dir, path, "this build reads another number of rows")


def prove(state_dir: Path, plan: Plan) -> None:
    """Pass three: every new file read back through this build, then the ledger's answers."""
    try:
        for each in plan.refiled:
            _prove_refiled(state_dir, each)
        for move in plan.moves:
            if move.payload is not None and type(move.payload).read(move.new) != move.payload:
                raise _unequal(state_dir, move.new, "its payload differs")
            if move.payload is None and move.new.read_bytes() != move.data:
                raise _unequal(state_dir, move.new, "its bytes differ")
        after = ledger.load_days(state_dir, LEDGER, plan.days, model=EvalRow)
        recorded = writer.recorded_observations(state_dir)
    except ValueError as refusal:
        raise NotProvenError(f"a new file would not read: {refusal}") from refusal
    if after != plan.settled:
        raise NotProvenError(
            f"the ledger settles {len(after)} rows over {len(plan.days)} days after the move, "
            f"and {len(plan.settled)} before, or not the same rows"
        )
    if recorded != plan.observations:
        raise NotProvenError(
            f"the dedupe holds {len(recorded)} measurements after the move, and "
            f"{len(plan.observations)} before, or not the same ones"
        )


def delete(state_dir: Path, plan: Plan) -> int:
    """Pass four: every old file this run read is deleted, then every folder it emptied.

    A file rewritten where it lay is the new file, so it stays.
    """
    moved = [old for old, new, _ in plan.targets() if old != new]
    for old in moved:
        old.unlink()
    for root in old_roots(state_dir):
        if not root.is_dir():
            continue
        for folder in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()
        if not any(root.iterdir()):
            root.rmdir()
    return len(moved)


def restore(plan: Plan) -> None:
    """Every file rewritten where it lies gets its own bytes back."""
    for path, data in plan.originals.items():
        atomic_write.write_atomic_bytes(path, data)


def move(state_dir: Path) -> Moved:
    """The four passes, each over every file before the next. Raises `NotProvenError`.

    A refusal in the second or third pass puts back every file rewritten where
    it lies, so nothing a run read is lost.
    """
    if not left(state_dir):
        return Moved()
    plan = plan_move(state_dir)
    try:
        written, already = write(plan)
        prove(state_dir, plan)
    except BaseException:
        restore(plan)
        raise
    return Moved(
        files=len(plan.targets()),
        written=written,
        already=already,
        ledger_files=len(plan.refiled),
        rows=sum(each.built.rows for each in plan.refiled),
        days=len(plan.days),
        settled_rows=len(plan.settled),
        observations=len(plan.observations),
        deleted=delete(state_dir, plan),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--state-dir", required=True, type=Path, help="The tree to move.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Write nothing. Exit 1 if any file is still under an old name.",
    )
    args = parser.parse_args(argv)
    state_dir: Path = args.state_dir
    if not state_dir.is_dir():
        print(f"{state_dir.as_posix()} is not a folder, so nothing was moved", file=sys.stderr)
        return EXIT_NOT_PROVEN
    if args.check:
        remaining = left(state_dir)
        for path in remaining:
            print(f"{_shown(state_dir, path)} is still under or names an old name")
        print(f"{len(remaining)} file(s) left under or naming an old name")
        return EXIT_NOT_PROVEN if remaining else EXIT_MOVED
    try:
        moved = move(state_dir)
    except NotProvenError as refusal:
        print(f"not proven, nothing deleted: {refusal}", file=sys.stderr)
        return EXIT_NOT_PROVEN
    print(
        f"{moved.files} file(s) moved or rewritten: {moved.written} written, "
        f"{moved.already} already in place, {moved.deleted} old file(s) deleted"
    )
    print(
        f"{moved.ledger_files} ledger file(s) holding {moved.rows} row(s), every cell equal "
        "but the ledger's name"
    )
    print(
        f"{moved.settled_rows} settled row(s) over {moved.days} day(s), and "
        f"{moved.observations} recorded measurement(s), equal before and after"
    )
    return EXIT_MOVED


if __name__ == "__main__":
    raise SystemExit(main())
