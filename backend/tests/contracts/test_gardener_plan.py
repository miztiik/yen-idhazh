"""Do both writers of the gardener's plan emit one payload, and does the payload hold together?

The plan job runs `backend/utilities/gardener_shards.py` with nothing of ours
installed; `idhazh gardener plan-shards` reads the same files through the typed
loader. Two writers of one payload are two chances to disagree, so they are
held to the same bytes for the same fixture config, and the payload is held to
the model that declares it.

The script is also run the way the plan job runs it - a fresh interpreter with
no site packages, in a folder holding only `config/`, the script and the module
it prints a crash with - so an import of anything outside the standard library
fails here first.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from gardener._garden import GARDENER_FIXTURES, a_config
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.gardener_plan import GardenerPlan, MatrixLeg
from idhazh.gardener import shards
from utilities import gardener_shards

pytestmark = pytest.mark.contract

SCRIPT = REPO_ROOT / "backend" / "utilities" / "gardener_shards.py"
EMPTY = '{"any_active_task":false,"matrix":{"include":[]},"shard_count":0,"shards":[]}'


def a_fixture_config(root: Path, garden: str | None) -> Path:
    config_dir = a_config(root, *([GARDENER_FIXTURES / garden] if garden else []))
    if garden is None:
        (config_dir / "gardener").rmdir()
    return config_dir


@pytest.mark.parametrize("garden", ["garden", "runner", None])
def test_both_writers_emit_one_payload_and_it_validates(tmp_path: Path, garden: str | None) -> None:
    config_dir = a_fixture_config(tmp_path, garden)

    typed = shards.payload(shards.plan(config.load_gardener(config_dir)))
    plain = gardener_shards.payload(gardener_shards.plan(config_dir))

    assert plain == typed
    reread = GardenerPlan.model_validate_json(plain)
    assert shards.payload(reread) == plain, "the payload does not survive its own model"
    assert "\n" not in plain


def test_the_script_runs_with_the_standard_library_alone(tmp_path: Path) -> None:
    """A fresh interpreter, no site packages, and `config/` with the script and what it reaches.

    Beside the script are the two files of its folder that the plan job's
    checkout holds and the script imports as it starts: the package file and the
    crash trace.
    """
    bare = tmp_path / "bare"
    config_dir = a_fixture_config(bare, "garden")
    script = bare / "backend" / "utilities" / SCRIPT.name
    script.parent.mkdir(parents=True)
    for name in ("__init__.py", "crash_trace.py", SCRIPT.name):
        shutil.copyfile(SCRIPT.parent / name, script.parent / name)
    expected = shards.payload(shards.plan(config.load_gardener(config_dir)))

    def ran(*flags: str) -> str:
        done = subprocess.run(
            [sys.executable, "-I", "-S", str(script), *flags],
            cwd=bare,
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, done.stderr
        return done.stdout.strip()

    assert ran("--json") == expected
    outputs = dict(line.split("=", 1) for line in ran().splitlines())
    assert outputs["any_active_task"] == "true"
    assert outputs["shard_count"] == "5"
    assert json.loads(outputs["matrix"]) == json.loads(expected)["matrix"]


def test_an_empty_garden_is_one_line_from_both_writers(tmp_path: Path) -> None:
    config_dir = a_fixture_config(tmp_path, None)
    assert gardener_shards.payload(gardener_shards.plan(config_dir)) == EMPTY
    assert gardener_shards.outputs(gardener_shards.plan(config_dir)) == [
        "any_active_task=false",
        "shard_count=0",
        'matrix={"include":[]}',
    ]


def test_both_loaders_ignore_unnamed_declarations(tmp_path: Path) -> None:
    config_dir = a_fixture_config(tmp_path, "garden")
    before = gardener_shards.payload(gardener_shards.plan(config_dir))
    (config_dir / "gardener/unnamed.json").write_bytes(b"\xff")
    assert gardener_shards.payload(gardener_shards.plan(config_dir)) == before
    assert shards.payload(shards.plan(config.load_gardener(config_dir))) == before


@pytest.mark.parametrize("failure", ["missing", "duplicate"])
def test_both_loaders_refuse_bad_named_lists(tmp_path: Path, failure: str) -> None:
    config_dir = a_fixture_config(tmp_path, "garden")
    knobs_path = config_dir / "idhazh_gardener.json"
    knobs = json.loads(knobs_path.read_text(encoding="utf-8"))
    name = knobs["task_names"][0]
    if failure == "missing":
        (config_dir / "gardener" / f"{name}.json").unlink()
        expected = "is missing"
    else:
        knobs["task_names"].append(name)
        knobs_path.write_text(json.dumps(knobs), encoding="ascii", newline="\n")
        expected = "repeats a task"
    with pytest.raises(ValueError, match=expected):
        gardener_shards.plan(config_dir)
    with pytest.raises(ValueError, match=expected):
        config.load_gardener(config_dir)


def _a_plan() -> dict[str, object]:
    return {
        "any_active_task": True,
        "shard_count": 2,
        "shards": [
            {"index": 0, "task_names": ["seen"]},
            {"index": 1, "task_names": ["traces"]},
        ],
        "matrix": {
            "include": [
                {"shard": 0, "task_names": ["seen"]},
                {"shard": 1, "task_names": ["traces"]},
            ]
        },
    }


@pytest.mark.parametrize(
    ("change", "refusal"),
    [
        ({"shard_count": 3}, "shard_count is 3"),
        ({"any_active_task": False}, "any_active_task"),
        ({"matrix": {"include": [{"shard": 0, "task_names": ["seen"]}]}}, "one leg per shard"),
        (
            {
                "matrix": {
                    "include": [
                        {"shard": 0, "task_names": ["seen"]},
                        {"shard": 1, "task_names": ["seen"]},
                    ]
                }
            },
            "tasks its shard runs",
        ),
        (
            {
                "shards": [
                    {"index": 0, "task_names": ["seen"]},
                    {"index": 2, "task_names": ["traces"]},
                ]
            },
            "numbered from 0",
        ),
        (
            {
                "shards": [
                    {"index": 0, "task_names": ["seen"]},
                    {"index": 1, "task_names": ["seen"]},
                ],
                "matrix": {
                    "include": [
                        {"shard": 0, "task_names": ["seen"]},
                        {"shard": 1, "task_names": ["seen"]},
                    ]
                },
            },
            "never two",
        ),
    ],
)
def test_a_plan_that_disagrees_with_itself_is_refused(
    change: dict[str, object], refusal: str
) -> None:
    GardenerPlan.model_validate(_a_plan())
    with pytest.raises(ValidationError, match=refusal):
        GardenerPlan.model_validate(_a_plan() | change)


def test_a_shard_with_no_task_is_refused() -> None:
    empty = _a_plan()
    empty["shards"] = [
        {"index": 0, "task_names": []},
        {"index": 1, "task_names": ["traces"]},
    ]
    with pytest.raises(ValidationError, match="at least 1"):
        GardenerPlan.model_validate(empty)


@pytest.mark.parametrize(
    ("task_names", "refusal"), [([], "at least 1"), (["traces", "seen"], "sorted order")]
)
def test_a_leg_lists_its_tasks_in_sorted_order_and_never_none(
    task_names: list[str], refusal: str
) -> None:
    """One deal always gives one job name, and a job named for no task says nothing."""
    MatrixLeg.model_validate({"shard": 0, "task_names": ["seen", "traces"]})
    with pytest.raises(ValidationError, match=refusal):
        MatrixLeg.model_validate({"shard": 0, "task_names": task_names})
