"""Do published records stay readable without changing their data?"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR

from idhazh.contracts.base import Contract, canonical_json, records_json
from idhazh.contracts.console_band import ConsoleBand
from idhazh.contracts.day_metrics import DayMetrics
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.digest_run_fragment import DigestRunFragment
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.source_health_view import SourceHealthView
from idhazh.contracts.visual_data import VisualData
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
        (DigestRunFragment, "digest-run-fragment/one-block.json", {"items", "verticals"}),
        (DayMetrics, "day-metrics/full.json", {"sources", "instruments", "stage_timing"}),
        (RunManifest, "run-manifest/two-runs.json", {"config_digests", "verticals"}),
        (ConsoleBand, "console-band/newest-day.json", {"routes"}),
        (PublicationInventory, "publication-inventory/published.json", {"entries", "changelog"}),
        (SourceHealthView, "source-health-view/four-facts.json", {"sources"}),
        (VisualData, "visual-data/bars-from-the-committed-plan.json", {"marks"}),
    ],
)
def test_published_contracts_compact_only_selected_lists(
    model: type[Contract], fixture: str, lists: set[str]
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
    if model is ConsoleBand:
        for row in expected["verdict"]["runs"]:
            assert json.dumps(row, sort_keys=True, separators=(",", ": ")) in text


@pytest.mark.parametrize("empty", [False, True])
def test_fragment_file_writer_preserves_records_and_metadata(tmp_path: Path, empty: bool) -> None:
    from idhazh.atomic_write import write_atomic

    fragment = DigestRunFragment.read(
        CONTRACT_FIXTURES_DIR / "digest-run-fragment" / "one-block.json"
    )
    if empty:
        fragment = fragment.model_copy(update={"items": [], "verticals": []})
    target = tmp_path / f"{fragment.run_id}.json"
    write_atomic(target, fragment.to_json())
    text = target.read_text(encoding="utf-8")
    assert DigestRunFragment.read(target) == fragment
    assert text.startswith("{\n")
    assert '  "failed_item_ids": [\n' in text
    assert text.endswith("\n") and "\r" not in text
    for name in ("items", "verticals"):
        rows = fragment.model_dump(mode="json")[name]
        lines = text.splitlines()
        for row in rows:
            rendered = json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ": "))
            assert any(line.strip().rstrip(",") == rendered for line in lines)
        if empty:
            assert f'  "{name}": []' in text


def test_month_producer_keeps_days_expanded_and_sources_on_one_line(tmp_path: Path) -> None:
    fixture = CONTRACT_FIXTURES_DIR / "day-metrics"
    metrics = DayMetrics.read(fixture / "full.json")
    state = tmp_path / "state"
    state_path = day_metrics.write(state, metrics)
    state_text = state_path.read_text(encoding="utf-8")
    assert state_text.startswith("{\n")
    assert '  "bands": {\n' in state_text
    assert json.loads(state_text) == metrics.model_dump(mode="json")
    assert DayMetrics.read(state_path) == metrics
    assert state_text == metrics.to_json()
    assert "\r" not in state_text and state_text.endswith("\n")
    for records in (metrics.sources, metrics.instruments, metrics.stage_timing):
        for record in records:
            rendered = json.dumps(
                record.model_dump(mode="json"), sort_keys=True, separators=(",", ": ")
            )
            assert any(line.strip().rstrip(",") == rendered for line in state_text.splitlines())
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
