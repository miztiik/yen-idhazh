"""Can the console stop reading `pipeline_fingerprint`, and what still holds it?

The operator console decides a day's pipeline identity from one of two records.
A day that recorded an input manifest is read from `run.json`. Every other day
falls back to the `pipeline_fingerprint` column of the score ledger, which says
that something moved without saying what. That fallback exists only for days
written before the manifest did, so it retires itself: once no score row the
widest console window can reach carries a stamp, the column and the code that
reads it are dead weight, and the score loop walks the window to build an empty
map on every build.

That is a fact about the rows, so a person asks the rows. This prints the
answer and changes nothing.

A day is read the way the ledger's own readers read one: every writer's file
in the day's directory and the day's `settled.csv`, settled into one row per
measurement, so a row held by both is counted once. The read is bounded by
`console.max_window_days` rather than by how much the archive has accumulated
(CLAUDE.md Guardrail #12).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from idhazh import day_shards, ledger
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.ledger_name import LedgerName

COLUMN = "pipeline_fingerprint"


def _stamped_rows(rows: list[dict[str, str]]) -> int:
    """Rows of one settled day that carry a stamp.

    A row written after the cutover still has the column; what it does not
    have is a value in it. An empty string is not a stamp, and counting the
    column instead of its contents would report the fallback as load-bearing forever.
    """
    return sum(1 for row in rows if (row.get(COLUMN) or "").strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=Path("state"))
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        help="Anchor the window on this date instead of today, for a dry run.",
    )
    args = parser.parse_args(argv)

    settings = json.loads((args.config_root / "idhazh.json").read_text(encoding="utf-8"))
    window = settings["console"]["max_window_days"]
    today = args.today or datetime.now(tz=UTC).date()
    scores_root = ledger.tree_root(args.state_root, LedgerName.SCORES)

    read = 0
    stamped_days: list[str] = []
    stamped_rows = 0
    for offset in range(window):
        day = (today - timedelta(days=offset)).isoformat()
        if not day_shards.one_day(scores_root, day):
            continue
        read += 1
        rows = _stamped_rows(
            day_shards.settled_day(scores_root, day, ledger.OBSERVATION_KEY, EvalRow)
        )
        if rows:
            stamped_days.append(day)
            stamped_rows += rows

    newest = max(stamped_days) if stamped_days else None
    # The window walks backwards from today, so a stamped day leaves the window
    # `window` days after it was written. That is the earliest the fallback can go.
    clear_on = (date.fromisoformat(newest) + timedelta(days=window)).isoformat() if newest else None

    print(f"due={'true' if not stamped_days else 'false'}")
    print(f"window_days={window}")
    print(f"days_read={read}")
    print(f"stamped_days={len(stamped_days)}")
    print(f"stamped_rows={stamped_rows}")
    print(f"newest_stamped_day={newest or 'none'}")
    print(f"clear_on={clear_on or 'now'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
