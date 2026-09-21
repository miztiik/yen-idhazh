"""Is every store the pipeline commits wired into the run that writes it?

Two halves of one question. A store the writing job never stages is deleted with
the runner, and a keyed ledger nothing settles keeps every row a retried job wrote
twice. Both failures are silent: the pipeline logs a row it wrote, the step that
would have carried it says nothing, and the next reader sees a shorter file than
the run produced.

`state/host-fingerprint` was the first half. It was written from the day the probe
shipped and staged by nothing, so every row went to the bin with the runner.
`state/span-rollup` was both halves at once: nine days written and discarded, then
staged but missing from the settlement registry.

Nothing here names a store. Both sides are derived - the store side from the
`*_relpath` helpers the store modules already export, the job side from the CLI's
own dispatch and the workflow's own `run:` bodies - because a hand-written list of
ledger names is the thing that went missing in the first place.

A store is filled two ways and both count here. A ledger takes an `append_*` or a
`write_*` call; the trace tree takes a file sink opened on its own path helper, and
a sink is still something a run writes and a job must stage. The three hand-written
lists this replaced were each scoped to one source file, so a second writer in a
second file bought a third list rather than failing anything.

Nothing here opens a file under `state/`. Every path is computed from a fixed date,
so what these tests cost does not move when the archive grows (CLAUDE.md
Guardrail #12).
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any, Final

import pytest

from idhazh import cli, ledger
from idhazh.contracts.base import ServerJob
from idhazh.stages import compact as compact_stage
from idhazh.telemetry import sinks, traces

from ._harness import (
    COMMIT_JOBS,
    COMMIT_STEPS,
    COMMIT_WORKFLOWS,
    SUBSTITUTED_DATE,
    _commit_call,
    _load_workflows,
    _steps,
    _strings,
)

pytestmark = pytest.mark.workflow

# Every workflow that commits, except the trial one. `measure.yml` writes under
# the trial state root, throws away most of what it writes, and holds its own
# staged list closed-world in test_bench_targets.py - so a ledger it does not
# stage is a decision rather than a loss. Every other commit label the harness
# declares is in scope, so a sixth commit step joins without an edit here, and a
# second workflow that writes a store is held to the same parity as the daily
# run.
TRIAL_WORKFLOW: Final = "measure.yml"

# A second date, in another year, so the longest prefix two paths from one helper
# share is the directory a commit step would stage rather than that directory plus
# a year or a month.
OTHER_DATE: Final = "2027-01-02"

# Every module that declares a committed store, each by exporting a `*_relpath`
# helper for one. `idhazh.ledger` holds the CSV ledgers; `idhazh.telemetry.traces`
# holds the trace tree beside them, which a sink writes rather than a writer
# function - which is why every guard that looked for a writer missed it.
STORE_MODULES: Final = (ledger, traces)

# A store whose path helper ships ahead of the thing that fills it, and what will
# fill it. Guardrail #3 puts the shape and the path in first, and
# `state/feed-retirements.csv` is the precedent: it was registered for settlement
# one commit before the plan stage wrote a row into it, so that two stale
# checkouts could not leave one address retired twice from the very first row.
#
# It is a list rather than a rule, so a NEW unfilled store fails this file instead
# of joining it unnoticed. An entry goes when its filler lands, and a name here
# that has since gained a writer fails too - a store nothing fills is a directory
# a commit step may be staging for nothing.
STORES_NOTHING_FILLS_YET: Final[Mapping[str, str]] = MappingProxyType(
    {
        "state/content-similarity-judge/merge-line-holdout-scores": (
            "the step that scores the applied merge line against the hand-marked holdout"
        ),
        "state/content-similarity-judge/metrics": (
            "the council's shipping capability, which this derivation cannot see: it "
            "renders a tenant's row rather than calling a ledger writer"
        ),
        "state/content-similarity-judge/archive": (
            "the fold, on the day a stamp under the record moves"
        ),
        "state/content-similarity-judge/holdout-pairs.csv": (
            "a person, and no run ever - the file is typed by hand"
        ),
    }
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

# The package the pipeline lives in, and the name its modules import the ledger as.
PACKAGE: Final = ledger.__name__.split(".")[0]
LEDGER_ALIAS: Final = ledger.__name__.rsplit(".", 1)[-1]
WRITER_CALL: Final = re.compile(rf"\b{LEDGER_ALIAS}\.((?:append|write)_[a-z_]+)\(")

# A sink that takes a path is a thing that writes a file, so the sink classes are
# read out of the module that declares them rather than named here: a second one
# joins this derivation on the day it is written.
SINK_CLASSES: Final = tuple(
    sorted(
        name
        for name, value in vars(sinks).items()
        if isinstance(value, type)
        and not name.startswith("_")
        and "path" in getattr(value, "__annotations__", {})
    )
)
SINK_CALL: Final = re.compile(
    rf"\b(?:{'|'.join(SINK_CLASSES)})\(\s*[A-Za-z_][\w.]*\.([a-z_]+_path)\("
)


def _store_publics(
    *, suffix: str = "", prefixes: tuple[str, ...] = ()
) -> dict[str, Callable[..., Any]]:
    """The public callables the store modules export under a suffix or a prefix."""
    found: dict[str, Callable[..., Any]] = {}
    for module in STORE_MODULES:
        for name, value in sorted(vars(module).items()):
            if name.startswith("_") or not callable(value):
                continue
            if suffix and not name.endswith(suffix):
                continue
            if prefixes and not name.startswith(prefixes):
                continue
            assert name not in found, (
                f"{module.__name__} and {found[name].__module__} both export {name}, and "
                "this test keys a store by the bare helper name. Rename one of them."
            )
            found[name] = value
    return found


def _helper_arguments(date: str) -> dict[str, object]:
    """What to pass a path helper, named by the parameter that asks for it.

    A store filed by something other than a date says so in its own signature - the
    trace tree files by run and by shard, a segment by run, attempt, job and shard,
    and an archived record files by the stamp its counts were taken under - so the
    value follows the parameter's name rather than the helper's.

    `ledger` picks one member of the declared set and any member would do: what the
    staging check asks is whether the job that writes a segment stages the store, and
    `state/segments` covers every ledger inside it.
    """
    return {
        "date": date,
        "month": date,
        "run_id": f"{date}-1",
        "shard": 0,
        "stamp": date,
        "ledger": ledger.SegmentLedger.HOST_FINGERPRINT,
        "attempt": 1,
        "job": ServerJob.WORK,
    }


def _relpath_for(name: str, helper: Callable[..., Any], date: str) -> str:
    """One store path for one date, from the helper the module already exports."""
    supplied = _helper_arguments(date)
    required = [
        parameter.name
        for parameter in inspect.signature(helper).parameters.values()
        if parameter.default is inspect.Parameter.empty
    ]
    unnamed = sorted(set(required) - set(supplied))
    assert not unnamed, (
        f"{helper.__module__}.{name} asks for {unnamed}, which this test has no value "
        "for. Name the parameter in _helper_arguments, so every *_relpath helper can "
        "still be called from one date."
    )
    produced = helper(**{parameter: supplied[parameter] for parameter in required})
    assert isinstance(produced, str), f"{helper.__module__}.{name} must return a path string"
    return produced


def _stores() -> dict[str, str]:
    """Every store the store modules declare: helper name -> the path a job stages.

    The staged path is the longest prefix two dates share, so a dated ledger reduces
    to its own directory and an undated one stays the file it is.
    """
    found: dict[str, str] = {}
    for name, helper in _store_publics(suffix="_relpath").items():
        first = _relpath_for(name, helper, SUBSTITUTED_DATE).split("/")
        second = _relpath_for(name, helper, OTHER_DATE).split("/")
        shared: list[str] = []
        for left, right in zip(first, second, strict=False):
            if left != right:
                break
            shared.append(left)
        assert shared, f"{helper.__module__}.{name} returns two paths with nothing in common"
        found[name] = "/".join(shared)
    return found


def _writer_stores() -> dict[str, str]:
    """Every public ledger writer, and the store it writes.

    Resolved from the path helper the writer's own body calls, so a writer named for
    one thing and writing another follows the code rather than the name.
    """
    stores = _stores()
    resolved: dict[str, str] = {}
    for name, writer in _store_publics(prefixes=("append_", "write_")).items():
        source = inspect.getsource(writer)
        stems = [
            call.removesuffix("_path").removesuffix("_relpath")
            for call in re.findall(r"\b([a-z_]+_(?:rel)?path)\(", source)
        ]
        stems.append(name.split("_", 1)[1])
        helper = next((f"{stem}_relpath" for stem in stems if f"{stem}_relpath" in stores), None)
        assert helper is not None, (
            f"{writer.__module__}.{name} writes a store this test cannot name: it calls "
            "no path helper it shares a name with. Add a `<store>_relpath()` helper "
            f"beside the others and call it from {name}."
        )
        resolved[name] = stores[helper]
    return resolved


def _package_sources() -> dict[str, str]:
    """Every module in the pipeline package: its dotted name -> its source text.

    The package's own files and nothing else, so what this reads grows with the code
    rather than with the archive (CLAUDE.md Guardrail #12).
    """
    package_dir = Path(inspect.getfile(ledger)).parent
    return {
        path.relative_to(package_dir.parent).with_suffix("").as_posix().replace("/", "."): (
            path.read_text(encoding="utf-8")
        )
        for path in sorted(package_dir.rglob("*.py"))
    }


def _sink_stores() -> dict[str, str]:
    """Every path helper a file sink is opened on, and the store it fills.

    Read out of the package's own source, because a sink has no `append_*` name to be
    found by: the call site is the only place that says which store it writes.
    """
    stores = _stores()
    opened = {
        helper for source in _package_sources().values() for helper in SINK_CALL.findall(source)
    }
    resolved: dict[str, str] = {}
    for helper in sorted(opened):
        stem = helper.removesuffix("_path")
        assert f"{stem}_relpath" in stores, (
            f"a file sink is opened on {helper}(), and no store module exports a "
            f"{stem}_relpath() helper for it. Add one beside the path helper, so this "
            "test can say which store the sink fills and which job has to stage it."
        )
        resolved[helper] = stores[f"{stem}_relpath"]
    return resolved


def _declared_keys() -> dict[str, tuple[str, ...]]:
    """Store -> the key its writer's own code names, for every writer that names one.

    Read from the syntax tree rather than the text, so a key mentioned in a docstring
    is not mistaken for a key the writer settles rows on.
    """
    stores = _writer_stores()
    declared: dict[str, tuple[str, ...]] = {}
    for name, writer in _store_publics(prefixes=("append_", "write_")).items():
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
        declared[stores[name]] = key
    return declared


def _branch_verbs(branch: ast.If) -> list[str]:
    """The `args.stage` values one branch of `cli.main` answers to."""
    if not isinstance(branch.test, ast.Compare):
        return []
    subject = branch.test.left
    if not (
        isinstance(subject, ast.Attribute)
        and subject.attr == "stage"
        and isinstance(subject.value, ast.Name)
        and subject.value.id == "args"
    ):
        return []
    verbs: list[str] = []
    for comparator in branch.test.comparators:
        elements = comparator.elts if isinstance(comparator, ast.Tuple) else [comparator]
        verbs += [
            element.value
            for element in elements
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        ]
    return verbs


def _dispatched_modules() -> dict[str, set[ModuleType]]:
    """CLI verb -> the stage modules its own branch of `cli.main` enters.

    A verb reaches a module when its branch calls a public function on it. A helper
    borrowed from another stage is not a dispatch: charging a job with another
    stage's ledgers because it borrowed one function would ask for staging nobody
    needs, and a test that asks for the wrong thing gets edited away. Every borrowed
    helper in the router is private, which is what the name is read for.

    **The marker cannot be a name prefix.** The digest pipeline calls its entry
    points `stage_*`; the council names its own after the work they do, because a
    verb named for its mechanism is what this plan's rename removed. A prefix test
    therefore saw the council enter no module at all and left its store charged to
    no job.
    """
    reached: dict[str, set[ModuleType]] = {}
    for branch in ast.walk(ast.parse(inspect.getsource(cli.main))):
        if not isinstance(branch, ast.If):
            continue
        verbs = _branch_verbs(branch)
        if not verbs:
            continue
        modules: set[ModuleType] = set()
        for call in ast.walk(ast.Module(body=branch.body, type_ignores=[])):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr.startswith("_"):
                continue
            if not isinstance(call.func.value, ast.Name):
                continue
            entered = getattr(cli, call.func.value.id, None)
            if isinstance(entered, ModuleType) and entered.__name__.startswith(f"{PACKAGE}."):
                modules.add(entered)
        for verb in verbs:
            reached.setdefault(verb, set()).update(modules)
    return reached


def _calls_into(module: ModuleType) -> set[ModuleType]:
    """The pipeline modules this one calls a function of."""
    source = inspect.getsource(module)
    return {
        value
        for alias, value in vars(module).items()
        if isinstance(value, ModuleType)
        and value.__name__.startswith(f"{PACKAGE}.")
        and re.search(rf"\b{re.escape(alias)}\.[a-z_]+\(", source)
    }


def _writers_called_by(module: ModuleType) -> set[str]:
    """The ledger writers this module's source names."""
    return set(WRITER_CALL.findall(inspect.getsource(module)))


def _sinks_opened_by(module: ModuleType) -> set[str]:
    """The store path helpers this module's source hands to a file sink."""
    return set(SINK_CALL.findall(inspect.getsource(module)))


def _reachable_modules() -> dict[str, set[ModuleType]]:
    """CLI verb -> the modules its own branch enters, and the ones those call.

    One hop past the dispatched stage, because a stage that hands the writing to a
    helper module still owes the run the rows: the fold writes its months through
    `retention`, and the probe writes its row through `telemetry.silicon`.
    """
    reachable: dict[str, set[ModuleType]] = {}
    for verb, dispatched in _dispatched_modules().items():
        entered: set[ModuleType] = set()
        for module in dispatched:
            entered.add(module)
            entered |= _calls_into(module)
        reachable[verb] = entered
    return reachable


def _verb_stores() -> dict[str, dict[str, str]]:
    """CLI verb -> store -> the sentence that says why that verb writes it.

    A ledger writer and a file sink are both writes, and a store filled either way
    is a store the job that runs the verb has to stage.
    """
    stores = _writer_stores()
    sunk = _sink_stores()
    compacted = _compacted_stores()
    charged: dict[str, dict[str, str]] = {}
    for verb, reachable in _reachable_modules().items():
        for module in sorted(reachable, key=lambda entered: entered.__name__):
            if module is compact_stage:
                for store, which in sorted(compacted.items()):
                    charged.setdefault(verb, {})[store] = (
                        f"`python -m idhazh {verb}` reaches {module.__name__}, "
                        f"which folds every waiting {which} segment into this head"
                    )
            for writer in sorted(_writers_called_by(module)):
                assert writer in stores, (
                    f"{module.__name__} calls ledger.{writer}, which idhazh.ledger does "
                    "not export. Rename the call, or export the writer so this test can "
                    "find the store it fills."
                )
                charged.setdefault(verb, {})[stores[writer]] = (
                    f"`python -m idhazh {verb}` reaches {module.__name__}, "
                    f"which calls ledger.{writer}"
                )
            for opener in sorted(_sinks_opened_by(module)):
                charged.setdefault(verb, {})[sunk[opener]] = (
                    f"`python -m idhazh {verb}` reaches {module.__name__}, "
                    f"which opens a file sink on {opener}()"
                )
    return charged


def _job_verbs(workflow: dict[str, object], job_name: str) -> set[str]:
    """The CLI verbs one job's steps run."""
    found: set[str] = set()
    for step in _steps(workflow, job_name):
        for text in _strings(step):
            found.update(re.findall(rf"\b{PACKAGE} (?!-)([a-z][a-z-]*)", text))
    return found


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


def _covers(staged: str, store: str) -> bool:
    """Would `git add <staged>` carry this store?"""
    return store == staged or store.startswith(f"{staged}/")


def _compacted_stores() -> dict[str, str]:
    """Every head the compaction fills, and the ledger whose segments drain into it.

    The compaction writes a head generically - one function, one declared head table,
    and no `append_*` name for `_writer_stores` to find - so it is read out of
    `SegmentLedger` rather than named here. That is what keeps a ledger joining the
    set from leaving its head charged to no job, which is the loss this whole file
    exists to catch.
    """
    stores = set(_stores().values())
    found: dict[str, str] = {}
    for which in ledger.SegmentLedger:
        head = ledger.segment_head(Path(ledger.STATE_DIRNAME), which, SUBSTITUTED_DATE).relpath
        store = next((name for name in stores if _covers(name, head)), None)
        assert store is not None, (
            f"{which.value} segments compact into {head}, and no store module exports a "
            "path helper that covers it. Add one beside the head's own path helper, so "
            "this test can say which job has to stage what the compaction writes."
        )
        found[store] = which.value
    return found


def test_every_store_is_filled_by_a_writer_this_test_can_follow() -> None:
    """The derivation must not answer an empty question.

    Every assertion below reads a list the staging check also reads. A store nothing
    writes, a sink class nothing matches, or a writer nothing calls would each shrink
    one of them in silence and leave a green test saying nothing at all about the
    store that went missing.
    """
    stores = _stores()
    written = set(_writer_stores().values()) | set(_sink_stores().values())
    written |= set(_compacted_stores())

    assert stores, "the store modules export no *_relpath helper, so nothing here is checked"
    assert SINK_CLASSES, (
        f"{sinks.__name__} declares no sink class that takes a path, so the sink half of "
        "the derivation matches nothing and a store written by one is checked by nobody."
    )
    unknown = sorted(set(STORES_NOTHING_FILLS_YET) - set(stores.values()))
    assert not unknown, (
        f"{', '.join(unknown)} is excused from needing a writer and no store module "
        "declares a path helper for it, so the excuse covers nothing. Delete the entry "
        "from STORES_NOTHING_FILLS_YET."
    )
    landed = sorted(set(STORES_NOTHING_FILLS_YET) & written)
    assert not landed, (
        f"{', '.join(landed)} now has a public writer and is still excused from having "
        "one. Delete the entry from STORES_NOTHING_FILLS_YET, so the store is held to "
        "the staging and settlement checks below from its first row."
    )
    unwritten = sorted(set(stores.values()) - written - set(STORES_NOTHING_FILLS_YET))
    assert not unwritten, (
        f"{', '.join(unwritten)} has a path helper and nothing public fills it. Either the "
        "writer is private - make it public, so the staging test can see it - or the "
        "helper is dead and a commit step is staging a directory nothing fills. A helper "
        "that is deliberately ahead of its writer (Guardrail #3) goes in "
        "STORES_NOTHING_FILLS_YET, named with what will fill it."
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
    uncalled = sorted(set(_writer_stores()) - called)
    assert not uncalled, (
        f"{', '.join(uncalled)} is exported as a writer and no module a `python -m idhazh "
        "<verb>` reaches calls it, so its store is charged to no job and the staging check "
        "below says nothing about it. Call it from the stage that fills the store, or "
        "delete it and the path helper beside it."
    )


def test_every_module_that_writes_a_store_is_reached_by_a_cli_verb() -> None:
    """A writer no verb reaches is a store no job can be asked to stage.

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
        if WRITER_CALL.search(source) or SINK_CALL.search(source)
    }

    unknown = sorted(set(MODULES_ONLY_A_TENANT_REACHES) - writing)
    assert not unknown, (
        f"{', '.join(unknown)} is excused from needing a verb and writes no store, so "
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
        f"{', '.join(stranded)} writes a store and no `python -m idhazh <verb>` reaches "
        "it, so no job can be held to staging what it writes. Dispatch it from a verb in "
        "backend/idhazh/cli.py, or call it from a module a verb already enters."
    )


def test_every_store_is_staged_by_the_job_whose_stage_writes_it() -> None:
    """A store no job stages is written on a runner and deleted with it.

    `state/host-fingerprint` was written and staged by nobody until 2026-09-16,
    `state/span-rollup` until 2026-09-15, and `state/traces` beside it. None of them
    broke a test: the writing side was in Python, the staging side was in YAML, and
    nothing read both.

    A job is credited only for its own commit steps. The assemble job stages `state`
    whole and that is worth nothing to a work shard - the shard runs on its own
    runner with its own checkout, and the file it wrote is not in the tree assemble
    committed. That is also why every committing workflow is asked, not only the
    daily one: a second workflow's runner is no closer to the daily run's tree.
    """
    workflows = _load_workflows()
    verb_stores = _verb_stores()
    commit_calls = _job_commit_calls()

    missing: list[str] = []
    credited: set[tuple[str, str]] = set()
    for (workflow_name, job_name), labels in sorted(commit_calls.items()):
        staged = {path for paths in labels.values() for path in paths}
        for verb in sorted(_job_verbs(workflows[workflow_name], job_name)):
            for store, because in sorted(verb_stores.get(verb, {}).items()):
                credited.add((workflow_name, job_name))
                if any(_covers(path, store) for path in staged):
                    continue
                steps = ", ".join(f'"{COMMIT_STEPS[label]}"' for label in sorted(labels))
                missing.append(
                    f"{store} is written by the {job_name} job ({because}) and no commit "
                    f"step in that job stages it. Add {store} to the paths of the {steps} "
                    f"step in .github/workflows/{workflow_name}. Another job staging a "
                    "parent of it is not enough: that job runs on its own runner and "
                    "cannot see a file this one wrote."
                )

    assert not missing, "\n".join(missing)
    assert credited == set(commit_calls), (
        f"the {sorted(set(commit_calls) - credited)} job commits and this test charged "
        "it with no store at all, so nothing above was checked for it."
    )


def _rewritten_stores() -> set[str]:
    """The stores a writer replaces whole, rather than appends a row to.

    `append_*` adds to the file and `write_*` replaces it - the convention the module
    already spells in its own names, and the one `_store_publics` already splits on.
    A writer that replaces settles nothing as it writes, so it names no key. The
    post-merge key is still right for it: two runs' folds can both land in the
    merged copy and the settler is the only thing that can take
    one of them back out again.

    A head the compaction fills is the same case one step further out. It settles its
    rows by key as it folds them (`stages.compact._settle`) rather than as it writes,
    and it has no `append_*`/`write_*` name at all - so it is added here from the
    declared head table. `state/host-fingerprint` is the case.
    """
    stores = _writer_stores()
    replaced = {store for name, store in stores.items() if name.startswith("write_")}
    replaced |= set(_compacted_stores())
    appended = {store for name, store in stores.items() if name.startswith("append_")}
    return replaced - appended


def test_every_ledger_that_declares_a_key_is_registered_for_settlement() -> None:
    """A keyed ledger outside the registry keeps every row a retried job wrote twice.

    `state/span-rollup` was exactly that: staged from 2026-09-15, settled by nothing.
    The two sides are compared as sets rather than as a subset, so a ledger that
    declares no key must also be absent from the registry - which is what
    `keyed_paths` says about the one ledger it deliberately leaves out.

    A store whose writer replaces the file is the exception, and it is derived rather
    than named: see `_rewritten_stores`.

    A store registered before its writer exists is the second exception, and that one
    is named rather than derived: `STORES_NOTHING_FILLS_YET`. Registering the key with
    the shape rather than with its first writer is what makes the settlement true from
    the first row instead of from the second, which is the position
    `state/feed-retirements.csv` was in on 2026-09-02.

    `keyed_paths` is asked for one named date, so it returns that day's cover instead
    of globbing the tree, and this test reads no committed file.
    """
    declared = _declared_keys()
    stores = set(_stores().values())

    registered: dict[str, tuple[str, ...]] = {}
    for entry in ledger.keyed_paths(Path("state"), date=SUBSTITUTED_DATE):
        path = entry.path.as_posix()
        store = next((name for name in stores if _covers(name, path)), None)
        assert store is not None, (
            f"{path} is registered for settlement and matches no store idhazh.ledger "
            "declares a path helper for, so nothing can say which writer fills it."
        )
        registered[store] = entry.key

    unregistered = sorted(set(declared) - set(registered))
    assert not unregistered, (
        f"{', '.join(unregistered)} declares a key in idhazh.ledger and keyed_paths() "
        "does not yield it, so a retried job's repeat of a row is kept instead of "
        "dropped. Add it to keyed_paths() in backend/idhazh/ledger.py."
    )

    keyless = sorted(
        set(registered) - set(declared) - _rewritten_stores() - set(STORES_NOTHING_FILLS_YET)
    )
    assert not keyless, (
        f"{', '.join(keyless)} is registered for settlement, its writer appends rows, and "
        "that writer names no key - so the settler has a key the writer does not use. Name "
        "the key in the writer in backend/idhazh/ledger.py, or take the ledger out of "
        "keyed_paths()."
    )

    for store, key in sorted(declared.items()):
        assert registered[store] == key, (
            f"{store} is written on {key} and settled on {registered[store]}. The two must "
            "be one tuple, or a repeat the writer would have dropped survives the merge."
        )
