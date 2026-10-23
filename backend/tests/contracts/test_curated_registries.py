"""Does a hand-curated registry still read back with the keys and values its contract declares?

Its layout is the curator's own choice and is not checked here. The writer's
layout is checked by `test_record_layouts.py` and `test_json_serialization.py`.
"""

from __future__ import annotations

import json

import pytest
from conftest import CONFIG_DIR, read_text

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
