"""Can a program that repairs a job's own checkout start when `pip install -e .` did not?

Two steps in this repository exist to put a run back in a state it can work
from: the one that replaces a stale `state/` with what origin's tip carries, and
the one that pushes the history the prune rewrote. A job reaches both of them
when something about that job has already gone wrong, and a failed install is
one of the things that goes wrong - so a name either program resolved at import
time would take the step down in exactly the job it exists to rescue.

Module scope only. A name imported inside a function is resolved when that
function runs, and neither program has one.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Final

import pytest
from conftest import read_text

from ._harness import PRUNE_PUSH_MODULE, TAKE_STATE_MODULE

pytestmark = pytest.mark.workflow

#: Every program held to this, named one by one. A third program a broken job
#: reaches for is declared here or it is held to nothing, and the two below are
#: the two whose calling step can run after the install has already failed.
STANDALONE_PROGRAMS: Final = (TAKE_STATE_MODULE, PRUNE_PUSH_MODULE)


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
