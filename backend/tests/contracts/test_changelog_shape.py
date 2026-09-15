"""Is every changelog entry one line, and is every changelog at most five of them?

`CLAUDE.md` section 11 bounds the changelog so it cannot become an archive. The
shape is checked in the source rather than on the loaded value, because implicit
concatenation joins a wrapped essay into one string with no newline in it - the
runtime value cannot tell a sentence from a page.
"""

from __future__ import annotations

import ast

import pytest
from conftest import REPO_ROOT

pytestmark = pytest.mark.contract

#: `ChangelogEntry(`, `version=`, `change=`, `why=` and `),` - an entry whose
#: three fields each fit one source line is exactly this tall. Ruff holds those
#: lines to 100 columns, so height here and width there are the whole rule.
LINES_AN_ENTRY_MAY_SPAN = 5

#: Four changes, then one pointer at the file's git history (section 11).
ENTRIES_A_CHANGELOG_MAY_CARRY = 5

CONTRACTS_DIR = REPO_ROOT / "backend" / "idhazh" / "contracts"


def _changelogs() -> list[tuple[str, int, list[ast.Call]]]:
    """Every `__changelog__` tuple in the contracts package, with where it sits.

    A fixed-size read of code a person wrote, never of data a run appended
    (`CLAUDE.md` section 13). It grows with the number of contracts and not with
    the archive.
    """
    found: list[tuple[str, int, list[ast.Call]]] = []
    for path in sorted(CONTRACTS_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if node.target.id != "__changelog__" or not isinstance(node.value, ast.Tuple):
                continue
            entries = [e for e in node.value.elts if isinstance(e, ast.Call)]
            if entries:
                found.append((path.relative_to(REPO_ROOT).as_posix(), node.lineno, entries))
    return found


def _changelog_id(case: tuple[str, int, list[ast.Call]]) -> str:
    return f"{case[0]}:{case[1]}"


@pytest.mark.parametrize("case", _changelogs(), ids=_changelog_id)
def test_a_changelog_carries_at_most_four_changes_and_a_pointer(
    case: tuple[str, int, list[ast.Call]],
) -> None:
    name, line, entries = case
    assert len(entries) <= ENTRIES_A_CHANGELOG_MAY_CARRY, (
        f"{name}:{line} carries {len(entries)} changelog entries. Keep the four newest "
        "and replace the rest with one entry pointing at this file's git history - git "
        "is the archive, and every entry here is copied into the generated schema and "
        "shipped (CLAUDE.md section 11)."
    )


@pytest.mark.parametrize("case", _changelogs(), ids=_changelog_id)
def test_every_changelog_entry_is_one_line_a_field(
    case: tuple[str, int, list[ast.Call]],
) -> None:
    name, _, entries = case
    for entry in entries:
        span = (entry.end_lineno or entry.lineno) - entry.lineno + 1
        assert span <= LINES_AN_ENTRY_MAY_SPAN, (
            f"{name}:{entry.lineno} spans {span} lines. `change` and `why` are one "
            "sentence each. An entry that will not fit is asking whether its reason "
            "earns a `## Design rationale` section in docs/ - write it there and leave "
            "one line here, or drop it (CLAUDE.md section 11)."
        )


@pytest.mark.parametrize("case", _changelogs(), ids=_changelog_id)
def test_no_changelog_entry_wraps_a_string_across_lines(
    case: tuple[str, int, list[ast.Call]],
) -> None:
    """The height check alone cannot see a one-line entry built by concatenation."""
    name, _, entries = case
    for entry in entries:
        for keyword in entry.keywords:
            value = keyword.value
            assert isinstance(value, ast.Constant) and isinstance(value.value, str), (
                f"{name}:{entry.lineno} builds `{keyword.arg}` from something other than "
                "one plain string. A joined string is a paragraph wearing one line."
            )


def test_the_contracts_package_actually_declares_changelogs() -> None:
    """Without this, a rename that empties the walk turns three gates green."""
    assert len(_changelogs()) > 1, "the changelog walk found nothing - has the shape moved?"
