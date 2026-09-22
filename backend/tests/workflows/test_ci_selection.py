"""Which checks does a change buy, and which does it never consult a list to skip?"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest
from conftest import REPO_ROOT, read_text

from ._harness import (
    SCRIPTS_DIR,
    SHELLCHECK_COMMAND,
    SHELLCHECK_STEP,
    SHIPPED_SCRIPTS,
    _git,
    _isolated_env,
    _load_workflows,
    _mapping,
    _script,
    _step,
    _steps,
    _write,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

#: The selector is a TypeScript file node runs directly, so a host without node cannot
#: answer for it. `ci.yml` installs one in both jobs that read it.
requires_node: Final = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="no node on this host to execute frontend/scripts/test-scope.ts",
)

#: What the `scope` job runs, as the workflow spells it. A copy of the path here
#: would keep agreeing with itself after the workflow moved.
SELECTOR: Final = REPO_ROOT / "frontend" / "scripts" / "test-scope.ts"

#: What the `docs` job runs.
CHANGED_DOCS: Final = REPO_ROOT / "backend" / "utilities" / "changed_docs.py"


def test_the_gates_job_lints_the_shell_it_ships() -> None:
    """`ruff` and `mypy` stop at Python. The one script under .github/scripts/
    is the retry loop both daily commit steps run, and a bug in it costs a whole
    day's digest - so it gets a linter of its own, from the same manifest that
    pins the other two.
    """
    steps = _steps(_load_workflows()["ci.yml"], "gates")
    step = _step(_load_workflows()["ci.yml"], "gates", "name", SHELLCHECK_STEP)
    assert _script(step, f"ci.yml/gates/{SHELLCHECK_STEP}").strip() == SHELLCHECK_COMMAND

    names = [item.get("name") for item in steps]
    assert names.index("Install") < names.index(SHELLCHECK_STEP), (
        "shellcheck arrives as a dev dependency, so the install has to run first"
    )
    manifest = tomllib.loads(read_text(REPO_ROOT / "pyproject.toml"))
    dev = manifest["project"]["optional-dependencies"]["dev"]
    assert any(requirement.startswith("shellcheck-py") for requirement in dev), (
        "the linter is pinned by the manifest, not fetched by the step"
    )
    assert list(SCRIPTS_DIR.glob("*.sh")), "the gate reads a glob, so it needs something to read"


def test_the_shell_the_gate_lints_is_the_shell_this_repository_declared() -> None:
    """Nothing lands a shell script here without somebody choosing to.

    The linter above reads a glob, so a `.sh` file that arrives with no owner is
    linted, shipped and invisible - which is how one arrived. The inventory is
    read both ways: a file nobody declared is the new script, and a declared
    name with no file is a deletion somebody half finished. Only a person
    editing this tree can turn either red.
    """
    present = {path.name for path in SCRIPTS_DIR.glob("*.sh")}
    declared = set(SHIPPED_SCRIPTS)
    undeclared = sorted(present - declared)
    missing = sorted(declared - present)
    assert not undeclared, (
        "a new .sh file under .github/scripts/ is a Level 3 design question, not a "
        f"convenience. Nothing declares: {', '.join(undeclared)}"
    )
    assert not missing, (
        "SHIPPED_SCRIPTS names a script that is gone, so the deletion left the list "
        f"behind: {', '.join(missing)}"
    )


def test_the_two_selection_steps_run_what_this_module_drives() -> None:
    """The step and the harness below have to name the same program.

    Both steps used to name a shell script, which is what kept them in step with
    the tests. The script is gone, so the agreement is checked here instead: a
    workflow that moved either program leaves the tests driving something the
    run does not.
    """
    workflow = _load_workflows()["ci.yml"]
    decide = _script(_step(workflow, "scope", "id", "decide"), "ci.yml/scope/decide")
    changed = _script(_step(workflow, "docs", "id", "changed"), "ci.yml/docs/changed")
    assert SELECTOR.relative_to(REPO_ROOT).as_posix() in decide
    assert decide.split()[0] == "node", "the step calls node itself, with no script between"
    assert CHANGED_DOCS.relative_to(REPO_ROOT).as_posix() in changed
    for body in (decide, changed):
        assert '>> "$GITHUB_OUTPUT"' in body, "a job reads these lines back as step outputs"


#: What the shipped script has to answer through a real git history.
#:
#: The truth table itself is in `frontend/scripts/tests/test-scope.test.mjs`,
#: where a case is a function call. Here a case is a temporary repository, two
#: commits and a shell, and twenty-four of them cost 168 s of this module's
#: 585 s on an i7-1265U, 2026-09-05 - for an answer the pure function already
#: gives. These four are the plumbing rather than the policy: one change that
#: buys everything, one that buys the browser half without the console, one that
#: re-reads the archive because it moved the shape a day is read through, and
#: one that buys nothing.
BROWSER_SCOPE_CASES: Final = (
    ("frontend/src/routes/console/+page.svelte", True, True, True, False),
    ("frontend/src/routes/[date]/+page.svelte", True, True, False, False),
    ("config/idhazh.json", True, True, False, True),
    ("docs/reference/pipeline-cost.md", False, False, False, False),
)

def test_the_selector_tests_use_the_same_node_as_the_ci_selector() -> None:
    workflow = _load_workflows()["ci.yml"]
    versions: dict[str, object] = {}
    for job in ("scope", "gates"):
        steps = _steps(workflow, job)
        node_steps = [
            step for step in steps
            if str(step.get("uses", "")).startswith("actions/setup-node@")
        ]
        assert len(node_steps) == 1, f"{job} must declare the selector's Node runtime"
        settings = node_steps[0].get("with")
        assert isinstance(settings, dict)
        versions[job] = settings.get("node-version")
        if job == "gates":
            test_step = next(step for step in steps if step.get("run") == "pytest")
            assert steps.index(node_steps[0]) < steps.index(test_step)
    assert versions["scope"] is not None
    assert versions["gates"] == versions["scope"]


def _two_commits(
    tmp_path: Path, changed: Sequence[str]
) -> tuple[Path, dict[str, str], str, str]:
    """A real repository, a seed commit and a commit changing each named path."""
    env = _isolated_env(tmp_path)
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, env, "init", "--quiet", "--initial-branch=main")
    _write(root / "seed.txt", "seed\n")
    _git(root, env, "add", "seed.txt")
    _git(root, env, "commit", "--quiet", "-m", "seed")
    base = _git(root, env, "rev-parse", "HEAD").strip()
    for name in changed:
        _write(root / name, "changed\n")
        _git(root, env, "add", name)
    _git(root, env, "commit", "--quiet", "-m", "change")
    return root, env, base, _git(root, env, "rev-parse", "HEAD").strip()


def _outputs(completed: subprocess.CompletedProcess[str]) -> dict[str, str]:
    """The `KEY=value` lines a step would append to `$GITHUB_OUTPUT`."""
    assert completed.returncode == 0, completed.stderr
    return dict(
        line.split("=", 1) for line in completed.stdout.strip().splitlines() if "=" in line
    )


def _browser_scope(
    tmp_path: Path, changed: Sequence[str], event: str = "pull_request"
) -> dict[str, str]:
    """Run the shipped selector over a real two-commit history and read its answer."""
    root, env, base, head = _two_commits(tmp_path, changed)
    return _outputs(
        subprocess.run(
            ["node", SELECTOR.as_posix(), "--ci"],
            cwd=root,
            env={**env, "EVENT": event, "BASE": base, "HEAD": head},
            capture_output=True,
            text=True,
            check=False,
        )
    )


@requires_node
@pytest.mark.parametrize(
    ("changed", "browser", "code", "console", "validate_all"), BROWSER_SCOPE_CASES
)
def test_the_browser_half_is_skipped_only_for_a_change_that_cannot_reach_a_page(
    changed: str, browser: bool, code: bool, console: bool, validate_all: bool, tmp_path: Path
) -> None:
    """The filter is executed, not read.

    A copy of the pattern in this file would agree with itself forever while the
    shipped selector skipped a change that breaks a published page. So the test
    builds a real two-commit history, runs the command the workflow runs, and
    reads the lines it writes to `$GITHUB_OUTPUT`.

    What is under test here is the plumbing - the invocation, the git range and
    the output format. Which paths select which groups is decided by a pure
    function and checked case by case in
    `frontend/scripts/tests/test-scope.test.mjs`.
    """
    assert _browser_scope(tmp_path, [changed]) == {
        "browser": str(browser).lower(),
        "code": str(code).lower(),
        "console": str(console).lower(),
        "validate_all": str(validate_all).lower(),
    }


@requires_node
def test_one_reaching_path_in_a_mixed_change_still_buys_the_browser_suite(
    tmp_path: Path,
) -> None:
    """A pull request is a set, not one file. Docs beside a frontend edit is the
    ordinary shape of this repo's changes, and the frontend edit decides.
    """
    mixed = ["docs/reference/pipeline-cost.md", "frontend/src/routes/+page.svelte"]
    assert _browser_scope(tmp_path, mixed)["browser"] == "true"


@requires_node
def test_a_push_carrying_code_still_never_consults_the_list(tmp_path: Path) -> None:
    """The group each path selects is a wager that nobody forgot a path. The
    merge commit is where that wager is settled, so a push that carries any code
    buys everything - a pull request the list was wrong about reddens `main`
    within minutes instead of reaching a reader.
    """
    assert _browser_scope(
        tmp_path, ["docs/x.md", "backend/idhazh/discover.py"], event="push"
    ) == {
        "browser": "true",
        "code": "true",
        "console": "true",
        "validate_all": "true",
    }


@requires_node
def test_a_push_carrying_no_code_starts_no_code_job(tmp_path: Path) -> None:
    """The one question a push does read the paths for.

    A changed sentence cannot break an application check, so the merge that
    carries it should not spend the suite proving that. This is safe where the
    wager above is not, because the documentation branch is a closed list of
    prefixes: a path nobody classified falls to full coverage instead.
    """
    assert _browser_scope(tmp_path, ["docs/x.md"], event="push") == {
        "browser": "false",
        "code": "false",
        "console": "false",
        "validate_all": "false",
    }


def test_a_trunk_push_is_never_cancelled_by_the_next_one() -> None:
    """The rule that makes the `scope` job safe on a push.

    `scope` answers from each push's own changed paths, so a push carrying only
    documentation correctly checks nothing. That is only sound while it cannot
    cancel a push that carried code: the surviving run checks nothing because
    nothing in ITS range needed checking, and the code reaches the trunk with no
    verdict on the trunk. Measured 2026-09-12, before this was fixed: two pushes
    carrying 14 code files between them were cancelled by a third that changed
    one plan-doc.
    """
    concurrency = _mapping(_load_workflows()["ci.yml"]["concurrency"], "ci.yml concurrency")
    cancel = str(concurrency["cancel-in-progress"])
    assert cancel != "true", "a push to the trunk has to keep the run it started"
    assert "pull_request" in cancel, (
        "cancelling is still right on a pull request, where a newer commit "
        "supersedes the older one and its verdict is worth nothing"
    )
    assert "github.sha" in str(concurrency["group"]), (
        "a push groups by its own commit, so it is neither cancelled by nor "
        "queued behind the next push"
    )


def _changed_docs(root: Path, env: dict[str, str], base: str, head: str) -> dict[str, str]:
    """Run the docs job's step in a real repository and read the lines it writes."""
    return _outputs(
        subprocess.run(
            [sys.executable, CHANGED_DOCS.as_posix()],
            cwd=root,
            env={**env, "BASE": base, "HEAD": head},
            capture_output=True,
            text=True,
            check=False,
        )
    )


#: Every base the docs job can be handed that does not start a range. A dispatch
#: names none at all, a branch's first push names the all-zero id, and a
#: force-push leaves a base this clone no longer holds.
UNRESOLVABLE_BASES: Final = (
    ("no-base-at-all", ""),
    ("no-earlier-tip", "0" * 40),
    ("not-in-this-clone", "b" * 40),
)


@pytest.mark.parametrize(
    "base", [base for _, base in UNRESOLVABLE_BASES], ids=[name for name, _ in UNRESOLVABLE_BASES]
)
def test_a_range_the_clone_cannot_resolve_answers_no_pages(base: str, tmp_path: Path) -> None:
    """The docs job gates nothing and can fail nothing, so neither can this.

    Asking git for a range it does not hold is a failure rather than an answer,
    and a failure here would redden a check over a number nobody set a threshold
    on. Each case is driven rather than read: the step is run, and its exit code
    is what `_outputs` asserts before the answer is compared.
    """
    root, env, _, head = _two_commits(tmp_path, ["docs/x.md"])
    assert _changed_docs(root, env, base, head) == {"any": "false"}


def test_a_head_the_event_never_named_answers_no_pages(tmp_path: Path) -> None:
    """The other half of a range. A dispatch names neither end."""
    root, env, base, _ = _two_commits(tmp_path, ["docs/x.md"])
    assert _changed_docs(root, env, base, "") == {"any": "false"}


def test_a_change_that_touched_a_page_names_every_page_it_touched(tmp_path: Path) -> None:
    """One line per answer, and the paths reach `doc_load.py --changed` as words."""
    root, env, base, head = _two_commits(
        tmp_path, ["docs/a.md", "docs/deep/b.md", "backend/idhazh/discover.py"]
    )
    assert _changed_docs(root, env, base, head) == {
        "any": "true",
        "paths": "docs/a.md docs/deep/b.md",
    }


def test_a_change_that_touched_no_page_answers_no_pages(tmp_path: Path) -> None:
    """A resolvable range is still no reason to start the reader below it."""
    root, env, base, head = _two_commits(tmp_path, ["backend/idhazh/discover.py"])
    assert _changed_docs(root, env, base, head) == {"any": "false"}


def test_a_page_the_change_deleted_is_left_out(tmp_path: Path) -> None:
    """`doc_load.py` reads each page it is given, so a deleted one is not one."""
    root, env, base, _ = _two_commits(tmp_path, ["docs/gone.md", "docs/kept.md"])
    _git(root, env, "rm", "--quiet", "docs/gone.md")
    _git(root, env, "commit", "--quiet", "-m", "delete")
    head = _git(root, env, "rev-parse", "HEAD").strip()
    assert _changed_docs(root, env, base, head) == {"any": "true", "paths": "docs/kept.md"}
