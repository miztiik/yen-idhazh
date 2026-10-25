"""Do configurable visual requests retain their facts and terminal outcomes through delivery?"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from pipeline._builders import (
    DRAWS_LABEL,
    DRAWS_SUMMARIZE_AND_PLAN,
    drawable_article_fetch,
    isolate_ledgers,
)
from pipeline._builders import (
    plan as fixture_plan,
)
from support.ledger import seed_item_health
from support.models import a_markers
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text
from support.prompts import label_payload
from support.server import RecordedEndpoint

from idhazh import config, ledger
from idhazh.classify import calls
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.element import ElementTable
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.summary import Summary
from idhazh.contracts.visual import VisualPlan, VisualType
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import VisualDecision, VisualState
from idhazh.fetch import FetchResult
from idhazh.render import asset_relpath
from idhazh.stages import common
from idhazh.stages.record import stage_record
from idhazh.stages.two_calls import _drawn
from idhazh.stages.work import stage_work
from idhazh.visual_outcomes import count_visual_outcomes, project_visual_outcome
from idhazh.visual_planner import reachable_types
from idhazh.visual_population import load_visual_population

pytestmark = [pytest.mark.visual, pytest.mark.contract]


def settings(**knobs: object) -> config.Settings:
    loaded = config.load(CONFIG_DIR)
    app = loaded.app.model_dump(mode="json")
    app["visuals"].update(knobs)
    return replace(loaded, app=AppConfig.model_validate(app))


def inputs(**changed: object) -> tuple[Summary, VisualPlan, ElementTable]:
    root = FIXTURES_DIR / "visual-validator"
    table = ElementTable.read(root / "tables/wind.json")
    requested = VisualPlan.model_validate(
        json.loads(read_text(root / "plans/passes.json")) | changed
    )
    summary = Summary.model_validate(
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary/ok.json"))
        | {"item_id": table.item_id, "url_key": table.url_key}
    )
    return summary, requested, table


def draw(
    knobs: config.Settings, *,
    population: Mapping[VisualType, Sequence[int]] | None = None, **changed: object,
) -> VisualDecision:
    summary, requested, table = inputs(**changed)
    return _drawn(
        summary, requested, table, settings=knobs, date="2026-08-21",
        stamp={
            "version": VisualDecision.schema_version(), "model_id": "fixture-model",
            "decided_at": "2026-08-21T12:00:00Z",
        },
        run_id="2026-08-21-1", published_marks=population,
    )


def record(decision: VisualDecision, number: int) -> ItemHealthRow:
    return ItemHealthRow.model_validate(
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "item-health-row/published.json"))
        | {"item_id": f"energy-{number:02d}", **project_visual_outcome(decision)}
    )


def test_selection_controls_the_actual_request_grammar_without_changing_its_prefix() -> None:
    article = Article.read(CONTRACT_FIXTURES_DIR / "article/ok.json")
    first = label_payload(article)
    off = settings(enabled_types=["quotecard"]).app.visuals
    selected = settings(type_selection_enabled=True, enabled_types=["dot", "quotecard"]).app.visuals
    markers = a_markers()
    full = calls.summarize_and_plan_schema(visuals=off)
    recorded = json.loads(read_text(DRAWS_LABEL))["choices"][0]["message"]["content"]
    request = calls.build_summarize_and_plan_request(
        first, recorded, markers=markers, visuals=selected
    )
    assert request["json_schema"]["$defs"]["VisualType"]["enum"] == ["dot", "quotecard"]
    assert request["prompt"].startswith(first["prompt"])
    assert full["$defs"]["VisualType"]["enum"] == [kind.value for kind in VisualType]
    assert calls.summarize_and_plan_schema()["$defs"]["VisualType"] == full["$defs"]["VisualType"]
    assert VisualPlan.json_schema()["$defs"]["VisualType"] == full["$defs"]["VisualType"]
    assert calls.prompt_inputs(markers=markers, visuals=off) == calls.prompt_inputs(markers=markers)
    assert calls.prompt_inputs(markers=markers, visuals=selected) != calls.prompt_inputs(
        markers=markers, visuals=off
    )
    assert "VisualType" not in calls.summarize_and_plan_schema(plan=False, visuals=selected).get(
        "$defs", {}
    )


def test_an_unruled_selection_is_not_erased_by_the_numeric_reachability_gate() -> None:
    _, _, table = inputs()
    empty = ElementTable.model_validate(table.model_dump(mode="json") | {"elements": []})
    assert reachable_types(empty, visuals=settings(
        type_selection_enabled=True, enabled_types=["quotecard"]
    ).app.visuals) == (VisualType.QUOTECARD,)
    assert reachable_types(empty, visuals=settings(
        type_selection_enabled=True, enabled_types=["bar"]
    ).app.visuals) == ()


def test_mixed_requests_preserve_types_source_figures_and_metric_denominators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    fixture = json.loads(read_text(FIXTURES_DIR / "chart-vocabulary/row1.json"))
    knobs = settings(downgrade_enabled=True)
    population = {VisualType.BAR: tuple(fixture["history_marks"])}
    outcomes: list[ItemHealthRow] = []
    for number, case in enumerate(fixture["cases"], start=1):
        decision = draw(knobs, population=population, type=case["type"], purpose=case["purpose"])
        assert decision.planned_type == case["type"], case["name"]
        assert decision.rendered_type == case["rendered_type"], case["name"]
        assert decision.downgrade_depth == case["depth"], case["name"]
        assert decision.rationale
        outcomes.append(record(decision, number))
        if decision.rendered_type is not None:
            assert decision.spec is not None
            data = VisualData.from_json(decision.spec)
            _, requested, table = inputs()
            known = {element.element_id: element for element in table.elements}
            actual = {mark.mark_id: mark for mark in data.marks}
            for source_id, mark_id in zip(
                requested.encodings.quantity, data.encoding.quantity, strict=True
            ):
                value = actual[mark_id].value
                original = known[source_id].value
                assert value is not None and original is not None
                assert Decimal(value) == Decimal(original)
                assert actual[mark_id].element_id == source_id
            assert decision.marks == len(data.encoding.quantity)
        else:
            assert decision.marks is None

    counted = count_visual_outcomes(outcomes)
    assert counted.measured_requests == len(fixture["cases"])
    assert counted.requested_types["dot"] == 2
    assert counted.wasted_decode_rate == 5 / 6
    legacy = ItemHealthRow.read(CONTRACT_FIXTURES_DIR / "item-health-row/published.json")
    assert count_visual_outcomes([*outcomes, legacy]) == counted
    assert count_visual_outcomes([legacy]).wasted_decode_rate is None


def test_selected_names_and_grouped_evidence_cannot_bypass_safe_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    population = {VisualType.BAR: (4,)}
    knobs = settings(downgrade_enabled=True, type_selection_enabled=True, enabled_types=["dot"])
    assert draw(knobs, population=population, type="dot").rendered_type is None
    assert draw(knobs, population=population).rendered_type is None
    _, requested, _ = inputs()
    grouped = requested.encodings.model_dump(mode="json") | {
        "series": requested.encodings.category
    }
    assert draw(
        settings(downgrade_enabled=True), population=population, type="dot", encodings=grouped
    ).rendered_type is None


def test_enabled_fallback_requires_real_input_and_cold_start_records_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    off = draw(settings(), type="dot")
    assert off.planned_type is VisualType.DOT and off.rendered_type is None
    assert off.rationale and "switched off" in off.rationale
    knobs = settings(downgrade_enabled=True)
    with pytest.raises(ValueError, match="population"):
        draw(knobs, type="dot")
    population = load_visual_population(
        common.STATE_ROOT, on="2026-08-21", visuals=knobs.app.visuals
    )
    refused = draw(knobs, population=population, type="dot")
    assert refused.planned_type is VisualType.DOT
    assert refused.rendered_type is None
    assert refused.rationale and "floor" in refused.rationale


def test_a_failed_write_keeps_the_request_and_selected_depth_without_claiming_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    summary, _, _ = inputs()
    occupied = tmp_path / "public" / asset_relpath("2026-08-21", summary.item_id)
    occupied.mkdir(parents=True)
    decision = draw(settings(downgrade_enabled=True), population={VisualType.BAR: (4,)}, type="dot")
    assert decision.visual_state is VisualState.RENDER_FAILED
    assert decision.planned_type is VisualType.DOT
    assert decision.downgrade_depth == 1
    assert decision.rendered_type is None and decision.marks is None
    assert decision.failure_detail
    assert count_visual_outcomes([record(decision, 1)]).wasted_decode_rate == 1


def test_real_shard_projects_outcomes_before_sealing_and_reuses_its_starting_population(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    run_plan = fixture_plan(item_count=2)
    history = ItemHealthRow.model_validate(
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "item-health-row/published.json")) | {
            "date": "2026-08-20", "run_id": "2026-08-20-1", "item_id": "energy-01",
            "planned_type": "bar", "rendered_type": "bar", "downgrade_depth": 0, "marks": 4,
        }
    )
    seed_item_health(common.STATE_ROOT, history.date, [history])
    reply = json.loads(DRAWS_SUMMARIZE_AND_PLAN.read_bytes())
    content = json.loads(reply["choices"][0]["message"]["content"])
    content["visual"]["type"] = "dot"
    reply["choices"][0]["message"]["content"] = json.dumps(content)
    knobs = settings(
        downgrade_enabled=True, downgrade_max_samples_per_type=1,
        type_selection_enabled=True, enabled_types=["bar", "dot"],
    )
    appended = False

    def fetch(url: str) -> FetchResult:
        nonlocal appended
        if not appended:
            seed_item_health(common.STATE_ROOT, history.date, [
                ItemHealthRow.model_validate(
                    history.model_dump(mode="json") | {"item_id": "energy-02", "marks": 8}
                )
            ])
            appended = True
        return drawable_article_fetch(url)

    caplog.set_level(logging.INFO, logger="idhazh")
    with RecordedEndpoint(200, DRAWS_LABEL.read_bytes(), json.dumps(reply).encode()) as server:
        stage_work(run_plan, settings=knobs, scorer=None, fetcher=fetch, model_endpoint=server.endpoint)
        assert server.sent[-1]["json_schema"]["$defs"]["VisualType"]["enum"] == ["bar", "dot"]
    assert stage_record(run_plan, settings=knobs, commit_sha="a" * 40)[0] == len(run_plan.items)
    rows = ledger.load_days(
        common.STATE_ROOT, LedgerName.ITEM_HEALTH, [run_plan.date], model=ItemHealthRow
    )
    assert {row.item_id for row in rows} == {item.item_id for item in run_plan.items}
    assert all(
        row.planned_type is VisualType.DOT and row.rendered_type is VisualType.BAR
        and row.downgrade_depth == 1 and row.marks == 4 for row in rows
    )
    assert load_visual_population(
        common.STATE_ROOT, on=run_plan.date, visuals=knobs.app.visuals
    ) == {VisualType.BAR: (8,)}
    report = next(
        json.loads(line) for line in caplog.messages
        if line.startswith("{") and json.loads(line).get("name") == "shard.done"
    )
    assert report["visual_outcomes"] == {
        "requested_types": {"dot": len(rows)}, "measured_requests": len(rows),
        "wasted_decode_rate": 1.0,
    }
