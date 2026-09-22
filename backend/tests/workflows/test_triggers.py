"""What starts a workflow, when, and what is done to a dispatched input before anything acts on it?"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import cast

import pytest
from conftest import CONFIG_DIR

from ._harness import (
    CONTENT_REFRESH_RUN_MINUTES,
    CONTENT_REFRESH_UTC_HOURS,
    DISPATCH_BOOLEAN,
    DISPATCH_CHOICE,
    DISPATCH_INPUT_SHAPES,
    DISPATCH_READ_BY_NAME,
    EXPECTED_WORKFLOWS,
    SCHEDULED_START_DRIFT_MINUTES,
    UNPUBLISHABLE_DATES,
    _declared_dispatch_inputs,
    _every_env,
    _job,
    _load_workflows,
    _mapping,
    _names_the_input,
    _run_bodies,
    _run_the_decide_step,
    _stages_a_state_path,
    _steps,
    _string_list,
    _triggers,
    requires_bash,
)

pytestmark = pytest.mark.workflow

_DISPATCH_FALLBACK = re.compile(r"^inputs\.(?P<input>[a-z_]+) \|\| '(?P<fallback>[^']+)'$")

_MINUTES_IN_A_DAY = 24 * 60


def test_workflow_names_and_trigger_classes_are_pinned() -> None:
    workflows = _load_workflows()

    for filename, (display_name, trigger_classes) in EXPECTED_WORKFLOWS.items():
        workflow = workflows[filename]
        assert workflow.get("name") == display_name
        assert set(_triggers(workflow)) == trigger_classes


def test_content_refresh_runs_at_the_five_approved_utc_hours() -> None:
    """Five one-slot lines, not one five-hour line, and the difference is load-bearing.

    `github.event.schedule` hands a run the cron line that fired. With one
    `20 2,6,10,14,18 * * *` line that string cannot say which of the five slots
    it was, so a run could not report how late it started - and GitHub drops
    scheduled slots under load without leaving a failed run behind.
    """
    workflows = _load_workflows()
    schedule = _triggers(workflows["digest.yml"])["schedule"]

    assert schedule == [{"cron": f"20 {hour} * * *"} for hour in CONTENT_REFRESH_UTC_HOURS]
    for entry in cast(list[dict[str, str]], schedule):
        fields = entry["cron"].split()
        assert len(fields) == 5, "a five-field cron"
        assert "," not in fields[1], (
            "one hour per line, so github.event.schedule names a single slot"
        )


def test_a_scheduled_run_reports_which_slot_it_is_and_how_late() -> None:
    """The alarm is a report, not a gate. It cannot fix the platform.

    Measured 2026-08-27 to 2026-08-29: 13 slots elapsed, 5 produced a run, and
    every run that started succeeded. Nothing recorded the eight that were never
    created, so this step is the only place the loss becomes visible.
    """
    plan_steps = _steps(_load_workflows()["digest.yml"], "plan")
    late = [step for step in plan_steps if "how late" in str(step.get("name", ""))]

    assert len(late) == 1, "exactly one step reports lateness"
    step = late[0]
    assert step.get("if") == "github.event_name == 'schedule'", (
        "a dispatch has no slot to be late for"
    )
    env = _mapping(step.get("env"), "the lateness step's env")
    assert env.get("SLOT") == "${{ github.event.schedule }}", (
        "the slot arrives through env, never pasted into the script (Guardrail #11)"
    )
    body = str(step.get("run", ""))
    assert "::warning title=Late run::" in body, "it annotates the run summary"
    assert "10#" in body, "every clock field is forced to base ten, or 08 is octal"


def _cron_minute_of_day(expression: str) -> int:
    """The UTC minute a plain daily five-field cron line fires at."""
    minute, hour, *rest = expression.split()
    assert rest == ["*", "*", "*"], f"{expression!r} must be a plain daily cron"
    return int(hour) * 60 + int(minute)


def _wall_clock(first: int, last: int) -> set[int]:
    """Every UTC minute of the day from `first` to `last`, wrapped over midnight."""
    return {minute % _MINUTES_IN_A_DAY for minute in range(first, last + 1)}


def test_the_prune_force_push_wakes_outside_every_digest_run() -> None:
    """`prune.yml` ends in `git push --force origin main`, so it may not wake while a digest can run.

    The span is derived from `digest.yml`'s own cron list rather than named here.
    A scheduled run starts 40 to 70 minutes after its cron minute and then takes
    164 to 184 minutes end to end, so each line at H:20 occupies H+1:00 to
    H+4:34. Prune's force-push is its last step, so what has to clear those spans
    is its own cron minute plus the same drift, through its `timeout-minutes`.

    This lowers the odds; it does not close them. GitHub queues scheduled runs by
    load, so a digest run later than the recorded normal still reaches the prune
    hour, and no workflow here can hold a lock against another one.
    """
    workflows = _load_workflows()
    earliest_start, latest_start = SCHEDULED_START_DRIFT_MINUTES
    _, longest_run = CONTENT_REFRESH_RUN_MINUTES

    digest_runs: set[int] = set()
    for entry in cast(list[dict[str, str]], _triggers(workflows["digest.yml"])["schedule"]):
        asked = _cron_minute_of_day(entry["cron"])
        digest_runs |= _wall_clock(asked + earliest_start, asked + latest_start + longest_run)

    prune = workflows["prune.yml"]
    schedule = cast(list[dict[str, str]], _triggers(prune)["schedule"])
    assert len(schedule) == 1, "one wake-up line, so there is one hour to place"
    wakes = _cron_minute_of_day(schedule[0]["cron"])
    bound = int(str(_job(prune, "prune")["timeout-minutes"]))
    force_push = _wall_clock(wakes + earliest_start, wakes + latest_start + bound)

    clash = sorted(force_push & digest_runs)
    assert not clash, (
        f"prune wakes at {schedule[0]['cron']!r}, and its force-push can land inside a "
        f"digest run: {len(clash)} shared UTC minutes from "
        f"{clash[0] // 60:02d}:{clash[0] % 60:02d}"
    )


def test_expensive_workflows_do_not_run_on_pull_request_or_push() -> None:
    workflows = _load_workflows()

    for filename in ("backfill.yml", "digest.yml", "measure.yml", "validate.yml"):
        assert {"pull_request", "push"}.isdisjoint(_triggers(workflows[filename]))


def test_every_dispatch_input_is_shaped_before_anything_acts_on_it() -> None:
    """A dispatch form is free text unless somebody constrained it, and a wrong
    value here is not loud - it is a run that finishes and publishes to an
    address nobody looks at.

    Discovery is closed-world. A new input turns up here whether or not anybody
    remembered it, and fails until it is written down as an enumeration, as a
    value read by name, or with the pattern the workflow matches it against.
    """
    workflows = _load_workflows()
    found = {
        (filename, name)
        for filename, workflow in workflows.items()
        for name in _declared_dispatch_inputs(workflow)
    }
    assert found == set(DISPATCH_INPUT_SHAPES), (
        "a dispatch input was added or removed without saying how its value is shaped"
    )

    for (filename, name), shape in sorted(DISPATCH_INPUT_SHAPES.items()):
        workflow = workflows[filename]
        where = f"{filename} input {name}"
        declared = _mapping(_declared_dispatch_inputs(workflow)[name], where)
        if shape == DISPATCH_CHOICE:
            assert declared.get("type") == "choice", f"{where} must be a choice"
            assert _string_list(declared.get("options"), f"{where} options"), (
                f"{where} is a choice with nothing to choose from"
            )
            continue
        if shape == DISPATCH_BOOLEAN:
            assert declared.get("type") == "boolean", f"{where} must be a boolean"
            continue
        if shape == DISPATCH_READ_BY_NAME:
            assert not any(_names_the_input(body, name) for body in _run_bodies(workflow)), (
                f"{where} is read by name, so it may not be pasted into a script"
            )
            assert any(
                _names_the_input(str(value), name)
                for _, scope in _every_env(workflow)
                for value in scope.values()
            ), f"{where} must reach a step through env"
            continue
        assert shape.startswith("^") and shape.endswith("$"), (
            f"{where}: an unanchored pattern matches a prefix, which is not a shape"
        )
        assert any(f"=~ {shape}" in body for body in _run_bodies(workflow)), (
            f"{where} must be matched against {shape} before anything acts on it"
        )


def _render_concurrency_group(group: str, dispatched: dict[str, str]) -> str:
    """Substitute a group's one expression the way GitHub would, or refuse to guess.

    Only the `inputs.<name> || '<literal>'` form is understood. Anything else
    raises rather than rendering something GitHub would not, because a test that
    quietly renders an expression wrong reports a distinctness that does not
    exist on the platform.
    """
    spans = re.findall(r"\$\{\{(.*?)\}\}", group)
    if not spans:
        return group
    rendered = group
    for span in spans:
        matched = _DISPATCH_FALLBACK.match(span.strip())
        assert matched, f"a concurrency group this test cannot evaluate: ${{{{{span}}}}}"
        name = matched.group("input")
        assert name in dispatched, f"the group names an input the dispatch form has no {name}"
        rendered = rendered.replace(f"${{{{{span}}}}}", dispatched[name] or matched.group("fallback"))
    return rendered


def test_every_workflow_that_commits_a_ledger_says_which_of_its_runs_may_overlap() -> None:
    """A `state/` writer with no concurrency group is a writer nothing holds apart.

    `measure.yml` was the last one. It is dispatched by hand many times a day
    and its `runtime` job pushes one host row into a day file that every other
    dispatch of that day also appends to, so two of them racing lose a row at
    the rebase - and the step is `continue-on-error`, so the run stays green
    while the record goes.

    What this settles is that none is missing. It cannot settle that a group is
    the right one: whether two dispatches are one question is a judgement about
    what the dispatch means, and the test above is where that is argued for the
    one workflow it matters most in.

    `cancel-in-progress` is checked as well, because the cancelling kind is not
    a queue - it throws the running job away, and a job that was about to
    commit a ledger takes the ledger with it.
    """
    workflows = _load_workflows()
    writers = sorted(name for name, body in workflows.items() if _stages_a_state_path(body))
    assert writers, "no workflow stages a path under state/, so this test proves nothing"

    for name in writers:
        concurrency = _mapping(workflows[name].get("concurrency"), f"{name} concurrency")
        assert str(concurrency.get("group", "")).strip(), (
            f"{name} commits a path under state/ and declares no concurrency group"
        )
        assert str(concurrency.get("cancel-in-progress")) != "true", (
            f"{name} would cancel a run that is already committing a ledger"
        )


def test_two_candidates_dispatched_together_are_two_qualifications_and_not_one() -> None:
    """One group per candidate, because two candidates are two questions.

    `group: validate` admitted one run. GitHub keeps only ONE pending run per
    group and a newer pending run cancels the older one, so a comparison fired
    several candidates wide kept the run that started and the case dispatched
    last, and cancelled every case between them - no error anywhere, only a
    cancelled run.

    The candidate list is read off `config/models/`, so a model added later is
    covered without anybody remembering this test.
    """
    concurrency = _mapping(_load_workflows()["validate.yml"]["concurrency"], "validate.yml")
    assert str(concurrency["cancel-in-progress"]) != "true", (
        "a queued qualification waits; cancelling one throws away an hour of runner time"
    )
    group = str(concurrency["group"])

    candidates = [f"models/{path.name}" for path in sorted(CONFIG_DIR.glob("models/*.json"))]
    assert candidates, "config/models is where a candidate is written down"
    # The empty field is the incumbent, which is a candidate like any other.
    dispatched = [*candidates, ""]
    groups = {
        value: _render_concurrency_group(group, {"candidate_models_file": value})
        for value in dispatched
    }

    assert len(set(groups.values())) == len(dispatched), (
        f"two candidates share a concurrency group, so GitHub cancels one of them: {groups}"
    )
    for value, rendered in groups.items():
        assert rendered.strip(), f"the group for {value or 'the configured model'!r} is empty"
        assert not rendered.endswith("-"), (
            f"the group for {value or 'the configured model'!r} ends in a bare dash, "
            "which every dispatch that fills nothing in would collide on"
        )


@requires_bash
def test_a_scheduled_run_still_decides_its_own_date(tmp_path: Path) -> None:
    """The pattern runs after the default, so the automatic path is the one it
    is proved against. A schedule passes no inputs at all, and a guard that
    rejected the empty string would take down every run this workflow makes.
    """
    before = datetime.datetime.now(datetime.UTC).date().isoformat()
    completed, outputs = _run_the_decide_step("", tmp_path)
    after = datetime.datetime.now(datetime.UTC).date().isoformat()

    assert completed.returncode == 0, completed.stderr
    assert outputs["date"] in {before, after}, "a scheduled run dates itself in UTC"
    assert outputs["day_dir"] == f"frontend/public/digest/{outputs['date'].replace('-', '/')}"
    assert outputs["faithfulness"] == "true"


@requires_bash
def test_a_dispatched_date_becomes_the_day_it_names(tmp_path: Path) -> None:
    completed, outputs = _run_the_decide_step("2026-08-25", tmp_path)

    assert completed.returncode == 0, completed.stderr
    assert outputs["date"] == "2026-08-25"
    assert outputs["day_dir"] == "frontend/public/digest/2026/08/25"


@requires_bash
@pytest.mark.parametrize("dispatched", UNPUBLISHABLE_DATES)
def test_a_date_that_is_not_a_day_stops_before_it_costs_a_run(
    dispatched: str, tmp_path: Path
) -> None:
    """Each of these reads as a date and publishes as a directory nobody visits.
    None of them fails anywhere else: the stages take the string, the commit
    lands, and the day is simply not where the site looks for it.
    """
    completed, outputs = _run_the_decide_step(dispatched, tmp_path)

    assert completed.returncode == 1, f"{dispatched!r} was accepted as a day"
    assert "YYYY-MM-DD" in completed.stderr
    assert outputs == {}, "a rejected date must not become a fact the run reads"
