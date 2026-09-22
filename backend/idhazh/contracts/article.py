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


class TitleSource(StrEnum):
    """Which stranger's string the published headline came from.

    Both are untrusted, and they are not trusted equally. The feed is a source
    somebody chose and the page is whoever answered the address, so the feed is
    read first and the page only when the feed said nothing - order is a
    control, and a page can never displace a headline we were given. The page
    path is then held to a tighter bound than the feed path and refused over it
    rather than cut. So this field records the outcome of a trust decision
    rather than provenance alone: `page` says the more attacker-controlled of
    the two strings is the one on the page.
    """

    FEED = "feed"
    PAGE = "page"


class Article(Contract):
    """The Extract stage's output payload, one per item."""

    __schema_stem__: ClassVar[str] = "article"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-22",
            change="Added corroborated_word_count; FailureCode gained contaminated.",
            why="The page states its own article's length, so an extraction can be checked.",
        ),
        ChangelogEntry(
            version="2026-09-15T22:10",
            change="FailureCode gained model_timed_out and shard_out_of_time.",
            why="Both were being reported under a name that sends an operator to the wrong place.",
        ),
        ChangelogEntry(
            version="2026-09-15T20:00",
            change="The embedded failure vocabulary gained model_refused.",
            why="It follows item-health-row, where the vocabulary is declared.",
        ),
        ChangelogEntry(
            version="2026-09-15T12:00",
            change="title_source records a trust decision, not provenance alone.",
            why="A page headline and a feed headline are not equally trustworthy.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
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
    secondary_desk: Slug | None = Field(
        default=None,
        description=(
            "The one other desk this article has a claim to, read off the same article "
            "`desk` is. It is where the day sends the story when the desk it is on is "
            "over its ceiling. One, never a list: a story on four desks is a story on "
            "no desk. Null is nothing having said, and the day falls back to "
            "`vertical`; a null is never read as a second desk and never as 'none'."
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
    title_source: TitleSource | None = Field(
        default=None,
        description=(
            "Where `title` came from: the feed entry, or the fetched page's own "
            "metadata when the feed carried none. Both are untrusted and they are not "
            "trusted equally - the feed is read first because it is the less "
            "attacker-controlled string, and the page path is held to a tighter bound "
            "and refused over it rather than cut. So this is the outcome of a trust "
            "decision, not provenance alone. Null on a failed payload, which publishes "
            "no headline, and on an ok payload written before the field existed."
        ),
    )
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
    corroborated_word_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Words the page's own markup says its article has, read independently of "
            "the extractor: the container whose heading matches `og:title`, JSON-LD "
            "`articleBody`, or microdata `articleBody`, whichever states the most. A "
            "count, never the text. None means the page stated no length worth "
            "reading, or the payload was written before the field existed - the two "
            "are not distinguished, because neither yields a ratio. Divide "
            "`source_word_count` by it for the ratio `extract.corroboration_ratio_max` "
            "bounds; the ratio is not stored, because two numbers that must agree "
            "eventually disagree."
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
                FailureCode.CONTAMINATED,
            }:
                raise ValueError("an ok article carries only a recorded extract signal")
        else:
            if self.failure_detail is None:
                raise ValueError("a failed article must record why")
            if self.title_source is not None:
                raise ValueError("a failed article publishes no headline, so it names no source")
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
