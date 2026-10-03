"""Does exactly one module import the parquet engine, and is it the one the door names?

An AST walk over every Python module under `backend/idhazh/` and
`frontend/src/`, not a grep: this file names the engine, and a grep would count
its own lines. What it guards is that the engine stays swappable - the moment a
second module imports pyarrow, replacing it stops being a one-file change.
"""

from __future__ import annotations

import ast
from typing import Final

import pytest
from _source_files import source_files
from conftest import REPO_ROOT

pytestmark = pytest.mark.contract

#: The engine's top-level package name, and the one module allowed to import it.
ENGINE: Final = "pyarrow"
THE_ONE_IMPORTER: Final = "backend/idhazh/ledger/parquet.py"

#: Every tree whose code could reach the engine. The frontend holds no Python
#: today, so its half finds nothing; it is walked so a Python file added there
#: tomorrow is held to the same rule.
WALKED: Final = (REPO_ROOT / "backend" / "idhazh", REPO_ROOT / "frontend" / "src")


def _engine_imports(tree: ast.Module) -> list[int]:
    """The lines where this module imports the engine, in either spelling."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            lines.extend(
                node.lineno
                for alias in node.names
                if alias.name == ENGINE or alias.name.startswith(f"{ENGINE}.")
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            if node.module == ENGINE or node.module.startswith(f"{ENGINE}."):
                lines.append(node.lineno)
    return lines


def _every_import_of_the_engine() -> dict[str, list[int]]:
    """Every module that imports the engine -> the lines where it does."""
    found: dict[str, list[int]] = {}
    for path in source_files(roots=WALKED, suffixes=(".py",)):
        lines = _engine_imports(ast.parse(path.read_text(encoding="utf-8")))
        if lines:
            found[path.relative_to(REPO_ROOT).as_posix()] = lines
    return found


def test_exactly_one_import_of_the_engine_and_it_is_in_the_parquet_module() -> None:
    found = _every_import_of_the_engine()

    assert set(found) == {THE_ONE_IMPORTER}, (
        f"pyarrow is imported by {sorted(found)}. Only {THE_ONE_IMPORTER} may import it: "
        "reach the engine through that module, so replacing it stays a one-file change."
    )
    assert len(found[THE_ONE_IMPORTER]) == 1, (
        f"{THE_ONE_IMPORTER} imports pyarrow on lines {found[THE_ONE_IMPORTER]}. One "
        "statement, so the engine's surface in this repository is one line to read."
    )


def test_the_walk_sees_an_import_in_every_spelling() -> None:
    """The walk is only worth running while it still finds what it looks for."""
    tree = ast.parse(
        "import pyarrow\n"
        "import pyarrow.parquet as pq\n"
        "from pyarrow import csv\n"
        "from pyarrow.parquet import write_table\n"
        "import pyarrowish\n"
        "from . import pyarrow\n"
    )

    assert _engine_imports(tree) == [1, 2, 3, 4]
