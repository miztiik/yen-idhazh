"""What does a work shard leave behind for assemble to read?"""

from __future__ import annotations

from pathlib import Path

from conftest import CONFIG_DIR, read_text
from pydantic import TypeAdapter
from pytest import MonkeyPatch

from idhazh import config, run_context, telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.run_manifest import RunManifest
from idhazh.fingerprint import UNRECORDED_BUILD, prose_changed_alone, runtime_build, text_digest
from idhazh.stages import common
from idhazh.stages.assemble import _recorded_inputs, stage_assemble
from idhazh.stages.common import INPUTS_PAYLOAD
from idhazh.stages.work import stage_work

from ._builders import (
    a_config_pointing_at,
    a_server_that_refuses_every_completion,
    captured_article_fetch,
    isolate_ledgers,
    plan,
    score_one_item,
    work_then_assemble,
)


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

    with a_server_that_refuses_every_completion() as server:
        stage_work(
            run_plan,
            settings=settings,
            scorer=None,
            fetcher=captured_article_fetch,
            model_endpoint=server.endpoint,
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
    assert recorded.chat_template_sha256 != text_digest(settings.models.summarizer.id)


def test_a_run_pointed_at_a_second_machine_records_no_build_for_it(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Every other field of this record describes the machine that ran the pipeline.

    So a build tag read from this machine's environment, on a run whose weights
    decoded on another one, is well formed, validates, and is false. The address
    in `config/` is the only thing that moves here - the build is pinned in the
    environment throughout, and the first assertion is what proves the sentinel
    came from the address rather than from an environment naming nothing.

    The record still has to survive the whole path: `_recorded_inputs` validates
    the payload the shard wrote, and the run record carries the same object, so a
    degraded field that broke any other one would fail here rather than publish.

    **What it does not prove is that a second machine answered.** Nothing in this
    repository binds a server off loopback, so the transport is pointed at the
    recording server on this one and the first end-to-end reading is a person
    running a server elsewhere by hand.
    """
    run_plan = plan()
    isolate_ledgers(tmp_path, monkeypatch)
    monkeypatch.setenv("LLAMA_CPP_BUILD", "b10598")
    settings = a_config_pointing_at(tmp_path, "http://192.168.1.20:9090")
    assert runtime_build(base_url="http://127.0.0.1:8080") == "b10598", (
        "this machine pinned no build, so a sentinel below would say nothing about the address"
    )

    work_then_assemble(run_plan, settings)

    recorded = _recorded_inputs(tmp_path / "run" / run_plan.date / "items")
    year, month, day = run_plan.date.split("-")
    manifest = RunManifest.from_json(
        read_text(tmp_path / "public" / "digest" / year / month / day / "run.json")
    )

    assert recorded is not None
    assert recorded.runtime_build == UNRECORDED_BUILD
    assert manifest.runs[-1].inputs == recorded


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


def test_a_traced_work_shard_writes_separate_item_passes_and_their_children(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The recorded model refusal still leaves the real worker's trace tree."""
    run_plan = plan()
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")
    settings = config.load(CONFIG_DIR)
    assert settings.app.observability.tracing_enabled, "the committed config traces by default"

    with a_server_that_refuses_every_completion() as server:
        stage_work(
            run_plan,
            settings=settings,
            scorer=None,
            fetcher=captured_article_fetch,
            model_endpoint=server.endpoint,
        )

    trace = telemetry.committed_trace_path(
        common.STATE_ROOT,
        run_id=run_plan.run_id,
        attempt=run_context.run_attempt(),
        job=ServerJob.WORK,
        shard=0,
    )
    adapter = TypeAdapter(telemetry.Span)
    spans = [
        adapter.validate_json(line) for line in trace.read_text(encoding="utf-8").splitlines()
    ]
    by_id = {span.span_id: span for span in spans}
    assert len(by_id) == len(spans)
    roots = [span for span in spans if span.name is telemetry.SpanName.ITEM]
    assert len(roots) >= 2
    assert all(span.parent_id is None for span in roots)
    children = [span for span in spans if span.parent_id is not None]
    assert children
    for span in children:
        assert span.parent_id is not None
        assert by_id[span.parent_id].trace_id == span.trace_id
    assert telemetry.SpanName.TAG in {span.name for span in spans}
