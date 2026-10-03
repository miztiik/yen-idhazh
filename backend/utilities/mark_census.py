"""Which test modules does each pytest mark declared in `pyproject.toml` select?

Read from source with `ast` rather than bought by collecting the suite
(`docs/reference/benchmarks/what-the-suite-costs.md`): reading `pytestmark` off
every module under `backend/tests` costs about 2 s, where asking pytest to
collect and resolve marks itself cost 29 s for the same answer.

Shared by two readers. `backend/tests/test_marks.py` holds every declared mark
against every module, so a module outside all of them is named rather than
silently never run. `backend/utilities/slow_mark_audit.py` checks the `slow`
mark specifically against a measured reading of how long each module's tests
actually took. Both need the same two facts - which modules exist, and which
marks each one declares - so this module is the one place that reads them.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
TESTS_DIR: Final = REPO_ROOT / "backend" / "tests"
PYPROJECT_PATH: Final = REPO_ROOT / "pyproject.toml"

#: A mark applied to one test rather than to its module. `parametrize` and the
#: other builtins select nothing, so they are the only ones this tree may carry.
DECORATOR_MARK: Final = re.compile(r"@pytest\.mark\.(\w+)")
BUILTIN_MARKS: Final = frozenset({"parametrize", "skip", "skipif", "xfail", "usefixtures"})


def declared_marks(pyproject_path: Path = PYPROJECT_PATH) -> tuple[str, ...]:
    """The mark names `pyproject.toml` declares, in the order it declares them.

    Read rather than copied, so a fifth mark is covered by every reader the
    moment somebody adds it.
    """
    manifest = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    declared = manifest["tool"]["pytest"]["ini_options"]["markers"]
    return tuple(str(entry).split(":", 1)[0].strip() for entry in declared)


def modules(tests_dir: Path = TESTS_DIR) -> list[Path]:
    """Every test module, including the ones that sit inside a package."""
    found = sorted(tests_dir.rglob("test_*.py"))
    # A census of nothing would make every assertion over it vacuous, which
    # reads exactly like a pass.
    assert len(found) > 100, f"found {len(found)} test modules, so the walk did not walk"
    return found


def mark_names(value: ast.expr) -> Iterator[str]:
    """The mark names a `pytestmark` right-hand side carries.

    Covers `pytest.mark.slow`, a list or tuple of those, and the called form
    `pytest.mark.slow(...)`. Anything else yields nothing, which `module_marks`
    turns into a refusal rather than a silent zero.
    """
    items = value.elts if isinstance(value, ast.List | ast.Tuple) else [value]
    for item in items:
        node = item.func if isinstance(item, ast.Call) else item
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "mark"
        ):
            yield node.attr


def module_marks(path: Path, *, repo_root: Path = REPO_ROOT) -> frozenset[str]:
    """The marks a module's own `pytestmark` names, read from its source.

    A `pytestmark` in a shape this cannot read is refused by name rather than
    counted as no marks, because no marks is a legal answer here and would hide
    the mistake behind a module that was simply never classified.
    """
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        ):
            names = frozenset(mark_names(node.value))
            assert names, (
                f"{path.relative_to(repo_root).as_posix()} assigns `pytestmark` in a shape "
                "this reads. Write it as `pytest.mark.<name>` or a list of those."
            )
            return names
    return frozenset()
