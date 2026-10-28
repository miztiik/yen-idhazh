"""A shard's whowhat decision, not its local file, is enough to publish the grid."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

from idhazh import config
from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.element import ElementTable
from idhazh.contracts.summary import Summary
from idhazh.contracts.visual import VisualPlan
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision, VisualKind
from idhazh.contracts.whowhat_grid import WhowhatGridData
from idhazh.render.whowhat_grid import write_whowhat_from_decisions
from idhazh.render.write import asset_relpath, assets_in_day
from idhazh.stages import common
from idhazh.stages.two_calls import _drawn

pytestmark = pytest.mark.visual

DATE = "2026-08-21"
ARTICLE_FIXTURE = FIXTURES_DIR / "visual-validator" / "articles" / "whowhat.txt"
PLAN_FIXTURE = FIXTURES_DIR / "visual-validator" / "plans" / "whowhat.json"
TABLE_FIXTURE = FIXTURES_DIR / "visual-validator" / "tables" / "whowhat.json"


def fixture_article(table: ElementTable) -> Article:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    text = read_text(ARTICLE_FIXTURE).rstrip("\r\n")
    words = len(text.split())
    payload.update(
        {
            "item_id": table.item_id,
            "url_key": table.url_key,
            "canonical_url": table.canonical_url,
            "source_url": table.canonical_url,
            "vertical": table.item_id.split("-", maxsplit=1)[0],
            "text": text,
            "word_count": words,
            "source_word_count": words,
            "token_count": words,
        }
    )
    return Article.model_validate(payload)


def test_publisher_writes_the_grid_from_the_item_decision_alone(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    table = ElementTable.read(TABLE_FIXTURE)
    article = fixture_article(table)
    plan = VisualPlan.read(PLAN_FIXTURE)
    summary_payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    summary_payload.update({"item_id": table.item_id, "url_key": table.url_key})
    summary = Summary.model_validate(summary_payload)

    worker = tmp_path / "worker"
    worker_public = worker / "public"
    monkeypatch.setattr(common, "PUBLIC_ROOT", worker_public / "digest")
    decision = _drawn(
        summary,
        plan,
        table,
        article=article,
        settings=config.load(CONFIG_DIR),
        date=DATE,
        stamp={
            "version": VisualDecision.schema_version(),
            "model_id": "fixture-model",
            "decided_at": "2026-10-28T00:00:00Z",
        },
        run_id="whowhat-fixture",
    )

    assert decision.kind is VisualKind.WHOWHAT
    assert decision.whowhat_grid is not None
    relpath = asset_relpath(DATE, table.item_id)
    assert decision.data_path == relpath
    assert (worker_public / relpath).is_file()

    worker_items = worker / "items"
    worker_items.mkdir(parents=True)
    decision_path = worker_items / f"{table.item_id}{PAYLOAD_SUFFIX}"
    decision_path.write_text(decision.to_json(), encoding="utf-8", newline="\n")

    publisher = tmp_path / "publisher"
    publisher_items = publisher / "run" / DATE / "items"
    shutil.copytree(worker_items, publisher_items)
    handed_off = VisualDecision.read(publisher_items / decision_path.name)
    publisher_public = publisher / "public"
    assert not (publisher_public / relpath).exists(), "the worker's public tree must stay behind"

    day_payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    item = next(item for item in day_payload["items"] if item["item_id"] == "ai-01")
    item["item_id"] = table.item_id
    item["visual"] = {
        "kind": VisualKind.WHOWHAT.value,
        "state": "rendered",
        "data_path": relpath,
        "alt": handed_off.alt_text,
    }
    day = DigestDay.model_validate(day_payload)

    write_whowhat_from_decisions(day, [handed_off], public_root=publisher_public)

    published_path = publisher_public / relpath
    assert published_path.read_bytes() == (worker_public / relpath).read_bytes()
    assert WhowhatGridData.from_json(read_text(published_path)) == handed_off.whowhat_grid
    assert relpath in assets_in_day(publisher_public, DATE)
