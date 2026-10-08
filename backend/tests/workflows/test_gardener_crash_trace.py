"""Does every gardener program and operator command print a crash as where it broke, never what it said?

Each case runs one program the way its job does, or one command the way a
person types it, in a fresh interpreter, through a driver. The driver raises an
exception carrying planted text and, while it handles that one, runs the
program as `__main__` on an input the program's own code cannot read: a config
folder with no config in it, a corpus stamp that is a folder, or a state tree
whose door holds a file where a day's folder goes. The path carries the planted
text, so the exception that ends the program quotes it, and so does the
exception chained to it. Python's own trace prints both messages (Guardrail
#11). Nothing is replaced: the program raises on real input, and Python chains
the two.

The plan job and the due check install nothing, so their cases run with
`-I -S`: no site packages, and no folder on the path but the one the program
puts there itself.

No workflow runs the three operator commands. The two `idhazh` commands run
through the package's `__main__.py`, which calls the `main` the console script
calls, and `run-task` stands for the gardener's three subcommands, which share
one `main`. The ledger migrator runs as a person runs it.

The last test holds the four workflow programs to every command in the workflow
that starts Python, so a fifth program cannot land without a case here. What
the trace holds for any chain is `test_crash_trace.py`.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final, NamedTuple

import pytest
from conftest import REPO_ROOT, SEED_COMMIT
from ledger_migration._fixtures import ITEM, OLD, item_row, write_csv, writer_file_name

from idhazh import ledger
from idhazh.contracts.base import ServerJob

from ._harness import (
    GARDENER_PLAN_MODULE,
    GARDENER_SHARD_MODULE,
    PRUNE_PUSH_MODULE,
    SQUASH_DUE_MODULE,
    _load_workflows,
    _mapping,
    _steps,
)

pytestmark = pytest.mark.workflow

WORKFLOW: Final = "idhazh-gardener.yml"

#: The package's own entry: the console script `idhazh` and `python -m idhazh`
#: both call the `main` this runs.
IDHAZH_ENTRY: Final = REPO_ROOT / "backend" / "idhazh" / "__main__.py"

#: The ledger migrator, which a person runs to move a CSV tree onto the door.
MIGRATOR: Final = REPO_ROOT / "backend" / "utilities" / "migrate_to_parquet.py"

#: What a fetched page might say, planted in the driver's exception; and the part
#: of it that the program's input path carries too, which no line may hold.
FETCHED: Final = "Breaking: click https://example.invalid/now"
PLANTED: Final = "example.invalid"

#: A run and a day the programs accept, so each gets as far as its input.
RUN_ID: Final = "2026-10-07-1"
TODAY: Final = "2026-10-07"

#: Raises an exception carrying the planted text and, while handling it, runs the
#: program named first after `-c` as `__main__`, with the rest as its arguments.
DRIVER: Final = (
    "import runpy, sys\n"
    "sys.argv = sys.argv[1:]\n"
    "try:\n"
    f"    raise LookupError({FETCHED!r})\n"
    "except LookupError:\n"
    "    runpy.run_path(sys.argv[0], run_name='__main__')\n"
)

HEADER: Final = "Traceback (most recent call last):"
CONTEXT: Final = "During handling of the above exception, another exception occurred:"

#: Every line a trace holds: the header, a frame, a sentence between two
#: exceptions, a type, or a blank.
TRACE_LINE: Final = re.compile(
    r"Traceback \(most recent call last\):"
    r"|  (?:\w+(?:\.\w+)*|\?):\d+"
    r"|The above exception was the direct cause of the following exception:"
    r"|During handling of the above exception, another exception occurred:"
    r"|\w+(?:\.\w+)*"
    r"|"
)

#: What a GitHub step sets, so a program run here never writes into CI's own step.
STEP_VARIABLES: Final = frozenset({"GITHUB_ACTIONS", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY"})

#: The commands that start Python: both interpreters, and the console script
#: `pyproject.toml` declares.
STARTS_PYTHON: Final = frozenset({"python", "python3", "idhazh"})


class Crash(NamedTuple):
    """One program or command, whether its job installs nothing first, and the input that ends it."""

    program: Path
    installs_nothing: bool
    #: Builds the input under a test's folder, and returns the program's
    #: arguments and the type of the exception that ends it.
    inputs: Callable[[Path], tuple[list[str], str]]
    #: The words of an `idhazh` command line before its arguments; none for a program.
    verb: tuple[str, ...] = ()

    @property
    def command(self) -> str:
        """The case's name: the `idhazh` command line, hyphenated, or the program's file name."""
        return "-".join(("idhazh", *self.verb)) if self.verb else self.program.name


def no_gardener_config(root: Path) -> str:
    """A config folder that does not exist, at a path that carries the planted text."""
    return str(root / PLANTED)


def the_planner_crashes(root: Path) -> tuple[list[str], str]:
    return ["--config-root", no_gardener_config(root)], "FileNotFoundError"


def a_shard_crashes(root: Path) -> tuple[list[str], str]:
    arguments = ["compact-gardener", "--run-id", RUN_ID, "--attempt", "1"]
    return [
        *arguments,
        "--repo-root",
        str(root),
        "--config",
        no_gardener_config(root),
    ], "FileNotFoundError"


def the_due_check_crashes(root: Path) -> tuple[list[str], str]:
    """The squash's declaration reads, and its stamp is a folder that reading refuses."""
    declared = root / "config" / "gardener" / "corpus-squash.json"
    declared.parent.mkdir(parents=True)
    window = {"unit": "days", "value": 60}
    declared.write_text(
        json.dumps({"every_days": 30, "lifecycle_status": "active", "window": window}),
        encoding="ascii",
    )
    stamp = root / PLANTED
    stamp.mkdir()
    arguments = ["--config-root", str(root / "config"), "--corpus-meta", str(stamp)]
    return arguments, what_reading_refuses(stamp)


def the_squash_crashes(root: Path) -> tuple[list[str], str]:
    arguments = ["--today", TODAY, "--run-id", RUN_ID, "--attempt", "1"]
    return [
        *arguments,
        "--repo-root",
        str(root),
        "--config",
        no_gardener_config(root),
    ], "FileNotFoundError"


def what_reading_refuses(folder: Path) -> str:
    """What reading a folder as a file raises here: IsADirectoryError, or on Windows PermissionError."""
    try:
        folder.read_text(encoding="utf-8")
    except OSError as refused:
        return type(refused).__name__
    raise AssertionError(f"{folder} reads as a file, so it cannot end the program")


def a_gardener_task_crashes(root: Path) -> tuple[list[str], str]:
    """`run-task` in the test's own folder, so nothing it runs can reach this checkout."""
    arguments = ["compact-gardener", "--run-id", RUN_ID, "--attempt", "1"]
    return [
        *arguments,
        "--git-sha",
        SEED_COMMIT,
        "--repo-root",
        str(root),
        "--config",
        no_gardener_config(root),
    ], "FileNotFoundError"


def a_prune_crashes(root: Path) -> tuple[list[str], str]:
    """A dry run over one day, of a state tree in the test's own folder."""
    arguments = ["--target", "feed-health", "--since", TODAY, "--until", TODAY]
    return [
        *arguments,
        "--state-root",
        str(root / "state"),
        "--config",
        no_gardener_config(root),
    ], "FileNotFoundError"


def a_migration_crashes(root: Path) -> tuple[list[str], str]:
    """A CSV day filed into a door that holds a file where the day's folder goes.

    The migrator turns a fault in what it reads into a refusal it prints on
    purpose, which keeps its words. A fault in what it writes is not caught: the
    write cannot make the day's folder, and the exception names that path. The
    text is planted in a folder above the state tree, because the migrator
    prints a root outside the checkout by its last folder name, on purpose.
    """
    state = root / PLANTED / "state"
    row = item_row(OLD, "ai-01", machine=True)
    write_csv(state, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [row.csv_row()])
    day = ledger.raw_root(state, ITEM).joinpath(*OLD.split("-"))
    day.parent.mkdir(parents=True)
    day.write_text("a file where the day's folder goes", encoding="ascii")
    arguments = ["--state-dir", str(state), "--month", OLD[:7], "--ledger", ITEM.value]
    return [
        *arguments,
        "--run-id",
        RUN_ID,
        "--git-sha",
        SEED_COMMIT,
        "--write",
    ], "FileExistsError"


#: The four programs the workflow runs, each with the input that ends it.
CRASHES: Final = (
    Crash(GARDENER_PLAN_MODULE, True, the_planner_crashes),
    Crash(GARDENER_SHARD_MODULE, False, a_shard_crashes),
    Crash(SQUASH_DUE_MODULE, True, the_due_check_crashes),
    Crash(PRUNE_PUSH_MODULE, False, the_squash_crashes),
)

#: The three commands a person runs on gardener code, which no workflow runs.
OPERATOR_CRASHES: Final = (
    Crash(IDHAZH_ENTRY, False, a_gardener_task_crashes, ("gardener", "run-task")),
    Crash(IDHAZH_ENTRY, False, a_prune_crashes, ("telemetry", "prune")),
    Crash(MIGRATOR, False, a_migration_crashes),
)


def main_call(program: Path) -> str:
    """The frame of the program's own `main()` call in its `__main__` block, as a trace prints it."""
    calls = [
        number
        for number, line in enumerate(program.read_text(encoding="utf-8").splitlines(), start=1)
        if line.strip().endswith("(main())")
    ]
    assert len(calls) == 1, f"{program.name} calls main() on {len(calls)} lines"
    return f"  __main__:{calls[0]}"


def programs_started(script: str) -> set[str]:
    """What each command of a step's script that starts Python runs: the word after it."""
    words = shlex.split(script, comments=True)
    return {
        words[at + 1] if at + 1 < len(words) else word
        for at, word in enumerate(words)
        if word in STARTS_PYTHON
    }


@pytest.mark.parametrize("crash", [*CRASHES, *OPERATOR_CRASHES], ids=lambda crash: crash.command)
def test_a_crash_prints_each_exceptions_type_and_frames_and_never_its_text(
    tmp_path: Path, crash: Crash
) -> None:
    arguments, ended_by = crash.inputs(tmp_path)
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("PYTHON") and name not in STEP_VARIABLES
    }
    flags = ["-I", "-S"] if crash.installs_nothing else []
    if not crash.installs_nothing:
        env["PYTHONPATH"] = str(REPO_ROOT / "backend")

    done = subprocess.run(
        [sys.executable, *flags, "-c", DRIVER, str(crash.program), *crash.verb, *arguments],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 1, "Python's own code for an exception, as before"
    assert PLANTED not in done.stdout + done.stderr, done.stderr
    printed = done.stderr.splitlines()
    assert HEADER in printed, done.stderr
    trace = printed[printed.index(HEADER) :]
    assert [line for line in trace if not TRACE_LINE.fullmatch(line)] == []
    assert trace[-1] == ended_by
    assert "LookupError" in trace
    assert CONTEXT in trace
    assert main_call(crash.program) in trace


def test_every_command_the_workflow_starts_python_with_runs_a_program_crashed_here() -> None:
    """A `python -m` step or an `idhazh` step starts Python too, and names no program here."""
    workflow = _load_workflows()[WORKFLOW]
    started = {
        program
        for job in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job)
        if isinstance(step.get("run"), str)
        for program in programs_started(str(step["run"]))
    }

    assert started == {crash.program.relative_to(REPO_ROOT).as_posix() for crash in CRASHES}
