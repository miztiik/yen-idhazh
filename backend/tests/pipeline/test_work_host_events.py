"""Do shadow events close before the real work stage seals item health?"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch
from test_host_event_client import SessionPeer, _manifest

from idhazh import config
from idhazh.contracts.host_events import HostSessionManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages.work import stage_work
from idhazh.telemetry import host
from idhazh.telemetry.host_event_client import HostEventClient
from idhazh.telemetry.record import HEALTH_SUFFIX

from ._builders import (
    _work_stage,
)
from .test_degrade import headless_page_fetch, headless_plan
from .test_work_health_payload import LABEL_REPLY, SUMMARIZE_AND_PLAN_REPLY


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
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"))
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


def test_native_window_cells_feed_item_health_without_python_watch(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    plan = headless_plan()
    item = plan.items[0]
    manifest = _work_manifest(tmp_path, plan)
    peer = SessionPeer(tmp_path, manifest)
    client = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=True)
    monkeypatch.setattr(
        host,
        "Watch",
        lambda **_: (_ for _ in ()).throw(AssertionError("native path opened Python Watch")),
    )
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
