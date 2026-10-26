"""Does the site build reject published ledger files whose columns do not match their row contracts?"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from contracts._fixtures import planner_payload
from pytest import CaptureFixture, mark
from support.ledger import writer_identity
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_ingest_selected_article import SelectedArticleRow
from idhazh.contracts.file_envelope import Compression, FileEnvelope, Format, Period, WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import RunPlan
from idhazh.ledger import parquet, published_columns
from idhazh.ledger.arrow_schema import Column, ColumnType, LogicalType
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
    planner = SelectedArticleRow.model_validate(planner_payload("selected-articles"))
    ledger.persist(
        site_tree / "state", [planner], ledger=LedgerName.FEED_INGEST_PLAN_SELECTED_ARTICLES,
        covers=planner.date, fmt=Format.PARQUET,
    )
    assert published_columns.check(site_tree, [LedgerName.FEED_INGEST_PLAN_SELECTED_ARTICLES]) == 0
    assert [column.name for column in file_columns(SelectedArticleRow)] == list(SelectedArticleRow.model_fields)


@mark.parametrize(
    ("envelope_version", "missing", "exit_code"),
    [
        ("2026-10-10", ("pipeline_name", "task_name"), 0),
        (FileEnvelope.schema_version(), ("pipeline_name", "task_name"), 1),
        ("2026-10-10", ("unit_id",), 1),
    ],
)
def test_writer_columns_follow_the_envelope_version_not_the_row_version(
    tmp_path: Path, capsys: CaptureFixture[str],
    envelope_version: str, missing: tuple[str, ...], exit_code: int,
) -> None:
    site_tree = tmp_path / "site"
    row = fixture_rows(FeedHealthRow)[0]
    (raw,) = ledger.persist(
        site_tree / "state", [row], ledger=LedgerName.FEED_HEALTH,
        covers=row.date, identity=_identity(), fmt=Format.PARQUET,
    )
    metadata, rows = parquet.read(raw.read_bytes())
    columns = tuple(column for column in file_columns(FeedHealthRow) if column.name not in missing)
    raw.write_bytes(parquet.render(
        columns, [{key: value for key, value in cells.items() if key not in missing} for cells in rows],
        envelope={**metadata, b"envelope_version": envelope_version.encode("ascii")},
        compression=Compression.NONE,
    ))

    assert published_columns.check(site_tree, [LedgerName.FEED_HEALTH]) == exit_code
    printed = capsys.readouterr().out
    if exit_code:
        assert all(f"column={name}" in printed for name in missing)
    else:
        assert "history " in printed
        assert "missing [pipeline_name, task_name]" in printed
        stored = ledger.load_stored([raw], model=FeedHealthRow)
        assert stored[0].identity.pipeline_name is None
        assert stored[0].identity.task_name is None


def test_current_host_columns_are_not_exempted_by_an_old_envelope(
    tmp_path: Path, capsys: CaptureFixture[str],
) -> None:
    site_tree, raw = _site_tree_with_host_file(tmp_path)
    metadata, rows = parquet.read(raw.read_bytes())
    columns = _columns_without("pipeline_name")
    raw.write_bytes(parquet.render(
        columns, [{key: value for key, value in cells.items() if key != "pipeline_name"} for cells in rows],
        envelope={**metadata, b"envelope_version": b"2026-10-10"},
        compression=Compression.NONE,
    ))

    assert published_columns.check(site_tree, [LedgerName.HOST_FINGERPRINT]) == 1
    assert "column=pipeline_name" in capsys.readouterr().out


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
    cases: tuple[
        tuple[
            type[RunPlan],
            LedgerName, str, str, str, bool,
        ], ...
    ] = (
        (
            RunPlan, LedgerName.RUN_PLAN, "run-plan/one-day.json",
            "items", "authority_score", True,
        ),
        (
            RunPlan, LedgerName.RUN_PLAN, "run-plan/one-day.json",
            "items", "feed_reliability", True,
        ),
        (
            RunPlan, LedgerName.RUN_PLAN, "run-plan/one-day.json",
            "items", "rank_score", False,
        ),
    )
    for index, (model, which, fixture, column_name, absent, compatible) in enumerate(cases):
        nested_tree = tmp_path / f"nested-{index}"
        row = model.from_json(read_text(CONTRACT_FIXTURES_DIR / fixture))
        (nested_file,) = ledger.persist(
            nested_tree / "state", [row], ledger=which,
            covers=row.date, identity=_identity(), fmt=Format.PARQUET,
        )
        columns = file_columns(model)
        column = next(column for column in columns if column.name == column_name)
        assert isinstance(column.type, LogicalType)
        if column.type.kind == "list":
            item = column.type.item_type
            assert item is not None and item.kind == "struct"
            older_type = replace(column.type, item_type=replace(
                item, fields=tuple(field for field in item.fields if field.name != absent),
            ))
        else:
            older_type = replace(
                column.type,
                fields=tuple(field for field in column.type.fields if field.name != absent),
            )
        older_columns = tuple(
            replace(held, type=older_type) if held.name == column_name else held
            for held in columns
        )
        _rewrite_file(nested_file, columns=older_columns, schema_version="2026-01-01")
        assert published_columns.check(nested_tree, [which]) == (0 if compatible else 1)
        printed = capsys.readouterr().out
        expected_line = (
            "history 2026-01-01:" if compatible else f"FAIL F2 ledger={which.value}"
        )
        assert expected_line in printed
        _rewrite_file(nested_file, columns=older_columns, schema_version=model.schema_version())
        assert published_columns.check(nested_tree, [which]) == 1
        assert f"column={column_name}" in capsys.readouterr().out


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
        f"file_schema={HostFingerprintRow.schema_version()} "
        f"contract_schema={HostFingerprintRow.schema_version()} column=unit_id "
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
    nested_tree = tmp_path / "nested-type-change"
    row = RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan/one-day.json"))
    (nested_file,) = ledger.persist(
        nested_tree / "state", [row], ledger=LedgerName.RUN_PLAN,
        covers=row.date, identity=_identity(), fmt=Format.PARQUET,
    )
    columns = file_columns(RunPlan)
    items = next(column for column in columns if column.name == "items")
    assert isinstance(items.type, LogicalType) and items.type.item_type is not None
    changed_items = replace(items.type, item_type=replace(
        items.type.item_type, fields=tuple(
            replace(field, type=replace(field.type, scalar="string"))
            if field.name == "authority_score" else field for field in items.type.item_type.fields
        ),
    ))
    _rewrite_file(nested_file, columns=tuple(
        replace(column, type=changed_items) if column.name == "items" else column
        for column in columns
    ), schema_version="2026-01-01")
    assert published_columns.check(
        nested_tree, [LedgerName.RUN_PLAN],
    ) == 1
    assert "column=items" in capsys.readouterr().out


def test_f3_newer_file_fails_and_prints(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    site_tree, raw = _site_tree_with_host_file(tmp_path)
    _rewrite_file(raw, columns=file_columns(HostFingerprintRow), schema_version="9999-01-01")

    assert published_columns.check(site_tree, [LedgerName.HOST_FINGERPRINT]) == 1

    printed = capsys.readouterr().out
    assert "published-columns FAIL F3 ledger=host-fingerprint" in printed
    assert (
        f"file_schema=9999-01-01 contract_schema={HostFingerprintRow.schema_version()} column=<not declared> "
        "file_type=<not declared> contract_type=<not declared>; fix: re-pack the file "
        "with this build or run a build at least as new"
    ) in printed


def test_f4_published_ledger_without_door_contract_fails_and_prints(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    assert published_columns.check(tmp_path / "site", [LedgerName.DAY_METRICS]) == 1

    assert capsys.readouterr().out == (
        "published-columns FAIL F4 ledger=day-metrics file=<no file> "
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
