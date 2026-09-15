"""Does the seeded-store audit see a store that is missing, narrow, or fine?

The audit itself is an operator surface because the question it asks is about a
working copy rather than about code (`CLAUDE.md` section 13). These are the code
questions that remain: that it declares the stores a commit step stages, that it
reads the header off the contract rather than off a copy, and that each of the
three verdicts is reachable. Every one of them is driven from a tree built here,
so nothing on this page can be changed by a run appending to the real one.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from idhazh import ledger
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from utilities.check_seeded_stores import audit, main, report, seeded_stores

pytestmark = pytest.mark.contract


def write_header(path: Path, columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(columns)


def a_seeded_checkout(root: Path) -> Path:
    """Both stores present under the header this checkout would append with."""
    for store in seeded_stores():
        write_header(root / store.relpath, store.columns)
    return root


def test_the_audit_names_every_store_whose_header_ships_with_the_contract() -> None:
    """The declaration, held against the contract rather than against a copy.

    A store added to `state/` with a seeded header and not added here would be
    audited by nothing, and the first time `git add` met it the commit step
    would abort with every sibling ledger staged in the same call.
    """
    declared = {store.relpath: store.columns for store in seeded_stores()}

    assert declared == {
        ledger.runtime_counters_relpath(): RuntimeCountersRow.csv_columns(),
        ledger.feed_retirements_relpath(): FeedRetirementRow.csv_columns(),
    }


def test_a_checkout_carrying_both_stores_passes(tmp_path: Path) -> None:
    findings = audit(a_seeded_checkout(tmp_path))

    assert [finding.store.relpath for finding in findings] == [
        store.relpath for store in seeded_stores()
    ]
    assert all(finding.ok for finding in findings)
    assert "2 of 2 seeded stores" in report(findings)


def test_a_missing_store_is_named_rather_than_counted(tmp_path: Path) -> None:
    """The fault has to say what it costs, because the cost is not the file.

    A missing header file costs the commit step, so it costs every ledger staged
    in the same `git add` call - which is the sentence an operator needs.
    """
    a_seeded_checkout(tmp_path)
    (tmp_path / ledger.feed_retirements_relpath()).unlink()

    findings = audit(tmp_path)

    broken = [finding for finding in findings if not finding.ok]
    assert [finding.store.relpath for finding in broken] == [ledger.feed_retirements_relpath()]
    assert broken[0].fault is not None
    assert "git add" in broken[0].fault


def test_a_store_under_an_older_header_is_a_fault_and_not_a_pass(tmp_path: Path) -> None:
    """A narrow header is the case a bare existence check cannot see.

    The file is there, so `git add` succeeds and the commit step runs - and the
    append then refuses the file because `require_matching_header` compares the
    tuple exactly. The audit has to say so before the run does.
    """
    a_seeded_checkout(tmp_path)
    narrow = RuntimeCountersRow.csv_columns()[:-1]
    write_header(tmp_path / ledger.runtime_counters_relpath(), narrow)

    findings = audit(tmp_path)

    broken = [finding for finding in findings if not finding.ok]
    assert [finding.store.relpath for finding in broken] == [ledger.runtime_counters_relpath()]
    assert broken[0].fault is not None
    assert str(len(narrow)) in broken[0].fault


def test_the_exit_code_is_what_a_shell_gates_on(tmp_path: Path) -> None:
    """Zero on a whole checkout, one on a broken one."""
    assert main(["--repo-root", str(a_seeded_checkout(tmp_path))]) == 0

    (tmp_path / ledger.runtime_counters_relpath()).unlink()

    assert main(["--repo-root", str(tmp_path)]) == 1
