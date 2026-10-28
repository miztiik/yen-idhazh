"""Compile and write source-backed actor/claim grids from local fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

from idhazh import config
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.element import ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualPlan, VisualType
from idhazh.contracts.visual_decision import NoneReason, VisualDecision, VisualKind, VisualState
from idhazh.render.whowhat_grid import (
    WhowhatCompileError,
    compile_whowhat_grid,
    render_planned_whowhat,
)
from idhazh.render.write import asset_relpath
from idhazh.text_fit import fit_source_span

pytestmark = pytest.mark.visual

ARTICLE_FIXTURE = FIXTURES_DIR / "visual-validator" / "articles" / "whowhat.txt"
PLAN_FIXTURE = FIXTURES_DIR / "visual-validator" / "plans" / "whowhat.json"
TABLE_FIXTURE = FIXTURES_DIR / "visual-validator" / "tables" / "whowhat.json"
DATE = "2026-10-28"


def article_for_fixture(table: ElementTable) -> Article:
    """Use a real article contract with the local source text and table identity."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    text = read_text(ARTICLE_FIXTURE).rstrip("\r\n")
    words = len(text.split())
    payload.update(
        {
            "item_id": table.item_id,
            "url_key": table.url_key,
            "canonical_url": table.canonical_url,
            "source_url": table.canonical_url,
            "vertical": table.item_id.split("-", maxsplit=1)[0],
            "text": text,
            "word_count": words,
            "source_word_count": words,
            "token_count": words,
        }
    )
    return Article.model_validate(payload)


def whowhat_inputs() -> tuple[VisualPlan, ElementTable, Article]:
    plan = VisualPlan.read(PLAN_FIXTURE)
    table = ElementTable.read(TABLE_FIXTURE)
    article = article_for_fixture(table)
    return plan, table, article


def initial_decision(article: Article) -> VisualDecision:
    """The normal pre-render decision, with identity from the article fixture."""
    return VisualDecision(
        version=VisualDecision.schema_version(),
        item_id=article.item_id,
        url_key=article.url_key,
        kind=VisualKind.NONE,
        rationale="the fixture has a validated whowhat plan",
        model_id="fixture-model",
        decided_at="2026-10-28T00:00:00Z",
        drafted_chart=False,
        none_reason=NoneReason.VALIDATION_FAILED,
        planned_type=VisualType.WHOWHAT,
        downgrade_depth=0,
    )


def test_compiler_emits_a_rectangular_grid_with_only_fixture_backed_pairs() -> None:
    plan, table, article = whowhat_inputs()
    visuals = config.load(CONFIG_DIR).app.visuals

    compiled = compile_whowhat_grid(plan, table, article, visuals=visuals)

    assert compiled.data.item_id == article.item_id
    assert len(compiled.data.rows) == 4
    assert compiled.paired_rows == 2
    assert (compiled.data.rows[1].actor, compiled.data.rows[1].claim) == (None, None)
    assert (compiled.data.rows[2].actor, compiled.data.rows[2].claim) == (None, None)
    assert compiled.data.rows[0].actor is not None
    assert compiled.data.rows[0].claim is not None
    assert compiled.data.rows[3].actor is not None
    assert compiled.data.rows[3].claim is not None

    text = article.text
    assert text is not None
    for row in compiled.data.rows:
        assert (row.actor is None) == (row.claim is None)
        if row.actor is None or row.claim is None:
            continue
        assert row.actor.sentence_index == row.claim.sentence_index
        assert text[row.actor.span_start : row.actor.span_end] == row.actor.span_excerpt
        assert text[row.claim.span_start : row.claim.span_end] == row.claim.span_excerpt
        assert row.claim.display_text == fit_source_span(
            row.claim.span_excerpt,
            max_characters=visuals.max_label_characters,
        )
        assert row.actor.display_text == fit_source_span(
            row.actor.span_excerpt,
            max_characters=visuals.max_label_characters,
        )


def test_cell_display_reuses_the_shared_fit_limit_without_changing_source_spans() -> None:
    plan, table, article = whowhat_inputs()
    shipped = config.load(CONFIG_DIR).app.visuals
    short_labels = VisualsConfig.model_validate(
        shipped.model_dump(mode="json") | {"max_label_characters": 10}
    )

    compiled = compile_whowhat_grid(plan, table, article, visuals=short_labels)
    actor = compiled.data.rows[0].actor
    claim = compiled.data.rows[0].claim

    assert actor is not None
    assert actor.span_excerpt == "Northstar Energy"
    assert actor.display_text == fit_source_span(
        actor.span_excerpt,
        max_characters=short_labels.max_label_characters,
    )
    assert actor.display_text.endswith("...")
    assert claim is not None
    assert claim.span_excerpt == "announced it will close the Ridge facility next year"
    assert claim.display_text == fit_source_span(
        claim.span_excerpt,
        max_characters=short_labels.max_label_characters,
    )
    assert claim.display_text.endswith("...")


def test_compiler_rejects_a_source_span_that_no_longer_slices_from_the_article() -> None:
    plan, table, article = whowhat_inputs()
    text = article.text
    assert text is not None
    changed_text = text.replace("Northstar", "Southstar", 1)
    changed_article = Article.model_validate(
        article.model_dump(mode="json") | {"text": changed_text}
    )
    changed_table_payload = table.model_dump(mode="json")
    changed_table_payload["source_text_hash"] = derive_text_digest(changed_text)
    changed_table = ElementTable.model_validate(changed_table_payload)

    with pytest.raises(WhowhatCompileError, match="span no longer matches"):
        compile_whowhat_grid(
            plan,
            changed_table,
            changed_article,
            visuals=config.load(CONFIG_DIR).app.visuals,
        )


def test_dedicated_writer_publishes_the_separate_grid_payload_atomically(tmp_path: Path) -> None:
    plan, table, article = whowhat_inputs()
    relpath = asset_relpath(DATE, article.item_id)

    decision = render_planned_whowhat(
        initial_decision(article),
        plan,
        table,
        article,
        date=DATE,
        public_root=tmp_path,
        relpath=relpath,
        visuals=config.load(CONFIG_DIR).app.visuals,
    )

    assert decision.kind is VisualKind.WHOWHAT
    assert decision.visual_state is VisualState.RENDERED
    assert decision.rendered_type is VisualType.WHOWHAT
    assert decision.data_path == relpath
    assert decision.spec is None
    assert decision.chart_evidence is None
    assert decision.whowhat_grid is not None
    written = read_text(tmp_path / relpath)
    assert json.loads(written) == json.loads(decision.whowhat_grid.to_json())


def test_decision_grid_must_name_the_same_item(tmp_path: Path) -> None:
    plan, table, article = whowhat_inputs()
    decision = render_planned_whowhat(
        initial_decision(article),
        plan,
        table,
        article,
        date=DATE,
        public_root=tmp_path,
        relpath=asset_relpath(DATE, article.item_id),
        visuals=config.load(CONFIG_DIR).app.visuals,
    )
    payload = decision.model_dump(mode="json")
    assert payload["whowhat_grid"] is not None
    payload["whowhat_grid"]["item_id"] = "ai-18"

    with pytest.raises(ValidationError, match="names its decision item"):
        VisualDecision.model_validate(payload)


def test_a_failed_grid_write_records_failure_without_a_published_path(tmp_path: Path) -> None:
    plan, table, article = whowhat_inputs()
    blocked_root = tmp_path / "not-a-directory"
    blocked_root.write_text("occupied", encoding="utf-8")
    relpath = asset_relpath(DATE, article.item_id)

    decision = render_planned_whowhat(
        initial_decision(article),
        plan,
        table,
        article,
        date=DATE,
        public_root=blocked_root,
        relpath=relpath,
        visuals=config.load(CONFIG_DIR).app.visuals,
    )

    assert decision.kind is VisualKind.WHOWHAT
    assert decision.visual_state is VisualState.RENDER_FAILED
    assert decision.data_path is None
    assert decision.failure_detail is not None
    assert decision.whowhat_grid is not None
