"""The plan-queue reader: the parser, what can start, and every drift rule.

Driven by a Status Reckoner built here, never by the plan-docs in `TODO/`. The
real ones change several times a day, so a test bound to them would fail for a
reason nobody introduced, and reading all of them would be a growing read
(CLAUDE.md section 13). A built one also carries the cases the real tree has
never produced - a mistyped status, a dependency that names nothing, a row that
landed before the row it waits on.

Every drift rule below has a case that makes it fire. A rule with no such case
would be a decorative oracle: green whatever the code did.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from utilities.plan_status import (
    Drift,
    Plan,
    PullRequest,
    Ref,
    TreeFacts,
    Worktree,
    counts,
    find_drift,
    idle_branches,
    index_rows,
    judge_tree,
    open_pull_notes,
    parse_depends,
    parse_plan,
    read_plans,
    ready,
    status_markdown,
    status_word,
    stranded_rows,
    unmet,
    unrecorded_merges,
)

ALPHA = """# Alpha

Prose that is not a table.

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | First | - | A | **DONE** | a1 | #101 | - |
| 2 | Second | 1 | A | PENDING | - | - | - |
| 3 | Third | 2 | B | PENDING | - | - | - |
| 4 | Fourth | 99 | B | PENDING | - | - | - |
| 5 | Fifth | 2 | C | DONE | - | #105 | - |
| 6 | Sixth | - | C | DONE | - | - | - |
| 7 | Seventh | - | C | PENDING | - | #107 | - |
| 8 | Eighth | - | D | DOEN | - | - | - |
| 9 | Ninth | plan 32 row #1 | D | PENDING | - | - | - |
| 10 | Tenth | plan 32 row #2 | D | PENDING | - | - | - |
| 11 | Eleventh | - | E | IN-FLIGHT | gone-tree | - | - |

Text after the table, which the parser must stop at.
"""

#: A second plan, spelling its group column `Group`, with no `Worktree` column.
BETA = """# Beta

## 1. Status Reckoner

| # | Row title | Depends-on | Group | Status | PR |
| --- | --- | --- | --- | --- | --- |
| 1 | Bravo one | - | A | **DONE** | #201 |
| 2 | Bravo two | 1 | A | PENDING | - |
"""

#: A plan whose first `#`-and-`Status` table is NOT its Reckoner.
GAMMA = """# Gamma

## 0. Options considered

| # | Option | Status |
| --- | --- | --- |
| 1 | The thing we did not do | REFUSED |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Gamma one | - | A | PENDING | - | - | - |
"""

#: A plan with no PR column at all, and a pull request number in its status text.
DELTA = """# Delta

## Section 9 - Status Reckoner

| Phase | # | Row | Depends on | Status |
| --- | --- | --- | --- | --- |
| A | 1 | Delta one | - | **DONE 2026-01-01** - merged by hand |
| A | 2 | Delta two | 1 (and 3 for the other arm) | CLOSED 2026-01-02 (PR #202) |
"""

#: A file under TODO/ that is not a plan. It must be found and then ignored.
NOTES = """# Notes

No table here at all, just a Status Reckoner mentioned in a sentence.
"""


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A repository root holding five files under `TODO/`, four of them plans."""
    todo = tmp_path / "TODO"
    todo.mkdir()
    for name, body in (
        ("20260101-31-alpha-plan.md", ALPHA),
        ("20260101-32-beta-plan.md", BETA),
        ("20260101-33-gamma-plan.md", GAMMA),
        ("20260101-34-delta-plan.md", DELTA),
        ("20260101-notes.md", NOTES),
    ):
        (todo / name).write_text(body, encoding="utf-8", newline="\n")
    return tmp_path


def plan_named(plans: list[Plan], stem: str) -> Plan:
    return next(plan for plan in plans if stem in plan.path.name)


# ------------------------------------------------------------------ discovery


def test_discovery_finds_the_plans_and_skips_the_note(tree: Path) -> None:
    plans = read_plans(tree)
    assert [plan.path.name for plan in plans] == [
        "20260101-31-alpha-plan.md",
        "20260101-32-beta-plan.md",
        "20260101-33-gamma-plan.md",
        "20260101-34-delta-plan.md",
    ]


def test_a_sixth_plan_appears_with_no_code_change(tree: Path) -> None:
    """Guardrail #6: discovery is a glob plus a table shape, never a list of names."""
    before = len(read_plans(tree))
    (tree / "TODO" / "20260202-35-epsilon-plan.md").write_text(
        BETA.replace("Bravo", "Echo"), encoding="utf-8", newline="\n"
    )
    after = read_plans(tree)
    assert len(after) == before + 1
    assert after[-1].rows[0].title == "Echo one"


def test_the_reckoner_is_the_table_after_the_heading(tree: Path) -> None:
    """Gamma's first `#`-and-`Status` table is a decision table, not its queue."""
    gamma = plan_named(read_plans(tree), "gamma")
    assert [row.title for row in gamma.rows] == ["Gamma one"]


def test_a_file_with_no_reckoner_parses_to_nothing() -> None:
    assert parse_plan(PurePosixPath("TODO/x.md"), NOTES) is None


# --------------------------------------------------------------------- parsing


def test_a_row_reads_every_column(tree: Path) -> None:
    alpha = plan_named(read_plans(tree), "alpha")
    first = alpha.rows[0]
    assert first.row_id == "1"
    assert first.title == "First"
    assert first.group == "A"
    assert first.status_word == "DONE"
    assert first.state == "landed"
    assert first.worktree == "a1"
    assert first.pull == 101
    assert first.plan_number == 31
    assert first.name == "plan 31 row #1"
    assert first.where == "TODO/20260101-31-alpha-plan.md:9"


def test_the_column_names_are_read_not_counted(tree: Path) -> None:
    """Beta spells its group column `Group` and has no `Worktree` column."""
    beta = plan_named(read_plans(tree), "beta")
    assert beta.rows[0].group == "A"
    assert beta.rows[0].pull == 201
    assert beta.rows[0].worktree == ""
    assert beta.has_pull_column is True

    delta = plan_named(read_plans(tree), "delta")
    assert delta.rows[0].title == "Delta one"
    assert delta.rows[0].group == "A"
    assert delta.has_pull_column is False


def test_a_pull_request_number_is_read_from_the_status_text(tree: Path) -> None:
    delta = plan_named(read_plans(tree), "delta")
    assert delta.rows[1].pull == 202
    assert delta.rows[1].state == "landed"


def test_the_table_stops_at_the_prose_under_it(tree: Path) -> None:
    alpha = plan_named(read_plans(tree), "alpha")
    assert len(alpha.rows) == 11


@pytest.mark.parametrize(
    ("cell", "word", "state"),
    [
        ("PENDING", "PENDING", "pending"),
        ("**DONE**", "DONE", "landed"),
        ("DONE #499", "DONE", "landed"),
        ("**DONE 2026-08-28** - the corpus contract", "DONE", "landed"),
        ("CLOSED 2026-08-27 (PR #180)", "CLOSED", "landed"),
        ("LANDED AND RUN (measured on ubuntu-latest)", "LANDED", "landed"),
        ("RETIRED", "RETIRED", "dropped"),
        ("DESCOPED", "DESCOPED", "dropped"),
        ("IN-FLIGHT", "IN-FLIGHT", "in-flight"),
        ("BLOCKED", "BLOCKED", "blocked"),
        ("DOEN", "DOEN", "unknown"),
        ("", "", "unknown"),
    ],
)
def test_a_status_cell_reduces_to_one_word(cell: str, word: str, state: str) -> None:
    assert status_word(cell) == word
    body = BETA.replace("| **DONE** | #201 |", f"| {cell} | #201 |")
    plan = parse_plan(PurePosixPath("TODO/20260101-32-beta-plan.md"), body)
    assert plan is not None
    assert plan.rows[0].state == state


@pytest.mark.parametrize(
    ("cell", "refs"),
    [
        ("-", ()),
        ("", ()),
        ("1", (Ref(None, "1", "1"),)),
        ("1, 2", (Ref(None, "1", "1"), Ref(None, "2", "2"))),
        ("#7b", (Ref(None, "7b", "#7b"),)),
        ("plan 24 row #1", (Ref(24, "1", "plan 24 row #1"),)),
        ("3, plan 11 row 6", (Ref(None, "3", "3"), Ref(11, "6", "plan 11 row 6"))),
        ("8 (and 9 for the student)", (Ref(None, "8", "8 (and 9 for the student)"),)),
    ],
)
def test_a_depends_on_cell_reads_as_references(cell: str, refs: tuple[Ref, ...]) -> None:
    assert parse_depends(cell) == refs


# ------------------------------------------------------------------- readiness


def test_what_can_start_now(tree: Path) -> None:
    plans = read_plans(tree)
    index = index_rows(plans)
    rows = [row for plan in plans for row in plan.rows]
    startable = {(row.plan_number, row.row_id) for row in ready(rows, index)}
    assert startable == {
        (31, "2"),  # depends on #1, which is DONE
        (31, "7"),  # depends on nothing
        (31, "9"),  # depends on plan 32 row #1, which is DONE
        (32, "2"),  # depends on #1, which is DONE
        (33, "1"),  # depends on nothing
    }


def test_a_row_says_why_it_cannot_start(tree: Path) -> None:
    plans = read_plans(tree)
    index = index_rows(plans)
    alpha = plan_named(plans, "alpha")
    by_id = {row.row_id: row for row in alpha.rows}
    assert unmet(by_id["3"], index) == ["2 is PENDING"]
    assert unmet(by_id["4"], index) == ["99 names no row"]
    assert unmet(by_id["10"], index) == ["plan 32 row #2 is PENDING"]
    assert unmet(by_id["2"], index) == []


def test_an_unreadable_status_never_counts_as_startable(tree: Path) -> None:
    """Row #8 says `DOEN`. It is live, so it is not lost, and it is not offered."""
    plans = read_plans(tree)
    index = index_rows(plans)
    alpha = plan_named(plans, "alpha")
    row = next(row for row in alpha.rows if row.row_id == "8")
    assert row.live is True
    assert row not in ready(alpha.rows, index)


def test_the_per_plan_tally(tree: Path) -> None:
    alpha = plan_named(read_plans(tree), "alpha")
    assert counts(alpha.rows) == {
        "landed": 3,
        "dropped": 0,
        "pending": 6,
        "in-flight": 1,
        "blocked": 0,
        "unknown": 1,
    }
    assert len(alpha.live) == 8


# ----------------------------------------------------------------- drift rules


def drift_by_rule(tree: Path, states: dict[int, str] | None) -> dict[str, list[Drift]]:
    plans = read_plans(tree)
    found: dict[str, list[Drift]] = {}
    for item in find_drift(plans, index_rows(plans), states):
        found.setdefault(item.rule, []).append(item)
    return found


def test_drift_unknown_status_fires(tree: Path) -> None:
    found = drift_by_rule(tree, None)["unknown-status"]
    assert [item.row for item in found] == ["plan 31 row #8"]
    assert "'DOEN'" in found[0].detail


def test_drift_dependency_not_found_fires(tree: Path) -> None:
    found = drift_by_rule(tree, None)["dependency-not-found"]
    assert [item.row for item in found] == ["plan 31 row #4"]
    assert "'99'" in found[0].detail


def test_drift_done_before_its_dependency_fires(tree: Path) -> None:
    found = drift_by_rule(tree, None)["done-before-its-dependency"]
    assert [item.row for item in found] == ["plan 31 row #5"]
    assert "plan 31 row #2 is PENDING" in found[0].detail


def test_drift_done_with_no_pr_fires(tree: Path) -> None:
    found = drift_by_rule(tree, None)["done-with-no-pr"]
    assert [item.row for item in found] == ["plan 31 row #6"]


def test_a_plan_with_no_pr_column_is_never_asked_for_one(tree: Path) -> None:
    """Delta's rows are done and name no pull request. That is the table's shape,
    not the row's fault, so the rule stays silent and the report says so once."""
    rows = [item.row for item in drift_by_rule(tree, None)["done-with-no-pr"]]
    assert not [row for row in rows if row.startswith("plan 34")]


def test_drift_merged_but_not_done_fires_only_when_gh_answered(tree: Path) -> None:
    silent = drift_by_rule(tree, None)
    assert "merged-but-not-done" not in silent

    answered = drift_by_rule(tree, {107: "MERGED"})["merged-but-not-done"]
    assert [item.row for item in answered] == ["plan 31 row #7"]
    assert "607" not in answered[0].detail

    open_still = drift_by_rule(tree, {107: "OPEN"})
    assert "merged-but-not-done" not in open_still


def test_a_clean_reckoner_finds_nothing(tree: Path) -> None:
    plans = [plan_named(read_plans(tree), "beta")]
    assert find_drift(plans, index_rows(plans), {}) == []


# -------------------------------------------- the rule that caught pull 608


def merged(number: int, title: str, body: str = "", day: str = "2026-06-01T00:00:00Z") -> PullRequest:
    return PullRequest(
        number=number,
        state="MERGED",
        head=f"b{number}",
        title=title,
        body=body,
        merged_at=day,
    )


def test_a_merged_pull_request_whose_row_never_learned(tree: Path) -> None:
    """The #608 case: the row's PR column is empty, so only the pull request knows."""
    rows = [row for plan in read_plans(tree) for row in plan.rows]
    pulls = [merged(900, "docs: a thing (row #3)", "`TODO/20260101-31-alpha-plan.md` section 2.")]
    found = unrecorded_merges(pulls, rows)
    assert [item.rule for item in found] == ["merged-but-row-not-updated"]
    assert found[0].row == "plan 31 row #3"
    assert "pull request 900" in found[0].detail


def test_a_merged_pull_request_whose_row_did_learn_is_silent(tree: Path) -> None:
    rows = [row for plan in read_plans(tree) for row in plan.rows]
    assert unrecorded_merges([merged(101, "feat: (row #2)", "alpha")], rows) == []
    assert unrecorded_merges([merged(902, "feat: (row #1)", "plan 31")], rows) == []
    assert unrecorded_merges([merged(903, "chore: no row named here")], rows) == []
    assert (
        unrecorded_merges(
            [PullRequest(number=904, state="OPEN", head="b", title="(row #3)", body="plan 31")],
            rows,
        )
        == []
    )


def test_a_pull_request_that_names_its_plan_is_not_matched_against_another(tree: Path) -> None:
    rows = [row for plan in read_plans(tree) for row in plan.rows]
    both = unrecorded_merges([merged(905, "feat: (row #2)")], rows)
    assert {item.row for item in both} == {"plan 31 row #2", "plan 32 row #2"}

    narrowed = unrecorded_merges([merged(906, "feat: (row #2)", "plan 32 changed")], rows)
    assert [item.row for item in narrowed] == ["plan 32 row #2"]

    by_file = unrecorded_merges(
        [merged(908, "feat: (row #2)", "`TODO/20260101-31-alpha-plan.md` section 2.")], rows
    )
    assert [item.row for item in by_file] == ["plan 31 row #2"]

    elsewhere = unrecorded_merges([merged(909, "feat: (row #2)", "plan 99 changed")], rows)
    assert elsewhere == []


def test_a_pull_request_older_than_the_plan_did_not_do_its_rows(tree: Path) -> None:
    """Measured on the real tree 2026-09-11: pull requests 556 and 557 said
    `row #12` and merged days before plans 23 and 25 were written, so without
    this bound each was reported against a row of both."""
    rows = [row for plan in read_plans(tree) for row in plan.rows]
    older = unrecorded_merges([merged(910, "feat: (row #2)", day="2025-12-31T00:00:00Z")], rows)
    assert older == []

    newer = unrecorded_merges([merged(911, "feat: (row #2)", day="2026-01-01T00:00:00Z")], rows)
    assert {item.row for item in newer} == {"plan 31 row #2", "plan 32 row #2"}


def test_only_the_title_and_the_opening_of_a_body_declare_a_row(tree: Path) -> None:
    """A body names rows it unblocks further down. Those are not rows it did.

    Row #1 of plan 31 has landed, row #3 has not. A window that ran to the end
    of the body would report row #3 as the row this pull request forgot.
    """
    rows = [row for plan in read_plans(tree) for row in plan.rows]
    body = "\n".join(
        ["# Row #1 of plan 31", "", "Intro.", "", "one", "two", "three", "This unblocks row #3."]
    )
    assert unrecorded_merges([merged(907, "feat: alpha", body)], rows) == []


# --------------------------------------------------------------- what is in flight


def facts(
    name: str,
    *,
    branch: str | None = "feat/x",
    uncommitted: int | None = 0,
    ahead: int | None = 0,
    pull: PullRequest | None = None,
    pull_read: bool = True,
) -> TreeFacts:
    return TreeFacts(
        tree=Worktree(path=Path("/w") / name, head="abc1234", branch=branch),
        uncommitted=uncommitted,
        ahead=ahead,
        pull=pull,
        pull_read=pull_read,
    )


def test_a_worktree_with_work_nobody_proposed_is_adopted(tree: Path) -> None:
    rows = [row for plan in read_plans(tree) for row in plan.rows]
    note = judge_tree(facts("p31-r2", uncommitted=16), rows)
    assert note.subject == "p31-r2"
    assert "no plan row names it" in note.detail
    assert "16 uncommitted files" in note.detail
    assert "ADOPT: work here was never proposed" in note.detail


def test_an_empty_worktree_is_removed(tree: Path) -> None:
    note = judge_tree(facts("leftover"), [])
    assert "REMOVE: nothing in it" in note.detail


def test_a_landed_worktree_is_removed(tree: Path) -> None:
    landed = PullRequest(number=608, state="MERGED", head="feat/x", title="t")
    assert "REMOVE: it landed" in judge_tree(facts("done", pull=landed), []).detail


def test_a_worktree_a_row_claims_is_named_by_that_row(tree: Path) -> None:
    rows = [row for plan in read_plans(tree) for row in plan.rows]
    note = judge_tree(facts("a1", branch="feat/first", ahead=2), rows)
    assert "plan 31 row #1" in note.detail
    assert "2 commits ahead" in note.detail


def test_a_detached_worktree_is_never_asked_about_a_pull_request(tree: Path) -> None:
    note = judge_tree(facts("review", branch=None, uncommitted=0, pull_read=False), [])
    assert "detached" in note.detail
    assert "pull request" not in note.detail


def test_a_worktree_whose_pull_request_could_not_be_read_gets_no_verdict(tree: Path) -> None:
    note = judge_tree(facts("offline", pull_read=False), [])
    assert "no verdict" in note.detail
    assert "REMOVE" not in note.detail
    assert "ADOPT" not in note.detail


def test_a_row_that_says_it_is_being_worked_on_where_nothing_is(tree: Path) -> None:
    rows = [row for plan in read_plans(tree) for row in plan.rows]
    notes = stranded_rows(rows, [Worktree(Path("/w/a1"), "abc", "feat/first")])
    assert [note.subject for note in notes] == ["plan 31 row #11"]
    assert "'gone-tree'" in notes[0].detail

    backed = stranded_rows(rows, [Worktree(Path("/w/gone-tree"), "abc", "feat/eleven")])
    assert backed == []


def test_a_branch_with_no_worktree_is_named(tree: Path) -> None:
    trees = [Worktree(Path("/w/a1"), "abc", "feat/first")]
    assert idle_branches(["main", "feat/first", "feat/abandoned"], trees, "origin/main") == [
        "feat/abandoned"
    ]


def test_an_open_pull_request_is_matched_to_the_row_it_is_finishing(tree: Path) -> None:
    """A pull request opened from a checkout since removed is still outstanding."""
    rows = [row for plan in read_plans(tree) for row in plan.rows]
    trees = [Worktree(Path("/w/a1"), "abc", "feat/first")]
    pulls = [
        PullRequest(number=101, state="OPEN", head="feat/first", title="the first row"),
        PullRequest(number=999, state="OPEN", head="chore/tidy", title="unrelated tidy"),
    ]
    notes = open_pull_notes(pulls, rows, trees)
    assert [note.subject for note in notes] == ["#101", "#999"]
    assert "plan 31 row #1" in notes[0].detail
    assert "a worktree still holds its branch" in notes[0].detail
    assert "no plan row records it" in notes[1].detail
    assert "no worktree holds it" in notes[1].detail

# ------------------------------------------------------------------ the written file


def test_the_written_page_is_the_same_bytes_every_time(tree: Path) -> None:
    """A drift gate over a file that moves on its own fails for no reason.

    So this asserts the one property the gate rests on: same tree in, same
    bytes out. Nothing in the page may come from a clock, the network or a
    checkout.
    """
    plans = read_plans(tree)
    index = index_rows(plans)

    once = status_markdown(plans, index)
    twice = status_markdown(read_plans(tree), index_rows(read_plans(tree)))

    assert once == twice


def test_the_written_page_names_every_live_plan_and_its_ready_rows(tree: Path) -> None:
    plans = read_plans(tree)
    page = status_markdown(plans, index_rows(plans))

    for plan in plans:
        if plan.live:
            assert plan.path.name in page

    startable = ready([row for plan in plans for row in plan.rows], index_rows(plans))
    assert f"## Ready now - {len(startable)}" in page
    for row in startable:
        assert row.title in page


def test_a_row_that_lands_changes_the_written_page(tree: Path) -> None:
    """The whole point: the file cannot lag behind the Reckoner that feeds it."""
    before = status_markdown(read_plans(tree), index_rows(read_plans(tree)))

    plan = tree / "TODO" / "20260101-31-alpha-plan.md"
    plan.write_text(
        plan.read_text(encoding="utf-8").replace("| PENDING |", "| DONE #77 |", 1),
        encoding="utf-8",
        newline="\n",
    )
    after = status_markdown(read_plans(tree), index_rows(read_plans(tree)))

    assert before != after


def test_every_emitted_row_is_a_well_formed_table_line(tree: Path) -> None:
    """A page whose tables do not parse is worse than the command it replaces.

    A bare `|` cannot reach here from a title - the Reckoner's own parser would
    have split the cell first - so what this guards is the emitter: every row
    line carries its five cells and no sixth.
    """
    plans = read_plans(tree)

    page = status_markdown(plans, index_rows(plans))

    emitted = [line for line in page.splitlines() if line.startswith("| #")]
    assert emitted
    for line in emitted:
        assert line.count("|") == 6, line
        assert not line.startswith("| # |")


def test_an_in_flight_row_is_listed_apart_from_the_ready_ones(tree: Path) -> None:
    """`IN-FLIGHT` is what a reader looks for to know somebody is already on it.

    The alpha fixture carries exactly one, and it must not also be offered as a
    row somebody could pick up.
    """
    plans = read_plans(tree)
    rows = [row for plan in plans for row in plan.rows]
    flying = [row for row in rows if row.state == "in-flight"]

    page = status_markdown(plans, index_rows(plans))

    assert f"## In flight - {len(flying)}" in page
    assert flying
    startable = ready(rows, index_rows(plans))
    assert not [row for row in startable if row.state == "in-flight"]