"""Does one dispatch of the pipeline test workflow compare three arms over one pair of articles?"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.pipeline_tests import MINIMUM_CANDIDATES, PipelineTestsConfig
from idhazh.contracts.run_plan import RunPlan

from ._harness import (
    SCRIPTS_DIR,
    WORKFLOWS_DIR,
    _bash,
    _declared_dispatch_inputs,
    _inline_programs,
    _isolated_env,
    _job,
    _load_workflows,
    _normalize_condition,
    _run_the_inline_program,
    _script,
    _step,
    _steps,
    _strings,
    _triggers,
    requires_bash,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

WORKFLOW: str = "idhazh-pipeline-tests.yaml"

JOB: str = "arms"

#: The one step that opens the address list, and the two steps that read what it
#: chose. Named here so a fourth reader has to be added on purpose.
PICK_STEP: str = "Pick the two articles"

PLAN_STEP: str = "Plan the two articles"

#: The step that restarts the server with two slots, and the step that reads its
#: outcome. Arm three is the only arm guarded on a step rather than only on the
#: job not being cancelled.
RESTART_STEP: str = "Restart the model with two slots"

REPORT_STEP: str = "Say what the three arms measured"

ARM_SCRIPT: Path = SCRIPTS_DIR / "run-pipeline-test-arm.sh"


def _recorded(root: Path, arm: str, item_ids: Sequence[str]) -> None:
    """Write what one arm's work stage would have left under `backend/var/arms/`."""
    items = root / "backend" / "var" / "arms" / arm / "run" / "items"
    items.mkdir(parents=True, exist_ok=True)
    for item_id in item_ids:
        (items / f"{item_id}.article.json").write_text("{}", encoding="utf-8")
        (items / f"{item_id}.summary.json").write_text(
            json.dumps({"status": "ok", "summarize_ms": 1000}), encoding="utf-8"
        )


def _report(root: Path, expected: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run the report step's own program over a tree of arm results.

    The shipped bytes, not a copy of them (Guardrail #7). It prints a markdown
    table rather than `key=value` lines, so it is run here rather than through
    `_run_the_inline_program`, which reads a step's output.
    """
    body = _script(_step(_load_workflows()[WORKFLOW], JOB, "name", REPORT_STEP), REPORT_STEP)
    programs = _inline_programs(body)
    assert len(programs) == 1, "the report carries one inline program"
    return subprocess.run(
        [sys.executable, "-c", programs[0]],
        cwd=root,
        env={**os.environ, "EXPECTED_ITEM_IDS": " ".join(expected)},
        capture_output=True,
        text=True,
        check=False,
    )


def _settings() -> PipelineTestsConfig:
    """The committed config, read inside the test that needs it.

    Never at module scope: a fixture opened while the module loads is opened
    before any test exists to own the failure, and one bad shape then takes
    every test in the file with it (`CLAUDE.md` section 13).
    """
    return PipelineTestsConfig.from_json(read_text(CONFIG_DIR / "pipeline-tests.json"))


def test_the_only_way_to_start_it_is_a_person_asking() -> None:
    """Dispatch and nothing else, and it takes nothing typed.

    A schedule would spend a runner-hour a day on a workflow nobody is reading
    the result of, and a push or pull_request trigger would spend one per
    commit. A dispatch input would be a value the run acts on that config does
    not already answer (Guardrail #6), and it would be a value somebody could
    mistype into a 45-minute job.
    """
    workflow = _load_workflows()[WORKFLOW]
    assert set(_triggers(workflow)) == {"workflow_dispatch"}
    assert _declared_dispatch_inputs(workflow) == {}, (
        "the dispatch declares no inputs: every arm setting is read from config"
    )


def test_the_arms_run_in_sequence_in_one_job_on_one_runner() -> None:
    """Not a matrix, and the reason is the spread between hosts.

    Prefill spans 4.2x between GitHub-hosted runners, which is larger than
    anything an arm here is looking for. Three jobs would report the three hosts
    they drew. One job in sequence cancels the host, so the arms differ by what
    they changed and by nothing else.
    """
    workflow = _load_workflows()[WORKFLOW]
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict) and list(jobs) == [JOB], (
        "one job, so the arms share one runner and one model load"
    )
    job = _job(workflow, JOB)
    assert "strategy" not in job, "a matrix would measure the hosts rather than the arms"
    assert job.get("runs-on") == "ubuntu-latest"


def test_the_job_bound_is_the_budget_config_declares() -> None:
    """The promise is a loop inside the hour, so the number lives in config.

    A literal in the YAML and a number in `config/pipeline-tests.json` would be
    two answers to one question, and the one an operator edits would be the one
    nothing reads.
    """
    job = _job(_load_workflows()[WORKFLOW], JOB)
    assert job.get("timeout-minutes") == str(_settings().budget_minutes)


def test_the_draw_happens_once_and_every_arm_reads_it() -> None:
    """The Oracle. One step opens the address list and the arms read its answer.

    This is what makes the three numbers comparable. An arm that drew its own
    pair would run different articles, and the difference between two arms would
    then be the articles rather than the change - which is exactly the confound
    a production day already has and this workflow exists to remove.

    Asserted by reading rather than by listing: every step that opens
    `config/pipeline-tests.json` for the draw is discovered, and there must be
    one. The report step opens the same file for the arm names and is not a
    second draw, so the test looks for the call that draws.
    """
    workflow = _load_workflows()[WORKFLOW]
    steps = _steps(workflow, JOB)
    drawing = [step.get("name") for step in steps if ".draw(" in str(step.get("run") or "")]
    assert drawing == [PICK_STEP], f"one step draws the pair, and it is {PICK_STEP!r}"

    pick = _script(_step(workflow, JOB, "name", PICK_STEP), f"{WORKFLOW}/{JOB}/{PICK_STEP}")
    assert 'os.environ["PICK_SEED"]' in pick, "the draw is seeded, never arbitrary"
    assert "github.run_id" in str(_step(workflow, JOB, "name", PICK_STEP).get("env")), (
        "the seed is the run id GitHub allocated, which nothing in the run can compute"
    )
    assert 'print(f"seed={seed}")' in pick, "a dispatch says which seed it drew on"
    assert '>> "$GITHUB_OUTPUT"' in pick or '"$GITHUB_OUTPUT"' in pick

    plan = _step(workflow, JOB, "name", PLAN_STEP)
    plan_env = str(plan.get("env"))
    assert "steps.pick.outputs.addresses" in plan_env, "the plan reads the pair the draw chose"
    assert "steps.pick.outputs.feeds" in plan_env

    names = [step.get("name") for step in steps]
    assert names.index(PICK_STEP) < names.index(PLAN_STEP), "the draw comes before the plan"


def test_every_arm_runs_the_one_plan_and_nothing_else_writes_one() -> None:
    """One plan file, written once, run three times.

    The arms are steps rather than one loop so the run page shows each arm's own
    wall clock, and that is exactly the shape that lets an arm quietly run
    something else. So the arm steps are held to the config's arm ids in order,
    and the only thing they are allowed to do is call the shared script.
    """
    workflow = _load_workflows()[WORKFLOW]
    steps = _steps(workflow, JOB)
    settings = _settings()

    arm_steps = [
        step
        for step in steps
        if isinstance(step.get("run"), str) and ARM_SCRIPT.name in str(step.get("run"))
    ]
    assert [step.get("name") for step in arm_steps] == [
        f"Arm {arm.id}" for arm in settings.arms
    ], "one step per declared arm, named for it, in the order config declares"

    for arm, step in zip(settings.arms, arm_steps, strict=True):
        body = _script(step, f"{WORKFLOW}/{JOB}/{step.get('name')}")
        assert f"{ARM_SCRIPT.name} {arm.id} " in body, "the step runs the arm it is named for"
        assert "steps.plan.outputs.date" in str(step.get("env")), (
            "an arm reads the day the one plan was written for"
        )
        assert ".draw(" not in body, "an arm never draws its own pair"

    written = [step.get("name") for step in steps if "plan.to_json()" in str(step.get("run") or "")]
    assert written == [PLAN_STEP], "one step mints the plan the arms share"


def test_the_report_holds_the_arms_to_the_two_items_the_draw_chose() -> None:
    """The runtime half of the Oracle, and it fails the job rather than warning.

    Reading the workflow proves the arms were HANDED one pair. It cannot prove
    they landed on it: an address can 404, and an arm that summarized one item
    where another summarized two would still print two rows of plausible
    numbers. So the report compares what each arm recorded against what the plan
    asked for, and raises.
    """
    workflow = _load_workflows()[WORKFLOW]
    report = _step(workflow, JOB, "name", REPORT_STEP)
    body = _script(report, f"{WORKFLOW}/{JOB}/report")
    assert "steps.plan.outputs.item_ids" in str(report.get("env"))
    assert "landed != sorted(expected)" in body, "the arms are compared against the plan"
    assert "raise SystemExit(" in body, "a disagreement fails the job"
    assert report.get("if") == "always()", (
        "the arm that failed is the one whose census is worth printing"
    )


def test_a_failed_arm_costs_the_run_that_arm_and_nothing_else() -> None:
    """Three arms are three readings, and one broken arm may not take the other two.

    The first dispatch failed exactly that way. The baseline step could not
    start, the two arms behind it never ran, and the run reported one failure
    where it had three to report - which read as a problem with the baseline
    rather than as a problem with the call all three share. An arm is read
    against the arms beside it, so an arm that did not run is evidence lost.

    `parallel-2` is the one arm that reads a step as well, and the reason is
    what a failed restart leaves behind: a healthy ONE-slot server. The arm
    would run against it and file that reading under two slots.
    """
    workflow = _load_workflows()[WORKFLOW]
    for arm in _settings().arms:
        step = _step(workflow, JOB, "name", f"Arm {arm.id}")
        condition = _normalize_condition(step.get("if"), f"arm {arm.id} condition")
        assert "!cancelled()" in condition, (
            f"arm {arm.id} stops when a sibling arm fails, and its reading is lost with it"
        )

    restart = _step(workflow, JOB, "name", RESTART_STEP)
    assert restart.get("id") == "restart", "the arm that needs the restart has to name it"
    assert "!cancelled()" in _normalize_condition(restart.get("if"), "restart condition"), (
        "the restart runs after a failed arm, or the arm behind it is lost too"
    )
    parallel = _normalize_condition(
        _step(workflow, JOB, "name", "Arm parallel-2").get("if"), "parallel-2 condition"
    )
    assert "steps.restart.conclusion == 'success'" in parallel, (
        "the two-slot arm runs only where the two-slot server started"
    )


def test_the_report_names_an_arm_that_recorded_nothing_and_prints_the_rest(
    tmp_path: Path,
) -> None:
    """An arm that produced nothing is a census line, not a broken comparison.

    It has already failed or been skipped, its own step is red and the job is
    red with it. What the report owes is the name: a table that quietly dropped
    the row would leave a reader counting arms to notice one was missing, and
    raising on it would hide the failure that really matters underneath a
    sentence about articles.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    expected = ["ai-0000000001", "world-0000000002"]
    arms = [arm.id for arm in _settings().arms]
    for arm in arms[:-1]:
        _recorded(tmp_path, arm, expected)

    completed = _report(tmp_path, expected)
    assert completed.returncode == 0, completed.stderr.strip()
    assert f"these arms produced nothing: {arms[-1]}" in completed.stdout
    assert f"| {arms[-1]} | 0 | 0 | 0 | nothing recorded |" in completed.stdout
    for arm in arms[:-1]:
        assert f"| {arm} | 2 | 2 | 2000 | - |" in completed.stdout, (
            "an arm that ran is still measured beside the one that did not"
        )


def test_the_report_refuses_a_comparison_across_different_articles(tmp_path: Path) -> None:
    """The half that still raises, and the reason it has to.

    Two arms that read different articles produce two numbers nobody may
    subtract, and the table is three rows of plausible milliseconds either way.
    This is the one thing the report fails the job over, and an arm that
    recorded nothing must not be able to trip it.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    expected = ["ai-0000000001", "world-0000000002"]
    arms = [arm.id for arm in _settings().arms]
    for arm in arms[:-1]:
        _recorded(tmp_path, arm, expected)
    _recorded(tmp_path, arms[-1], ["ai-0000000001", "world-0000000003"])

    completed = _report(tmp_path, expected)
    assert completed.returncode != 0, "a disagreement about the articles fails the job"
    assert "did not all read the same two articles" in completed.stderr
    assert arms[-1] in completed.stderr, "the arm that disagreed is named"


def test_it_publishes_nothing_and_commits_nothing() -> None:
    """A test workflow that could write the site would be a second publisher.

    Everything it produces lives under `backend/var/`, which is never committed,
    and leaves as an artifact. Nothing it wrote is on a reader's path.
    """
    workflow = _load_workflows()[WORKFLOW]
    permissions = workflow.get("permissions")
    assert permissions == {"contents": "read"}, "it reads the repository and writes nothing back"

    for text in _strings(workflow):
        assert "git commit" not in text, "a test dispatch commits nothing"
        assert "git push" not in text, "a test dispatch pushes nothing"
        assert "frontend/public" not in text, "a test dispatch publishes nothing"

    upload = _step(workflow, JOB, "name", "Upload what the arms produced")
    with_block = upload.get("with")
    assert isinstance(with_block, dict)
    assert str(with_block.get("path")).startswith("backend/var/")
    assert with_block.get("retention-days") == "90"


def test_the_address_list_can_still_answer_a_draw() -> None:
    """Twenty candidates at least, all distinct, each naming a feed we really read.

    A candidate on a feed `config/sources.json` no longer carries is an address
    the run would have to invent a vertical and a tier for. The plan step reads
    both off the feed, so an orphan candidate is a `KeyError` 40 minutes into a
    dispatch rather than a failure here.
    """
    settings = _settings()
    assert len(settings.candidates) >= MINIMUM_CANDIDATES

    sources = read_text(CONFIG_DIR / "sources.json")
    for candidate in settings.candidates:
        assert f'"id": "{candidate.source_id}"' in sources, (
            f"{candidate.source_id} is not a feed in config/sources.json"
        )


@pytest.mark.parametrize("headline", ["", "   ", "\t\n"], ids=["empty", "spaces", "tab-newline"])
def test_a_candidate_with_a_blank_headline_is_refused_by_the_config(headline: str) -> None:
    """The typo is a hand edit to this file, so this is where it has to land.

    Extract refuses an item with no headline, which degrades that item and costs
    a dispatch half its articles. A blank headline in the list is a mistake we
    can see before anything is dispatched, and a minimum length of one would not
    see it: three spaces is three characters.
    """
    settings = _settings()
    payload = settings.model_dump(mode="json")
    payload["candidates"][0]["title"] = headline

    with pytest.raises(ValidationError):
        PipelineTestsConfig.model_validate(payload)


def test_the_draw_is_decided_by_the_seed_and_by_nothing_else() -> None:
    """Same seed, same pair, anywhere. Different seed, different pair.

    A draw that moved between two runs of the same seed could not be replayed,
    and a draw that ignored the seed would read the same two articles forever -
    which is the fixed pair this list exists instead of.
    """
    settings = _settings()
    once = settings.draw("34852763827")
    assert once == settings.draw("34852763827")
    assert len(once) == settings.articles_a_dispatch
    assert len({candidate.url for candidate in once}) == len(once)

    seeds = {tuple(c.url for c in settings.draw(str(seed))) for seed in range(40)}
    assert len(seeds) > 1, "the seed has to move the pair, or the list is decorative"


def test_the_pick_step_publishes_the_pair_the_plan_step_asks_for() -> None:
    """Run the shipped bytes, do not read them (Guardrail #7).

    The two steps meet through three output names. A step that printed
    `urls=` while the next one read `addresses=` would fail 40 minutes into a
    dispatch, with an empty plan and no article fetched.
    """
    workflow = _load_workflows()[WORKFLOW]
    seed = "34852763827"
    published = _run_the_inline_program(
        _script(_step(workflow, JOB, "name", PICK_STEP), PICK_STEP),
        REPO_ROOT,
        {"PICK_SEED": seed},
    )
    assert published["seed"] == seed
    drawn = _settings().draw(seed)
    assert published["addresses"] == " ".join(candidate.url for candidate in drawn)
    assert published["feeds"] == " ".join(candidate.source_id for candidate in drawn)


def test_the_arm_configs_the_workflow_writes_all_load(tmp_path: Path) -> None:
    """Every arm's config root has to survive `config.load`, or the arm cannot start.

    The work stage and the argv builder both open it. An arm that wrote a knob
    outside its schema would fail on the runner after the weights were fetched,
    and the arm whose numbers are worth having most - two slots, a doubled
    window - is the last one to run.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    workflow = _load_workflows()[WORKFLOW]
    written = _run_the_inline_program(
        _script(_step(workflow, JOB, "name", "Write each arm's config"), "arm config"),
        tmp_path,
    )

    settings = _settings()
    assert sorted(written) == sorted(arm.id for arm in settings.arms)
    for arm in settings.arms:
        loaded = config.load(tmp_path / written[arm.id])
        assert loaded.app.summarize.asks_for_a_visual_plan is arm.asks_for_a_visual_plan
        if not arm.asks_for_a_visual_plan:
            assert loaded.app.visuals.enabled_kinds == [], "no picture is reachable"
        inference = loaded.models.summarize.inference
        committed = config.load(CONFIG_DIR).models.summarize.inference
        assert inference.n_parallel == (arm.n_parallel or committed.n_parallel)
        assert inference.n_ctx == (arm.n_ctx or committed.n_ctx)


def test_the_parallel_arm_keeps_the_window_the_gate_admits_articles_against() -> None:
    """A slot count without a window beside it is a test of a smaller window.

    llama-server divides the window it is given between its slots, so two slots
    on the committed number halve what each one holds - and the sequence gate
    still admits articles against the config number. The arm would then refuse
    long articles and read as a concurrency result.
    """
    committed = config.load(CONFIG_DIR).models.summarize.inference
    for arm in _settings().arms:
        if arm.n_parallel is None or arm.n_parallel == (committed.n_parallel or 1):
            continue
        assert arm.n_ctx is not None, f"{arm.id} moves the slot count and not the window"
        assert arm.n_ctx >= committed.n_ctx * arm.n_parallel, (
            f"{arm.id} leaves each slot less than the gate admits articles against"
        )


def test_the_plan_step_writes_a_plan_the_work_stage_can_open(tmp_path: Path) -> None:
    """The one payload every arm reads, built by the shipped program.

    `RunPlan` refuses a list whose desk counts disagree with its items, and the
    program builds those counts itself because nothing read a feed. Asserting
    the shape by eye is how that is found on the runner instead of here.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    workflow = _load_workflows()[WORKFLOW]
    seed = "34852763827"
    drawn = _settings().draw(seed)

    published = _run_the_inline_program(
        _script(_step(workflow, JOB, "name", PLAN_STEP), PLAN_STEP),
        tmp_path,
        {
            "PICKED_ADDRESSES": " ".join(candidate.url for candidate in drawn),
            "PICKED_FEEDS": " ".join(candidate.source_id for candidate in drawn),
            "RUN_EXECUTION": seed,
        },
    )

    written = tmp_path / "backend" / "var" / "pipeline-tests" / "plan.json"
    plan = RunPlan.from_json(read_text(written))
    assert plan.run_id == f"{published['date']}-{seed}"
    assert [item.source_url for item in plan.items] == [c.url for c in drawn]
    assert [item.title for item in plan.items] == [c.title for c in drawn], (
        "a planned item with no headline is refused by extract, so every arm reads zero items"
    )
    assert published["item_ids"] == " ".join(item.item_id for item in plan.items)
    assert plan.feeds_read == 0, "this plan came off a config list, so no feed was asked"


@requires_bash
@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "usage:"),
        (["baseline"], "usage:"),
        (["not-an-arm", "2026-09-14"], "unknown arm"),
    ],
)
def test_the_arm_script_refuses_a_call_it_cannot_serve(
    argv: list[str], message: str, tmp_path: Path
) -> None:
    """Run it, do not read it (Guardrail #7).

    Three steps pass an arm id as a bare string. A typo would otherwise run the
    committed config under another arm's name, and the report would file that
    arm's number against a config it never used.
    """
    shell = _bash()
    assert shell is not None
    completed = subprocess.run(
        [shell, ARM_SCRIPT.as_posix(), *argv],
        cwd=tmp_path,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert message in completed.stderr


@requires_bash
def test_the_arm_script_refuses_to_run_without_the_plan_the_arms_share(tmp_path: Path) -> None:
    """An arm with no plan is an arm that would summarize nothing and say so quietly.

    `idhazh work` with an absent plan is a failure four steps later about a file
    a reader of the log has to go and find. This one names what is missing and
    which step writes it.
    """
    (tmp_path / "backend" / "var" / "arms" / "baseline" / "config").mkdir(parents=True)
    shell = _bash()
    assert shell is not None
    completed = subprocess.run(
        [shell, ARM_SCRIPT.as_posix(), "baseline", "2026-09-14"],
        cwd=tmp_path,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "no plan to run" in completed.stderr


def test_the_shell_it_runs_is_linted_like_every_other_script() -> None:
    """A script under `.github/scripts/` is read by shellcheck; a `run:` body is not.

    That is most of why the arm body is a script at all, so the file has to be
    where the linter looks and it has to be executable shell rather than a
    fragment somebody pasted.
    """
    assert ARM_SCRIPT.parent == SCRIPTS_DIR
    text = read_text(ARM_SCRIPT)
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text


def test_no_arm_setting_is_written_into_the_workflow() -> None:
    """Guardrail #6. The arms, the slot counts and the windows are all in config.

    A slot count written into the YAML would be the number an operator edits in
    the wrong place, and it would be invisible to the schema that bounds it.
    """
    text = read_text(WORKFLOWS_DIR / WORKFLOW)
    settings = _settings()
    for arm in settings.arms:
        if arm.n_ctx is not None:
            assert str(arm.n_ctx) not in text, f"{arm.id} writes its window into the workflow"
    for candidate in settings.candidates:
        assert candidate.url not in text, "an address belongs in config, never in the workflow"
