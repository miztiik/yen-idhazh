"""Does the plan's dispatch count survive fan-out, assembly and rebuilds?"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from pipeline._builders import isolate_ledgers, plan
from support.ledger import SEED_COMMIT
from support.paths import CONFIG_DIR

from idhazh import assemble, cli, config, ledger
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.run_shards import RunShards
from idhazh.fan_out import shard_count
from idhazh.stages import common
from idhazh.stages import plan as plan_stage
from idhazh.stages.assemble import stage_assemble

from ._harness import _evaluate_shard_matrix, _load_workflows, _step

pytestmark = pytest.mark.workflow


def _with_dispatch(source: RunPlan, *, execution: int, shards: int | None) -> RunPlan:
    return RunPlan.model_validate(
        {
            **source.model_dump(mode="json"),
            "run_id": f"{source.date}-{execution}",
            "shards": shards,
        }
    )


def _file_plan(plan: RunPlan, *, commit_sha: str) -> None:
    ledger.persist(
        common.STATE_ROOT,
        [plan],
        ledger=LedgerName.RUN_PLAN,
        covers=plan.date,
        identity=plan_stage.plan_writer(plan.run_id, commit_sha),
    )


def _assemble(plan: RunPlan, settings: config.Settings, *, regenerate_only: bool = False) -> None:
    stage_assemble(
        plan,
        settings=settings,
        commit_sha=SEED_COMMIT,
        runner="test-cpu",
        regenerate_only=regenerate_only,
    )


def _run_shard_file_count(date: str) -> int:
    return len(ledger.find_holding_files(common.STATE_ROOT, LedgerName.RUN_SHARDS, [date]))


def _settled_counts(date: str) -> dict[str, int | None]:
    rows = ledger.load_days(
        common.STATE_ROOT,
        LedgerName.RUN_SHARDS,
        [date],
        model=RunShards,
    )
    return {row.run_id: row.shards for row in rows}


def _manifest(date: str) -> RunManifest:
    return RunManifest.read(assemble.day_dir(common.PUBLIC_ROOT, date) / "run.json")


def _cut_plan(source: RunPlan, *, shards: int) -> RunPlan:
    kept = source.items[:1]
    counts = Counter(item.vertical for item in kept)
    payload = source.model_dump(mode="json")
    payload["items"] = [item.model_dump(mode="json") for item in kept]
    for vertical in payload["verticals"]:
        vertical["planned"] = counts.get(vertical["id"], 0)
    payload["shards"] = shards
    return RunPlan.model_validate(payload)


def test_dispatch_count_reaches_the_matrix_manifest_and_count_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    source = plan()
    settings = config.load(CONFIG_DIR)
    derived = shard_count(len(source.items), run=settings.app.run)
    dispatched = 8 if derived != 8 else 7
    recorded = _with_dispatch(source, execution=1, shards=dispatched)
    _file_plan(recorded, commit_sha=SEED_COMMIT)

    assert cli.main(["shards", "--date", recorded.date, "--execution", "1"]) == 0
    assert capsys.readouterr().out.strip() == str(dispatched)

    script = _step(_load_workflows()["digest.yml"], "plan", "id", "fanout").get("run")
    assert isinstance(script, str)
    assert _evaluate_shard_matrix(script, str(dispatched)) == list(range(dispatched))

    loaded = common._load_plan(recorded.date, recorded.run_id)
    _assemble(loaded, settings)
    assert _manifest(recorded.date).runs[-1].shards == dispatched
    assert _settled_counts(recorded.date) == {recorded.run_id: dispatched}

    count_files = _run_shard_file_count(recorded.date)
    _assemble(loaded, settings, regenerate_only=True)
    assert _run_shard_file_count(recorded.date) == count_files


def test_a_replanned_run_replaces_the_count_from_its_earlier_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    source = plan()
    settings = config.load(CONFIG_DIR)
    initial = _with_dispatch(source, execution=2, shards=3)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    _file_plan(initial, commit_sha=SEED_COMMIT)
    _assemble(common._load_plan(initial.date, initial.run_id), settings)
    previous_files = _run_shard_file_count(initial.date)

    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    cut = _cut_plan(_with_dispatch(source, execution=2, shards=3), shards=5)
    _file_plan(cut, commit_sha=SEED_COMMIT)
    loaded = common._load_plan(cut.date, cut.run_id)
    assert loaded.shards == 5
    assert [item.item_id for item in loaded.items] == [cut.items[0].item_id]

    _assemble(loaded, settings)
    assert _manifest(cut.date).runs[-1].shards == 5
    assert _settled_counts(cut.date) == {cut.run_id: 5}
    assert _run_shard_file_count(cut.date) == previous_files + 1


def test_a_missing_plan_count_stays_unknown_without_replacing_a_recorded_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    source = _with_dispatch(plan(), execution=3, shards=4)
    settings = config.load(CONFIG_DIR)
    _file_plan(source, commit_sha=SEED_COMMIT)
    _assemble(source, settings)
    count_files = _run_shard_file_count(source.date)

    unknown = source.model_copy(update={"shards": None})
    _assemble(unknown, settings)

    assert _manifest(source.date).runs[-1].shards is None
    assert _settled_counts(source.date) == {source.run_id: 4}
    assert _run_shard_file_count(source.date) == count_files
