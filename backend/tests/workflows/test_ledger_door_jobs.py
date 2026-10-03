"""Does every step that writes through the ledger door name the commit its run checked out?

Every file the door writes names that commit, so a step that runs a writing verb
without `--commit` records forty zeros and fails nothing at all.

The verbs below are declared by hand (Guardrail #3), mirroring
`idhazh.ledger.staging.REGISTRY`'s per-ledger writers, rather than walked from
the package's own code - a walk that cost more as the package grew (OWNER
RULING 2026-10-03, "no read may grow with the repository"). A verb joins
`DOOR_WRITING_VERBS` in the same commit that gives one of its reachable
modules a `ledger.persist`/`append_*`/`write_*` call; the steps still come
from the workflows' own `run:` bodies, so a step that starts running a
writing verb is held to this from its first commit.
"""

from __future__ import annotations

from typing import Final

import pytest

from ._harness import _load_workflows, _stage_invocations

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

#: The flag a writing verb takes the commit on.
COMMIT_FLAG: Final = "--commit"

#: Every CLI verb that files a row through the ledger door on some run, and what
#: it writes. Declared by hand rather than derived: see `idhazh.ledger.staging`
#: for the fuller per-ledger table this summarizes at the verb level.
DOOR_WRITING_VERBS: Final[dict[str, str]] = {
    "plan": (
        "idhazh.stages.plan (seen, feed-health, counterfactual-scores, "
        "feed-retirements) and idhazh.telemetry.silicon (host-fingerprint)"
    ),
    "record": (
        "idhazh.stages.record (item-health) and idhazh.evals.writer "
        "(summary-quality-evals, summary-quality-evals-index)"
    ),
    "assemble": (
        "idhazh.stages.assemble (item-health, published, digest-fragments), "
        "idhazh.evals.writer (summary-quality-evals, summary-quality-evals-index), "
        "idhazh.telemetry.source_health (feed-retirements) and "
        "idhazh.telemetry.publish.day_metrics (day-metrics)"
    ),
    "decide": "idhazh.stages.decide (candidate-models)",
    "qualify-decide": "idhazh.stages.qualify_decide (candidate-models)",
    "fingerprint": "idhazh.telemetry.silicon (host-fingerprint)",
    "job-clock": "idhazh.telemetry.silicon (host-fingerprint)",
}


def test_every_step_that_writes_through_the_door_names_its_commit() -> None:
    """A writing verb is run with `--commit`, or its files name forty zeros as their code."""
    assert DOOR_WRITING_VERBS, "no verb writes through the ledger door, so nothing here is checked"
    unnamed: list[str] = []
    checked = 0
    for workflow_name, workflow in sorted(_load_workflows().items()):
        for job_name, step_name, stage, words in _stage_invocations(workflow, workflow_name):
            if stage not in DOOR_WRITING_VERBS:
                continue
            checked += 1
            if COMMIT_FLAG in words:
                continue
            unnamed.append(
                f"{workflow_name} job {job_name}, step {step_name!r}, runs `idhazh {stage}`, "
                f"which files rows through the door from {DOOR_WRITING_VERBS[stage]}, "
                f"and passes no {COMMIT_FLAG}. Pass {COMMIT_FLAG} with the commit the run "
                "checked out."
            )
    assert not unnamed, "\n".join(unnamed)
    assert checked, "no workflow step runs a verb that writes through the door"
