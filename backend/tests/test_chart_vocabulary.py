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
    a_server_that_refuses_every_completion,
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
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual import VisualPlan, VisualType
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    NoneReason,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.contracts.visual_telemetry import ValidatorCheck, VisualAttemptRow
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


@pytest.fixture(autouse=True)
def isolate_visual_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")


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
        assert decision.rendered_type == case["rendered_type"], case["name"]

    counted = count_visual_outcomes(outcomes)
    assert counted.measured_requests == len(fixture["cases"])
    assert counted.requested_types["dot"] == 1
    assert counted.requested_types["comparison"] == 1
    assert counted.wasted_decode_rate == 2 / 3
    legacy = ItemHealthRow.read(CONTRACT_FIXTURES_DIR / "item-health-row/published.json")
    assert count_visual_outcomes([*outcomes, legacy]) == counted
    assert count_visual_outcomes([legacy]).wasted_decode_rate is None


def test_selected_names_limit_rendering_and_dot_keeps_grouped_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    population = {VisualType.BAR: (4,)}
    knobs = settings(downgrade_enabled=True, type_selection_enabled=True, enabled_types=["bar"])
    disabled = draw(knobs, population=population, type="dot")
    assert disabled.planned_type is VisualType.DOT and disabled.rendered_type is None
    assert disabled.rejection_reason is None
    assert disabled.deepest_downgrade_depth == 0
    assert disabled.gate_floor_applied is None
    assert draw(knobs, population=population).rendered_type is VisualType.BAR
    _, requested, _ = inputs()
    grouped = requested.encodings.model_dump(mode="json") | {"series": requested.encodings.category}
    grouped_dot = draw(
        settings(downgrade_enabled=True), population=population, type="dot", encodings=grouped
    )
    assert grouped_dot.rendered_type is VisualType.DOT


@pytest.mark.parametrize(
    ("history_marks", "selected_depth", "floor_applied"),
    [(4, 1, False), (8, 0, True)],
)
def test_downgrade_records_floor_effect_separately_from_selected_depth(
    history_marks: int,
    selected_depth: int,
    floor_applied: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    decision = draw(
        settings(downgrade_enabled=True, downgrade_floor_percentiles=[50]),
        population={VisualType.BAR: (history_marks,)},
        type="comparison",
    )

    assert decision.downgrade_depth == selected_depth
    assert decision.deepest_downgrade_depth == 1
    assert decision.gate_floor_applied is floor_applied
    assert decision.rejection_reason is not None


def test_enabled_fallback_requires_real_input_and_cold_start_records_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    off = draw(settings(), type="comparison")
    assert off.planned_type is VisualType.COMPARISON and off.rendered_type is None
    assert off.rationale and "switched off" in off.rationale
    knobs = settings(downgrade_enabled=True)
    with pytest.raises(ValueError, match="population"):
        draw(knobs, type="comparison")
    population = load_visual_population(
        common.STATE_ROOT, on="2026-08-21", visuals=knobs.app.visuals
    )
    refused = draw(knobs, population=population, type="comparison")
    assert refused.planned_type is VisualType.COMPARISON
    assert refused.rendered_type is None
    assert refused.gate_floor_applied is None
    assert refused.rationale and "floor" in refused.rationale


def test_a_failed_write_keeps_the_request_and_selected_depth_without_claiming_delivery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    summary, _, _ = inputs()
    occupied = tmp_path / "public" / asset_relpath("2026-08-21", summary.item_id)
    occupied.mkdir(parents=True)
    decision = draw(
        settings(downgrade_enabled=True), population={VisualType.BAR: (4,)}, type="comparison"
    )
    assert decision.visual_state is VisualState.RENDER_FAILED
    assert decision.planned_type is VisualType.COMPARISON
    assert decision.downgrade_depth == 1
    assert decision.rendered_type is None and decision.marks is None
    assert decision.failure_detail
    assert count_visual_outcomes([record(decision, 1)]).wasted_decode_rate == 1


def test_real_shard_projects_outcomes_before_sealing_and_reuses_its_starting_population(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
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
    content["visual"]["type"] = "comparison"
    reply["choices"][0]["message"]["content"] = json.dumps(content)
    knobs = settings(
        downgrade_enabled=True,
        downgrade_max_samples_per_type=1,
        type_selection_enabled=True,
        enabled_types=["bar", "comparison"],
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
        stage_work(
            run_plan, settings=knobs, scorer=None, fetcher=fetch, model_endpoint=server.endpoint
        )
        assert server.sent[-1]["json_schema"]["$defs"]["VisualType"]["enum"] == [
            "bar",
            "comparison",
        ]
    assert stage_record(run_plan, settings=knobs, commit_sha="a" * 40)[0] == len(run_plan.items)
    rows = ledger.load_days(
        common.STATE_ROOT, LedgerName.ITEM_HEALTH, [run_plan.date], model=ItemHealthRow
    )
    assert {row.item_id for row in rows} == {item.item_id for item in run_plan.items}
    assert all(
        row.planned_type is VisualType.COMPARISON
        and row.rendered_type is VisualType.BAR
        and row.downgrade_depth == 1
        and row.marks == 4
        for row in rows
    )
    attempts = ledger.load_days(
        common.STATE_ROOT, LedgerName.VISUAL_DESIGN_ATTEMPTS,
        [run_plan.date], model=VisualAttemptRow,
    )
    assert len(attempts) == len(run_plan.items)
    for row in attempts:
        decision = VisualDecision.read(
            common._run_dir(run_plan.date) / "items" / f"{row.item_id}{PAYLOAD_SUFFIX}"
        )
        assert row.visual_id == decision.visual_id
        assert row.elements_found is not None
        assert row.potential_primary is not None
        assert row.downgrade_depth == decision.deepest_downgrade_depth
    assert load_visual_population(
        common.STATE_ROOT, on=run_plan.date, visuals=knobs.app.visuals
    ) == {VisualType.BAR: (8,)}
    report = next(
        json.loads(line) for line in caplog.messages
        if line.startswith("{") and json.loads(line).get("name") == "shard.done"
    )
    assert report["visual_outcomes"] == {
        "requested_types": {"comparison": len(rows)},
        "measured_requests": len(rows),
        "wasted_decode_rate": 1.0,
    }


def test_real_shard_keeps_story_when_pie_fallback_parts_do_not_match_its_whole(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    run_plan = fixture_plan(item_count=1)
    reply = json.loads(DRAWS_SUMMARIZE_AND_PLAN.read_bytes())
    content = json.loads(reply["choices"][0]["message"]["content"])
    visual = content["visual"]
    categories = visual["encodings"]["category"][1:]
    quantities = visual["encodings"]["quantity"]
    whole, parts = quantities[0], quantities[1:]
    visual.update(
        purpose="composition",
        type="pie",
        declared_whole_element_id=whole,
        element_ids=[whole, *categories, *parts],
        labels=[whole, *categories],
        annotations=[parts[0]],
    )
    visual["encodings"]["category"] = categories
    visual["encodings"]["quantity"] = parts
    reply["choices"][0]["message"]["content"] = json.dumps(content)
    knobs = settings(
        downgrade_enabled=True,
        type_selection_enabled=True,
        enabled_types=["pie", "stacked_bar"],
    )

    with RecordedEndpoint(200, DRAWS_LABEL.read_bytes(), json.dumps(reply).encode()) as server:
        stage_work(
            run_plan,
            settings=knobs,
            scorer=None,
            fetcher=drawable_article_fetch,
            model_endpoint=server.endpoint,
        )

    item = run_plan.items[0]
    items_dir = common._run_dir(run_plan.date) / "items"
    summary = Summary.read(items_dir / f"{item.item_id}.summary.json")
    decision = VisualDecision.read(items_dir / f"{item.item_id}{PAYLOAD_SUFFIX}")
    assert summary.status is SummaryStatus.OK and summary.summary
    assert decision.kind is VisualKind.NONE
    assert decision.none_reason is NoneReason.VALIDATION_FAILED
    assert decision.planned_type is VisualType.PIE and decision.rendered_type is None
    assert decision.rejection_reason is ValidatorCheck.PIE_EXHAUSTIVE
    assert decision.deepest_downgrade_depth == 1
    assert decision.gate_floor_applied is None
    assert decision.spec is None and decision.data_path is None
    assert decision.rationale and "stacked_bar_exhaustive" in decision.rationale
    (attempt,) = ledger.load_days(
        common.STATE_ROOT, LedgerName.VISUAL_DESIGN_ATTEMPTS,
        [run_plan.date], model=VisualAttemptRow,
    )
    assert attempt.visual_id == decision.visual_id
    assert attempt.downgrade_depth == 1
    assert attempt.none_reason is NoneReason.VALIDATION_FAILED


def test_settled_visuals_survive_a_later_summary_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    run_plan = fixture_plan(item_count=2)
    items = common._run_dir(run_plan.date) / "items"
    (items / f"{run_plan.items[1].item_id}.summary.json").mkdir(parents=True)
    with RecordedEndpoint(
        200, DRAWS_LABEL.read_bytes(), DRAWS_SUMMARIZE_AND_PLAN.read_bytes()
    ) as server:
        with pytest.raises(OSError):
            stage_work(
                run_plan, settings=settings(), scorer=None, fetcher=drawable_article_fetch,
                model_endpoint=server.endpoint, commit_sha="a" * 40,
            )
    attempts = ledger.load_days(
        common.STATE_ROOT, LedgerName.VISUAL_DESIGN_ATTEMPTS,
        [run_plan.date], model=VisualAttemptRow,
    )
    assert {row.item_id for row in attempts} == {item.item_id for item in run_plan.items}
    for raw in ledger.list_raw_files(
        common.STATE_ROOT, LedgerName.VISUAL_DESIGN_ATTEMPTS, days=[run_plan.date]
    ):
        envelope = ledger.read_envelope(raw.path)
        assert envelope.identity.git_sha == "a" * 40


def test_work_without_a_summary_does_not_invent_a_visual_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    run_plan = fixture_plan(item_count=1)
    with a_server_that_refuses_every_completion() as server:
        stage_work(
            run_plan, settings=settings(), scorer=None, fetcher=drawable_article_fetch,
            model_endpoint=server.endpoint,
        )
    assert ledger.load_days(
        common.STATE_ROOT, LedgerName.VISUAL_DESIGN_ATTEMPTS,
        [run_plan.date], model=VisualAttemptRow,
    ) == []
