"""How does a retention test run the shipped visual-prune task and read back the row it filed?

Through the gardener's own task runner for tests, over a checkout the test
builds, with the committed declaration and only the knobs a test names changed.
The digest tree sits where that declaration says, so the task walks the folder
it ships owning and nothing a test had to point it at.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Final

from gardener.tasks._task import declared, run_task

from idhazh import ledger
from idhazh.contracts.visual_prune import VisualPruneRow

from ._trees import site

NAME: Final = "visual-prune"


def digest_folder() -> str:
    """The one folder the shipped declaration owns."""
    (folder,) = declared()[NAME].owns or []
    return folder


def published(checkout: Path, days: dict[str, list[str]]) -> Path:
    """The digest tree, built where the shipped declaration owns it inside `checkout`."""
    return site(checkout / digest_folder(), days)


def window(months: int) -> dict[str, Any]:
    """The declaration's window for what the old knob said: thirty-day months, or forever at -1."""
    return {"unit": "forever"} if months < 0 else {"unit": "days", "value": 30 * months}


def pruned(root: Path, today: date, **changed: Any) -> VisualPruneRow:
    """Run the task over the checkout `root` sits in, and read back the one row it filed today."""
    checkout = root.parents[len(Path(digest_folder()).parts) - 1]
    run_task(NAME, checkout, today=today, **changed)
    rows = [
        row
        for row in ledger.load_visual_prunes(checkout / ledger.STATE_DIRNAME)
        if row.date == today.isoformat()
    ]
    assert len(rows) == 1, f"a pass files one row for its day, and {len(rows)} were read back"
    return rows[0]
