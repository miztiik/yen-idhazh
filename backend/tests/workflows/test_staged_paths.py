"""Which paths does a run stage, do they exist in a fresh checkout, and which may force-push?"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from typing import cast

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh import ledger
from idhazh.telemetry.publish import series

from ._harness import (
    COMMIT_STAGED_PATHS,
    COMMIT_STEPS,
    CORPUS_SEED,
    HARVEST_COMMAND,
    HARVEST_STEP,
    PRUNE_PUSH_MODULE,
    PRUNE_PUSH_STEP,
    REVIEW_ARTIFACT,
    REVIEW_COMMAND,
    REVIEW_STEP,
    SQUASH_DUE_MODULE,
    SUBSTITUTED_DATE,
    SUBSTITUTED_DAY_DIR,
    TOLERATED,
    _artifact_upload,
    _commit_call,
    _job,
    _load_workflows,
    _mapping,
    _normalize_condition,
    _script,
    _step,
    _steps,
    _triggers,
)

pytestmark = pytest.mark.workflow

#: A push that replaces a branch rather than adding to it. `-f` as well as
#: `--force`, because the short spelling does the same thing and a check that
#: only read the long one would be a rule about typing.
FORCE_PUSH = re.compile(r"push\s+(--force|-f)\b")

#: What separates two words in a command line, in either language a runner
#: executes. A shell writes `git push --force`; Python writes the same command
#: as a list, so the two words arrive quoted and comma-separated. Flattening the
#: punctuation is what lets one rule read both, and it is why the rule survived
#: the day the prune's push stopped being a shell script.
ARGUMENT_PUNCTUATION = re.compile(r"[^\w./-]+")


def test_the_harvest_runs_where_the_article_text_still_is() -> None:
    """A corpus built anywhere else is a corpus of nothing.

    `backend/var/run/<date>/items/` is gitignored and travels as a one-day
    artifact, so a workflow of its own would check out a fresh tree and find an
    empty directory - and it would report success while doing it. The step
    therefore sits in the job that already downloaded that artifact, between the
    publish that proves the day and the commit that pushes it.
    """
    workflow = _load_workflows()["digest.yml"]
    names = [step.get("name") for step in _steps(workflow, "assemble")]
    step = _step(workflow, "assemble", "name", HARVEST_STEP)

    assert HARVEST_COMMAND in _script(step, "assemble harvest step")
    assert step.get("continue-on-error") == TOLERATED, (
        "a corpus that will not build must never be what stops a reader getting the day"
    )
    assert (
        names.index("Assemble and publish")
        < names.index(HARVEST_STEP)
        < names.index(COMMIT_STEPS["assemble"])
    )


def test_the_review_tree_is_an_artifact_and_no_commit_step_can_reach_it() -> None:
    """The row's oracle, asked of the workflow: a review surface never becomes a published one.

    Three separate things have to hold, and the third is the one that could go
    wrong quietly. The tree is written under `backend/var/`, which `.gitignore`
    covers, so no diff would ever show it drifting into the published tree. So
    the assertion is that no path any commit step stages names it, taken over
    every staged path in the file rather than over the assemble job alone.
    """
    workflow = _load_workflows()["digest.yml"]
    step = _step(workflow, "assemble", "name", REVIEW_STEP)
    assert REVIEW_COMMAND in _script(step, "assemble review step")

    upload = _artifact_upload(workflow, "assemble", REVIEW_ARTIFACT)
    with_block = _mapping(upload.get("with"), "review upload")
    path = str(with_block["path"])
    assert path.startswith("backend/var/review/"), (
        "the review tree is a build artifact; a path outside backend/var/ is one git can see"
    )
    assert int(str(with_block["retention-days"])) > 0
    assert upload.get("if") == "always()", (
        "the step above may have degraded, and a partial sheet is still worth looking at"
    )

    staged: list[str] = []
    for label in COMMIT_STEPS:
        paths, settings = _commit_call(label)
        staged += paths
        staged += [settings.get("REFRESH_PATHS", "")]
    assert staged, "no commit step declares a staged path, so this test proves nothing"
    for value in staged:
        assert "review" not in value, f"a commit step stages the review tree: {value}"


def test_the_corpus_is_committed_but_never_rebuilt() -> None:
    """The window records what a run saw. It is not derived from origin's tip.

    So it is staged by the commit step and deliberately absent from the refresh
    set: on a lost race the answer is to replay this run's rows onto the new
    base, which is what the rebase already does, and never to run a producer
    again over articles the new checkout cannot see.
    """
    staged, settings = _commit_call("assemble")

    assert "corpus" in staged
    assert "corpus" not in settings["REFRESH_PATHS"].split()
    assert "corpus" not in settings["REGENERATE_COMMAND"].split()


def test_every_path_the_day_stages_exists_in_a_fresh_checkout() -> None:
    """`git add "$@"` runs under `set -euo pipefail`.

    A staged path that only appears once its producer succeeded therefore aborts
    the whole commit step, and takes every sibling ledger staged in the same call
    with it. The seed is what makes the corpus path safe to name.

    Every path the step names is asked of the working tree, so a root added to
    the list without a committed file in it fails here rather than on the runner.
    The console payload roots are the five that still have a producer: each ships
    with the shard the producer wrote, which is the same pattern a seeded header
    takes. `scores` and `feed-health` were two more
    until 2026-09-16, and they are why the list is derived from
    `series.PUBLISHED_ROOTS` rather than written out here - a root deleted in one
    place has to leave the staging call in the same commit, or the next run's
    `git add` aborts and takes every sibling ledger with it.
    """
    for relative in CORPUS_SEED:
        assert (REPO_ROOT / relative).is_file(), f"{relative} must be committed, even when empty"
    for relative in COMMIT_STAGED_PATHS["assemble"]:
        assert (REPO_ROOT / relative).exists(), f"{relative} must be in a fresh checkout"
    for dirname in series.PUBLISHED_ROOTS:
        root = REPO_ROOT / "frontend" / "public" / dirname
        assert root.is_dir(), f"frontend/public/{dirname} must be in a fresh checkout"
        committed = subprocess.run(
            ["git", "ls-files", f"frontend/public/{dirname}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert committed, f"frontend/public/{dirname} must hold at least one committed file"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", *CORPUS_SEED],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode == 0, tracked.stderr.strip()


def test_every_path_the_plan_stages_exists_in_a_fresh_checkout() -> None:
    """`git add` runs under `set -euo pipefail`, so a path that is not there ends the step.

    The list became `state` whole on 2026-09-17, when the catch-up compaction
    joined this job. It folds a segment into whichever head that segment's own
    rows name, so what the job writes is not knowable when a list is written -
    and a hand-listed set would commit the segment deletions while leaving the
    heads behind. Naming the directory answers this test's own rule at the same
    time: `state` is in every checkout, and a collection inside it need not be.

    The feed retirements needed a header-only file of their own while they were
    a CSV, because every run read the file and almost none wrote to it. They
    moved under `state/raw/` on 2026-09-28, where a folder that is not there yet
    reads as no retirements at all, so the seed went with them.
    """
    named = COMMIT_STAGED_PATHS["plan"]
    assert named == [ledger.STATE_DIRNAME]
    for relative in named:
        assert (REPO_ROOT / relative).exists(), f"{relative} must be in a fresh checkout"


def test_the_corpus_is_not_union_merged() -> None:
    """A rolling window is not an append-only ledger.

    Asked of git rather than of a pattern matcher written here. Unioning two
    rolls produces a file that carries evicted rows again and sits above
    `finetune.corpus_rows`, which is the one shape this file must never take.
    """
    answered = subprocess.run(
        ["git", "check-attr", "merge", "--", *CORPUS_SEED],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert answered == [f"{path}: merge: unspecified" for path in CORPUS_SEED]


def test_only_the_scheduled_prune_may_force_push() -> None:
    """The single exception in `CLAUDE.md` section 8, held closed-world.

    Discovery is over every source a runner executes - every workflow body,
    every shipped script, and every Python program under `backend/` - so a
    second forcing push fails here whoever adds it and wherever they put it.

    One file is named rather than none. The squash's push moved out of the
    workflow so a test could drive it against a real repository and watch it
    refuse a tip that moved, and the forcing flag moved with it.
    """
    forcing: set[str] = set()
    for filename, workflow in _load_workflows().items():
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            for step in _steps(workflow, job_name):
                script = step.get("run")
                if isinstance(script, str) and FORCE_PUSH.search(script):
                    forcing.add(f"{filename} step {step.get('name')}")
    executable = (
        *(REPO_ROOT / "backend" / "utilities").glob("*.py"),
        *(REPO_ROOT / "backend" / "idhazh").rglob("*.py"),
    )
    assert executable, "nothing was read, so this is checking nothing"
    for path in sorted(executable):
        if FORCE_PUSH.search(ARGUMENT_PUNCTUATION.sub(" ", read_text(path))):
            forcing.add(path.name)

    assert forcing == {PRUNE_PUSH_MODULE.name}


def test_the_prune_reads_both_its_numbers_from_config() -> None:
    """The cadence is a config value, so it cannot be a cron line.

    `on.schedule` is parsed before any step runs, so nothing in `config/` can
    reach it, and 5-field cron has no every-N-days field to write one with. The
    daily cron is the wake-up; this step is the schedule. Run against the real
    committed declaration, so a renamed knob fails here.
    """
    workflow = _load_workflows()["idhazh-gardener.yml"]
    step = _step(workflow, "history", "id", "due")
    assert "backend/utilities/corpus_squash_due.py" in _script(step, "history due step")
    done = subprocess.run(
        [sys.executable, str(SQUASH_DUE_MODULE)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    outputs = dict(line.split("=", 1) for line in done.stdout.splitlines() if "=" in line)
    declared = json.loads(read_text(CONFIG_DIR / "gardener" / "corpus-squash.json"))
    keep_days = declared["window"]["value"]

    assert outputs["due"] in {"true", "false"}
    assert outputs["keep_days"] == str(keep_days)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", outputs["today"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", outputs["boundary"])
    assert (
        datetime.date.fromisoformat(outputs["today"])
        - datetime.date.fromisoformat(outputs["boundary"])
    ).days == keep_days

    schedule = _triggers(workflow)["schedule"]
    assert isinstance(schedule, list) and len(schedule) == 1
    cron = _mapping(cast(list[object], schedule)[0], "gardener cron")["cron"]
    assert isinstance(cron, str)
    assert "*/" not in cron, (
        "a step-value cron is not an every-N-days cadence: */30 fires on the 1st and 31st"
    )


def test_the_prune_only_clones_the_whole_history_when_it_is_due() -> None:
    """29 wakes out of 30 read one committed file and stop.

    The deep fetch, the Python setup, the install and the push are each gated on
    the same output, so a repository nobody is pruning costs a shallow checkout a
    day rather than a full clone a day. Both checkouts take `main` as it is now,
    because the gardener's shards push before this job starts: a rewrite of the
    commit the run was created at would find `main` moved and refuse every time.
    """
    workflow = _load_workflows()["idhazh-gardener.yml"]
    steps = _steps(workflow, "history")
    checkouts = [
        _mapping(step.get("with"), "checkout with")
        for step in steps
        if isinstance(step.get("uses"), str)
        and cast(str, step.get("uses")).startswith("actions/checkout@")
    ]
    depths = [checkout.get("fetch-depth") for checkout in checkouts]

    assert depths == ["1", "0"], "a shallow read first, and the full history only when due"
    assert [checkout.get("ref") for checkout in checkouts] == ["main", "main"], (
        "the history job checks out main as the shards left it, not the run's own commit"
    )
    gated = [
        _normalize_condition(step["if"], "history step condition")
        for step in steps
        if "if" in step
    ]
    assert gated.count("steps.due.outputs.due == 'true'") == len(gated) - 1
    for step in steps:
        if step.get("name") == PRUNE_PUSH_STEP:
            assert _normalize_condition(step["if"], "push condition") == (
                "steps.due.outputs.due == 'true'"
            )
            break
    else:
        pytest.fail("the prune must have a push step")


def test_the_plan_job_publishes_the_day_directory_it_decided() -> None:
    """The refresh set has to name two files inside the day, so the run says where it is."""
    workflow = _load_workflows()["digest.yml"]
    script = _script(_step(workflow, "plan", "id", "decide"), "plan decide step")
    outputs = _mapping(_job(workflow, "plan").get("outputs"), "plan outputs")

    assert outputs.get("day_dir") == "${{ steps.decide.outputs.day_dir }}"
    assert 'echo "day_dir=frontend/public/digest/${DATE//-//}" >> "$GITHUB_OUTPUT"' in [
        line.strip() for line in script.splitlines()
    ]
    # The expansion above, evaluated the way bash would.
    assert f"frontend/public/digest/{SUBSTITUTED_DATE.replace('-', '/')}" == SUBSTITUTED_DAY_DIR
