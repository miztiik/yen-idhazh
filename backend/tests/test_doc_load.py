"""Does the docs measurement answer for one change, and not just for the tree?

The whole-tree report has always existed and nobody read it at the moment it
mattered. `--changed` is the same measurement narrowed to the pages a change
touched, so CI can put it in front of a reviewer.

Every fixture here is a built tree under `tmp_path`. Nothing reads the real
`docs/`, which grows, so nothing here costs more as it does (CLAUDE.md
section 13).
"""

from __future__ import annotations

from pathlib import Path

from utilities import doc_load


def tree(root: Path) -> None:
    """Three pages: a heavy one, a light one, and one nobody links."""
    (root / "docs" / "concepts").mkdir(parents=True)
    (root / "docs" / "reference").mkdir(parents=True)
    (root / "docs" / "concepts" / "heavy.md").write_text(
        "# Heavy\n\n## One\n\n"
        + ("filler. " * 400)
        + "\n\n## Two\n\n"
        + ("filler. " * 400)
        + "\n\nSee [the light page](../reference/light.md).\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "docs" / "reference" / "light.md").write_text(
        "# Light\n\n## Only\n\n" + ("one short answer. " * 20),
        encoding="utf-8",
        newline="\n",
    )
    (root / "docs" / "reference" / "orphan.md").write_text(
        "# Orphan\n\n## Only\n\nNobody links here.\n\nThis was corrected 2026-01-01.\n",
        encoding="utf-8",
        newline="\n",
    )


def test_a_page_carries_the_five_numbers_the_tests_read(tmp_path: Path) -> None:
    """Each column is an input to a named test, so each has to be filled."""
    tree(tmp_path)

    rows = {name: row for row in doc_load.measure(tmp_path) for name in [row[1]]}

    assert rows["docs/concepts/heavy.md"][2] == 2, "two h2 sections"
    assert rows["docs/reference/light.md"][4] == 1, "the heavy page links to it"
    assert rows["docs/reference/orphan.md"][4] == 0, "nobody links to it"
    assert rows["docs/reference/orphan.md"][5] == 1, "one superseded section"


def test_the_heaviest_page_is_first(tmp_path: Path) -> None:
    """The caller ranks by this order, so the order is the contract."""
    tree(tmp_path)

    rows = doc_load.measure(tmp_path)

    assert rows[0][1] == "docs/concepts/heavy.md"
    assert rows[0][0] > rows[-1][0]


def test_changed_prints_only_the_pages_named_and_their_rank(tmp_path: Path, capsys: object) -> None:
    """A reviewer wants the page in front of them, and where it sits in the tree."""
    tree(tmp_path)

    doc_load.changed(tmp_path, ["docs/reference/light.md"])

    printed = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "docs/reference/light.md" in printed
    assert "docs/concepts/heavy.md" not in printed
    assert "2/3" in printed, "second of three pages by weight"
    assert "The page you add to pays first" in printed


def test_a_change_touching_no_page_prints_nothing(tmp_path: Path, capsys: object) -> None:
    """CI hands over whatever the diff listed, so a code-only change is silent."""
    tree(tmp_path)

    doc_load.changed(tmp_path, ["config/idhazh.json", "backend/idhazh/cli.py"])

    assert capsys.readouterr().out == ""  # type: ignore[attr-defined]


def test_a_page_that_does_not_exist_is_skipped_rather_than_refused(
    tmp_path: Path, capsys: object
) -> None:
    """A deleted page has no rows, and a run must not redden over one."""
    tree(tmp_path)

    doc_load.changed(tmp_path, ["docs/reference/light.md", "docs/gone.md"])

    printed = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "docs/reference/light.md" in printed
    assert "docs/gone.md" not in printed
