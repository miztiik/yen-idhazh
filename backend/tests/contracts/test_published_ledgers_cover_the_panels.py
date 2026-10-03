"""Is every ledger the typed browser query accepts published by the site?"""

from __future__ import annotations

import re

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh.contracts.app_config import AppConfig

pytestmark = pytest.mark.contract


def test_every_ledger_the_door_can_be_asked_for_is_published() -> None:
    """The TypeScript compiler restricts callers to this closed set of names."""
    shapes = REPO_ROOT / "frontend" / "src" / "lib" / "data" / "slice-shapes.ts"
    found = re.search(
        r"export const LEDGER_NAMES = \[(.*?)\] as const;", read_text(shapes), re.DOTALL
    )
    assert found, f"{shapes.name} no longer declares LEDGER_NAMES as a frozen array"
    names = set(re.findall(r"'([^']*)'", found[1]))
    assert names, f"{shapes.name} names no ledger"
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    published = {ledger.value for ledger in committed.ledger.published}
    assert names <= published, (
        f"{shapes.name} lets a panel ask for {sorted(names - published)}, "
        "which config/idhazh.json does not publish."
    )
