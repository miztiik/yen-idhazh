"""A source-backed actor/claim grid, separate from chart mark data."""

from __future__ import annotations

from typing import ClassVar, Final, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import ChangelogEntry, Contract, ItemId, Model
from idhazh.contracts.element import ElementId, ElementKind, derive_element_id
from idhazh.contracts.visual import MAX_IDS_PER_ROLE

MAX_WHOWHAT_ROWS: Final = MAX_IDS_PER_ROLE


class WhowhatSourceSpan(Model):
    """A bounded source span, fitted display text and position in one article."""

    element_id: ElementId
    sentence_index: int = Field(ge=0)
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=1)
    span_excerpt: UntrustedLine
    display_text: UntrustedLine

    @model_validator(mode="after")
    def _span_is_exactly_its_excerpt(self) -> Self:
        if self.span_end <= self.span_start:
            raise ValueError("a source span ends after it starts")
        if self.span_end - self.span_start != len(self.span_excerpt):
            raise ValueError("a source span's width matches its excerpt")
        if self.display_text != self.span_excerpt:
            if (
                len(self.display_text) <= 3
                or len(self.display_text) >= len(self.span_excerpt)
                or not self.display_text.endswith("...")
                or not self.span_excerpt.startswith(self.display_text[:-3])
            ):
                raise ValueError("display text is a source prefix followed by an ellipsis")
        return self


class WhowhatEntitySpan(WhowhatSourceSpan):
    kind: Literal[ElementKind.ENTITY] = ElementKind.ENTITY

    @model_validator(mode="after")
    def _element_id_names_its_entity_span(self) -> Self:
        if self.element_id != derive_element_id(ElementKind.ENTITY, self.span_start, self.span_end):
            raise ValueError("an entity element id is derived from its source span")
        return self

class WhowhatClaimSpan(WhowhatSourceSpan):
    kind: Literal[ElementKind.CLAIM] = ElementKind.CLAIM

    @model_validator(mode="after")
    def _element_id_names_its_claim_span(self) -> Self:
        if self.element_id != derive_element_id(ElementKind.CLAIM, self.span_start, self.span_end):
            raise ValueError("a claim element id is derived from its source span")
        return self


class WhowhatGridRow(Model):
    """Two fixed-width cells; either both carry a same-sentence pair or neither does."""

    actor: WhowhatEntitySpan | None
    claim: WhowhatClaimSpan | None

    @model_validator(mode="after")
    def _cells_are_paired_in_one_sentence(self) -> Self:
        if (self.actor is None) != (self.claim is None):
            raise ValueError("an actor/claim row carries both cells or leaves both empty")
        if self.actor is not None and self.claim is not None:
            if self.actor.sentence_index != self.claim.sentence_index:
                raise ValueError("an actor and claim in a row come from the same sentence")
        return self


class WhowhatGridData(Contract):
    """The persisted, versioned data read by the whowhat grid component."""

    __schema_stem__: ClassVar[str] = "whowhat-grid"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-28",
            change="Initial source-backed actor/claim grid payload.",
            why="Text cells need their own versioned contract without changing chart data.",
        ),
    )

    item_id: ItemId
    rows: list[WhowhatGridRow] = Field(min_length=1, max_length=MAX_WHOWHAT_ROWS)

    @model_validator(mode="after")
    def _a_grid_has_at_least_one_source_pair(self) -> Self:
        if not any(row.actor is not None and row.claim is not None for row in self.rows):
            raise ValueError("a whowhat grid carries at least one paired source row")
        return self
