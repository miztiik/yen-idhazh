"""What is validated, built and gated before a day is published?"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Final, cast

import pytest

from ._harness import (
    COMMIT_SCRIPT_CALL,
    PUBLISHING_SITE_JOBS,
    STATUS_PAGE,
    STATUS_PAGE_GUARD,
    STATUS_PAGE_JOB,
    STATUS_PAGE_WRITE,
    VALIDATE_DAYS_CALL,
    VALIDATE_DAYS_JOBS,
    _bash,
    _git,
    _isolated_env,
    _job,
    _load_workflows,
    _mapping,
    _normalize_condition,
    _script,
    _step,
    _steps,
    _triggers,
    _write,
    requires_bash,
)

pytestmark = pytest.mark.workflow


@pytest.mark.parametrize(("filename", "job_name"), VALIDATE_DAYS_JOBS)
def test_every_committed_day_is_validated_where_the_build_stopped_doing_it(
    filename: str, job_name: str
) -> None:
    """The guard that replaced the one the migration removed.

    A reading document carried every story its day published until 2026-09-01,
    so a story the contract refused failed `npm run build` and could not reach a
    reader. It carries a seed now and the browser fetches the rest, so the build
    never opens the stories past the seed. Nothing else does either, unless this
    step is in the job.

    It takes no path. There is exactly one committed digest tree, so unlike
    `--site-tree` a default here cannot name the wrong one.
    """
    steps = _steps(_load_workflows()[filename], job_name)
    calls = [
        index
        for index, step in enumerate(steps)
        if tuple(shlex.split(str(step.get("run", "")))[:4]) == VALIDATE_DAYS_CALL
    ]
    assert calls, f"{filename}/{job_name} never validates the committed days"
    assert "continue-on-error" not in steps[calls[0]], (
        "a day that fails its contract is a day no reader can read; the step still fails"
    )


def test_the_daily_publish_validates_the_day_it_wrote_and_not_every_other_one() -> None:
    """A published day is frozen, so re-opening all of them buys nothing.

    Measured 2026-09-05 on an i7-1265U: 16 committed days took 6.6 s to 7.1 s,
    about 0.27 s a day on top of a fixed start. The pipeline publishes five
    times a day, so a year of days would spend roughly eight minutes a day
    re-deriving an answer settled when each of those days was written
    (`CLAUDE.md` Guardrail #12).

    `backfill.yml` is deliberately not here: it repairs days it chooses, so the
    day it has to check is not one this file can name.
    """
    steps = _steps(_load_workflows()["digest.yml"], "assemble")
    call = next(
        shlex.split(str(step.get("run", "")))
        for step in steps
        if tuple(shlex.split(str(step.get("run", "")))[:4]) == VALIDATE_DAYS_CALL
    )
    assert "--day" in call, "the daily publish still opens every committed day"
    named = call[call.index("--day") + 1]
    assert "needs.plan.outputs.date" in named, (
        f"the day is {named!r}, which is not the day this run was planned for"
    )


def test_the_whole_tree_is_re_read_only_when_the_shape_it_is_read_through_moves() -> None:
    """The other half: `ci.yml` pays the full price on the change that earns it.

    A contract, schema, config or harness edit can invalidate a day nobody
    touched, and a merge to `main` always counts. Anything else leaves every
    committed day exactly as valid as it was when it was pushed.
    """
    workflow = _load_workflows()["ci.yml"]
    # `needs:` is a bare string for one dependency and a list for several.
    declared = _job(workflow, "gates").get("needs")
    waits_for = [declared] if isinstance(declared, str) else declared
    assert isinstance(waits_for, list) and "scope" in waits_for, (
        "gates cannot read the selector's answer without waiting for it"
    )
    outputs = _job(workflow, "scope").get("outputs")
    assert isinstance(outputs, dict) and "validate_all" in outputs, (
        "the selector's answer is not published for another job to read"
    )
    step = next(
        step
        for step in _steps(workflow, "gates")
        if tuple(shlex.split(str(step.get("run", "")))[:4]) == VALIDATE_DAYS_CALL
    )
    assert "validate_all" in str(step.get("if", "")), (
        "the full pass over the archive runs on every change, whatever moved"
    )


@pytest.mark.parametrize(("filename", "job_name", "commit_step"), PUBLISHING_SITE_JOBS)
def test_the_day_is_validated_before_it_is_published(
    filename: str, job_name: str, commit_step: str
) -> None:
    """Same severity as the build, so the same side of the commit.

    A day whose stories no reader's browser can parse must not publish, and
    finding that out after the push costs the reader the day either way.
    """
    steps = _steps(_load_workflows()[filename], job_name)
    names = [step.get("name") for step in steps]
    validated = next(
        index
        for index, step in enumerate(steps)
        if tuple(shlex.split(str(step.get("run", "")))[:4]) == VALIDATE_DAYS_CALL
    )
    assert validated < names.index(commit_step), (
        "a day the contract refuses must never reach a reader"
    )


@pytest.mark.parametrize(("filename", "job_name", "commit_step"), PUBLISHING_SITE_JOBS)
def test_the_build_gates_the_publish_and_the_weight_gate_runs_after_it(
    filename: str, job_name: str, commit_step: str
) -> None:
    """Two severities, and only one of them may cost a reader the day.

    `npm run build` compiles every route and prerenders six of them, so a route
    that cannot build, and one of those six that cannot render, fails here
    instead of in a reader's browser. That day is broken and must not publish,
    so the build runs before the commit. The two dated reading routes render in
    the browser and the build no longer answers for them; `idhazh validate-days`
    sits beside it at the same severity and for the same reason - it is what
    opens the stories a seeded document never serialises.

    `npm run bundle-gate` holds each capped page under the ceiling somebody
    priced for it. A page over it still reads correctly - what grew is the
    document, not the meaning - and stopping the publish for that throws away
    the day and the two to three hours that built it. So it runs after the
    commit, and stays fatal: the job goes red until somebody re-prices the
    ceiling.
    """
    steps = _steps(_load_workflows()[filename], job_name)
    names = [step.get("name") for step in steps]

    built = next(
        index for index, step in enumerate(steps) if "npm run build" in str(step.get("run", ""))
    )
    gate = next(
        index
        for index, step in enumerate(steps)
        if "npm run bundle-gate" in str(step.get("run", ""))
    )
    commit = names.index(commit_step)

    before_build = steps[:built]
    assert any(
        str(step.get("uses", "")).startswith("actions/setup-node@") for step in before_build
    ), "node must be set up before the site is built"
    assert any(
        "npm ci" in str(step.get("run", "")) for step in before_build
    ), "the site must be installed before it is built"
    assert built < commit, "a route that cannot render must never reach a reader"
    assert commit < gate, "a page over its ceiling loses the ceiling, not the day"
    assert "continue-on-error" not in steps[gate], "the gate publishes the day; it still fails"


@pytest.mark.parametrize(("filename", "job_name", "commit_step"), PUBLISHING_SITE_JOBS)
def test_the_weight_gate_reads_a_build_of_the_tree_that_was_pushed(
    filename: str, job_name: str, commit_step: str
) -> None:
    """One tree's pages may not be weighed against another tree's ceilings.

    `commit-and-push.sh` rebases when the push loses a race, and that brings
    main's tip into the checkout - its frontend source and its
    `config/idhazh.json` ceilings with it. `frontend/build` still holds the
    build made before the commit, so the gate would read limits the build it
    measures never saw. Run 33270983446 failed exactly that way, on a day that
    had already published and deployed.

    So a build sits after every commit step in the job, and the gate reads that
    one. `npm ci` is deliberately not repeated with it: the lockfile moves far
    more rarely than the source, and a reinstall would delete `node_modules` on
    every run to cover the rarer of the two.

    And it is conditional, because a push that landed first try left the tree
    the first build already read. The condition has to name every commit step
    that runs before it: `assemble` commits twice, the second stages
    `frontend/public/telemetry`, and the console pages read that - so a
    condition naming only the day's commit would skip the rebuild on the other
    one and put run 33270983446 straight back.
    """
    steps = _steps(_load_workflows()[filename], job_name)
    names = [step.get("name") for step in steps]
    builds = [
        index for index, step in enumerate(steps) if "npm run build" in str(step.get("run", ""))
    ]
    commits = [
        index
        for index, step in enumerate(steps)
        if COMMIT_SCRIPT_CALL[1] in str(step.get("run", ""))
    ]
    gate = next(
        index
        for index, step in enumerate(steps)
        if "npm run bundle-gate" in str(step.get("run", ""))
    )

    assert names.index(commit_step) in commits, "the publishing step runs the shared commit script"
    rebuilt = [index for index in builds if index > max(commits)]
    assert rebuilt, "the gate must read a build made after the last commit, not before it"
    assert max(rebuilt) < gate, "the rebuild is what the gate reads, so it comes first"
    assert "continue-on-error" not in steps[rebuilt[0]], (
        "a rebuild that fails quietly leaves the gate reading the stale build again"
    )

    assert "if" in steps[rebuilt[0]], (
        "an unconditional rebuild pays for the race on every run, raced or not"
    )
    condition = _normalize_condition(
        steps[rebuilt[0]].get("if"), f"{filename}/{job_name} rebuild condition"
    )
    for index in commits:
        # Either the step's own `id`, so the condition reads what it reported,
        # or the condition that decides whether it commits at all - which is how
        # a job with one commit step and a dispatch switch says the same thing.
        named = str(steps[index].get("id") or steps[index].get("if") or "")
        assert named and named in condition, (
            f"{steps[index].get('name')} can rewrite the checkout, so the rebuild's "
            "condition has to name it"
        )


#: Every job that builds the site, and so every job that can grow it past the cap.
SITE_WEIGHT_JOBS: Final = (
    ("ci.yml", "site"),
    ("digest.yml", "assemble"),
    ("backfill.yml", "backfill"),
)

SITE_WEIGHT_CALL: Final = ("python", "-m", "idhazh", "site-weight")


def _published_tree() -> str:
    """The directory the Pages deploy uploads, read off the deploy itself."""
    step = next(
        item
        for item in _steps(_load_workflows()["pages.yml"], "build")
        if str(item.get("uses", "")).startswith("actions/upload-pages-artifact@")
    )
    with_block = _mapping(step.get("with"), "pages.yml upload-pages-artifact with")
    path = with_block.get("path")
    assert isinstance(path, str), "the deploy must upload one named directory"
    return path.rstrip("/")


def _site_weight_step(workflow: dict[str, object], job_name: str) -> tuple[int, list[str]]:
    """Where the site-weight call sits in a job, and the argv it runs."""
    for index, step in enumerate(_steps(workflow, job_name)):
        argv = shlex.split(str(step.get("run", "")))
        if tuple(argv[:4]) == SITE_WEIGHT_CALL:
            directory = str(step.get("working-directory", "")).strip("/")
            return index, [directory, *argv]
    raise AssertionError(f"{job_name} builds the site and never measures it")


@pytest.mark.parametrize(("filename", "job_name"), SITE_WEIGHT_JOBS)
def test_the_site_gate_measures_the_tree_the_deploy_uploads(filename: str, job_name: str) -> None:
    """The 1 GB cap is a property of the published bundle, so that is what gets
    measured - the same directory `pages.yml` hands to the deploy.

    This is the defect the row fixed. The alarm used to measure
    `frontend/public/digest`, which is the pipeline's committed output and not
    the site: 7,027,075 bytes against 128,064,853 on 2026-08-27, eighteen times
    apart and growing at different rates. An alarm at 800 MB on that tree could
    not have fired before the site was already six times past the cap.

    Deriving the expected path from the deploy is what makes the fix structural.
    Point the gate back at `frontend/public/digest`, or anywhere else, and the
    two stop agreeing here.
    """
    workflow = _load_workflows()[filename]
    index, argv = _site_weight_step(workflow, job_name)
    directory, *call = argv

    assert "--site-tree" in call, "the tree is named at the call site, never defaulted"
    measured = f"{directory}/{call[call.index('--site-tree') + 1]}".strip("/")
    assert measured == _published_tree(), (
        f"{filename}/{job_name} measures {measured!r}; the deploy uploads "
        f"{_published_tree()!r}. One of the two is measuring the wrong tree."
    )
    assert not measured.startswith("frontend/public"), (
        "frontend/public is what the pipeline writes, not what a reader downloads"
    )

    built = next(
        position
        for position, step in enumerate(_steps(workflow, job_name))
        if "npm run build" in str(step.get("run", ""))
    )
    assert built < index, "the tree does not exist until the site is built"


def test_ci_keeps_its_push_boundary_and_pages_publishes_only_a_verdict() -> None:
    workflows = _load_workflows()

    ci_push = cast(dict[str, object], _triggers(workflows["ci.yml"])["push"])
    assert set(ci_push) == {"branches", "paths-ignore"}
    assert ci_push["branches"] == ["main"]
    # The `status-page` job's loop guard, and the reason it is a trigger filter
    # rather than a job condition or a `[skip ci]` marker: a push holding only
    # this file starts no run at all, whoever pushed it, and every other gate on
    # that commit still runs.
    assert ci_push["paths-ignore"] == [STATUS_PAGE]

    pages = _triggers(workflows["pages.yml"])
    assert "push" not in pages, (
        "a push reaches this workflow at the same moment it reaches CI, so "
        "publishing on one publishes before anything has judged the commit"
    )
    assert pages["workflow_run"] == {
        "workflows": ["CI", "Content refresh"],
        "types": ["completed"],
    }

    jobs = _mapping(workflows["pages.yml"]["jobs"], "pages.yml jobs")
    decide = _mapping(jobs["decide"], "pages.yml decide job")
    condition = str(decide["if"])
    assert "conclusion == 'success'" in condition, (
        "a workflow_run trigger cannot be filtered by conclusion, so a CI run "
        "that failed has to be refused by the job that reads it"
    )
    assert "!= 'CI'" in condition, (
        "the daily path is deliberately not gated on conclusion: the job that "
        "writes a day validates it before committing, so a sibling job failing "
        "afterwards must not hold a good day back"
    )
    checkout = next(
        step
        for step in _steps(workflows["pages.yml"], "build")
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    pinned = str(_mapping(checkout["with"], "pages.yml build checkout").get("ref"))
    assert "needs.decide.outputs.ref" in pinned, (
        "what deploys is the commit that was verified, not the tip minutes later"
    )


def test_the_plan_queue_has_exactly_one_writer() -> None:
    """One job regenerates the page, and a pull request may not carry it.

    Two assertions, because either alone leaves the conflict in place: a second
    writer anywhere puts two branches back on the same lines, and a gate that
    does not refuse the file lets a branch bring its own copy.
    """
    workflow = _load_workflows()["ci.yml"]

    writers = [
        f"{job_name}/{step.get('name')}"
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if STATUS_PAGE_WRITE in str(step.get("run", ""))
    ]
    assert len(writers) == 1, f"{STATUS_PAGE} has one writer; these regenerate it: {writers}"
    assert writers[0].startswith(f"{STATUS_PAGE_JOB}/")

    guard = _step(workflow, "gates", "name", STATUS_PAGE_GUARD)
    assert _normalize_condition(guard.get("if"), "plan queue guard condition") == (
        "github.event_name == 'pull_request'"
    )
    script = _script(guard, f"ci.yml/gates/{STATUS_PAGE_GUARD}")
    assert STATUS_PAGE in script
    # A pull request is checked out as a merge commit whose first parent is the
    # base branch, so this range is what the branch changes - and reading it
    # needs the one extra commit below rather than a fetch over the network.
    assert "HEAD^1 HEAD" in script
    checkout = next(
        step
        for step in _steps(workflow, "gates")
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert _mapping(checkout.get("with"), "gates checkout 'with'").get("fetch-depth") == "2"


def test_the_status_page_job_writes_only_after_a_merge() -> None:
    workflow = _load_workflows()["ci.yml"]
    job = _job(workflow, STATUS_PAGE_JOB)

    assert _normalize_condition(job.get("if"), "status-page condition") == (
        "github.event_name == 'push'"
    )
    assert _mapping(workflow.get("permissions"), "ci.yml permissions") == {
        "contents": "read"
    }, "only the job that writes is widened, and it widens itself"
    assert _mapping(job.get("permissions"), "status-page permissions") == {"contents": "write"}
    assert "needs" not in job, (
        "the page is derived from the plan-docs alone, so a gate that is red "
        "about something else would only hold a correct page back"
    )

    names = [str(step.get("name")) for step in _steps(workflow, STATUS_PAGE_JOB)]
    commit_step = "Commit the plan queue, when a Reckoner moved"
    commit = _step(workflow, STATUS_PAGE_JOB, "name", commit_step)
    assert names.index("Regenerate the plan queue from the Reckoners") < names.index(commit_step)

    script = _script(commit, f"ci.yml/{STATUS_PAGE_JOB}/commit")
    # The termination argument the trigger filter does not carry: a run over a
    # tree this job already wrote finds no diff, so it commits nothing and there
    # is no second push to guard against.
    assert f"git diff --quiet -- {STATUS_PAGE}" in script
    assert f"git add {STATUS_PAGE}" in script
    assert "git push origin HEAD:main" in script


@requires_bash
def test_the_plan_queue_guard_reads_a_real_merge_commit(tmp_path: Path) -> None:
    """The shipped shell, against a real merge commit, both ways.

    The check is about what a pull request changes, and a pull request is a
    merge commit - so the fixture is one, built twice: once where the branch
    edits the page and once where it does not. A check that read the working
    tree, or the tip of `main`, would pass both arms.
    """
    bash = _bash()
    assert bash is not None, "requires_bash admitted a run with no bash"
    script = _script(
        _step(_load_workflows()["ci.yml"], "gates", "name", STATUS_PAGE_GUARD),
        f"ci.yml/gates/{STATUS_PAGE_GUARD}",
    )
    env = _isolated_env(tmp_path)

    for edits_the_page, expected in ((False, 0), (True, 1)):
        repo = tmp_path / ("edited" if edits_the_page else "untouched")
        repo.mkdir()
        _git(repo, env, "init", "-b", "main")
        _write(repo / STATUS_PAGE, "# The plan queue\n")
        _write(repo / "docs" / "page.md", "before\n")
        _git(repo, env, "add", ".")
        _git(repo, env, "commit", "-m", "the base")
        _git(repo, env, "switch", "-c", "branch")
        _write(repo / "docs" / "page.md", "after\n")
        if edits_the_page:
            _write(repo / STATUS_PAGE, "# The plan queue\n\nhand-edited\n")
        _git(repo, env, "add", ".")
        _git(repo, env, "commit", "-m", "the branch")
        _git(repo, env, "switch", "main")
        _git(repo, env, "merge", "--no-ff", "--no-edit", "branch")

        run = subprocess.run(
            [bash, "-c", script], cwd=repo, env=env, capture_output=True, text=True
        )
        assert run.returncode == expected, f"{run.stdout}\n{run.stderr}"
        if expected:
            assert STATUS_PAGE in run.stderr, "the message says which file and why"
