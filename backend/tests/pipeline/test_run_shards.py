"""Assemble files exactly its final manifest counts, including regeneration and unknowns."""

from pathlib import Path

import pytest
from conftest import CONFIG_DIR, SEED_COMMIT
from pytest import MonkeyPatch

from idhazh import assemble, config, ledger
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_shards import RunShards
from idhazh.stages.assemble import stage_assemble

from ._builders import isolate_ledgers, plan

pytestmark = pytest.mark.contract


def test_assemble_and_regeneration_record_only_the_final_manifest_count(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    source = plan(item_count=1)
    settings = config.load(CONFIG_DIR)
    exact: dict[str, int | None] = {}
    for count, regenerate in ((3, False), (4, True), (None, True)):
        stage_assemble(
            source.model_copy(update={"shards": count}),
            settings=settings,
            commit_sha=SEED_COMMIT,
            regenerate_only=regenerate,
        )
        written = RunManifest.read(
            assemble.day_dir(tmp_path / "public" / "digest", source.date) / "run.json"
        )
        for run in written.runs:
            if run.run_id not in exact or run.shards is not None:
                exact[run.run_id] = run.shards
        held = ledger.load_days(
            tmp_path / "state", LedgerName.RUN_SHARDS, [source.date], model=RunShards,
        )
        assert {row.run_id: row.shards for row in held} == exact
        assert set(RunShards.model_fields) == {"version", "date", "run_id", "shards"}
