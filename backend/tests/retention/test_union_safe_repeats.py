"""Does a row arriving twice change any answer a union-safe tree gives?

`.gitattributes` gives nine committed collections `merge=union`, so a merge that
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

from idhazh import ledger, paths
from idhazh.contracts.council_shard_outcome import CouncilShardOutcome
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.merge_line_holdout_score import MergeLineHoldoutScore
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.contracts.visual_prune import VisualPruneRow

pytestmark = pytest.mark.contract

A_DATE = "2026-08-20"
A_RUN = "2026-08-20-1"
AN_ADDRESS = "a" * 64

#: What makes two rows of `state/seen` and `state/published` the same record.
#: Neither carries a key constant, because neither settles a file: both readers
#: return a mapping from the address, so the address is the key and a second row
#: for it lands on the first.
ADDRESS_KEY = ("url_key",)

#: Every union-safe tree, with the contract that spells its columns and what
#: makes two of its rows one record. Checked against `paths.UNION_SAFE` below,
#: so a tree added to that list without a row here fails rather than merges
#: untested.
_TREES = (
    ("state/seen", SeenRow, ADDRESS_KEY, {"url_key": AN_ADDRESS}),
    ("state/published", PublishedRow, ADDRESS_KEY, {"url_key": AN_ADDRESS}),
    (
        "state/visual-prunes",
        VisualPruneRow,
        ledger.VISUAL_PRUNE_KEY,
        {"date": A_DATE, "run_id": A_RUN},
    ),
    (
        "state/feed-retirements.csv",
        FeedRetirementRow,
        ledger.FEED_RETIREMENT_KEY,
        {"endpoint_key": AN_ADDRESS},
    ),
    (
        "state/llm-council/shard-outcomes",
        CouncilShardOutcome,
        ledger.COUNCIL_SHARD_OUTCOME_KEY,
        {"date": A_DATE, "run_id": A_RUN, "judge_id": "judge-a", "shard": "0"},
    ),
    (
        "state/content-similarity-judge/merge-line-holdout-scores",
        MergeLineHoldoutScore,
        ledger.MERGE_LINE_HOLDOUT_SCORE_KEY,
        {"date": A_DATE, "run_id": A_RUN},
    ),
    (
        "state/content-similarity-judge/scored-pairs",
        StorySimilarityPair,
        ledger.STORY_SIMILARITY_PAIR_KEY,
        {"date": A_DATE, "run_id": A_RUN, "pair_key": AN_ADDRESS, "judged_by_run_id": A_RUN},
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
    """A tenth tree joins the list and arrives with nothing proving it settles.

    `state/content-similarity-judge/metrics` is the one entry with no case
    below. It is named here so the gap is a known one rather than a silent one.
    """
    driven = {name for name, _, _, _ in _TREES}
    absent = set(paths.UNION_SAFE) - driven

    assert absent == {"state/content-similarity-judge/metrics"}, (
        f"these union-safe trees have no repeat case: {sorted(absent)}"
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


def test_two_shards_of_one_run_are_two_records(tmp_path: Path) -> None:
    """The other half, or the case above would pass on a function that kept one row.

    Two council shards of one run are two units of work, and a settlement that
    collapsed them would lose one shard's record for ever.
    """
    columns = CouncilShardOutcome.csv_columns()
    path = tmp_path / "shard-outcomes.csv"
    rows = [
        {
            name: {
                "date": A_DATE,
                "run_id": A_RUN,
                "judge_id": "judge-a",
                "shard": shard,
            }.get(name, "")
            for name in columns
        }
        for shard in ("0", "1")
    ]
    path.write_text(ledger.render_file(columns, rows), encoding="utf-8", newline="")
    both = path.read_bytes()

    assert ledger.drop_repeated_rows(path, ledger.COUNCIL_SHARD_OUTCOME_KEY) == 0
    assert path.read_bytes() == both
