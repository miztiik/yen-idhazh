"""Do published records stay readable without changing their data?"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.base import Contract, canonical_json
from idhazh.contracts.console_band import ConsoleBand
from idhazh.contracts.day_metrics import DayMetrics
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.digest_run_fragment import DigestRunFragment
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.source_health_view import SourceHealthView
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.watchlist import Watchlist
from idhazh.telemetry.publish import day_metrics


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
    if model is DayMetrics:
        expected.pop("label_similarity", None)
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
    assert '  "failed_item_ids": [\n' in text
    assert text.endswith("\n") and "\r" not in text
    for name in ("items", "verticals"):
        rows = fragment.model_dump(mode="json")[name]
        lines = text.splitlines()
        for row in rows:
            rendered = json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ": "))
            assert any(line.strip().rstrip(",") == rendered for line in lines)


def test_state_producer_keeps_days_expanded_and_sources_on_one_line(tmp_path: Path) -> None:
    fixture = CONTRACT_FIXTURES_DIR / "day-metrics"
    metrics = DayMetrics.read(fixture / "full.json")
    state = tmp_path / "state"
    state_path = day_metrics.write(state, metrics)
    state_text = state_path.read_text(encoding="utf-8")
    expected = metrics.model_dump(mode="json")
    expected.pop("label_similarity", None)
    assert state_text.startswith("{\n")
    assert '  "bands": {\n' in state_text
    assert json.loads(state_text) == expected
    assert DayMetrics.read(state_path).label_similarity is None
    assert state_text == metrics.to_json()
    assert "\r" not in state_text and state_text.endswith("\n")
    for records in (metrics.sources, metrics.instruments, metrics.stage_timing):
        for record in records:
            rendered = json.dumps(
                record.model_dump(mode="json"), sort_keys=True, separators=(",", ": ")
            )
            assert any(line.strip().rstrip(",") == rendered for line in state_text.splitlines())


@pytest.mark.parametrize(
    ("model", "name"),
    [
        pytest.param(Sources, "sources.json", id="sources"),
        pytest.param(Taxonomy, "taxonomy.json", id="taxonomy"),
        pytest.param(Watchlist, "watchlist.json", id="watchlist"),
    ],
)
def test_a_curated_registry_writer_holds_one_record_a_line(
    model: type[Contract], name: str
) -> None:
    """The writer, not the committed file, decides the layout a curator reads.

    Counted over what the contract writes, so the day the writer goes back to a
    field a line this fails, and no whitespace edit to the committed file can
    make it pass or fail.
    """
    rewritten = model.from_json(read_text(CONFIG_DIR / name)).to_json()
    payload = json.loads(rewritten)
    expected = [
        record
        for _, value in sorted(payload.items())
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value)
        for record in value
    ]
    assert expected, f"config/{name} holds no records, so this proves nothing"

    found = [
        json.loads(line.strip().rstrip(","))
        for line in rewritten.splitlines()
        if line.startswith("    {")
    ]
    assert found == expected, f"{model.__name__} does not write one record a line"
