"""Does every Python program written inline in a workflow import the modules it uses?

A program in a heredoc is never imported, never linted by the repository's own
ruff pass, and never run until the step runs - so a missing `import` is not a
red test, it is a runner hour spent and thrown away at the line that needed it.
That is not hypothetical: the server arm of `measure.yml` used `hashlib.sha256`
without importing it, which fired only after the model had summarized all five
articles, about fifty minutes in.

The check is deliberately narrow. It asks one question - is a name that is
spelled like a standard-library module, used as a module, and bound nowhere in
the program, imported by it? - and answers nothing else. It cannot see a
third-party module, a typo in an attribute, or a name a step expects the shell
to define, and it is not trying to.
"""

from __future__ import annotations

import ast
import sys
from typing import Final

import pytest

from ._harness import _inline_programs, _load_workflows, _run_bodies

pytestmark = [pytest.mark.workflow, pytest.mark.slow]


#: Stdlib names common enough as ordinary variables that treating them as a
#: module would read the program wrong. Each is bound by the program itself in
#: every real use, so this list only stops a confusing message, never a defect.
NOT_A_MODULE: Final = frozenset({"array", "calendar", "code", "copy", "types"})


def _bound_names(tree: ast.Module) -> set[str]:
    """Every name the program binds, by any spelling.

    Over-collecting is the safe direction here: a name wrongly counted as bound
    only makes this test quieter, never wrong about a name it does report.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.alias):
            bound.add(node.asname or node.name.split(".")[0])
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Global | ast.Nonlocal):
            bound.update(node.names)
    return bound


def _modules_used(tree: ast.Module) -> set[str]:
    """Every bare name the program reads an attribute off, as `json` in `json.loads`."""
    return {
        node.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and isinstance(node.value.ctx, ast.Load)
    }


def test_every_inline_program_imports_the_modules_it_uses() -> None:
    checked = 0

    for filename, workflow in sorted(_load_workflows().items()):
        for script in _run_bodies(workflow):
            for program in _inline_programs(script):
                tree = ast.parse(program)
                checked += 1
                missing = sorted(
                    (_modules_used(tree) & sys.stdlib_module_names)
                    - _bound_names(tree)
                    - NOT_A_MODULE
                )
                first = program.strip().splitlines()[0]
                assert not missing, (
                    f"{filename}: an inline program uses {', '.join(missing)} "
                    f"without importing it, and the step only finds out when it "
                    f"runs. The program starts `{first}`."
                )

    assert checked, "no inline Python program was found, so this test proved nothing"
