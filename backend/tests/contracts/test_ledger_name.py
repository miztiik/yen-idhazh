"""Does one typed name cover every ledger the pipeline can address?"""

from __future__ import annotations

import ast
import inspect

import pytest

from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.ledger import keys, paths, rows, staging

pytestmark = pytest.mark.contract

#: The modules that build paths under `state/`. Named rather than discovered, so
#: the read stays fixed as the repository grows; a new builder module is added here.
PATH_BUILDER_MODULES = (paths, rows, staging)


def _path_builders(tree: ast.Module) -> tuple[set[str], set[str]]:
    """One module's public path builders, split by how each says which ledger.

    A builder handed a `LedgerName` names no ledger of its own - it builds the
    address of whichever one it was given. A builder that takes none has a single
    ledger written into its body, and that is the second spelling this refuses.
    """
    generic: set[str] = set()
    naming: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
            continue
        if not node.name.endswith(("path", "root")):
            continue
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        annotations = {ast.unparse(arg.annotation) for arg in arguments if arg.annotation}
        target = generic if LedgerName.__name__ in annotations else naming
        target.add(node.name)
    return generic, naming


def test_the_day_trees_are_exactly_the_ledgers_with_a_settlement_shape() -> None:
    """The subset and the table it keys have to be the same set.

    A member of the subset with no shape is a segment call that raises on a
    lookup nobody wrote a message for; a shape for a ledger outside the subset is
    a settlement rule the refusal makes unreachable. This is the coverage test
    the widened argument rests on: the type now admits every ledger under
    `state/`, so the set that says which of them a writer files into is the only
    thing left saying no.
    """
    assert set(keys._TREE_SHAPES) == DAY_TREES


def test_every_path_under_state_is_built_from_a_name_this_vocabulary_declares() -> None:
    """Every builder in the named path-builder modules takes its ledger as a name.

    Every builder takes the ledger as a typed argument, so no address under
    `state/` can be reached by a name this vocabulary does not declare. A builder
    with one ledger written into it is what this refuses, and it refuses it
    whether or not the ledger is a known one: a second place that spells where a
    ledger lives is a second place that can disagree with the registry, and a
    path built outside the vocabulary is a path nothing downstream can key on.
    """
    generic: set[str] = set()
    naming: dict[str, str] = {}
    for module in PATH_BUILDER_MODULES:
        takes, names = _path_builders(ast.parse(inspect.getsource(module)))
        generic |= takes
        naming.update(dict.fromkeys(names, module.__name__))

    assert generic, "no path builder was found, so this test is asserting nothing"
    offenders = ", ".join(f"{name} in {where}" for name, where in sorted(naming.items()))
    assert not naming, (
        f"{offenders} builds a path with one ledger written into it. Take a "
        f"{LedgerName.__name__} argument and read the address from the registry, so "
        "every ledger has one spelling of where it lives."
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
