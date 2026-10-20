"""Can current readers still read recorded kinds, tiers and scores?"""

import json
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR
from pydantic import TypeAdapter, ValidationError

from idhazh.contracts.article import Article
from idhazh.contracts.base import field_column
from idhazh.contracts.digest_day import DigestDay, DigestItem
from idhazh.contracts.digest_view import DigestView
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.run_plan import PlannedItem, RunPlan

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    ("model", "fixture"),
    [
        (Article, "article/ok.json"),
        (RunPlan, "run-plan/one-day.json"),
        (DigestDay, "digest-day/two-runs.json"),
        (DigestView, "digest-view/one-day.json"),
        (ItemHealthRow, "item-health-row/published.json"),
    ],
)
def test_historical_payload_round_trip(model: type, fixture: str) -> None:
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
