"""The one door a contract payload takes to disk under `state/raw/` or `state/compact/`, and back.

A producer hands the door its rows, the ledger, the period and its writer
identity. The door mints the two identifiers, builds the path, assembles the
envelope, renders the file and writes it whole. A producer never builds a path,
never invents a filename and never assembles an envelope, which is what makes
the next ledger's migration a change of call site rather than a change of
design. `identity.producer` is the one field a call site must get right: it is
what keeps two producers of one ledger apart inside `unit_id`.

**One write a tier.** `persist` files new rows under `state/raw/` and stamps
each with the writer's identity. `persist_period` files one compact period
under `state/compact/` from rows that already carry the identity their raw file
gave them, and keeps it: a compact file says which writer first filed each row,
never that the compaction did, so a re-run's second attempt can still replace
its first after the day was compacted. `render_period` builds that same file and
writes nothing, for a pass that only reports. `render_grouped_period` builds one
from groups of rows held one group at a time, each group its own row group, for
a period too big to hold whole - a year, built one month at a time.
`render_renamed` builds a file that already exists again under another ledger's
name and changes nothing else, for a ledger whose name moves.

Two formats behind one door: parquet, and JSON lines a person can read in a
pull request. `ledger/parquet.py` is the only module that imports the engine, and
it is imported inside the functions that need it, so importing the ledger never
loads pyarrow. The write is `atomic_write.write_atomic_bytes` and nothing else,
so a half-written file is never visible under its own name.

`load` is the inverse of `persist` and nothing else, and `load_stored` is the
same read with each row's identity cells kept beside it. Neither removes
duplicates: a union over several attempts at one work unit keeps the highest
`attempt` per `unit_id`, and that settlement is a reader's job, not the door's.

Every instant here is UTC (CLAUDE.md section 2).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError

from idhazh import atomic_write, config
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.base import MAINTENANCE_JOBS, Contract, PeriodStamp
from idhazh.contracts.file_envelope import (
    Compression,
    FileEnvelope,
    Format,
    Period,
    RowIdentity,
    Tier,
    WriterIdentity,
    covers_fits,
)
from idhazh.contracts.knobs.ledger import LedgerConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import arrow_schema, filenames, json_lines, lifecycle, paths
from idhazh.ledger.arrow_schema import Column
from idhazh.ledger.keys import DATE_CELL
from idhazh.ledger.paths import compact_path, raw_path

#: The committed config file the `ledger` block is read from.
_APP_CONFIG_FILENAME: Final = "idhazh.json"

#: What every parquet file opens with. How the door tells the two containers
#: apart without trusting a suffix: a format literal, fixed by the parquet spec.
_PARQUET_MAGIC: Final = b"PAR1"

#: The envelope keys that are also a column on every row, declared once by
#: `RowIdentity`: a union keeps the highest `attempt` per `unit_id`, and a bad
#: run is traced by filtering on `run_id`. A contract field of the same name is
#: the column instead, so a row's own value is never overwritten; the envelope
#: still carries the writer's.
_IDENTITY_COLUMNS: Final[tuple[Column, ...]] = arrow_schema.columns_of(RowIdentity)

#: The identity cells a row's own contract may not contradict, because the
#: union ranks and groups on them: a row carrying another try than its writer's
#: would be kept or dropped for a try that never wrote it.
_RANKED_CELLS: Final = ("attempt", "unit_id")


@dataclass(frozen=True, slots=True)
class StoredRow[C: Contract]:
    """One row as a ledger file holds it: the identity cells beside the contract's own."""

    identity: RowIdentity
    row: C


@dataclass(frozen=True, slots=True)
class PeriodFile:
    """One ledger file, built: where it goes, every byte of it, and its rows."""

    path: Path
    data: bytes
    #: How many rows the file holds.
    rows: int


@dataclass(frozen=True, slots=True)
class FileFooter:
    """What one ledger file says of itself with no row read: its envelope and its row count."""

    envelope: FileEnvelope
    #: How many rows the file holds.
    rows: int


@cache
def _knobs() -> LedgerConfig:
    """The committed `ledger` block: the default format and the two compressions."""
    text = (config.DEFAULT_CONFIG_DIR / _APP_CONFIG_FILENAME).read_text(encoding="utf-8")
    return AppConfig.from_json(text).ledger


def _refuse_a_period_the_tier_cannot_take(
    covers: str, *, tier: Tier, period: Period | None
) -> None:
    """`covers` is a day for a raw or daily file, else the month or year its period covers."""
    if not covers_fits(covers, tier=tier, period=period):
        raise ValueError(
            f"covers {covers!r} is not the shape a {tier.value} "
            f"{period.value + ' ' if period else ''}file covers: a raw or daily file "
            "covers YYYY-MM-DD, a monthly file covers YYYY-MM and a yearly file covers YYYY"
        )


def _one_contract(rows: Sequence[Contract]) -> type[Contract]:
    """The contract every row is, or a refusal: one file holds rows of one shape."""
    model = type(rows[0])
    strays = sorted({type(row).__name__ for row in rows if type(row) is not model})
    if strays:
        raise TypeError(f"one file holds rows of one contract, and {model.__name__} met {strays}")
    return model


def _by_day(
    rows: Sequence[Contract], *, model: type[Contract], covers: str
) -> dict[str, list[Contract]]:
    """Each row under the day it belongs to.

    A row is filed under the day its own `date` cell names, so rows a run left
    behind three days ago land under that day rather than under today, and a
    call holding three days writes three files. A contract with no date cell
    files under `covers`.
    """
    dated = DATE_CELL in model.model_fields
    grouped: dict[str, list[Contract]] = {}
    for row in rows:
        grouped.setdefault(getattr(row, DATE_CELL) if dated else covers, []).append(row)
    return grouped


def _compression(fmt: Format, tier: Tier, knobs: LedgerConfig) -> Compression:
    """What the rows are compressed with: JSON lines are plain text, parquet follows its tier."""
    if fmt is Format.JSON:
        return Compression.NONE
    return knobs.compression_raw if tier is Tier.RAW else knobs.compression_compact


def _columns(model: type[Contract]) -> tuple[Column, ...]:
    """The contract's own columns, then every identity column it does not declare itself."""
    own = arrow_schema.columns_of(model)
    return own + tuple(
        column for column in _IDENTITY_COLUMNS if column.name not in model.model_fields
    )


def _unit(ledger: LedgerName, covers: str, identity: WriterIdentity) -> uuid.UUID:
    """The work unit one writer's file for one period records."""
    return filenames.unit_id(
        ledger=ledger,
        covers=covers,
        run_id=identity.run_id,
        job=identity.job,
        shard=identity.shard,
        producer=identity.producer,
    )


def _envelope(
    *,
    model: type[Contract],
    ledger: LedgerName,
    covers: str,
    identity: WriterIdentity,
    tier: Tier,
    period: Period | None,
    built_from: int | None,
    fmt: Format,
    compression: Compression,
    written_at_ms: int,
    content_sha256: str,
) -> tuple[uuid.UUID, dict[bytes, bytes]]:
    """One file's envelope as the bytes it is kept as, beside the `file_id` minted for it.

    The `file_id` comes back because a raw file is named by it and a compact one
    by its period.
    """
    unit = _unit(ledger, covers, identity)
    name = filenames.file_id(unit=unit, attempt=identity.attempt, written_at_ms=written_at_ms)
    if fmt is Format.PARQUET:
        from idhazh.ledger import parquet

        writer, engine = parquet.__name__, parquet.engine_version()
    else:
        writer, engine = json_lines.__name__, json_lines.engine_version()
    envelope = FileEnvelope(
        version=FileEnvelope.schema_version(),
        row_schema_version=model.schema_version(),
        tier=tier,
        ledger=ledger,
        covers=covers,
        period=period,
        written_at_ms=written_at_ms,
        identity=identity,
        unit_id=unit,
        file_id=name,
        content_sha256=content_sha256,
        writer=writer,
        writer_version=engine,
        compression=compression,
        built_from=built_from,
    ).as_metadata()
    return name, envelope


def _rendered(
    stored: Sequence[Mapping[str, Any]],
    *,
    model: type[Contract],
    ledger: LedgerName,
    covers: str,
    identity: WriterIdentity,
    tier: Tier,
    period: Period | None,
    built_from: int | None,
    fmt: Format,
    compression: Compression,
    written_at_ms: int,
) -> tuple[uuid.UUID, bytes]:
    """One file's bytes: identifiers minted, envelope assembled, rows rendered.

    Returns the minted `file_id` beside the bytes, because a raw file is named
    by it and a compact one is named by its period.
    """
    name, envelope = _envelope(
        model=model,
        ledger=ledger,
        covers=covers,
        identity=identity,
        tier=tier,
        period=period,
        built_from=built_from,
        fmt=fmt,
        compression=compression,
        written_at_ms=written_at_ms,
        content_sha256=hashlib.sha256(json_lines.rows_bytes(stored)).hexdigest(),
    )
    if fmt is Format.PARQUET:
        from idhazh.ledger import parquet

        return name, parquet.render(
            _columns(model), stored, envelope=envelope, compression=compression
        )
    return name, json_lines.render(stored, envelope=envelope)


def _refuse_a_row_that_names_another_try(
    stamped: Mapping[str, Any], own: Sequence[Mapping[str, Any]], *, where: str
) -> None:
    """A row's own `attempt` or `unit_id` is its writer's, or none at all.

    A union keeps the highest attempt per unit, so a row naming another try
    would be kept or dropped for a try that never wrote it.
    """
    for cells in own:
        for cell in _RANKED_CELLS:
            if cell in cells and cells[cell] != stamped[cell]:
                raise ValueError(
                    f"{where}: a row names {cell} {cells[cell]!r} and its writer is "
                    f"{stamped[cell]!r}. A row may not name another try than the one "
                    "that files it"
                )


def _refuse_an_identity_no_reader_could_read(
    stored: Sequence[Mapping[str, Any]], *, where: str
) -> None:
    """Every row's identity cells read back as a `RowIdentity`, checked before the write.

    A contract field that shares a name with an identity cell is the column, so
    a row can carry a value there the reader refuses - an empty `job`, say. A
    file written with such a row would be refused whole by `load_stored`, and
    once its source is gone that is lost data, so it is refused here instead.
    """
    for cells in stored:
        try:
            RowIdentity.model_validate(
                {column.name: cells.get(column.name) for column in _IDENTITY_COLUMNS}
            )
        except ValidationError as refusal:
            raise ValueError(
                f"{where}: a row's identity cells would not read back, so nothing is "
                f"written: {refusal}"
            ) from refusal


def persist(
    state_dir: Path,
    rows: Sequence[Contract],
    *,
    ledger: LedgerName,
    covers: PeriodStamp,
    identity: WriterIdentity,
    fmt: Format | None = None,
    registry: paths.DoorRegistry | None = None,
) -> list[Path]:
    """File these new rows under `state/raw/` and return where they went, one path per day.

    `state_dir` is the state root the caller writes under - `common.STATE_ROOT`
    for a stage, which a trial run and the test suite both redirect. `covers` is
    the day a row with no date cell of its own is filed under; a row that has one
    is filed under the day it names. `fmt` of `None` means `config/idhazh.json`'s
    `ledger.format`, and nothing else.

    A write into a paused or retired family from a pipeline job writes nothing
    and returns an empty list, with one warning. A write from a job in
    `MAINTENANCE_JOBS` is never skipped: it files rows again that were already
    recorded.

    Every file is built before the first is written, so a row refused on its
    third day leaves no file for the first two. The paths come back ascending by
    the day each file covers, never by path string.
    """
    _refuse_a_period_the_tier_cannot_take(covers, tier=Tier.RAW, period=None)
    if not rows:
        return []
    model = _one_contract(rows)
    if identity.job not in MAINTENANCE_JOBS and not lifecycle.accepts_new_rows(ledger, len(rows)):
        return []
    knobs = _knobs()
    chosen = knobs.format if fmt is None else fmt
    compression = _compression(chosen, Tier.RAW, knobs)
    written_at_ms = int(datetime.now(UTC).timestamp() * 1000)
    built: list[tuple[Path, bytes]] = []
    for day, batch in sorted(_by_day(rows, model=model, covers=covers).items()):
        stamped = {
            "ledger": ledger.value,
            "covers": day,
            "run_id": identity.run_id,
            "attempt": identity.attempt,
            "job": identity.job.value,
            "shard": identity.shard,
            "unit_id": str(_unit(ledger, day, identity)),
        }
        own = [row.model_dump(mode="json") for row in batch]
        _refuse_a_row_that_names_another_try(stamped, own, where=f"{ledger.value} {day}")
        stored = [stamped | cells for cells in own]
        _refuse_an_identity_no_reader_could_read(stored, where=f"{ledger.value} {day}")
        name, data = _rendered(
            stored,
            model=model,
            ledger=ledger,
            covers=day,
            identity=identity,
            tier=Tier.RAW,
            period=None,
            built_from=None,
            fmt=chosen,
            compression=compression,
            written_at_ms=written_at_ms,
        )
        built.append((raw_path(state_dir, ledger, day, name, fmt=chosen, registry=registry), data))
    for target, data in built:
        atomic_write.write_atomic_bytes(target, data)
    return [target for target, _ in built]


def _inside(day: str, covers: str) -> bool:
    """Whether a raw day falls inside a compact period: the day, or a day of its month or year."""
    return day == covers or day.startswith(f"{covers}-")


def _refuse_rows_outside_the_period[C: Contract](
    rows: Sequence[StoredRow[C]], *, model: type[C], ledger: LedgerName, covers: str
) -> None:
    """Every row is one `model` row, filed into this ledger inside this period, or none is kept.

    A compact file replaces its whole period, so a row filed anywhere else is
    refused rather than allowed to overwrite a finished period with a stranger's.
    """
    strays = sorted({type(held.row).__name__ for held in rows if type(held.row) is not model})
    if strays:
        raise TypeError(f"one file holds rows of one contract, and {model.__name__} met {strays}")
    outside = sorted(
        {
            f"{held.identity.ledger.value} {held.identity.covers}"
            for held in rows
            if held.identity.ledger is not ledger or not _inside(held.identity.covers, covers)
        }
    )
    if outside:
        raise ValueError(
            f"a compact {ledger.value} file covering {covers} was handed rows filed under "
            f"{outside}. A compact write replaces the whole period, so every row must have "
            "been filed inside it"
        )


def _stored[C: Contract](rows: Sequence[StoredRow[C]]) -> list[dict[str, Any]]:
    """Each row as the cells a file holds: its identity cells, then its contract's own."""
    return [
        held.identity.model_dump(mode="json") | held.row.model_dump(mode="json") for held in rows
    ]


def render_period[C: Contract](
    state_dir: Path,
    rows: Sequence[StoredRow[C]],
    *,
    model: type[C],
    ledger: LedgerName,
    period: Period,
    covers: PeriodStamp,
    identity: WriterIdentity,
    built_from: int,
    fmt: Format | None = None,
    registry: paths.DoorRegistry | None = None,
) -> PeriodFile:
    """One compact period's file, built in memory and written nowhere.

    `rows` keep the identity their raw file gave them, and the file keeps it
    too; `identity` is the compaction's own, and it goes in the envelope, which
    says who wrote this file. `model` is passed rather than read off a row, so a
    period that held nothing still becomes a file with every column. A compact
    file replaces its whole period, so every row must have been filed inside
    it, into this ledger - one that was not is refused rather than allowed to
    overwrite a finished period with a stranger's row.
    """
    _refuse_a_period_the_tier_cannot_take(covers, tier=Tier.COMPACT, period=period)
    _refuse_rows_outside_the_period(rows, model=model, ledger=ledger, covers=covers)
    knobs = _knobs()
    chosen = knobs.format if fmt is None else fmt
    compression = _compression(chosen, Tier.COMPACT, knobs)
    _, data = _rendered(
        _stored(rows),
        model=model,
        ledger=ledger,
        covers=covers,
        identity=identity,
        tier=Tier.COMPACT,
        period=period,
        built_from=built_from,
        fmt=chosen,
        compression=compression,
        written_at_ms=int(datetime.now(UTC).timestamp() * 1000),
    )
    path = compact_path(state_dir, ledger, period, covers, fmt=chosen, registry=registry)
    return PeriodFile(path, data, len(rows))


def render_grouped_period[C: Contract](
    state_dir: Path,
    groups: Iterable[Sequence[StoredRow[C]]],
    *,
    model: type[C],
    ledger: LedgerName,
    period: Period,
    covers: PeriodStamp,
    identity: WriterIdentity,
    built_from: int,
    fmt: Format | None = None,
    registry: paths.DoorRegistry | None = None,
) -> PeriodFile:
    """One compact period's file built one group of rows at a time, and written nowhere.

    The rows, envelope and digest `render_period` would give for every group's
    rows in order, refused the same way. In parquet each group that holds a row
    is one row group, so its statistics bound that group alone and a reader
    filtering on a date can skip the rest; and only one group is held at a time,
    so a year is built one month at a time. JSON lines has no row groups and is
    built whole.
    """
    _refuse_a_period_the_tier_cannot_take(covers, tier=Tier.COMPACT, period=period)
    knobs = _knobs()
    chosen = knobs.format if fmt is None else fmt
    compression = _compression(chosen, Tier.COMPACT, knobs)
    written_at_ms = int(datetime.now(UTC).timestamp() * 1000)
    digest = hashlib.sha256()
    counted = 0

    def checked() -> Iterator[list[dict[str, Any]]]:
        nonlocal counted
        for group in groups:
            _refuse_rows_outside_the_period(group, model=model, ledger=ledger, covers=covers)
            stored = _stored(group)
            digest.update(json_lines.rows_bytes(stored))
            counted += len(stored)
            yield stored

    def envelope() -> dict[bytes, bytes]:
        return _envelope(
            model=model,
            ledger=ledger,
            covers=covers,
            identity=identity,
            tier=Tier.COMPACT,
            period=period,
            built_from=built_from,
            fmt=chosen,
            compression=compression,
            written_at_ms=written_at_ms,
            content_sha256=digest.hexdigest(),
        )[1]

    if chosen is Format.PARQUET:
        from idhazh.ledger import parquet

        data = parquet.render_groups(
            _columns(model), checked(), envelope=envelope, compression=compression
        )
    else:
        whole = [cells for stored in checked() for cells in stored]
        data = json_lines.render(whole, envelope=envelope())
    path = compact_path(state_dir, ledger, period, covers, fmt=chosen, registry=registry)
    return PeriodFile(path, data, counted)


def persist_period[C: Contract](
    state_dir: Path,
    rows: Sequence[StoredRow[C]],
    *,
    model: type[C],
    ledger: LedgerName,
    period: Period,
    covers: PeriodStamp,
    identity: WriterIdentity,
    built_from: int,
    fmt: Format | None = None,
    registry: paths.DoorRegistry | None = None,
) -> Path:
    """Write one compact period's file whole, and return where it went.

    `render_period`, then one atomic write. Never skipped for a paused family:
    it files rows again that were already recorded, and skipping it after its
    sources were deleted would lose them while the run reported success.
    """
    built = render_period(
        state_dir,
        rows,
        model=model,
        ledger=ledger,
        period=period,
        covers=covers,
        identity=identity,
        built_from=built_from,
        fmt=fmt,
        registry=registry,
    )
    atomic_write.write_atomic_bytes(built.path, built.data)
    return built.path


def render_renamed[C: Contract](
    state_dir: Path,
    metadata: Mapping[bytes, bytes],
    stored: Sequence[Mapping[str, Any]],
    *,
    model: type[C],
    ledger: LedgerName,
    registry: paths.DoorRegistry | None = None,
) -> PeriodFile:
    """One ledger file built again under another ledger's name, and written nowhere.

    `metadata` and `stored` are the file's envelope and rows as its container
    holds them, taken before any check, because a build refuses a name it no
    longer declares. Only the name changes, in the envelope and in every row.
    Every other envelope key keeps its bytes - `unit_id`, `file_id`,
    `written_at_ms`, the writer's identity, both version stamps, the
    compression - and every row keeps its identity cells and its columns,
    because a reader settles by those cells and a compact row carries no
    producer to mint them from again. `content_sha256` is taken over the renamed
    rows, and `writer_version` names the engine that rendered them.

    Everything is checked before a byte is built - the envelope, every row's
    identity cells, every row as `model` - so a file this build could not read
    back is refused rather than rewritten. So is a column `model` does not
    declare, because the container would drop it in silence.
    """
    renamed = {**metadata, b"ledger": ledger.value.encode("utf-8")}
    envelope = FileEnvelope.from_metadata(renamed)
    where = f"{ledger.value} {envelope.covers}"
    if envelope.row_schema_version > model.schema_version():
        raise ValueError(
            f"{where}: rows written under {model.__name__} {envelope.row_schema_version}, and "
            f"this build reads {model.schema_version()}. Rename it with a build at least as new"
        )
    known = {column.name: column for column in _columns(model)}
    cells = [{**row, "ledger": ledger.value} for row in stored]
    held = list(cells[0]) if cells else list(known)
    strangers = sorted(set(held) - set(known))
    if strangers or any(set(row) != set(held) for row in cells):
        raise ValueError(
            f"{where}: the rows hold columns {model.__name__} does not declare ({strangers}), "
            "or two rows hold different columns, so a rewrite would not keep every cell"
        )
    _refuse_an_identity_no_reader_could_read(cells, where=where)
    added = set(known) - set(model.model_fields)
    for row in cells:
        try:
            model.model_validate({key: value for key, value in row.items() if key not in added})
        except ValidationError as refusal:
            raise ValueError(f"{where}: a row this build refuses: {refusal}") from refusal
    digest = hashlib.sha256(json_lines.rows_bytes(cells)).hexdigest()

    def restamp(engine: str) -> dict[bytes, bytes]:
        update = {b"content_sha256": digest.encode("ascii"), b"writer_version": engine.encode()}
        FileEnvelope.from_metadata(renamed | update)
        return renamed | update

    if envelope.writer == json_lines.__name__:
        fmt = Format.JSON
        data = json_lines.render(cells, envelope=restamp(json_lines.engine_version()))
    else:
        from idhazh.ledger import parquet

        if envelope.writer != parquet.__name__:
            raise ValueError(f"{where}: {envelope.writer} wrote it, and no container here reads it")
        fmt = Format.PARQUET
        data = parquet.render(
            [known[name] for name in held],
            cells,
            envelope=restamp(parquet.engine_version()),
            compression=envelope.compression,
        )
    if envelope.period is None:
        path = raw_path(
            state_dir, ledger, envelope.covers, envelope.file_id, fmt=fmt, registry=registry
        )
    else:
        path = compact_path(
            state_dir, ledger, envelope.period, envelope.covers, fmt=fmt, registry=registry
        )
    return PeriodFile(path, data, len(cells))


def _opened(path: Path) -> tuple[FileEnvelope, list[dict[str, Any]]]:
    """One file's envelope and its stored rows, read by the container its own bytes name.

    The container is told from the file's first bytes and never from its suffix,
    and the envelope then has to name the module that reads it - a file whose
    envelope disagrees with its own bytes is refused rather than half-trusted.
    """
    data = path.read_bytes()
    metadata: Mapping[bytes, bytes]
    if data.startswith(_PARQUET_MAGIC):
        from idhazh.ledger import parquet

        metadata, stored = parquet.read(data)
        reader = parquet.__name__
    elif data.startswith(json_lines.MAGIC):
        metadata, stored = json_lines.read(data)
        reader = json_lines.__name__
    else:
        raise ValueError(f"{path.name} is neither a parquet nor a JSON-lines ledger file")
    envelope = FileEnvelope.from_metadata(metadata)
    if envelope.writer != reader:
        raise ValueError(
            f"{path.name} says {envelope.writer} wrote it, and its bytes are {reader}'s"
        )
    return envelope, stored


def read_envelope(path: Path) -> FileEnvelope:
    """One file's envelope. A parquet file's comes from its footer, without touching a row."""
    return read_footer(path).envelope


def read_footer(path: Path) -> FileFooter:
    """One file's envelope and how many rows it holds.

    A parquet file answers both from its footer, without touching a row. A
    JSON-lines file has no footer, so it is read whole. The container is told
    from the file's first bytes, as `_opened` tells it.
    """
    with path.open("rb") as handle:
        head = handle.read(len(_PARQUET_MAGIC))
    if head == _PARQUET_MAGIC:
        from idhazh.ledger import parquet

        metadata, rows = parquet.read_footer(path)
        return FileFooter(envelope=FileEnvelope.from_metadata(metadata), rows=rows)
    envelope, stored = _opened(path)
    return FileFooter(envelope=envelope, rows=len(stored))


def load_stored[C: Contract](paths: Sequence[Path], *, model: type[C]) -> list[StoredRow[C]]:
    """Read these files back as rows of one contract, each beside its identity cells.

    In the order the paths give, and each file's rows in file order. A file
    written under a newer shape of `model` than this build declares is refused,
    naming the file, the stamp it holds and the stamp this build reads: only a
    build at least that new knows what those rows mean. A row whose cells either
    shape refuses is refused naming its file.
    """
    wanted = model.schema_version()
    added = {column.name for column in _IDENTITY_COLUMNS} - set(model.model_fields)
    held: list[StoredRow[C]] = []
    for path in paths:
        envelope, stored = _opened(path)
        if envelope.row_schema_version > wanted:
            raise ValueError(
                f"{path.name} ({envelope.ledger.value}, {envelope.covers}) holds "
                f"{model.__name__} rows written under {envelope.row_schema_version}, and this "
                f"build reads {model.__name__} {wanted}. Read it with a build at least as new"
            )
        try:
            held.extend(
                StoredRow(
                    identity=RowIdentity.model_validate(
                        {column.name: cells.get(column.name) for column in _IDENTITY_COLUMNS}
                    ),
                    row=model.model_validate(
                        {key: value for key, value in cells.items() if key not in added}
                    ),
                )
                for cells in stored
            )
        except ValidationError as refusal:
            raise ValueError(f"{path.name} holds a row this build refuses: {refusal}") from refusal
    return held


def load[C: Contract](paths: Sequence[Path], *, model: type[C]) -> list[C]:
    """Read these files back as rows of one contract, in the order the paths give.

    `load_stored` with the identity cells dropped: every row is validated by
    `model` and the door's own columns are left behind.
    """
    return [held.row for held in load_stored(paths, model=model)]
