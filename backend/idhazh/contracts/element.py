"""Every fact a run found in one article, with the characters that prove it.

An **element** is one fact - a quantity, a date, an entity, a place, a quote or
a claim - together with the character range of `Article.text` it was cut from.
The range is what makes a drawn figure checkable: anybody holding the article
can re-slice it and see the same characters.

**A span here is a character range, not a trace span.** `span_rollup.py` uses
the word for an execution timing and this module never does. `span_start` and
`span_end` are indices into one string, half-open in Python's own convention, so
`article.text[span_start:span_end]` is `span_excerpt` and nothing else.

**The string they index is `Article.text`** - post-sanitize and post-truncation
(`idhazh.extract`). It is neither the fetched page nor the pre-cap body, so an
offset taken against either of those points somewhere else. `ElementTable`
carries the sha256 of that exact string, one hash per article, so a later read
can tell whether the text a span was cut from is the text it now holds.

**One name for the verbatim slice, and it is `span_excerpt`.** `raw` on
`visual_planner.NumericFact` is whitespace-cleaned and drops the magnitude word
and the unit, so it is not a slice of anything. `surface` is this project's word
for a place something is shown or persisted, in 458 sentences across 104 files
(measured 2026-09-08), and it does not get a second meaning here. The reason the
name is one word rather than two fields is on
`docs/architecture/extraction/elements.md`.

Two tiers, and the split is the whole trust argument.

**Tier 1 is what code found.** `element_id`, `kind`, `span_start`, `span_end`,
`span_excerpt`, `value`, `unit`, `sentence_index` and `extractor` come from a
pattern over the bytes and from arithmetic on offsets. Nothing model-authored
reaches them, on any kind. Every one of them is required - stated as null where
the kind has none - so an element carrying a judgement and no anchor does not
load.

**Tier 2 is what a labeller said about it.** `entity`, `time`, `measure`,
`measure_canonical`, `dimension`, `salience`, `attribution` and `hedge` are
optional and a later pass may assign them; `label_source` and `ledger_version`
record who assigned them and under which pass. A judged field without that pair
is unattributable and the pair with nothing judged is a claim about nothing, so
neither half loads alone.

**`context` is not a field here, and the absence is deliberate.**
`visual_planner.NumericFact` carries a whitespace-cleaned window of the words
around a number. This shape replaces that derived string with a pointer:
`sentence_index` plus the span says where the words are, and `Article.text`
still holds them, so nothing stores a second copy of the reader's sentence.
`NumericFact.context` is untouched by this module and retires with its producer.

Six kinds land here and two of them have a producer. A kind with no producer is
legal and simply never appears, which is cheaper than widening a persisted shape
four more times.

**`elements` is capped and `candidates_found` is not, and that is the point.**
How many candidates a producer keeps is a tunable, so the length of `elements`
saturates. A density signal read off a saturating counter cannot tell a short
note carrying a few figures from a data story carrying many, and it fails
silently because a capped counter still returns a plausible integer. The count
is taken before any dedupe and before the cap, one per kind, and the shape
refuses a table that kept more of a kind than it says it found.
"""

from __future__ import annotations

import re
from collections import Counter
from enum import StrEnum
from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    ItemId,
    Model,
    SchemaVersion,
    Sha256,
    Slug,
    Url,
    UrlKey,
    derive_url_key,
)

#: `<kind>-<span_start>-<span_end>`: the element's address inside its article.
#: Derived from the two facts that make it unique there, so it is rebuilt on
#: read rather than trusted, and legible in a committed diff.
ELEMENT_ID_PATTERN: Final = r"^[a-z]+-[0-9]+-[0-9]+$"
#: A quantity's value: a decimal, pinned as text for the reason a timestamp is.
#: One spelling, and no float formatting that can drift under a committed file.
QUANTITY_VALUE_PATTERN: Final = r"^-?[0-9]+(?:\.[0-9]+)?$"
#: A date's value, and a Tier 2 time reference. Absolute dates and years only:
#: "three years ago" resolves against a publication date the article never
#: wrote, and a derived value is not a found one.
DATE_OR_YEAR_PATTERN: Final = r"^\d{4}(?:-\d{2}-\d{2})?$"

ElementId = Annotated[str, StringConstraints(pattern=ELEMENT_ID_PATTERN)]
DateOrYear = Annotated[str, StringConstraints(pattern=DATE_OR_YEAR_PATTERN)]
#: The two bounds a producer needs as numbers rather than as annotations. A
#: pattern over fetched bytes can match a 200-digit serial number or a
#: 600-character hyphenated word, and a producer that cannot read the bound has
#: no way to refuse one except by letting the shape raise mid-article (Rule #11).
VALUE_MAX_LENGTH: Final = 40
UNIT_MAX_LENGTH: Final = 32
#: The machine-readable reading of what the span says. Bounded because an
#: unbounded string on a payload is a defect waiting for a malformed page.
ElementValue = Annotated[str, StringConstraints(min_length=1, max_length=VALUE_MAX_LENGTH)]
#: Normalised: lowercase and de-pluralised, or a currency symbol, or `%`. What
#: makes "these measure the same thing" a string comparison instead of a
#: judgement.
Unit = Annotated[str, StringConstraints(min_length=1, max_length=UNIT_MAX_LENGTH)]
#: Which model or person assigned the Tier 2 fields. A model id from the run
#: manifest, or a labeller's name - never a free sentence.
LabelSource = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class ElementKind(StrEnum):
    """The six things an element can be.

    Declared in the order the producers arrive: `quantity` and `date` are pure
    patterns over the bytes and ship with this contract's first two producers.
    The other four need a model to point at them, and until that producer exists
    they are legal and never written.
    """

    #: A number a reader can plot, with the unit that makes it comparable.
    QUANTITY = "quantity"
    #: An absolute date or a bare year the article stated.
    DATE = "date"
    #: A named organisation, person or product.
    ENTITY = "entity"
    #: A named location.
    PLACE = "place"
    #: Words the article attributed to somebody.
    QUOTE = "quote"
    #: An assertion the article made in its own voice.
    CLAIM = "claim"


class Extractor(StrEnum):
    """Which path found the element.

    It exists so a later run can measure the two apart. Without it a fall in the
    quantity count reads the same whether a pattern stopped matching or a model
    stopped pointing, and those have different fixes.

    Not to be confused with `Article.extractor_version`, which is the version of
    the HTML-to-text extractor that produced the article body. That names the
    stage that made the string; this names the pass that found a fact inside it.
    """

    #: A pattern over the article's own bytes. Code cut every character.
    REGEX = "regex"
    #: A model proposed the location and code cut the characters at it.
    MODEL = "model"


_VALUE_GRAMMAR: Final[dict[ElementKind, re.Pattern[str]]] = {
    ElementKind.QUANTITY: re.compile(QUANTITY_VALUE_PATTERN),
    ElementKind.DATE: re.compile(DATE_OR_YEAR_PATTERN),
}
#: The kinds that read as something other than words. Everything else carries no
#: value, because a number invented for a quote is exactly the defect the span
#: exists to refuse.
VALUED_KINDS: Final = frozenset(_VALUE_GRAMMAR)

#: The two tiers, named so the split is machine-checked rather than promised in
#: a docstring. Every field of `Element` belongs to exactly one of them, and the
#: module refuses to import if one is left unassigned.
TIER_ONE_FIELDS: Final[tuple[str, ...]] = (
    "element_id",
    "kind",
    "span_start",
    "span_end",
    "span_excerpt",
    "value",
    "unit",
    "sentence_index",
    "extractor",
)
TIER_TWO_FIELDS: Final[tuple[str, ...]] = (
    "entity",
    "time",
    "measure",
    "measure_canonical",
    "dimension",
    "salience",
    "attribution",
    "hedge",
    "label_source",
    "ledger_version",
)
#: The Tier 2 fields that carry a judgement. `label_source` and `ledger_version`
#: are the other two, and they record who made the judgements rather than making
#: one.
JUDGED_FIELDS: Final[tuple[str, ...]] = TIER_TWO_FIELDS[:-2]


def derive_element_id(kind: ElementKind, span_start: int, span_end: int) -> str:
    """The element's address inside its article: its kind and its span.

    Rebuilt on read like every other derived key here, so an element cannot
    claim an identity its own span does not produce. It is unique within one
    table because two elements of one kind cannot hold the same characters, and
    the table names the article.
    """
    return f"{kind.value}-{span_start}-{span_end}"


class Element(Model):
    """One fact, and the characters it was cut from."""

    element_id: ElementId = Field(
        description="<kind>-<span_start>-<span_end>, recomputed on read, never trusted."
    )
    kind: ElementKind
    span_start: int = Field(ge=0, description="Index into Article.text. Inclusive.")
    span_end: int = Field(ge=1, description="Index into Article.text. Exclusive.")
    span_excerpt: UntrustedLine = Field(
        description=(
            "The verbatim slice Article.text[span_start:span_end]. Untrusted text: "
            "data and never instruction (Rule #11), and never republished to a reader."
        )
    )
    value: ElementValue | None = Field(
        description=(
            "What the span reads as - a decimal for a quantity, a date or a year for a "
            "date, and null for the four kinds that are words. Stated even when null."
        )
    )
    unit: Unit | None = Field(
        description="A quantity's normalised unit, and null on every other kind."
    )
    sentence_index: int = Field(
        ge=0, description="Which sentence of Article.text the span starts in, from zero."
    )
    extractor: Extractor

    entity: Slug | None = Field(
        default=None, description="Tier 2. The watchlist entity this element is about."
    )
    time: DateOrYear | None = Field(
        default=None, description="Tier 2. When the element applies, if that is not now."
    )
    measure: UntrustedLine | None = Field(
        default=None, description="Tier 2. What is measured, in the article's own words."
    )
    measure_canonical: Slug | None = Field(
        default=None,
        description=(
            "Tier 2. The same measure under one controlled name, so two articles' "
            "words for it compare as a string. A free-text canonical name is not "
            "canonical, it is a second wording."
        ),
    )
    dimension: Slug | None = Field(
        default=None, description="Tier 2. What the element is broken down by."
    )
    salience: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Tier 2. How much of the story this fact is."
    )
    attribution: UntrustedLine | None = Field(
        default=None, description="Tier 2. Who the article said it, if anyone."
    )
    hedge: bool | None = Field(
        default=None,
        description="Tier 2. Whether the article hedged the fact rather than asserting it.",
    )
    label_source: LabelSource | None = Field(
        default=None,
        description="Tier 2 provenance. Which model or person assigned the judgements.",
    )
    ledger_version: SchemaVersion | None = Field(
        default=None,
        description="Tier 2 provenance. The date-stamp of the pass that assigned them.",
    )

    @model_validator(mode="after")
    def _the_span_is_what_it_says_it_is(self) -> Self:
        if self.span_end <= self.span_start:
            raise ValueError("span_end must be past span_start - a span covers a character")
        if len(self.span_excerpt) != self.span_end - self.span_start:
            raise ValueError("span_excerpt is the verbatim slice, so its length is the span width")
        if self.element_id != derive_element_id(self.kind, self.span_start, self.span_end):
            raise ValueError("element_id must be <kind>-<span_start>-<span_end>, rebuilt on read")
        return self

    @model_validator(mode="after")
    def _only_a_measured_kind_reads_as_a_value(self) -> Self:
        if self.kind in VALUED_KINDS:
            if self.value is None:
                raise ValueError(f"a {self.kind.value} element carries the value code read out")
            if not _VALUE_GRAMMAR[self.kind].fullmatch(self.value):
                raise ValueError(f"a {self.kind.value} value must be written the one way")
        elif self.value is not None:
            raise ValueError("only a quantity or a date carries a value")
        if self.unit is not None and self.kind is not ElementKind.QUANTITY:
            raise ValueError("only a quantity carries a unit")
        return self

    @model_validator(mode="after")
    def _tier_two_is_never_drawn_without_its_anchor(self) -> Self:
        judged = (
            self.entity,
            self.time,
            self.measure,
            self.measure_canonical,
            self.dimension,
            self.salience,
            self.attribution,
            self.hedge,
        )
        assigned = any(field is not None for field in judged)
        if (self.label_source is None) != (self.ledger_version is None):
            raise ValueError("label_source and ledger_version are set together")
        if assigned and self.label_source is None:
            raise ValueError("a judged field carries label_source and ledger_version")
        if self.label_source is not None and not assigned:
            raise ValueError("label_source records a judgement, so one must be present")
        if self.measure_canonical is not None and self.measure is None:
            raise ValueError("measure_canonical canonicalises a measure, so the measure is present")
        return self


_TIERED: Final = TIER_ONE_FIELDS + TIER_TWO_FIELDS
if tuple(Element.model_fields) != _TIERED:
    raise TypeError(
        "every Element field belongs to exactly one tier, in declaration order - "
        f"declared {tuple(Element.model_fields)}, tiered {_TIERED}"
    )


class ElementTable(Contract):
    """Every element one article yielded, and the text they were cut from."""

    __schema_stem__: ClassVar[str] = "element-table"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-08T12:00",
            change=(
                "candidates_found added and required, one count per kind, holding what "
                "each pass matched before the cap. VALUE_MAX_LENGTH and UNIT_MAX_LENGTH "
                "are exported so a producer can refuse what the shape will not hold."
            ),
            why=(
                "`elements` is capped by a tunable, so its length saturates and a density "
                "signal read off it cannot tell a 600-word note carrying 16 figures from "
                "a 3,000-word data story carrying 60 - and the second is the chartable "
                "one. It fails silently, because a capped counter returns a plausible "
                "integer. Required rather than defaulted, because a default of zero is "
                "indistinguishable from a pass that genuinely found nothing, which is the "
                "same silent failure one level down; nothing had been persisted under the "
                "previous shape, so the only payloads to move were the two committed "
                "fixtures. Keyed by kind because a single total stops answering the "
                "density question the moment a second pass writes into the same table."
            ),
        ),
        ChangelogEntry(
            version="2026-09-08",
            change=(
                "Initial shape: six element kinds, a Tier 1 half only code writes and a "
                "Tier 2 half a later labeller may assign, over one article's text."
            ),
            why=(
                "Contracts before logic - the two pattern producers are written against a "
                "fixed payload (Rule #3). Six kinds land in one entry rather than four "
                "later widenings of a persisted shape. `span_excerpt` is the one name for "
                "the verbatim slice, because `raw` is whitespace-cleaned and `surface` is "
                "already this project's word for a place something is shown."
            ),
        ),
    )

    item_id: ItemId
    url_key: UrlKey = Field(
        description="sha256 of canonical_url. The same identity Article carries, rebuilt on read."
    )
    canonical_url: Url = Field(description="The address url_key derives from.")
    source_text_hash: Sha256 = Field(
        description=(
            "sha256 of the Article.text every span indexes - one hash per article, not "
            "per element. A per-element hash would be redundant against this plus the "
            "re-slice, on every article for ever."
        )
    )
    source_text_length: int = Field(
        ge=0,
        description=(
            "Characters in that same string. It is what lets this shape refuse a span "
            "past the end of the text without holding the text."
        ),
    )
    elements: list[Element] = Field(
        default_factory=list,
        description=(
            "In the order the article wrote them. Uncapped here: what a producer keeps "
            "is a tunable and lives in config, not in the shape."
        ),
    )
    candidates_found: dict[ElementKind, int] = Field(
        description=(
            "How many candidates each pass matched, before any dedupe and before the "
            "cap. `elements` saturates at the cap and this does not, so the two "
            "together say whether the cap bit and by how much."
        )
    )

    @model_validator(mode="after")
    def _identity_is_rebuilt_not_trusted(self) -> Self:
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("url_key must be the sha256 of canonical_url, recomputed on read")
        return self

    @model_validator(mode="after")
    def _a_kept_element_was_found_first(self) -> Self:
        """The cap only ever removes, so a count below what survived it is impossible.

        This is what stops `candidates_found` from becoming a second number
        nobody checks. A pass that forgot to count before capping, or counted
        the capped list, fails here rather than reporting a plausible integer.
        """
        kept = Counter(element.kind for element in self.elements)
        for kind, count in kept.items():
            found = self.candidates_found.get(kind)
            if found is None:
                raise ValueError(f"{self.item_id} kept {count} {kind.value} elements and counted 0")
            if found < count:
                raise ValueError(
                    f"{self.item_id} kept {count} {kind.value} elements out of {found} found - "
                    "a cap removes, so it cannot keep more than the pass matched"
                )
        for kind, found in self.candidates_found.items():
            if found < 0:
                raise ValueError(f"a pass cannot find {found} {kind.value} elements")
        return self

    @model_validator(mode="after")
    def _every_span_lands_inside_the_text_it_names(self) -> Self:
        ids = [element.element_id for element in self.elements]
        if len(set(ids)) != len(ids):
            raise ValueError("two elements claim one address - a kind and a span identify one fact")
        starts = [element.span_start for element in self.elements]
        if starts != sorted(starts):
            raise ValueError("elements are ordered by span_start, the order the article wrote them")
        for element in self.elements:
            if element.span_end > self.source_text_length:
                raise ValueError(
                    f"{element.element_id} ends past the {self.source_text_length} characters "
                    "the text holds"
                )
        return self
