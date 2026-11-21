"""Does a chart a work shard drew reach the published day when its file stays on the shard's runner?"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from support.paths import CONFIG_DIR, read_text

from idhazh import assemble, config
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision, VisualKind
from idhazh.publication import read_inventory
from idhazh.render.write import asset_relpath

from ._builders import (
    DRAWS_SUMMARIZE_AND_PLAN,
    _work_stage,
    assert_planning_readings,
    assert_reader_accepts,
    drawable_article_fetch,
    finding_the_wind_countries,
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
    with finding_the_wind_countries(config.load(CONFIG_DIR)) as settings:
        run_plan, items, server = _work_stage(
            worker,
            monkeypatch,
            replies=(DRAWS_SUMMARIZE_AND_PLAN.read_bytes(),),
            fetcher=drawable_article_fetch,
            run_plan=plan(item_count=1),
            settings=settings,
        )
    item_id = run_plan.items[0].item_id
    decision = VisualDecision.read(items / f"{item_id}{PAYLOAD_SUFFIX}")
    relpath = asset_relpath(run_plan.date, item_id)
    assert decision.kind is VisualKind.CHART
    assert decision.rationale == (
        "The countries' offshore wind capacity awards share a basis, with Denmark awarding the most."
    )
    assert decision.data_path == relpath
    assert decision.spec is not None
    compiled = VisualData.from_json(decision.spec)
    assert_planning_readings(
        server,
        [
            ("q1", "1200 MW"),
            ("q2", "900 MW"),
            ("q3", "640 MW"),
            ("q4", "410 MW"),
        ],
    )
    marks = {mark.mark_id: mark for mark in compiled.marks}
    assert [marks[name].text for name in compiled.encoding.category] == [
        "Denmark", "Germany", "Poland", "Ireland"
    ]
    assert [Decimal(str(marks[name].value)) for name in compiled.encoding.quantity] == [
        Decimal(1200), Decimal(900), Decimal(640), Decimal(410)
    ]
    assert compiled.emphasized_mark_id == compiled.encoding.quantity[0], "the cited reading"

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
