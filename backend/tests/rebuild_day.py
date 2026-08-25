"""Rebuild a day the way `stage_assemble` does, with no pipeline behind it.

The workflow harness in `test_workflows.py` needs a producer it can drive
through `.github/scripts/commit-and-push.sh`: something that really reads the
day a repository already published, really appends what this run produced, and
really rewrites the derived payload. The pipeline's own `assemble` cannot be
that producer here. It anchors every path on the installed repository root, so a
test driving it inside a temporary clone would write into the working
repository - and it would put the pipeline under test rather than the git loop.

So this is a real program doing real file I/O with `stage_assemble`'s shape:
read the previous day, drop the items it already carries, replace this run's
entry in the run list, blind-append the two ledgers that blind-append,
deduplicate the one that deduplicates, and rewrite the telemetry projection
whole. It decides nothing - no model, no scorer, no contracts - because the
thing under test is the loop, not the digest.

Usage: rebuild_day.py --date YYYY-MM-DD, from the root of a checkout. This run's
artifacts are read from `backend/var/run/<date>/items.json`, which stands in for
the worker artifacts the assemble job downloads.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Final

PUBLISHED_COLUMNS: Final[tuple[str, ...]] = ("item_id", "published_on")
SCORE_COLUMNS: Final[tuple[str, ...]] = ("item_id", "hhem")
HEALTH_COLUMNS: Final[tuple[str, ...]] = ("date", "item_id", "outcome")


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def rebuild(root: Path, date: str) -> None:
    """Publish this run's items into whatever day the checkout already holds."""
    day_dir = root / "frontend" / "public" / "digest" / date[:4] / date[5:7] / date[8:10]
    month = date[:7]
    artifacts = root / "backend" / "var" / "run" / date / "items.json"
    mine: list[str] = list(json.loads(artifacts.read_text(encoding="utf-8"))["items"])

    previous_path = day_dir / "digest.json"
    previous = (
        json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else None
    )
    carried: list[str] = list(previous["items"]) if previous else []
    runs: list[dict[str, int]] = list(previous["runs"]) if previous else []

    # The run number is read from the day, so it says which run this is only
    # while the day is the one origin holds.
    run_n = max((int(run["n"]) for run in runs), default=0) + 1
    fresh = [item for item in mine if item not in carried]
    runs = [run for run in runs if int(run["n"]) != run_n]
    runs.append({"n": run_n, "items_added": len(fresh)})
    runs.sort(key=lambda run: int(run["n"]))

    _write_json(day_dir / "digest.json", {"date": date, "items": [*carried, *fresh], "runs": runs})
    _write_json(day_dir / "run.json", {"date": date, "runs": runs})

    # Two of the three ledgers append blind, as `ledger._append` does: a row is
    # a fact about a run, and a run that runs twice records twice.
    published = _read_rows(root / "state" / "published.csv")
    published += [{"item_id": item, "published_on": date} for item in mine]
    _write_rows(root / "state" / "published.csv", PUBLISHED_COLUMNS, published)

    health_path = root / "state" / "item-health" / f"{month}.csv"
    health = _read_rows(health_path)
    health += [{"date": date, "item_id": item, "outcome": "published"} for item in mine]
    _write_rows(health_path, HEALTH_COLUMNS, health)

    # The eval ledger refuses an observation it already holds, as
    # `idhazh.evals.writer.append` does.
    scores = _read_rows(root / "state" / "scores.csv")
    already = {row["item_id"] for row in scores}
    scores += [{"item_id": item, "hhem": "0.900"} for item in mine if item not in already]
    _write_rows(root / "state" / "scores.csv", SCORE_COLUMNS, scores)

    # The public projection is a full rewrite of the item-health ledger, never a
    # merge of two of them.
    _write_rows(
        root / "frontend" / "public" / "telemetry" / f"{month}.csv", HEALTH_COLUMNS, health
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild one day of the scripted digest.")
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    rebuild(Path.cwd(), args.date)


if __name__ == "__main__":
    main()
