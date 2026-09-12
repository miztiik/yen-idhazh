"""Write the day-metrics record for every already-published day, once.

The pipeline writes one record per published day at publication
(`idhazh.publish_day_metrics`). The days already on disk were published before
that producer existed, so this one-time pass gives each of them the same record
a fresh publication would - read from the committed day and its committed ledger
slice, written to `state/day-metrics/<YYYY>/<MM>/<DD>.json`.

Operator tooling. It runs by hand, reads the committed record and writes
committed state, and reaches no reader.

A walk over every published day is the growing cost Guardrail #12 keeps out of the
pipeline - which is why the pipeline writes one record per run and this walk runs
once, by a person, to seed the days that predate the producer. Each day's
figures are still read from that one day's month shard, so the work for any one
day does not itself grow with the archive.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from idhazh import config, ledger, publish_day_metrics
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.run_manifest import RunManifest


def published_days(digest_root: Path) -> list[Path]:
    """Every committed `digest.json`, oldest first, by its `<YYYY>/<MM>/<DD>` path."""
    return sorted(digest_root.glob("*/*/*/digest.json"))


def backfill(digest_root: Path, state_root: Path) -> list[Path]:
    """Rewrite the record for each published day from its own committed slice."""
    written: list[Path] = []
    for digest_path in published_days(digest_root):
        day = DigestDay.read(digest_path)
        manifest = RunManifest.read(digest_path.parent / "run.json")
        written.append(
            publish_day_metrics.publish(
                state_root=state_root, date=day.date, day=day, manifest=manifest
            )
        )
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--digest",
        type=Path,
        default=config.REPO_ROOT / "frontend" / "public" / "digest",
        help="The published digest tree to read.",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=config.REPO_ROOT / ledger.STATE_DIRNAME,
        help="The state tree to write the records under.",
    )
    args = parser.parse_args()

    written = backfill(args.digest, args.state)
    for path in written:
        print(f"wrote {path.relative_to(config.REPO_ROOT).as_posix()}")
    print(f"wrote {len(written)} day-metrics record(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
