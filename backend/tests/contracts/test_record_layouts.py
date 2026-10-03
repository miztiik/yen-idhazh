"""Do published records stay readable without changing their data?"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR

from idhazh.contracts.base import canonical_json, records_json
from idhazh.contracts.day_metrics import DayMetrics
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.run_manifest import RunManifest
from idhazh.telemetry.publish import day_metrics


def test_selected_record_lists_leave_outer_records_expanded() -> None:
    payload = [{"runs": [{"n": 1, "verticals": [{"id": "ai", "published": 2}]}]}]
    text = records_json(payload, record_lists=frozenset({"verticals"}))
    assert '      "n": 1,\n' in text
    assert '        {"id": "ai","published": 2}\n' in text
    assert json.loads(text) == payload
    assert records_json(json.loads(text), record_lists=frozenset({"verticals"})) == text
    assert records_json(payload) == (
        '[\n  {"runs": [{"n": 1,"verticals": [{"id": "ai","published": 2}]}]}\n]\n'
    )


@pytest.mark.parametrize(
    ("model", "fixture", "lists"),
    [
        (DigestDay, "digest-day/two-runs.json", {"items", "runs", "leads", "verticals"}),
        (RunManifest, "run-manifest/two-runs.json", {"config_digests", "verticals"}),
    ],
)
def test_published_contracts_compact_only_selected_lists(
    model: type[DigestDay] | type[RunManifest], fixture: str, lists: set[str]
) -> None:
    payload = json.loads((CONTRACT_FIXTURES_DIR / fixture).read_text(encoding="utf-8"))
    record = model.from_json(canonical_json(payload))
    text = record.to_json()
    expected = record.model_dump(mode="json")
    assert json.loads(text) == expected
    assert model.from_json(text).to_json() == text
    for name in lists:
        for row in expected.get(name, []):
            assert (
                json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ": ")) in text
            )
    if model is RunManifest:
        assert '  "runs": [\n    {\n' in text
        assert '      "models": [\n        {\n' in text
        for run in expected["runs"]:
            for name in lists:
                for row in run[name]:
                    assert (
                        json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ": "))
                        in text
                    )


def test_month_producer_keeps_days_expanded_and_sources_on_one_line(tmp_path: Path) -> None:
    fixture = CONTRACT_FIXTURES_DIR / "day-metrics"
    metrics = DayMetrics.read(fixture / "full.json")
    state = tmp_path / "state"
    day_metrics.write(state, metrics)
    digest = tmp_path / "public" / "digest"
    paths = day_metrics.publish_public(
        state_root=state,
        digest_root=digest,
        keep_months=1,
        today=date.fromisoformat(metrics.date),
        months=[metrics.date[:7]],
    )
    text = paths[0].read_text(encoding="utf-8")
    assert text.startswith("[\n  {\n")
    assert json.loads(text) == [metrics.model_dump(mode="json")]
    for records in (metrics.sources, metrics.instruments, metrics.stage_timing):
        for record in records:
            row = record.model_dump(mode="json")
            assert json.dumps(row, sort_keys=True, separators=(",", ": ")) in text
    assert day_metrics.read_public_shard(paths[0]) == [metrics]
