"""Compile and publish a source-backed actor/claim grid.

The grid is text, not chart marks. It has its own persisted contract and reader
so adding it cannot change the chart payload or the browser's chart protocol.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.element import Element, ElementKind, ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import PlanDecision, VisualPlan, VisualType
from idhazh.contracts.visual_decision import (
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.contracts.whowhat_grid import (
    WhowhatClaimSpan,
    WhowhatEntitySpan,
    WhowhatGridData,
    WhowhatGridRow,
    WhowhatSourceSpan,
)
from idhazh.render.write import asset_relpath, log_render_failed, write_bytes_atomic
from idhazh.sanitize import sanitize
from idhazh.text_fit import fit_source_span
from idhazh.visual_vocabulary import whowhat_rows

LOG = logging.getLogger("idhazh")


class WhowhatCompileError(RuntimeError):
    """The selected plan did not become a source-backed grid."""


@dataclass(frozen=True, slots=True)
class CompiledWhowhatGrid:
    """The persisted grid and its derived accessibility summary."""

    data: WhowhatGridData
    alt_text: str
    paired_rows: int


def _source_span(
    element: Element, text: str, *, max_label_characters: int
) -> WhowhatSourceSpan:
    """Re-slice one selected element against this article before persisting it."""
    excerpt = text[element.span_start : element.span_end]
    if excerpt != element.span_excerpt:
        raise WhowhatCompileError("a selected span no longer matches the article text")
    values = {
        "element_id": element.element_id,
        "sentence_index": element.sentence_index,
        "span_start": element.span_start,
        "span_end": element.span_end,
        "span_excerpt": excerpt,
        "display_text": fit_source_span(
            excerpt, max_characters=max_label_characters
        ),
    }
    if element.kind is ElementKind.ENTITY:
        return WhowhatEntitySpan.model_validate(values)
    if element.kind is ElementKind.CLAIM:
        return WhowhatClaimSpan.model_validate(values)
    raise WhowhatCompileError("a whowhat cell must cite an entity or a claim element")


def compile_whowhat_grid(
    plan: VisualPlan,
    table: ElementTable,
    article: Article,
    *,
    visuals: VisualsConfig,
) -> CompiledWhowhatGrid:
    """Compile selected, unambiguous same-sentence pairs into fixed-width rows."""
    if plan.decision is not PlanDecision.VISUAL or plan.type is not VisualType.WHOWHAT:
        raise WhowhatCompileError("only a visual whowhat plan becomes a grid")
    if article.text is None or not article.text:
        raise WhowhatCompileError("the article has no text to ground a grid in")
    if table.item_id != article.item_id or table.url_key != article.url_key:
        raise WhowhatCompileError("the element table and article have different identities")
    if table.source_text_length != len(article.text):
        raise WhowhatCompileError("the element table and article have different text lengths")
    if table.source_text_hash != derive_text_digest(article.text):
        raise WhowhatCompileError("the element table was built from different article text")
    if table.span_drift(article.text) is not None:
        raise WhowhatCompileError("an element span no longer matches the article text")

    selected_entities = set(plan.encodings.entity)
    selected_claims = set(plan.encodings.event_label)
    entities = [
        element for element in table.elements
        if element.element_id in selected_entities and element.kind is ElementKind.ENTITY
    ]
    claims = [
        element for element in table.elements
        if element.element_id in selected_claims and element.kind is ElementKind.CLAIM
    ]
    if len(entities) != len(selected_entities) or len(claims) != len(selected_claims):
        raise WhowhatCompileError("a selected actor or claim is missing from the element table")

    paired_rows = whowhat_rows(entities, claims)
    if not paired_rows:
        raise WhowhatCompileError("the plan selects no actor rows")

    rows: list[WhowhatGridRow] = []
    for pair in paired_rows:
        if pair.entity is None or pair.claim is None:
            rows.append(WhowhatGridRow(actor=None, claim=None))
            continue
        actor = _source_span(
            pair.entity, article.text, max_label_characters=visuals.max_label_characters
        )
        claim = _source_span(
            pair.claim, article.text, max_label_characters=visuals.max_label_characters
        )
        if not isinstance(actor, WhowhatEntitySpan) or not isinstance(claim, WhowhatClaimSpan):
            raise WhowhatCompileError("a whowhat row did not resolve to an actor and a claim")
        if actor.sentence_index != claim.sentence_index:
            raise WhowhatCompileError("a whowhat row crosses sentence boundaries")
        rows.append(WhowhatGridRow(actor=actor, claim=claim))

    data = WhowhatGridData(
        version=WhowhatGridData.schema_version(),
        item_id=article.item_id,
        rows=rows,
    )
    paired = sum(row.actor is not None and row.claim is not None for row in data.rows)
    return CompiledWhowhatGrid(
        data=data,
        alt_text=f"Actor and claim grid with {paired} source-backed pairs.",
        paired_rows=paired,
    )


def render_planned_whowhat(
    decision: VisualDecision,
    plan: VisualPlan,
    table: ElementTable,
    article: Article,
    *,
    date: str,
    public_root: Path,
    relpath: str,
    visuals: VisualsConfig,
    run_id: str | None = None,
) -> VisualDecision:
    """Compile, atomically write and record one whowhat grid decision."""
    if decision.kind is not VisualKind.NONE:
        raise ValueError("a planned visual starts as an item decided to nothing")
    if plan.type is not VisualType.WHOWHAT:
        raise ValueError("the grid writer accepts only a whowhat plan")
    if decision.item_id != article.item_id:
        raise ValueError("the whowhat decision and article have different identities")
    expected_relpath = asset_relpath(date, article.item_id)
    if relpath != expected_relpath:
        raise ValueError(
            f"{article.item_id} grid path must be {expected_relpath}, not {relpath}"
        )
    if decision.planned_type is None:
        decision = VisualDecision.model_validate(
            decision.model_dump(mode="json")
            | {"planned_type": plan.type.value, "downgrade_depth": 0}
        )
    try:
        compiled = compile_whowhat_grid(plan, table, article, visuals=visuals)
    except (WhowhatCompileError, ValidationError, ValueError) as error:
        return VisualDecision.model_validate(
            decision.model_dump(mode="json") | {"rationale": sanitize(str(error))}
        )

    planned = VisualDecision.model_validate(
        decision.model_dump(mode="json")
        | {
            "kind": VisualKind.WHOWHAT.value,
            "none_reason": None,
            "spec": None,
            "chart_evidence": None,
            "whowhat_grid": compiled.data.model_dump(mode="json"),
            "alt_text": compiled.alt_text,
        }
    )
    try:
        write_bytes_atomic(public_root / relpath, compiled.data.to_json().encode("utf-8"))
    except OSError as error:
        log_render_failed(planned, error=error, run_id=run_id)
        return VisualDecision.model_validate(
            planned.model_dump(mode="json")
            | {
                "visual_state": VisualState.RENDER_FAILED,
                "failure_detail": f"the data file could not be written: {type(error).__name__}",
            }
        )
    return VisualDecision.model_validate(
        planned.model_dump(mode="json")
        | {
            "visual_state": VisualState.RENDERED,
            "data_path": relpath,
            "rendered_type": VisualType.WHOWHAT.value,
            "marks": compiled.paired_rows,
        }
    )


def write_whowhat_from_decisions(
    day: DigestDay, decisions: Iterable[VisualDecision], *, public_root: Path
) -> None:
    """Publish only this run's whowhat files, without entering the chart writer."""
    decisions = tuple(decisions)
    if any(decision.kind is not VisualKind.WHOWHAT for decision in decisions):
        raise ValueError("the whowhat writer accepts only whowhat decisions")
    rendered = {
        decision.item_id: decision
        for decision in decisions
        if decision.visual_state is VisualState.RENDERED
    }
    for item in day.items:
        decision = rendered.get(item.item_id)
        if decision is None or item.visual is None or item.visual.data_path is None:
            continue
        relpath = asset_relpath(day.date, item.item_id)
        if (
            decision.data_path != relpath
            or item.visual.data_path != relpath
            or item.visual.kind is not VisualKind.WHOWHAT
        ):
            raise ValueError(
                f"{item.item_id} is not consistently filed as a whowhat grid at {relpath}"
            )
        grid = decision.whowhat_grid
        if grid is None or grid.item_id != item.item_id:
            raise ValueError(f"{item.item_id}: the decision carries no matching whowhat grid")
        target = public_root / relpath
        if not target.is_file():
            write_bytes_atomic(target, grid.to_json().encode("utf-8"))
