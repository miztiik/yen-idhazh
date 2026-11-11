"""Does a chart a work shard drew reach the published day when its file stays on the shard's runner?"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch
from support.paths import read_text

from idhazh import assemble
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision, VisualKind
from idhazh.publication import read_inventory
from idhazh.render.write import asset_relpath

from ._builders import (
    DRAWS_LABEL,
    DRAWS_SUMMARIZE_AND_PLAN,
    _work_stage,
    assert_planning_references,
    assert_reader_accepts,
    drawable_article_fetch,
    plan,
    publish_worker_items,
)

pytestmark = pytest.mark.visual


def test_assemble_publishes_a_chart_from_its_decision_alone(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Two trees, and only the items directory crosses between them, as in `digest.yml`.

    The work shard draws on a runner that is thrown away, and `items-<shard>` is
    all assemble receives. Run `37212772816` (2026-10-04) also carried each
    shard's whole day directory across to bring the charts, and the merged
    copies of `digest.json` left a file assemble could not read. A test that ran
    both stages in one tree could not tell who wrote the chart; this one fails
    if assemble stops writing it.
    """
    worker = tmp_path / "worker"
    run_plan, items, server = _work_stage(
        worker,
        monkeypatch,
        replies=(DRAWS_LABEL.read_bytes(), DRAWS_SUMMARIZE_AND_PLAN.read_bytes()),
        fetcher=drawable_article_fetch,
        run_plan=plan(item_count=1),
    )
    item_id = run_plan.items[0].item_id
    decision = VisualDecision.read(items / f"{item_id}{PAYLOAD_SUFFIX}")
    relpath = asset_relpath(run_plan.date, item_id)
    assert decision.kind is VisualKind.CHART
    assert decision.data_path == relpath
    assert decision.spec is not None
    compiled = VisualData.from_json(decision.spec)
    references = {mark.element_id for mark in compiled.marks if mark.element_id is not None}
    assert references
    assert_planning_references(server, references)

    publisher = tmp_path / "publisher"
    publish_worker_items(run_plan, items, publisher, monkeypatch)

    public = publisher / "public"
    day = DigestDay.from_json(
        read_text(assemble.day_dir(public / "digest", run_plan.date) / "digest.json")
    )
    named = {item.visual.data_path for item in day.items if item.visual is not None}
    inventoried = {entry.path for entry in read_inventory(public).entries}
    assert relpath in named, f"the published day does not name {relpath}"
    assert (public / relpath).read_bytes() == (worker / "public" / relpath).read_bytes(), (
        f"{relpath} is not the chart the work shard drew"
    )
    assert VisualData.read(public / relpath) == compiled
    assert relpath in inventoried, f"the inventory does not count {relpath}"
    assert_reader_accepts(public / relpath, item_id=item_id)
