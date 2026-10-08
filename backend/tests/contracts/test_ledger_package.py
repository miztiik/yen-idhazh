"""Is the ledger a package with one door, and does the door stay empty?

Checks over named files or a single fixed interpreter run do not scan the
package tree. What each one has to be able to fail is the property the move
could break: the facade shape, the load order and the pyarrow probe.

A caller reaching a name the facade does not bind is a mypy `attr-defined`
error, not a check here. A module outside this package importing the writer-name
patterns `idhazh.ledger.filenames` keeps private is a ruff `TID251` finding
(`pyproject.toml`), not a check here either - both read one file or one import
graph, so neither one costs more as the repository grows.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger

pytestmark = [pytest.mark.contract, pytest.mark.slow]

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
BACKEND: Final = REPO_ROOT / "backend"
PACKAGE: Final = BACKEND / "idhazh" / "ledger"


def _fresh_interpreter(body: str) -> subprocess.CompletedProcess[str]:
    """Run `body` in a new interpreter that has imported nothing of ours yet.

    A same-process assertion is worthless for anything about import order: this
    suite has already imported every module by the time it runs.
    """
    return subprocess.run(
        [sys.executable, "-c", body],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"PYTHONPATH": str(BACKEND)},
        cwd=str(REPO_ROOT),
    )


# --- the facade holds imports and one __all__, and nothing else --------------


def test_the_facade_defines_nothing_of_its_own() -> None:
    """A definition here would be a second home for something a module owns.

    The door's whole job is to say which module holds a name. A constant or a
    function that grew back into it would be a second source of truth, and the
    next reader would have no way to tell which one a caller reached.
    """
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    strays: list[str] = []
    for at, node in enumerate(tree.body):
        if isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if at == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # the leading module docstring
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__all__"
        ):
            continue
        strays.append(f"line {node.lineno}: {ast.unparse(node).splitlines()[0]}")

    assert not strays, (
        "backend/idhazh/ledger/__init__.py holds something other than an import, the "
        f"one __all__ and its docstring: {strays}. Put it in the module that answers "
        "its question and re-export the name."
    )


def test_the_facade_names_its_exports_once() -> None:
    """One `__all__`, and every name in it is bound. Two lists disagree by hand."""
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    declared = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
    ]
    assert len(declared) == 1, f"the facade declares __all__ {len(declared)} times"
    for name in ledger.__all__:
        assert hasattr(ledger, name), f"__all__ names {name} and the facade does not bind it"


# --- the package and day_shards stay acyclic ---------------------------------


@pytest.mark.parametrize("first", ["idhazh.ledger", "idhazh.day_shards"])
def test_either_module_loads_first_in_a_cold_interpreter(first: str) -> None:
    """Both orders, each in a process that has imported nothing of ours.

    The `day_shards` order is the load-bearing one: it forces that module's own
    top-level import of this package against a package nobody has built yet.

    **It does not replace the check above it.** Measured 2026-09-27 by promoting
    the import on purpose: both orders still loaded, because the facade happens
    to import `csv_file` before `rows`, so the name `day_shards` asks for is
    already bound by the time it asks. Reorder the facade and the same promotion
    raises. The check above is what holds the rule; this one says the package
    loads at all.
    """
    done = _fresh_interpreter(f"import {first}")
    assert done.returncode == 0, f"importing {first} first fails:\n{done.stderr}"


def test_the_facade_does_not_load_pyarrow() -> None:
    """A caller that wants a day's rows must not pay for a columnar reader.

    Checked inside the child, because the parent cannot see what the child
    imported. Green today and load-bearing the day a parquet module joins the
    package: importing a name executes its module whatever `__all__` says, so
    the only mechanism that keeps this true is the facade not binding it.
    """
    done = _fresh_interpreter(
        "import sys\n"
        "from idhazh import ledger\n"
        "loaded = [n for n in sys.modules if n == 'pyarrow' or n.startswith('pyarrow.')]\n"
        "loaded += [n for n in sys.modules if n == 'idhazh.ledger.parquet']\n"
        "sys.exit('the facade loaded ' + ', '.join(loaded) if loaded else 0)\n"
    )
    assert done.returncode == 0, done.stderr


# --- the ledger owns every name and folder under state/ ----------------------
#
# Five checks used to live here, each walking every .py file under backend/
# (~640 files, 8.8 MB) to enforce an architectural rule by parsing the whole
# tree on every run. Per the owner ruling of 2026-10-03 ("no read may grow
# with the repository"), a check whose cost rises with the archive rather
# than with the code under test is forbidden, so all five were removed:
#
# - test_only_path_classes_reads_the_writer_name_patterns: the writer-name
#   patterns (`_SEGMENT_NAME`, `_SEGMENT_SUFFIX`, `_REPAIR_NAME`,
#   `_REPAIR_STAMP` in ledger/filenames.py) are now private. Ruff's TID251
#   (banned-api, see pyproject.toml) flags any import of them from outside
#   `path_classes.py` - a one-file, one-import-graph check, not a tree walk.
#
# - test_nothing_outside_the_package_mints_a_name_under_state,
#   test_nothing_outside_the_package_joins_a_ledgers_name_onto_a_path,
#   test_no_module_types_a_folder_under_state, and the self-test that backed
#   them (test_the_folder_checks_can_see_what_they_refuse): no linter, type
#   checker or import-boundary rule currently enforces "a producer hands the
#   ledger rows and identity rather than minting a file name", "a ledger's
#   folder is read from the registry rather than hand-joined", or "a
#   state/<family> folder is never typed outside this package". A fixed named
#   list was tried and rejected: a single pattern (any file referencing
#   `LedgerName.`) already touches 18+ files across backend/idhazh/ and keeps
#   growing, so the list would need constant manual upkeep with silent drift
#   as its failure mode - worse than no check. Moving the rule into the
#   producer was also rejected: it would mean turning `LedgerName` from a
#   `StrEnum` into a plain `Enum` so `path / LedgerName.X` raises at runtime,
#   a persisted-contract change (Level 4/5) out of scope here. The rule is
#   preserved only in the docstrings of ledger/__init__.py and
#   docs/architecture/contracts/state-ledgers.md, for a human reviewing a
#   diff that touches those names. This is a real, disclosed gap in automated
#   coverage, not a quiet one.
