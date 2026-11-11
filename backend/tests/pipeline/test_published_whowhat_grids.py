"""A shard's whowhat decision, not its local file, is enough to publish the grid."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch
from support.paths import read_text

from idhazh import assemble
from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision, VisualKind
from idhazh.contracts.whowhat_grid import WhowhatGridData
from idhazh.publication import read_inventory
from idhazh.render.write import asset_relpath

from ._builders import (
    _work_stage,
    assert_planning_references,
    assert_reader_accepts,
    drawable_article_fetch,
    plan,
    publish_worker_items,
    whowhat_replies,
)

pytestmark = pytest.mark.visual

def test_publisher_writes_the_grid_from_the_item_decision_alone(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    worker = tmp_path / "worker"
    run_plan, items, server = _work_stage(
        worker,
        monkeypatch,
        replies=whowhat_replies(),
        fetcher=drawable_article_fetch,
        run_plan=plan(item_count=1),
    )
    item_id = run_plan.items[0].item_id
    article = Article.read(items / f"{item_id}.article.json")
    decision = VisualDecision.read(items / f"{item_id}{PAYLOAD_SUFFIX}")
    assert decision.kind is VisualKind.WHOWHAT
    assert decision.whowhat_grid is not None
    relpath = asset_relpath(run_plan.date, item_id)
    assert decision.data_path == relpath
    pairs = decision.whowhat_grid.rows
    assert [(row.actor.span_excerpt if row.actor else None) for row in pairs] == [
        "Denmark", "Ireland",
    ]
    assert article.text is not None
    for row in pairs:
        assert row.actor is not None and row.claim is not None
        assert row.actor.sentence_index == row.claim.sentence_index
        for span in (row.actor, row.claim):
            assert article.text[span.span_start:span.span_end] == span.span_excerpt
    assert_planning_references(
        server,
        {span.element_id for row in pairs for span in (row.actor, row.claim) if span is not None},
    )

    publisher = tmp_path / "publisher"
    publish_worker_items(run_plan, items, publisher, monkeypatch)
    publisher_public = publisher / "public"
    day = DigestDay.from_json(
        read_text(assemble.day_dir(publisher_public / "digest", run_plan.date) / "digest.json")
    )
    published_item = next(item for item in day.items if item.item_id == item_id)
    assert published_item.visual is not None
    assert published_item.visual.kind == VisualKind.WHOWHAT.value
    assert published_item.visual.data_path == relpath
    published_path = publisher_public / relpath
    assert published_path.read_bytes() == (worker / "public" / relpath).read_bytes()
    assert WhowhatGridData.from_json(read_text(published_path)) == decision.whowhat_grid
    assert relpath in {entry.path for entry in read_inventory(publisher_public).entries}
    assert_reader_accepts(published_path, item_id=item_id)
