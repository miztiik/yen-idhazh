"""Measure old and new compaction against the same original fixture in one gate slot."""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from types import CodeType
from typing import TypedDict


class FunctionReading(TypedDict):
    """One profiler function's call count and elapsed seconds."""

    function: str
    calls: int
    self_seconds: float
    total_seconds: float


def _function(code: CodeType | str) -> tuple[str, int, str]:
    """Name a Python function by file and line, or a native function by its profiler label."""
    if isinstance(code, str):
        return "~", 0, code
    return Path(code.co_filename).name, code.co_firstlineno, code.co_name


def measure_fixture(root: Path, original_tests: Path) -> None:
    """Time a real fixture and count the index work of each compaction pass."""
    sys.path[:0] = [str(root / "backend"), str(original_tests)]
    from conftest import seed_item_health
    from gardener.tasks._task import run_task
    from ledger._every_tier import (
        FILED_DAYS,
        KNOBS,
        PASSES,
        ROWS_A_DAY,
        TASK,
        TODAY,
    )
    from retention._trees import health_row

    from idhazh import ledger
    from idhazh.contracts.item_health import ItemStage

    def count_calls(profile: cProfile.Profile) -> dict[str, int]:
        return {
            name: sum(
                entry.callcount for entry in profile.getstats() if _function(entry.code)[2] == name
            )
            for name in ("write_index", "_decide_index", "_take", "resolve")
        }

    with tempfile.TemporaryDirectory() as folder:
        state = Path(folder) / ledger.STATE_DIRNAME
        started = time.perf_counter()
        for number, day in enumerate(FILED_DAYS):
            seed_item_health(
                state,
                day,
                [
                    health_row(
                        day=day, run=1, number=number * ROWS_A_DAY + row, stage=ItemStage.PUBLISH
                    )
                    for row in range(ROWS_A_DAY)
                ],
            )
        passes = []
        for _ in range(PASSES):
            profile = cProfile.Profile()
            start = time.perf_counter()
            profile.enable()
            result = run_task(TASK, Path(folder), today=TODAY, dry_run=False, **KNOBS)
            profile.disable()
            assert result.stopped_because.value == "exhausted", result
            passes.append({"seconds": time.perf_counter() - start, **count_calls(profile)})
        print(json.dumps({"seconds": time.perf_counter() - started, "passes": passes}), flush=True)


def profile_current(root: Path) -> None:
    """Profile one full minimum-span fixture, including its raw seeding."""
    sys.path[:0] = [str(root / "backend"), str(root / "backend" / "tests")]
    from ledger._every_tier import a_census_in_every_tier

    with tempfile.TemporaryDirectory() as folder:
        profile = cProfile.Profile()
        started = time.perf_counter()
        profile.runcall(a_census_in_every_tier, Path(folder))
        readings: list[FunctionReading] = []
        for entry in profile.getstats():
            file, line, name = _function(entry.code)
            readings.append(
                {
                    "function": f"{file}:{line}:{name}",
                    "calls": entry.callcount,
                    "self_seconds": entry.inlinetime,
                    "total_seconds": entry.totaltime,
                }
            )
        print(
            json.dumps(
                {
                    "seconds": time.perf_counter() - started,
                    "by_total": sorted(
                        readings, key=lambda held: held["total_seconds"], reverse=True
                    )[:10],
                    "by_self": sorted(
                        readings, key=lambda held: held["self_seconds"], reverse=True
                    )[:10],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "child":
        measure_fixture(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        current = Path.cwd()
        parser = argparse.ArgumentParser(description=__doc__)
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--baseline", help="Git ref containing the original compaction.")
        selection.add_argument("--profile-current", action="store_true")
        args = parser.parse_args()
        if args.profile_current:
            profile_current(current)
            sys.exit(0)
        archive = subprocess.run(
            ["git", "archive", "--format=zip", args.baseline, "backend", "config"],
            check=True,
            stdout=subprocess.PIPE,
        ).stdout
        with tempfile.TemporaryDirectory() as temporary:
            old = Path(temporary)
            with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
                zipped.extractall(old)
            environment = dict(os.environ)
            environment.pop("PYTHONPATH", None)
            for label, code, tests in (
                ("old-original-span", old, old / "backend" / "tests"),
                ("new-original-span", current, old / "backend" / "tests"),
                ("new-minimum-span", current, current / "backend" / "tests"),
            ):
                print(label, flush=True)
                subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "child", str(code), str(tests)],
                    cwd=code,
                    env=environment,
                    check=True,
                )
