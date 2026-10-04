
import re
from pathlib import Path

from idhazh.contracts.ledgers import LedgerEntry, LedgerFamily

ROOT = Path(__file__).resolve().parents[3]
REGISTRY_TS = ROOT / "frontend" / "src" / "lib" / "console" / "explorer" / "registry.ts"


def fields_from_type(source: str, name: str) -> set[str]:
    match = re.search(rf"export type {name} = \{{(?P<body>.*?)\}};", source, re.S)
    assert match is not None, f"{name} is not declared"
    return set(re.findall(r"^\s*([a-z_]+):", match.group("body"), re.M))


def test_frontend_registry_copy_matches_backend_contract() -> None:
    source = REGISTRY_TS.read_text(encoding="utf-8")
    assert fields_from_type(source, "RegistryFamily") == set(LedgerFamily.model_fields)
    assert fields_from_type(source, "RegistryLedger") == {"name", "grain"}
    assert {"name", "grain"}.issubset(LedgerEntry.model_fields)
