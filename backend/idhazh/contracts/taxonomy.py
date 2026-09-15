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
            change=(
                "Added VerticalDef.floor, the fewest stories a desk publishes in a day, and "
                "VerticalDef.ceiling, the most of a day it may hold as a share."
            ),
            why=(
                "Five desks cannot go empty today and nothing in the code guarantees it - a "
                "feed sits on exactly one desk and min_feeds counts FEEDS rather than "
                "stories, so the five are held up by the shape of config/sources.json and not "
                "by a rule. The measured risk when the desk becomes what the article says it "
                "is, is the opposite of an empty desk: three AI-adjacent stories arriving on "
                "an Energy feed, a Business feed and a World feed are three desks today and "
                "one desk afterwards, so a five-desk digest becomes a one-desk digest with "
                "four thin rails on exactly the day a reader most needs the other four. The "
                "ceiling stops that and the floor fills the gap it leaves. Both re-file a "
                "story onto its second-best desk and neither admits or drops one, so the day "
                "is exactly as long either way. Both sit beside min_feeds because that is "
                "where a desk's other bound already is, and both are per-desk because ai has "
                "35 feeds where the other four have 21. Additive with defaults that are the "
                "identity - floor 0 and ceiling 1.0 are no rule - so a taxonomy written "
                "before this still validates and moves nothing; no read-side migration is "
                "needed. Optional rather than required on purpose: the schema gates shape and "
                "never contents, and a taxonomy fixture another plan writes must still "
                "validate without them."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13",
            change=(
                "EventDef extends Lifecycled, so an event carries status and retired_on the "
                "way a vertical and a lens already do. definition_block offers only active "
                "events, event_terms drops a retired one, and the definition rule asks only "
                "the events the vocabulary still offers."
            ),
            why=(
                "Retire, never delete is the rule the other two vocabularies follow, and the "
                "event vocabulary could not follow it: EventDef extended plain Model, so there "
                "was nothing to retire an event WITH. Deleting the entry was the only way to "
                "stop offering a word, and that leaves every committed day carrying it holding "
                "an id nothing can name - which is the cost the lens tombstone already exists "
                "to avoid. Additive with defaults, so a taxonomy written before this still "
                "validates unchanged and every event in it reads as active; no read-side "
                "migration is needed. Its own entry rather than a clause of the "
                "2026-09-12T03:55 retype, because that one is breaking on the write side and "
                "an expand bundled into a break cannot be reverted on its own (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T03:55",
            change=(
                "LensDef.id and EventDef.id are Slug rather than the closed LensId and "
                "EventType enums, which are deleted. Taxonomy no longer requires the "
                "file to label every enum member exactly once; ids must only be "
                "distinct within their vocabulary."
            ),
            why=(
                "Adding or retiring a lens was a Python edit, a schema regeneration and "
                "a release, which is the opposite of the rule that a label vocabulary is "
                "config - and it is why the vocabulary had not moved. The schema now "
                "gates shape (the slug pattern) and never membership, so a word is one "
                "config edit. Breaking on the write side, read-compatible on the read "
                "side and deliberately so (section 11): every id any committed payload "
                "carries is a well-formed slug, so a widened type accepts every one of "
                "them, where a narrowed one would reject a day whose word this file has "
                "since stopped carrying. Nothing may invent a label, because "
                "tag.tags can only return a key of the mapping this file builds. What "
                "the enum was also doing was making it impossible to DELETE an id: "
                "measured 2026-09-12, ai-roi is retired here and carried by 18 committed "
                "items over 2026-08-27, 08-28 and 08-29, so deleting it rather than "
                "tombstoning it would leave those 18 holding a word nothing can name. "
                "That is what the reading side migrates for - it renders an id it cannot "
                "name rather than dropping it."
            ),
        ),
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
