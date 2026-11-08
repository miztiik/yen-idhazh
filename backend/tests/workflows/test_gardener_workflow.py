"""Does the gardener planner partition tasks and keep shard reads narrow?"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.paths import CONFIG_DIR, read_text

from idhazh import config, ledger
from idhazh.ledger.paths import COMPACT_DIRNAME, RAW_DIRNAME
from utilities import gardener_publish, gardener_shards

pytestmark = pytest.mark.workflow

TASK_FILES = ("compact-feed-health.json", "traces.json", "corpus-squash.json")
BARE_ROOTS = frozenset(
    {
        ledger.STATE_DIRNAME,
        f"{ledger.STATE_DIRNAME}/{RAW_DIRNAME}",
        f"{ledger.STATE_DIRNAME}/{COMPACT_DIRNAME}",
    }
)


def a_config_with_shards(root: Path, shards: int) -> Path:
    config_dir = root / "config"
    (config_dir / "gardener" / "config").mkdir(parents=True, exist_ok=True)
    for filename in TASK_FILES:
        (config_dir / "gardener" / filename).write_text(
            read_text(CONFIG_DIR / "gardener" / filename), encoding="ascii", newline="\n"
        )
    for filename in ("idhazh.json", "ledgers.json", "appearance.json"):
        (config_dir / filename).write_text(
            read_text(CONFIG_DIR / filename), encoding="ascii", newline="\n"
        )
    knobs = json.loads(read_text(CONFIG_DIR / "gardener/config/idhazh_gardener.json"))
    knobs["shards"] = shards
    knobs["task_names"] = [Path(filename).stem for filename in TASK_FILES]
    (config_dir / "gardener/config/idhazh_gardener.json").write_text(
        json.dumps(knobs), encoding="ascii", newline="\n"
    )
    return config_dir


def test_every_shard_count_the_planner_can_run_is_a_partition_of_tasks(
    tmp_path: Path,
) -> None:
    declared = gardener_shards.declarations(a_config_with_shards(tmp_path / "declared", 1))
    tasks = {
        name
        for name, held in declared.items()
        if held["lifecycle_status"] == "active" and held["kind"] != "history"
    }
    assert tasks
    for shards in range(1, len(tasks) + 2):
        planned = gardener_shards.plan(a_config_with_shards(tmp_path / str(shards), shards))
        dealt = [list(shard["task_names"]) for shard in planned["shards"]]
        assert all(dealt)
        placed = [name for held in dealt for name in held]
        assert sorted(placed) == sorted(tasks)
        assert planned["shard_count"] == min(shards, len(tasks)) == len(dealt)
        legs = planned["matrix"]["include"]
        assert [leg["shard"] for leg in legs] == [shard["index"] for shard in planned["shards"]]


def test_a_shard_lists_task_owned_folders_and_never_a_whole_root(tmp_path: Path) -> None:
    config_root = a_config_with_shards(tmp_path, 2)
    settings = config.load_gardener(config_root)
    planned = gardener_shards.plan(config_root)
    shard_of_folder: dict[str, int] = {}
    for shard in planned["shards"]:
        owned, read = gardener_publish.declared_folders(shard["task_names"], settings)
        named = [settings.tasks[name] for name in shard["task_names"]]
        assert {*owned, *read} == {
            folder for policy in named for folder in (*(policy.owns or ()), *policy.reads)
        }
        for folder in owned:
            assert folder not in shard_of_folder
            shard_of_folder[folder] = shard["index"]
        assert BARE_ROOTS.isdisjoint([*owned, *read])
    assert shard_of_folder
