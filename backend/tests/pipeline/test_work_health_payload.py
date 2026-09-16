"""Does the row a shard recorded outlive the process that recorded it?

The recorder validates 113 cells an item at a time and used to hand them to a
log line and to nothing else. A log line is a CI artifact that expires, so the
census was rebuilt later out of the article and the summary payloads, which
between them cannot carry most of those cells. These tests read the file the
work stage now leaves beside those payloads, over a real work stage against
captured pages and recorded replies - no network and nothing mocked
(Guardrail #7).

Sibling question, sibling module: `test_work_records.py` asks what a shard SAYS
while it runs. This one asks what SURVIVES it.

The day every test here is driven from is the fixture plan's, so the volume is
five items and the cost does not move when the archive grows (Guardrail #12).
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text
from pytest import LogCaptureFixture, MonkeyPatch

from idhazh import config
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages import common
from idhazh.stages.work import stage_work
from idhazh.telemetry.record import HEALTH_SUFFIX

from ._builders import _work_stage, captured_article_fetch, closed_loopback_endpoint, plan
from .test_degrade import headless_page_fetch, headless_plan

pytestmark = pytest.mark.slow

#: The fixture plan's size. Named once so a sixth item moves one line.
PLANNED_ITEMS: Final = 5

LABEL_REPLY: Final = FIXTURES_DIR / "completions" / "label" / "labelled.json"

SUMMARIZE_AND_PLAN_REPLY: Final = (
    FIXTURES_DIR / "completions" / "summarize-and-plan" / "summary-and-plan.json"
)


def worked(
    tmp_path: Path, monkeypatch: MonkeyPatch, *, degraded: bool = False
) -> tuple[RunPlan, Path]:
    """One real work stage, and the items directory it wrote."""
    run_plan, items_dir, _ = _work_stage(
        tmp_path,
        monkeypatch,
        replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        fetcher=headless_page_fetch if degraded else captured_article_fetch,
        run_plan=headless_plan() if degraded else None,
    )
    return run_plan, items_dir


def rows(items_dir: Path) -> dict[str, ItemHealthRow]:
    """Every persisted census row, by the item it describes.

    Read inside the test rather than at module scope, so an unexpected shape
    fails the test that wanted it instead of the whole file (CLAUDE.md section
    13).
    """
    return {
        path.name.removesuffix(HEALTH_SUFFIX): ItemHealthRow.from_json(read_text(path))
        for path in sorted(items_dir.glob(f"*{HEALTH_SUFFIX}"))
    }


def closed(caplog: LogCaptureFixture) -> list[dict[str, Any]]:
    """Every `item.done` record the run emitted, parsed.

    Flat records are one JSON object with no `ctx`, so the nested events sharing
    this logger are dropped by shape rather than by name.
    """
    found: list[dict[str, Any]] = []
    for line in caplog.messages:
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        if "ctx" not in payload and payload.get("name") == "item.done":
            found.append(payload)
    return found


def test_every_item_the_shard_closed_left_its_row_on_disk(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """One row an item, and no row for an item the plan never named.

    The bijection is the assertion. A file for four of five items is a shard
    that measured an item and dropped it, which is the defect this payload
    exists to end, and a sixth file is a row about an item nobody planned.
    """
    run_plan, items_dir = worked(tmp_path, monkeypatch)

    assert set(rows(items_dir)) == {item.item_id for item in run_plan.items}
    assert len(run_plan.items) == PLANNED_ITEMS


def test_the_file_is_the_row_the_shard_reported_cell_for_cell(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """The log and the file have to be one reading, not two.

    The log line is the only account of a shard that anybody trusted before this
    payload existed. If the two ever disagree, a reader has no way to tell which
    one measured the item - so the test compares all 113 cells rather than the
    handful a caller happens to use.
    """
    caplog.set_level(logging.INFO, logger="idhazh")
    _, items_dir = worked(tmp_path, monkeypatch)

    written = rows(items_dir)
    reported = closed(caplog)

    assert len(reported) == PLANNED_ITEMS
    for record in reported:
        said = ItemHealthRow.model_validate(
            {column: record[column] for column in ItemHealthRow.csv_columns()}
        )
        assert json.loads(written[said.item_id].to_json()) == json.loads(said.to_json())


def test_an_item_that_failed_extraction_still_leaves_a_row(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The failing item is the one worth measuring, and it stops earliest.

    An item with no headline never reaches the model, so the work stage closes
    its record on a branch of its own. That branch is where a payload written at
    one call site only would go missing, and a shard whose failures are the rows
    that did not survive is a shard that reports a clean day.
    """
    run_plan, items_dir = worked(tmp_path, monkeypatch, degraded=True)

    written = rows(items_dir)

    assert set(written) == {item.item_id for item in run_plan.items}
    for planned in run_plan.items[:2]:
        row = written[planned.item_id]
        assert row.outcome is ItemOutcome.FAILED, planned.item_id
        assert row.code is FailureCode.NO_TITLE, planned.item_id


def test_an_item_the_shard_abandoned_leaves_a_row_too(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """An item that never ran is a measurement, and it is the only one there is.

    A shard that stops on its own clock appends nothing to the list it hands the
    slowest-item reading, deliberately - an item that never ran has no duration
    to be slowest. So this branch is the one place the payload cannot be written
    from the list of finished items, and the only proof it was written is a file
    for an item that produced nothing else.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    out_of_time = replace(
        settings,
        app=settings.app.model_copy(
            update={
                "run": settings.app.run.model_copy(
                    update={"shard_timeout_minutes": 1, "shard_wrap_up_minutes": 1}
                )
            }
        ),
    )
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")

    stage_work(
        run_plan,
        settings=out_of_time,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )

    written = rows(tmp_path / "run" / run_plan.date / "items")

    assert set(written) == {item.item_id for item in run_plan.items}
    assert {row.code for row in written.values()} == {FailureCode.SHARD_OUT_OF_TIME}
