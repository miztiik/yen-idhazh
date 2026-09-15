"""Does one unusable item take its siblings down with it?

`CLAUDE.md` section 1a says a missing visual, a failed extraction or an
unreachable source degrades that item and never takes down the run. That is a
property of the whole shard rather than of any one function, so it is checked
here over a real work stage - captured pages off disk and recorded replies
played back by a real loopback server, no network and nothing mocked (Guardrail
#7).

The plan is the committed fixture with two items altered, so the run is five
items whatever the archive holds (Guardrail #12).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_DIR, read_text
from pytest import MonkeyPatch

from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.run_plan import RunPlan

from ._builders import _work_stage, plan

pytestmark = pytest.mark.slow

LABEL_REPLY: Final = FIXTURES_DIR / "completions" / "label" / "labelled.json"

SUMMARIZE_AND_PLAN_REPLY: Final = (
    FIXTURES_DIR / "completions" / "summarize-and-plan" / "summary-and-plan.json"
)


def headless_plan() -> RunPlan:
    """The fixture day, with the first item's headline absent and the second's blank.

    Both shapes arrive from a real feed. `discover.clean_title` hands back None
    for an entry with no title element and for one whose title sanitizes to
    nothing, and `rank` plans the item either way - so this is the day's plan as
    a feed with a thin entry would really have written it.
    """
    day = plan()
    items = list(day.items)
    items[0] = items[0].model_copy(update={"title": None})
    items[1] = items[1].model_copy(update={"title": "   "})
    return day.model_copy(update={"items": items})


def worked_a_headless_day(tmp_path: Path, monkeypatch: MonkeyPatch) -> tuple[RunPlan, Path]:
    run_plan, items, _ = _work_stage(
        tmp_path,
        monkeypatch,
        replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        run_plan=headless_plan(),
    )
    return run_plan, items


def test_an_item_with_no_headline_is_recorded_and_its_siblings_still_run(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """This is the defect, and a unit test could never have caught it.

    The extractor used to build an ok payload carrying the planned item's title,
    `Article` refuses an ok payload with no title, and the per-item loop above it
    catches nothing - so one headline-less entry raised out of the stage and the
    other four items were never attempted. The shard reported no items at all.
    """
    run_plan, items = worked_a_headless_day(tmp_path, monkeypatch)

    written = {path.name.removesuffix(".article.json") for path in items.glob("*.article.json")}

    assert written == {item.item_id for item in run_plan.items}


def test_the_headline_that_was_missing_is_the_reason_that_was_recorded(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A degraded item is only useful if it says which knob an operator turns."""
    run_plan, items = worked_a_headless_day(tmp_path, monkeypatch)

    for planned in run_plan.items[:2]:
        article = Article.from_json(read_text(items / f"{planned.item_id}.article.json"))
        assert article.status is ArticleStatus.EXTRACT_FAILED, planned.item_id
        assert article.failure_code is FailureCode.NO_TITLE, planned.item_id


def test_a_sibling_in_the_same_batch_still_reaches_a_summary(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Degrading one item is only degrading if the rest of the shard finishes."""
    run_plan, items = worked_a_headless_day(tmp_path, monkeypatch)

    for planned in run_plan.items[2:]:
        article = Article.from_json(read_text(items / f"{planned.item_id}.article.json"))
        assert article.status is ArticleStatus.OK, planned.item_id
        assert article.title == planned.title

    assert list(items.glob("*.summary.json"))
