"""Can registered contracts import anything outside their own package?"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from conftest import read_text

from idhazh.contracts import CONTRACTS
from idhazh.contracts.base import Contract

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_contracts_import_no_other_subpackage(contract: type[Contract]) -> None:
    """Read the module of one registered document, never discover source files."""
    module = Path(inspect.getfile(contract))
    tree = ast.parse(read_text(module), filename=str(module))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            if name.startswith("idhazh.") and not name.startswith("idhazh.contracts"):
                pytest.fail(f"{module.name} imports {name}")
