"""Does the month index name every published item? Answered over both wholes.

**An operator script, never a test.** The question needs every committed day and
every committed month shard at once, and no bound can answer it: a window would
compare the days inside it and say nothing about the ones outside, which is the
only place a dropped item can hide. That read costs more each time a run
publishes (CLAUDE.md Guardrail #12), and section 13 forbids a test to carry it.
So it lives here, where pytest does not collect it.

It was `test_the_index_names_every_published_item` until 2026-09-22. Everything
else that test module asks is bounded - the gate is pinned to
`assist.eval_corpus_through`, and the knob check reads the trailing window
`assist.search_months` names - so this was the one question that had to move
rather than take a cover.

Run it from the repository root:

    python backend/utilities/measure_retrieval.py

**What it settles.** Whether the two collections hold the same addresses, and
whether the same number of them carry a vector. Membership first, because a lost
item and a lost vector are different failures and only one of them shows up in
recall as a small number. It exits 1 when they disagree and names the addresses
on each side.

**What it does not settle.** Whether the ranking is any good. That is
`backend/tests/test_retrieval_eval.py`, which is gated and stays gated.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from idhazh.config import REPO_ROOT
from idhazh.evals import retrieval


def report(root: Path) -> tuple[str, int]:
    """The membership lines, and the exit code they add up to."""
    corpus = retrieval.load_corpus(root)
    index = retrieval.load_index_corpus(root)

    published = {item.address for item in corpus.items}
    indexed = {item.address for item in index.items}
    unindexed = sorted(published - indexed)
    unpublished = sorted(indexed - published)

    lines = [
        f"{'published days':<15} {len({item.date for item in corpus.items})}",
        f"{'month shards':<15} {len(retrieval.index_months(root))}",
        f"{'published items':<15} {len(published)}, {len(corpus.searchable)} carry a vector",
        f"{'indexed items':<15} {len(indexed)}, {len(index.searchable)} carry a vector",
    ]
    for label, rows in (("in no shard", unindexed), ("in no day", unpublished)):
        lines.append(f"{label:<15} {len(rows)}")
        lines.extend(f"  {date}/{item_id}" for date, item_id in rows[:20])
        if len(rows) > 20:
            lines.append(f"  ... and {len(rows) - 20} more")

    vectors_agree = len(index.searchable) == len(corpus.searchable)
    if not vectors_agree:
        lines.append(
            "the two collections hold the same addresses and a different number of "
            "vectors, so a shard carries an entry the day payload embedded"
        )
    return "\n".join(lines), 0 if not unindexed and not unpublished and vectors_agree else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root to read.")
    args = parser.parse_args()
    root: Path = args.root
    if not retrieval.index_months(root):
        parser.error(f"no committed month shard under {retrieval.INDEX_RELDIR}")
    text, code = report(root)
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
