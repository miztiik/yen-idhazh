"""Run one case of the pipeline test over the two articles the draw chose.

Every case runs the same plan, so the cases record the same two item ids and the
numbers between them can be subtracted. The plan is copied in rather than
written here: one case minting its own would be one case reading different
articles, which is the whole failure this workflow exists to avoid.

**The exit code is the contract.** `2` means this program was asked for something
it cannot serve - a case id the config does not declare, or a dispatch with no
plan - and any other non-zero code is the one the pipeline itself returned. A
person reading the run page can then tell a typo from a case that really failed,
and the three case steps run on `!cancelled()` so the other two still report.

The faithfulness scorer is skipped. It is a second model download, it is the
same in every case so it cancels from every comparison here, and it is not what
the two-call path is being measured for.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

#: What a call this program cannot serve exits with.
REFUSED = 2

#: Where the case-config step writes one config root per declared case.
CASES_ROOT = Path("backend/var/cases")

#: The one plan every case runs, written by the plan step before any case.
PLAN = Path("backend/var/pipeline-tests/plan.json")

#: Where a run writes, before the case takes it.
RUN_ROOT = Path("backend/var/run")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", help="an id declared in config/pipeline-tests.json")
    parser.add_argument("date", help="the day the plan was written for")
    args = parser.parse_args(argv)

    case_root = CASES_ROOT / args.case
    # The case has to be one config declares. A typo would otherwise run the
    # committed config under another case's name and report it as that case's
    # number.
    if not (case_root / "config").is_dir():
        print(
            f"unknown case {args.case} - config/pipeline-tests.json declares no such id",
            file=sys.stderr,
        )
        return REFUSED

    # `idhazh work` with an absent plan fails four steps later about a file a
    # reader of the log has to go and find. This names what is missing.
    if not PLAN.is_file():
        print(
            "no plan to run - the draw and the plan step come before every case",
            file=sys.stderr,
        )
        return REFUSED

    run_root = RUN_ROOT / args.date
    shutil.rmtree(run_root, ignore_errors=True)
    shutil.rmtree(case_root / "run", ignore_errors=True)
    run_root.mkdir(parents=True)
    shutil.copy(PLAN, run_root / "plan.json")

    started = time.monotonic()
    # A subprocess, because a case is meant to run the way a shard does and a
    # shard is a process with its own memory. `sys.executable` rather than a
    # bare `python`, so the case runs on the interpreter that started this.
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "idhazh",
            "work",
            "--date",
            args.date,
            "--config",
            str(case_root / "config"),
            "--no-faithfulness",
        ],
        check=False,
    )
    if done.returncode != 0:
        return done.returncode

    print(f"case {args.case} took {int(time.monotonic() - started)} seconds")
    shutil.move(run_root, case_root / "run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
