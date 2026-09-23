"""Rebuild a day the way `stage_assemble` does, with no pipeline behind it.

The workflow harness in `_harness.py` needs a producer it can drive
through `backend/utilities/commit_and_push.py`: something that really reads the
day a repository already published, really appends what this run produced, and
really rewrites the derived payload. The pipeline's own `assemble` cannot be
that producer here. It anchors every path on the installed repository root, so a
test driving it inside a temporary clone would write into the working
repository - and it would put the pipeline under test rather than the git loop.

So this is a real program doing real file I/O with `stage_assemble`'s shape:
read the previous day, drop the items it already carries, replace this run's
entry in the run list, copy each decision's asset path into the day the way
`to_digest_visual` does, blind-append the one ledger that blind-appends, write
the two day trees one file per writer, and rebuild the month search index from
the days on disk. It decides nothing - no model, no scorer, no contracts -
because the thing under test is the loop, not the digest.

Usage: rebuild_day.py --date YYYY-MM-DD --writer NAME, from the root of a
checkout. This run's artifacts are read from `backend/var/run/<date>/items.json`,
which stands in for the worker artifacts the assemble job downloads. `--writer`
is the filename this run owns inside a day directory. The harness builds it
through `ledger.segment_name`, so a name spelled here could not drift from the
name a run produces.
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


def _read_day(day_dir: Path, *, without: str = "") -> list[dict[str, str]]:
    """Every writer's rows for one day, in the order a settlement reads them."""
    if not day_dir.is_dir():
        return []
    return [
        row
        for path in sorted(day_dir.glob("*.csv"))
        if path.name != without
        for row in _read_rows(path)
    ]


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
    """Where this run's decisions say their published marks landed.

    `stage_assemble` copies each decision's `data_path` into the day payload
    verbatim, so the payload and the files on disk agree only while something
    keeps them agreeing. A stand-in that skipped this could not tell a day that
    publishes a picture from a day that points at a file nobody wrote.
    """
    items = root / "backend" / "var" / "run" / date / "items"
    if not items.is_dir():
        return {}
    found: dict[str, str] = {}
    for path in sorted(items.glob("*.visual.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        marks = payload.get("data_path")
        if marks:
            found[str(payload["item_id"])] = str(marks)
    return found


def rebuild(root: Path, date: str, writer: str) -> None:
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
    decided = _read_visuals(root, date)
    visuals: dict[str, str] = dict(previous["visuals"]) if previous else {}
    visuals.update({item: decided[item] for item in fresh if item in decided})

    _write_json(
        day_dir / "digest.json",
        {"date": date, "items": [*carried, *fresh], "runs": runs, "visuals": visuals},
    )
    _write_json(day_dir / "run.json", {"date": date, "runs": runs})

    # `state/published` appends blind, as `ledger.extend_ledger_file` does: a row
    # is a fact about a run, and a run that runs twice records twice. It is one
    # day file that two runs can both append to, and a union merge driver is
    # what settles them.
    published_path = root / "state" / "published" / date[:4] / date[5:7] / f"{date[8:10]}.csv"
    published = _read_rows(published_path)
    published += [{"item_id": item, "published_on": date} for item in mine]
    _write_rows(published_path, PUBLISHED_COLUMNS, published)

    # The other two are day directories, and this run writes the one file it
    # owns inside each. Two runs of one day write two names, so there is nothing
    # for a merge to settle and nothing a rebase has to choose between.
    health_day = root / "state" / "item-health" / date[:4] / date[5:7] / date[8:10]
    _write_rows(
        health_day / writer,
        HEALTH_COLUMNS,
        [{"date": date, "item_id": item, "outcome": "published"} for item in mine],
    )

    # The eval ledger refuses an observation another writer already recorded, as
    # `idhazh.evals.writer.append_segment` does. Its own file is excluded from
    # that read: a rerun replaces the file this writer owns rather than adding
    # to it, so counting its own rows as already recorded would empty it.
    scores_day = root / "state" / "scores" / date[:4] / date[5:7] / date[8:10]
    already = {
        row["item_id"] for row in _read_day(scores_day, without=writer)
    }
    _write_rows(
        scores_day / writer,
        SCORE_COLUMNS,
        [{"item_id": item, "hhem": "0.900"} for item in mine if item not in already],
    )

    # The public projection is a full rewrite of the month the day falls in,
    # folded from that month's days, never a merge of two of them.
    health_month = root / "state" / "item-health" / date[:4] / date[5:7]
    _write_rows(
        root / "frontend" / "public" / "telemetry" / f"{month}.csv",
        HEALTH_COLUMNS,
        [row for day in sorted(health_month.glob("*")) if day.is_dir() for row in _read_day(day)],
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
        {"date": date, "sources": sorted({row["item_id"] for row in _read_day(health_day)})},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild one day of the scripted digest.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--writer", required=True)
    args = parser.parse_args()
    rebuild(Path.cwd(), args.date, args.writer)


if __name__ == "__main__":
    main()
