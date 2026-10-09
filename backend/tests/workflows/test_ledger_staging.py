"""Is every ledger the pipeline commits wired into the run that writes it?

A ledger the writing job never stages is deleted with the runner. The failure is
silent: the pipeline logs a row it wrote, the step that would have carried it says
nothing, and the next reader sees fewer rows than the run produced. A retried
job's second write needs no settlement here: the ledger door keeps the higher
attempt of each work unit when a reader asks.

`state/host-fingerprint` was the first ledger this caught. It was written from the
day the probe shipped and staged by nothing, so every row went to the bin with the
runner.

The check used to be derived from the package's own source with `ast` and
`inspect`: every `*.py` under `idhazh` was read and parsed on every call, because a
hand-written list of ledger names is the thing that went missing in the first
place. That walk cost more every time the package grew, and OWNER RULING
2026-10-03 ("no read may grow with the repository") forbids a sweep over
`backend/idhazh` in production and in tests alike. `idhazh.ledger.staging.REGISTRY`
now carries the same fact by hand instead: a writer and the commit labels whose
job must stage it, declared in the same change that gives a ledger its first row
(CLAUDE.md Guardrail #3). These tests compare that registry with the workflow
files `_harness.py` already reads, which is a fixed cost - one dict and 24
ledgers, never a walk of the tree the registry describes.

The CLI-reachability half of the old derivation - whether a writer is dispatched
from `python -m idhazh <verb>` at all - has no replacement here. A writer no verb
reaches is now caught only by code review and by the per-module unit tests under
`backend/tests/idhazh/`, the same as any other dead code.

Nothing here opens a file under `state/`. Every path is computed from a fixed date,
so what these tests cost does not move when the archive grows (CLAUDE.md
Guardrail #12).
"""

from __future__ import annotations

from typing import Final

import pytest

from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.staging import REGISTRY, staged_path

from ._harness import (
    COMMIT_JOBS,
    COMMIT_STEPS,
    COMMIT_WORKFLOWS,
    _commit_call,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

# Every workflow that commits, except the trial one. `measure.yml` writes under
# the trial state root, throws away most of what it writes, and holds its own
# staged list closed-world in test_bench_targets.py - so a ledger it does not
# stage is a decision rather than a loss. Every other commit label the harness
# declares is in scope, so a sixth commit step joins without an edit here, and a
# second workflow that writes a ledger is held to the same parity as the daily
# run.
TRIAL_WORKFLOW: Final = "measure.yml"

def _job_commit_calls() -> dict[tuple[str, str], dict[str, list[str]]]:
    """(Workflow, job) -> commit label -> the paths that label stages.

    Keyed by the pair rather than by the job name, because two workflows may each
    carry a job of one name and their runners share nothing.
    """
    calls: dict[tuple[str, str], dict[str, list[str]]] = {}
    for label, workflow in COMMIT_WORKFLOWS.items():
        if workflow == TRIAL_WORKFLOW:
            continue
        calls.setdefault((workflow, COMMIT_JOBS[label]), {})[label] = _commit_call(label)[0]
    return calls


def _covers(staged: str, path: str) -> bool:
    """Would `git add <staged>` carry this path?"""
    return path == staged or path.startswith(f"{staged}/")


def test_every_store_is_filled_by_a_writer_this_test_can_follow() -> None:
    """Every `LedgerName` is in the registry, and every named writer resolves.

    A ledger absent from `idhazh.ledger.staging.REGISTRY` is a ledger neither test
    in this file says anything about. A `symbol` that does not resolve is a writer
    renamed or deleted out from under the table that still claims it fills the
    ledger.
    """
    missing = sorted(set(LedgerName) - set(REGISTRY), key=lambda name: name.value)
    assert not missing, (
        f"{', '.join(name.value for name in missing)} has no row in "
        "idhazh.ledger.staging.REGISTRY, so neither test in this file checks it. Add it, "
        "naming its writer and the commit labels whose job stages it."
    )

    unresolved: list[str] = []
    for name, staging in sorted(REGISTRY.items(), key=lambda kv: kv[0].value):
        if staging.symbol is None:
            continue
        module_name, _, attr = staging.symbol.rpartition(".")
        try:
            module = __import__(module_name, fromlist=[attr])
        except ImportError as error:
            unresolved.append(f"{name.value}: {staging.symbol} does not import ({error})")
            continue
        if not hasattr(module, attr):
            unresolved.append(
                f"{name.value}: {staging.symbol} names no attribute {attr!r} on {module_name}"
            )
    assert not unresolved, (
        "\n".join(unresolved) + "\n\nUpdate the `symbol` in idhazh.ledger.staging.REGISTRY, "
        "or set it to None and say in `writer` why there is nothing to follow."
    )


def test_every_store_is_staged_by_the_job_whose_stage_writes_it() -> None:
    """A ledger no job stages is written on a runner and deleted with it.

    The writing side is `idhazh.ledger.staging.REGISTRY` and the staging side is
    the workflow YAML `_harness.py` reads. A job is credited only for its own
    commit steps. The assemble job stages `state` whole and that is worth
    nothing to a work shard - the shard runs on its own runner with its own
    checkout, and the file it wrote is not in the tree assemble committed. That
    is also why every committing workflow is asked, not only the daily one: a
    second workflow's runner is no closer to the daily run's tree.
    """
    commit_calls = _job_commit_calls()

    missing: list[str] = []
    credited: set[tuple[str, str]] = set()
    for (workflow_name, job_name), labels in sorted(commit_calls.items()):
        staged = {path for paths in labels.values() for path in paths}
        for label in labels:
            for name, staging in sorted(REGISTRY.items(), key=lambda kv: kv[0].value):
                if label not in staging.job_labels:
                    continue
                credited.add((workflow_name, job_name))
                ledger_path = staged_path(name)
                if any(_covers(path, ledger_path) for path in staged):
                    continue
                steps = ", ".join(f'"{COMMIT_STEPS[each]}"' for each in sorted(labels))
                missing.append(
                    f"{ledger_path} is written by the {job_name} job ({staging.writer}) and "
                    f"no commit step in that job stages it. Add {ledger_path} to the paths "
                    f"of the {steps} step in .github/workflows/{workflow_name}. Another job "
                    "staging a parent of it is not enough: that job runs on its own runner "
                    "and cannot see a file this one wrote."
                )

    assert not missing, "\n".join(missing)
    assert credited == set(commit_calls), (
        f"the {sorted(set(commit_calls) - credited)} job commits and this test charged "
        "it with no ledger at all, so nothing above was checked for it."
    )
