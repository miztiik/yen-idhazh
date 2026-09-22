"""Does every `inputs.<name>` a workflow expression reads name an input that workflow declares?"""

from __future__ import annotations

import re
from typing import Final

import pytest

from ._harness import _declared_dispatch_inputs, _load_workflows, _strings

pytestmark = pytest.mark.workflow

#: `${{ inputs.x }}`, `${{ fromJSON(inputs.x) }}` and the older
#: `${{ github.event.inputs.x }}` all resolve against the same declared form, so
#: one pattern covers the three spellings.
INPUT_REFERENCE: Final = re.compile(r"(?:github\.event\.)?inputs\.([a-z0-9_]+)")

#: The `on:` block is where the form is declared, not where it is read, and a
#: `workflow_run` trigger names other workflows. Reading it back here would let
#: a declaration satisfy itself.
DECLARATION_KEY: Final = "on"


def _referenced_inputs(workflow: dict[str, object]) -> set[str]:
    body = {key: value for key, value in workflow.items() if key != DECLARATION_KEY}
    return {
        name for text in _strings(body) for name in INPUT_REFERENCE.findall(text)
    }


def test_every_input_an_expression_reads_is_declared_by_that_workflow() -> None:
    """An undeclared `inputs.x` is empty at expression time, and that is the quiet failure.

    `${{ inputs.x }}` on a workflow that no longer declares `x` does not error -
    it resolves to the empty string, so a step runs with a blank environment
    variable or a flag with nothing after it. `fromJSON(inputs.x)` is the loud
    half: it fails while the expression is evaluated, before a step starts, so
    every dispatch of that workflow dies with no log to read.

    Discovery is closed-world over the parsed file rather than a list here, so a
    reference added tomorrow is covered the day it lands.
    """
    for filename, workflow in sorted(_load_workflows().items()):
        declared = set(_declared_dispatch_inputs(workflow))
        undeclared = sorted(_referenced_inputs(workflow) - declared)
        assert not undeclared, (
            f"{filename} reads {undeclared} but declares no such dispatch input, so the "
            "expression resolves to nothing"
        )
