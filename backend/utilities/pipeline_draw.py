"""Which two articles does this dispatch run, and what plan do they make?"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

from idhazh import assemble, config, discover, rank
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.pipeline_tests import PipelineTestsConfig
from idhazh.contracts.run_plan import PlannedItem, RunPlan, VerticalPlan

PLAN_FILE = Path("backend/var/pipeline-tests/plan.json")
TESTS_FILE = Path("config/pipeline-tests.json")


def _tests(config_root: Path) -> PipelineTestsConfig:
    return PipelineTestsConfig.from_json(
        (config_root / TESTS_FILE.name).read_text(encoding="utf-8")
    )


def pick(args: argparse.Namespace) -> int:
    drawn = _tests(args.config_root).draw(args.seed)
    print(f"seed={args.seed}")
    print("addresses=" + " ".join(candidate.url for candidate in drawn))
    print("feeds=" + " ".join(candidate.source_id for candidate in drawn))
    return 0


def plan(args: argparse.Namespace) -> int:
    settings = config.load(args.config_root)
    feeds = {feed.id: feed for feed in settings.sources.feeds}
    # These addresses fell out of their feeds' windows long ago, so the headline
    # comes off the list - a missing one raises here rather than degrading later.
    tests = _tests(args.config_root)
    headlines = {candidate.url: candidate.title for candidate in tests.candidates}
    date = datetime.now(UTC).strftime("%Y-%m-%d")

    items = []
    for address, source_id in zip(args.addresses.split(), args.feeds.split(), strict=True):
        feed = feeds[source_id]
        canonical = discover.canonicalise(address)
        url_key = derive_url_key(canonical)
        items.append(
            PlannedItem(
                item_id=rank.item_id(feed.vertical, url_key),
                url_key=url_key,
                source_url=address,
                canonical_url=canonical,
                source_id=feed.id,
                tier=feed.tier,
                source_form=feed.form,
                vertical=feed.vertical,
                title=headlines[address],
                rank_score=0.0,
            )
        )

    # `feeds_read` stays zero, which is the honest reading: this plan came off a
    # config list, so no feed was asked anything.
    counts: dict[str, int] = {}
    for item in items:
        counts[item.vertical] = counts.get(item.vertical, 0) + 1
    verticals = [
        VerticalPlan(id=name, considered=drawn, planned=drawn, eligible_feeds=drawn)
        for name, drawn in sorted(counts.items())
    ]

    written = RunPlan(
        version=RunPlan.schema_version(),
        date=date,
        run_id=f"{date}-{args.execution}",
        generated_at=assemble.utc_now(),
        verticals=verticals,
        items=items,
    )
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    assemble.write_atomic(PLAN_FILE, written.to_json())
    print(f"date={date}")
    print("item_ids=" + " ".join(item.item_id for item in written.items))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    sub = parser.add_subparsers(dest="command", required=True)

    drawn = sub.add_parser("pick", help="Draw the two addresses for this run.")
    drawn.add_argument("--seed", default=os.environ.get("GITHUB_RUN_ID", ""))

    made = sub.add_parser("plan", help="Write the run plan the cases all share.")
    made.add_argument("--addresses", required=True)
    made.add_argument("--feeds", required=True)
    made.add_argument("--execution", required=True)

    args = parser.parse_args(argv)
    return pick(args) if args.command == "pick" else plan(args)


if __name__ == "__main__":
    raise SystemExit(main())
