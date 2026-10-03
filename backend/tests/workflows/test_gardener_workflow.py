"""Does the gardener's workflow run every task once, in a checkout its readers fit inside?

Everything here reads the named workflow and three named declarations copied
into a temporary config, and nothing runs a workflow. What is decidable from those files
is decided here: that the matrix can only ever produce a partition of the
tasks, that every job the workflow spells is a job a record can name, that the
plan job's sparse checkout holds every folder its reader opens, that only the
history job takes the whole history, and that each job holds only the
permissions it uses. Whether five shards pushing at once land is not decidable
here; the first scheduled run's records answer it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Final, cast

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.ledger.paths import COMPACT_DIRNAME, RAW_DIRNAME
from utilities import gardener_publish, gardener_shards

from ._harness import (
    WORKFLOWS_DIR,
    _job,
    _load_workflows,
    _mapping,
    _normalize_condition,
    _script,
    _step,
    _steps,
    _string_list,
)

pytestmark = pytest.mark.workflow

WORKFLOW: Final = "idhazh-gardener.yml"

#: The three jobs, in the order a wake reaches them.
PLAN, RUN_TASKS, HISTORY = "plan", "run-tasks", "history"

#: The program the plan job runs before anything of ours is installed.
PLANNER: Final = REPO_ROOT / "backend" / "utilities" / "gardener_shards.py"

#: The person's gate on the history job, word for word and wrapper included:
#: after every shard, whatever the shards did, unless the run was cancelled.
#: Without `${{ }}` the `!` would open a YAML tag. The person's ruling, 2026-09-29.
HISTORY_GATE: Final = "${{ !cancelled() }}"

#: The folders a shard may never list for a task: a whole root that holds every ledger.
BARE_ROOTS: Final = frozenset(
    {
        ledger.STATE_DIRNAME,
        f"{ledger.STATE_DIRNAME}/{RAW_DIRNAME}",
        f"{ledger.STATE_DIRNAME}/{COMPACT_DIRNAME}",
    }
)

# Two active tasks exercise partitioning; history exercises exclusion from it.
TASK_FILES: Final = ("feed-health.json", "traces.json", "corpus-squash.json")


def gardener() -> dict[str, object]:
    return _load_workflows()[WORKFLOW]


def _checkouts(workflow: dict[str, object], job: str) -> list[dict[str, object]]:
    """The `with` block of every `actions/checkout` step in one job, in order."""
    return [
        _mapping(step.get("with") or {}, f"{job} checkout with")
        for step in _steps(workflow, job)
        if isinstance(step.get("uses"), str)
        and cast(str, step.get("uses")).startswith("actions/checkout@")
    ]


def _sparse(checkout: dict[str, object]) -> list[str]:
    return [line for line in str(checkout["sparse-checkout"]).splitlines() if line]


def a_config_with_shards(root: Path, shards: int) -> Path:
    """Three named declarations, with the gardener's `shards` set to this."""
    config_dir = root / "config"
    (config_dir / "gardener").mkdir(parents=True, exist_ok=True)
    for filename in TASK_FILES:
        (config_dir / "gardener" / filename).write_text(
            read_text(CONFIG_DIR / "gardener" / filename), encoding="ascii", newline="\n"
        )
    for filename in ("idhazh.json", "appearance.json"):
        (config_dir / filename).write_text(
            read_text(CONFIG_DIR / filename), encoding="ascii", newline="\n"
        )
    knobs = json.loads(read_text(CONFIG_DIR / "idhazh_gardener.json"))
    knobs["shards"] = shards
    knobs["task_names"] = [Path(filename).stem for filename in TASK_FILES]
    (config_dir / "idhazh_gardener.json").write_text(
        json.dumps(knobs), encoding="ascii", newline="\n"
    )
    return config_dir


def test_every_shard_count_the_matrix_can_run_is_a_partition_of_the_tasks(tmp_path: Path) -> None:
    """Each active fixture task is in exactly one shard, and none is empty.

    Swept over every shard count from one to one past the number of tasks, so a
    change to the split is held at the boundaries, not at a growing production
    task count.
    """
    declared = gardener_shards.declarations(a_config_with_shards(tmp_path / "declared", 1))
    tasks = {
        name
        for name, held in declared.items()
        if held["lifecycle_status"] == "active" and held["kind"] != "history"
    }
    assert tasks, "nothing is declared active, so this checks nothing"
    for shards in range(1, len(tasks) + 2):
        planned = gardener_shards.plan(a_config_with_shards(tmp_path / str(shards), shards))
        dealt = [list(shard["task_names"]) for shard in planned["shards"]]
        assert all(dealt), f"at {shards} shards a shard runs no task"
        placed = [name for held in dealt for name in held]
        assert sorted(placed) == sorted(tasks), f"at {shards} shards a task is missing or twice"
        assert planned["shard_count"] == min(shards, len(tasks)) == len(dealt)
        legs = planned["matrix"]["include"]
        assert [leg["shard"] for leg in legs] == [shard["index"] for shard in planned["shards"]]


def test_a_shard_lists_what_its_tasks_own_or_read_and_never_a_whole_root(tmp_path: Path) -> None:
    """Every owned folder is listed by the one shard that runs its owner, and none is a root.

    A shard checks out none of these folders: it lists their files from the
    commit. A whole root here would list every ledger's files for one task.
    """
    config_root = a_config_with_shards(tmp_path, 2)
    settings = config.load_gardener(config_root)
    planned = gardener_shards.plan(config_root)
    owner: dict[str, int] = {}
    for shard in planned["shards"]:
        owned, read = gardener_publish.declared_folders(shard["task_names"], settings)
        named = [settings.tasks[name] for name in shard["task_names"]]
        assert {*owned, *read} == {
            folder for policy in named for folder in (*(policy.owns or ()), *policy.reads)
        }
        for folder in owned:
            assert folder not in owner, f"{folder} is owned in two shards"
            owner[folder] = shard["index"]
        assert BARE_ROOTS.isdisjoint([*owned, *read])
    assert owner, "no shard owns a folder, so this checks nothing"


def test_every_job_the_workflow_spells_is_a_job_a_record_can_name() -> None:
    """A job id is what a record's `job` column and a file's writer carry, so it is closed."""
    workflow = gardener()
    jobs = _mapping(workflow.get("jobs"), "jobs")
    spelled = set(jobs)
    for name in jobs:
        needs = _job(workflow, name).get("needs")
        if isinstance(needs, str):
            spelled.add(needs)
        elif needs is not None:
            spelled |= set(_string_list(needs, f"{name} needs"))
    assert spelled == {PLAN, RUN_TASKS, HISTORY}
    assert spelled <= {job.value for job in ServerJob}
    assert (ServerJob.RUN_TASKS.value, ServerJob.HISTORY.value) == (RUN_TASKS, HISTORY)


def _what_the_planner_opens(tmp_path: Path) -> list[str]:
    """Every file the committed planner opens and every folder it lists, run as the plan job runs it.

    A fresh interpreter with no site packages, in a test-built tree, against the
    named config inputs, with an audit hook recording each `open` and each folder
    listing. Paths inside the interpreter's own installation are left out.
    """
    trace = tmp_path / "opened.json"
    a_config_with_shards(tmp_path, 2)
    driver = (
        "import json, os, runpy, sys\n"
        "seen = []\n"
        "def hook(event, args):\n"
        "    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):\n"
        "        seen.append(os.fsdecode(args[0]))\n"
        "    elif event in ('os.scandir', 'os.listdir') and args and args[0] is not None:\n"
        "        seen.append(os.fsdecode(args[0]))\n"
        "sys.addaudithook(hook)\n"
        f"sys.argv = [{str(PLANNER)!r}, '--json']\n"
        "try:\n"
        f"    runpy.run_path({str(PLANNER)!r}, run_name='__main__')\n"
        "except SystemExit as done:\n"
        "    assert not done.code, done.code\n"
        "opened = list(seen)\n"
        f"with open({str(trace)!r}, 'w', encoding='utf-8') as out:\n"
        "    out.write(json.dumps(opened))\n"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-S", "-c", driver],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={key: value for key, value in os.environ.items() if not key.startswith("PYTHON")},
    )
    assert done.returncode == 0, done.stderr
    installed = [Path(prefix).resolve() for prefix in {sys.prefix, sys.base_prefix}]
    opened: list[str] = []
    for raw in json.loads(trace.read_text(encoding="utf-8")):
        path = Path(raw) if Path(raw).is_absolute() else tmp_path / raw
        resolved = path.resolve()
        if any(resolved.is_relative_to(prefix) for prefix in installed):
            continue
        if resolved.is_relative_to(REPO_ROOT.resolve()):
            opened.append(resolved.relative_to(REPO_ROOT.resolve()).as_posix())
        elif resolved.is_relative_to(tmp_path.resolve()):
            opened.append(resolved.relative_to(tmp_path.resolve()).as_posix())
    return opened


def test_the_plan_jobs_checkout_holds_every_folder_its_reader_opens(tmp_path: Path) -> None:
    """The gate the plan was missing, both sides computed rather than listed by hand.

    The cone comes from the committed workflow, and what the reader opens comes
    from running the committed reader. A reader that drifted outside its own
    checkout would find nothing there on the runner, answer "no tasks" and
    report success - so this fails first, here.
    """
    (checkout,) = _checkouts(gardener(), PLAN)
    cone = _sparse(checkout)
    assert (str(checkout["fetch-depth"]), checkout["filter"]) == ("1", "blob:none")

    opened = _what_the_planner_opens(tmp_path)

    assert any(path.startswith("config/gardener") for path in opened), (
        "the reader opened no declaration, so this checks nothing"
    )
    outside = [
        path
        for path in opened
        if "/" in path
        and not any(
            PurePosixPath(path).is_relative_to(PurePosixPath(folder)) for folder in cone
        )
    ]
    assert not outside, (
        f"the plan job's reader opens {outside[0]}, which its sparse checkout {cone} never "
        "writes, so on the runner it would read nothing there"
    )


def test_among_jobs_that_may_push_only_the_history_jobs_second_checkout_is_a_full_clone() -> None:
    """A job that commits and takes the whole history pays for a clone it does not use.

    The history job takes one on purpose: it rewrites every commit. Jobs that
    never push, such as CI's two full clones, are outside the rule, which is
    about a job that commits.
    """
    full: list[tuple[str, str, int]] = []
    for filename, workflow in _load_workflows().items():
        for job in _mapping(workflow.get("jobs"), "jobs"):
            granted = _job(workflow, job).get("permissions", workflow.get("permissions"))
            pushes = granted == "write-all" or (
                isinstance(granted, dict) and granted.get("contents") == "write"
            )
            if not pushes:
                continue
            for position, checkout in enumerate(_checkouts(workflow, job)):
                if str(checkout.get("fetch-depth")) == "0":
                    full.append((filename, job, position))
    assert full == [(WORKFLOW, HISTORY, 1)]


def test_each_job_holds_only_the_permissions_it_uses() -> None:
    """A job's `permissions` replace the workflow's, so each one names its whole set.

    The shards push their records and list, and once live delete, GitHub's
    artifacts and runs. The history job rewrites `main` and calls no Actions
    API, so the one job that force-pushes holds no permission it never calls.
    """
    workflow = gardener()
    assert workflow.get("permissions") == {"contents": "read"}
    assert _job(workflow, PLAN).get("permissions") == {"contents": "read"}
    assert _job(workflow, RUN_TASKS).get("permissions") == {
        "contents": "write",
        "actions": "write",
    }
    assert _job(workflow, HISTORY).get("permissions") == {"contents": "write"}


def test_the_shards_push_with_the_default_token_and_never_a_personal_one() -> None:
    """A push made with the default token starts no workflow, and the header says so.

    Five shard pushes a day that started CI would be five full CI runs a day. The
    guard is invisible in the file that depends on it, so the header states it
    and this reads both halves: no checkout names a token, and the one secret any
    step reads is the default one.
    """
    text = read_text(WORKFLOWS_DIR / WORKFLOW)
    assert "A push made with the default GITHUB_TOKEN starts no workflow" in text
    workflow = gardener()
    for job in (PLAN, RUN_TASKS, HISTORY):
        assert all("token" not in checkout for checkout in _checkouts(workflow, job)), job
    secrets = {
        part.split("}}")[0].strip()
        for part in text.split("${{")[1:]
        if part.strip().startswith("secrets.")
    }
    assert secrets == {"secrets.GITHUB_TOKEN"}
    step = _step(workflow, RUN_TASKS, "name", "Run the shard's tasks and land its record")
    assert _mapping(step.get("env"), "shard step env")["GITHUB_TOKEN"] == (
        "${{ secrets.GITHUB_TOKEN }}"
    )


def test_the_plan_job_runs_the_standard_library_planner_before_any_install() -> None:
    workflow = gardener()
    assert str(_job(workflow, PLAN)["timeout-minutes"]) == "5"
    steps = _steps(workflow, PLAN)
    assert not [step for step in steps if "setup-python" in str(step.get("uses", ""))]
    assert not [step for step in steps if "pip install" in str(step.get("run", ""))]
    assert "python3 backend/utilities/gardener_shards.py" in _script(
        _step(workflow, PLAN, "id", "shards"), "plan step"
    )
    outputs = _mapping(_job(workflow, PLAN).get("outputs"), "plan outputs")
    assert outputs == {
        "any_active_task": "${{ steps.shards.outputs.any_active_task }}",
        "shard_count": "${{ steps.shards.outputs.shard_count }}",
        "matrix": "${{ steps.shards.outputs.matrix }}",
        "run_id": "${{ steps.run.outputs.run_id }}",
    }


def test_a_shard_checks_out_only_its_code_and_runs_the_landing_program() -> None:
    """No folder a task owns or reads is checked out: its names come from the commit."""
    workflow = gardener()
    job = _job(workflow, RUN_TASKS)
    assert (job.get("needs"), str(job["timeout-minutes"])) == (PLAN, "20")
    assert _normalize_condition(job["if"], "run-tasks if") == (
        "needs.plan.outputs.any_active_task == 'true'"
    )
    strategy = _mapping(job.get("strategy"), "strategy")
    assert _mapping(strategy.get("matrix"), "matrix") == {
        "include": "${{ fromJSON(needs.plan.outputs.matrix).include }}"
    }
    assert str(strategy["fail-fast"]) == "false"
    assert strategy["max-parallel"] == "${{ fromJSON(needs.plan.outputs.shard_count) }}"

    steps = _steps(workflow, RUN_TASKS)
    (checkout,) = _checkouts(workflow, RUN_TASKS)
    assert _sparse(checkout) == ["config", "backend", ".github"]
    assert (str(checkout["fetch-depth"]), checkout["filter"]) == ("1", "blob:none")
    assert steps[1].get("run") == "git config index.sparse true", (
        "the index turns sparse right after the checkout, before any widening can expand it"
    )
    assert any(step.get("run") == "pip install -e ." for step in steps)

    landing = _step(workflow, RUN_TASKS, "name", "Run the shard's tasks and land its record")
    assert _script(landing, "shard step").split() == [
        "python",
        "backend/utilities/gardener_publish.py",
        "--shard",
        '"$SHARD"',
        "--run-id",
        '"$RUN_ID"',
        "--attempt",
        '"$ATTEMPT"',
    ]
    assert _mapping(landing.get("env"), "shard step env") == {
        "SHARD": "${{ matrix.shard }}",
        "RUN_ID": "${{ needs.plan.outputs.run_id }}",
        "ATTEMPT": "${{ github.run_attempt }}",
        "GITHUB_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
    }


def test_the_history_job_runs_last_and_unless_the_run_was_cancelled() -> None:
    """Every shard has ended before history is rewritten, and only a cancel stops the squash.

    A day no task is active and a day a shard failed both still squash. The
    condition is read as written rather than normalised, because the wrapper is
    what keeps the `!` from being read as a YAML tag.
    """
    job = _job(gardener(), HISTORY)
    assert job.get("needs") == [PLAN, RUN_TASKS]
    assert job["if"] == HISTORY_GATE
    assert str(job["timeout-minutes"]) == "30"


def test_the_workflow_names_no_task_the_matrix_runs(tmp_path: Path) -> None:
    """Adding a task is a declaration and never a workflow edit (decision 5).

    The one task outside the matrix is the history task, and its job is about
    it by design: it reads that declaration to decide whether the squash is due.
    """
    declared = gardener_shards.declarations(a_config_with_shards(tmp_path, 2))
    names = {name for name, held in declared.items() if held["kind"] != "history"}
    assert names, "nothing is declared, so this checks nothing"

    def strings(value: Any) -> list[str]:
        if isinstance(value, dict):
            return [text for key, held in value.items() for text in (str(key), *strings(held))]
        if isinstance(value, list):
            return [text for held in value for text in strings(held)]
        return [str(value)]

    spelled = " ".join(strings(gardener()))
    named = sorted(
        name for name in names if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", spelled)
    )
    assert not named, f"the workflow spells {named}, so adding a task would mean editing it"
