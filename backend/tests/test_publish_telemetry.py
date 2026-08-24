from __future__ import annotations

import csv
import inspect
from pathlib import Path

from idhazh import cli
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.publish_telemetry import FORBIDDEN_COLUMNS, PUBLIC_COLUMNS, publish


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
        }
    ]


def test_publish_telemetry_can_seed_an_empty_month(tmp_path: Path) -> None:
    public = tmp_path / "frontend" / "public" / "telemetry"

    written = publish(state_root=tmp_path / "state", public_root=public, ensure_month="2026-08")

    assert [path.name for path in written] == ["2026-08.csv"]
    assert written[0].read_text(encoding="utf-8") == ",".join(PUBLIC_COLUMNS) + "\n"


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