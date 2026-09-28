"""Run one test case of the pipeline test over the two articles the draw chose.

Every test case runs the same plan, so the test cases record the same two item
ids and the numbers between them can be subtracted. The plan is copied in rather
than written here: one test case minting its own would be one test case reading
different articles, which is the whole failure this workflow exists to avoid.

**The exit code is the contract.** `2` means this program was asked for something
it cannot serve - a test case id the config does not declare, or a dispatch with
no plan - and any other non-zero code is the one the pipeline itself returned. A
person reading the run page can then tell a typo from a test case that really
failed, and the three test case steps run on `!cancelled()` so the other two
still report.

The faithfulness scorer is skipped. It is a second model download, it is the
same in every test case so it cancels from every comparison here, and it is not
what the two-call path is being measured for.
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

#: Where each test case's tree lives: the config root the config step writes,
#: and the run this program files beside it. The config writer and the report
#: import it from here, so the three programs cannot name two folders.
TEST_CASES_ROOT = Path("backend/var/test-cases")

#: The one plan every test case runs, written by the plan step before any test
#: case.
PLAN = Path("backend/var/pipeline-tests/plan.json")

#: Where a run writes, before the test case takes it.
RUN_ROOT = Path("backend/var/run")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("test_case", help="an id declared in config/pipeline-tests.json")
    parser.add_argument("date", help="the day the plan was written for")
    args = parser.parse_args(argv)

    test_case_root = TEST_CASES_ROOT / args.test_case
    # The test case has to be one config declares. A typo would otherwise run
    # the committed config under another test case's name and report it as that
    # test case's number.
    if not (test_case_root / "config").is_dir():
        print(
            f"unknown test case {args.test_case} - config/pipeline-tests.json declares no such id",
            file=sys.stderr,
        )
        return REFUSED

    # `idhazh work` with an absent plan fails four steps later about a file a
    # reader of the log has to go and find. This names what is missing.
    if not PLAN.is_file():
        print(
            "no plan to run - the draw and the plan step come before every test case",
            file=sys.stderr,
        )
        return REFUSED

    run_root = RUN_ROOT / args.date
    shutil.rmtree(run_root, ignore_errors=True)
    shutil.rmtree(test_case_root / "run", ignore_errors=True)
    run_root.mkdir(parents=True)
    shutil.copy(PLAN, run_root / "plan.json")

    started = time.monotonic()
    # A subprocess, because a test case is meant to run the way a shard does and
    # a shard is a process with its own memory. `sys.executable` rather than a
    # bare `python`, so the test case runs on the interpreter that started this.
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "idhazh",
            "work",
            "--date",
            args.date,
            "--config",
            str(test_case_root / "config"),
            "--no-faithfulness",
        ],
        check=False,
    )
    if done.returncode != 0:
        return done.returncode

    print(f"test case {args.test_case} took {int(time.monotonic() - started)} seconds")
    shutil.move(run_root, test_case_root / "run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
