"""Does a wake split its active tasks into shards the same way every time, with none empty?

The split is round-robin over sorted task names, into the smaller of
`shards` and the number of tasks, and a shard checks out exactly the folders
its tasks own. These tests read a fixture garden of eleven declarations - every
status and every kind - so each rule is tested against the cases it has to
leave out as well as the ones it takes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from idhazh import config
from idhazh.config import GardenerSettings
from idhazh.contracts.knobs.gardener import TaskKind, TaskLifecycleStatus
from idhazh.gardener import shards

from ._garden import GARDENER_FIXTURES, a_config

pytestmark = pytest.mark.contract

#: The folders a cone may never be: a whole root that holds every ledger.
BARE_ROOTS = frozenset({"state", "state/raw", "state/compact"})


def the_garden(tmp_path: Path) -> GardenerSettings:
    return config.load_gardener(a_config(tmp_path, GARDENER_FIXTURES / "garden"))


def test_the_matrix_runs_every_active_task_but_history(tmp_path: Path) -> None:
    settings = the_garden(tmp_path)
    planned = shards.plan(settings)
    running = [name for shard in planned.shards for name in shard.task_names]

    expected = {
        name
        for name, policy in settings.tasks.items()
        if policy.lifecycle_status is TaskLifecycleStatus.ACTIVE and policy.kind != TaskKind.HISTORY
    }
    assert set(running) == expected
    assert len(running) == len(set(running)), "a task runs in two shards"
    assert {"history", "host-fingerprint", "day-validations"}.isdisjoint(running)


def test_the_split_is_round_robin_over_sorted_names(tmp_path: Path) -> None:
    """Eight tasks into five shards: the first three shards take two, the last two take one."""
    planned = shards.plan(the_garden(tmp_path))

    assert planned.shard_count == 5
    assert [shard.task_names for shard in planned.shards] == [
        ("compact-gardener", "traces"),
        ("feed-health", "trials"),
        ("scores", "workflow-artifacts"),
        ("seen",),
        ("telemetry-aggregate",),
    ]
    assert shards.fullest(planned) == planned.shards[0]


def test_fewer_tasks_than_shards_is_one_shard_a_task(tmp_path: Path) -> None:
    settings = config.load_gardener(a_config(tmp_path, GARDENER_FIXTURES / "runner"))
    planned = shards.plan(settings)
    assert planned.shard_count == len(settings.tasks) == 3
    assert all(len(shard.task_names) == 1 for shard in planned.shards)


def test_a_cone_is_what_its_tasks_own_and_the_complement_adds_nothing(tmp_path: Path) -> None:
    """Every owned folder is in exactly one shard's cone, and no cone is a whole root."""
    settings = the_garden(tmp_path)
    planned = shards.plan(settings)
    cones = {shard.index: shard.cone for shard in planned.shards}

    assert cones[1] == ("state/feed-health",), "the complement task added a folder"
    assert cones[2] == ("state/score-archive", "state/score-index", "state/scores")
    owned = [
        folder
        for shard in planned.shards
        for name in shard.task_names
        for folder in settings.tasks[name].owns or ()
    ]
    everywhere = [folder for cone in cones.values() for folder in cone]
    assert sorted(everywhere) == sorted(owned)
    assert BARE_ROOTS.isdisjoint(everywhere)


def test_an_empty_garden_is_the_empty_shape_on_one_line(tmp_path: Path) -> None:
    """No folder of declarations is no tasks, and the workflow still reads every key."""
    config_dir = a_config(tmp_path)
    (config_dir / "gardener").rmdir()

    planned = shards.plan(config.load_gardener(config_dir))

    assert shards.payload(planned) == (
        '{"any_active_task":false,"matrix":{"include":[]},"shard_count":0,"shards":[]}'
    )
    assert shards.fullest(planned) is None
