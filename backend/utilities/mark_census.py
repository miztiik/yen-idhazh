"""Which pytest marks do the named test source files declare?

Read only the supplied source paths. The slow-mark audit gets those paths from
one JUnit report, not from discovering modules in the committed test tree.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Iterator, Sequence
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


def modules(named: Sequence[Path]) -> list[Path]:
    """Validate and sort a named list of test module files."""
    found = sorted(set(named))
    if not found:
        raise ValueError("name at least one test module")
    for path in found:
        if not path.is_file() or not path.name.startswith("test_") or path.suffix != ".py":
            raise ValueError(f"not a test module file: {path.name}")
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
