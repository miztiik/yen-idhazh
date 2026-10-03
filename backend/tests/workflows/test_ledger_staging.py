"""Is every ledger the pipeline commits wired into the run that writes it?

Two halves of one question. A ledger the writing job never stages is deleted with
the runner, and a keyed ledger nothing settles keeps every row a retried job wrote
twice. Both failures are silent: the pipeline logs a row it wrote, the step that
would have carried it says nothing, and the next reader sees a shorter file than
the run produced.

`state/host-fingerprint` was the first half. It was written from the day the probe
shipped and staged by nothing, so every row went to the bin with the runner.

Nothing here names a ledger. Both sides are derived - the ledger side from the
registry every ledger is declared in, the job side from the CLI's own dispatch and
the workflow's own `run:` bodies - because a hand-written list of ledger names is
the thing that went missing in the first place. Every ledger under `state/` is in
the registry. The trace tree's module stays in the derivation for its sink: a sink
is opened on a path helper, and the `*_relpath` helper beside it is how the sink
half names the ledger it fills.

A ledger is filled three ways and all three count here. A ledger takes an
`append_*` or a `write_*` call; the trace tree takes a file sink opened on its own
path helper, and a sink is still something a run writes and a job must stage; and
a ledger under `state/raw/` takes a call to the ledger door, `ledger.persist`,
which names the ledger in its own `ledger=` argument. The three hand-written
lists this replaced were each scoped to one source file, so a second writer in a
second file bought a third list rather than failing anything.

The derivation itself lives in `_ledger_derivation.py` beside this file, because
the check that every job reaching the door installs its engine reads the same
answer.

A writer says which ledger it fills by naming it. Most name one `LedgerName` in
their own body. One is generic over the vocabulary and takes the name from its
caller, so its ledgers are read from the calls the package makes to it. One is
handed a path rather than a name, and has only its own name left to go on.

Nothing here opens a file under `state/`. Every path is computed from a fixed date,
so what these tests cost does not move when the archive grows (CLAUDE.md
Guardrail #12).
"""

from __future__ import annotations

import ast
import importlib
import inspect
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

import pytest

from idhazh import ledger
from idhazh.telemetry import sinks

from ._harness import (
    COMMIT_JOBS,
    COMMIT_STEPS,
    COMMIT_WORKFLOWS,
    SUBSTITUTED_DATE,
    _commit_call,
    _load_workflows,
)
from ._ledger_derivation import (
    PERSIST_CALL,
    SINK_CALL,
    SINK_CLASSES,
    WRITER_CALL,
    _compacted_ledgers,
    _job_verbs,
    _ledger_publics,
    _ledgers,
    _package_sources,
    _persisted_ledgers,
    _reachable_modules,
    _sink_ledgers,
    _verb_ledgers,
    _writer_ledgers,
    _writers_called_by,
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


# A ledger whose entry ships ahead of the thing that fills it, and what will fill
# it. Guardrail #3 puts the shape and the address in first, and the feed
# retirements were the precedent: registered for settlement one commit before the
# plan stage wrote a row into them, so that two stale checkouts could not leave
# one address retired twice from the very first row.
#
# Each of these waits on the council, whose tenant module is resolved from config
# at call time - so with no slug registered nothing runs it, and the module behind
# it writes its record straight to the address rather than through a ledger writer
# this derivation could follow.
#
# It is a list rather than a rule, so a NEW unfilled ledger fails this file instead
# of joining it unnoticed. An entry goes when its filler lands, and a name here
# that has since gained a writer fails too - a ledger nothing fills is a directory
# a commit step may be staging for nothing.
LEDGERS_NOTHING_FILLS_YET: Final[Mapping[str, str]] = MappingProxyType(
    {
        "state/content-similarity-judge/metrics": (
            "the council's shipping capability, which this derivation cannot see: it "
            "renders a tenant's row rather than calling a ledger writer"
        ),
        "state/content-similarity-judge/score-distribution.json": (
            "the same capability, through idhazh.similarity.tenant and "
            "idhazh.stages.count_verdicts: both write the record straight to its "
            "address rather than calling a ledger writer"
        ),
        "state/content-similarity-judge/archive": (
            "the fold, on the day a stamp under the record moves"
        ),
    }
)

# A ledger no run ever fills, and who does. These are the operator's files: a
# person runs the verb, reads what it wrote, and commits it from their own
# checkout. No job stages them because no job writes them, which is a different
# answer from the list above rather than a softer one - waiting for a filler is
# temporary, and this is the design.
#
# It is a list rather than a rule for the same reason: a ledger that stops having a
# writing job fails this file instead of joining it unnoticed.
LEDGERS_NO_RUN_FILLS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "state/content-similarity-judge/holdout-pairs.csv": (
            "a person, typing the marks, or the labelling loop in "
            "backend/utilities/sample_sheet.py harvesting them back"
        ),
        "state/content-similarity-judge/merge-line-holdout-scores": (
            "a person, running `python -m idhazh score-merge-line-holdout`. The marked "
            "file changes when somebody labels more pairs rather than when a day "
            "publishes, so nothing in the daily pipeline calls it and no job stages it"
        ),
    }
)

# A ledger whose files the module that owns it writes straight to the registry's
# address, with no `append_*` or `write_*` in the ledger package and no sink for
# this derivation to follow. The registry says where each one lives; the module
# named here is who writes it, and its owner stages what it writes - the job that
# runs the module stages `state` whole, or the owner stages each file itself -
# which is the only reason nothing here checks it more closely.
#
# It is a list rather than a rule for the reason the two above are: another such
# ledger fails this file instead of joining it unnoticed, and an entry that gains a
# writer this derivation can follow fails too.
LEDGERS_AN_OWNER_WRITES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "state/day-metrics": (
            "idhazh.telemetry.publish.day_metrics, one JSON record per published day, "
            "written by `python -m idhazh assemble`"
        ),
        "state/digest-fragments": (
            "idhazh.stages.assemble through idhazh.assemble.fragment_path, one JSON "
            "block per run of a date, written by `python -m idhazh assemble`"
        ),
    }
)

# The three lists excuse a ledger from needing a writer this derivation can follow,
# so every assertion that subtracts one subtracts all three.
LEDGERS_NO_JOB_WRITES: Final = (
    frozenset(LEDGERS_NOTHING_FILLS_YET)
    | frozenset(LEDGERS_NO_RUN_FILLS)
    | frozenset(LEDGERS_AN_OWNER_WRITES)
)

# A module a verb used to reach and now reaches only through a tenant the council
# hosts. The resolver imports a tenant by name at call time, so a module behind one
# is in no verb's import closure however many slugs the config registers - and the
# job that runs the verb stages what the tenant named rather than what this file
# could have charged it with.
#
# It is a list rather than a rule, so a module that goes unreachable for any OTHER
# reason fails this file instead of joining it unnoticed. An entry goes the day a
# verb reaches the module directly, and a name here that a verb DOES reach fails
# too.
MODULES_ONLY_A_TENANT_REACHES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "idhazh.stages.set_merge_line": (
            "the content-similarity judge's tenant module, resolved from config"
        ),
        "idhazh.stages.count_verdicts": (
            "the content-similarity judge's tenant module, resolved from config"
        ),
    }
)


def _declared_keys() -> dict[str, tuple[str, ...]]:
    """Ledger -> the key its writer's own code names, for every writer that names one.

    Read from the syntax tree rather than the text, so a key mentioned in a docstring
    is not mistaken for a key the writer settles rows on.
    """
    ledgers = _writer_ledgers()
    declared: dict[str, tuple[str, ...]] = {}
    for name, writer in _ledger_publics(prefixes=("append_", "write_")).items():
        tree = ast.parse(inspect.getsource(writer).lstrip())
        used = sorted(
            {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name) and node.id.endswith("_KEY")
            }
        )
        assert len(used) <= 1, f"{writer.__module__}.{name} names {used}; one writer, one key"
        if not used:
            continue
        key = getattr(inspect.getmodule(writer), used[0], None)
        assert isinstance(key, tuple), (
            f"{writer.__module__}.{used[0]} must be a tuple of columns"
        )
        for ledger_path in sorted(ledgers[name]):
            declared[ledger_path] = key
    return declared


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


def _covers(staged: str, ledger: str) -> bool:
    """Would `git add <staged>` carry this ledger?"""
    return ledger == staged or ledger.startswith(f"{staged}/")


def test_every_store_is_filled_by_a_writer_this_test_can_follow() -> None:
    """The derivation must not answer an empty question.

    Every assertion below reads a list the staging check also reads. A ledger nothing
    writes, a sink class nothing matches, or a writer nothing calls would each shrink
    one of them in silence and leave a green test saying nothing at all about the
    ledger that went missing.
    """
    ledgers = _ledgers()
    written = {ledger_path for filled in _writer_ledgers().values() for ledger_path in filled}
    written |= set(_sink_ledgers().values())
    written |= set(_compacted_ledgers())
    written |= {ledger_path for filled in _persisted_ledgers().values() for ledger_path in filled}

    assert ledgers, "no ledger is declared anywhere, so nothing here is checked"
    assert SINK_CLASSES, (
        f"{sinks.__name__} declares no sink class that takes a path, so the sink half of "
        "the derivation matches nothing and a ledger written by one is checked by nobody."
    )
    unknown = sorted(LEDGERS_NO_JOB_WRITES - set(ledgers.values()))
    assert not unknown, (
        f"{', '.join(unknown)} is excused from needing a writer and nothing declares it, "
        "so the excuse covers nothing. Delete the entry from LEDGERS_NOTHING_FILLS_YET, "
        "LEDGERS_NO_RUN_FILLS or LEDGERS_AN_OWNER_WRITES."
    )
    landed = sorted(LEDGERS_NO_JOB_WRITES & written)
    assert not landed, (
        f"{', '.join(landed)} now has a public writer and is still excused from having "
        "one. Delete the entry from LEDGERS_NOTHING_FILLS_YET, LEDGERS_NO_RUN_FILLS or "
        "LEDGERS_AN_OWNER_WRITES, so the ledger is held to the staging and settlement "
        "checks below from its first row."
    )
    unwritten = sorted(set(ledgers.values()) - written - LEDGERS_NO_JOB_WRITES)
    assert not unwritten, (
        f"{', '.join(unwritten)} is declared and nothing public fills it. Either the "
        "writer is private - make it public, so the staging test can see it - or the "
        "ledger is dead and a commit step is staging a directory nothing fills. A ledger "
        "that is deliberately ahead of its writer (Guardrail #3) goes in "
        "LEDGERS_NOTHING_FILLS_YET, named with what will fill it; a ledger only a person "
        "ever fills goes in LEDGERS_NO_RUN_FILLS, named with who fills it; a ledger its "
        "owning module writes straight to its address goes in LEDGERS_AN_OWNER_WRITES, "
        "named with that module."
    )

    called = {
        writer
        for reachable in _reachable_modules().values()
        for module in reachable
        for writer in _writers_called_by(module)
    }
    called |= {
        writer
        for name in MODULES_ONLY_A_TENANT_REACHES
        for writer in _writers_called_by(importlib.import_module(name))
    }
    uncalled = sorted(set(_writer_ledgers()) - called)
    assert not uncalled, (
        f"{', '.join(uncalled)} is exported as a writer and no module a `python -m idhazh "
        "<verb>` reaches calls it, so its ledger is charged to no job and the staging check "
        "below says nothing about it. Call it from the stage that fills the ledger, or "
        "delete it and the path helper beside it."
    )


def test_every_module_that_writes_a_store_is_reached_by_a_cli_verb() -> None:
    """A writer no verb reaches is a ledger no job can be asked to stage.

    This is the hole the staging assertion would otherwise fall through. A stage that
    writes rows from a module the CLI never enters is charged to no job, so the
    parity check stays green while the rows go nowhere.

    A module a tenant reaches is excused by name, because a tenant is resolved from
    config rather than dispatched from the router - and with no tenant registered
    nothing runs it at all. The excuse clears itself: a module named there that a
    verb does reach fails below.
    """
    reached = {
        module.__name__
        for reachable in _reachable_modules().values()
        for module in reachable
    }
    writing = {
        name
        for name, source in _package_sources().items()
        if WRITER_CALL.search(source) or SINK_CALL.search(source) or PERSIST_CALL.search(source)
    }

    unknown = sorted(set(MODULES_ONLY_A_TENANT_REACHES) - writing)
    assert not unknown, (
        f"{', '.join(unknown)} is excused from needing a verb and writes no ledger, so "
        "the excuse covers nothing. Delete the entry from MODULES_ONLY_A_TENANT_REACHES."
    )
    landed = sorted(set(MODULES_ONLY_A_TENANT_REACHES) & reached)
    assert not landed, (
        f"{', '.join(landed)} is reached by a verb now and is still excused from being. "
        "Delete the entry from MODULES_ONLY_A_TENANT_REACHES, so the job that runs the "
        "verb is held to staging what it writes."
    )

    stranded = sorted(
        writing - reached - {ledger.__name__} - set(MODULES_ONLY_A_TENANT_REACHES)
    )
    assert not stranded, (
        f"{', '.join(stranded)} writes a ledger and no `python -m idhazh <verb>` reaches "
        "it, so no job can be held to staging what it writes. Dispatch it from a verb in "
        "backend/idhazh/cli.py, or call it from a module a verb already enters."
    )


def test_every_store_is_staged_by_the_job_whose_stage_writes_it() -> None:
    """A ledger no job stages is written on a runner and deleted with it.

    The writing side is in Python and the staging side is in YAML. A writer
    that no stage commits must fail this check before a runner discards its output.

    A job is credited only for its own commit steps. The assemble job stages `state`
    whole and that is worth nothing to a work shard - the shard runs on its own
    runner with its own checkout, and the file it wrote is not in the tree assemble
    committed. That is also why every committing workflow is asked, not only the
    daily one: a second workflow's runner is no closer to the daily run's tree.
    """
    workflows = _load_workflows()
    verb_ledgers = _verb_ledgers()
    commit_calls = _job_commit_calls()

    missing: list[str] = []
    credited: set[tuple[str, str]] = set()
    for (workflow_name, job_name), labels in sorted(commit_calls.items()):
        staged = {path for paths in labels.values() for path in paths}
        for verb in sorted(_job_verbs(workflows[workflow_name], job_name)):
            for ledger_path, because in sorted(verb_ledgers.get(verb, {}).items()):
                credited.add((workflow_name, job_name))
                if any(_covers(path, ledger_path) for path in staged):
                    continue
                steps = ", ".join(f'"{COMMIT_STEPS[label]}"' for label in sorted(labels))
                missing.append(
                    f"{ledger_path} is written by the {job_name} job ({because}) and no commit "
                    f"step in that job stages it. Add {ledger_path} to the paths of the {steps} "
                    f"step in .github/workflows/{workflow_name}. Another job staging a "
                    "parent of it is not enough: that job runs on its own runner and "
                    "cannot see a file this one wrote."
                )

    assert not missing, "\n".join(missing)
    assert credited == set(commit_calls), (
        f"the {sorted(set(commit_calls) - credited)} job commits and this test charged "
        "it with no ledger at all, so nothing above was checked for it."
    )


def _rewritten_ledgers() -> set[str]:
    """The ledgers a writer replaces whole, rather than appends a row to.

    `append_*` adds to the file and `write_*` replaces it - the convention the module
    already spells in its own names, and the one `_ledger_publics` already splits on.
    A writer that replaces settles nothing as it writes, so it names no key. The
    post-merge key is still right for it: two runs' folds can both land in the
    merged copy and the settler is the only thing that can take
    one of them back out again.

    A day tree the closed-day fold rewrites is the same case one step further out.
    The fold settles its rows by key as it folds them (`day_shards.settle`, run by
    the gardener's `closed_day_fold`) rather than as they are written, and it has no
    `append_*`/`write_*` name at all - so it is added here from `DAY_TREES`.
    `state/host-fingerprint` is the case.
    """
    ledgers = _writer_ledgers()
    replaced = {
        ledger_path
        for name, filled in ledgers.items()
        if name.startswith("write_")
        for ledger_path in filled
    }
    replaced |= set(_compacted_ledgers())
    appended = {
        ledger_path
        for name, filled in ledgers.items()
        if name.startswith("append_")
        for ledger_path in filled
    }
    return replaced - appended


def test_every_ledger_that_declares_a_key_is_registered_for_settlement() -> None:
    """A keyed ledger outside the registry keeps every row a retried job wrote twice.

    The two sides are compared as sets rather than as a subset, so a ledger that
    declares no key must also be absent from the registry - which is what
    `keyed_paths` says about the one ledger it deliberately leaves out.

    A ledger whose writer replaces the file is the exception, and it is derived rather
    than named: see `_rewritten_ledgers`.

    A ledger registered before its writer exists is the second exception, and that one
    is named rather than derived: `LEDGERS_NOTHING_FILLS_YET` and `LEDGERS_NO_RUN_FILLS`.
    Registering the key with the shape rather than with its first writer is what makes
    the settlement true from the first row instead of from the second, which is the
    position `state/feed-retirements.csv` was in on 2026-09-02.

    `keyed_paths` is asked for one named date, so it returns that day's cover instead
    of globbing the tree, and this test reads no committed file.
    """
    declared = _declared_keys()
    ledgers = set(_ledgers().values())

    registered: dict[str, tuple[str, ...]] = {}
    for entry in ledger.keyed_paths(Path("state"), date=SUBSTITUTED_DATE):
        path = entry.path.as_posix()
        ledger_path = next((name for name in ledgers if _covers(name, path)), None)
        assert ledger_path is not None, (
            f"{path} is registered for settlement and matches no ledger the registry "
            "declares, so nothing can say which writer fills it."
        )
        registered[ledger_path] = entry.key

    unregistered = sorted(set(declared) - set(registered))
    assert not unregistered, (
        f"{', '.join(unregistered)} declares a key in idhazh.ledger and keyed_paths() "
        "does not yield it, so a retried job's repeat of a row is kept instead of "
        "dropped. Add it to keyed_paths() in backend/idhazh/ledger/settle.py."
    )

    keyless = sorted(set(registered) - set(declared) - _rewritten_ledgers() - LEDGERS_NO_JOB_WRITES)
    assert not keyless, (
        f"{', '.join(keyless)} is registered for settlement, its writer appends rows, and "
        "that writer names no key - so the settler has a key the writer does not use. Name "
        "the key in the writer in backend/idhazh/ledger/rows.py, or take the ledger out of "
        "keyed_paths()."
    )

    for ledger_path, key in sorted(declared.items()):
        assert registered[ledger_path] == key, (
            f"{ledger_path} is written on {key} and settled on {registered[ledger_path]}. The two must "
            "be one tuple, or a repeat the writer would have dropped survives the merge."
        )
