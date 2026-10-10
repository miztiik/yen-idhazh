"""Does a run report evidence from the numeric chart figures it actually published?"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh import assemble
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.chart_evidence import ChartEvidence
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.contracts.element import ElementTable
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.visual import EncodingRole, VisualPlan
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import VisualDecision, VisualKind, VisualState
from idhazh.derived_values import measure_displayed_values, resolve_displayed_values
from idhazh.render.chart import compile_bar
from idhazh.render.write import asset_relpath, render_planned_visual
from idhazh.telemetry.publish import run_days

pytestmark = [pytest.mark.visual, pytest.mark.contract]

DATE = "2026-08-21"
VISUAL_FIXTURES = FIXTURES_DIR / "visual-validator"


def _render(
    root: Path,
    *,
    plan_name: str = "passes",
    table_name: str = "wind",
    item_id: str | None = None,
    fail_write: bool = False,
) -> VisualDecision:
    table = ElementTable.read(VISUAL_FIXTURES / "tables" / f"{table_name}.json")
    if item_id is not None:
        table = table.model_copy(update={"item_id": item_id})
    path = asset_relpath(DATE, table.item_id)
    if fail_write:
        (root / path).mkdir(parents=True)
    return render_planned_visual(
        VisualDecision(
            version=VisualDecision.schema_version(),
            item_id=table.item_id,
            url_key=table.url_key,
            kind=VisualKind.NONE,
            model_id="fixture-model",
            decided_at=f"{DATE}T06:00:00Z",
        ),
        VisualPlan.read(VISUAL_FIXTURES / "plans" / f"{plan_name}.json"),
        table,
        public_root=root,
        relpath=path,
        visuals=AppConfig.read(CONFIG_DIR / "idhazh.json").visuals,
    )


def _card(decision: VisualDecision, *, run: int = 1, **updates: Any) -> DigestItem:
    return DigestItem.model_validate(
        {
            "item_id": decision.item_id,
            "vertical": decision.item_id.rsplit("-", 1)[0],
            "title": "A fixture story",
            "source_url": f"https://example.org/{decision.item_id}",
            "source_id": "fixture-source",
            "source_name": "Fixture Source",
            "summary": "The source states these figures.",
            "band": ConfidenceBand.HIGH,
            "introduced_by_run": run,
            "visual": (
                {
                    "kind": decision.kind,
                    "state": decision.visual_state,
                    "data_path": decision.data_path,
                    "alt": decision.alt_text,
                }
                if decision.kind is VisualKind.CHART
                else None
            ),
        }
        | updates
    )


def _day(items: Sequence[DigestItem]) -> DigestDay:
    return DigestDay(
        version=DigestDay.schema_version(),
        date=DATE,
        generated_at=f"{DATE}T18:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        items=list(items),
        runs=[
            DigestRunRef(
                n=n,
                at=f"{DATE}T{n * 6:02d}:00:00Z",
                run_id=f"{DATE}-{n}",
                completed_at=f"{DATE}T{n * 6:02d}:30:00Z",
                items_added=sum(item.introduced_by_run == n for item in items),
            )
            for n in (1, 2)
        ],
        verticals=[
            DigestVerticalRef(
                id=vertical,
                display_name=vertical,
                count=sum(item.vertical == vertical for item in items),
            )
            for vertical in sorted({item.vertical for item in items})
        ],
    )


def _manifest(
    day: DigestDay,
    decisions: Sequence[VisualDecision],
    *,
    run: int = 1,
    previous: RunManifest | None = None,
) -> RunManifest:
    plan = RunPlan.read(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")
    return assemble.build_manifest(
        plan=plan.model_copy(
            update={
                "run_id": f"{DATE}-{run}",
                "verticals": [
                    vertical.model_copy(update={"planned": max(vertical.planned, len(day.items))})
                    for vertical in plan.verticals
                ],
            }
        ),
        day=day,
        previous=previous,
        summaries=[],
        decisions=decisions,
        models=[],
        commit_sha="0" * 40,
        runner="fixture-cpu",
        started_at=f"{DATE}T06:00:00Z",
        completed_at=f"{DATE}T06:30:00Z",
        config_digests=[],
        site_bytes=0,
        site_files=0,
    )


def test_compiler_decision_manifest_and_month_reader_preserve_weighted_evidence(
    tmp_path: Path,
) -> None:
    wind = _render(tmp_path)
    steel = _render(tmp_path, plan_name="units-convert", table_name="tonnes-and-kilotonnes")
    assert wind.chart_evidence == ChartEvidence.from_counts(displayed=4, derived=0, trusted=4)
    assert steel.chart_evidence == ChartEvidence.from_counts(displayed=3, derived=1, trusted=3)
    assert wind.spec is not None and steel.spec is not None
    wind_data, steel_data = VisualData.from_json(wind.spec), VisualData.from_json(steel.spec)
    held = {mark.mark_id: mark for mark in steel_data.marks}
    figures = [held[mark_id] for mark_id in steel_data.encoding.quantity]
    assert [mark.value for mark in figures] == ["4200", "4200", "3900"]
    assert figures[1].derived is not None
    assert figures[1].derived.inputs == ["quantity-55-61"]
    assert len(wind_data.marks) == 8  # Four names are not four more numeric figures.

    day = _day([_card(wind), _card(steel)])
    manifest = _manifest(day, [wind, steel])
    expected = ChartEvidence.from_counts(displayed=7, derived=1, trusted=7)
    assert manifest.runs[0].chart_evidence == expected
    assert expected.derived_value_rate == 1 / 7
    assert expected.derived_value_rate != (0 + 1 / 3) / 2
    digest_root = tmp_path / "digest"
    folder = assemble.day_dir(digest_root, DATE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "digest.json").write_text(day.to_json(), encoding="utf-8", newline="\n")
    (folder / "run.json").write_text(manifest.to_json(), encoding="utf-8", newline="\n")
    paths = run_days.publish(
        digest_root=digest_root,
        keep_months=1,
        today=date(2026, 8, 21),
        months=[DATE[:7]],
    )
    assert len(paths) == 1
    loaded = run_days.read_shard(paths[0])
    assert loaded[0].runs[0].chart_evidence == expected
    assert json.loads(paths[0].read_text(encoding="utf-8"))[0]["runs"][0]["chart_evidence"] == (
        expected.model_dump(mode="json")
    )


def test_reporting_does_not_count_unused_encodings_labels_or_annotations() -> None:
    plan = VisualPlan.read(VISUAL_FIXTURES / "plans" / "passes.json")
    table = ElementTable.read(VISUAL_FIXTURES / "tables" / "wind.json")
    # A compiler consumes the validated type's own channels, not every resolver reference.
    extra = plan.encodings.model_copy(update={"size": plan.encodings.quantity})
    compiled = compile_bar(
        plan.model_copy(update={"encodings": extra}),
        table,
        visuals=AppConfig.read(CONFIG_DIR / "idhazh.json").visuals,
    )
    assert compiled.evidence == ChartEvidence.from_counts(displayed=4, derived=0, trusted=4)


@pytest.mark.parametrize("plan_name", ["declines", "element-missing"])
def test_refused_plans_report_measured_no_charts(tmp_path: Path, plan_name: str) -> None:
    refused = _render(tmp_path, plan_name=plan_name)
    assert refused.chart_evidence is None
    assert refused.kind is VisualKind.NONE
    assert _manifest(_day([_card(refused)]), [refused]).runs[0].chart_evidence == (
        ChartEvidence.from_counts(displayed=0, derived=0, trusted=0)
    )


def test_failed_writes_unpublished_collapsed_and_carried_charts_add_no_figures(
    tmp_path: Path,
) -> None:
    kept = _render(tmp_path, item_id="energy-01")
    collapsed = _render(tmp_path, item_id="energy-02")
    failed = _render(tmp_path, item_id="energy-03", fail_write=True)
    unpublished = _render(tmp_path, item_id="energy-04")
    carried = _render(tmp_path, item_id="energy-05")
    assert failed.visual_state is VisualState.RENDER_FAILED
    assert failed.chart_evidence == kept.chart_evidence
    day = _day(
        [
            _card(carried),
            _card(kept, run=2),
            _card(collapsed, run=2, same_story_as=kept.item_id, also_covered_by=1),
            _card(failed, run=2),
        ]
    )
    result = _manifest(day, [kept, collapsed, failed, unpublished, carried], run=2)
    assert result.runs[0].chart_evidence == kept.chart_evidence
    empty = _manifest(_day([_card(carried)]), [carried], run=2)
    assert empty.runs[0].chart_evidence == ChartEvidence.from_counts(
        displayed=0, derived=0, trusted=0
    )


def test_a_revision_belongs_to_the_run_that_wrote_it(tmp_path: Path) -> None:
    revised = _render(tmp_path)
    card = _card(revised, updated_at=f"{DATE}T12:00:00Z", updated_by_run=2)
    day = _day([card])
    first = _manifest(day, [revised])
    second = _manifest(day, [revised], run=2, previous=first)
    assert first.runs[0].chart_evidence == ChartEvidence.from_counts(
        displayed=0, derived=0, trusted=0
    )
    assert second.runs[0] == first.runs[0]
    assert second.runs[1].chart_evidence == revised.chart_evidence
    assert _manifest(day, [revised], run=2, previous=second) == second


@pytest.mark.parametrize("missing", ["evidence", "decision", "path"])
def test_one_unmeasured_eligible_chart_makes_the_whole_run_unknown(
    tmp_path: Path, missing: str
) -> None:
    known = _render(tmp_path, item_id="energy-01")
    old = _render(tmp_path, item_id="energy-02")
    card = _card(old)
    if missing == "evidence":
        payload = old.model_dump(mode="json")
        del payload["chart_evidence"]
        old = VisualDecision.model_validate(payload)
    elif missing == "path":
        assert card.visual is not None
        card = card.model_copy(
            update={"visual": card.visual.model_copy(update={"data_path": None})}
        )
    decisions = [known] if missing == "decision" else [known, old]
    assert _manifest(_day([_card(known), card]), decisions).runs[0].chart_evidence is None


def test_old_manifests_remain_unknown_including_runs_with_no_charts() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    for run in payload["runs"]:
        del run["chart_evidence"]
    old = RunManifest.model_validate(payload)
    assert all(run.chart_evidence is None for run in old.runs)


def test_trusted_ratio_measures_reference_membership_not_a_constant() -> None:
    table = ElementTable.read(VISUAL_FIXTURES / "tables" / "tonnes-and-kilotonnes.json")
    plan = VisualPlan.read(VISUAL_FIXTURES / "plans" / "units-convert.json")
    resolution = resolve_displayed_values(
        plan, table, visuals=AppConfig.read(CONFIG_DIR / "idhazh.json").visuals
    )
    values = [value for value in resolution.values if value.role is EncodingRole.QUANTITY]
    stranger = ElementTable.read(VISUAL_FIXTURES / "tables" / "wind.json")
    assert measure_displayed_values(values, stranger) == ChartEvidence.from_counts(
        displayed=3, derived=1, trusted=0
    )
    partial = table.model_copy(update={"elements": table.elements[:-1]})
    assert measure_displayed_values(values, partial) == ChartEvidence.from_counts(
        displayed=3, derived=1, trusted=2
    )
    assert measure_displayed_values([], table) == ChartEvidence.from_counts(
        displayed=0, derived=0, trusted=0
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"displayed_values": -1},
        {"displayed_values": 3.5},
        {"derived_values": 5},
        {"trusted_values": 5},
        {"derived_value_rate": None},
        {"derived_value_rate": 0.5},
        {"trusted_data_ratio": 0.75},
        {"trusted_data_ratio": 1.1},
    ],
)
def test_evidence_refuses_counts_and_rates_that_disagree(changes: dict[str, Any]) -> None:
    expected = ChartEvidence.from_counts(displayed=4, derived=1, trusted=4)
    with pytest.raises(ValidationError):
        ChartEvidence.model_validate(expected.model_dump(mode="json") | changes)


def test_empty_counts_require_null_rates() -> None:
    empty = ChartEvidence.from_counts(displayed=0, derived=0, trusted=0)
    with pytest.raises(ValidationError, match="derived_value_rate"):
        ChartEvidence.model_validate(empty.model_dump(mode="json") | {"derived_value_rate": 0})
