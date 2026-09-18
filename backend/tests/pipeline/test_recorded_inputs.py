"""What does a work shard leave behind for assemble to read?"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text
from pytest import MonkeyPatch

from idhazh import config, ledger, telemetry
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.runtime_counters import ServerJob
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.fingerprint import prose_changed_alone, text_digest
from idhazh.stages import common
from idhazh.stages.assemble import _recorded_inputs, stage_assemble
from idhazh.stages.common import INPUTS_PAYLOAD
from idhazh.stages.work import stage_work

from ._builders import (
    captured_article_fetch,
    closed_loopback_endpoint,
    isolate_ledgers,
    plan,
    score_one_item,
    work_then_assemble,
)

pytestmark = pytest.mark.slow


def test_the_work_stage_leaves_its_inputs_where_assemble_can_reach_them(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The oracle: the stage that can observe the inputs is not the stage that records them.

    Only the work shard sees the weights the runtime opened, the build that
    decoded them and the template the server will apply, and its checkout is
    thrown away when the shard ends. So it writes one payload beside the items it
    produced and `stage_assemble`, which owns the run record, hangs it on the run.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    items_dir = tmp_path / "run" / run_plan.date / "items"

    stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    score_one_item(items_dir, run_plan)
    stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    written = _recorded_inputs(items_dir)
    manifest = RunManifest.from_json(
        read_text(tmp_path / "public" / "digest" / "2026" / "08" / "21" / "run.json")
    )

    assert (items_dir / INPUTS_PAYLOAD).is_file()
    assert written is not None
    assert manifest.runs[-1].inputs == written
    assert "pipeline_fingerprints" not in type(manifest.runs[-1]).model_fields, (
        "the stamp was retired, and the run record stopped carrying the list on 2026-09-13"
    )


def test_an_assemble_that_saw_no_work_shard_records_no_inputs(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Absent is a reading of its own, and it is not a manifest of defaults.

    A run record that invented an input set would say the weights and the build
    were observed when nothing observed them (Guardrail #10).
    """
    isolate_ledgers(tmp_path, monkeypatch)
    items_dir = tmp_path / "run" / plan().date / "items"
    items_dir.mkdir(parents=True)

    assert _recorded_inputs(items_dir) is None


def test_the_recorded_inputs_name_the_run_and_never_a_placeholder(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The three fields this row replaced were two literals and a model slug."""
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    work_then_assemble(run_plan, settings)

    recorded = _recorded_inputs(tmp_path / "run" / run_plan.date / "items")

    assert recorded is not None
    assert recorded.runtime_build != "llama-server-local"
    assert recorded.runner_class != "local"
    assert recorded.chat_template_sha256 != text_digest(settings.models.summarize.id)


def test_a_second_run_over_the_same_inputs_reports_no_prose_change(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The one alarm that survived the gate fires on a change and on nothing else.

    Two runs of the same configuration moved nothing, so the run that follows
    publishes with no warning. The alarm compares against one earlier manifest
    the caller already holds, so it costs the same on a repository of one
    published day and of a thousand (Guardrail #12).
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    work_then_assemble(run_plan, settings)

    recorded = _recorded_inputs(tmp_path / "run" / run_plan.date / "items")
    assert recorded is not None

    assert prose_changed_alone(recorded, recorded) == ()
    reworded = recorded.model_copy(update={"prompt_sha256": "b" * 64})
    assert prose_changed_alone(recorded, reworded) == ("prompt_sha256",)


def test_a_traced_work_shard_writes_a_reconciling_span_rollup(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Tracing on, a work shard folds its own spans into its own segment and the
    item row's residual reconciles against the shard wall clock.

    The model is a closed loopback, so the summaries fail - which is fine, the
    fold is over the spans the shard opened (the item, the tagger, the prompt
    render), not over a scored run. `roll_up_spans` raises if the spans claim more
    time than the shard ran, so a residual on the item row is proof they did not.
    The raw trace lands under state/traces/, the committed path the sink now
    writes in place of the gitignored one.

    Read at the segment rather than at the month head, because the shard is no
    longer what writes the head: eight of them fold one month, so each writes
    `state/segments/span-rollup/<run>-<attempt>-work-<shard>.csv` and
    `stage_compact` merges them. The head is `tests/pipeline/test_compact.py`.
    """
    run_plan = plan()
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")
    settings = config.load(CONFIG_DIR)
    assert settings.app.observability.tracing_enabled, "the committed config traces by default"

    stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )

    shard = ledger.segment_path(
        common.STATE_ROOT,
        ledger.SegmentLedger.SPAN_ROLLUP,
        run_id=run_plan.run_id,
        attempt=1,
        job=ServerJob.WORK,
        shard=0,
    )
    rows = [
        SpanRollupRow.from_csv_row(raw)
        for raw in csv.DictReader(shard.read_text(encoding="utf-8").splitlines())
    ]
    by_name = {row.span_name: row for row in rows}
    assert RollupSpan.ITEM in by_name, "the shard opened no item span"
    assert len(by_name) >= 2, "only the item span was folded; a sub-step should have too"
    assert set(by_name) <= set(RollupSpan), "a non-committed span reached the rollup"

    item = by_name[RollupSpan.ITEM]
    assert item.unattributed_ms is not None and item.unattributed_ms >= 0
    for name, row in by_name.items():
        rides_on_item = name is RollupSpan.ITEM
        assert (row.unattributed_ms is not None) is rides_on_item

    traces = list((common.STATE_ROOT / telemetry.TRACES_DIRNAME).rglob("*.jsonl"))
    assert traces, "no committed trace was written under state/traces/"
