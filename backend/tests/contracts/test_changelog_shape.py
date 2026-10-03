"""Does each registered document declare a short, single-line changelog?"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from idhazh.contracts import CONTRACTS
from idhazh.contracts.base import Contract

pytestmark = pytest.mark.contract

LINES_AN_ENTRY_MAY_SPAN = 5
ENTRIES_A_CHANGELOG_MAY_CARRY = 5


def changelog_entries(contract: type[Contract]) -> list[ast.Call]:
    """Read one registered class, never discover modules in the package."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(contract)))
    declaration = tree.body[0]
    assert isinstance(declaration, ast.ClassDef), f"{contract.__name__} is not a class"
    for node in declaration.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__changelog__"
            and isinstance(node.value, ast.Tuple)
        ):
            entries = [entry for entry in node.value.elts if isinstance(entry, ast.Call)]
            assert entries, f"{contract.__name__} declares an empty changelog"
            return entries
    pytest.fail(f"{contract.__name__} declares no changelog")


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_a_changelog_carries_at_most_four_changes_and_a_pointer(
    contract: type[Contract],
) -> None:
    entries = changelog_entries(contract)
    assert len(entries) <= ENTRIES_A_CHANGELOG_MAY_CARRY, (
        f"{contract.__name__} carries {len(entries)} changelog entries. "
        "Keep the four newest and one pointer to git history."
    )


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_every_changelog_entry_is_one_line_a_field(contract: type[Contract]) -> None:
    for entry in changelog_entries(contract):
        span = (entry.end_lineno or entry.lineno) - entry.lineno + 1
        assert span <= LINES_AN_ENTRY_MAY_SPAN, (
            f"{contract.__name__}:{entry.lineno} spans {span} lines. "
            "Put the rationale in docs/ and leave one line per field."
        )


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_no_changelog_entry_wraps_a_string_across_lines(contract: type[Contract]) -> None:
    for entry in changelog_entries(contract):
        for keyword in entry.keywords:
            value = keyword.value
            assert isinstance(value, ast.Constant) and isinstance(value.value, str), (
                f"{contract.__name__}:{entry.lineno} builds {keyword.arg} "
                "from something other than one plain string."
            )
