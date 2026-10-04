"""Does every Records example question bind against the row contracts of the ledgers it names?

The page offers an example only when every ledger it names is published, and the browser
suite runs only the examples whose ledgers the canary build publishes. So an example over
any other ledger could name a column its ledger never had, or compute something its title
does not say, and nothing would notice until a reader pressed it. Here each ledger an
example names becomes an empty DuckDB table with its row contract's columns and types, and
the statement runs against those tables: a column, a function or a type the contract does
not carry fails the bind before any reader sees it.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pytest
from conftest import REPO_ROOT

from idhazh import config
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.keys import door_contract

pytestmark = pytest.mark.contract

_SCALARS = {"integer": "BIGINT", "number": "DOUBLE", "boolean": "BOOLEAN", "string": "VARCHAR"}


def _column_type(prop: dict[str, Any], defs: dict[str, Any]) -> str:
    """The DuckDB type a contract field is written as, from its JSON schema."""
    if "$ref" in prop:
        return _column_type(defs[prop["$ref"].rsplit("/", 1)[-1]], defs)
    if "anyOf" in prop:
        kinds = [one for one in prop["anyOf"] if one.get("type") != "null"]
        return _column_type(kinds[0], defs) if kinds else "VARCHAR"
    if prop.get("type") == "array":
        return f"{_column_type(prop.get('items', {}), defs)}[]"
    return _SCALARS.get(prop.get("type", "string"), "VARCHAR")


def _empty_ledger(con: duckdb.DuckDBPyConnection, ledger: LedgerName) -> None:
    schema = door_contract(ledger).model_json_schema()
    defs = schema.get("$defs", {})
    columns = ", ".join(
        f'"{name}" {_column_type(prop, defs)}' for name, prop in schema["properties"].items()
    )
    con.execute(f'CREATE TABLE "{ledger.value}" ({columns})')


def _examples() -> list[tuple[str, dict[str, Any]]]:
    committed = config.load(REPO_ROOT / "config").appearance.console.explorer_examples
    defaults = ConsoleConfig().explorer_examples
    return [(f"committed {one['id']}", one) for one in committed] + [
        (f"default {one['id']}", one) for one in defaults
    ]


@pytest.mark.parametrize(("where", "example"), _examples(), ids=[where for where, _ in _examples()])
def test_every_example_binds_against_its_ledgers_row_contracts(
    where: str, example: dict[str, Any]
) -> None:
    ledgers = [LedgerName(name) for name in example["ledgers"]]
    assert ledgers, f"{where} names no ledger"
    con = duckdb.connect()
    for ledger in ledgers:
        _empty_ledger(con, ledger)
    try:
        con.execute(str(example["sql"])).fetchall()
    except duckdb.Error as error:
        pytest.fail(f"{where} does not bind against {example['ledgers']}: {error}")
