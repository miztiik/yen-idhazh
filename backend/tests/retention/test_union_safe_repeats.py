"""Does a row arriving twice change any answer a union-safe tree gives?

`.gitattributes` gives the judge's CSV trees `merge=union`, so a merge that
finds the same row on both sides keeps both copies. That is safe only where the
row is keyed and something settles the repeat: the same key twice is one record
recorded twice, never two records.

Each case writes one row through the tree's own contract columns, doubles it the
way a union merge leaves it, and settles it through `ledger.drop_repeated_rows` -
the function every one of these writers calls straight after its append. The
proof is that the settled bytes are the bytes one arrival left.

Nothing here reads `state/` (CLAUDE.md section 13). **The edit that would make
one of these fail** is a key losing a cell, which turns a merge git resolved
quietly into a double-counted row nobody sees.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from idhazh import ledger, path_classes
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.merge_line_holdout_score import MergeLineHoldoutScore

pytestmark = pytest.mark.contract

A_DATE = "2026-08-20"
A_RUN = "2026-08-20-1"

#: Every union-safe tree, with the contract that spells its columns and what
#: makes two of its rows one record. Checked against `path_classes.UNION_SAFE` below,
#: so a tree added to that list without a row here fails rather than merges
#: untested.
_TREES = (
    (
        "state/content-similarity-judge/merge-line-holdout-scores",
        MergeLineHoldoutScore,
        ledger.MERGE_LINE_HOLDOUT_SCORE_KEY,
        {"date": A_DATE, "run_id": A_RUN},
    ),
    (
        "state/content-similarity-judge/fitted-thresholds",
        FittedSimilarityThreshold,
        ledger.STORY_SIMILARITY_THRESHOLD_KEY,
        {"date": A_DATE, "run_id": A_RUN},
    ),
)

def _doubled(path: Path) -> None:
    """Append every record line a second time, the way a union merge leaves them."""
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([*lines, *lines[1:]]) + "\n", encoding="utf-8", newline="")


def test_every_union_safe_tree_has_a_repeat_case_beside_it() -> None:
    """A tree that joins the list arrives with nothing proving it settles."""
    driven = {name for name, _, _, _ in _TREES}

    assert set(path_classes.UNION_SAFE) == driven, (
        f"these union-safe trees have no repeat case: "
        f"{sorted(set(path_classes.UNION_SAFE) - driven)}"
    )


@pytest.mark.parametrize(("tree", "model", "key", "cells"), _TREES, ids=[row[0] for row in _TREES])
def test_a_row_arriving_twice_settles_back_to_one(
    tmp_path: Path,
    tree: str,
    model: type[ledger.CsvContract],
    key: tuple[str, ...],
    cells: dict[str, str],
) -> None:
    """One key twice is one record, whichever side of a merge the second copy came from.

    Only the key cells carry a value. A settlement reads the key and nothing
    else, so a row filled out further would prove the same thing and would have
    to be rebuilt every time the contract gained a column.
    """
    columns = model.csv_columns()
    for name in key:
        assert name in columns, f"{tree}: the key names {name}, which the contract does not"

    path = tmp_path / "ledger.csv"
    row = {name: cells.get(name, "") for name in columns}
    path.write_text(ledger.render_file(columns, [row]), encoding="utf-8", newline="")
    once = path.read_bytes()

    _doubled(path)
    assert path.read_bytes() != once, "the second copy did not land, so nothing is proved"

    dropped = ledger.drop_repeated_rows(path, key)

    assert dropped == 1, f"{tree}: the repeat was read as a second record"
    assert path.read_bytes() == once, f"{tree}: the settled file is not what one arrival wrote"
