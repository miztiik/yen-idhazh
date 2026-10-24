"""Do configuration-only source extensions reach scoring, publication and display?"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, REPO_ROOT

from idhazh import assemble
from idhazh.config import load
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.discover import Candidate
from idhazh.rank import authority_terms, plan_vertical

from ._fixtures import copy_config

pytestmark = pytest.mark.contract


def read(root: Path, name: str) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((root / name).read_text(encoding="utf-8"))
    return value


def write(root: Path, name: str, value: dict[str, Any]) -> None:
    (root / name).write_text(json.dumps(value), encoding="utf-8")


def extended_config(tmp_path: Path) -> Path:
    copy_config(tmp_path)
    root = tmp_path / "config"
    taxonomy = read(root, "taxonomy.json")
    taxonomy["source_kinds"].append(
        {
            **taxonomy["source_kinds"][1],
            "id": "independent-review",
            "display_name": "Independent review",
        }
    )
    taxonomy["source_tiers"].append(
        {**taxonomy["source_tiers"][0], "id": 4, "display_name": "Review", "weight": 0.8}
    )
    write(root, "taxonomy.json", taxonomy)
    sources = read(root, "sources.json")
    sources["feeds"][0].update(kind="independent-review", tier=4)
    write(root, "sources.json", sources)
    return root


def frontend_copies(definitions: list[dict[str, Any]]) -> dict[str, Any]:
    script = """
import {sourceKindCopy, sourceKindLabels, visibleSourceKinds}
    from './frontend/src/lib/bands.ts';
const definitions = JSON.parse(process.argv[1]);
console.log(JSON.stringify({
  labels: sourceKindLabels(definitions),
  visible: visibleSourceKinds(definitions),
  custom: sourceKindCopy('independent-review', definitions),
  missing: sourceKindCopy('old-publisher-kind', definitions)
}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, json.dumps(definitions)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    value: dict[str, Any] = json.loads(result.stdout)
    return value


def test_frontend_kind_vocabulary_comes_from_the_same_registry() -> None:
    settings = load()
    definitions = [entry.model_dump(mode="json") for entry in settings.taxonomy.source_kinds]
    copies = frontend_copies(definitions)
    assert copies["labels"] == {entry["id"]: entry["display_name"] for entry in definitions}
    assert copies["visible"] == [entry["id"] for entry in definitions if entry["show_on_item"]]
    assert copies["missing"] == {
        "label": "old-publisher-kind (unregistered source kind)",
        "showOnItem": True,
        "registered": False,
    }


def test_config_only_extension_reaches_plan_publication_and_frontend(tmp_path: Path) -> None:
    root = extended_config(tmp_path)
    settings = load(root)
    feed = settings.sources.feeds[0]
    candidate = Candidate(
        canonical_url="https://example.test/registry",
        source_url="https://example.test/registry",
        url_key=derive_url_key("https://example.test/registry"),
        source_id=feed.id,
        vertical=feed.vertical,
        tier=feed.tier,
        source_form=feed.form,
        title="An independent review",
        published_at="2026-10-20T06:00:00Z",
        weight=feed.weight,
    )
    assert authority_terms(candidate, settings.app.collect).tier_score == 0.8
    vertical = settings.taxonomy.vertical(feed.vertical)
    assert vertical is not None
    planned = plan_vertical(
        vertical,
        [candidate],
        config=settings.app.collect,
        eligible_feeds=vertical.min_feeds,
        now="2026-10-20T07:00:00Z",
    ).items[0]
    assert planned.tier == 4
    assert planned.tier_score == 0.8
    article = Article.from_json(
        (CONTRACT_FIXTURES_DIR / "article/ok.json").read_text(encoding="utf-8")
    ).model_copy(
        update={
            "source_id": feed.id,
            "tier": 4,
            "item_id": planned.item_id,
            "vertical": feed.vertical,
        }
    )
    summary = Summary.from_json(
        (CONTRACT_FIXTURES_DIR / "summary/ok.json").read_text(encoding="utf-8")
    ).model_copy(update={"item_id": planned.item_id})
    item = assemble.to_digest_item(
        article=article,
        summary=summary,
        band=ConfidenceBand.HIGH,
        source_name=feed.title,
        source_kind=feed.kind,
        run_n=1,
        planned=planned,
    )
    assert DigestItem.model_validate_json(item.model_dump_json()).source_kind == feed.kind
    assert item.rank_score == planned.rank_score
    copies = frontend_copies(
        [entry.model_dump(mode="json") for entry in settings.taxonomy.source_kinds]
    )
    assert copies["custom"] == {
        "label": "Independent review",
        "showOnItem": True,
        "registered": True,
    }
    changed = read(root, "taxonomy.json")
    changed["source_tiers"][-1]["weight"] = 0.2
    write(root, "taxonomy.json", changed)
    assert authority_terms(candidate, load(root).app.collect).tier_score == 0.2
    assert planned.tier_score == 0.8


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ("missing-weight", "weight"),
        ("duplicate-kind", "source kind ids"),
        ("duplicate-tier", "source tier ids"),
        ("unknown-kind", "independent-review"),
        ("unknown-tier", "tier 4"),
        ("default-kind", "default_source_kind"),
        ("default-tier", "default_entity_tier"),
        ("nonfinite-weight", "finite"),
        ("invalid-property", "invented_rule"),
        ("inactive-kind", "independent-review"),
        ("conflicting-legacy-weight", "conflicts"),
    ],
)
def test_invalid_registry_refuses_loading_by_name(tmp_path: Path, change: str, error: str) -> None:
    root = extended_config(tmp_path)
    taxonomy = read(root, "taxonomy.json")
    if change == "missing-weight":
        del taxonomy["source_tiers"][-1]["weight"]
    elif change == "duplicate-kind":
        taxonomy["source_kinds"].append(taxonomy["source_kinds"][-1])
    elif change == "duplicate-tier":
        taxonomy["source_tiers"].append(taxonomy["source_tiers"][-1])
    elif change == "unknown-kind":
        taxonomy["source_kinds"].pop()
    elif change == "unknown-tier":
        taxonomy["source_tiers"].pop()
    elif change == "default-kind":
        taxonomy["default_source_kind"] = "missing-kind"
    elif change == "default-tier":
        taxonomy["default_entity_tier"] = 99
    elif change == "nonfinite-weight":
        taxonomy["source_tiers"][-1]["weight"] = float("inf")
    elif change == "invalid-property":
        taxonomy["source_kinds"][-1]["invented_rule"] = True
    elif change == "inactive-kind":
        taxonomy["source_kinds"][-1]["status"] = "draft"
    elif change == "conflicting-legacy-weight":
        app = read(root, "idhazh.json")
        app["collect"]["tier_weights"] = {
            "institution": 0.9,
            "trade_press": 0.6,
            "community": 0.3,
        }
        write(root, "idhazh.json", app)
    write(root, "taxonomy.json", taxonomy)
    with pytest.raises((ValueError, ValidationError), match=error):
        load(root)


def test_configured_defaults_apply_only_to_authored_config(tmp_path: Path) -> None:
    root = extended_config(tmp_path)
    taxonomy = read(root, "taxonomy.json")
    taxonomy.update(default_source_kind="independent-review", default_entity_tier=4)
    write(root, "taxonomy.json", taxonomy)
    sources = read(root, "sources.json")
    sources["feeds"][0].pop("kind")
    sources["feeds"][1]["kind"] = "reporting"
    write(root, "sources.json", sources)
    watchlist = read(root, "watchlist.json")
    watchlist["entities"][0]["feeds"] = [
        {
            "id": "entity-review-default",
            "title": "Entity review default",
            "url": "https://example.test/feed",
        },
        {
            "id": "entity-review-explicit",
            "title": "Entity review explicit",
            "url": "https://example.test/second-feed",
            "tier": 2,
        },
    ]
    write(root, "watchlist.json", watchlist)
    settings = load(root)
    assert settings.sources.feeds[0].kind == "independent-review"
    assert settings.sources.feeds[1].kind == "reporting"
    assert settings.watchlist.entities[0].feeds[0].tier == 4
    assert settings.watchlist.entities[0].feeds[1].tier == 2
    historical = Taxonomy.from_json(
        (CONTRACT_FIXTURES_DIR / "taxonomy/with-tombstones.json").read_text(encoding="utf-8")
    )
    assert historical.source_kinds == []
