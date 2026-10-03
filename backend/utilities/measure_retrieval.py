"""Do the named month shards name every item the named days published?

**An operator tool, never a test.** Whether the month index agrees with the day
payloads is a fact about published data, so pytest does not gate it (CLAUDE.md
section 13 rule 2). An operator runs it by hand over the days and months they
want checked - and only those (CLAUDE.md Guardrail #12): the cost is the size
of the names given, never the size of the archive.

Run it from the repository root, naming every day and month to compare:

    python backend/utilities/measure_retrieval.py --day 2026-08-26 --month 2026-08

Name the month shards that cover exactly the named days, or the two sides
differ by the days you left out.

**What it settles.** Whether the two sets hold the same addresses, and whether
the same number of them carry a vector. Membership first, because a lost item
and a lost vector are different failures. It exits 1 when they disagree and
names the addresses on each side.

**What it does not settle by itself.** Whether the ranking is any good. Pass
`--quality` and it also embeds the committed query set
(`tests/fixtures/search/retrieval-queries.json`) with the committed encoder,
ranks it over the named days with the configured floor and slot count, and
prints recall and the floor's null-score evidence. Those are measurements an
operator tunes against; no test gates them.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from idhazh.config import DEFAULT_CONFIG_DIR, REPO_ROOT
from idhazh.contracts.app_config import AppConfig
from idhazh.evals import retrieval


def report(root: Path, days: Sequence[str], months: Sequence[str]) -> tuple[str, int]:
    """The membership lines for the named days and months, and their exit code."""
    corpus = retrieval.load_corpus(root, days=days)
    index = retrieval.load_index_corpus(root, months=months)

    published = {item.address for item in corpus.items}
    indexed = {item.address for item in index.items}
    unindexed = sorted(published - indexed)
    unpublished = sorted(indexed - published)

    lines = [
        f"{'named days':<15} {len(days)}",
        f"{'named shards':<15} {len(months)}",
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
            "the two sets hold the same addresses and a different number of "
            "vectors, so a shard carries an entry the day payload embedded"
        )
    return "\n".join(lines), 0 if not unindexed and not unpublished and vectors_agree else 1


def quality(root: Path, days: Sequence[str]) -> str:
    """Recall and the floor's null-score evidence over the named days. A reading, not a gate."""
    assist = AppConfig.from_json(
        (DEFAULT_CONFIG_DIR / "idhazh.json").read_text(encoding="utf-8")
    ).assist
    corpus = retrieval.load_corpus(root, days=days)
    queries = retrieval.load_queries(root)
    embedded = retrieval.embed_queries(root, queries)
    report = retrieval.evaluate(
        corpus, queries, embedded, limit=assist.result_limit, floor=assist.similarity_floor
    )
    nulls = retrieval.null_scores(corpus, queries, embedded)
    above = sum(score >= assist.similarity_floor for score in nulls)
    share = above / len(nulls) if nulls else 0.0
    return "\n".join(
        [
            report.summary(),
            f"null scores: {len(nulls)}; {share:.1%} clear the floor "
            f"{assist.similarity_floor}; p99 {retrieval.quantile(nulls, 0.99):.3f}",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root to read.")
    parser.add_argument(
        "--day", action="append", required=True, help="A published day, YYYY-MM-DD (UTC). Repeat."
    )
    parser.add_argument(
        "--month", action="append", required=True, help="A month shard, YYYY-MM. Repeat."
    )
    parser.add_argument(
        "--quality", action="store_true", help="Also measure recall with the committed encoder."
    )
    args = parser.parse_args()
    text, code = report(args.root, days=args.day, months=args.month)
    print(text)
    if args.quality:
        print(quality(args.root, days=args.day))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
