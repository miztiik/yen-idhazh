"""Does one dispatch of the pipeline test workflow compare three cases over one pair of articles?"""

from __future__ import annotations

import json
import os
import re
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
from utilities import candidate_pointer, model_refs

from ._harness import (
    LLAMA_PIN_SCRIPT,
    LLAMA_RUNTIME_SCRIPT,
    PINNED_LLAMA_BUILD,
    SCRIPTS_DIR,
    WORKFLOWS_DIR,
    _bash,
    _declared_dispatch_inputs,
    _isolated_env,
    _job,
    _load_workflows,
    _mapping,
    _normalize_condition,
    _pin_output_name,
    _run_bodies,
    _script,
    _script_closure,
    _step,
    _steps,
    _strings,
    _triggers,
    requires_bash,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

WORKFLOW: str = "idhazh-pipeline-tests.yaml"

JOB: str = "cases"

#: The one step that opens the address list, and the two steps that read what it
#: chose. Named here so a fourth reader has to be added on purpose.
PICK_STEP: str = "Pick the two articles"

PLAN_STEP: str = "Plan the two articles"

#: The modules the steps call, and the call each step must still carry. Reading
#: the step and running the module is what keeps this a test of the shipped
#: bytes rather than of a copy (Guardrail #7).
DRAW_MODULE: str = "backend/utilities/pipeline_draw.py"
CASE_CONFIG_MODULE: str = "backend/utilities/pipeline_case_config.py"
REPORT_MODULE: str = "backend/utilities/pipeline_case_report.py"
PICK_CALL: str = f"{DRAW_MODULE} pick"
PLAN_CALL: str = f"{DRAW_MODULE} plan"
CASE_CONFIG_CALL: str = CASE_CONFIG_MODULE
REPORT_CALL: str = REPORT_MODULE


def _module_outputs(
    argv: list[str], *, cwd: Path, module: str = DRAW_MODULE
) -> dict[str, str]:
    """The `KEY=value` lines a step appends to `$GITHUB_OUTPUT`, as a mapping."""
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / module), *argv],
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return dict(line.split("=", 1) for line in done.stdout.splitlines() if "=" in line)

#: The step that restarts the server with two slots, and the step that reads its
#: outcome. Case three is the only case guarded on a step rather than only on the
#: job not being cancelled.
RESTART_STEP: str = "Restart the model with two slots"

REPORT_STEP: str = "Say what the three cases measured"

CASE_SCRIPT: Path = SCRIPTS_DIR / "run-pipeline-test-case.sh"

#: The one dispatch input, the action that acts on it, and the scratch root that
#: action writes. Named here so a second way of reaching a candidate has to be
#: added on purpose.
CANDIDATE_INPUT: str = "candidate_models_file"

CANDIDATE_ACTION: str = "./.github/actions/candidate-config"

SCRATCH_CONFIG: str = "backend/var/candidate-config"

#: Where this dispatch's own ledgers land, as `run.trial_state_dirname`. The
#: same directory the bench already writes to, so nothing a dispatch records
#: sits beside the rows the console reads.
TRIAL_STATE: str = "pipeline-tests"

RUNTIME_SCRIPT: Path = SCRIPTS_DIR / LLAMA_RUNTIME_SCRIPT

PIN_SCRIPT: Path = SCRIPTS_DIR / LLAMA_PIN_SCRIPT

#: What the fetch step publishes for the cache key to read, read off the pin
#: script itself so this file cannot name an output the pin does not print.
PIN_OUTPUT: str = _pin_output_name()

FETCH_STEP: str = "Fetch runtime and weights"

PIN_STEP: str = "Say which llama.cpp build this job installs"

CACHE_STEP: str = "Cache weights and runtime"

CASE_CONFIG_STEP: str = "Write each case's config"


def _required_environment(script: str) -> set[str]:
    """Every variable a shell script refuses to run without.

    Read off the script's own `: "${NAME:?...}"` guards rather than listed, so a
    guard added to the script is a guard the caller is held to from that commit
    on. A list here would be a second copy of the script's interface, and the
    copy is what goes stale.
    """
    return set(re.findall(r':\s*"\$\{([A-Z_][A-Z0-9_]*):\?', script))


def _recorded(root: Path, case: str, item_ids: Sequence[str]) -> None:
    """Write what one case's work stage would have left under `backend/var/cases/`."""
    items = root / "backend" / "var" / "cases" / case / "run" / "items"
    items.mkdir(parents=True, exist_ok=True)
    for item_id in item_ids:
        (items / f"{item_id}.article.json").write_text("{}", encoding="utf-8")
        (items / f"{item_id}.summary.json").write_text(
            json.dumps({"status": "ok", "summarize_ms": 1000}), encoding="utf-8"
        )


def _report(root: Path, expected: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run the report the step runs, over a tree of case results.

    The shipped bytes, not a copy of them (Guardrail #7). It prints a markdown
    table rather than `key=value` lines, so it is run rather than read.
    """
    assert REPORT_CALL in _script(
        _step(_load_workflows()[WORKFLOW], JOB, "name", REPORT_STEP), REPORT_STEP
    ), "the report step no longer calls the module this drives"
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / REPORT_MODULE), "--expected", " ".join(expected)],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
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
    """Dispatch and nothing else, and the form asks one question.

    A schedule would spend a runner-hour a day on a workflow nobody is reading
    the result of, and a push or pull_request trigger would spend one per
    commit.

    The form asks which model to run, and nothing else. Every case setting is
    still read from config or drawn (Guardrail #6) - the addresses, the draw
    size, the job bound, the slot counts, the windows. Which model is the one
    question config cannot answer, because the committed config names the
    incumbent by design, and a second input would be a value somebody could
    mistype into a job measured in hours.
    """
    workflow = _load_workflows()[WORKFLOW]
    assert set(_triggers(workflow)) == {"workflow_dispatch"}
    declared = _declared_dispatch_inputs(workflow)
    assert sorted(declared) == [CANDIDATE_INPUT], (
        "one input, and it names the model: every case setting is read from config"
    )
    named = _mapping(declared[CANDIDATE_INPUT], f"{WORKFLOW} input {CANDIDATE_INPUT}")
    assert named.get("default") == "", (
        "empty is the default, so a dispatch that types nothing runs the configured model"
    )


def test_the_cases_run_in_sequence_in_one_job_on_one_runner() -> None:
    """Not a matrix, and the reason is the spread between hosts.

    Prefill spans 4.2x between GitHub-hosted runners, which is larger than
    anything a case here is looking for. Three jobs would report the three hosts
    they drew. One job in sequence cancels the host, so the cases differ by what
    they changed and by nothing else.
    """
    workflow = _load_workflows()[WORKFLOW]
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict) and list(jobs) == [JOB], (
        "one job, so the cases share one runner and one model load"
    )
    job = _job(workflow, JOB)
    assert "strategy" not in job, "a matrix would measure the hosts rather than the cases"
    assert job.get("runs-on") == "ubuntu-latest"


def test_the_job_bound_is_the_budget_config_declares() -> None:
    """The promise is a loop inside the hour, so the number lives in config.

    A literal in the YAML and a number in `config/pipeline-tests.json` would be
    two answers to one question, and the one an operator edits would be the one
    nothing reads.
    """
    job = _job(_load_workflows()[WORKFLOW], JOB)
    assert job.get("timeout-minutes") == str(_settings().budget_minutes)


def test_the_draw_happens_once_and_every_case_reads_it() -> None:
    """The Oracle. One step opens the address list and the cases read its answer.

    This is what makes the three numbers comparable. A case that drew its own
    pair would run different articles, and the difference between two cases would
    then be the articles rather than the change - which is exactly the confound
    a production day already has and this workflow exists to remove.

    Asserted by reading rather than by listing: every step that opens
    `config/pipeline-tests.json` for the draw is discovered, and there must be
    one. The report step opens the same file for the case names and is not a
    second draw, so the test looks for the call that draws.
    """
    workflow = _load_workflows()[WORKFLOW]
    steps = _steps(workflow, JOB)
    drawing = [step.get("name") for step in steps if PICK_CALL in str(step.get("run") or "")]
    assert drawing == [PICK_STEP], f"one step draws the pair, and it is {PICK_STEP!r}"

    pick = _script(_step(workflow, JOB, "name", PICK_STEP), f"{WORKFLOW}/{JOB}/{PICK_STEP}")
    assert '--seed "$PICK_SEED"' in pick, "the draw is seeded, never arbitrary"
    assert "github.run_id" in str(_step(workflow, JOB, "name", PICK_STEP).get("env")), (
        "the seed is the run id GitHub allocated, which nothing in the run can compute"
    )
    assert '"$GITHUB_OUTPUT"' in pick, "a dispatch publishes the seed it drew on"

    plan = _step(workflow, JOB, "name", PLAN_STEP)
    plan_env = str(plan.get("env"))
    assert "steps.pick.outputs.addresses" in plan_env, "the plan reads the pair the draw chose"
    assert "steps.pick.outputs.feeds" in plan_env

    names = [step.get("name") for step in steps]
    assert names.index(PICK_STEP) < names.index(PLAN_STEP), "the draw comes before the plan"


def test_every_case_runs_the_one_plan_and_nothing_else_writes_one() -> None:
    """One plan file, written once, run three times.

    The cases are steps rather than one loop so the run page shows each case's own
    wall clock, and that is exactly the shape that lets a case quietly run
    something else. So the case steps are held to the config's case ids in order,
    and the only thing they are allowed to do is call the shared script.
    """
    workflow = _load_workflows()[WORKFLOW]
    steps = _steps(workflow, JOB)
    settings = _settings()

    case_steps = [
        step
        for step in steps
        if isinstance(step.get("run"), str) and CASE_SCRIPT.name in str(step.get("run"))
    ]
    assert [step.get("name") for step in case_steps] == [
        f"Case {case.id}" for case in settings.cases
    ], "one step per declared case, named for it, in the order config declares"

    for case, step in zip(settings.cases, case_steps, strict=True):
        body = _script(step, f"{WORKFLOW}/{JOB}/{step.get('name')}")
        assert f"{CASE_SCRIPT.name} {case.id} " in body, "the step runs the case it is named for"
        assert "steps.plan.outputs.date" in str(step.get("env")), (
            "a case reads the day the one plan was written for"
        )
        assert PICK_CALL not in body, "a case never draws its own pair"

    written = [step.get("name") for step in steps if PLAN_CALL in str(step.get("run") or "")]
    assert written == [PLAN_STEP], "one step mints the plan the cases share"


def test_the_report_holds_the_cases_to_the_two_items_the_draw_chose() -> None:
    """The runtime half of the Oracle, and it fails the job rather than warning.

    Reading the workflow proves the cases were HANDED one pair. It cannot prove
    they landed on it: an address can 404, and a case that summarized one item
    where another summarized two would still print two rows of plausible
    numbers. So the report compares what each case recorded against what the plan
    asked for, and raises.
    """
    workflow = _load_workflows()[WORKFLOW]
    report = _step(workflow, JOB, "name", REPORT_STEP)
    body = _script(report, f"{WORKFLOW}/{JOB}/report")
    assert "steps.plan.outputs.item_ids" in str(report.get("env"))
    assert REPORT_CALL in body, "the report the step runs"
    source = read_text(REPO_ROOT / REPORT_MODULE)
    assert "landed != expected" in source, "the cases are compared against the plan"
    assert "raise SystemExit(" in source, "a disagreement fails the job"
    assert report.get("if") == "always()", (
        "the case that failed is the one whose census is worth printing"
    )


def test_a_failed_case_costs_the_run_that_case_and_nothing_else() -> None:
    """Three cases are three readings, and one broken case may not take the other two.

    The first dispatch failed exactly that way. The baseline step could not
    start, the two cases behind it never ran, and the run reported one failure
    where it had three to report - which read as a problem with the baseline
    rather than as a problem with the call all three share. A case is read
    against the cases beside it, so a case that did not run is evidence lost.

    `parallel-2` is the one case that reads a step as well, and the reason is
    what a failed restart leaves behind: a healthy ONE-slot server. The case
    would run against it and file that reading under two slots.
    """
    workflow = _load_workflows()[WORKFLOW]
    for case in _settings().cases:
        step = _step(workflow, JOB, "name", f"Case {case.id}")
        condition = _normalize_condition(step.get("if"), f"case {case.id} condition")
        assert "!cancelled()" in condition, (
            f"case {case.id} stops when a sibling case fails, and its reading is lost with it"
        )

    restart = _step(workflow, JOB, "name", RESTART_STEP)
    assert restart.get("id") == "restart", "the case that needs the restart has to name it"
    assert "!cancelled()" in _normalize_condition(restart.get("if"), "restart condition"), (
        "the restart runs after a failed case, or the case behind it is lost too"
    )
    parallel = _normalize_condition(
        _step(workflow, JOB, "name", "Case parallel-2").get("if"), "parallel-2 condition"
    )
    assert "steps.restart.conclusion == 'success'" in parallel, (
        "the two-slot case runs only where the two-slot server started"
    )


def test_the_report_names_a_case_that_recorded_nothing_and_prints_the_rest(
    tmp_path: Path,
) -> None:
    """A case that produced nothing is a census line, not a broken comparison.

    It has already failed or been skipped, its own step is red and the job is
    red with it. What the report owes is the name: a table that quietly dropped
    the row would leave a reader counting cases to notice one was missing, and
    raising on it would hide the failure that really matters underneath a
    sentence about articles.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    expected = ["ai-0000000001", "world-0000000002"]
    cases = [case.id for case in _settings().cases]
    for case in cases[:-1]:
        _recorded(tmp_path, case, expected)

    completed = _report(tmp_path, expected)
    assert completed.returncode == 0, completed.stderr.strip()
    assert f"these cases produced nothing: {cases[-1]}" in completed.stdout
    assert f"| {cases[-1]} | 0 | 0 | 0 | nothing recorded |" in completed.stdout
    for case in cases[:-1]:
        assert f"| {case} | 2 | 2 | 2000 | - |" in completed.stdout, (
            "a case that ran is still measured beside the one that did not"
        )


def test_the_report_refuses_a_comparison_across_different_articles(tmp_path: Path) -> None:
    """The half that still raises, and the reason it has to.

    Two cases that read different articles produce two numbers nobody may
    subtract, and the table is three rows of plausible milliseconds either way.
    This is the one thing the report fails the job over, and a case that
    recorded nothing must not be able to trip it.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    expected = ["ai-0000000001", "world-0000000002"]
    cases = [case.id for case in _settings().cases]
    for case in cases[:-1]:
        _recorded(tmp_path, case, expected)
    _recorded(tmp_path, cases[-1], ["ai-0000000001", "world-0000000003"])

    completed = _report(tmp_path, expected)
    assert completed.returncode != 0, "a disagreement about the articles fails the job"
    assert "did not all read the same two articles" in completed.stderr
    assert cases[-1] in completed.stderr, "the case that disagreed is named"


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

    upload = _step(workflow, JOB, "name", "Upload what the cases produced")
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

    The live list, never the file's text. The dispatch builds its map from
    `settings.sources.feeds`, so a candidate whose feed has moved to `retired`
    is that same `KeyError` while a search of the whole file still finds the id
    on the tombstone shelf. It would also have the test workflow request a
    source we decided to stop asking.
    """
    settings = _settings()
    assert len(settings.candidates) >= MINIMUM_CANDIDATES

    live = {feed.id for feed in config.load(CONFIG_DIR).sources.feeds}
    for candidate in settings.candidates:
        assert candidate.source_id in live, (
            f"{candidate.source_id} is not a live feed in config/sources.json"
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
    assert PICK_CALL in _script(_step(workflow, JOB, "name", PICK_STEP), PICK_STEP)
    published = _module_outputs(["pick", "--seed", seed], cwd=REPO_ROOT)

    assert published["seed"] == seed
    drawn = _settings().draw(seed)
    assert published["addresses"] == " ".join(candidate.url for candidate in drawn)
    assert published["feeds"] == " ".join(candidate.source_id for candidate in drawn)


def test_the_case_configs_the_workflow_writes_all_load(tmp_path: Path) -> None:
    """Every case's config root has to survive `config.load`, or the case cannot start.

    The work stage and the argv builder both open it. A case that wrote a knob
    outside its schema would fail on the runner after the weights were fetched,
    and the case whose numbers are worth having most - two slots, a doubled
    window - is the last one to run.

    Cut from the scratch root the step names, not from `config/`, so this drives
    the route a candidate dispatch really takes.
    """
    scratch = _scratch(tmp_path, models_file=None)
    workflow = _load_workflows()[WORKFLOW]
    case_config = _script(_step(workflow, JOB, "name", CASE_CONFIG_STEP), "case config")
    assert CASE_CONFIG_CALL in case_config
    assert f"--config-root {SCRATCH_CONFIG}" in case_config, (
        "the cases are cut from the scratch copy, so a candidate reaches all three"
    )
    written = _module_outputs(
        ["--config-root", scratch.as_posix()], cwd=tmp_path, module=CASE_CONFIG_MODULE
    )

    settings = _settings()
    assert sorted(written) == sorted(case.id for case in settings.cases)
    for case in settings.cases:
        loaded = config.load(tmp_path / written[case.id])
        assert loaded.app.summarize.asks_for_a_visual_plan is case.asks_for_a_visual_plan
        if not case.asks_for_a_visual_plan:
            assert loaded.app.visuals.enabled_kinds == [], "no picture is reachable"
        inference = loaded.models.summarize.inference
        committed = config.load(CONFIG_DIR).models.summarize.inference
        assert inference.n_parallel == (case.n_parallel or committed.n_parallel)
        assert inference.n_ctx == (case.n_ctx or committed.n_ctx)


def test_the_parallel_case_keeps_the_window_the_gate_admits_articles_against() -> None:
    """A slot count without a window beside it is a test of a smaller window.

    llama-server divides the window it is given between its slots, so two slots
    on the committed number halve what each one holds - and the sequence gate
    still admits articles against the config number. The case would then refuse
    long articles and read as a concurrency result.
    """
    committed = config.load(CONFIG_DIR).models.summarize.inference
    for case in _settings().cases:
        if case.n_parallel is None or case.n_parallel == (committed.n_parallel or 1):
            continue
        assert case.n_ctx is not None, f"{case.id} moves the slot count and not the window"
        assert case.n_ctx >= committed.n_ctx * case.n_parallel, (
            f"{case.id} leaves each slot less than the gate admits articles against"
        )


def test_the_plan_step_writes_a_plan_the_work_stage_can_open(tmp_path: Path) -> None:
    """The one payload every case reads, built by the shipped program.

    `RunPlan` refuses a list whose desk counts disagree with its items, and the
    program builds those counts itself because nothing read a feed. Asserting
    the shape by eye is how that is found on the runner instead of here.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    seed = "34852763827"
    drawn = _settings().draw(seed)

    published = _module_outputs(
        [
            "plan",
            "--addresses",
            " ".join(candidate.url for candidate in drawn),
            "--feeds",
            " ".join(candidate.source_id for candidate in drawn),
            "--execution",
            seed,
        ],
        cwd=tmp_path,
    )

    written = tmp_path / "backend" / "var" / "pipeline-tests" / "plan.json"
    plan = RunPlan.from_json(read_text(written))
    assert plan.run_id == f"{published['date']}-{seed}"
    assert [item.source_url for item in plan.items] == [c.url for c in drawn]
    assert [item.title for item in plan.items] == [c.title for c in drawn], (
        "a planned item with no headline is refused by extract, so every case reads zero items"
    )
    assert published["item_ids"] == " ".join(item.item_id for item in plan.items)
    assert plan.feeds_read == 0, "this plan came off a config list, so no feed was asked"


@requires_bash
@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "usage:"),
        (["baseline"], "usage:"),
        (["not-a-case", "2026-09-14"], "unknown case"),
    ],
)
def test_the_case_script_refuses_a_call_it_cannot_serve(
    argv: list[str], message: str, tmp_path: Path
) -> None:
    """Run it, do not read it (Guardrail #7).

    Three steps pass a case id as a bare string. A typo would otherwise run the
    committed config under another case's name, and the report would file that
    case's number against a config it never used.
    """
    shell = _bash()
    assert shell is not None
    completed = subprocess.run(
        [shell, CASE_SCRIPT.as_posix(), *argv],
        cwd=tmp_path,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert message in completed.stderr


@requires_bash
def test_the_case_script_refuses_to_run_without_the_plan_the_cases_share(tmp_path: Path) -> None:
    """A case with no plan is a case that would summarize nothing and say so quietly.

    `idhazh work` with an absent plan is a failure four steps later about a file
    a reader of the log has to go and find. This one names what is missing and
    which step writes it.
    """
    (tmp_path / "backend" / "var" / "cases" / "baseline" / "config").mkdir(parents=True)
    shell = _bash()
    assert shell is not None
    completed = subprocess.run(
        [shell, CASE_SCRIPT.as_posix(), "baseline", "2026-09-14"],
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

    That is most of why the case body is a script at all, so the file has to be
    where the linter looks and it has to be executable shell rather than a
    fragment somebody pasted.
    """
    for script in (CASE_SCRIPT, RUNTIME_SCRIPT, PIN_SCRIPT):
        assert script.parent == SCRIPTS_DIR
        text = read_text(script)
        assert text.startswith("#!/usr/bin/env bash\n"), script.name
        assert "set -euo pipefail" in text, script.name


def _scratch(tmp_path: Path, *, models_file: str | None) -> Path:
    """The scratch config root the composite action builds, built the same way.

    The committed tree is copied and the shipped program moves the pointer, so a
    test that passes here is a test of the bytes the action runs (Guardrail #7).
    `None` means an empty dispatch, which is the committed pointer.
    """
    scratch = tmp_path / "backend" / "var" / "candidate-config"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CONFIG_DIR, scratch)
    named = models_file or json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models_file"]
    candidate_pointer.point_at(named, scratch=scratch, trial_state=TRIAL_STATE)
    return scratch


def test_a_dispatch_that_names_nothing_runs_the_model_config_already_names() -> None:
    """The empty form is the old behaviour, and the program is what says so.

    The input exists to check a candidate. It may not change what a dispatch
    that types nothing runs, because every reading this workflow has ever taken
    was taken that way - and a form whose default quietly moved the model would
    make the old numbers describe something else (Guardrail #10).
    """
    empty = dict(
        row.split("=", 1)
        for row in model_refs.candidate_rows(REPO_ROOT, "", prefix="candidate_")
    )
    configured = dict(
        row.split("=", 1) for row in model_refs.configured_rows(REPO_ROOT, with_draft=False)
    )

    pointer = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models_file"]
    assert empty["candidate_models_file"] == pointer
    for field in model_refs.CONFIGURED_FIELDS:
        assert empty[f"candidate_{field}"] == configured[f"summarize_{field}"], field


def test_a_named_candidate_moves_one_line_and_leaves_the_committed_config_alone(
    tmp_path: Path,
) -> None:
    """One line moves, and it is the line a swap would later move.

    A dispatch that edited `config/` would leave the checkout it measured on
    disagreeing with the tree it was cut from, and every control this workflow
    holds fixed - the prompt, the schema, the sampler, the window, the
    truncation cap - is the committed one only because the copy differs by that
    one line and nothing else.
    """
    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    named = next(
        path.relative_to(CONFIG_DIR).as_posix()
        for path in sorted((CONFIG_DIR / "models").glob("*.json"))
        if path.relative_to(CONFIG_DIR).as_posix() != committed["models_file"]
    )

    scratch = _scratch(tmp_path, models_file=named)
    written = json.loads(read_text(scratch / "idhazh.json"))

    assert written["models_file"] == named
    assert written["run"]["trial_state_dirname"] == TRIAL_STATE
    moved = {
        key
        for key in set(committed) | set(written)
        if committed.get(key) != written.get(key)
    }
    assert moved == {"models_file", "run"}, f"one pointer and one state root, not {moved}"
    assert json.loads(read_text(CONFIG_DIR / "idhazh.json")) == committed, (
        "the committed config is read, never written"
    )
    assert config.load(scratch).models.summarize.id, "the scratch root still loads"


def test_no_step_opens_the_committed_models_file_once_a_candidate_may_be_named() -> None:
    """Every reader of a model fact reads the copy, or a candidate is half-applied.

    The failure this stops is a dispatch that fetches the candidate, checks it
    against the incumbent's recorded digest, and starts a server on flags the
    committed entry declares. Each of those is a step that looks right on its
    own.
    """
    workflow = _load_workflows()[WORKFLOW]
    build = _step(workflow, JOB, "uses", CANDIDATE_ACTION)
    with_block = build.get("with")
    assert isinstance(with_block, dict)
    assert with_block.get("models_file") == "${{ steps.models.outputs.candidate_models_file }}"
    assert with_block.get("trial_state") == TRIAL_STATE, (
        "the ledgers this dispatch writes land off the production state root"
    )

    for body in _run_bodies(workflow):
        for line in body.splitlines():
            if line.lstrip().startswith("#"):
                continue
            assert '"config/idhazh.json"' not in line, line
            assert 'Path("config")' not in line, line

    names = [step.get("name") for step in _steps(workflow, JOB)]
    assert names.index(build.get("name")) < names.index("Verify the weights"), (
        "the digest is read out of the copy, so the copy has to exist first"
    )
    assert names.index(build.get("name")) < names.index(CASE_CONFIG_STEP)


def test_the_fetch_step_hands_the_script_every_value_it_refuses_to_run_without() -> None:
    """Read the script's own guards, never a list beside them.

    A script that refuses a missing value and a caller that never passes it is a
    step that fails after the cache step, on a runner, with the weights half
    downloaded. The guards are the interface, so they are what the call site is
    held to - and a guard added later is one this test enforces from that commit
    without being edited.

    The whole call chain, because the runtime install is now its own script: a
    guard that moved one file further away is still a guard this step has to
    satisfy, and reading only the top file would have gone green on a step that
    no longer passes `GITHUB_TOKEN`.

    Through `env`, never pasted: a value pasted into a program is text before it
    is a value (Guardrail #11).
    """
    required = _required_environment(_script_closure(read_text(RUNTIME_SCRIPT)))
    assert "GITHUB_TOKEN" in required and "WEIGHTS_FILE" in required, (
        f"the script no longer guards what it needs: {sorted(required)}"
    )

    fetch = _step(_load_workflows()[WORKFLOW], JOB, "name", FETCH_STEP)
    assert _script(fetch, FETCH_STEP).strip() == f"bash .github/scripts/{LLAMA_RUNTIME_SCRIPT}"
    supplied = fetch.get("env")
    assert isinstance(supplied, dict)
    assert required <= set(supplied), f"the step never passes {sorted(required - set(supplied))}"


def test_the_cache_key_names_the_build_the_script_is_about_to_install() -> None:
    """The key holds the runtime, so a key naming another build serves the wrong one.

    The fetch runs only on a miss. A key that could name a build the script does
    not install would restore one binary under the name of another and never
    fetch again, which is the instability of following the newest release with
    none of its freshness.

    So the key reads the pin off the script rather than repeating it, and the
    weights half names the candidate rather than the committed model - or a
    dispatch checking one model would be served the other from cache.
    """
    workflow = _load_workflows()[WORKFLOW]
    cache = _step(workflow, JOB, "name", CACHE_STEP)
    with_block = cache.get("with")
    assert isinstance(with_block, dict)
    key = str(with_block.get("key"))
    assert f"steps.runtime.outputs.{PIN_OUTPUT}" in key, key
    assert "steps.models.outputs.candidate_file" in key, key
    assert "steps.models.outputs.candidate_revision" in key, key

    names = [step.get("name") for step in _steps(workflow, JOB)]
    assert names.index(PIN_STEP) < names.index(CACHE_STEP), "the key cannot read a later step"


@requires_bash
def test_the_pin_script_prints_the_build_the_cache_key_reads(tmp_path: Path) -> None:
    """Run it, do not read it (Guardrail #7).

    The build is a constant in one file, the fetch sources that file, and the
    cache key is built from what that file prints. This is the one place the
    printed value and the pinned value are compared, and it is what makes the
    extraction safe: an upgrade that moved the constant and not the print would
    key the cache on the old build and restore the old binary forever.
    """
    shell = _bash()
    assert shell is not None
    completed = subprocess.run(
        [shell, PIN_SCRIPT.as_posix()],
        cwd=tmp_path,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == f"{PIN_OUTPUT}={PINNED_LLAMA_BUILD}"
    assert not (tmp_path / "backend").exists(), "asking which build must not fetch one"


def test_no_case_setting_is_written_into_the_workflow() -> None:
    """Guardrail #6. The cases, the slot counts and the windows are all in config.

    A slot count written into the YAML would be the number an operator edits in
    the wrong place, and it would be invisible to the schema that bounds it.
    """
    text = read_text(WORKFLOWS_DIR / WORKFLOW)
    settings = _settings()
    for case in settings.cases:
        if case.n_ctx is not None:
            assert str(case.n_ctx) not in text, f"{case.id} writes its window into the workflow"
    for candidate in settings.candidates:
        assert candidate.url not in text, "an address belongs in config, never in the workflow"
