"""Does the judging workflow bound its units, name no tenant, and commit once?

Driven by the committed YAML, never by a live run. Every assertion here is about
a shape a wrong run would only reveal hours later - a unit with no bound dies at
the 6 h ceiling with nothing written, a second cache key costs a multi-gigabyte
download inside a job that has one, and a venue that spells a tenant's paths
commits the first tenant's output and silently drops the second's.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, REPO_ROOT

from idhazh import cli
from idhazh.council import session
from utilities import council_matrix, shard_bound

from ._harness import (
    MODEL_SERVER_ACTION,
    MODEL_SERVER_CALLERS,
    MODEL_SERVER_STEPS,
    SUBSTITUTED_DATE,
    _action_call,
    _declared_steps,
    _job,
    _load_workflows,
    _local_action_inputs,
    _normalize_condition,
    _script,
    _stage_invocations,
    _step,
    _steps,
)

pytestmark = pytest.mark.workflow

FILENAME: Final = "llm-council.yml"

#: The dotted path the unit's bound is read from. Spelled once here and asserted
#: in the file, so a workflow that read a different knob fails rather than
#: bounding the unit by the work shard's clock - or by a tenant's block, which a
#: night with no tenant registered does not have.
TIMEOUT_KEY: Final = "council.shard_timeout_minutes"

#: What that path prints, and therefore the name the workflow reads it back by.
#: An Actions output name cannot carry a dot, so the reader prints the leaf.
TIMEOUT_OUTPUT: Final = "shard_timeout_minutes"

#: What mints the name this night files its rows under, and the key it prints
#: that name under. The module is the council's own, so the mint resolves in a
#: repository with no judge in it.
MINT_COMMAND: Final = "python -m idhazh.council.run_identity"
RUN_ID_OUTPUT: Final = "run_id"

#: The step that says what tonight fans out to, and the utility behind it.
FANOUT_STEP: Final = "fanout"
FANOUT_COMMAND: Final = "backend/utilities/council_matrix.py"

#: The step that says which dates tonight judges, and the council module behind
#: it. The module is the council's own, so the plan resolves in a repository
#: with no judge in it.
PLAN_STEP: Final = "plan"
PLAN_COMMAND: Final = "python -m idhazh.council.night_plan"
DATES_OUTPUT: Final = "dates"

#: How long an upload outlives the run that wrote it. The committed cap repairs
#: one older date, so three nights keeps a dead night's work reachable for as
#: long as the plan can still name that night.
VERDICT_RETENTION_DAYS: Final = 3

#: Every verb this workflow runs. All three are the council's own and every one
#: of them writes under a name the council minted, so every one is handed it.
COUNCIL_VERBS: Final = ("council-prepare", "council-settle", "council-shard")

#: The one commit call the night makes, and the guard that keeps it off a night
#: with nothing to stage.
COMMIT_STEP: Final = "Commit what the night's tenants wrote"
COMMIT_SCRIPT: Final = ".github/scripts/commit-and-push.sh"

#: What a unit's output travels in, and what a date's selection travels in.
METRICS_ARTIFACT: Final = "council-metrics-"
SELECTION_ARTIFACT: Final = "council-selection-"


def _judges() -> dict[str, object]:
    return _load_workflows()[FILENAME]


def _named(job: str) -> list[str]:
    return [str(step.get("name") or step.get("uses") or "") for step in _steps(_judges(), job)]


def _uploads(job: str, prefix: str) -> list[dict[str, object]]:
    """Every step in `job` uploading an artifact whose name starts with `prefix`."""
    found = []
    for step in _steps(_judges(), job):
        settings = step.get("with")
        if isinstance(settings, dict) and str(settings.get("name", "")).startswith(prefix):
            found.append(step)
    return found


def _emitted(capsys: pytest.CaptureFixture[str]) -> dict[str, str]:
    """What the fan-out utility prints for one date, against the committed config."""
    council_matrix.main(["--config-root", str(CONFIG_DIR), "--date", SUBSTITUTED_DATE])
    printed = capsys.readouterr().out.splitlines()
    return dict(line.split("=", 1) for line in printed if line)


def test_the_unit_reads_its_timeout_from_the_one_file_that_says_so() -> None:
    """The bound is a knob, and the workflow spells no number.

    A literal here would be a second answer to how long a unit may take, and the
    two can disagree - which is exactly what `digest.yml` did for a while, saying
    330 in the file while config said 150.
    """
    bounds = _step(_judges(), "draw", "id", "bounds")
    script = _script(bounds, "the bounds step")

    assert f"backend/utilities/shard_bound.py --key {TIMEOUT_KEY}" in script
    assert not re.search(r"\btimeout-minutes:\s*\d", str(_judges())), (
        "a timeout literal is a second answer to a question config already answers"
    )


def test_the_timeout_travels_as_a_job_output() -> None:
    """`timeout-minutes` resolves from `needs` before the job's first step.

    `steps` is not readable there, so a step output would leave the unit with no
    bound at all - and Actions takes whatever it is handed, so nothing would say
    so until the 6 h ceiling killed the job with nothing written.
    """
    draw = _job(_judges(), "draw")
    judge = _job(_judges(), "judge")
    outputs = draw.get("outputs")

    assert isinstance(outputs, dict)
    assert outputs[TIMEOUT_OUTPUT] == f"${{{{ steps.bounds.outputs.{TIMEOUT_OUTPUT} }}}}"
    assert judge["timeout-minutes"] == f"${{{{ fromJSON(needs.draw.outputs.{TIMEOUT_OUTPUT}) }}}}"


@pytest.mark.parametrize("value", [200.0, "200", 0, -1, True])
def test_an_unreadable_timeout_is_refused_before_the_job_starts(
    value: object, tmp_path: Path
) -> None:
    """A float, a string, a zero and a bool are each a job with no bound.

    `True` is in the list because `isinstance(True, int)` is true in Python, and
    a bound of `True` reaches Actions as `true` - which it cannot read as a
    number. The refusal is `type(value) is not int`, and this is what holds that
    exact spelling shut.
    """
    block, leaf = TIMEOUT_KEY.split(".")
    (tmp_path / "idhazh.json").write_text(
        json.dumps({block: {leaf: value}}), encoding="utf-8", newline="\n"
    )

    with pytest.raises(SystemExit):
        shard_bound.minutes(tmp_path, key=TIMEOUT_KEY)


def test_a_bound_the_config_does_not_carry_is_refused_rather_than_traced() -> None:
    """A path into a block that is not there is a job that would run unbounded.

    The two bounds sit in different blocks now, so a stale key resolves to
    nothing rather than to the wrong number. A `KeyError` traceback in a
    workflow step says which dictionary was missing a name; this says which knob
    the job was looking for.
    """
    stale = "run.judge_shard_timeout_minutes"
    with pytest.raises(SystemExit, match=re.escape(stale)):
        shard_bound.minutes(CONFIG_DIR, key=stale)


def test_the_bound_reader_still_answers_its_first_caller() -> None:
    """One reader and one refusal. A second utility would be a second answer."""
    assert shard_bound.minutes(CONFIG_DIR) >= 1
    assert shard_bound.minutes(CONFIG_DIR, key=TIMEOUT_KEY) >= 1


def test_the_unit_reaches_the_model_through_the_one_shared_action() -> None:
    """The five steps live in one file, so there is no second key to compare.

    This job and the daily run's work shard spelled the same cache, fetch,
    digest check, start and health probe with only the publishing job's name
    between them, and they had already drifted once: the daily run gained a
    weights revision in its cache key and this file got the same edit by hand
    afterwards. A test that compared two literals is what a second copy costs,
    and it can only catch a drift somebody has already shipped.

    One literal costs nothing, so what is asserted here is that the copy is
    gone: this job calls the action and spells none of the five names itself.
    A cache step written back into this file would key a second multi-gigabyte
    entry that competes for eviction, and would throw away the only throughput
    reading this feature has - which was taken on these weights.
    """
    assert (FILENAME, "judge") in MODEL_SERVER_CALLERS
    given = _action_call(_judges(), "judge", MODEL_SERVER_ACTION)
    assert set(given) == set(_local_action_inputs(MODEL_SERVER_ACTION))

    spelled = [
        str(step.get("name"))
        for step in _declared_steps(_judges(), "judge")
        if step.get("name") in MODEL_SERVER_STEPS
    ]
    assert not spelled, f"the unit owns a second copy of {spelled}"

    # A `./` action is this repository at the commit the run checked out, so a
    # job that calls one before checking out has nothing to call.
    names = _named("judge")
    assert names.index("actions/checkout@v6") < names.index(MODEL_SERVER_ACTION)


def test_the_unit_fetches_the_selection_before_it_reads_it() -> None:
    """Without the selection a unit has nothing to work on.

    By pattern rather than by name, and into the council's own scratch root: the
    artifact carries the date and the tenant as directory levels, so two tenants'
    selections arrive beside each other instead of one overwriting the other.
    """
    names = _named("judge")
    download = _step(_judges(), "judge", "uses", "actions/download-artifact@v8")
    settings = download.get("with")

    assert isinstance(settings, dict)
    assert str(settings["pattern"]).startswith(SELECTION_ARTIFACT)
    assert settings["merge-multiple"] == "true"
    assert str(settings["path"]) == session.COUNCIL_ROOT_RELPATH
    assert names.index("actions/download-artifact@v8") < names.index(
        "Run this unit of the tenant's work"
    )


def test_the_matrix_is_emitted_by_the_utility_and_not_computed_in_the_file() -> None:
    """The cells come from the tenants, so the workflow reads no config key at all.

    A key read here is a key the venue has to know about, and a judge's key read
    here raises before the planning job plans anything on a night with no judge
    configured. The one-liner this replaced read a judge's block for the width.
    """
    fanout = _script(_step(_judges(), "draw", "id", FANOUT_STEP), "the fanout step")

    assert FANOUT_COMMAND in fanout
    assert "--date" in fanout
    assert "idhazh.json" not in fanout, (
        "the planning job reads no config key of its own; the utility is what reads config"
    )
    assert "adaptive_dedup_threshold" not in fanout


def test_the_planning_job_asks_the_night_plan_which_dates_tonight_judges() -> None:
    """Tonight, plus whatever its tenants say they are behind on.

    The council asks and never looks, so this step needs no tenant to run - and
    a night with nobody registered plans tonight and nothing else. A date
    computed in the file instead would be one answer the tenants never saw.
    """
    plan = _step(_judges(), "draw", "id", PLAN_STEP)
    environment = plan.get("env")
    script = _script(plan, "the night plan step")

    assert PLAN_COMMAND in script
    assert isinstance(environment, dict)
    assert environment["TONIGHT"] == "${{ steps.decide.outputs.date }}"
    assert environment["DISPATCH_DATE"] == "${{ inputs.date }}", (
        "a dispatched date replaces the plan, and it arrives through env rather than "
        "pasted into the command"
    )
    assert "${{" not in script, "a value pasted into the command is not a value read by name"


def test_every_date_the_plan_names_reaches_the_matrix() -> None:
    """A plan of two dates that fans out to one judges half the night it planned.

    The list is turned into one `--date` an entry rather than word-split into
    the command line, so a date can never arrive as two - and the fan-out reads
    the plan's output rather than the single date the planning job opened on.
    """
    fanout = _step(_judges(), "draw", "id", FANOUT_STEP)
    environment = fanout.get("env")
    script = _script(fanout, "the fanout step")

    assert isinstance(environment, dict)
    assert environment["NIGHT_DATES"] == f"${{{{ steps.{PLAN_STEP}.outputs.{DATES_OUTPUT} }}}}"
    assert "steps.decide.outputs.date" not in str(environment), (
        "the fan-out takes the plan's dates, not the one date the night opened on"
    )
    assert "asked+=(--date" in script
    assert 'python3 backend/utilities/council_matrix.py "${asked[@]}"' in script


def test_every_fanout_output_the_workflow_reads_is_one_the_emitter_prints(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two sides of one contract, held against each other rather than spelled twice.

    An output the workflow publishes and the utility never prints is an empty
    string at the far end, which Actions reports as nothing at all - a matrix
    that silently does not exist, or a commit step that stages nothing and says
    the night was quiet.
    """
    printed = set(_emitted(capsys))
    outputs = _job(_judges(), "draw").get("outputs")

    assert isinstance(outputs, dict)
    read = {
        name
        for name, value in outputs.items()
        if f"steps.{FANOUT_STEP}.outputs." in str(value)
    }
    assert read == printed, (
        f"the planning job publishes {sorted(read)} and the utility prints {sorted(printed)}"
    )


def test_a_matrix_with_no_cells_never_reaches_the_strategy_evaluator() -> None:
    """An empty matrix is a job Actions refuses to build, so the guard has to exist.

    A night with nobody registered fans out to no cells, which is a legal night
    the venue is designed to run. Without the guard it would red on a strategy
    evaluation nobody could read, and the failure would look like a broken
    workflow rather than a room with no case in it.

    What the emitter prints on such a night is asked in
    `backend/tests/council/test_council_matrix.py`, against a config written
    there: the committed one registers a judge, so it cannot answer that
    question here.
    """
    judge = _job(_judges(), "judge")

    assert _normalize_condition(judge["if"], "the judging job") == (
        "needs.draw.outputs.matrix != '[]'"
    )
    assert _normalize_condition(_job(_judges(), "collect")["if"], "the collecting job") == "always()"


def test_the_parallelism_is_the_cell_count_and_never_the_shard_width() -> None:
    """Bound to the width, two tenants over two dates take four waves.

    That is about 5.4 h of wall clock for 81 minutes of work, finishing after
    the digest cron and across the scheduled prune. Bound to the cell count
    under the platform's own ceiling, the same night is one wave.
    """
    strategy = _job(_judges(), "judge").get("strategy")

    assert isinstance(strategy, dict)
    assert strategy["max-parallel"] == "${{ fromJSON(needs.draw.outputs.max_parallel) }}"
    assert strategy["matrix"] == {"include": "${{ fromJSON(needs.draw.outputs.matrix) }}"}
    assert "shards" not in str(strategy["max-parallel"]), (
        "the shard width is a per-tenant number and sizes no wave"
    )


def test_a_cell_carries_its_tenant_its_date_and_its_own_width(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The four values a unit needs, on the cell rather than on a job output.

    A width published once for the whole run would hand every tenant the widest
    tenant's width, and a tenant that runs no model would pay four weights
    restores for work that uses none of them.
    """
    shard = _script(_step(_judges(), "judge", "name", "Run this unit of the tenant's work"), "")
    emitted = _emitted(capsys)
    cells = json.loads(emitted["matrix"])

    for value in ("tenant", "date", "shard", "shards"):
        assert f"matrix.{value}" in shard, f"the unit is never told which {value} it is"
    assert cells, "the committed config registers a tenant, so tonight fans out to cells"
    assert all(set(cell) == {"tenant", "date", "shard", "shards"} for cell in cells), (
        "a cell the unit reads four values off has to carry all four and nothing else"
    )
    assert json.loads(emitted["dates"]) == [SUBSTITUTED_DATE]


def test_one_server_per_unit() -> None:
    """Four servers on four logical CPUs does not fit and would not be faster.

    One `llama-server` peaks at 12.57 to 13.16 GiB and reaches 14.31 GiB with the
    unit's python - 96.0 percent of the 16 GB runner, measured 2026-09-08 over
    four captures of run 2026-08-29-3. And this host is slower at 8 threads than
    at 4 at every prompt length.
    """
    starters = [name for name in _named("judge") if name.startswith("Start the")]

    assert starters == ["Start the model"]


def test_a_dead_unit_does_not_cancel_its_siblings() -> None:
    """A unit that runs out of clock costs its own work for that day and nothing else."""
    strategy = _job(_judges(), "judge").get("strategy")
    collect = _job(_judges(), "collect")

    assert isinstance(strategy, dict)
    # The harness reads the file as text, so a YAML boolean arrives as the word
    # somebody wrote. Comparing to the word is what this file can actually see.
    assert str(strategy["fail-fast"]).lower() == "false"
    assert collect["needs"] == ["draw", "judge"]


def test_a_unit_that_stops_early_still_ships_what_it_did() -> None:
    """The exposure was never the collecting job dying - it is a unit dying.

    A unit that stops on its own clock, or is killed on the platform's, has
    already done every piece of work it reached. Without `always()` the upload is
    skipped on the way out and all of it is lost after up to three hours of model
    time, so the night pays for it twice.
    """
    uploads = _uploads("judge", METRICS_ARTIFACT)

    assert len(uploads) == 1, f"one {METRICS_ARTIFACT}* upload a unit, not {len(uploads)}"
    guard = uploads[0].get("if")
    assert guard is not None, (
        "the output upload carries no condition, so a unit that stopped early skips it "
        "and everything it did goes in the bin"
    )
    assert _normalize_condition(guard, "the output upload") == "always()"


def test_every_artifact_this_night_writes_is_named_for_the_cell_that_wrote_it() -> None:
    """Two tenants at shard zero would otherwise collide on the artifact name.

    And on the merged filename after it, which is the collision the name cannot
    fix on its own - so the date and the tenant are directory levels inside the
    upload as well as words in its name.
    """
    metrics = _uploads("judge", METRICS_ARTIFACT)[0]
    selection = _uploads("draw", SELECTION_ARTIFACT)[0]
    metrics_with = metrics.get("with")
    selection_with = selection.get("with")

    assert isinstance(metrics_with, dict)
    assert isinstance(selection_with, dict)
    for value in ("tenant", "date", "shard"):
        assert f"matrix.{value}" in str(metrics_with["name"]), (
            f"a unit's artifact does not say which {value} produced it"
        )
    assert "steps.decide.outputs.date" in str(selection_with["name"])
    assert str(selection_with["path"]) == session.COUNCIL_ROOT_RELPATH, (
        "the selection is uploaded from the scratch root, so the date and the tenant "
        "survive as directory levels and two tenants do not merge on top of each other"
    )
    assert str(metrics_with["path"]).splitlines()[0] == session.COUNCIL_ROOT_RELPATH
    assert f"!{session.COUNCIL_ROOT_RELPATH}/*/{session.SELECTION_DIRNAME}" in str(
        metrics_with["path"]
    ), "a unit re-uploads the selection it downloaded"


def test_what_a_night_wrote_outlives_the_run_that_wrote_it() -> None:
    """One day expired before the next scheduled run had even started.

    A run that judged a whole night and then died before committing left its
    verdicts in artifacts nothing could still reach, so the only repair was to
    judge the date again from nothing. Three nights covers the committed cap of
    one older date. At about 27 KB a shard file, a week of four shards is under
    a megabyte.
    """
    uploads = _uploads("judge", METRICS_ARTIFACT) + _uploads("draw", SELECTION_ARTIFACT)

    assert uploads, "the night uploads nothing at all"
    for upload in uploads:
        settings = upload.get("with")
        assert isinstance(settings, dict)
        assert int(str(settings["retention-days"])) == VERDICT_RETENTION_DAYS


def test_reading_an_artifact_is_a_scope_the_permissions_block_grants() -> None:
    """A declared block sets every scope it does not list to none.

    So the read has to be named, and it is named read-only. The default
    credential carries it and reaches each download by hand: no stored token is
    introduced, and `contents: write` stays the only write the night has.
    """
    granted = _judges().get("permissions")
    downloads = [
        step
        for job in ("judge", "collect")
        for step in _steps(_judges(), job)
        if str(step.get("uses", "")).startswith("actions/download-artifact@")
    ]

    assert granted == {"contents": "write", "actions": "read"}
    assert downloads, "nothing downloads an artifact"
    for step in downloads:
        settings = step.get("with")
        assert isinstance(settings, dict)
        assert settings["github-token"] == "${{ secrets.GITHUB_TOKEN }}"


def test_no_unit_commits() -> None:
    """Many units pushing into one union-merged file buys many races and many rebases.

    One settle is one push, so two processes never write one path: no merge
    driver to trust, no union stacking to census afterwards, and no key to
    settle across units.
    """
    bodies = [
        _script(step, "a judge step") for step in _steps(_judges(), "judge") if "run" in step
    ]

    assert not [body for body in bodies if "commit-and-push.sh" in body]


def test_the_night_makes_one_commit_call_over_the_paths_its_tenants_named() -> None:
    """The venue spells no store path, because a spelled list is one tenant's list.

    It stages what `committed_paths` came back with, so a second tenant's output
    is committed the day that tenant registers and not the day somebody
    remembers to edit this file.
    """
    calls = [
        _script(step, "a collect step")
        for step in _steps(_judges(), "collect")
        if "run" in step and COMMIT_SCRIPT in _script(step, "a collect step")
    ]
    step = _step(_judges(), "collect", "name", COMMIT_STEP)
    environment = step.get("env")

    assert len(calls) == 1, "one collecting job, one push"
    assert "$COMMITTED_PATHS" in calls[0]
    assert isinstance(environment, dict)
    assert environment["COMMITTED_PATHS"] == "${{ needs.draw.outputs.committed_paths }}"
    assert not re.search(r"\bstate/\S+", calls[0]), (
        "a store path spelled here is a path a second tenant's output never reaches"
    )
    assert _normalize_condition(step["if"], "the commit step") == (
        "needs.draw.outputs.committed_paths != ''"
    )


def test_every_path_a_registered_tenant_names_exists_in_a_fresh_checkout() -> None:
    """`git add` runs under `set -euo pipefail`, so a missing path aborts the step.

    A path named without a committed file behind it costs every store staged
    beside it, on the runner, hours in. It fails here instead - and it is asked
    of the tenants, so a tenant registering a path nothing has created fails on
    the day it registers rather than on the night it runs.
    """
    staged = council_matrix.committed_paths(CONFIG_DIR)
    missing = [path for path in staged if not (REPO_ROOT / path).exists()]

    assert not missing, f"a tenant names paths a fresh checkout does not have: {missing}"


def test_the_collecting_job_settles_every_date_inside_one_job() -> None:
    """One job a date would put two jobs of one run pushing `main`.

    The workflow-level `concurrency` group serialises runs, not the jobs inside
    one, so the second push would race the first. One job, a loop over the dates
    the planning job named, one push.
    """
    settle = _step(_judges(), "collect", "name", "Settle each date")
    environment = settle.get("env")
    script = _script(settle, "the settle step")

    assert isinstance(environment, dict)
    assert environment["COUNCIL_DATES"] == "${{ needs.draw.outputs.dates }}"
    assert "while read" in script, "the dates are looped rather than taken one at a time"
    assert "idhazh council-settle" in script


def test_the_one_commit_message_names_every_date_the_night_settled() -> None:
    """A two-date night that says one date sends a reader to the wrong commit.

    One job, one push, one message - so the message carries the whole list the
    planning job named rather than the single date the night opened on.
    """
    environment = _step(_judges(), "collect", "name", COMMIT_STEP).get("env")

    assert isinstance(environment, dict)
    assert environment["COMMIT_MESSAGE"] == (
        "council: ${{ join(fromJSON(needs.draw.outputs.dates), ' ') }}"
    )


def test_the_night_mints_one_name_and_publishes_it_to_the_later_jobs() -> None:
    """The planning job names the run, the way it already names the bound and the refs.

    A job output because `needs` is what the later jobs can read; a step output
    is not visible across a job boundary. The platform's value arrives through
    `env` rather than pasted into the command, which is how every other value
    this workflow reads by name arrives.
    """
    identity = _step(_judges(), "draw", "id", "identity")
    outputs = _job(_judges(), "draw").get("outputs")
    environment = identity.get("env")

    assert MINT_COMMAND in _script(identity, "the identity step")
    assert isinstance(environment, dict)
    assert environment["PLATFORM_RUN_ID"] == "${{ github.run_id }}"
    assert isinstance(outputs, dict)
    assert outputs[RUN_ID_OUTPUT] == f"${{{{ steps.identity.outputs.{RUN_ID_OUTPUT} }}}}"


def test_the_name_is_minted_once_and_never_per_job() -> None:
    """Four jobs each reading the platform's value would compute the prefix four times.

    The prefix is a day, so a run crossing midnight would file one night's rows
    under two addresses - and nothing downstream could tell that the two were one
    night. So the platform's value is read at exactly one place in the file.
    """
    spelled = str(_judges()).count("github.run_id")

    assert spelled == 1, (
        "the platform's run id is read in more than one step, so the date prefix "
        "is computed more than once and a run crossing midnight splits in two"
    )


def test_this_workflow_runs_the_councils_own_verbs_and_names_no_tenant() -> None:
    """The venue's runtime is its own, not one tenant's four commands.

    A verb this router does not carry is a run that dies mid-pipeline, so both
    sides are read: the workflow's own `run:` bodies and the router's own tuple.
    A verb naming a tenant's mechanism would be the seam this row exists to cut,
    rebuilt as a string that no import check can see.
    """
    run = sorted({stage for _, _, stage, _ in _stage_invocations(_judges(), FILENAME)})

    assert run == sorted(COUNCIL_VERBS)
    assert set(run) <= set(cli.STAGES), f"{sorted(set(run) - set(cli.STAGES))} is not a verb"
    assert not [stage for stage in run if not stage.startswith("council-")]


def test_every_verb_that_writes_a_row_is_handed_the_same_name() -> None:
    """One night, one name, in every verb that files something under it.

    A verb left without it stops at its own command line rather than filing the
    row under a digest run's id - but that is a failed job two hours in, and this
    is the check that runs in seconds. The planning job reads the step that
    minted the name; the later jobs read it back across the job boundary.
    """
    handed: dict[str, str] = {}
    for job_name, _, stage, words in _stage_invocations(_judges(), FILENAME):
        handed[stage] = f"{job_name} {' '.join(words)}"

    assert sorted(handed) == sorted(COUNCIL_VERBS)
    for verb, body in sorted(handed.items()):
        assert "--run-id" in body, f"{verb} files a row under no name of the council's"

    carried = {
        "Pick the work for each date": ("draw", f"steps.identity.outputs.{RUN_ID_OUTPUT}"),
        "Run this unit of the tenant's work": (
            "judge",
            f"needs.draw.outputs.{RUN_ID_OUTPUT}",
        ),
        "Settle each date": ("collect", f"needs.draw.outputs.{RUN_ID_OUTPUT}"),
    }
    for step_name, (job_name, expression) in sorted(carried.items()):
        environment = _step(_judges(), job_name, "name", step_name).get("env")
        assert isinstance(environment, dict)
        assert environment["COUNCIL_RUN_ID"] == f"${{{{ {expression} }}}}"
