"""Do actual visual outcomes survive registered storage without losing refused attempts?"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from support.ledger import writer_identity
from support.paths import CONTRACT_FIXTURES_DIR, read_text
from support.prompts import SUMMARIZE_AND_PLAN_REPLIES, WIND_TEXT, chart_data_over
from test_chart_vocabulary import draw, inputs, settings
from test_classify import a_reply

from idhazh import completed_writes, elements, ledger
from idhazh.contracts.article import Article
from idhazh.contracts.base import ServerJob
from idhazh.contracts.element import ElementKind, ElementTable
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual import EncodingRole, PlanDecision, VisualPlan, VisualType
from idhazh.contracts.visual_decision import NoneReason, VisualDecision, VisualState
from idhazh.contracts.visual_telemetry import ValidatorCheck, VisualAttemptRow
from idhazh.elements import ExtractionHealth
from idhazh.llm.server import Completion, response_limit, window
from idhazh.stages import common
from idhazh.stages.summarize_one_item import _decide_the_visual, _drawn
from idhazh.telemetry import visual_attempts
from idhazh.visual_validator import validate_plan
from utilities.digest_publish import permissions

pytestmark = [pytest.mark.visual, pytest.mark.contract]

DATE = "2026-08-21"
RUN = f"{DATE}-1"
LEDGER = LedgerName.VISUAL_DESIGN_ATTEMPTS


def stored(tmp_path: Path, decision: VisualDecision, *, attempt: int = 1) -> VisualAttemptRow:
    paths = visual_attempts.record(
        tmp_path, decision, date=DATE,
        identity=writer_identity(RUN, attempt=attempt, job=ServerJob.WORK),
        extraction=ExtractionHealth(True, 12, None),
    )
    assert len(paths) == 1
    assert paths[0].suffix == ".parquet"
    assert paths[0].relative_to(tmp_path).as_posix().startswith(
        "raw/visual-design-attempts/2026/08/21/"
    )
    return ledger.load(paths, model=VisualAttemptRow)[0]


def test_real_decisions_keep_refusals_replacements_floor_evidence_and_render_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    for history, expected_floor, rendered in ((4, False, VisualType.BAR), (8, True, None)):
        decision = draw(
            settings(
                type_selection_enabled=False,
                downgrade_enabled=True, downgrade_floor_percentiles=[50],
            ),
            population={VisualType.BAR: (history,)}, type="comparison",
        )
        row = stored(tmp_path / str(history), decision)
        assert row.visual_id == decision.visual_id
        assert row.planned_type is VisualType.COMPARISON
        assert row.rendered_type is rendered
        assert row.downgrade_depth == 1
        assert row.gate_floor_applied is expected_floor
        assert row.rejection_reason == decision.rejection_reason
        assert row.decision is PlanDecision.VISUAL
        assert row.none_reason == decision.none_reason

    disabled = draw(settings(type_selection_enabled=True, enabled_types=["dot"]))
    refused = stored(tmp_path / "disabled", disabled)
    assert refused.decision is PlanDecision.VISUAL
    assert refused.planned_type is VisualType.BAR and refused.rendered_type is None
    assert refused.none_reason is NoneReason.VALIDATION_FAILED
    assert refused.rejection_reason is None

    summary, _, _ = inputs()
    occupied = tmp_path / "public" / "digest" / "2026" / "08" / "21" / f"{summary.item_id}.json"
    occupied.parent.mkdir(parents=True, exist_ok=True)
    if occupied.exists():
        occupied.unlink()
    occupied.mkdir()
    failed = draw(settings())
    row = stored(tmp_path / "failed", failed)
    assert row.state is VisualState.RENDER_FAILED
    assert row.marks is None and row.rendered_type is None


def test_production_decider_covers_exactly_the_five_implemented_none_gates(tmp_path: Path) -> None:
    summary, _, _ = inputs()
    knobs = settings()
    table, data = chart_data_over(
        Article.read(CONTRACT_FIXTURES_DIR / "article" / "ok.json"), WIND_TEXT
    )
    stamp = {
        "version": VisualDecision.schema_version(), "model_id": "fixture-model",
        "decided_at": f"{DATE}T12:00:00Z",
    }
    cut = json.loads(read_text(SUMMARIZE_AND_PLAN_REPLIES / "cut-in-the-plan.json"))[
        "choices"
    ][0]["message"]["content"]
    # The largest prompt that still leaves a reply its whole response limit.
    room = window(knobs.models.summarizer.server) - response_limit(
        knobs.models.summarizer.sampling
    )
    cases = (
        (Completion(content="", finish_reason="stop"), ()),
        (Completion(content=cut, finish_reason="length", prompt_tokens=room), data),
        (Completion(content=cut, finish_reason="length", prompt_tokens=room + 1), data),
        (Completion(content='{"visual":{"type":"bar"}', finish_reason="stop"), data),
    )
    decisions = [
        _decide_the_visual(
            summary, reply, table, forms=shown, text=WIND_TEXT,
            settings=knobs, date=DATE, stamp=stamp,
            run_id=RUN,
        )
        for reply, shown in cases
    ]
    declined = a_reply(decline=True)
    decisions.append(_decide_the_visual(
        summary, Completion(content=declined, finish_reason="stop"), table,
        forms=data, text=WIND_TEXT,
        settings=knobs, date=DATE, stamp=stamp, run_id=RUN,
    ))
    assert all(
        decision.planned_type is None and decision.rejection_reason is None
        for decision in decisions
    )
    observed = {stored(tmp_path / str(index), decision).none_reason
                for index, decision in enumerate(decisions)}
    assert observed == set(NoneReason)
    assert len(observed) == 5


def test_shape_evidence_and_missing_compiler_refusals_persist_without_invented_requests(
    tmp_path: Path,
) -> None:
    summary, requested, table = inputs()
    article = Article.read(CONTRACT_FIXTURES_DIR / "article" / "ok.json")
    wind, data = chart_data_over(article, WIND_TEXT)
    knobs = settings()
    stamp = {
        "version": VisualDecision.schema_version(), "model_id": "fixture-model",
        "decided_at": f"{DATE}T12:00:00Z",
    }
    malformed = _decide_the_visual(
        summary,
        Completion(content=a_reply(rows="model-only words"), finish_reason="stop"),
        wind, forms=data, text=WIND_TEXT, settings=knobs, date=DATE, stamp=stamp, run_id=RUN,
    )
    empty = ElementTable.model_validate(table.model_dump() | {"elements": []})
    evidence = _drawn(
        summary, requested, empty, settings=knobs, date=DATE, stamp=stamp, run_id=RUN,
    )

    text = (
        "The level was 10 MW in January 2020. The level was 20 MW in January 2021. "
        "The level was 30 MW in January 2022."
    )
    timed_article = Article.model_validate(article.model_dump() | {"text": text})
    timed = elements.element_table(timed_article, config=knobs.app.elements)
    quantities = [one.element_id for one in timed.elements if one.kind is ElementKind.QUANTITY]
    dates = [one.element_id for one in timed.elements if one.kind is ElementKind.DATE]
    historical = VisualPlan.model_validate(requested.model_dump() | {
        "type": "area", "purpose": "trend", "title": "Measured level over time",
        "why": "Compare the measured level over time.", "caption": None,
        "element_ids": [*quantities, *dates], "labels": [], "annotations": quantities[:1],
        "encodings": {
            role.value: quantities if role is EncodingRole.QUANTITY
            else dates if role is EncodingRole.TIME else []
            for role in EncodingRole
        },
    })
    generic = settings(type_selection_enabled=False)
    assert validate_plan(historical, timed, visuals=generic.app.visuals) == []
    timed_summary = type(summary).model_validate(summary.model_dump() | {
        "item_id": timed.item_id, "url_key": timed.url_key,
    })
    unsupported = _drawn(
        timed_summary, historical, timed, settings=generic, date=DATE, stamp=stamp, run_id=RUN,
    )

    cases = (
        (malformed, None, None, "list_type"),
        (evidence, VisualType.BAR, ValidatorCheck.ELEMENT_EXISTS, "element_exists"),
        (unsupported, VisualType.AREA, None, "area has no compiler"),
    )
    for index, (decision, planned_type, rejection, cause) in enumerate(cases):
        persisted = VisualDecision.from_json(decision.to_json())
        row = stored(tmp_path / str(index), persisted)
        assert persisted.none_reason is row.none_reason is NoneReason.VALIDATION_FAILED
        assert persisted.planned_type is row.planned_type is planned_type
        assert persisted.rejection_reason is row.rejection_reason is rejection
        assert row.rendered_type is None and row.marks is None
        assert persisted.rationale and cause in persisted.rationale
        assert "model-only words" not in persisted.rationale
    assert malformed.rationale and "rows" in malformed.rationale


def test_distinct_actual_attempts_survive_reader_settlement_and_lossless_packing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    first = draw(settings())
    second = VisualDecision.model_validate(first.model_dump(mode="json") | {
        "decided_at": f"{DATE}T12:00:01Z",
    })
    expected = [stored(tmp_path, first), stored(tmp_path, second, attempt=2)]
    rows = ledger.load_days(tmp_path, LEDGER, [DATE], model=VisualAttemptRow)
    assert {row.visual_id for row in rows} == {row.visual_id for row in expected}
    raw = ledger.list_raw_files(tmp_path, LEDGER, days=[DATE])
    held = ledger.load_stored([file.path for file in raw], model=VisualAttemptRow)
    compact = ledger.persist_period(
        tmp_path, held, ledger=LEDGER, covers=DATE, period=Period.DAILY,
        built_from=len(raw), model=VisualAttemptRow, identity=writer_identity(RUN),
    )
    assert ledger.load([compact], model=VisualAttemptRow) == rows
    assert {row.visual_id for row in ledger.load_days(
        tmp_path, LEDGER, [DATE], model=VisualAttemptRow
    )} == {row.visual_id for row in expected}


def test_completed_attempt_is_collected_even_when_later_work_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    with completed_writes.collect() as writes:
        with pytest.raises(RuntimeError, match="later item"):
            first = draw(settings())
            expected = stored(tmp_path, first)
            raise RuntimeError("later item failed")
    assert writes
    assert ledger.load_days(tmp_path, LEDGER, [DATE], model=VisualAttemptRow) == [expected]
    assert "state/raw/visual-design-attempts" in permissions("work", date=DATE)
    assert "state/raw/visual-design-attempts" not in permissions("assemble", date=DATE)


def test_old_attempts_remain_readable_without_invented_outcome_evidence() -> None:
    old = VisualAttemptRow(
        version="2026-10-27T11:32", date=DATE, run_id=RUN, item_id="energy-01",
        decision=PlanDecision.NONE, none_reason=NoneReason.MODEL_DECLINED,
        state=VisualState.ABSENT,
    )
    read = VisualAttemptRow.from_csv_row(old.csv_row())
    assert read == old
    assert read.planned_type is read.rendered_type is None
    assert read.gate_floor_applied is None
    with pytest.raises(ValidationError):
        VisualAttemptRow.model_validate(old.model_dump() | {"planned_type": "bar"})
