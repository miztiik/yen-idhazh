"""Hold the pure frontend parser's accepted fields to the native registry models."""

import re
from pathlib import Path

import pytest

from idhazh.contracts.ledgers import LedgerEntry, LedgerFamily, LedgersConfig

pytestmark = pytest.mark.contract

CATALOG = (
    Path(__file__).resolve().parents[3]
    / "frontend" / "src" / "lib" / "data" / "ledger-catalog.ts"
)


def test_frontend_registry_copy_matches_backend_contract() -> None:
    source = CATALOG.read_text(encoding="utf-8")
    fields = {
        "LEDGER_CONFIG_FIELDS": set(LedgersConfig.model_fields),
        "LEDGER_FAMILY_FIELDS": set(LedgerFamily.model_fields),
        "LEDGER_ENTRY_FIELDS": set(LedgerEntry.model_fields),
    }
    for name, expected in fields.items():
        found = re.search(rf"export const {name} = \[(.*?)\] as const;", source, re.S)
        assert found is not None, f"{name} is not declared"
        assert set(re.findall(r"'([^']*)'", found[1])) == expected
