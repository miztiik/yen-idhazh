"""Does the gardener planner partition tasks and keep shard reads narrow?"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from gardener._garden import a_config
from support.paths import CONFIG_DIR, read_text

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.task_performance import TaskPerformanceRow
from idhazh.gardener import cli as gardener_cli
from idhazh.gardener import runner
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


def test_telemetry_proof_shards_pack_eligible_days_and_leave_current_receipts_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    root = a_config(
        tmp_path, *(CONFIG_DIR / "gardener" / f"{name}.json" for name in (
            "compact-feed-health", "compact-host-fingerprint", "compact-task-performance",
            "corpus-squash",
        )),
    )
    event = tmp_path / "dispatch.json"
    event.write_text('{"inputs":{"telemetry_proof":"true","force":"false"}}', encoding="ascii")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "off")
    settings = config.load_gardener(root)
    state = tmp_path / "state"
    day, current = "2026-11-24", "2026-11-26"
    wake = datetime.fromisoformat(f"{current}T00:40:00Z").astimezone(UTC)
    sha = "a" * 40
    raw: dict[tuple[LedgerName, str], Path] = {}
    expected: dict[LedgerName, HostFingerprintRow | TaskPerformanceRow] = {}
    for covers in (current, day):
        run_id = f"{covers}-1"
        host = HostFingerprintRow(
            version=HostFingerprintRow.schema_version(), date=covers, run_id=run_id,
            job=ServerJob.PLAN, shard=0, fingerprint="0123456789abcdef",
            fingerprint_version=1, measured_at=f"{covers}T00:01:00Z",
        )
        performance = TaskPerformanceRow(
            version="2026-11-25", date=covers, run_id=run_id, pipeline_name="digest",
            task_name="plan", shard=0, task_kind="workflow-task", outcome="success",
            elapsed_ms=27.5,
        )
        for which, row in (
            (LedgerName.HOST_FINGERPRINT, host), (LedgerName.TASK_PERFORMANCE, performance),
        ):
            (raw[which, covers],) = ledger.persist(
                state, [row], ledger=which, covers=covers, identity=WriterIdentity(
                    run_id=run_id, attempt=1, shard=0,
                    job=ServerJob.PLAN if isinstance(row, HostFingerprintRow) else None,
                    pipeline_name=row.pipeline_name, task_name=row.task_name,
                    producer="tests.telemetry_proof", git_sha=sha,
                ),
            )
            if covers == day:
                expected[which] = row

    assert gardener_shards.main(["--config-root", str(root)]) == 0
    outputs = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
    assert outputs["history_allowed"] == "false"
    matrix = json.loads(outputs["matrix"])["include"]
    assert matrix == [
        {"shard": 0, "task_names": ["compact-host-fingerprint"]},
        {"shard": 1, "task_names": ["compact-task-performance"]},
    ]

    parser = argparse.ArgumentParser()
    gardener_cli.add_the_run(parser)
    for leg in matrix:
        args = parser.parse_args([
            "--shard", str(leg["shard"]), "--run-id", f"{current}-2", "--attempt", "1",
        ])
        names, shard = gardener_publish.chosen_tasks(settings, args, parser)
        result = runner.run(
            names, settings=settings, repo_root=tmp_path, run_id=args.run_id, attempt=args.attempt,
            shard=shard, git_sha=sha, committed_folders=None, cone_bytes=None, listing=None,
            clock=lambda: wake,
        )
        assert result.exit_code == 0
        assert [task.task for task in result.finished_tasks] == leg["task_names"]

    for which, row in expected.items():
        packed = ledger.compact_path(state, which, Period.DAILY, day)
        assert ledger.load([packed], model=type(row)) == [row]
        index = CompactIndex.read(ledger.compact_index_path(state, which, Period.DAILY))
        assert [entry.covers for entry in index.period_entries] == [day]
        assert not raw[which, day].exists()
        assert raw[which, current].is_file()
