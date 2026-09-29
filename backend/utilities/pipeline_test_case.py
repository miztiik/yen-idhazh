"""Which runners a pipeline-test dispatch starts, and what one of them runs.

`jobs` prints the matrix the plan job hands to GitHub: one entry for every
runner of every test case `config/pipeline-tests.json` switches on. `run` is
what one of those runners does once its model server is healthy: every shard
it holds, all at once against that one server, through the two production
commands a work job runs - `work`, then `record` - and then the run is filed
beside the test case's config for the upload to take.

Every test case runs the same plan, so every test case records the same item
ids. The plan is copied in rather than written here: a runner minting its own
would be a runner reading different articles.

**The exit code is the contract.** `2` means this program was asked for something
it cannot serve - a test case the config does not declare or does not switch
on, a runner that holds no shard, or a dispatch with no plan - and any other
non-zero code is the one the pipeline itself returned. A person reading the run
page can then tell a typo from a test case that really failed.

The faithfulness scorer is skipped. It is a second model download, and this
workflow checks that a model walks the production path quickly; how good its
summaries are is `validate.yml`'s question.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from idhazh.contracts.pipeline_tests import PipelineTestsConfig

#: What a call this program cannot serve exits with.
REFUSED = 2

#: Where each test case's tree lives: the config root the config step writes,
#: and the run this program files beside it. The config writer and the report
#: import it from here, so the three programs cannot name two folders.
TEST_CASES_ROOT = Path("backend/var/test-cases")

#: The one plan every test case runs, written by the plan job before any runner
#: starts.
PLAN = Path("backend/var/pipeline-tests/plan.json")

#: Where a run writes, before the test case takes it.
RUN_ROOT = Path("backend/var/run")

#: The key the plan job publishes the matrix under.
JOBS_KEY = "jobs"


def jobs(settings: PipelineTestsConfig) -> str:
    """The `key=value` line the plan job appends to `$GITHUB_OUTPUT`.

    Compact JSON, because a step output is one line.
    """
    matrix = [
        {"test_case": test_case.id, "runner": runner} for test_case, runner in settings.runs()
    ]
    return f"{JOBS_KEY}={json.dumps(matrix, separators=(',', ':'))}"


def _stage(stage: str, *, date: str, config_root: Path, shard: int, shards: int) -> list[str]:
    """One production command, on the interpreter that started this program."""
    return [
        sys.executable,
        "-m",
        "idhazh",
        stage,
        "--date",
        date,
        "--config",
        config_root.as_posix(),
        "--shard",
        str(shard),
        "--shards",
        str(shards),
    ]


def _refuse(message: str) -> int:
    print(message, file=sys.stderr)
    return REFUSED


def run(settings: PipelineTestsConfig, test_case_id: str, date: str, runner: int) -> int:
    """Work every shard this runner holds at once, record each, and file the run.

    A process per shard, because a shard is a process with its own memory in
    production too, and these share one server the way production's one shard
    does. `record` runs even when a shard failed: it keeps the rows of every item
    that did settle. A runner whose shard failed files no run, so the report
    names its articles as missing rather than reading half a run as a result.
    """
    test_case = next((one for one in settings.test_cases if one.id == test_case_id), None)
    if test_case is None:
        return _refuse(
            f"unknown test case {test_case_id} - config/pipeline-tests.json declares no such id"
        )
    if not test_case.enabled:
        return _refuse(f"test case {test_case.id} is switched off in config/pipeline-tests.json")
    test_case_root = TEST_CASES_ROOT / test_case.id
    config_root = test_case_root / "config"
    if not config_root.is_dir():
        return _refuse(
            f"test case {test_case.id} has no config - the config step writes "
            f"{config_root.as_posix()}"
        )
    held = settings.shards_on(test_case, runner)
    if not held:
        return _refuse(f"runner {runner} of test case {test_case.id} holds no shard")
    # `idhazh work` with an absent plan fails four steps later about a file a
    # reader of the log has to go and find. This names what is missing.
    if not PLAN.is_file():
        return _refuse("no plan to run - the plan job comes before every test case")

    run_root = RUN_ROOT / date
    shutil.rmtree(run_root, ignore_errors=True)
    shutil.rmtree(test_case_root / "run", ignore_errors=True)
    run_root.mkdir(parents=True)
    shutil.copy(PLAN, run_root / "plan.json")

    shards = settings.shard_count()
    started = time.monotonic()
    working = [
        subprocess.Popen(
            [
                *_stage("work", date=date, config_root=config_root, shard=shard, shards=shards),
                "--no-faithfulness",
            ]
        )
        for shard in held
    ]
    failed = [code for code in (worker.wait() for worker in working) if code != 0]
    for shard in held:
        recorded = subprocess.run(
            _stage("record", date=date, config_root=config_root, shard=shard, shards=shards),
            check=False,
        )
        if recorded.returncode != 0:
            print(f"::warning::shard {shard} of {test_case.id} recorded no rows", file=sys.stderr)
    print(
        f"test case {test_case.id} runner {runner} worked shards {list(held)} of {shards} "
        f"in {int(time.monotonic() - started)} seconds"
    )
    if failed:
        return failed[0]
    shutil.move(run_root, test_case_root / "run")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    verbs = parser.add_subparsers(dest="verb", required=True)
    verbs.add_parser("jobs", help="Print the matrix of runners the enabled test cases need.")
    one = verbs.add_parser("run", help="Work the shards one runner of a test case holds.")
    one.add_argument("test_case", help="an id config/pipeline-tests.json switches on")
    one.add_argument("date", help="the day the plan was written for")
    one.add_argument("--runner", type=int, default=0, help="which of the test case's runners")
    args = parser.parse_args(argv)

    settings = PipelineTestsConfig.from_json(
        (args.config_root / "pipeline-tests.json").read_text(encoding="utf-8")
    )
    if args.verb == "jobs":
        print(jobs(settings))
        return 0
    return run(settings, args.test_case, args.date, args.runner)


if __name__ == "__main__":
    raise SystemExit(main())