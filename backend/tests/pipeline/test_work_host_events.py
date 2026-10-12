"""Do shadow events close before the real work stage seals item health?"""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch
from test_host_event_client import SessionPeer, _manifest

from idhazh.telemetry.host_event_client import HostEventClient
from idhazh.telemetry.record import HEALTH_SUFFIX

from ._builders import (
    _work_stage,
)
from .test_degrade import headless_page_fetch, headless_plan
from .test_work_health_payload import LABEL_REPLY, SUMMARIZE_AND_PLAN_REPLY


def test_no_scoring_window_finishes_before_health_is_sealed(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    plan = headless_plan()
    item = plan.items[0]
    manifest = _manifest(tmp_path, item_id=tuple(value.item_id for value in plan.items))
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
