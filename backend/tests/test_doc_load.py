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


def test_a_relative_root_counts_the_same_inbound_links_as_an_absolute_one(
    tmp_path: Path, monkeypatch: object
) -> None:
    """A relative root used to read as a tree where nobody links to anybody."""
    tree(tmp_path)
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]

    here = {row[1]: row[4] for row in doc_load.measure(Path())}

    assert here["docs/reference/light.md"] == 1, "the heavy page still links to it"


def page(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


WELL_FORMED = "# Title\n\n**Last Updated**: 2026-09-20\n\nOne answer.\n\n## See also\n\n- nothing\n"


def test_a_page_carrying_every_required_element_raises_nothing(tmp_path: Path) -> None:
    """The clean case has to be silent, or the noisy one says nothing either."""
    page(tmp_path, "docs/concepts/clean.md", WELL_FORMED)

    assert doc_load.faults(tmp_path) == {}


def test_each_missing_element_is_named_on_the_page_missing_it(tmp_path: Path) -> None:
    """A fault has to say which element, or the reader re-derives it per page."""
    page(tmp_path, "docs/concepts/bare.md", "# One\n\n# Two\n\nNo stamp, no way out.\n")

    found = doc_load.faults(tmp_path)["docs/concepts/bare.md"]

    assert any("2 H1 titles" in f for f in found)
    assert any("Last Updated" in f for f in found)
    assert any("See also" in f for f in found)


def test_a_hash_inside_a_code_fence_is_a_comment_and_not_a_title(tmp_path: Path) -> None:
    """This is the trap: a plain grep counts a shell comment as a second H1."""
    page(
        tmp_path,
        "docs/how-to/do-a-thing.md",
        "# Do A Thing\n\n**Last Updated**: 2026-09-20\n\n"
        "```powershell\n# install the thing first\nnpm ci\n```\n\n## See also\n\n- nothing\n",
    )

    assert doc_load.faults(tmp_path) == {}


def test_a_stamp_that_is_not_a_date_does_not_count(tmp_path: Path) -> None:
    """A date nobody can compare prices no staleness, so it is the same as none."""
    page(tmp_path, "docs/concepts/vague.md", WELL_FORMED.replace("2026-09-20", "recently"))

    found = doc_load.faults(tmp_path)["docs/concepts/vague.md"]

    assert any("Last Updated" in f for f in found)


def test_a_link_to_a_page_that_is_not_there_is_found(tmp_path: Path) -> None:
    """A wrong number of `../` resolves inside docs/ and reads as a real path."""
    page(tmp_path, "docs/reference/benchmarks/one-run.md", WELL_FORMED)
    page(
        tmp_path,
        "docs/reference/benchmarks/other-run.md",
        WELL_FORMED.replace("- nothing", "- [one](one-run.md) and [up](../../CLAUDE.md)"),
    )
    (tmp_path / "CLAUDE.md").write_text("# C\n", encoding="utf-8", newline="\n")

    found = doc_load.faults(tmp_path)["docs/reference/benchmarks/other-run.md"]

    assert found == ["links to a page that is not there: ../../CLAUDE.md"]


def test_a_placeholder_in_a_worked_example_names_no_page(tmp_path: Path) -> None:
    """`docs/concepts/<slug>.md` is a shape being shown, not a link being made."""
    page(
        tmp_path,
        "docs/how-to/distil.md",
        WELL_FORMED.replace("- nothing", "- `[title](docs/concepts/<slug>.md)` - the form"),
    )

    assert doc_load.faults(tmp_path) == {}


def test_a_link_whose_capitals_are_wrong_is_found(tmp_path: Path) -> None:
    """Windows and macOS say yes to it. GitHub serves a 404, and nobody local sees it."""
    page(tmp_path, "docs/reference/target.md", WELL_FORMED)
    page(
        tmp_path,
        "docs/reference/source.md",
        WELL_FORMED.replace("- nothing", "- [shouty](Target.md)"),
    )

    found = doc_load.faults(tmp_path)["docs/reference/source.md"]

    assert found == ["links to a page that is not there: Target.md"]


def test_a_link_to_a_section_that_is_not_there_is_found(tmp_path: Path) -> None:
    """The file surviving proves nothing about the heading somebody meant."""
    page(tmp_path, "docs/reference/target.md", WELL_FORMED + "\n## The Real Heading\n\nHere.\n")
    page(
        tmp_path,
        "docs/reference/source.md",
        WELL_FORMED.replace(
            "- nothing",
            "- [good](target.md#the-real-heading) and [gone](target.md#a-deleted-heading)",
        ),
    )

    found = doc_load.faults(tmp_path)["docs/reference/source.md"]

    assert found == ["links to a section that is not there: target.md#a-deleted-heading"]


def test_a_heading_becomes_the_anchor_github_would_give_it(tmp_path: Path) -> None:
    """Punctuation and formatting drop out, so a styled heading still resolves."""
    got = doc_load.anchors("# Title\n\n## What the grader's bias **is**, at `4 vCPU`\n")

    assert "what-the-graders-bias-is-at-4-vcpu" in got


def test_a_heading_inside_a_code_fence_is_not_an_anchor(tmp_path: Path) -> None:
    """Otherwise a shell comment makes a dangling link look like a good one."""
    got = doc_load.anchors("# Title\n\n```sh\n## not a heading\n```\n")

    assert got == {"title"}


def test_a_page_nested_too_deep_is_two_topics(tmp_path: Path) -> None:
    """The depth rule is the split test made mechanical, so the tool can see it."""
    page(tmp_path, "docs/architecture/publishing/console/charts.md", WELL_FORMED)

    found = doc_load.faults(tmp_path)["docs/architecture/publishing/console/charts.md"]

    assert any("two topics" in f for f in found)
