"""Does the ledger door write any contract as parquet or JSON lines, and read it back unchanged?

The door is the one path a payload takes to `state/raw/` and `state/compact/`,
so these tests drive it the way a producer will: rows in, paths out, rows back.
They cover the round trip in both formats, the envelope each file carries about
itself, the two identifiers that let a re-run replace its first attempt, the
routing that files a row under its own day, and every refusal the door makes.

Every row comes from a committed contract fixture, read inside the test.
Nothing here reads `state/`.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import ClassVar, Final

import pyarrow.parquet
import pytest
from conftest import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import Field

from idhazh import ledger
from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId, ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.file_envelope import (
    Compression,
    FileEnvelope,
    Format,
    Period,
    Tier,
    WriterIdentity,
)
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.knobs.ledger import LedgerConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.ledger import filenames, json_lines, parquet

pytestmark = pytest.mark.contract

#: The door's own module. The package binds `persist` to the function, so the
#: module is reached through the import system rather than as an attribute.
DOOR: Final = importlib.import_module("idhazh.ledger.persist")

A_RUN: Final = "2026-09-24-17482910337"
A_SHA: Final = "0735031c2a9e4b8f1d6c3a5e7b9d0f2a4c6e8b1d"

#: Which ledger each fixture contract is written into. The door does not tie a
#: contract to a ledger, so this only has to be a real, active one.
LEDGER_OF: Final[dict[type[Contract], LedgerName]] = {
    VisualPruneRow: LedgerName.VISUAL_PRUNES,
    FeedRetirementRow: LedgerName.FEED_RETIREMENTS,
    HostFingerprintRow: LedgerName.HOST_FINGERPRINT,
    EvalRow: LedgerName.SUMMARY_QUALITY_EVALS,
}


class EveryColumn(Contract):
    """One field of every column type, with both a value and a null in the optional ones.

    **A fixture, not a mock** (Guardrail #7): it stands in for nobody, computes
    nothing, and is deliberately absent from `contracts.CONTRACTS`.
    """

    __schema_stem__: ClassVar[str] = "every-column"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-27",
            change="Initial shape: one field of every column type the door writes.",
            why="A round trip is only proven for the types a row actually carries.",
        ),
    )

    date: DateStamp
    words: str
    maybe_words: str | None = None
    count: int
    maybe_count: int | None = None
    share: float
    maybe_share: float | None = None
    flag: bool
    maybe_flag: bool | None = None
    tier: Tier
    maybe_period: Period | None = None
    run_ids: tuple[RunId, ...] = Field(default=())


def _every_column_rows() -> list[Contract]:
    """Two rows: one with every optional cell empty, one with every cell holding a value."""
    return [
        EveryColumn(
            version=EveryColumn.schema_version(),
            date="2026-09-24",
            words='a, "quoted" line',
            count=0,
            share=0.1,
            flag=True,
            tier=Tier.RAW,
        ),
        EveryColumn(
            version=EveryColumn.schema_version(),
            date="2026-09-24",
            words="",
            maybe_words="x",
            count=-7,
            maybe_count=2**40,
            share=2.5e-10,
            maybe_share=-1.0,
            flag=False,
            maybe_flag=False,
            tier=Tier.COMPACT,
            maybe_period=Period.MONTHLY,
            run_ids=("2026-09-24-1", "2026-09-24-2"),
        ),
    ]


def _fixture_rows(model: type[Contract]) -> list[Contract]:
    """Every committed contract fixture of this model, as rows."""
    directory = CONTRACT_FIXTURES_DIR / model.__schema_stem__
    return [model.from_json(read_text(path)) for path in sorted(directory.glob("*.json"))]


def _identity(*, attempt: int = 1, job: ServerJob = ServerJob.ASSEMBLE) -> WriterIdentity:
    return WriterIdentity(
        run_id=A_RUN, attempt=attempt, job=job, shard=3, producer="tests.ledger", git_sha=A_SHA
    )


def _same_rows(got: list[Contract], want: list[Contract]) -> None:
    """Equal as a collection, because rows of several days come back grouped by day."""
    assert sorted(row.to_json() for row in got) == sorted(row.to_json() for row in want)


def _stored(path: Path) -> list[dict[str, object]]:
    """A file's rows as stored, identity columns included, read by the container's module."""
    data = path.read_bytes()
    reader = parquet.read if data.startswith(b"PAR1") else json_lines.read
    return reader(data)[1]


# --- the round trip ------------------------------------------------------------


def test_a_short_lived_parquet_reader_exits_cleanly() -> None:
    fixture = FIXTURES_DIR / "parquet" / "visual-prunes-raw-2026-09-06.parquet"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "from pathlib import Path\n"
            "from idhazh.ledger import parquet\n"
            "metadata, rows = parquet.read(Path(sys.argv[1]).read_bytes())\n"
            "print(len(rows))\n",
            str(fixture),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == str(len(_fixture_rows(VisualPruneRow)))


@pytest.mark.parametrize("fmt", list(Format), ids=[fmt.value for fmt in Format])
@pytest.mark.parametrize("model", list(LEDGER_OF), ids=[model.__name__ for model in LEDGER_OF])
def test_every_contract_comes_back_equal_in_both_formats(
    model: type[Contract], fmt: Format, tmp_path: Path
) -> None:
    """The oracle: `load(persist(rows))` is the rows, for every model the door will carry."""
    rows = _fixture_rows(model)

    written = ledger.persist(
        tmp_path, rows, ledger=LEDGER_OF[model], covers="2026-09-24", identity=_identity(), fmt=fmt
    )

    _same_rows(ledger.load(written, model=model), rows)


@pytest.mark.parametrize("fmt", list(Format), ids=[fmt.value for fmt in Format])
def test_every_column_type_comes_back_equal_and_in_order(fmt: Format, tmp_path: Path) -> None:
    rows = _every_column_rows()

    written = ledger.persist(
        tmp_path,
        rows,
        ledger=LedgerName.VISUAL_PRUNES,
        covers="2026-09-24",
        identity=_identity(),
        fmt=fmt,
    )

    assert len(written) == 1
    assert ledger.load(written, model=EveryColumn) == rows


@pytest.mark.parametrize("fmt", list(Format), ids=[fmt.value for fmt in Format])
def test_the_files_an_earlier_engine_wrote_still_load(fmt: Format) -> None:
    """A file yesterday's build committed has to read today (CLAUDE.md section 11)."""
    committed = FIXTURES_DIR / "parquet" / f"visual-prunes-raw-2026-09-06.{fmt.value}"

    assert ledger.load([committed], model=VisualPruneRow) == _fixture_rows(VisualPruneRow)
    assert ledger.read_envelope(committed).ledger is LedgerName.VISUAL_PRUNES


# --- the envelope inside every file ----------------------------------------------


@pytest.mark.parametrize("fmt", list(Format), ids=[fmt.value for fmt in Format])
def test_every_file_carries_a_whole_envelope_that_round_trips_byte_for_byte(
    fmt: Format, tmp_path: Path
) -> None:
    (written,) = ledger.persist(
        tmp_path,
        _fixture_rows(VisualPruneRow),
        ledger=LedgerName.VISUAL_PRUNES,
        covers="2026-09-06",
        identity=_identity(),
        fmt=fmt,
    )
    data = written.read_bytes()
    raw = (parquet.read if fmt is Format.PARQUET else json_lines.read)(data)[0]

    envelope = FileEnvelope.from_metadata(raw)

    assert envelope.as_metadata() == raw
    assert set(raw) == {
        key.encode()
        for key in (
            "envelope_version",
            "schema_version",
            "tier",
            "ledger",
            "covers",
            "written_at_ms",
            "run_id",
            "attempt",
            "job",
            "shard",
            "producer",
            "unit_id",
            "file_id",
            "content_sha256",
            "git_sha",
            "writer",
            "writer_version",
            "compression",
        )
    }, "a raw file carries every key but period and built_from"
    assert envelope.row_schema_version == VisualPruneRow.schema_version()
    assert envelope.writer == (parquet if fmt is Format.PARQUET else json_lines).__name__


@pytest.mark.parametrize("fmt", list(Format), ids=[fmt.value for fmt in Format])
def test_the_filename_is_the_file_id_and_both_identifiers_recompute(
    fmt: Format, tmp_path: Path
) -> None:
    """The oracle: name, envelope and column agree, and each identifier is recomputable."""
    (written,) = ledger.persist(
        tmp_path,
        _fixture_rows(VisualPruneRow),
        ledger=LedgerName.VISUAL_PRUNES,
        covers="2026-09-06",
        identity=_identity(),
        fmt=fmt,
    )
    envelope = ledger.read_envelope(written)
    unit = filenames.unit_id(
        ledger=envelope.ledger,
        covers=envelope.covers,
        run_id=envelope.identity.run_id,
        job=envelope.identity.job,
        shard=envelope.identity.shard,
        producer=envelope.identity.producer,
    )

    assert written.stem == str(envelope.file_id)
    assert (
        filenames.file_id(
            unit=envelope.unit_id,
            attempt=envelope.identity.attempt,
            written_at_ms=envelope.written_at_ms,
        )
        == envelope.file_id
    )
    assert unit == envelope.unit_id
    assert {row["unit_id"] for row in _stored(written)} == {str(unit)}


def test_two_attempts_at_one_unit_are_two_files_and_the_union_keeps_the_second(
    tmp_path: Path,
) -> None:
    """The oracle, and the case that would have caught one identifier doing both jobs.

    GitHub re-runs a failed job into the same run id. The re-run's file must not
    take the first attempt's name, and it must share its `unit_id`, so a union
    keeping the highest attempt per unit holds attempt 2's rows only - even when
    attempt 2 wrote fewer rows than attempt 1.
    """
    rows = _fixture_rows(VisualPruneRow)
    first = ledger.persist(
        tmp_path,
        rows,
        ledger=LedgerName.VISUAL_PRUNES,
        covers="2026-09-06",
        identity=_identity(attempt=1),
    )
    second = ledger.persist(
        tmp_path,
        rows[:1],
        ledger=LedgerName.VISUAL_PRUNES,
        covers="2026-09-06",
        identity=_identity(attempt=2),
    )
    newest: dict[object, tuple[int, Path]] = {}
    for path in [*first, *second]:
        envelope = ledger.read_envelope(path)
        held = newest.get(envelope.unit_id)
        if held is None or envelope.identity.attempt > held[0]:
            newest[envelope.unit_id] = (envelope.identity.attempt, path)

    assert first[0].name != second[0].name
    assert ledger.read_envelope(first[0]).unit_id == ledger.read_envelope(second[0]).unit_id
    assert ledger.load([path for _, path in newest.values()], model=VisualPruneRow) == rows[:1]


def test_pack_v8_packs_the_worked_example() -> None:
    """RFC 9562 version 8, bit for bit: the clock first, then the version, then the variant."""
    packed = filenames._pack_v8(0x01A0D03C2E00, 0x461, 0x18E0A67898E9A802)

    assert str(packed) == "01a0d03c-2e00-8461-98e0-a67898e9a802"
    assert packed.version == 8
    assert packed.variant == "specified in RFC 4122"


def test_a_file_id_sorts_by_its_clock_across_milliseconds() -> None:
    unit = filenames.unit_id(
        ledger="visual-prunes", covers="2026-09-24", run_id=A_RUN, job="run-tasks", shard=3,
        producer="tests.ledger",
    )
    earlier = filenames.file_id(unit=unit, attempt=2, written_at_ms=1_790_200_000_431)
    later = filenames.file_id(unit=unit, attempt=1, written_at_ms=1_790_200_000_432)

    assert str(earlier) < str(later)


# --- routing and the period a file covers ------------------------------------------


def test_a_raw_write_files_each_row_under_its_own_day_and_returns_the_days_in_order(
    tmp_path: Path,
) -> None:
    """Rows a run left behind days ago land under their own day, never under today."""
    template = _every_column_rows()[0]
    rows: list[Contract] = [
        template.model_copy(update={"date": day})
        for day in ("2026-09-24", "2026-09-22", "2026-09-23", "2026-09-22")
    ]

    written = ledger.persist(
        tmp_path, rows, ledger=LedgerName.VISUAL_PRUNES, covers="2026-09-24", identity=_identity()
    )

    assert [ledger.read_envelope(path).covers for path in written] == [
        "2026-09-22",
        "2026-09-23",
        "2026-09-24",
    ]
    assert [len(ledger.load([path], model=EveryColumn)) for path in written] == [2, 1, 1]


def test_a_contract_with_no_date_files_under_covers(tmp_path: Path) -> None:
    rows = _fixture_rows(FeedRetirementRow)

    written = ledger.persist(
        tmp_path,
        rows,
        ledger=LedgerName.FEED_RETIREMENTS,
        covers="2026-09-24",
        identity=_identity(),
    )

    assert [ledger.read_envelope(path).covers for path in written] == ["2026-09-24"]


def _filed_raw(
    state: Path, rows: list[Contract], *, covers: str = "2026-09-24"
) -> list[ledger.StoredRow[Contract]]:
    """Rows as raw files hold them: filed through the door, read back beside their identity."""
    written = ledger.persist(
        state, rows, ledger=LedgerName.VISUAL_PRUNES, covers=covers, identity=_identity()
    )
    return ledger.load_stored(written, model=type(rows[0]))


def test_a_compact_write_covers_its_period_and_keeps_every_rows_own_identity(
    tmp_path: Path,
) -> None:
    """The oracle for a re-run after compaction: each row keeps the writer that filed it.

    The envelope names the compaction, which wrote the file. The rows keep the
    `unit_id` and `attempt` their raw file gave them, so a second attempt that
    lands after the day was compacted can still replace the first.
    """
    template = _every_column_rows()[1]
    rows: list[Contract] = [
        template.model_copy(update={"date": day}) for day in ("2026-08-01", "2026-08-31")
    ]
    stored = _filed_raw(tmp_path / "raw-side", rows)

    written = ledger.persist_period(
        tmp_path,
        stored,
        model=EveryColumn,
        ledger=LedgerName.VISUAL_PRUNES,
        period=Period.MONTHLY,
        covers="2026-08",
        identity=_identity(job=ServerJob.RUN_TASKS),
        built_from=31,
    )
    envelope = ledger.read_envelope(written)

    assert written.relative_to(tmp_path).as_posix() == "compact/visual-prunes/monthly/2026/08.parquet"
    assert (envelope.tier, envelope.period, envelope.built_from) == (
        Tier.COMPACT,
        Period.MONTHLY,
        31,
    )
    assert envelope.identity.job is ServerJob.RUN_TASKS
    assert ledger.load([written], model=EveryColumn) == rows
    kept = ledger.load_stored([written], model=EveryColumn)
    assert [held.identity for held in kept] == [held.identity for held in stored]
    assert {held.identity.job for held in kept} == {ServerJob.ASSEMBLE}


def test_a_compact_write_refuses_a_row_filed_outside_the_period_it_covers(tmp_path: Path) -> None:
    """A compact write replaces the whole period, so a stray row would overwrite a finished one."""
    template = _every_column_rows()[0]
    rows: list[Contract] = [
        template.model_copy(update={"date": day}) for day in ("2026-08-31", "2026-09-01")
    ]
    stored = _filed_raw(tmp_path / "raw-side", rows)

    with pytest.raises(ValueError, match=r"filed under \['visual-prunes 2026-09-01'\]"):
        ledger.persist_period(
            tmp_path,
            stored,
            model=EveryColumn,
            ledger=LedgerName.VISUAL_PRUNES,
            period=Period.MONTHLY,
            covers="2026-08",
            identity=_identity(),
            built_from=2,
        )
    assert not (tmp_path / "compact").exists()


def test_a_period_that_held_nothing_is_still_a_file_with_every_column(tmp_path: Path) -> None:
    """A quiet day gets a zero-row file, so the model is passed rather than read off a row."""
    built = ledger.render_period(
        tmp_path,
        [],
        model=VisualPruneRow,
        ledger=LedgerName.VISUAL_PRUNES,
        period=Period.DAILY,
        covers="2026-09-06",
        identity=_identity(job=ServerJob.RUN_TASKS),
        built_from=0,
    )

    assert not built.path.exists(), "rendering writes nothing"
    columns = pyarrow.parquet.read_schema(pyarrow.BufferReader(built.data)).names
    assert set(VisualPruneRow.model_fields) - {"version"} <= set(columns)
    assert {"unit_id", "attempt", "covers"} <= set(columns)
    assert parquet.read(built.data)[1] == []


def test_a_row_naming_another_try_than_its_writer_is_refused(tmp_path: Path) -> None:
    """The union ranks on `attempt`, so a row's own may not contradict the writer that files it."""
    (row,) = _fixture_rows(CollectionPruneRow)[:1]
    assert isinstance(row, CollectionPruneRow)
    mismatched = row.model_copy(update={"attempt": 1})

    with pytest.raises(ValueError, match="a row names attempt 1 and its writer is 2"):
        ledger.persist(
            tmp_path,
            [mismatched],
            ledger=LedgerName.GARDENER,
            covers=mismatched.date,
            identity=_identity(attempt=2, job=ServerJob.RUN_TASKS),
        )
    assert not tmp_path.exists() or not any(tmp_path.rglob("*.*"))


def test_a_row_whose_own_identity_cell_would_not_read_back_is_refused_before_the_write(
    tmp_path: Path,
) -> None:
    """A field named like an identity cell is that column, so a bad value there loses the file.

    The reader refuses a file whose identity cells do not validate, so a row
    carrying one would be written once and never read again. `model_copy` skips
    validation, which is how such a value would get past the row's own model.
    """
    row = _fixture_rows(HostFingerprintRow)[0]
    assert isinstance(row, HostFingerprintRow)
    unreadable = row.model_copy(update={"shard": -1})

    with pytest.raises(ValueError, match="identity cells would not read back"):
        ledger.persist(
            tmp_path,
            [unreadable],
            ledger=LedgerName.HOST_FINGERPRINT,
            covers=unreadable.date,
            identity=_identity(job=unreadable.job),
        )
    assert not tmp_path.exists() or not any(tmp_path.rglob("*.*"))


@pytest.mark.parametrize(
    ("covers", "refusal"),
    [
        ("2026-09", "is not the shape a raw file covers"),
        ("24 September", "is not the shape a raw file covers"),
    ],
    ids=["raw-covering-a-month", "raw-covering-no-day"],
)
def test_a_raw_write_refuses_a_period_that_is_not_a_day_before_anything_is_written(
    covers: str, refusal: str, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match=refusal):
        ledger.persist(
            tmp_path,
            _every_column_rows(),
            ledger=LedgerName.VISUAL_PRUNES,
            covers=covers,
            identity=_identity(),
        )
    assert not any(tmp_path.rglob("*.*"))


@pytest.mark.parametrize(
    ("period", "covers", "refusal"),
    [
        (Period.DAILY, "2026-09", "is not the shape a compact daily"),
        (Period.MONTHLY, "2026-09-24", "is not the shape a compact monthly"),
        (Period.MONTHLY, "2026", "is not the shape a compact monthly"),
        (Period.YEARLY, "2026-09", "is not the shape a compact yearly"),
    ],
    ids=[
        "daily-covering-a-month",
        "monthly-covering-a-day",
        "monthly-covering-a-year",
        "yearly-covering-a-month",
    ],
)
def test_a_compact_write_refuses_a_period_of_the_wrong_shape_before_anything_is_written(
    period: Period, covers: str, refusal: str, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match=refusal):
        ledger.persist_period(
            tmp_path,
            [],
            model=EveryColumn,
            ledger=LedgerName.VISUAL_PRUNES,
            period=period,
            covers=covers,
            identity=_identity(),
            built_from=0,
        )
    assert not any(tmp_path.rglob("*.*"))


def test_one_file_holds_rows_of_one_contract(tmp_path: Path) -> None:
    mixed = [*_every_column_rows(), *_fixture_rows(VisualPruneRow)]

    with pytest.raises(TypeError, match="one file holds rows of one contract"):
        ledger.persist(
            tmp_path, mixed, ledger=LedgerName.VISUAL_PRUNES, covers="2026-09-24", identity=_identity()
        )


def test_an_empty_write_writes_nothing(tmp_path: Path) -> None:
    written = ledger.persist(
        tmp_path, [], ledger=LedgerName.VISUAL_PRUNES, covers="2026-09-24", identity=_identity()
    )

    assert written == []
    assert not tmp_path.exists() or not any(tmp_path.iterdir())


# --- the format and the compression come from config -----------------------------------


def test_the_format_and_both_compressions_come_from_the_ledger_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fmt=None` means the config's format, and each tier takes its own compression."""
    monkeypatch.setattr(
        DOOR,
        "_knobs",
        lambda: LedgerConfig(
            format=Format.PARQUET,
            compression_raw=Compression.ZSTD,
            compression_compact=Compression.NONE,
        ),
    )
    rows = _every_column_rows()

    (raw,) = ledger.persist(
        tmp_path, rows, ledger=LedgerName.VISUAL_PRUNES, covers="2026-09-24", identity=_identity()
    )
    compact = ledger.persist_period(
        tmp_path,
        ledger.load_stored([raw], model=EveryColumn),
        model=EveryColumn,
        ledger=LedgerName.VISUAL_PRUNES,
        period=Period.DAILY,
        covers="2026-09-24",
        identity=_identity(),
        built_from=1,
    )

    assert raw.suffix == ".parquet"
    assert ledger.read_envelope(raw).compression is Compression.ZSTD
    assert ledger.read_envelope(compact).compression is Compression.NONE
    footer = pyarrow.parquet.read_metadata(raw)
    assert footer.row_group(0).column(0).compression == "ZSTD", "the knob reached the engine"


def test_a_json_lines_file_records_that_it_is_not_compressed(tmp_path: Path) -> None:
    (written,) = ledger.persist(
        tmp_path,
        _every_column_rows(),
        ledger=LedgerName.VISUAL_PRUNES,
        covers="2026-09-24",
        identity=_identity(),
        fmt=Format.JSON,
    )

    assert written.suffix == ".json"
    assert ledger.read_envelope(written).compression is Compression.NONE


# --- what load refuses --------------------------------------------------------------


def _rewritten(path: Path, **envelope: str) -> Path:
    """A JSON-lines file with some envelope keys changed, as a damaged or foreign file is."""
    lines = path.read_text(encoding="ascii").splitlines()
    head = json.loads(lines[0]) | envelope
    path.write_text("\n".join([json.dumps(head, sort_keys=True), *lines[1:]]) + "\n", "ascii")
    return path


def test_a_file_written_under_a_newer_shape_is_refused_naming_both_stamps(tmp_path: Path) -> None:
    (written,) = ledger.persist(
        tmp_path,
        _fixture_rows(VisualPruneRow),
        ledger=LedgerName.VISUAL_PRUNES,
        covers="2026-09-06",
        identity=_identity(),
        fmt=Format.JSON,
    )
    _rewritten(written, schema_version="2099-01-01")

    with pytest.raises(ValueError, match="2099-01-01") as refused:
        ledger.load([written], model=VisualPruneRow)

    assert VisualPruneRow.schema_version() in str(refused.value)
    assert written.name in str(refused.value)


def test_the_container_is_read_from_the_bytes_and_never_the_suffix(tmp_path: Path) -> None:
    rows = _every_column_rows()
    (written,) = ledger.persist(
        tmp_path, rows, ledger=LedgerName.VISUAL_PRUNES, covers="2026-09-24", identity=_identity()
    )
    misnamed = written.rename(written.with_suffix(".json"))

    assert ledger.load([misnamed], model=EveryColumn) == rows


def test_a_file_whose_envelope_names_another_writer_is_refused(tmp_path: Path) -> None:
    (written,) = ledger.persist(
        tmp_path,
        _every_column_rows(),
        ledger=LedgerName.VISUAL_PRUNES,
        covers="2026-09-24",
        identity=_identity(),
        fmt=Format.JSON,
    )
    _rewritten(written, writer=parquet.__name__)

    with pytest.raises(ValueError, match="its bytes are"):
        ledger.load([written], model=EveryColumn)
