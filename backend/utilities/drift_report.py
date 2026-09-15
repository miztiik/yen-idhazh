"""Has anything moved between the recent window and the baseline one?"""

from __future__ import annotations

import argparse
import datetime
import os
from pathlib import Path

from idhazh.config import load
from idhazh.drift import issue_body, read_windows, report

ISSUE_FILE = Path("drift-issue.txt")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recent-days", type=int, required=True)
    parser.add_argument("--baseline-days", type=int, required=True)
    parser.add_argument("--state-root", type=Path, default=Path("state"))
    args = parser.parse_args(argv)

    windows = read_windows(
        args.state_root,
        today=datetime.datetime.now(datetime.UTC).date(),
        recent_days=args.recent_days,
        baseline_days=args.baseline_days,
    )
    config = load().app.drift
    text, status = report(windows, config=config)
    print(text)
    if status == 0:
        run_url = (
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
            f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
        )
        body = issue_body(windows, config=config, run_url=run_url)
        ISSUE_FILE.write_text(body, encoding="utf-8", newline="\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
