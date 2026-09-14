"""How does a published item carry a desk without losing the feed's own word?"""

from __future__ import annotations

import pytest
from conftest import CONFIG_DIR

from idhazh import assemble, config
from idhazh.contracts.article import Article
from idhazh.contracts.taxonomy import SourceKind

from ._builders import (
    article,
    digest_item,
    plan,
    row,
    summary,
)

pytestmark = pytest.mark.slow


#
# Row #6 of TODO/20260910-23-article-classification-plan.md, at the stage that
# builds a published item and a published day. Every case is built from the
# committed contract fixtures in memory; nothing reads the digest tree.


def relabelled_article() -> Article:
    """An energy feed's story about compute, addressed from the feed's word.

    `model_copy` rather than a new Article, so the url_key and every other field
    stay the fixture's own - the only thing under test is which of the two words
    ends up where.
    """
    return article().model_copy(
        update={"item_id": "energy-01", "vertical": "energy", "desk": "ai"}
    )

def test_a_published_item_carries_the_desk_and_keeps_the_feeds_address() -> None:
    """The oracle, at the stage that writes the item.

    The desk is what the day publishes it under. `item_id` is addressed from
    `vertical`, which did not move - so a link somebody shared this morning
    still resolves this evening.
    """
    item = assemble.to_digest_item(
        article=relabelled_article(),
        summary=summary().model_copy(update={"item_id": "energy-01"}),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
    )

    assert item.vertical == "energy"
    assert item.desk == "ai"
    assert item.item_id.startswith("energy-")

def test_an_unlabelled_article_publishes_with_no_desk_at_all() -> None:
    """Nothing fills `desk` yet, and the published item may not invent one.

    Null is unknown, and the page falls back to the vertical. A default here
    would make every item claim a reading of itself that never happened.
    """
    item = assemble.to_digest_item(
        article=article(),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
    )

    assert item.desk is None

def test_a_story_relabelled_onto_a_desk_that_will_not_render_stays_put() -> None:
    """Decision 8, at the stage that decides it.

    A vertical under its feed floor is collected and never rendered. Letting
    another vertical's stories land there would render a topic the same day's
    payload flags as having planned nothing.
    """
    item = assemble.to_digest_item(
        article=relabelled_article(),
        summary=summary().model_copy(update={"item_id": "energy-01"}),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
        below_floor_desks=frozenset({"ai"}),
    )

    assert item.desk == "energy", "the feed floor is about supply, and supply is per feed"

def test_a_day_lists_both_words_and_counts_each_under_its_own() -> None:
    """`count` is the feed's word; `desk_count` is what the page draws.

    Both names are owed a ref. The vertical needs one because `count` is a
    statement about its feeds, and the desk needs one because the page draws a
    heading, a pill and a route from it - so a day that listed only the desk
    would publish a count with nothing to attach it to, and one that listed only
    the vertical would render a story under a nameless topic.
    """
    day = assemble.build_day(
        plan=plan(),
        items=[
            assemble.to_digest_item(
                article=relabelled_article(),
                summary=summary().model_copy(update={"item_id": "energy-01"}),
                band=row().band,
                source_name="Example Lab",
                source_kind=SourceKind.REPORTING,
                run_n=1,
            )
        ],
        previous=None,
        taxonomy=config.load(CONFIG_DIR).taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    refs = {ref.id: ref for ref in day.verticals}
    assert set(refs) == {"ai", "energy"}
    assert refs["energy"].count == 1, "the feed that carried it still declares energy"
    assert refs["energy"].desk_count == 0, "and the page draws nothing under energy"
    assert refs["ai"].count == 0, "no ai feed carried this story"
    assert refs["ai"].desk_count == 1, "the reader finds it under ai"
    assert refs["ai"].display_name, "a desk a reader can reach needs a name to reach it by"

def test_a_day_nothing_relabelled_publishes_the_same_two_numbers() -> None:
    """The ordinary day, which is every day published so far.

    `desk_count` is written on every day from now on rather than only when it
    differs, so a page never has to ask whether this day is one of the ones that
    said - and on a day nothing relabelled the two numbers agree.
    """
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=config.load(CONFIG_DIR).taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    assert day.verticals
    for ref in day.verticals:
        assert ref.desk_count == ref.count
