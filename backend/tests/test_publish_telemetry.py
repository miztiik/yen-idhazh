from __future__ import annotations

import csv
import inspect
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from pydantic import ValidationError

from idhazh import cli
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.public_telemetry import PublicTelemetryRow
from idhazh.publish_telemetry import (
    FORBIDDEN_COLUMNS,
    PUBLIC_COLUMNS,
    migrate,
    publish,
    read_shard,
)

COMMITTED_SHARDS = sorted((REPO_ROOT / "frontend" / "public" / "telemetry").glob("*.csv"))


def _row(**overrides: object) -> ItemHealthRow:
    payload: dict[str, object] = {
        "version": ItemHealthRow.schema_version(),
        "date": "2026-08-23",
        "run_id": "2026-08-23-1",
        "item_id": "ai-01",
        "url_key": "a" * 64,
        "canonical_url": "https://example.com/story",
        "vertical": "ai",
        "source_id": "example",
        "stage": ItemStage.PUBLISH,
        "outcome": ItemOutcome.OK,
        "code": None,
        "http_status": None,
        "source_chars": 1200,
        "source_words": 180,
        "summary_words": 65,
        "detail": None,
        "fetch_ms": 100,
        "extract_ms": 20,
        "summarize_ms": 600,
    }
    payload.update(overrides)
    return ItemHealthRow.model_validate(payload)


def _write_item_health(state: Path, rows: list[ItemHealthRow]) -> None:
    path = state / "item-health" / "2026-08.csv"
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ItemHealthRow.csv_columns(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(row.csv_row() for row in rows)


def test_publish_telemetry_drops_url_keys_urls_and_detail(tmp_path: Path) -> None:
    state = tmp_path / "state"
    public = tmp_path / "frontend" / "public" / "telemetry"
    _write_item_health(
        state,
        [
            _row(
                stage=ItemStage.EXTRACT,
                outcome=ItemOutcome.FAILED,
                code=FailureCode.UNKNOWN,
                detail="host returned a shape we do not classify yet",
            )
        ],
    )

    written = publish(state_root=state, public_root=public)

    assert [path.name for path in written] == ["2026-08.csv"]
    with written[0].open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or []) == PUBLIC_COLUMNS
        projected = list(reader)
    assert not (FORBIDDEN_COLUMNS & set(projected[0]))
    assert projected == [
        {
            "date": "2026-08-23",
            "run_id": "2026-08-23-1",
            "item_id": "ai-01",
            "vertical": "ai",
            "source_id": "example",
            "stage": "extract",
            "outcome": "failed",
            "code": "unknown",
            "source_words": "180",
            "summary_words": "65",
            "source_words_before_cap": "",
        }
    ]


def test_publish_telemetry_can_seed_an_empty_month(tmp_path: Path) -> None:
    public = tmp_path / "frontend" / "public" / "telemetry"

    written = publish(state_root=tmp_path / "state", public_root=public, ensure_month="2026-08")

    assert [path.name for path in written] == ["2026-08.csv"]
    assert written[0].read_text(encoding="utf-8") == ",".join(PUBLIC_COLUMNS) + "\n"


def test_publish_telemetry_carries_both_word_counts(tmp_path: Path) -> None:
    """The console needs the pre-cap count to say a body was cut.

    It is a word count of our own extraction, the same class as `source_words`,
    which the browser has always had. The three cells the browser never gets -
    canonical_url, url_key and detail - are untouched by this column.
    """
    state = tmp_path / "state"
    public = tmp_path / "frontend" / "public" / "telemetry"
    _write_item_health(
        state, [_row(source_words=1923, source_words_before_cap=2610), _row(item_id="ai-02")]
    )

    written = publish(state_root=state, public_root=public)

    with written[0].open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert "source_words_before_cap" in (reader.fieldnames or [])
        projected = list(reader)
    assert not (FORBIDDEN_COLUMNS & set(projected[0]))
    assert projected[0]["source_words_before_cap"] == "2610"
    assert int(projected[0]["source_words_before_cap"]) > int(projected[0]["source_words"])
    assert projected[1]["source_words_before_cap"] == ""


def test_the_pipeline_never_writes_the_committed_telemetry_projection(tmp_path: Path) -> None:
    """A test run must not rewrite published bytes.

    `stage_assemble` used the module default for `public_root`, so driving the
    pipeline from a temporary tree still truncated the committed projection in
    `frontend/public/telemetry/`. A dirty tree is what aborts the publish push
    and discards a day, so the default must never reach a caller that passed
    its own roots.
    """
    source = inspect.getsource(cli.stage_assemble)

    assert "publish_telemetry.publish(" in source
    assert "public_root=" in source.split("publish_telemetry.publish(", 1)[1][:200]


def test_the_projection_carries_the_contract_header_and_no_version_cell() -> None:
    """`version` is a field of the shape and never a cell.

    The browser checks the header as a prefix, so a name at position zero would
    shift every position the console reads and blank its charts on every cached
    bundle.
    """
    assert PUBLIC_COLUMNS == PublicTelemetryRow.csv_columns()
    assert "version" in PublicTelemetryRow.model_fields
    assert "version" not in PUBLIC_COLUMNS
    assert not FORBIDDEN_COLUMNS & set(PublicTelemetryRow.model_fields)


def test_every_committed_shard_reads_back_through_the_contract() -> None:
    """The migration's oracle, on the published files themselves.

    A published shard is the one artifact nobody can re-derive once its source
    month has been folded away, so "it still parses" is not the question - the
    question is whether every row loads through the shape that now owns it.
    """
    assert COMMITTED_SHARDS, "the committed projection has no shards to migrate"
    for path in COMMITTED_SHARDS:
        rows = read_shard(path)
        assert rows, f"{path.name} published no rows"
        assert all(isinstance(row, PublicTelemetryRow) for row in rows)
        assert b"\r" not in path.read_bytes(), f"{path.name} must be LF"


def test_migrating_the_committed_shards_changes_no_byte(tmp_path: Path) -> None:
    """The migration is a read-back, so it must be a no-op on bytes.

    Run against a copy rather than the committed tree: a dirty working tree is
    what aborts the publish push and discards a day.
    """
    public = tmp_path / "telemetry"
    public.mkdir()
    before = {path.name: path.read_bytes() for path in COMMITTED_SHARDS}
    for path in COMMITTED_SHARDS:
        (public / path.name).write_bytes(before[path.name])

    results = migrate(public)

    assert [path.name for path, _, _ in results] == [path.name for path in COMMITTED_SHARDS]
    for path, rows, unchanged in results:
        assert unchanged, f"{path.name} did not survive its own round trip"
        assert rows > 0
        assert path.read_bytes() == before[path.name]


def test_a_published_failure_without_a_reason_is_refused() -> None:
    """The console groups failures by code, so a bar it cannot label is not a row."""
    with pytest.raises(ValidationError, match="failure code"):
        PublicTelemetryRow.from_csv_row(
            {
                "date": "2026-09-01",
                "run_id": "2026-09-01-1",
                "item_id": "ai-01",
                "vertical": "ai",
                "source_id": "example",
                "stage": "fetch",
                "outcome": "failed",
                "code": "",
                "source_words": "",
                "summary_words": "",
                "source_words_before_cap": "",
            }
        )
