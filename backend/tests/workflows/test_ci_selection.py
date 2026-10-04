"""Which checks does a change buy, and which does it never consult a list to skip?"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest
from conftest import REPO_ROOT

from ._harness import (
    GITHUB_DIR,
    _artifact_upload,
    _git,
    _isolated_env,
    _job,
    _load_workflows,
    _mapping,
    _script,
    _step,
    _steps,
    _write,
)

pytestmark = pytest.mark.workflow

#: The selector is a TypeScript file node runs directly, so a host without node cannot
#: answer for it. `ci.yml` installs one in both jobs that read it.
requires_node: Final = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="no node on this host to execute frontend/scripts/test-scope.ts",
)

#: What the `scope` job runs, as the workflow spells it. A copy of the path here
#: would keep agreeing with itself after the workflow moved.
SELECTOR: Final = REPO_ROOT / "frontend" / "scripts" / "test-scope.ts"

#: The directory the gate set no longer has a check for.
RETIRED_SCRIPTS_DIR: Final = GITHUB_DIR / "scripts"


def test_the_platform_runs_no_shell_script_directory() -> None:
    """Shell under `.github/` is a language the gate set stopped covering.

    `ruff` and `mypy` stop at Python, so a file here needed a linter of its own,
    a bash-on-the-host skip in every test that drove it, and a word-splitting
    rule that forbade a space in any path it was handed. All three went with the
    last script on 2026-09-23, so a file arriving here now is shipped, executed
    by a runner and checked by nothing.
    """
    assert not RETIRED_SCRIPTS_DIR.exists(), (
        f"{RETIRED_SCRIPTS_DIR.relative_to(REPO_ROOT).as_posix()} came back, and nothing "
        "lints or drives what is in it. Write the program in Python under "
        "backend/utilities/ and call it from the step, or reopen the directory as a "
        "Level 3 design question and bring its linter back with it "
        "(docs/reference/repository-layout.md)."
    )


def test_the_selection_step_runs_what_this_module_drives() -> None:
    """The step and the harness below have to name the same program, or the
    tests drive something the run does not.
    """
    workflow = _load_workflows()["ci.yml"]
    decide = _script(_step(workflow, "scope", "id", "decide"), "ci.yml/scope/decide")
    assert SELECTOR.relative_to(REPO_ROOT).as_posix() in decide
    assert decide.split()[0] == "node", "the step calls node itself, with no script between"
    assert '>> "$GITHUB_OUTPUT"' in decide, "a job reads these lines back as step outputs"


def test_the_robots_job_runs_the_module_the_selector_keys_on() -> None:
    """The selector buys `robots` only when it selects the module this job runs,
    so the two must name the same file."""
    workflow = _load_workflows()["ci.yml"]
    assert _job(workflow, "robots")["if"] == "needs.scope.outputs.robots == 'true'"
    outputs = _mapping(_job(workflow, "scope").get("outputs"), "ci.yml scope outputs")
    assert outputs["robots"] == "${{ steps.decide.outputs.robots }}"
    run = _step(workflow, "robots", "name", "The robots fixtures, on the newest supported interpreter")
    module = str(run["run"]).split()[-1]
    assert f"const ROBOTS_TESTS = '{module}';" in SELECTOR.read_text(encoding="utf-8")


#: What the shipped script has to answer through a real git history.
#:
#: The truth table itself is in `frontend/scripts/tests/test-scope.test.mjs`,
#: where a case is a function call. Here a case is a temporary repository, two
#: commits and a shell, and twenty-four of them cost 168 s of this module's
#: 585 s on an i7-1265U, 2026-09-05 - for an answer the pure function already
#: gives. These four are the plumbing rather than the policy: one change that
#: buys everything, one that buys the browser half without the console or its
#: panel pictures, one that re-reads the archive because it moved the shape a
#: day is read through, and one that buys nothing.
BROWSER_SCOPE_CASES: Final = (
    ("frontend/src/routes/console/+page.svelte", True, True, True, True, False, False, False),
    ("frontend/src/routes/[date]/+page.svelte", True, True, False, False, False, False, True),
    ("config/idhazh.json", True, True, False, False, True, True, True),
    ("docs/reference/pipeline-cost.md", False, False, False, False, False, False, False),
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
            test_step = _step(
                workflow, "gates", "name", "Tests, including the five injection canaries"
            )
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
    ("changed", "browser", "code", "console", "panels", "robots", "validate_all", "model_absent"),
    BROWSER_SCOPE_CASES,
)
def test_the_browser_half_is_skipped_only_for_a_change_that_cannot_reach_a_page(
    changed: str,
    browser: bool,
    code: bool,
    console: bool,
    panels: bool,
    robots: bool,
    validate_all: bool,
    model_absent: bool,
    tmp_path: Path,
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
        "model_absent": str(model_absent).lower(),
        "console": str(console).lower(),
        "panels": str(panels).lower(),
        "robots": str(robots).lower(),
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
        "model_absent": "true",
        "console": "true",
        "panels": "true",
        "robots": "true",
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
        "model_absent": "false",
        "console": "false",
        "panels": "false",
        "robots": "false",
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


def test_panel_pictures_are_explicit_but_sufficiency_checks_still_follow_selection() -> None:
    """Routine runs keep panel assertions; a manual review asks for pictures."""
    workflow = _load_workflows()["ci.yml"]
    outputs = _mapping(_job(workflow, "scope").get("outputs"), "ci.yml scope outputs")
    assert outputs["panels"] == "${{ steps.decide.outputs.panels }}"

    suite = _step(workflow, "browser", "name", "Browser suite - canaries and retrieval")
    env = _mapping(suite.get("env"), "the browser suite's env")
    assert env["SKIP_PANELS_SUITE"] == "${{ needs.scope.outputs.panels == 'false' }}"
    assert env["SKIP_PANEL_CAPTURES"] == "${{ inputs.panel_captures != true }}"

    upload = _artifact_upload(workflow, "browser", "panel-captures")
    condition = str(upload.get("if", ""))
    assert "!cancelled()" in condition and "inputs.panel_captures == true" in condition
    settings = _mapping(upload.get("with"), "the panel-captures upload")
    assert settings["path"] == "frontend/test-results/panels/"
    assert settings["if-no-files-found"] == "error"
    assert _steps(workflow, "browser").index(upload) > _steps(workflow, "browser").index(suite), (
        "the upload keeps what the suite drew, so it runs after the suite"
    )

    traces = _mapping(
        _artifact_upload(workflow, "browser", "playwright-traces").get("with"), "the traces upload"
    )
    assert "!frontend/test-results/panels/" in str(traces["path"]).split(), (
        "a red run must not upload every panel picture a second time inside the traces"
    )


def test_model_absent_build_and_browser_timings_are_wired_to_their_inputs() -> None:
    workflow = _load_workflows()["ci.yml"]
    outputs = _mapping(_job(workflow, "scope").get("outputs"), "ci.yml scope outputs")
    assert outputs["model_absent"] == "${{ steps.decide.outputs.model_absent }}"
    absent = _step(workflow, "site", "name", "Model-absent gate - the digest does not depend on any of it")
    assert absent["if"] == "needs.scope.outputs.model_absent == 'true'"
    suite = _step(workflow, "browser", "name", "Browser suite - canaries and retrieval")
    assert "--reporter=github,json" in str(suite["run"])
    env = _mapping(suite.get("env"), "browser suite env")
    report = _artifact_upload(workflow, "browser", "browser-results")
    settings = _mapping(report.get("with"), "browser results upload")
    assert settings["path"] == f"frontend/{env['PLAYWRIGHT_JSON_OUTPUT_NAME']}"
    assert report["if"] == "${{ !cancelled() }}"
    assert settings["if-no-files-found"] == "error"
