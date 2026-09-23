"""Does every run manifest ever committed still read today?"""

from __future__ import annotations

import json

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.run_manifest import ModelRole, RunManifest

pytestmark = pytest.mark.contract


def test_every_committed_run_manifest_still_reads_today() -> None:
    """The release blocker this class of change carries: a payload yesterday's run
    wrote that today's build cannot open (section 11).

    Driven from the fixture with the two fields removed, not from the committed
    tree. Walking the tree cost one parse per published day and carried a fuse:
    it counted the desks that still LACK the field and failed at zero, so it goes
    red on the day the last unmigrated day ages out of retention - a date on the
    calendar rather than a change anybody made.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    stripped = 0
    for run in payload["runs"]:
        for written in run.get("verticals", []):
            written.pop("eligible_feeds", None)
            written.pop("feed_floor", None)
            stripped += 1
    assert stripped, "the fixture declares no desk, so removing the fields proved nothing"

    parsed = RunManifest.model_validate(payload)
    counts = [count for record in parsed.runs for count in record.verticals]
    assert len(counts) == stripped
    assert all(count.eligible_feeds is None for count in counts)
    assert all(count.feed_floor is None for count in counts)


def test_the_manifest_keeps_the_keys_its_python_names_stopped_matching() -> None:
    """Three Python names moved on 2026-09-05 and no published key was allowed to.

    The rename is a read-side alias, so the payload keeps `items_routed` and
    `route_ms` and the model answers to `items_decided` and `decision_ms`. That
    is a property of the model against one payload, and the committed tree was
    parsed once per published day to re-ask it.
    """
    assert ModelRole.VISUAL_PLANNER.value == "route"
    assert ModelRole.SUMMARIZER.value == "summarize", (
        "the published role value is pinned; only the python name and the config key moved"
    )

    raw = read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json")
    payload = json.loads(raw)
    carrying = 0
    for run in payload["runs"]:
        if "items_routed" not in run:
            continue
        carrying += 1
    assert carrying, "the fixture carries no items_routed, so the alias is untested"

    parsed = RunManifest.model_validate(payload)
    for record, written in zip(parsed.runs, payload["runs"], strict=True):
        if "items_routed" not in written:
            continue
        assert record.items_decided == written["items_routed"]
        assert record.decision_ms == written["route_ms"]
    # The published key is the contract. A writer that started emitting the
    # Python name would break every reader of every day already committed.
    assert "items_decided" not in raw
    assert "decision_ms" not in raw

    # And the round trip puts the keys back, which is what a reader fetches.
    written_back = json.loads(parsed.to_json())["runs"][-1]
    assert "items_routed" in written_back and "route_ms" in written_back
