"""The closed vocabularies and the vertical registry (`config/taxonomy.json`).

Lenses and event types are closed enums rather than free-text strings, so a new
value is a schema change carrying a changelog entry rather than a typo waiting
to happen. Verticals are config-declared, because a vertical is built in the
open over weeks under `draft` status until it clears its feed floor.

An id is an immutable slug; `display_name` is separate and freely mutable, so
renaming what a reader sees never orphans a payload written under the old label.

An id and a display name tell a model nothing, so every entry also carries the
sentence the model is asked to choose against. That sentence is config: change
it and the next run labels against the new text, with no Python edit and no
schema regeneration. The schema bounds the shape - the keys, the id pattern, the
sentence's length - and never the words.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, Model, Slug


class LifecycleStatus(StrEnum):
    """Retire, never delete: a tombstone keeps old payloads valid."""

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class SourceTier(IntEnum):
    """The tier IS the ranking weight (docs/architecture/sources/discovery.md)."""

    INSTITUTION = 1
    TRADE_PRESS = 2
    COMMUNITY = 3


class SourceKind(StrEnum):
    """What kind of speaker this is - the thing a reader uses to decide belief.

    "A company said its product is faster" and "a reporter measured it" are not
    the same claim, and without this they arrive looking identical. The
    dangerous case is `announcement`: forwarding a vendor's own copy without
    knowing it was the vendor is how a reader ends up carrying an ad.
    """

    REPORTING = "reporting"
    ANNOUNCEMENT = "announcement"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    GOVERNMENT = "government"
    COMMUNITY = "community"


class LensId(StrEnum):
    """A question asked of items already collected. Costs no extra request."""

    CHINA = "china"
    AI_ROI = "ai-roi"
    MARKETS = "markets"
    CYBER = "cyber"
    WAR = "war"
    TRADE = "trade"
    CHIPS = "chips"


class EventType(StrEnum):
    """What happened to an item. One or more per item."""

    RELEASE = "release"
    DEAL = "deal"
    ACQUISITION = "acquisition"
    FUNDING = "funding"
    CAPEX = "capex"
    EARNINGS = "earnings"
    REGULATION = "regulation"
    RESEARCH = "research"
    INCIDENT = "incident"


MatchTerm = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9 '/&.-]*$", min_length=2)
]
"""One curated phrase that assigns a tag.

At least two characters, because a one-character term matches most English
prose. Punctuation is dropped before the comparison, so `ai-roi`, `AI/ROI` and
`AI ROI` are the same term - the pattern exists to keep a term readable in
config, not to define the match.
"""


DefinitionText = Annotated[str, StringConstraints(max_length=240)]
"""The sentence a model is asked to choose this entry against.

The bound is a token budget rather than a style rule. Thirty definition
sentences were measured at 805 tokens together with `llama-tokenize` against
the pinned `Qwen3-8B-Q4_K_M` on 2026-09-11, which is about 27 tokens each, and
they ride in every labelling prompt this pipeline sends. 240 characters is
roughly twice that: room to sharpen a sentence, not room for a paragraph.

Empty is legal and means the entry is offered to no prompt. A proposed entry
arrives with no definition, because the words that would go in it came off the
open web and a person writes the real one when they promote it (Rule #11).
`Taxonomy` is what refuses an empty definition on an entry it does offer.
"""


class VocabularyEntry(Model):
    """One word the model chooses, and the sentence it chooses against."""

    display_name: str = Field(min_length=1)
    definition: DefinitionText = Field(
        default="",
        description=(
            "The sentence the model is scored against. It is the label, as far as the "
            "model is concerned: an id and a display name say nothing, and `research` "
            "means whatever sentence sits next to it. Edit it and the next run labels "
            "against the new text - no code change, no schema regeneration. Every "
            "figure measured against the old text is stale from that day, which is why "
            "a measurement records the version of this file it was taken under."
        ),
    )


class Lifecycled(Model):
    """Anything that can be drafted, published and later retired."""

    status: LifecycleStatus = LifecycleStatus.ACTIVE
    retired_on: DateStamp | None = None

    @model_validator(mode="after")
    def _retired_on_matches_status(self) -> Self:
        retired = self.status is LifecycleStatus.RETIRED
        if retired and self.retired_on is None:
            raise ValueError("a retired entry must carry retired_on")
        if not retired and self.retired_on is not None:
            raise ValueError("retired_on is only meaningful on a retired entry")
        return self


AUTO_DISCOVERED_DESCRIPTION: Final = (
    "True when a model proposed this entry rather than a person writing it. The marker "
    "survives promotion on purpose: a word that arrived from an article read six weeks "
    "ago reads exactly like one a person chose, and the difference is the first thing "
    "anybody asks when a label looks wrong. A proposal lands under `draft` status with "
    "no definition, so it is offered to no prompt and rendered on no page until a person "
    "writes the sentence and changes the status in a pull request."
)


class VerticalDef(VocabularyEntry, Lifecycled):
    """A subject with its own reporters and its own feeds.

    It is also the desk vocabulary: a feed declares one of these and a model
    reading the article names one of these. Two deciders, one list of words
    (`docs/concepts/taxonomy.md`).
    """

    id: Slug
    min_feeds: int = Field(
        ge=1,
        description="Feed floor below which the vertical does not render at all.",
    )
    is_auto_discovered: bool = Field(default=False, description=AUTO_DISCOVERED_DESCRIPTION)


class LensDef(VocabularyEntry, Lifecycled):
    id: LensId
    keywords: list[MatchTerm] = Field(
        default_factory=list,
        description=(
            "The curated terms that assign this lens. A lens is assigned when one of "
            "them appears in the item's words as a whole-word phrase, case-folded. "
            "Nothing is derived from the id or the display name: deriving from the id "
            "was measured at 88.2 percent of items, because `ai` sits inside `said`. "
            "An empty list means the lens is never assigned."
        ),
    )
    weight: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "What this lens adds to a story's rank when one of its terms is in the "
            "headline. Zero means the lens only labels. A weighted lens must be an "
            "under-carried theme: the bonus is there to rescue a story one outlet has "
            "and nobody has repeated yet, and on an over-carried theme it only "
            "compounds a lead that repetition already gave."
        ),
    )
    is_auto_discovered: bool = Field(default=False, description=AUTO_DISCOVERED_DESCRIPTION)


class EventDef(VocabularyEntry):
    id: EventType
    keywords: list[MatchTerm] = Field(
        default_factory=list,
        description="The curated terms that assign this event. Same rule as LensDef.keywords.",
    )


class Taxonomy(Contract):
    """`config/taxonomy.json` - the vocabulary every payload indexes against."""

    __schema_stem__: ClassVar[str] = "taxonomy"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-12",
            change=(
                "Added VocabularyEntry.definition to every vertical, lens and event, "
                "and is_auto_discovered to VerticalDef and LensDef."
            ),
            why=(
                "An id and a display name tell a model nothing. `research` means "
                "whatever sentence sits next to it, so the sentence is the label and it "
                "has to be somewhere a person can edit without touching Python - change "
                "the text and the next run labels against it, with no code change and "
                "no schema regeneration. The bound is a token budget: 30 definition "
                "sentences measured 805 tokens together with llama-tokenize against the "
                "pinned Qwen3-8B-Q4_K_M on 2026-09-11, about 27 tokens each, and 240 "
                "characters is roughly twice that. is_auto_discovered says a model "
                "proposed the entry, which stops a word that arrived from the open web "
                "reading like one a person chose. Both are additive with defaults, so a "
                "taxonomy written before this still validates and offers nothing extra "
                "to a prompt; no read-side migration is needed. An entry the vocabulary "
                "does offer must carry its sentence, which is a rule on Taxonomy rather "
                "than a required key, because a draft entry has no definition yet."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30",
            change=(
                "Added the war, trade and chips lenses, and LensDef.weight. "
                "ai-roi keeps its id and is retired in config."
            ),
            why=(
                "A lens could only label, so the vocabulary had no way to say a theme "
                "was worth publishing. Measured 2026-08-30 over the 2,900 published "
                "items on record, 2,683 of them - 92.5 percent - carried no lens at "
                "all, while war words appeared in 637 and tariff words in 75 with no "
                "id to hold them. weight is what a lens adds to a rank when one of its "
                "terms is in the headline, which is all a run has at plan time. Zero is "
                "the default and the answer for most lenses: a bonus rescues a story "
                "one outlet has and nobody has repeated, and on a theme every wire "
                "already carries it compounds a lead repetition gave. Additive with a "
                "default, so a taxonomy written before this still validates and scores "
                "nothing. Three new enum members widen a closed vocabulary, so an older "
                "payload still reads - no published lens id was removed or renamed, and "
                "ai-roi is tombstoned rather than deleted so days that carry it stay "
                "valid (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change="Added keywords to LensDef and EventDef.",
            why=(
                "Both vocabularies shipped with no way to say what assigns a tag, so "
                "nothing ever did: 0 of 2,121 committed items carried a lens or an event. "
                "The rule cannot be derived from the id - measured, deriving it tags 88.2 "
                "percent of items because `ai` sits inside `said` - so it has to be "
                "written down. Additive with an empty default, so a taxonomy written "
                "before this still validates and simply assigns nothing."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22T11:00",
            change="Removed VerticalDef.daily_cap.",
            why=(
                "It decided how big a vertical's day was before the ranking had a say. "
                "Supply and the score set the size now; max_per_source still stops one "
                "feed becoming the vertical."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: verticals, lenses and events.",
            why="Contracts before logic - the vocabulary is fixed before any stage reads it.",
        ),
    )

    verticals: list[VerticalDef]
    lenses: list[LensDef]
    events: list[EventDef]

    @model_validator(mode="after")
    def _vocabularies_are_complete_and_distinct(self) -> Self:
        vertical_ids = [item.id for item in self.verticals]
        if len(set(vertical_ids)) != len(vertical_ids):
            raise ValueError("vertical ids must be distinct")

        lens_ids = [item.id for item in self.lenses]
        if sorted(lens_ids) != sorted(LensId):
            raise ValueError("lenses must label every LensId exactly once")

        event_ids = [item.id for item in self.events]
        if sorted(event_ids) != sorted(EventType):
            raise ValueError("events must label every EventType exactly once")
        return self

    @model_validator(mode="after")
    def _every_offered_entry_carries_its_definition(self) -> Self:
        """A word offered to the model with no sentence beside it is a word it cannot read.

        Only the offered entries. A draft is a proposal a person has not written
        the sentence for yet, and a tombstone is there so an older payload still
        renders - neither reaches a prompt, so neither needs one.
        """
        undefined = [
            f"{kind} {entry_id}"
            for kind, entry_id, defined in (
                *(
                    ("vertical", item.id, bool(item.definition))
                    for item in self.verticals
                    if item.status is LifecycleStatus.ACTIVE
                ),
                *(
                    ("lens", item.id.value, bool(item.definition))
                    for item in self.lenses
                    if item.status is LifecycleStatus.ACTIVE
                ),
                *(("event", item.id.value, bool(item.definition)) for item in self.events),
            )
            if not defined
        ]
        if undefined:
            raise ValueError(f"offered with no definition: {', '.join(undefined)}")
        return self

    def definition_block(self) -> str:
        """The definition sentences a labelling prompt is built from.

        One place, so a prompt cannot carry a word this file does not, and so
        editing `config/taxonomy.json` is the whole of changing what the model
        is asked. The vocabulary's own order is kept: a model asked to pick from
        a list is not indifferent to the list's order, so the order is a
        committed fact rather than whatever a dict iterated to that day.

        Active entries only. A draft contributes nothing at all - not a heading,
        not a blank line - which is what makes `status` a control rather than a
        convention, and it is asserted by comparing this block's bytes with and
        without the draft. Events have no status to read yet.
        """
        sections = (
            ("Desks", [item for item in self.verticals if item.status is LifecycleStatus.ACTIVE]),
            ("Lenses", [item for item in self.lenses if item.status is LifecycleStatus.ACTIVE]),
            ("Events", list(self.events)),
        )
        written = [
            "\n".join(
                [
                    f"{heading}:",
                    *(f"- {item.id} ({item.display_name}): {item.definition}" for item in entries),
                ]
            )
            for heading, entries in sections
            if entries
        ]
        return "\n\n".join(written)

    def vertical(self, vertical_id: str) -> VerticalDef | None:
        return next((item for item in self.verticals if item.id == vertical_id), None)

    def lens_terms(self) -> dict[LensId, list[str]]:
        """The lens match surface. A retired lens keeps its tombstone and stops matching."""
        return {
            lens.id: lens.keywords
            for lens in self.lenses
            if lens.status is not LifecycleStatus.RETIRED
        }

    def lens_weights(self) -> dict[LensId, float]:
        """Only the lenses that score, so a caller cannot spend time on the others.

        Every id here is also in `lens_terms`, so a scoring hit is always a label
        too - the headline is inside the text the label reads.
        """
        return {
            lens.id: lens.weight
            for lens in self.lenses
            if lens.status is not LifecycleStatus.RETIRED and lens.weight > 0.0
        }

    def event_terms(self) -> dict[EventType, list[str]]:
        return {event.id: event.keywords for event in self.events}
