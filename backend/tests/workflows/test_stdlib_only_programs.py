"""Can a program a job runs outside its install start when `pip install -e .` did not?

Five programs in this repository are held to the standard library at import.
The one that replaces a stale `state/` with what origin's tip carries puts a run
back in a state it can work from, and a job reaches it when something has
already gone wrong - a failed install is one of those things. The history job's
due check runs on a shallow checkout before any install at all, and it is what
decides whether the job goes on to rewrite `main`. The history job's squash
program keeps its push and the refusal in front of it drivable by a test with
nothing of this project loaded. The gardener's plan job splits the tasks into
shards on a checkout of two folders, and installs nothing at all. The Pages
workflow decides whether to publish on a bare checkout, before any install.
The gardener's programs import one module of ours as they start, to print a
crash without its text, so that module is held to the same.

Module scope only. A name imported inside a function is resolved when that
function runs, and the squash program imports `idhazh` in the one function that
reads its declaration.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Final

import pytest
from conftest import read_text

from ._harness import (
    CRASH_TRACE_MODULE,
    GARDENER_PLAN_MODULE,
    PRUNE_PUSH_MODULE,
    PUBLISH_DECISION_MODULE,
    SQUASH_DUE_MODULE,
    TAKE_STATE_MODULE,
)

pytestmark = pytest.mark.workflow

#: Every program held to this, and the one module the gardener's programs import
#: as they start, named one by one. A sixth program a broken job reaches for is
#: declared here or it is held to nothing.
STANDALONE_PROGRAMS: Final = (
    TAKE_STATE_MODULE,
    SQUASH_DUE_MODULE,
    PRUNE_PUSH_MODULE,
    GARDENER_PLAN_MODULE,
    PUBLISH_DECISION_MODULE,
    CRASH_TRACE_MODULE,
)


def _imports_at_module_scope(source: str, filename: str) -> list[str]:
    """Every module a program names at import time, by the name it writes."""
    named: list[str] = []
    for node in ast.parse(source, filename=filename).body:
        if isinstance(node, ast.Import):
            named.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            named.append(node.module)
    return named


@pytest.mark.parametrize("program", STANDALONE_PROGRAMS, ids=lambda path: path.name)
def test_a_program_a_broken_job_runs_imports_only_the_standard_library(program: Path) -> None:
    outside = sorted(
        name
        for name in _imports_at_module_scope(read_text(program), program.name)
        if name != "__future__" and name.split(".")[0] not in sys.stdlib_module_names
    )
    assert not outside, (
        f"{program.name} resolves {', '.join(outside)} at import time, so it dies "
        "in a job whose install failed - which is a job that runs it"
    )
