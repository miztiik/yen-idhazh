"""Does a chart a work shard drew reach the published day when its file stays on the shard's runner?"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text
from pytest import MonkeyPatch

from idhazh import assemble, config
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision
from idhazh.publication import read_inventory
from idhazh.stages.assemble import stage_assemble

from ._builders import (
    DRAWS_LABEL,
    DRAWS_SUMMARIZE_AND_PLAN,
    drawable_article_fetch,
    isolate_ledgers,
    worked,
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
    run_plan, items, _ = worked(
        worker,
        monkeypatch,
        replies=(DRAWS_LABEL.read_bytes(), DRAWS_SUMMARIZE_AND_PLAN.read_bytes()),
        fetcher=drawable_article_fetch,
    )
    drawn = [
        decision.data_path
        for decision in (
            VisualDecision.read(path) for path in sorted(items.glob(f"*{PAYLOAD_SUFFIX}"))
        )
        if decision.data_path is not None
    ]
    assert drawn, "the recorded pair drew no chart, so this test would assert nothing"

    publisher = tmp_path / "publisher"
    isolate_ledgers(publisher, monkeypatch)
    shutil.copytree(items, publisher / "run" / run_plan.date / "items")
    stage_assemble(
        run_plan, settings=config.load(CONFIG_DIR), commit_sha="a" * 40, runner="fixture"
    )

    public = publisher / "public"
    day = DigestDay.from_json(
        read_text(assemble.day_dir(public / "digest", run_plan.date) / "digest.json")
    )
    named = {item.visual.data_path for item in day.items if item.visual is not None}
    inventoried = {entry.path for entry in read_inventory(public).entries}
    for relpath in drawn:
        assert relpath in named, f"the published day does not name {relpath}"
        assert (public / relpath).read_bytes() == (worker / "public" / relpath).read_bytes(), (
            f"{relpath} is not the chart the work shard drew"
        )
        assert relpath in inventoried, f"the inventory does not count {relpath}"
