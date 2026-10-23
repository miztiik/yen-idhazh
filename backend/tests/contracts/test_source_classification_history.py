"""Can current readers still read recorded kinds, tiers and scores?"""

import json
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR
from pydantic import TypeAdapter, ValidationError

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import Contract, field_column
from idhazh.contracts.digest_day import DigestDay, DigestItem
from idhazh.contracts.digest_run_fragment import DigestRunFragment
from idhazh.contracts.digest_view import DigestView
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import EntityFeed
from idhazh.ledger.arrow_schema import ColumnType, columns_of

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    ("model", "fixture"),
    [
        (Article, "article/ok.json"),
        (RunPlan, "run-plan/one-day.json"),
        (DigestDay, "digest-day/two-runs.json"),
        (DigestView, "digest-view/one-day.json"),
        (DigestRunFragment, "digest-run-fragment/one-block.json"),
        (ItemHealthRow, "item-health-row/published.json"),
        (Taxonomy, "taxonomy/with-tombstones.json"),
    ],
)
def test_historical_payload_round_trip(model: type[Contract], fixture: str) -> None:
    path: Path = FIXTURES_DIR / "contracts" / fixture
    recorded = model.from_json(path.read_text(encoding="utf-8"))
    assert model.model_validate_json(recorded.to_json()) == recorded


def test_open_identifiers_preserve_historical_wire_types() -> None:
    rows = json.loads(
        (FIXTURES_DIR / "source-classification" / "legacy-ledger-rows.json").read_text(
            encoding="utf-8"
        )
    )
    tier = TypeAdapter(field_column(PlannedItem.model_fields["tier"]))
    kind = TypeAdapter(field_column(DigestItem.model_fields["source_kind"]))
    for row in rows:
        assert tier.validate_python(row["tier"]) == row["tier"]
        assert kind.validate_python(row["source_kind"]) == row["source_kind"]
    assert tier.validate_python(4) == 4
    assert kind.validate_python("independent-review") == "independent-review"
    for invalid in (True, "1", 1.5, 0, -1):
        with pytest.raises(ValidationError):
            tier.validate_python(invalid)
    with pytest.raises(ValidationError):
        kind.validate_python("not a slug")


def test_storage_columns_remain_numeric_and_text() -> None:
    assert (
        next(column for column in columns_of(PlannedItem) if column.name == "tier").type
        is ColumnType.INT64
    )
    assert (
        next(column for column in columns_of(DigestItem) if column.name == "source_kind").type
        is ColumnType.STRING
    )


def test_omitted_historical_fields_keep_their_original_meaning() -> None:
    payload = json.loads(
        (FIXTURES_DIR / "contracts/digest-day/two-runs.json").read_text(encoding="utf-8")
    )
    payload["items"][0].pop("source_kind", None)
    assert DigestDay.model_validate(payload).items[0].source_kind == "reporting"
    assert EntityFeed(id="old-feed", title="Old feed", url="https://example.test/rss").tier == 1


def test_legacy_config_weights_are_read_without_rewriting_the_fixture() -> None:
    path = FIXTURES_DIR / "gardener/pre-yearly-retention/config/idhazh.json"
    app = AppConfig.from_json(path.read_text(encoding="utf-8"))
    legacy = app.collect.legacy_tier_weights
    assert legacy is not None
    assert (legacy.institution, legacy.trade_press, legacy.community) == (1.0, 0.6, 0.3)
    assert "tier_weights" not in json.loads(app.to_json())["collect"]


def test_historical_taxonomy_does_not_gain_unrecorded_registry_fields() -> None:
    path = FIXTURES_DIR / "contracts/taxonomy/with-tombstones.json"
    recorded = path.read_text(encoding="utf-8")
    taxonomy = Taxonomy.from_json(recorded)
    written = taxonomy.to_json()
    assert json.loads(written) == json.loads(recorded)
    assert Taxonomy.from_json(written).to_json() == written
    assert taxonomy.source_kinds == []
    assert taxonomy.source_tiers == []


@pytest.mark.parametrize(("weights", "institution"), [({}, 1.0), ({"institution": 0.5}, 0.5)])
def test_legacy_weight_defaults_keep_their_original_meaning(
    weights: dict[str, float], institution: float
) -> None:
    path = FIXTURES_DIR / "gardener/pre-yearly-retention/config/idhazh.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["collect"]["tier_weights"] = weights
    legacy = AppConfig.model_validate(payload).collect.legacy_tier_weights
    assert legacy is not None
    assert (legacy.institution, legacy.trade_press, legacy.community) == (institution, 0.6, 0.3)
