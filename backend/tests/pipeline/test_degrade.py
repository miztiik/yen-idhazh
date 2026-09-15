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

import re
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_DIR, read_text
from pytest import MonkeyPatch

from idhazh.contracts.article import Article, ArticleStatus, TitleSource
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.run_plan import RunPlan
from idhazh.fetch import FetchResult

from ._builders import _work_stage, captured_article_fetch, plan

pytestmark = pytest.mark.slow

LABEL_REPLY: Final = FIXTURES_DIR / "completions" / "label" / "labelled.json"

SUMMARIZE_AND_PLAN_REPLY: Final = (
    FIXTURES_DIR / "completions" / "summarize-and-plan" / "summary-and-plan.json"
)

#: Every element the captured page heads itself with.
_HEADLINES: Final = re.compile(r"<(title|h1|h2)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)


def headless_page_fetch(url: str) -> FetchResult:
    """The captured page with every headline it carries taken out.

    All three elements go, and the third is why: with `<title>` and `<h1>` gone,
    trafilatura's own title extraction reaches the `<h2>` of the page's "Related
    stories" aside and hands back `Related stories`. So a page this stripped is
    what it takes to reach `no_title` at all - a real page that heads itself,
    however badly, now publishes under the headline it gave.
    """
    captured = captured_article_fetch(url)
    stripped = _HEADLINES.sub("", captured.body.decode("utf-8"))
    return replace(captured, body=stripped.encode("utf-8"))


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
    """A day where the feed named nothing and the page names nothing either."""
    run_plan, items, _ = _work_stage(
        tmp_path,
        monkeypatch,
        replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        fetcher=headless_page_fetch,
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
        assert article.title_source is None, planned.item_id


def test_a_feed_that_named_nothing_publishes_under_the_page_s_own_headline(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The same two items, over a page that heads itself - the degradation this fixes.

    Nothing about the feed changed between this test and the one above it. What
    changed is the page, which is the whole point: the headline was in the bytes
    the fetch returned all along, and the item was refused beside it.
    """
    run_plan, items, _ = _work_stage(
        tmp_path,
        monkeypatch,
        replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        run_plan=headless_plan(),
    )

    for planned in run_plan.items[:2]:
        article = Article.from_json(read_text(items / f"{planned.item_id}.article.json"))
        assert article.status is ArticleStatus.OK, planned.item_id
        assert article.title == "Example Grid orders four small modular reactors"
        assert article.title_source is TitleSource.PAGE, planned.item_id


def test_a_sibling_in_the_same_batch_still_reaches_a_summary(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Degrading one item is only degrading if the rest of the shard finishes."""
    run_plan, items = worked_a_headless_day(tmp_path, monkeypatch)

    for planned in run_plan.items[2:]:
        article = Article.from_json(read_text(items / f"{planned.item_id}.article.json"))
        assert article.status is ArticleStatus.OK, planned.item_id
        assert article.title == planned.title
        assert article.title_source is TitleSource.FEED, planned.item_id

    assert list(items.glob("*.summary.json"))
