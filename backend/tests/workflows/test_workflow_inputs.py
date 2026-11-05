"""Does every `inputs.<name>` a workflow expression reads name an input that workflow declares?"""

from __future__ import annotations

from typing import Final

import pytest

from ._harness import (
    _declared_dispatch_inputs,
    _expression,
    _expression_references,
    _load_workflows,
    _mapping,
    _strings,
)

pytestmark = pytest.mark.workflow

#: The `on:` block is where the form is declared, not where it is read, and a
#: `workflow_run` trigger names other workflows. Reading it back here would let
#: a declaration satisfy itself.
DECLARATION_KEY: Final = "on"


def _referenced_inputs(workflow: dict[str, object]) -> set[str]:
    body = {key: value for key, value in workflow.items() if key != DECLARATION_KEY}
    expressions = list(_strings(body))
    for value in _mapping(body.get("jobs", {}), "workflow jobs").values():
        job = _mapping(value, "workflow job")
        steps = job.get("steps", [])
        assert isinstance(steps, list), "job steps must contain a YAML sequence"
        declarations = [job] + [_mapping(step, "workflow step") for step in steps]
        for declaration in declarations:
            condition = declaration.get("if")
            if isinstance(condition, str) and "${{" not in condition:
                expressions.append(_expression(condition))
    names: set[str] = set()
    for text in expressions:
        for reference in _expression_references(text, ("inputs", "github")):
            if len(reference) > 1 and reference[0] == "inputs":
                names.add(reference[1])
            elif len(reference) > 3 and reference[:3] == ("github", "event", "inputs"):
                names.add(reference[3])
    return names


def test_input_check_helpers_distinguish_references_from_declarations() -> None:
    workflow: dict[str, object] = {
        "on": {
            "workflow_dispatch": {
                "inputs": {
                    "declared": {
                        "description": "${{ inputs.declaration_only }}",
                    }
                }
            }
        },
        "jobs": {
            "check": {
                "steps": [{"run": "echo ${{ inputs.declared }} ${{ inputs.missing }}"}]
            }
        },
    }

    declared = set(_declared_dispatch_inputs(workflow))
    referenced = _referenced_inputs(workflow)

    assert declared == {"declared"}
    assert referenced == {"declared", "missing"}
    assert referenced - declared == {"missing"}


def test_input_references_exclude_filenames_and_quoted_expression_literals() -> None:
    workflow: dict[str, object] = {
        "jobs": {
            "check": {
                "steps": [{
                    "run": (
                        "cat tests/fixtures/host-probes/process-inputs.json inputs.json\n"
                        "echo ${{ format('inputs.literal', inputs['selected-name']) }} "
                        "${{ fromJSON(github.event.inputs.legacy) }}"
                    ),
                }],
            },
        },
    }
    assert _referenced_inputs(workflow) == {"selected-name", "legacy"}


@pytest.mark.parametrize("conditional_scope", ["job", "step"])
def test_input_references_include_implicit_conditional_expressions(conditional_scope: str) -> None:
    condition = "inputs.enabled == true && github.event.inputs.mode != 'inputs.literal'"
    step: dict[str, object] = {"run": "echo inputs.not_a_reference"}
    job: dict[str, object] = {"steps": [step]}
    (job if conditional_scope == "job" else step)["if"] = condition
    assert _referenced_inputs({"jobs": {"check": job}}) == {"enabled", "mode"}


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
