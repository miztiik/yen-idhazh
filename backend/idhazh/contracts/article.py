"""One item's fetched, extracted and sanitized text - or the recorded failure.

The Extract stage is the trust boundary, crossed exactly once. Everything on
this payload that originated on someone else's server - `title`, `text`,
`source_url` - is data and never instruction (Guardrail #11). Nothing here may
become a system prompt, a shell argument, a file path or an outbound URL.

A failure is a state of this payload, not an absence of it: a dead link, a
paywall or a broken extractor degrades its own item and records why, and its
siblings never notice.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    ItemId,
    Slug,
    Timestamp,
    Url,
    UrlKey,
    derive_url_key,
)
from idhazh.contracts.item_health import FAILURE_CODE_STAGES, FailureCode, ItemStage
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import SourceTier

# Structural bounds on untrusted text that reaches a page or a log line. Not a
# tunable: the extraction caps a reasonable operator would move live in config.
#: The width as a number, for the same reason `VALUE_MAX_LENGTH` is one: a
#: producer that cuts a run of sentences out of an article has to refuse a slice
#: this will not hold, and the only other way to find out is to let the shape
#: raise part-way through an article.
UNTRUSTED_LINE_MAX: Final = 500
UntrustedLine = Annotated[str, StringConstraints(min_length=1, max_length=UNTRUSTED_LINE_MAX)]


class ArticleStatus(StrEnum):
    OK = "ok"
    FETCH_FAILED = "fetch_failed"
    EXTRACT_FAILED = "extract_failed"
    ROBOTS_DENIED = "robots_denied"


class Article(Contract):
    """The Extract stage's output payload, one per item."""

    __schema_stem__: ClassVar[str] = "article"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-12T18:40",
            change=(
                "item_id accepts a second shape: sixteen Crockford base32 symbols "
                "beside the decimal digits it already took."
            ),
            why=(
                "Ten decimal digits is 33 bits of the address, which collides often "
                "enough that the collision had to be resolved - and the only way to "
                "resolve one is to step the loser past whatever else the run planned, "
                "so a collided id depended on the day's pool rather than on the "
                "address alone. Two runs of one day draw different pools, so the same "
                "article came back under a second id and published twice. Eighty bits "
                "do not collide. This widens and never contracts: every day published "
                "before today carries the decimal shape and a published day is frozen, "
                "so nothing was rewritten and no read-side migration is owed."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T06:56",
            change=(
                "Added desk: where the digest publishes the story, beside vertical, "
                "which keeps carrying the word the feed declares about itself."
            ),
            why=(
                "One word was doing two jobs. A feed declares a vertical and the digest "
                "needs to know what the article is about, and those are different "
                "questions the moment an energy feed carries an AI story. Repointing "
                "vertical was refused instead of taken: _identity_is_rebuilt_not_trusted "
                "asserts item_id.startswith(f'{self.vertical}-'), so repointing it "
                "rejects, at read time, every item whose desk moved. Additive and "
                "optional: null is nothing having said, the digest falls back to "
                "vertical, and every payload written before today still reads (section "
                "11). Nothing fills it yet - the model that will is a later row."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T03:55",
            change=(
                "lenses and events are lists of Slug rather than of the closed LensId "
                "and EventType enums, which are deleted. The schema gates the slug "
                "pattern and no longer enumerates the members."
            ),
            why=(
                "A lens id was a Python enum member, so adding or retiring a word was a "
                "code change, a schema regeneration and a release. The vocabulary is "
                "config/taxonomy.json and nothing else, and the tagger can only ever "
                "emit a key of the mapping that file builds - so the type can widen "
                "without letting anything invent a label (Guardrail #11). Read-compatible: "
                "every id any payload on disk carries is a well-formed slug, so this "
                "build reads every one of them, and a re-run of a stage against a "
                "payload an older build wrote produces the same tags. The break is on "
                "the write side, where the schema stops refusing a word the vocabulary "
                "has gained (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27",
            change="failure_code may now carry copied_source or leaked_address.",
            why=(
                "Summarize gained two rejects and the failure vocabulary is inlined into "
                "this schema, so this generated file's bytes move even though no field "
                "on this payload changed and extract can never write either value. "
                "Stamped here rather than left to the drift gate to announce (section "
                "11). Additive - a payload written before today names none of the new "
                "values and still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change="Added source_word_count: the body length before the truncation cap.",
            why=(
                "The length band is named min_source_words and was being chosen from the "
                "post-cap count, which cannot exceed int(truncation_cap_tokens / 1.3). At "
                "the committed cap of 2500 that ceiling is 1923 words, so the 2000-word "
                "band was unreachable by arithmetic. The field is None on payloads written "
                "before it existed, where band_source_words falls back to the post-cap "
                "count the build that wrote them used."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:49",
            change="Added source_form to the extract payload.",
            why=(
                "Summarize and publish need the curator-declared source form after the "
                "plan file is no longer in hand. The field defaults to article so older "
                "payloads still read."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:15",
            change="Added brief and failure_code to the extract payload.",
            why=(
                "Extract now publishes short or list-shaped pages by default while recording "
                "the shape signal, and it rejects paywalled or unsupported forms with typed "
                "codes that the item-health classifier can carry."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: identity, provenance, text, truncation and failure states.",
            why="Contracts before logic - Extract is written against a fixed payload.",
        ),
    )

    item_id: ItemId
    url_key: UrlKey = Field(
        description="sha256 of canonical_url. Identity for dedupe and skip - a field, never a path."
    )
    source_url: Url = Field(description="The address as discovered.")
    canonical_url: Url = Field(
        description="The address after canonicalisation. url_key derives from it."
    )
    source_id: Slug = Field(description="The feed that carried it.")
    tier: SourceTier
    source_form: SourceForm = Field(
        default=SourceForm.ARTICLE,
        description="Declared by the feed config. Never inferred from extracted text.",
    )

    vertical: Slug = Field(
        description=(
            "The vertical the carrying feed declares about itself, copied from the "
            "source config and never read out of the article. `item_id` is addressed "
            "from it, so it may not be repointed - see "
            "`_identity_is_rebuilt_not_trusted` below."
        )
    )
    desk: Slug | None = Field(
        default=None,
        description=(
            "Where the digest publishes this story, read off the whole article rather "
            "than off the feed that carried it. Null is nothing having said, and the "
            "digest falls back to `vertical`; a null is never read as a desk."
        ),
    )
    lenses: list[Slug] = Field(default_factory=list)
    events: list[Slug] = Field(default_factory=list)
    entities: list[Slug] = Field(default_factory=list)
    carried_by: int = Field(
        default=1, ge=1, description="Independent sources that carried this story today."
    )
    rank_score: float = Field(ge=0.0)

    title: UntrustedLine | None = None
    text: str | None = Field(default=None, description="Sanitized text. Never republished.")
    word_count: int = Field(default=0, ge=0, description="Words in `text`, after the cap.")
    source_word_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Words in the extracted body before `extract.truncation_cap_tokens` cut it. "
            "A count, never the text: the pre-cap body is not kept and is not ours to "
            "republish. None on a payload written before the field existed."
        ),
    )
    token_count: int = Field(default=0, ge=0)
    brief: bool = Field(
        default=False,
        description="True when the source is short enough that summarize uses the brief tier.",
    )
    truncated: bool = False
    truncated_at_tokens: int | None = Field(default=None, ge=1)

    published_at: Timestamp | None = None
    fetched_at: Timestamp
    status: ArticleStatus
    failure_code: FailureCode | None = Field(
        default=None,
        description="Typed extract failure, or a recorded extract signal on an ok article.",
    )
    failure_detail: UntrustedLine | None = None

    extractor_version: str = Field(min_length=1)
    sanitizer_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _identity_is_rebuilt_not_trusted(self) -> Self:
        """Both halves of the identity are recomputed rather than believed.

        The second clause is also what keeps `vertical` unrepointable. `item_id`
        is addressed from the carrying feed's word and a published address never
        moves, so pointing `vertical` at a reading of the article would reject,
        at read time, every item whose desk moved. That is why `desk` is a field
        beside it rather than a second meaning for it.
        """
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("url_key must be the sha256 of canonical_url, recomputed on read")
        if not self.item_id.startswith(f"{self.vertical}-"):
            raise ValueError("item_id must be addressed <vertical>-<NN>")
        return self

    @model_validator(mode="after")
    def _state_is_complete(self) -> Self:
        if self.status is ArticleStatus.OK:
            if not self.text or self.title is None:
                raise ValueError("an ok article carries title and text")
            if self.failure_detail is not None:
                raise ValueError("an ok article carries no failure_detail")
            if self.failure_code not in {
                None,
                FailureCode.TOO_SHORT,
                FailureCode.NOT_PROSE,
                FailureCode.BOILERPLATE,
            }:
                raise ValueError("an ok article carries only a recorded extract signal")
        elif self.failure_detail is None:
            raise ValueError("a failed article must record why")
        if (
            self.failure_code is not None
            and ItemStage.EXTRACT not in FAILURE_CODE_STAGES[self.failure_code]
            and ItemStage.FETCH not in FAILURE_CODE_STAGES[self.failure_code]
        ):
            raise ValueError("article failure_code must belong to fetch or extract")
        if self.truncated != (self.truncated_at_tokens is not None):
            raise ValueError("truncated and truncated_at_tokens must agree")
        if self.source_word_count is not None and self.source_word_count < self.word_count:
            raise ValueError("source_word_count counts the body before the cap, so it is not less")
        if len(set(self.lenses)) != len(self.lenses):
            raise ValueError("lenses must be distinct")
        if len(set(self.events)) != len(self.events):
            raise ValueError("events must be distinct")
        return self

    @property
    def band_source_words(self) -> int:
        """The length a `summarize.bands` tier is chosen from.

        The read-side migration for `source_word_count`. A payload written
        before the field existed carries only the post-cap count, which is the
        number the build that wrote it used, so that is what it keeps reading.
        """
        return self.word_count if self.source_word_count is None else self.source_word_count
