"""Does a hand-curated registry still read back with the keys and values its contract declares?

Its layout is the curator's own choice and is not checked here. The writer's
layout is checked by `test_record_layouts.py` and `test_json_serialization.py`.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError
from support.paths import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh.contracts.base import Contract
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

pytestmark = pytest.mark.contract

#: The three registries a person writes by hand. Each is lists of short records
#: read together or not at all, so each is written one record a line. Every
#: other payload here is written by a program and keeps the field-a-line
#: layout, which is the right shape for reading down a single record.
CURATED: dict[str, type[Contract]] = {
    "sources.json": Sources,
    "taxonomy.json": Taxonomy,
    "watchlist.json": Watchlist,
}


@pytest.mark.parametrize("name", sorted(CURATED), ids=lambda n: n)
def test_a_curated_registry_survives_a_read_and_a_rewrite(name: str) -> None:
    """A hand-edited config holds exactly the keys and values its contract writes.

    Every field is present even at its default, and no key is unknown: the
    contract refuses unknown keys on read. Whitespace is not compared, so a
    curator may reflow a record without breaking this test.
    """
    text = read_text(CONFIG_DIR / name)
    rewritten = CURATED[name].from_json(text).to_json()
    assert json.loads(rewritten) == json.loads(text), (
        f"config/{name} does not hold the keys and values its contract writes"
    )


@pytest.mark.parametrize(
    ("name", "records", "index", "default_field"),
    [
        pytest.param("sources.json", "feeds", 1, "weight", id="sources.json"),
        pytest.param("taxonomy.json", "verticals", 1, "floor", id="taxonomy.json"),
        pytest.param("watchlist.json", "entities", 0, "kind", id="watchlist.json"),
    ],
)
def test_a_controlled_registry_survives_a_read_and_a_rewrite(
    name: str, records: str, index: int, default_field: str
) -> None:
    """Native readers preserve chosen values and order, including an omitted default."""
    expected = json.loads(read_text(FIXTURES_DIR / "curated-registries" / name))
    expected["version"] = CURATED[name].schema_version()
    authored = deepcopy(expected)
    del authored["version"]
    del authored[records][index][default_field]

    rewritten = CURATED[name].from_json(json.dumps(authored)).to_json()
    assert json.loads(rewritten) == expected, f"{name} lost a chosen key, value or list order"
    assert CURATED[name].from_json(rewritten).model_dump(mode="json") == expected, (
        f"{name} changed values on the next read"
    )
    if name == "sources.json":
        legacy = deepcopy(authored)
        legacy.pop("publishers", None)
        for feed in [*legacy["feeds"], *legacy.get("retired", [])]:
            feed.pop("publisher_id", None)
            feed.pop("added_on", None)
            feed.pop("retirement_reason", None)
        legacy_sources = Sources.from_json(json.dumps(legacy))
        assert legacy_sources.publishers == []
        assert all(feed.publisher_id is None for feed in legacy_sources.feeds)

        publisher = {
            "id": "reviewed-publication", "display_name": "Reviewed Publication",
        }
        mapped = deepcopy(authored)
        mapped["publishers"] = [publisher]
        mapped["feeds"][0]["publisher_id"] = publisher["id"]
        assert Sources.model_validate(mapped).feeds[0].publisher_id == publisher["id"]
        assert Sources.model_validate(mapped).publishers[0].model_dump(mode="json") == publisher
        with pytest.raises(ValidationError, match="publisher ids must be distinct"):
            Sources.model_validate({**mapped, "publishers": [publisher, publisher]})
        with pytest.raises(ValidationError, match="must reference a defined publisher"):
            Sources.model_validate({
                **mapped, "feeds": [{**mapped["feeds"][0], "publisher_id": "missing-publication"}],
            })
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Sources.model_validate({
                **mapped,
                "publishers": [{**publisher, "status": "retired"}],
            })

        assert all(feed.added_on is None for feed in legacy_sources.retired)
        assert all(feed.retirement_reason is None for feed in legacy_sources.retired)
        retired_feed = deepcopy(mapped)
        retired_feed["retired"][0]["added_on"] = "2026-09-10"
        retired_feed["retired"][0]["retirement_reason"] = "feed retired"
        parsed_retirement = Sources.model_validate(retired_feed).retired[0]
        assert parsed_retirement.added_on == "2026-09-10"
        assert parsed_retirement.retirement_reason == "feed retired"
        incomplete_retirement = deepcopy(mapped)
        incomplete_retirement["retired"][0]["added_on"] = "2026-09-10"
        with pytest.raises(ValidationError, match="newly retired feed"):
            Sources.model_validate(incomplete_retirement)
        active_with_reason = deepcopy(mapped)
        active_with_reason["feeds"][0]["retirement_reason"] = "feed retired"
        with pytest.raises(ValidationError, match="only meaningful on a retired feed"):
            Sources.model_validate(active_with_reason)
        with pytest.raises(ValidationError, match="lowercase"):
            Sources.model_validate({
                **mapped,
                "retired": [{
                    **mapped["retired"][0], "added_on": "2026-09-10",
                    "retirement_reason": "Feed Retired",
                }],
            })
        with pytest.raises(ValidationError, match="retired_on cannot precede added_on"):
            Sources.model_validate({
                **mapped,
                "retired": [{
                    **mapped["retired"][0], "added_on": "2026-09-20",
                    "retirement_reason": "feed retired",
                }],
            })
