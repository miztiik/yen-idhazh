"""Is every ledger `idhazh.ledger` declares wired into the run that writes it?

Two halves of one question. A ledger the writing job never stages is deleted with
the runner, and a keyed ledger nothing settles keeps every row a retried job wrote
twice. Both failures are silent: the pipeline logs a row it wrote, the step that
would have carried it says nothing, and the next reader sees a shorter file than
the run produced.

`state/host-fingerprint` was the first half. It was written from the day the probe
shipped and staged by nothing, so every row went to the bin with the runner.
`state/span-rollup` was both halves at once: nine days written and discarded, then
staged but missing from the settlement registry.

Nothing here names a ledger. Both sides are derived - the ledger side from the
`*_relpath` helpers `idhazh.ledger` already exports, the job side from the CLI's
own dispatch and the workflow's own `run:` bodies - because a hand-written list of
ledger names is the thing that went missing in the first place.

Nothing here opens a file under `state/`. Every path is computed from a fixed date,
so what these tests cost does not move when the archive grows (CLAUDE.md
Guardrail #12).
"""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, Final

import pytest

from idhazh import cli, ledger

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

# The daily run, and only the daily run. `measure.yml` writes under the trial state
# root, throws away most of what it writes, and holds its own staged list
# closed-world in test_bench_targets.py - so a ledger it does not stage is a
# decision rather than a loss. The labels in scope are whichever ones the harness
# says live in this file, so a sixth commit step joins without an edit here.
DAILY_WORKFLOW: Final = "digest.yml"

# A second date, in another year, so the longest prefix two paths from one helper
# share is the directory a commit step would stage rather than that directory plus
# a year or a month.
OTHER_DATE: Final = "2027-01-02"

# The package the pipeline lives in, and the name its modules import the ledger as.
PACKAGE: Final = ledger.__name__.split(".")[0]
LEDGER_ALIAS: Final = ledger.__name__.rsplit(".", 1)[-1]
WRITER_CALL: Final = re.compile(rf"\b{LEDGER_ALIAS}\.((?:append|write)_[a-z_]+)\(")


def _ledger_publics(
    *, suffix: str = "", prefixes: tuple[str, ...] = ()
) -> dict[str, Callable[..., Any]]:
    """The public callables `idhazh.ledger` exports under a suffix or a prefix."""
    found: dict[str, Callable[..., Any]] = {}
    for name, value in sorted(vars(ledger).items()):
        if name.startswith("_") or not callable(value):
            continue
        if suffix and not name.endswith(suffix):
            continue
        if prefixes and not name.startswith(prefixes):
            continue
        found[name] = value
    return found


def _relpath_for(name: str, helper: Callable[..., Any], date: str) -> str:
    """One ledger path for one date, from the helper the module already exports."""
    required = [
        parameter
        for parameter in inspect.signature(helper).parameters.values()
        if parameter.default is inspect.Parameter.empty
    ]
    assert len(required) <= 1, (
        f"idhazh.ledger.{name} takes {len(required)} arguments with no default. This "
        "test calls every *_relpath helper with a date or with nothing, so a helper "
        "that needs more has to say here what to pass it."
    )
    produced = helper(date) if required else helper()
    assert isinstance(produced, str), f"idhazh.ledger.{name} must return a path string"
    return produced


def _stores() -> dict[str, str]:
    """Every store the ledger module declares: helper name -> the path a job stages.

    The staged path is the longest prefix two dates share, so a dated ledger reduces
    to its own directory and an undated one stays the file it is.
    """
    found: dict[str, str] = {}
    for name, helper in _ledger_publics(suffix="_relpath").items():
        first = _relpath_for(name, helper, SUBSTITUTED_DATE).split("/")
        second = _relpath_for(name, helper, OTHER_DATE).split("/")
        shared: list[str] = []
        for left, right in zip(first, second, strict=False):
            if left != right:
                break
            shared.append(left)
        assert shared, f"idhazh.ledger.{name} returns two paths with nothing in common"
        found[name] = "/".join(shared)
    return found


def _writer_stores() -> dict[str, str]:
    """Every public ledger writer, and the store it writes.

    Resolved from the path helper the writer's own body calls, so a writer named for
    one thing and writing another follows the code rather than the name.
    """
    stores = _stores()
    resolved: dict[str, str] = {}
    for name, writer in _ledger_publics(prefixes=("append_", "write_")).items():
        source = inspect.getsource(writer)
        stems = [
            call.removesuffix("_path").removesuffix("_relpath")
            for call in re.findall(r"\b([a-z_]+_(?:rel)?path)\(", source)
        ]
        stems.append(name.split("_", 1)[1])
        helper = next((f"{stem}_relpath" for stem in stems if f"{stem}_relpath" in stores), None)
        assert helper is not None, (
            f"idhazh.ledger.{name} writes a store this test cannot name: it calls no "
            "path helper it shares a name with. Add a `<store>_relpath()` helper beside "
            f"the others and call it from {name}."
        )
        resolved[name] = stores[helper]
    return resolved


def _declared_keys() -> dict[str, tuple[str, ...]]:
    """Store -> the key its writer's own code names, for every writer that names one.

    Read from the syntax tree rather than the text, so a key mentioned in a docstring
    is not mistaken for a key the writer settles rows on.
    """
    stores = _writer_stores()
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
        assert len(used) <= 1, f"idhazh.ledger.{name} names {used}; one writer, one key"
        if not used:
            continue
        key = getattr(ledger, used[0])
        assert isinstance(key, tuple), f"idhazh.ledger.{used[0]} must be a tuple of columns"
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

    A verb reaches a module when its branch calls a `stage_*` entry point on it. A
    helper borrowed from another stage is not a dispatch: charging a job with another
    stage's ledgers because it borrowed one function would ask for staging nobody
    needs, and a test that asks for the wrong thing gets edited away.
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
            if not call.func.attr.startswith("stage_"):
                continue
            if not isinstance(call.func.value, ast.Name):
                continue
            entered = getattr(cli, call.func.value.id, None)
            if isinstance(entered, ModuleType):
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


def _verb_stores() -> dict[str, dict[str, str]]:
    """CLI verb -> store -> the sentence that says why that verb writes it.

    One hop past the dispatched stage, because a stage that hands the writing to a
    helper module still owes the run the rows: the fold writes its months through
    `retention`, and the probe writes its row through `telemetry.silicon`.
    """
    stores = _writer_stores()
    charged: dict[str, dict[str, str]] = {}
    for verb, dispatched in _dispatched_modules().items():
        reachable: set[ModuleType] = set()
        for module in dispatched:
            reachable.add(module)
            reachable |= _calls_into(module)
        for module in sorted(reachable, key=lambda entered: entered.__name__):
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
    return charged


def _job_verbs(workflow: dict[str, object], job_name: str) -> set[str]:
    """The CLI verbs one job's steps run."""
    found: set[str] = set()
    for step in _steps(workflow, job_name):
        for text in _strings(step):
            found.update(re.findall(rf"\b{PACKAGE} (?!-)([a-z][a-z-]*)", text))
    return found


def _job_commit_calls() -> dict[str, dict[str, list[str]]]:
    """Job -> commit label -> the paths that label stages, read from the workflow."""
    calls: dict[str, dict[str, list[str]]] = {}
    for label, workflow in COMMIT_WORKFLOWS.items():
        if workflow != DAILY_WORKFLOW:
            continue
        calls.setdefault(COMMIT_JOBS[label], {})[label] = _commit_call(label)[0]
    return calls


def _covers(staged: str, store: str) -> bool:
    """Would `git add <staged>` carry this store?"""
    return store == staged or store.startswith(f"{staged}/")


def test_every_ledger_writer_resolves_to_one_store_this_test_can_check() -> None:
    """The derivation must not answer an empty question.

    Both assertions below read the same two lists. A store nothing writes would
    shrink one of them in silence and leave a green test asserting nothing about the
    ledger that went missing.
    """
    stores = _stores()
    written = set(_writer_stores().values())

    assert stores, "idhazh.ledger exports no *_relpath helper, so nothing here is checked"
    unwritten = sorted(set(stores.values()) - written)
    assert not unwritten, (
        f"{', '.join(unwritten)} has a path helper in idhazh.ledger and no public writer. "
        "Either the writer is private - make it public, so the staging test can see it - "
        "or the helper is dead and a commit step is staging a directory nothing fills."
    )


def test_every_module_that_writes_a_ledger_is_reached_by_a_cli_verb() -> None:
    """A writer no verb reaches is a ledger no job can be asked to stage.

    This is the hole the staging assertion would otherwise fall through. A stage that
    writes rows from a module the CLI never enters is charged to no job, so the
    parity check stays green while the rows go nowhere.
    """
    reached: set[str] = set()
    for dispatched in _dispatched_modules().values():
        for module in dispatched:
            reached.add(module.__name__)
            reached |= {called.__name__ for called in _calls_into(module)}

    package_dir = Path(inspect.getfile(ledger)).parent
    writing = {
        path.relative_to(package_dir.parent).with_suffix("").as_posix().replace("/", ".")
        for path in sorted(package_dir.rglob("*.py"))
        if WRITER_CALL.search(path.read_text(encoding="utf-8"))
    }

    stranded = sorted(writing - reached - {ledger.__name__})
    assert not stranded, (
        f"{', '.join(stranded)} calls a ledger writer and no `python -m idhazh <verb>` "
        "reaches it, so no job can be held to staging what it writes. Dispatch it from a "
        "verb in backend/idhazh/cli.py, or call it from a module a verb already enters."
    )


def test_every_ledger_is_staged_by_the_job_whose_stage_writes_it() -> None:
    """A ledger no job stages is written on a runner and deleted with it.

    `state/host-fingerprint` was written and staged by nobody until 2026-09-16, and
    `state/span-rollup` until 2026-09-15. Neither broke a test: the ledger side was
    in Python, the staging side was in YAML, and nothing read both.

    A job is credited only for its own commit steps. The assemble job stages `state`
    whole and that is worth nothing to a work shard - the shard runs on its own
    runner with its own checkout, and the file it wrote is not in the tree assemble
    committed.
    """
    workflow = _load_workflows()[DAILY_WORKFLOW]
    verb_stores = _verb_stores()
    commit_calls = _job_commit_calls()

    missing: list[str] = []
    credited: dict[str, set[str]] = {}
    for job_name, labels in sorted(commit_calls.items()):
        staged = {path for paths in labels.values() for path in paths}
        for verb in sorted(_job_verbs(workflow, job_name)):
            for store, because in sorted(verb_stores.get(verb, {}).items()):
                credited.setdefault(job_name, set()).add(store)
                if any(_covers(path, store) for path in staged):
                    continue
                steps = ", ".join(f'"{COMMIT_STEPS[label]}"' for label in sorted(labels))
                missing.append(
                    f"{store} is written by the {job_name} job ({because}) and no commit "
                    f"step in that job stages it. Add {store} to the paths of the {steps} "
                    f"step in .github/workflows/{DAILY_WORKFLOW}. Another job staging a "
                    "parent of it is not enough: that job runs on its own runner and "
                    "cannot see a file this one wrote."
                )

    assert not missing, "\n".join(missing)
    assert set(credited) == set(commit_calls), (
        f"the {sorted(set(commit_calls) - set(credited))} job commits in "
        f".github/workflows/{DAILY_WORKFLOW} and this test charged it with no ledger at "
        "all, so nothing above was checked for it."
    )


def test_every_ledger_that_declares_a_key_is_registered_for_settlement() -> None:
    """A keyed ledger outside the registry keeps every row a retried job wrote twice.

    `state/span-rollup` was exactly that: staged from 2026-09-15, settled by nothing.
    The two sides are compared as sets rather than as a subset, so a ledger that
    declares no key must also be absent from the registry - which is what
    `keyed_paths` says about the one ledger it deliberately leaves out.

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

    keyless = sorted(set(registered) - set(declared))
    assert not keyless, (
        f"{', '.join(keyless)} is registered for settlement and its writer names no key, "
        "so the settler has a key the writer does not use. Name the key in the writer in "
        "backend/idhazh/ledger.py, or take the ledger out of keyed_paths()."
    )

    for store, key in sorted(declared.items()):
        assert registered[store] == key, (
            f"{store} is written on {key} and settled on {registered[store]}. The two must "
            "be one tuple, or a repeat the writer would have dropped survives the merge."
        )
