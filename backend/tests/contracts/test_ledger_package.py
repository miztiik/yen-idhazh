"""Is the ledger a package with one door, and does the door stay empty?

Seven checks. Most pass at both ends of the split by design - what each one has to
be able to fail is the property the move could break, and the ones that can are
the facade shape, the write-path composition, the load order and the pyarrow
probe. The seventh is the door itself: no module outside the package spells
where a ledger's folder is.

Nothing here reads `state/`. Every walk is over the package's own files, so what
it costs grows with the code rather than with the archive (Guardrail #12).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from functools import cache
from pathlib import Path
from typing import Final

import pytest
from _source_files import source_files
from conftest import writer_identity

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.evals.observation_batches import preparation_path
from idhazh.ledger import filenames, paths

pytestmark = pytest.mark.contract

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
BACKEND: Final = REPO_ROOT / "backend"
PACKAGE: Final = BACKEND / "idhazh" / "ledger"

#: One fixed writer, so the composition and the old inline rule are compared on
#: the same four identity cells rather than on two sets that happen to agree.
A_DAY: Final = "2026-09-18"
A_RUN: Final = "2026-09-18-1"
AN_ATTEMPT: Final = 2
A_JOB: Final = ServerJob.WORK
A_SHARD: Final = 7

#: Every tree a writer files a segment into, in one fixed order.
WRITTEN_INTO: Final[tuple[LedgerName, ...]] = tuple(
    sorted(DAY_TREES, key=lambda member: member.value)
)

#: Modules naming ignored runtime files rather than a ledger file under state/.
#:
#: Qualification artifacts and evaluation preparation manifests live under
#: backend/var/. The latter's boundary is checked below.
#:
MINTS_ITS_OWN_NAME: Final[frozenset[str]] = frozenset({
    "backend/idhazh/stages/qualify.py",
    "backend/idhazh/evals/observation_batches.py",
})

#: Names whose whole point is that one module outside the package asks for them
#: rather than carrying a copy. `path_classes` answers whether a committed path
#: has exactly one writer, which it cannot do without the pattern.
ASKS_RATHER_THAN_COPIES: Final = "backend/idhazh/path_classes.py"
OWNED_PATTERNS: Final = ("SEGMENT_NAME", "SEGMENT_SUFFIX", "REPAIR_NAME", "REPAIR_STAMP")

#: What a filename is assembled out of. A literal ending in one of these plus a
#: cell of writer identity is a name being built, wherever it sits.
IDENTITY_CELLS: Final = ("run_id", "attempt", "shard", "job")
ROW_SUFFIXES: Final = (".csv", ".jsonl", ".json", ".parquet")

#: Where a typed folder under `state/` is refused: every module that is not a
#: test. A test may build a fixture tree under any root it likes, and the join
#: check below still holds it to the registry's names.
READS_STATE: Final = ("backend/idhazh/", "backend/utilities/", "backend/bin/")

#: The one module outside the package that types folders under `state/`, and why.
#: `path_classes` copies the per-path rules `.gitattributes` declares, so each
#: folder in it is that file's spelling rather than a reach into the registry,
#: and `backend/tests/contracts/test_path_classes.py` holds the two in step.
#:
#: Written out so a SECOND one fails here rather than joining it unnoticed.
TYPES_ITS_OWN_FOLDERS: Final[frozenset[str]] = frozenset({"backend/idhazh/path_classes.py"})


@cache
def _backend_modules() -> dict[str, ast.Module]:
    """Every backend module: its repository-relative path -> its syntax tree.

    The code tree and nothing else, so this costs what the repository holds in
    Python rather than what a run has written under `state/` (Guardrail #12).
    Parsed once and shared, because three checks here walk the same trees and
    parsing them per check is most of what this file costs.
    """
    return {
        path.relative_to(REPO_ROOT).as_posix(): ast.parse(path.read_text(encoding="utf-8"))
        for path in source_files(
            roots=(BACKEND,),
            suffixes=(".py",),
            excluded_roots=(BACKEND / "var",),
        )
    }


def _fresh_interpreter(body: str) -> subprocess.CompletedProcess[str]:
    """Run `body` in a new interpreter that has imported nothing of ours yet.

    A same-process assertion is worthless for anything about import order: this
    suite has already imported every module by the time it runs.
    """
    return subprocess.run(
        [sys.executable, "-c", body],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"PYTHONPATH": str(BACKEND)},
        cwd=str(REPO_ROOT),
    )


# --- the facade holds imports and one __all__, and nothing else --------------


def test_the_facade_defines_nothing_of_its_own() -> None:
    """A definition here would be a second home for something a module owns.

    The door's whole job is to say which module holds a name. A constant or a
    function that grew back into it would be a second source of truth, and the
    next reader would have no way to tell which one a caller reached.
    """
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    strays: list[str] = []
    for at, node in enumerate(tree.body):
        if isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if at == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # the leading module docstring
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__all__"
        ):
            continue
        strays.append(f"line {node.lineno}: {ast.unparse(node).splitlines()[0]}")

    assert not strays, (
        "backend/idhazh/ledger/__init__.py holds something other than an import, the "
        f"one __all__ and its docstring: {strays}. Put it in the module that answers "
        "its question and re-export the name."
    )


def test_the_facade_names_its_exports_once() -> None:
    """One `__all__`, and every name in it is bound. Two lists disagree by hand."""
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    declared = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
    ]
    assert len(declared) == 1, f"the facade declares __all__ {len(declared)} times"
    for name in ledger.__all__:
        assert hasattr(ledger, name), f"__all__ names {name} and the facade does not bind it"


def test_evaluation_job_manifests_live_outside_state(tmp_path: Path) -> None:
    state = tmp_path / ledger.STATE_DIRNAME
    manifest = preparation_path(state, writer_identity(A_RUN))
    assert manifest.is_relative_to(tmp_path / "backend" / "var")
    assert not manifest.is_relative_to(state)


# --- every name a caller reaches is bound on the package ---------------------


def _shadows_the_module(scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> bool:
    """Whether this scope binds `ledger` to something of its own.

    Several readers name a local `ledger` - a `Path`, a row, a directory name -
    so `ledger.name` in one of them is a string attribute rather than a reach
    into this package. Asked per scope, so a module holding both still has its
    real reaches read.
    """
    arguments = [
        *scope.args.posonlyargs,
        *scope.args.args,
        *scope.args.kwonlyargs,
        *([scope.args.vararg] if scope.args.vararg else []),
        *([scope.args.kwarg] if scope.args.kwarg else []),
    ]
    if any(argument.arg == "ledger" for argument in arguments):
        return True
    return any(
        isinstance(node, ast.Name) and node.id == "ledger" and isinstance(node.ctx, ast.Store)
        for node in ast.walk(scope)
    )


def _reaches(tree: ast.Module) -> set[str]:
    """Every ledger name this module reaches, in either spelling.

    Read from the syntax tree, so a name written in a docstring is not mistaken
    for one a caller reaches. Descended rather than walked flat, so a function
    that names its own `ledger` takes its whole body out of the count.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "idhazh.ledger":
            found.update(alias.name for alias in node.names)
    imports_it = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "idhazh"
        and any(alias.name == "ledger" and alias.asname is None for alias in node.names)
        for node in ast.walk(tree)
    )
    if not imports_it:
        return found

    pending: list[ast.AST] = [tree]
    while pending:
        node = pending.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) and (
            _shadows_the_module(node)
        ):
            continue
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "ledger"
        ):
            found.add(node.attr)
        pending.extend(ast.iter_child_nodes(node))
    return found


def _demanded() -> dict[str, set[str]]:
    """Every ledger name reached from backend code -> the modules that reach it."""
    asked: dict[str, set[str]] = {}
    for relpath, tree in _backend_modules().items():
        if relpath.startswith("backend/idhazh/ledger/"):
            continue
        for name in _reaches(tree):
            asked.setdefault(name, set()).add(relpath)
    return asked


def test_every_name_a_caller_reaches_is_bound_on_the_package() -> None:
    """The completeness check, and the caller demand is the whole of it.

    A name with no caller left need not be bound; a missed repoint, or a reader
    of a name that was deleted or evicted, shows up here as a demanded name the
    package does not answer to. A demanded name that is itself a module under
    `ledger/` resolves by import rather than by the facade.
    """
    submodules = {path.stem for path in PACKAGE.glob("*.py")}
    unbound = {
        name: sorted(where)
        for name, where in sorted(_demanded().items())
        if name not in submodules and not hasattr(ledger, name)
    }
    assert not unbound, (
        f"these names are reached through idhazh.ledger and the package does not bind "
        f"them: {unbound}. Either re-export the name from __init__.py, or repoint the "
        "caller at the module that holds it now."
    )


# --- the day-shard write path composes to the address it always had ----------


@pytest.mark.parametrize(
    "tree", WRITTEN_INTO, ids=[member.value for member in WRITTEN_INTO]
)
def test_a_writers_day_shard_is_the_day_directory_plus_the_writers_name(
    tree: LedgerName, tmp_path: Path
) -> None:
    """The one write path rewritten rather than moved, so nothing else covers it.

    `day_shard_path` used to hold the join in its own body. It now composes the
    day directory from the registry with the writer's name from the filename
    grammar, and this says the two spell the same address - in both forms, for
    every tree a writer files into.
    """
    name = filenames.segment_name(run_id=A_RUN, attempt=AN_ATTEMPT, job=A_JOB, shard=A_SHARD)
    built = ledger.day_shard_path(
        tmp_path, tree, date=A_DAY, run_id=A_RUN, attempt=AN_ATTEMPT, job=A_JOB, shard=A_SHARD
    )
    assert built == paths.path(tmp_path, tree, A_DAY) / name
    assert ledger.day_shard_relpath(
        tree, date=A_DAY, run_id=A_RUN, attempt=AN_ATTEMPT, job=A_JOB, shard=A_SHARD
    ) == f"{paths.relpath(tree, A_DAY)}/{name}"


# --- the package and day_shards stay acyclic ---------------------------------


def test_no_ledger_module_imports_day_shards_at_module_scope() -> None:
    """`day_shards` imports out of this package at its own top, so we cannot.

    Importing the package runs `__init__`, which imports every module below it.
    A module-scope `day_shards` import in any of them would re-enter a package
    that is still half built. The readers that need it import it inside the
    function body, where the package is finished by the time the call runs.
    """
    at_module_scope: list[str] = []
    for path in sorted(PACKAGE.glob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            reaches = (
                isinstance(node, ast.ImportFrom)
                and node.module == "idhazh"
                and any(alias.name == "day_shards" for alias in node.names)
            ) or (
                isinstance(node, ast.Import)
                and any(alias.name == "idhazh.day_shards" for alias in node.names)
            )
            if reaches:
                at_module_scope.append(f"{path.name}:{node.lineno}")

    assert not at_module_scope, (
        f"{at_module_scope} imports day_shards at module scope. Move it inside the "
        "function that calls it: day_shards imports names back out of this package, so "
        "a module-scope import here closes a load-time cycle."
    )


@pytest.mark.parametrize("first", ["idhazh.ledger", "idhazh.day_shards"])
def test_either_module_loads_first_in_a_cold_interpreter(first: str) -> None:
    """Both orders, each in a process that has imported nothing of ours.

    The `day_shards` order is the load-bearing one: it forces that module's own
    top-level import of this package against a package nobody has built yet.

    **It does not replace the check above it.** Measured 2026-09-27 by promoting
    the import on purpose: both orders still loaded, because the facade happens
    to import `csv_file` before `rows`, so the name `day_shards` asks for is
    already bound by the time it asks. Reorder the facade and the same promotion
    raises. The check above is what holds the rule; this one says the package
    loads at all.
    """
    done = _fresh_interpreter(f"import {first}")
    assert done.returncode == 0, f"importing {first} first fails:\n{done.stderr}"


def test_the_facade_does_not_load_pyarrow() -> None:
    """A caller that wants a day's rows must not pay for a columnar reader.

    Checked inside the child, because the parent cannot see what the child
    imported. Green today and load-bearing the day a parquet module joins the
    package: importing a name executes its module whatever `__all__` says, so
    the only mechanism that keeps this true is the facade not binding it.
    """
    done = _fresh_interpreter(
        "import sys\n"
        "from idhazh import ledger\n"
        "loaded = [n for n in sys.modules if n == 'pyarrow' or n.startswith('pyarrow.')]\n"
        "loaded += [n for n in sys.modules if n == 'idhazh.ledger.parquet']\n"
        "sys.exit('the facade loaded ' + ', '.join(loaded) if loaded else 0)\n"
    )
    assert done.returncode == 0, done.stderr


# --- the ledger owns every name under state/ ---------------------------------


def test_only_path_classes_reads_the_writer_name_patterns() -> None:
    """One module outside the package may ask, and none may carry a copy.

    `path_classes` answers whether a committed path has exactly one writer, so
    it has to reach the pattern. Anything else importing it would be a second
    grammar, and a reader that knew only one would walk past the other's files.
    """
    outside: dict[str, list[str]] = {}
    for relpath, tree in _backend_modules().items():
        if relpath.startswith("backend/idhazh/ledger/") or relpath == ASKS_RATHER_THAN_COPIES:
            continue
        reached = [
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "ledger"
            and node.attr in OWNED_PATTERNS
        ]
        reached += [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "idhazh.ledger"
            for alias in node.names
            if alias.name in OWNED_PATTERNS
        ]
        if reached:
            outside[relpath] = sorted(set(reached))

    assert not outside, (
        f"{outside} reaches the writer-name grammar. Ask the ledger what a file is "
        "called rather than reading the pattern: a caller that builds a name will "
        "disagree with the parser the next time either one changes."
    )


def test_nothing_outside_the_package_mints_a_name_under_state() -> None:
    """A producer hands the ledger its rows and its writer identity, not a name.

    A literal file suffix joined to a cell of writer identity is a file name
    being assembled. The one place outside the package that does it is named
    above with the reason; a second fails here rather than arriving unnoticed.
    """
    minting: dict[str, list[str]] = {}
    for relpath, tree in _backend_modules().items():
        if relpath.startswith(("backend/idhazh/ledger/", "backend/tests/")):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.JoinedStr):
                continue
            literal = "".join(
                part.value
                for part in node.values
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
            if not literal.endswith(ROW_SUFFIXES):
                continue
            spelled = {
                reached.id if isinstance(reached, ast.Name) else reached.attr
                for part in node.values
                if isinstance(part, ast.FormattedValue)
                for reached in ast.walk(part.value)
                if isinstance(reached, ast.Name | ast.Attribute)
            }
            if any(cell in spelling for cell in IDENTITY_CELLS for spelling in spelled):
                minting.setdefault(relpath, []).append(f"line {node.lineno}")

    assert set(minting) <= MINTS_ITS_OWN_NAME, (
        f"{sorted(set(minting) - MINTS_ITS_OWN_NAME)} builds a file name out of writer "
        f"identity ({minting}). Hand the rows and the identity to the ledger and let it "
        "name the file, or say here why this tree names its own."
    )


# --- the ledger owns every folder under state/ -------------------------------


def _is_a_ledger_name(node: ast.AST) -> bool:
    """`LedgerName.X` or `LedgerName.X.value`: one ledger's name, written in code."""
    if isinstance(node, ast.Attribute) and node.attr == "value":
        node = node.value
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == LedgerName.__name__
    )


def _hand_joins(tree: ast.Module) -> list[int]:
    """The lines where a ledger's name is joined onto a path by `/` or `joinpath`."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if _is_a_ledger_name(node.left) or _is_a_ledger_name(node.right):
                lines.add(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "joinpath"
            and any(_is_a_ledger_name(argument) for argument in node.args)
        ):
            lines.add(node.lineno)
    return sorted(lines)


def _docstrings(tree: ast.Module) -> set[int]:
    """The node ids of every docstring in one module, which is prose and not a path."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


def _typed_folders(tree: ast.Module, families: frozenset[str]) -> list[int]:
    """The lines where a string spells `state/<family>`, or a path inside one."""
    prose = _docstrings(tree)
    spelled = [f"{ledger.STATE_DIRNAME}/{family}" for family in families]
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in prose:
            continue
        if any(node.value == folder or node.value.startswith(f"{folder}/") for folder in spelled):
            lines.add(node.lineno)
    return sorted(lines)


def _where(found: dict[str, list[int]]) -> str:
    """Every offender as `file:line`, so the failure says where to look."""
    return ", ".join(
        f"{relpath}:{line}" for relpath, lines in sorted(found.items()) for line in lines
    )


def test_nothing_outside_the_package_joins_a_ledgers_name_onto_a_path() -> None:
    """A ledger's folder comes from the registry, so moving the ledger moves every reader.

    A hand join agrees with the registry only until the registry files that
    ledger somewhere else. Then the reader walks a folder that holds nothing,
    which reads as a ledger with no history rather than as a fault. Tests are
    held to it too: a fixture built by a hand join is a fixture in the old place.
    """
    joined: dict[str, list[int]] = {}
    for relpath, tree in _backend_modules().items():
        if relpath.startswith("backend/idhazh/ledger/"):
            continue
        lines = _hand_joins(tree)
        if lines:
            joined[relpath] = lines

    assert not joined, (
        f"{_where(joined)} joins a LedgerName member onto a path by hand. Ask the "
        "registry instead: ledger.tree_root(state_dir, which) for the ledger's folder, "
        "ledger.path(state_dir, which, covers) for one of its files."
    )


def test_no_module_types_a_folder_under_state() -> None:
    """A typed `state/<family>` is a second spelling of where a family's ledgers sit.

    The families are the registry's, so one added tomorrow is covered the day it
    lands. A docstring is prose and is not read. The one module allowed to type
    them is named above with its reason.
    """
    families = ledger.claimed_roots()
    typed: dict[str, list[int]] = {}
    for relpath, tree in _backend_modules().items():
        if not relpath.startswith(READS_STATE) or relpath in TYPES_ITS_OWN_FOLDERS:
            continue
        lines = _typed_folders(tree, families)
        if lines:
            typed[relpath] = lines

    assert not typed, (
        f"{_where(typed)} types a folder under {ledger.STATE_DIRNAME}/ by hand. Build it "
        "from the registry - ledger.tree_relpath(which) for a log line, "
        "ledger.tree_root(state_dir, which) for a read - or say in "
        "TYPES_ITS_OWN_FOLDERS why this module spells its own."
    )


def test_the_folder_checks_can_see_what_they_refuse() -> None:
    """Both walks are only worth running while each still finds what it looks for.

    A walk that has drifted from the syntax it reads passes on everything, so
    each is handed one offender of its own - and the exempt module is checked to
    still type the folders it is exempt for.
    """
    joined = ast.parse(
        "from idhazh.contracts.ledger_name import LedgerName\n"
        "root = state_dir / LedgerName.SUMMARY_QUALITY_EVALS\n"
        "other = state_dir.joinpath(LedgerName.SEEN.value, '2026')\n"
    )
    typed = ast.parse(
        '"""A docstring naming state/summary-quality-evals is prose."""\n'
        'ROOT = "state/summary-quality-evals"\n'
    )

    assert _hand_joins(joined) == [2, 3]
    assert _typed_folders(typed, ledger.claimed_roots()) == [2]
    for exempt in TYPES_ITS_OWN_FOLDERS:
        assert _typed_folders(_backend_modules()[exempt], ledger.claimed_roots()), (
            f"{exempt} no longer types a folder under state/, so its exemption is stale"
        )
