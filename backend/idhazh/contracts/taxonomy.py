"""The label vocabularies and the vertical registry (`config/taxonomy.json`).

Every id here is an open slug, so adding or retiring a word is a config edit.
The closed vocabulary is this file, not the Python type: nothing may invent a
label, because `tag.tags` can only ever return a key of the mapping this file
builds, and no fetched text reaches that mapping (Guardrail #11). What the open type
buys is that a day written before the vocabulary moved still reads - a closed
type would reject a payload whose word this file has since stopped carrying.

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

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    Slug,
    records_json,
)


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

The bound is a token budget rather than a style rule. Every definition sentence
together measured 658 tokens over 23 sentences, which is 28.6 each, and they
ride in every labelling prompt this pipeline sends. At 4.7 characters a token
that is about 134 characters a sentence, and 240 is roughly twice it: room to
sharpen a sentence, not room for a paragraph.

**The bound did not move when the reading was retaken on 2026-09-14**, and that
is a decision rather than an oversight. The same derivation on the new figure
gives about 268 characters, so 240 is inside it, and the longest committed
definition is 233. Widening to 268 would buy 35 characters nobody is asking for;
narrowing would refuse a definition the taxonomy already carries.

**The reading is `idhazh.measured.DEFINITION_SENTENCE_TOKENS`.** It is cited
rather than imported: this package is the bottom of the dependency graph and
imports no other subpackage (`CLAUDE.md` section 4), so the bound stays a literal
here and the record carries the provenance.
`backend/utilities/measure_budgets.py check` is what says the reading is stale;
`read` is what retakes it.

Empty is legal and means the entry is offered to no prompt. A proposed entry
arrives with no definition, because the words that would go in it came off the
open web and a person writes the real one when they promote it (Guardrail #11).
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
    floor: int = Field(
        default=0,
        ge=0,
        description=(
            "The fewest stories this desk publishes in a day, where the day still holds a "
            "story whose second-best desk is this one. A count rather than a share, because "
            "it answers whether the desk is worth opening at all and a desk page is a "
            "fragment below six stories on a 100-story day and on a 450-story one alike. It "
            "never admits a story a gate refused and never reaches a previous day: a desk it "
            "cannot fill publishes thin, and DigestVerticalRef already carries why. Zero, "
            "the default, is no rule."
        ),
    )
    ceiling: float = Field(
        default=1.0,
        gt=0.0,
        le=1.0,
        description=(
            "The most of a published day this desk may hold, as a share. A share rather "
            "than a count, because a count is a moving share - ten stories is 1.4 percent of "
            "a 731-story day and a quarter of a 40-story one. The stories over it are "
            "re-filed onto their second-best desk and never dropped, so the day is exactly "
            "as long either way and a desk with nowhere to send its overflow stays over its "
            "ceiling rather than shortening the day. A desk may always hold its floor "
            "whatever this says. 1.0, the default, is no rule."
        ),
    )
    is_auto_discovered: bool = Field(default=False, description=AUTO_DISCOVERED_DESCRIPTION)


class LensDef(VocabularyEntry, Lifecycled):
    id: Slug
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


class EventDef(VocabularyEntry, Lifecycled):
    id: Slug
    keywords: list[MatchTerm] = Field(
        default_factory=list,
        description="The curated terms that assign this event. Same rule as LensDef.keywords.",
    )


class Taxonomy(Contract):
    """`config/taxonomy.json` - the vocabulary every payload indexes against."""

    __schema_stem__: ClassVar[str] = "taxonomy"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13T13:49",
            change="Added VerticalDef.floor, the fewest stories a desk publishes in a day.",
            why="Nothing in the code stopped a desk going empty on a quiet day.",
        ),
        ChangelogEntry(
            version="2026-09-13",
            change="EventDef extends Lifecycled, so an event carries status and retired_on.",
            why="Retire, never delete is the rule the other two vocabularies follow.",
        ),
        ChangelogEntry(
            version="2026-09-12T03:55",
            change="LensDef.id and EventDef.id are Slug rather than the closed LensId.",
            why="Adding or retiring a lens was a source edit where it should be a config edit.",
        ),
        ChangelogEntry(
            version="2026-09-12",
            change="Added VocabularyEntry.definition to every vertical, lens and event.",
            why="An id and a display name tell a model nothing.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    verticals: list[VerticalDef]
    lenses: list[LensDef]
    events: list[EventDef]

    @model_validator(mode="after")
    def _vocabulary_ids_are_distinct(self) -> Self:
        """Distinct within each vocabulary, and that is the whole rule.

        It used to also demand that `lenses` label every `LensId` and `events`
        every `EventType` exactly once. There is no enum left to be complete
        against: this file IS the vocabulary, so a word it does not carry does
        not exist, and a word it stops carrying is one a person deleted on
        purpose. What that costs is written down rather than guarded here - a
        deleted id leaves every committed day that carries it holding a word
        nothing can name, which is why `retired` exists and why the reading side
        renders an id it cannot name instead of dropping it.
        """
        for kind, ids in (
            ("vertical", [item.id for item in self.verticals]),
            ("lens", [item.id for item in self.lenses]),
            ("event", [item.id for item in self.events]),
        ):
            if len(set(ids)) != len(ids):
                raise ValueError(f"{kind} ids must be distinct")
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
                    ("lens", item.id, bool(item.definition))
                    for item in self.lenses
                    if item.status is LifecycleStatus.ACTIVE
                ),
                *(
                    ("event", item.id, bool(item.definition))
                    for item in self.events
                    if item.status is LifecycleStatus.ACTIVE
                ),
            )
            if not defined
        ]
        if undefined:
            raise ValueError(f"offered with no definition: {', '.join(undefined)}")
        return self

    def to_json(self) -> str:
        """One word a line - see `records_json`.

        A person curates this file, and an entry's fields only mean anything
        together: the id says nothing without the sentence the model reads it
        by, and the keywords say nothing without the lens they match for.
        """
        return records_json(self.model_dump(mode="json"))

    def definition_block(self) -> str:
        """The definition sentences a labelling prompt is built from.

        One place, so a prompt cannot carry a word this file does not, and so
        editing `config/taxonomy.json` is the whole of changing what the model
        is asked. The vocabulary's own order is kept: a model asked to pick from
        a list is not indifferent to the list's order, so the order is a
        committed fact rather than whatever a dict iterated to that day.

        Active entries only, in all three vocabularies. A draft contributes
        nothing at all - not a heading, not a blank line - which is what makes
        `status` a control rather than a convention, and it is asserted by
        comparing this block's bytes with and without the draft.
        """
        sections = (
            ("Desks", [item for item in self.verticals if item.status is LifecycleStatus.ACTIVE]),
            ("Lenses", [item for item in self.lenses if item.status is LifecycleStatus.ACTIVE]),
            ("Events", [item for item in self.events if item.status is LifecycleStatus.ACTIVE]),
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

    def lens_terms(self) -> dict[str, list[str]]:
        """The lens match surface. A retired lens keeps its tombstone and stops matching.

        This mapping is the closed vocabulary the tagger works from, which is
        what keeps an open id type safe: `tag.tags` can only return a key of
        what it is handed, so a hostile page can win itself a word we already
        publish and can never invent one (Guardrail #11).
        """
        return {
            lens.id: lens.keywords
            for lens in self.lenses
            if lens.status is not LifecycleStatus.RETIRED
        }

    def lens_weights(self) -> dict[str, float]:
        """Only the lenses that score, so a caller cannot spend time on the others.

        Every id here is also in `lens_terms`, so a scoring hit is always a label
        too - the headline is inside the text the label reads.
        """
        return {
            lens.id: lens.weight
            for lens in self.lenses
            if lens.status is not LifecycleStatus.RETIRED and lens.weight > 0.0
        }

    def event_terms(self) -> dict[str, list[str]]:
        """The event match surface, on the same rule as `lens_terms`.

        A retired event keeps its tombstone and stops matching, so a word the
        vocabulary has stopped carrying cannot be assigned to a new item while
        the days that already carry it still read.
        """
        return {
            event.id: event.keywords
            for event in self.events
            if event.status is not LifecycleStatus.RETIRED
        }
