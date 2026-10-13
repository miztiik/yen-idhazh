"""Do native window results reach the complete health record before Work seals it?"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from test_host_event_client import SessionPeer, _manifest

from idhazh import config
from idhazh.contracts.host_events import HostSessionManifest, HostWindowCells
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages.work import stage_work
from idhazh.telemetry.host_event_client import HostEventClient
from idhazh.telemetry.record import HEALTH_SUFFIX

from ._builders import (
    _work_stage,
)
from .test_degrade import headless_page_fetch, headless_plan
from .test_work_health_payload import LABEL_REPLY, SUMMARIZE_AND_PLAN_REPLY, rows


def _work_manifest(root: Path, plan: RunPlan) -> HostSessionManifest:
    source = _manifest(root, item_id=tuple(value.item_id for value in plan.items))
    values = source.model_dump(mode="json") | {
        "date": plan.date,
        "run_id": plan.run_id,
        "event_root": (
            f"backend/var/host-events/{plan.run_id}/{source.attempt}/"
            f"{source.job.value}/{source.shard}/{source.session_id}"
        ),
    }
    manifest = HostSessionManifest.model_validate(values)
    (root / "manifest.json").write_text(manifest.to_json(), encoding="ascii", newline="\n")
    return manifest


def test_no_scoring_window_finishes_before_health_is_sealed(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    plan = headless_plan()
    item = plan.items[0]
    manifest = _work_manifest(tmp_path, plan)
    peer = SessionPeer(tmp_path, manifest)
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
    try:
        _, items, _ = _work_stage(
            tmp_path,
            monkeypatch,
            replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
            fetcher=headless_page_fetch,
            run_plan=plan,
            host_events=client,
        )
        assert peer.seen[0].kind == "worker.register"
        assert [event.kind for event in peer.seen[1:]] == [
            kind for _ in plan.items for kind in ("window.begin", "window.end")
        ]
        assert (items / f"{item.item_id}{HEALTH_SUFFIX}").is_file()
    finally:
        peer.close()


@pytest.mark.parametrize("native", [False, True])
def test_native_window_cells_feed_item_health_including_resource_only_sessions(
    tmp_path: Path, monkeypatch: MonkeyPatch, native: bool
) -> None:
    plan = headless_plan()
    item = plan.items[0]
    manifest = _work_manifest(tmp_path, plan)
    cells = HostWindowCells(
        cpu_busy_pct=25.0,
        cpu_busy_max=50.0,
        cpu_busy_min=10.0,
        cpu_steal_pct=2.0,
        load_1m=1.5,
        llama_rss_bytes=8192,
        llama_rss_anon_bytes=4096,
        llama_rss_peak_bytes=16384,
        llama_major_faults=3,
        python_rss_bytes=2048,
        python_rss_anon_bytes=1024,
        os_mem_available_bytes=65536,
        os_mem_total_bytes=131072,
        os_mem_cached_bytes=32768,
        os_swap_free_bytes=4096,
        os_swap_total_bytes=8192,
        os_mem_available_min_bytes=49152,
    )
    peer = SessionPeer(tmp_path, manifest, window_cells=cells)
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=native)
    try:
        _, items, _ = _work_stage(
            tmp_path,
            monkeypatch,
            replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
            fetcher=headless_page_fetch,
            run_plan=plan,
            host_events=client,
        )
        assert (items / f"{item.item_id}{HEALTH_SUFFIX}").is_file()
        written = rows(items)
        assert len(written) == len(plan.items)
        for row in written.values():
            assert {
                name: getattr(row, name) for name in HostWindowCells.model_fields
            } == cells.model_dump()
            assert row.machine_job == manifest.job
            assert row.cpu_model is None
            assert row.label_ms is not None and row.summary_ms is not None
        assert [event.kind for event in peer.seen] == [
            "worker.register",
            *[kind for _ in plan.items for kind in ("window.begin", "window.end")],
        ]
    finally:
        peer.close()


def test_empty_native_work_registers_without_opening_a_model_or_item_window(tmp_path: Path) -> None:
    plan = headless_plan().model_copy(update={"items": []})
    manifest = _work_manifest(tmp_path, plan)
    peer = SessionPeer(tmp_path, manifest)
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
    try:
        stage_work(
            plan,
            settings=config.load(),
            scorer=None,
            model_endpoint="http://127.0.0.1:1",
            host_events=client,
        )
        assert [event.kind for event in peer.seen] == ["worker.register"]
        assert not (tmp_path / "state").exists()
    finally:
        peer.close()


def test_wrong_plan_is_refused_before_registration_or_model_access(tmp_path: Path) -> None:
    plan = headless_plan()
    _work_manifest(tmp_path, plan)
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
    wrong = plan.model_copy(update={"run_id": f"{plan.date}-2"})
    with pytest.raises(ValueError, match="expected run plan identity"):
        stage_work(
            wrong,
            settings=config.load(),
            scorer=None,
            model_endpoint="http://127.0.0.1:1",
            host_events=client,
        )
    assert not client.native_started


@pytest.mark.parametrize("native", [False, True])
def test_work_memory_control_mismatch_is_refused_before_registration_or_model_access(
    tmp_path: Path, native: bool
) -> None:
    plan = headless_plan()
    _work_manifest(tmp_path, plan)
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=native)
    settings = config.load()
    memory_off = replace(
        settings,
        app=settings.app.model_copy(
            update={
                "observability": settings.app.observability.model_copy(
                    update={"memory_profiling_enabled": False}
                )
            }
        ),
    )
    with pytest.raises(ValueError, match="native work memory control differs"):
        stage_work(
            plan,
            settings=memory_off,
            scorer=None,
            model_endpoint="http://127.0.0.1:1",
            host_events=client,
        )
    assert not client.native_started


def test_missing_declared_item_is_refused_before_registration_or_model_access(
    tmp_path: Path,
) -> None:
    plan = headless_plan()
    manifest = _work_manifest(tmp_path, plan)
    source = manifest.model_dump(mode="json") | {"windows": []}
    (tmp_path / "manifest.json").write_text(
        HostSessionManifest.model_validate(source).to_json(), encoding="ascii", newline="\n"
    )
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
    with pytest.raises(ValueError, match="exact selected run plan shard"):
        stage_work(
            plan,
            settings=config.load(),
            scorer=None,
            model_endpoint="http://127.0.0.1:1",
            host_events=client,
        )
    assert not client.native_started
