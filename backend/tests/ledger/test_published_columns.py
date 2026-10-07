"""Does the site build reject published ledger files whose columns do not match their row contracts?"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from conftest import writer_identity
from pytest import CaptureFixture

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Compression, Format, Period, WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import parquet, published_columns
from idhazh.ledger.arrow_schema import Column, ColumnType
from idhazh.ledger.persist import file_columns

from ._fixtures import fixture_rows


def _identity() -> WriterIdentity:
    return writer_identity(
        "2026-10-07-1",
        job=ServerJob.ASSEMBLE,
        shard=1,
        producer="tests.ledger.test_published_columns",
    )


def _site_tree_with_host_file(tmp_path: Path) -> tuple[Path, Path]:
    site_tree = tmp_path / "site"
    state = site_tree / "state"
    row = fixture_rows(HostFingerprintRow)[0]
    (raw,) = ledger.persist(
        state,
        [row],
        ledger=LedgerName.HOST_FINGERPRINT,
        covers=row.date,
        identity=_identity(),
        fmt=Format.PARQUET,
    )
    return site_tree, raw


def _site_tree_with_raw_and_compact_host_files(tmp_path: Path) -> Path:
    site_tree, raw = _site_tree_with_host_file(tmp_path)
    state = site_tree / "state"
    row = fixture_rows(HostFingerprintRow)[0]
    stored = ledger.load_stored([raw], model=HostFingerprintRow)
    ledger.persist_period(
        state,
        stored,
        model=HostFingerprintRow,
        ledger=LedgerName.HOST_FINGERPRINT,
        period=Period.DAILY,
        covers=row.date,
        identity=_identity(),
        built_from=1,
        fmt=Format.PARQUET,
    )
    return site_tree


def _rewrite_file(
    path: Path,
    *,
    columns: tuple[Column, ...],
    schema_version: str | None = None,
    compression: Compression = Compression.NONE,
) -> None:
    metadata, rows = parquet.read(path.read_bytes())
    if schema_version is not None:
        metadata = {**metadata, b"schema_version": schema_version.encode("utf-8")}
    names = {column.name for column in columns}
    path.write_bytes(
        parquet.render(
            columns,
            [{key: value for key, value in row.items() if key in names} for row in rows],
            envelope=metadata,
            compression=compression,
        )
    )


def _columns_without(name: str) -> tuple[Column, ...]:
    return tuple(column for column in file_columns(HostFingerprintRow) if column.name != name)


def _columns_with_string_attempt() -> tuple[Column, ...]:
    return tuple(
        replace(column, type=ColumnType.STRING) if column.name == "attempt" else column
        for column in file_columns(HostFingerprintRow)
    )


def test_current_published_columns_pass(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    site_tree = _site_tree_with_raw_and_compact_host_files(tmp_path)

    assert published_columns.check(site_tree, [LedgerName.HOST_FINGERPRINT]) == 0

    assert capsys.readouterr().out == (
        "published-columns host-fingerprint: checked 2 file(s), current 2, history none\n"
    )


def test_older_file_lacking_a_newer_column_passes_and_prints(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    site_tree, raw = _site_tree_with_host_file(tmp_path)
    _rewrite_file(raw, columns=_columns_without("unit_id"), schema_version="2000-01-01")

    assert published_columns.check(site_tree, [LedgerName.HOST_FINGERPRINT]) == 0

    assert capsys.readouterr().out == (
        "published-columns host-fingerprint: checked 1 file(s), current 0, "
        "history 2000-01-01: 1 file(s), missing [unit_id], extra [none]\n"
    )


def test_f1_current_stamp_with_missing_column_fails_and_prints(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    site_tree, raw = _site_tree_with_host_file(tmp_path)
    _rewrite_file(raw, columns=_columns_without("unit_id"))

    assert published_columns.check(site_tree, [LedgerName.HOST_FINGERPRINT]) == 1

    printed = capsys.readouterr().out
    assert (
        "published-columns FAIL F1 ledger=host-fingerprint "
        "file=state/raw/host-fingerprint/2026/09/16/"
    ) in printed
    assert (
        "file_schema=2026-09-20 contract_schema=2026-09-20 column=unit_id "
        "file_type=<not declared> contract_type=string; fix: give the contract a new "
        "version, CLAUDE.md section 11, or re-pack the file"
    ) in printed


def test_f2_shared_column_with_changed_type_fails_and_prints(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    site_tree, raw = _site_tree_with_host_file(tmp_path)
    metadata, rows = parquet.read(raw.read_bytes())
    raw.write_bytes(
        parquet.render(
            _columns_with_string_attempt(),
            [{**row, "attempt": str(row["attempt"])} for row in rows],
            envelope=metadata,
            compression=Compression.NONE,
        )
    )

    assert published_columns.check(site_tree, [LedgerName.HOST_FINGERPRINT]) == 1

    printed = capsys.readouterr().out
    assert "published-columns FAIL F2 ledger=host-fingerprint" in printed
    assert (
        "column=attempt file_type=string contract_type=int64; fix: give the contract "
        "a new version, CLAUDE.md section 11, or re-pack the file"
    ) in printed


def test_f3_newer_file_fails_and_prints(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    site_tree, raw = _site_tree_with_host_file(tmp_path)
    _rewrite_file(raw, columns=file_columns(HostFingerprintRow), schema_version="9999-01-01")

    assert published_columns.check(site_tree, [LedgerName.HOST_FINGERPRINT]) == 1

    printed = capsys.readouterr().out
    assert "published-columns FAIL F3 ledger=host-fingerprint" in printed
    assert (
        "file_schema=9999-01-01 contract_schema=2026-09-20 column=<not declared> "
        "file_type=<not declared> contract_type=<not declared>; fix: re-pack the file "
        "with this build or run a build at least as new"
    ) in printed


def test_f4_published_ledger_without_door_contract_fails_and_prints(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    assert (
        published_columns.check(
            tmp_path / "site", [LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS]
        )
        == 1
    )

    assert capsys.readouterr().out == (
        "published-columns FAIL F4 ledger=scored-pairs file=<no file> "
        "file_schema=<not declared> contract_schema=<not declared> "
        "column=<not declared> file_type=<not declared> contract_type=<not declared>; "
        "fix: add the ledger to the door table in idhazh/ledger/keys.py\n"
    )


def test_a_site_tree_with_no_published_files_fails_and_prints(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    site_tree = tmp_path / "site"

    assert published_columns.check(site_tree, [LedgerName.HOST_FINGERPRINT]) == 1

    assert capsys.readouterr().out == (
        "published-columns FAIL F0 "
        f"tree={site_tree.resolve().as_posix()} file_schema=<not declared> "
        "contract_schema=<not declared> column=<not declared> "
        "file_type=<not declared> contract_type=<not declared>; "
        "fix: is --site-tree the built site?\n"
    )
