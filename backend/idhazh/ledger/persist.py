"""The one door a contract payload takes to disk under `state/raw/` or `state/compact/`, and back.

A producer hands the door its rows, the ledger, the period and its writer
identity. The door mints the two identifiers, builds the path, assembles the
envelope, renders the file and writes it whole. A producer never builds a path,
never invents a filename and never assembles an envelope, which is what makes
the next ledger's migration a change of call site rather than a change of
design. `identity.producer` is the one field a call site must get right: it is
what keeps two producers of one ledger apart inside `unit_id`.

Two formats behind one door: parquet, and JSON lines a person can read in a
pull request. `ledger/parquet.py` is the only module that imports the engine, and
it is imported inside the functions that need it, so importing the ledger never
loads pyarrow. The write is `atomic_write.write_atomic_bytes` and nothing else,
so a half-written file is never visible under its own name.

`load` is the inverse of `persist` and nothing else. It does not remove
duplicates: a union over several attempts at one work unit keeps the highest
`attempt` per `unit_id`, and that settlement is a reader's job, not the door's.

Every instant here is UTC (CLAUDE.md section 2).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any, Final

from idhazh import atomic_write, config
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.base import MAINTENANCE_JOBS, Contract, PeriodStamp
from idhazh.contracts.file_envelope import (
    Compression,
    FileEnvelope,
    Format,
    Period,
    Tier,
    WriterIdentity,
    covers_fits,
)
from idhazh.contracts.knobs.ledger import LedgerConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import arrow_schema, filenames, json_lines, lifecycle
from idhazh.ledger.arrow_schema import Column, ColumnType
from idhazh.ledger.keys import DATE_CELL
from idhazh.ledger.paths import compact_path, raw_path

#: The committed config file the `ledger` block is read from.
_APP_CONFIG_FILENAME: Final = "idhazh.json"

#: What every parquet file opens with. How the door tells the two containers
#: apart without trusting a suffix: a format literal, fixed by the parquet spec.
_PARQUET_MAGIC: Final = b"PAR1"

#: The envelope keys that are also a column on every row, because a query filters
#: or groups on them: a union keeps the highest `attempt` per `unit_id`, and a
#: bad run is traced by filtering on `run_id`. A contract field of the same name
#: is the column instead, so a row's own value is never overwritten; the
#: envelope still carries the writer's.
_IDENTITY_COLUMNS: Final[tuple[Column, ...]] = (
    Column("ledger", ColumnType.STRING, nullable=False),
    Column("covers", ColumnType.STRING, nullable=False),
    Column("run_id", ColumnType.STRING, nullable=False),
    Column("attempt", ColumnType.INT64, nullable=False),
    Column("job", ColumnType.STRING, nullable=False),
    Column("shard", ColumnType.INT64, nullable=False),
    Column("unit_id", ColumnType.STRING, nullable=False),
)


@cache
def _knobs() -> LedgerConfig:
    """The committed `ledger` block: the default format and the two compressions."""
    text = (config.DEFAULT_CONFIG_DIR / _APP_CONFIG_FILENAME).read_text(encoding="utf-8")
    return AppConfig.from_json(text).ledger


def _refuse_a_shape_the_tier_cannot_take(
    *, tier: Tier, period: Period | None, covers: str, built_from: int | None
) -> None:
    """A compact file names its period and a raw one does not, and `covers` fits it."""
    if tier is Tier.COMPACT and period is None:
        raise ValueError(
            "a compact file covers one daily or monthly period, so persist needs a period"
        )
    if tier is Tier.RAW and period is not None:
        raise ValueError(
            "a raw file is filed under the day its rows name, so persist takes no period for it"
        )
    if tier is Tier.RAW and built_from is not None:
        raise ValueError("a raw file was read from nothing, so it carries no built_from")
    if not covers_fits(covers, tier=tier, period=period):
        raise ValueError(
            f"covers {covers!r} is not the shape a {tier.value} "
            f"{period.value + ' ' if period else ''}file covers: a raw or daily file "
            "covers YYYY-MM-DD and a monthly file covers YYYY-MM"
        )


def _one_contract(rows: Sequence[Contract]) -> type[Contract]:
    """The contract every row is, or a refusal: one file holds rows of one shape."""
    model = type(rows[0])
    strays = sorted({type(row).__name__ for row in rows if type(row) is not model})
    if strays:
        raise TypeError(f"one file holds rows of one contract, and {model.__name__} met {strays}")
    return model


def _routed(
    rows: Sequence[Contract], *, model: type[Contract], tier: Tier, covers: str
) -> dict[str, list[Contract]]:
    """Each row under the period it belongs to.

    On the raw tier a row is filed under the day its own `date` cell names, so
    rows a run left behind three days ago land under that day rather than under
    today, and a call holding three days writes three files. A contract with no
    date cell files under `covers`. On the compact tier a write replaces the
    whole period file, so `covers` is a promise: a row outside it is refused
    rather than allowed to overwrite a finished period with a fragment.
    """
    dated = DATE_CELL in model.model_fields
    if tier is Tier.RAW:
        grouped: dict[str, list[Contract]] = {}
        for row in rows:
            grouped.setdefault(getattr(row, DATE_CELL) if dated else covers, []).append(row)
        return grouped
    if dated:
        outside = sorted(
            {
                getattr(row, DATE_CELL)
                for row in rows
                if not str(getattr(row, DATE_CELL)).startswith(covers)
            }
        )
        if outside:
            raise ValueError(
                f"a compact file covering {covers} was handed rows dated {outside}. A compact "
                "write replaces the whole period, so every row must fall inside it"
            )
    return {covers: list(rows)}


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


def _write_one(
    state_dir: Path,
    batch: Sequence[Contract],
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
) -> Path:
    """One period's file: identifiers minted, envelope assembled, bytes written whole."""
    unit = filenames.unit_id(
        ledger=ledger,
        covers=covers,
        run_id=identity.run_id,
        job=identity.job,
        shard=identity.shard,
        producer=identity.producer,
    )
    name = filenames.file_id(unit=unit, attempt=identity.attempt, written_at_ms=written_at_ms)
    stamped: dict[str, Any] = {
        "ledger": ledger.value,
        "covers": covers,
        "run_id": identity.run_id,
        "attempt": identity.attempt,
        "job": identity.job.value,
        "shard": identity.shard,
        "unit_id": str(unit),
    }
    stored = [stamped | row.model_dump(mode="json") for row in batch]
    if tier is Tier.RAW:
        target = raw_path(state_dir, ledger, covers, name, fmt=fmt)
    else:
        assert period is not None  # refused above when absent
        target = compact_path(state_dir, ledger, period, covers, fmt=fmt)
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
        content_sha256=hashlib.sha256(json_lines.rows_bytes(stored)).hexdigest(),
        writer=writer,
        writer_version=engine,
        compression=compression,
        built_from=built_from,
    ).as_metadata()
    if fmt is Format.PARQUET:
        payload = parquet.render(
            _columns(model), stored, envelope=envelope, compression=compression
        )
    else:
        payload = json_lines.render(stored, envelope=envelope)
    atomic_write.write_atomic_bytes(target, payload)
    return target


def persist(
    state_dir: Path,
    rows: Sequence[Contract],
    *,
    ledger: LedgerName,
    covers: PeriodStamp,
    identity: WriterIdentity,
    tier: Tier = Tier.RAW,
    period: Period | None = None,
    built_from: int | None = None,
    fmt: Format | None = None,
) -> list[Path]:
    """Write these rows and return where they went, one path per period they cover.

    `state_dir` is the state root the caller writes under - `common.STATE_ROOT`
    for a stage, which a trial run and the test suite both redirect. `covers` is
    the period a row is routed to rather than a promise about the batch on the
    raw tier, and the one period the file covers on the compact tier. `period`
    is required on the compact tier and refused on the raw one. `fmt` of `None`
    means `config/idhazh.json`'s `ledger.format`, and nothing else.

    A raw write into a paused or retired family from a pipeline job writes
    nothing and returns an empty list, with one warning. A compact write and a
    write from a job in `MAINTENANCE_JOBS` are never skipped: each files rows
    again that were already recorded.

    The paths come back ascending by the period each file covers, never by path
    string.
    """
    _refuse_a_shape_the_tier_cannot_take(
        tier=tier, period=period, covers=covers, built_from=built_from
    )
    if not rows:
        return []
    model = _one_contract(rows)
    records_new_rows = tier is Tier.RAW and identity.job not in MAINTENANCE_JOBS
    if records_new_rows and not lifecycle.accepts_new_rows(ledger, len(rows)):
        return []
    knobs = _knobs()
    chosen = knobs.format if fmt is None else fmt
    compression = _compression(chosen, tier, knobs)
    written_at_ms = int(datetime.now(UTC).timestamp() * 1000)
    grouped = _routed(rows, model=model, tier=tier, covers=covers)
    return [
        _write_one(
            state_dir,
            grouped[filed_under],
            model=model,
            ledger=ledger,
            covers=filed_under,
            identity=identity,
            tier=tier,
            period=period,
            built_from=built_from,
            fmt=chosen,
            compression=compression,
            written_at_ms=written_at_ms,
        )
        for filed_under in sorted(grouped)
    ]


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
    with path.open("rb") as handle:
        head = handle.read(len(_PARQUET_MAGIC))
    if head == _PARQUET_MAGIC:
        from idhazh.ledger import parquet

        return FileEnvelope.from_metadata(parquet.read_envelope(path))
    return _opened(path)[0]


def load[C: Contract](paths: Sequence[Path], *, model: type[C]) -> list[C]:
    """Read these files back as rows of one contract, in the order the paths give.

    A file written under a newer shape of `model` than this build declares is
    refused, naming the file, the stamp it holds and the stamp this build reads:
    only a build at least that new knows what those rows mean. The identity
    columns the door added are dropped, and every row is validated by `model`.
    """
    wanted = model.schema_version()
    added = {column.name for column in _IDENTITY_COLUMNS} - set(model.model_fields)
    rows: list[C] = []
    for path in paths:
        envelope, stored = _opened(path)
        if envelope.row_schema_version > wanted:
            raise ValueError(
                f"{path.name} ({envelope.ledger.value}, {envelope.covers}) holds "
                f"{model.__name__} rows written under {envelope.row_schema_version}, and this "
                f"build reads {model.__name__} {wanted}. Read it with a build at least as new"
            )
        rows.extend(
            model.model_validate({key: value for key, value in cells.items() if key not in added})
            for cells in stored
        )
    return rows
