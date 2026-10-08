"""Does the seeded-ledger audit name no ledger, now that none ships a header?

The audit is an operator surface because the question it asks is about a
working copy rather than about code (`CLAUDE.md` section 13). The holdout marks
were the last ledger whose header shipped with the contract, and they file
through the ledger door now, where each writer creates its own file. So the code
question left is that the audit declares nothing and passes a checkout with no
seeded file at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utilities.check_seeded_ledgers import audit, main, report, seeded_ledgers

pytestmark = pytest.mark.contract


def test_the_audit_names_no_ledger_once_the_holdout_marks_moved_to_the_door() -> None:
    assert seeded_ledgers() == ()


def test_an_empty_checkout_passes_an_audit_of_nothing(tmp_path: Path) -> None:
    assert audit(tmp_path) == []
    assert "0 of 0 seeded ledgers" in report([])
    assert main(["--repo-root", str(tmp_path)]) == 0
