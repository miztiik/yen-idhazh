"""Does one typed name cover every ledger the module can address?"""

from __future__ import annotations

import ast

import pytest
from conftest import REPO_ROOT

from idhazh import ledger
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName

pytestmark = pytest.mark.contract

#: The module that builds every path under `state/`. Read here rather than
#: imported, because the question is which functions it declares.
LEDGER_SOURCE = REPO_ROOT / "backend" / "idhazh" / "ledger" / "__init__.py"


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Every module-level name bound to a string literal, and what it is bound to."""
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant):
            if isinstance(value.value, str):
                found[target.id] = value.value
    return found


def _ledger_naming_functions(tree: ast.Module) -> dict[str, set[str]]:
    """Each path builder that names a ledger, and the constant values it reads.

    A builder handed a `LedgerName` names no ledger of its own - it builds the
    path for whichever one it was given - so it is not one of these.
    """
    constants = _module_constants(tree)
    found: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.endswith(("_path", "_relpath")):
            continue
        annotations = {ast.unparse(arg.annotation) for arg in node.args.args if arg.annotation}
        if "LedgerName" in annotations:
            continue
        read = {
            constants[inner.id]
            for inner in ast.walk(node)
            if isinstance(inner, ast.Name) and inner.id in constants
        }
        found[node.name] = read
    return found


def test_the_day_trees_are_exactly_the_ledgers_with_a_settlement_shape() -> None:
    """The subset and the table it keys have to be the same set.

    A member of the subset with no shape is a segment call that raises on a
    lookup nobody wrote a message for; a shape for a ledger outside the subset is
    a settlement rule the refusal makes unreachable. This is the coverage test
    the widened argument rests on: the type now admits every ledger under
    `state/`, so the set that says which of them a writer files into is the only
    thing left saying no.
    """
    assert set(ledger._TREE_SHAPES) == DAY_TREES


def test_every_path_a_builder_names_belongs_to_a_ledger_this_vocabulary_knows() -> None:
    """Derived from the module rather than listed, so a new builder cannot slip past.

    A ledger addressed by filename rather than by a directory is the one this
    would otherwise miss - `feed-retirements.csv` and `holdout-pairs.csv` are
    ledgers with no directory of their own. The extension is dropped because a
    name is not a filename.
    """
    tree = ast.parse(LEDGER_SOURCE.read_text(encoding="utf-8"))
    builders = _ledger_naming_functions(tree)
    known = {member.value for member in LedgerName}

    assert builders, "no path builder was found, so this test is asserting nothing"
    for name, read in sorted(builders.items()):
        named = {value.rsplit(".", 1)[0] for value in read} | read
        assert named & known, (
            f"{name} builds a path out of {sorted(read)}, and none of those is a "
            "LedgerName. A ledger with a path but no typed name is one nothing "
            "downstream can key on"
        )


def test_a_ledgers_name_is_one_segment_and_carries_no_extension() -> None:
    """The name is the ledger. Where it nests and what its file ends in are separate facts.

    A value with a slash in it would put the nest inside the name, and two
    spellings of a nest can disagree. A value with an extension in it would be a
    second spelling of the suffix the path builder already carries.
    """
    for member in LedgerName:
        assert "/" not in member.value, f"{member.name} carries a nest rather than a name"
        assert "." not in member.value, f"{member.name} carries a file extension"
