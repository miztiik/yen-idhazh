"""Which ledgers the package declares, which CLI verbs write them, and which verbs a job runs.

The derivation the ledger wiring checks share, so each check reads one answer
rather than keeping a copy of it. Nothing here names a ledger. The ledger side
is read from the registry every ledger is declared in, and the job side from
the CLI's own dispatch and the workflows' own `run:` bodies, because a
hand-written list of ledger names is the thing that went missing in the first
place.

Nothing here opens a file under `state/`. Every path is computed from a fixed
date, and every source read is the package's own code, so what this costs does
not move when the archive grows (CLAUDE.md Guardrail #12).
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
import uuid
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from idhazh import cli, day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.ledger import paths
from idhazh.stages import compact as compact_stage
from idhazh.telemetry import sinks, traces

from ._harness import SUBSTITUTED_DATE, _steps, _strings

# A second date, in another year, so the longest prefix two paths from one helper
# share is the directory a commit step would stage rather than that directory plus
# a year or a month.
OTHER_DATE: Final = "2027-01-02"


# Every module this derivation reads a ledger's writers and path helpers from.
# `idhazh.telemetry.traces` is here for its path helper rather than for an
# address of its own: the trace tree is registered, and a sink rather than a
# writer function fills it, so the sink half keys it by the `*_relpath` helper
# beside the path the sink is opened on. `idhazh.ledger` is here for its writers:
# every address it builds comes from the registry.
LEDGER_MODULES: Final = (ledger, traces)


# The package the pipeline lives in, and the name its modules import the ledger as.
PACKAGE: Final = ledger.__name__.split(".")[0]


LEDGER_ALIAS: Final = ledger.__name__.rsplit(".", 1)[-1]


WRITER_CALL: Final = re.compile(rf"\b{LEDGER_ALIAS}\.((?:append|write)_[a-z_]+)\(")

#: The door every raw-and-compact ledger is written through, and the pattern a
#: call to it matches. The door is generic over the vocabulary, so which ledger a
#: call fills is read from that call's own `ledger=` argument.
PERSIST: Final = ledger.persist.__name__
PERSIST_CALL: Final = re.compile(rf"\b{LEDGER_ALIAS}\.{PERSIST}\(")

#: The name `cli.main` keeps the command line in, and the attribute a package it
#: hands that line to names its own verb with.
LINE_NAME: Final = "words"
HANDOVER_WORD: Final = "VERB"


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


def _ledger_publics(
    *, suffix: str = "", prefixes: tuple[str, ...] = ()
) -> dict[str, Callable[..., Any]]:
    """The public callables the ledger modules export under a suffix or a prefix."""
    found: dict[str, Callable[..., Any]] = {}
    for module in LEDGER_MODULES:
        for name, value in sorted(vars(module).items()):
            if name.startswith("_") or not callable(value):
                continue
            if suffix and not name.endswith(suffix):
                continue
            if prefixes and not name.startswith(prefixes):
                continue
            assert name not in found, (
                f"{module.__name__} and {found[name].__module__} both export {name}, and "
                "this test keys a ledger by the bare helper name. Rename one of them."
            )
            found[name] = value
    return found


def _helper_arguments(date: str) -> dict[str, object]:
    """What to pass a path helper, named by the parameter that asks for it.

    A ledger filed by something other than a date says so in its own signature - the
    trace tree files by run and by shard - so the value follows the parameter's name
    rather than the helper's.

    Only a helper that names its own ledger is called this way. A builder generic
    over the vocabulary is addressed through the registry instead, which knows what
    period each ledger's address asks for.
    """
    return {
        "date": date,
        "month": date,
        "run_id": f"{date}-1",
        "shard": 0,
        "stamp": date,
        "attempt": 1,
        "job": ServerJob.WORK,
    }


def _relpath_for(name: str, helper: Callable[..., Any], date: str) -> str:
    """One ledger path for one date, from the helper the module already exports."""
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


def _shared_prefix(first: str, second: str) -> str:
    """The longest directory prefix two paths share, which is what a job stages."""
    shared: list[str] = []
    for left, right in zip(first.split("/"), second.split("/"), strict=False):
        if left != right:
            break
        shared.append(left)
    return "/".join(shared)


def _names_a_ledger(helper: Callable[..., Any]) -> bool:
    """Does this helper carry one ledger of its own, rather than take the name?

    A builder handed a `LedgerName` addresses whichever ledger it was given, so it
    declares none and the registry above already covers every one it can reach.
    """
    return not any(
        LedgerName.__name__ in str(parameter.annotation)
        for parameter in inspect.signature(helper).parameters.values()
    )


def _period(grain: Grain, date: str) -> str | None:
    """The cover one ledger's address asks for, spelled the way its grain asks.

    A flat ledger names no period and is handed none. The rest take the day, the
    month it falls in, or a stamp taken during it - and two dates have to give two
    addresses, or the prefix they share would be the whole path.
    """
    if grain is Grain.FLAT:
        return None
    if grain is Grain.MONTH_FILE:
        return date[: len("YYYY-MM")]
    if grain is Grain.STAMPED:
        return f"{date.replace('-', '')}T120000Z"
    return date


def _address(member: LedgerName, date: str) -> str:
    """One ledger's file for one date, from the builder its grain uses.

    A ledger that goes through the door has no registry address, so its raw file
    for the day is asked of the raw builder instead, under a fixed file id.
    """
    grain = paths.entry(member).grain
    if grain is Grain.RAW_AND_COMPACT:
        state = Path(paths.STATE_DIRNAME)
        return paths.raw_path(state, member, date, uuid.UUID(int=0)).as_posix()
    return paths.relpath(member, _period(grain, date))


def _ledgers() -> dict[str, str]:
    """Every ledger the pipeline declares: its own name -> the path a job stages.

    The registry is the declaration, so a ledger joins this derivation on the day
    its entry lands rather than on the day somebody remembers to write a helper for
    it. A ledger outside the registry keeps declaring itself by exporting a
    `*_relpath` helper, and is keyed by that helper's name.

    The staged path is the longest prefix two dates share, so a dated ledger reduces
    to its own directory and an undated one stays the file it is.
    """
    found: dict[str, str] = {}
    for member in LedgerName:
        shared = _shared_prefix(
            _address(member, SUBSTITUTED_DATE), _address(member, OTHER_DATE)
        )
        assert shared, f"{member.value} addresses two dates with nothing in common"
        found[member.value] = shared
    for name, helper in _ledger_publics(suffix="_relpath").items():
        if not _names_a_ledger(helper):
            continue
        shared = _shared_prefix(
            _relpath_for(name, helper, SUBSTITUTED_DATE),
            _relpath_for(name, helper, OTHER_DATE),
        )
        assert shared, f"{helper.__module__}.{name} returns two paths with nothing in common"
        found[name] = shared
    return found


def _ledgers_named_in(tree: ast.AST) -> set[LedgerName]:
    """Every `LedgerName` member this syntax names.

    Read from the syntax tree rather than the text, so a member mentioned in a
    docstring is not mistaken for a ledger the code addresses.
    """
    return {
        LedgerName[node.attr]
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == LedgerName.__name__
        and node.attr in LedgerName.__members__
    }


def _ledgers_handed_to() -> dict[str, frozenset[LedgerName]]:
    """Called function -> the ledgers the package's own calls name in its arguments.

    A writer generic over the vocabulary fills whichever ledger its caller names, so
    the call site is the only place that says which - the same reason a file sink is
    read from its call site rather than from a name.

    Read from the package's own files, so what this costs grows with the code rather
    than with the archive (CLAUDE.md Guardrail #12).
    """
    handed: dict[str, set[LedgerName]] = {}
    for source in _package_sources().values():
        for call in ast.walk(ast.parse(source)):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
            named = {member for argument in arguments for member in _ledgers_named_in(argument)}
            if named:
                handed.setdefault(call.func.attr, set()).update(named)
    return {name: frozenset(members) for name, members in handed.items()}


def _writer_ledgers() -> dict[str, frozenset[str]]:
    """Every public ledger writer, and the ledgers it fills.

    Resolved from the `LedgerName` the writer's own body names, so a writer named
    for one thing and filling another follows the code rather than the name.

    Two writers name none, and each is asked the next question down. A writer that
    takes a `LedgerName` is generic over the vocabulary, so it is charged with every
    ledger the package hands it. A writer that takes a path has neither, and only
    its own name is left to read - which is why that name has to be the ledger's.
    """
    ledgers = _ledgers()
    handed = _ledgers_handed_to()
    resolved: dict[str, frozenset[str]] = {}
    for name, writer in _ledger_publics(prefixes=("append_", "write_")).items():
        filled = _ledgers_named_in(ast.parse(inspect.getsource(writer).lstrip()))
        if not filled and not _names_a_ledger(writer):
            filled = set(handed.get(name, frozenset()))
        if not filled:
            spelled = name.split("_", 1)[1].replace("_", "-")
            filled = {member for member in LedgerName if member.value == spelled}
        assert filled, (
            f"{writer.__module__}.{name} fills a ledger this test cannot name: it names no "
            "LedgerName, it is handed none by any caller, and no ledger is called "
            f"{name.split('_', 1)[1].replace('_', '-')!r}. Name the ledger in the writer, "
            "or take a LedgerName argument and let the caller name it."
        )
        resolved[name] = frozenset(ledgers[member.value] for member in filled)
    return resolved


def _package_sources() -> dict[str, str]:
    """Every module in the pipeline package: its dotted name -> its source text.

    The package's own files and nothing else, so what this reads grows with the code
    rather than with the archive (CLAUDE.md Guardrail #12).

    Located from the pipeline package itself, never from a module inside it. Taking
    the parent of `ledger`'s own file read the whole package while the ledger was one
    file and only the ledger package once it became a directory, which silently
    dropped every sink call outside it.
    """
    package_dir = Path(inspect.getfile(importlib.import_module(PACKAGE))).parent
    return {
        path.relative_to(package_dir.parent).with_suffix("").as_posix().replace("/", "."): (
            path.read_text(encoding="utf-8")
        )
        for path in sorted(package_dir.rglob("*.py"))
    }


def _sink_ledgers() -> dict[str, str]:
    """Every path helper a file sink is opened on, and the ledger it fills.

    Read out of the package's own source, because a sink has no `append_*` name to be
    found by: the call site is the only place that says which ledger it writes.
    """
    ledgers = _ledgers()
    opened = {
        helper for source in _package_sources().values() for helper in SINK_CALL.findall(source)
    }
    resolved: dict[str, str] = {}
    for helper in sorted(opened):
        stem = helper.removesuffix("_path")
        assert f"{stem}_relpath" in ledgers, (
            f"a file sink is opened on {helper}(), and no ledger module exports a "
            f"{stem}_relpath() helper for it. Add one beside the path helper, so this "
            "test can say which ledger the sink fills and which job has to stage it."
        )
        resolved[helper] = ledgers[f"{stem}_relpath"]
    return resolved


def _handover_verb(test: ast.expr) -> str | None:
    """The verb a hand-over branch of `cli.main` answers to, or `None` for any other branch.

    `telemetry` and `gardener` hand the rest of the line to their own package
    before the parser is built, so their branches compare the line's first word
    rather than `args.stage`. The word is read from the handed-to module's own
    `VERB` and never spelled here. A branch that compares the first word any
    other way fails by name, because a verb this cannot map is a module no job
    can be charged with.
    """
    compared_all = test.values if isinstance(test, ast.BoolOp) else [test]
    for compared in compared_all:
        if not (isinstance(compared, ast.Compare) and isinstance(compared.left, ast.Subscript)):
            continue
        first = compared.left
        if not (
            isinstance(first.value, ast.Name)
            and first.value.id == LINE_NAME
            and isinstance(first.slice, ast.Constant)
            and first.slice.value == 0
        ):
            continue
        word = compared.comparators[0] if len(compared.comparators) == 1 else None
        handed = (
            getattr(cli, word.value.id, None)
            if isinstance(word, ast.Attribute)
            and isinstance(word.value, ast.Name)
            and word.attr == HANDOVER_WORD
            else None
        )
        verb = getattr(handed, HANDOVER_WORD, None)
        assert isinstance(compared.ops[0], ast.Eq) and isinstance(handed, ModuleType), (
            f"cli.main hands the line over on `{ast.unparse(compared)}`, which this "
            f"derivation cannot map to a verb. Compare {LINE_NAME}[0] with the handed-to "
            f"module's own {HANDOVER_WORD}."
        )
        assert isinstance(verb, str), f"{handed.__name__}.{HANDOVER_WORD} is not a word"
        return verb
    return None


def _branch_verbs(branch: ast.If) -> list[str]:
    """The `args.stage` values one branch of `cli.main` answers to, or its hand-over verb."""
    handed = _handover_verb(branch.test)
    if handed is not None:
        return [handed]
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
    therefore saw the council enter no module at all and left its ledger charged to
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
    """The ledger path helpers this module's source hands to a file sink."""
    return set(SINK_CALL.findall(inspect.getsource(module)))


def _persisted_in(source: str, where: str) -> set[str]:
    """The ledgers one module's source hands to `ledger.persist`, as the paths a job stages.

    Read from each call's own `ledger=` argument, because the door fills
    whichever ledger its caller names. A call that names none is refused by
    name: a write this cannot follow is a ledger no job can be charged with.
    """
    ledgers = _ledgers()
    found: set[str] = set()
    for call in ast.walk(ast.parse(source)):
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == PERSIST
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == LEDGER_ALIAS
        ):
            continue
        named = {
            member
            for keyword in call.keywords
            if keyword.arg == "ledger"
            for member in _ledgers_named_in(keyword.value)
        }
        assert named, (
            f"{where} calls {LEDGER_ALIAS}.{PERSIST} on line {call.lineno} and names no "
            "LedgerName in its ledger= argument, so this test cannot say which ledger it "
            "fills. Name the ledger at the call."
        )
        found |= {ledgers[member.value] for member in named}
    return found


def _persisted_by(module: ModuleType) -> set[str]:
    """The ledgers this module files rows into through the door."""
    return _persisted_in(inspect.getsource(module), module.__name__)


def _persisted_ledgers() -> dict[str, set[str]]:
    """Every pipeline module that files rows through the door -> the ledgers it fills.

    Read from the package's own files, so what this costs grows with the code
    rather than with the archive (CLAUDE.md Guardrail #12).
    """
    filled = {name: _persisted_in(source, name) for name, source in _package_sources().items()}
    return {name: ledgers for name, ledgers in filled.items() if ledgers}


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


def _verb_ledgers() -> dict[str, dict[str, str]]:
    """CLI verb -> ledger -> the sentence that says why that verb writes it.

    A ledger writer, a file sink and a call to the ledger door are all writes,
    and a ledger filled any of those ways is a ledger the job that runs the verb
    has to stage.
    """
    ledgers = _writer_ledgers()
    sunk = _sink_ledgers()
    compacted = _compacted_ledgers()
    charged: dict[str, dict[str, str]] = {}
    for verb, reachable in _reachable_modules().items():
        for module in sorted(reachable, key=lambda entered: entered.__name__):
            if module is compact_stage:
                for ledger_path, which in sorted(compacted.items()):
                    charged.setdefault(verb, {})[ledger_path] = (
                        f"`python -m idhazh {verb}` reaches {module.__name__}, "
                        f"which folds every waiting {which} segment into this head"
                    )
            for writer in sorted(_writers_called_by(module)):
                assert writer in ledgers, (
                    f"{module.__name__} calls ledger.{writer}, which idhazh.ledger does "
                    "not export. Rename the call, or export the writer so this test can "
                    "find the ledger it fills."
                )
                for ledger_path in sorted(ledgers[writer]):
                    charged.setdefault(verb, {})[ledger_path] = (
                        f"`python -m idhazh {verb}` reaches {module.__name__}, "
                        f"which calls ledger.{writer}"
                    )
            for opener in sorted(_sinks_opened_by(module)):
                charged.setdefault(verb, {})[sunk[opener]] = (
                    f"`python -m idhazh {verb}` reaches {module.__name__}, "
                    f"which opens a file sink on {opener}()"
                )
            for ledger_path in sorted(_persisted_by(module)):
                charged.setdefault(verb, {})[ledger_path] = (
                    f"`python -m idhazh {verb}` reaches {module.__name__}, "
                    f"which files rows through ledger.{PERSIST}"
                )
    return charged


def _job_verbs(workflow: dict[str, object], job_name: str) -> set[str]:
    """The CLI verbs one job's steps run."""
    found: set[str] = set()
    for step in _steps(workflow, job_name):
        for text in _strings(step):
            found.update(re.findall(rf"\b{PACKAGE} (?!-)([a-z][a-z-]*)", text))
    return found


def _folded_day(which: LedgerName, date: str) -> str:
    """Where the fold of one tree's day lands, spelled by the producer.

    A settled file sits beside the writer files it replaced, so the day-shard helper
    names the directory and the fold names the file inside it.
    """
    written = ledger.day_shard_relpath(
        which,
        date=date,
        run_id=f"{date}-1",
        attempt=1,
        job=ServerJob.WORK,
        shard=0,
    )
    return f"{written.rsplit('/', 1)[0]}/{day_shards.SETTLED_NAME}"


def _compacted_ledgers() -> dict[str, str]:
    """Every tree the fold writes into, and the ledger a job has to stage for it.

    The fold writes generically - one function over every declared tree, and no
    `append_*` name for `_writer_ledgers` to find - so it is read out of
    `DAY_TREES` rather than named here. That is what keeps a ledger joining the
    set from leaving its folded day charged to no job, which is the loss this whole
    file exists to catch.

    The ledger is the prefix two dates share, taken from the one helper that names a
    day shard for any tree. Reading it per tree from `day_shard_relpath` is what
    reaches all nine: a tree also has a `*_relpath` helper of its own only where a
    reader outside the fold asks for one day of it by date.
    """
    found: dict[str, str] = {}
    for which in DAY_TREES:
        shared = _shared_prefix(
            _folded_day(which, SUBSTITUTED_DATE), _folded_day(which, OTHER_DATE)
        )
        assert shared, f"{which.value} folds two dates to paths with nothing in common"
        found[shared] = which.value
    return found


def _door_calls() -> frozenset[str]:
    """Every name on `idhazh.ledger` whose call reads or writes a file under the two roots.

    The door's own functions, the raw reader's, and every public reader that
    reads through the raw reader - found in their own sources, so a reader that
    moves onto the door joins this set the day it does, and nothing here names
    one.
    """
    door = importlib.import_module(ledger.persist.__module__)
    raw_reader = importlib.import_module(ledger.load_current_rows.__module__)
    through = re.compile(rf"\b{raw_reader.__name__.rsplit('.', 1)[-1]}\.[a-z_]+\(")
    names: set[str] = set()
    for name, value in vars(ledger).items():
        if name.startswith("_") or not callable(value):
            continue
        if getattr(value, "__module__", None) in (door.__name__, raw_reader.__name__):
            names.add(name)
            continue
        try:
            source = inspect.getsource(value)
        except (OSError, TypeError):
            continue
        if through.search(source):
            names.add(name)
    return frozenset(names)


def _door_verbs() -> dict[str, set[str]]:
    """CLI verb -> the modules it reaches that read or write a ledger through the door.

    A verb that only reads a retirement still needs the engine: the read opens a
    parquet file whatever the verb does with the row afterwards.
    """
    calls = _door_calls()
    pattern = re.compile(rf"\b{LEDGER_ALIAS}\.(?:{'|'.join(sorted(calls))})\(")
    touched: dict[str, set[str]] = {}
    for verb, reachable in _reachable_modules().items():
        for module in reachable:
            if pattern.search(inspect.getsource(module)):
                touched.setdefault(verb, set()).add(module.__name__)
    return touched
