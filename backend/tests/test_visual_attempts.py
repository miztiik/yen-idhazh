"""Do actual visual outcomes survive registered storage without losing refused attempts?"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from support.ledger import writer_identity
from support.paths import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text
from support.prompts import SUMMARIZE_AND_PLAN_REPLIES
from test_chart_vocabulary import draw, inputs, settings
from test_whowhat_grid import whowhat_inputs

from idhazh import completed_writes, ledger
from idhazh.classify import calls
from idhazh.contracts.article import Article
from idhazh.contracts.base import ServerJob
from idhazh.contracts.element import ElementTable
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual import PlanDecision, VisualType
from idhazh.contracts.visual_decision import NoneReason, VisualDecision, VisualState
from idhazh.contracts.visual_telemetry import VisualAttemptRow
from idhazh.elements import ExtractionHealth
from idhazh.fingerprint import text_digest
from idhazh.llm.server import Completion, window
from idhazh.stages import common
from idhazh.stages.two_calls import _decide_the_visual, _drawn
from idhazh.telemetry import visual_attempts
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
            settings(downgrade_enabled=True, downgrade_floor_percentiles=[50]),
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
    summary, _, table = inputs()
    article = Article.read(CONTRACT_FIXTURES_DIR / "article" / "ok.json")
    knobs = settings()
    stamp = {
        "version": VisualDecision.schema_version(), "model_id": "fixture-model",
        "decided_at": f"{DATE}T12:00:00Z",
    }
    cut = json.loads(read_text(SUMMARIZE_AND_PLAN_REPLIES / "cut-in-the-plan.json"))[
        "choices"
    ][0]["message"]["content"]
    cases = (
        (Completion(content="", finish_reason="stop"), False),
        (Completion(content=cut, finish_reason="length", prompt_tokens=0), True),
        (Completion(
            content=cut, finish_reason="length",
            prompt_tokens=window(knobs.models.summarizer.server),
        ), True),
        (Completion(content="not JSON", finish_reason="stop"), True),
    )
    decisions = [
        _decide_the_visual(
            summary, article, reply, table, settings=knobs, date=DATE, stamp=stamp,
            wants_a_plan=wants, run_id=RUN,
        )
        for reply, wants in cases
    ]
    original = json.loads(read_text(SUMMARIZE_AND_PLAN_REPLIES / "summary-and-plan.json"))[
        "choices"
    ][0]["message"]["content"]
    content = json.loads(original)
    content["visual"] = {
        name: value for name, value in json.loads(
            read_text(FIXTURES_DIR / "visual-validator" / "plans" / "declines.json")
        ).items() if name not in {"version", "plan_version"}
    }
    # Validate the recorded reply before exercising the production decision router.
    calls.parse_summarize_and_plan(json.dumps(content), source_words=article.band_source_words)
    decisions.append(_decide_the_visual(
        summary, article, Completion(content=json.dumps(content), finish_reason="stop"), table,
        settings=knobs, date=DATE, stamp=stamp, wants_a_plan=True, run_id=RUN,
    ))
    observed = {stored(tmp_path / str(index), decision).none_reason
                for index, decision in enumerate(decisions)}
    assert observed == set(NoneReason)
    assert len(observed) == 5


def test_whowhat_uses_the_same_attempt_mapping_and_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    plan, table, article = whowhat_inputs()
    summary, _, _ = inputs()
    summary = type(summary).model_validate(summary.model_dump(mode="json") | {
        "item_id": article.item_id, "url_key": article.url_key,
    })
    decision = _drawn(
        summary, plan, table, article=article, settings=settings(), date=DATE,
        stamp={"version": VisualDecision.schema_version(), "model_id": "fixture-model",
               "decided_at": f"{DATE}T12:00:00Z"},
        run_id=RUN,
    )
    row = stored(tmp_path, decision)
    assert row.planned_type is row.rendered_type is VisualType.WHOWHAT
    assert row.state is VisualState.RENDERED
    assert row.visual_id == decision.visual_id


def test_real_compiler_refusal_remains_a_drafted_attempt(tmp_path: Path) -> None:
    plan, table, article = whowhat_inputs()
    assert article.text is not None
    changed_text = article.text.replace("Northstar", "Southstar", 1)
    changed_article = Article.model_validate(
        article.model_dump(mode="json") | {"text": changed_text}
    )
    changed_table = ElementTable.model_validate(
        table.model_dump(mode="json") | {"source_text_hash": text_digest(changed_text)}
    )
    summary, _, _ = inputs()
    summary = type(summary).model_validate(summary.model_dump(mode="json") | {
        "item_id": article.item_id, "url_key": article.url_key,
    })
    decision = _drawn(
        summary, plan, changed_table, article=changed_article, settings=settings(), date=DATE,
        stamp={"version": VisualDecision.schema_version(), "model_id": "fixture-model",
               "decided_at": f"{DATE}T12:00:00Z"},
        run_id=RUN,
    )
    row = stored(tmp_path, decision)
    assert row.decision is PlanDecision.VISUAL
    assert row.planned_type is VisualType.WHOWHAT and row.rendered_type is None
    assert row.none_reason is NoneReason.VALIDATION_FAILED
    assert row.rejection_reason is None
    assert row.state is VisualState.ABSENT


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
    assert read.planned_type is read.rendered_type is read.gate_floor_applied is None
    with pytest.raises(ValidationError):
        VisualAttemptRow.model_validate(old.model_dump() | {"planned_type": "bar"})


@pytest.mark.parametrize("name", ["visuals_full_grain_months", "visual_aggregate_keep_months"])
def test_obsolete_visual_retention_knobs_are_refused_by_name(name: str) -> None:
    with pytest.raises(ValidationError, match=name):
        ObservabilityConfig.model_validate({name: 14})
