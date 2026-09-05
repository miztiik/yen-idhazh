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
entry in the run list, copy each route's asset path into the day the way
`to_digest_visual` does, blind-append the two ledgers that blind-append,
deduplicate the one that deduplicates, rewrite the telemetry projection whole,
and rebuild the month search index from the days on disk. It decides nothing -
no model, no scorer, no contracts - because the thing under test is the loop,
not the digest.

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


def _read_visuals(root: Path, date: str) -> dict[str, str]:
    """Where this run's routes say their rendered assets landed.

    `stage_assemble` copies each route's `asset_path` into the day payload
    verbatim, so the payload and the files on disk agree only while something
    keeps them agreeing. A stand-in that skipped this could not tell a day that
    publishes a picture from a day that publishes a broken image.
    """
    items = root / "backend" / "var" / "run" / date / "items"
    if not items.is_dir():
        return {}
    found: dict[str, str] = {}
    for path in sorted(items.glob("*.visual.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        asset = payload.get("asset_path")
        if asset:
            found[str(payload["item_id"])] = str(asset)
    return found


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

    # An item already published keeps the picture it published with, as
    # `build_day` does: only a fresh item brings one.
    routed = _read_visuals(root, date)
    visuals: dict[str, str] = dict(previous["visuals"]) if previous else {}
    visuals.update({item: routed[item] for item in fresh if item in routed})

    _write_json(
        day_dir / "digest.json",
        {"date": date, "items": [*carried, *fresh], "runs": runs, "visuals": visuals},
    )
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
    scores = _read_rows(root / "state" / "scores" / "2026-08.csv")
    already = {row["item_id"] for row in scores}
    scores += [{"item_id": item, "hhem": "0.900"} for item in mine if item not in already]
    _write_rows(root / "state" / "scores" / "2026-08.csv", SCORE_COLUMNS, scores)

    # The public projection is a full rewrite of the item-health ledger, never a
    # merge of two of them.
    _write_rows(
        root / "frontend" / "public" / "telemetry" / f"{month}.csv", HEALTH_COLUMNS, health
    )

    # The month search index is derived from the days on disk, so it is rebuilt
    # rather than merged - which is what lets the loop hand it back to origin
    # and rerun this producer against origin's tip.
    index_dir = root / "frontend" / "public" / "assist" / "index"
    month_dir = root / "frontend" / "public" / "digest" / date[:4] / date[5:7]
    entries: list[dict[str, object]] = []
    for payload_path in sorted(month_dir.glob("*/digest.json")):
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        entries += [{"date": payload["date"], "item_id": item} for item in payload["items"]]
    _write_json(index_dir / f"{month}.json", {"month": month, "entries": entries})
    (index_dir / f"{month}.bin").write_bytes(bytes(len(entries)))

    # The source-health view is a projection of `state/`, rewritten whole every
    # run for the reason the telemetry shard is: a merge of two of them is a
    # census of neither. It is a named file rather than a directory, which is
    # what `_seed_ledger` in the harness has to know about it.
    _write_json(
        root / "frontend" / "public" / "source-health.json",
        {"date": date, "sources": sorted({row["item_id"] for row in health})},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild one day of the scripted digest.")
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    rebuild(Path.cwd(), args.date)


if __name__ == "__main__":
    main()
