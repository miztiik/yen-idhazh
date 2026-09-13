"""One article of the frozen classification reference set, as one line of `dataset.jsonl`.

`corpus/reference-dataset-1/` is the set every classification accuracy number in
plan 23 is measured on. A row here says which article it is, where its text
lives, and what a person labelled it. It never says which split it is in: the two
committed lists under `splits/` are the split, and a second copy of that fact on
the row is a second thing that can disagree with the first.

**The set is frozen and the splits are committed as lists.** A split recomputed
from a seed moves when the row order moves, and then last month's number and this
month's number were taken on different sets (plan 23 row #P2 decision 3).

**Article text lives in its own file**, `articles/<url_key>.txt`, one an article.
Editing a label re-emits one short line rather than the whole article, which
matters because `.github/workflows/prune.yml` rewrites this range of history on a
schedule (`CLAUDE.md` section 8, plan 23 row #P2 decision 4). `article_sha256`
and `article_words` are what tie the line back to the file: a text somebody edited
in place stops matching, and `build_reference_dataset.py verify` is what says so.

**This repository is public, so every article text under `corpus/` is readable by
anyone.** That cost was taken on 2026-08-28 and is restated here rather than
assumed (`CLAUDE.md` section 0a, plan 23 row #P2 decision 8). Nothing renders
this text, links to it or serves it.

**A model writes no field on this row.** The labels are a person's, taken against
the committed definition text, and `labelled_by` records whose. That keeps the set
clear of `CLAUDE.md` section 0a without needing the property it states: there is
no model verdict here at all.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.app_config import ExtractConfig
from idhazh.contracts.article import ArticleStatus
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    RelPath,
    Sha256,
    Slug,
    Timestamp,
    Url,
    UrlKey,
    derive_url_key,
)


class ReferenceSplit(StrEnum):
    """The two sides, and there is no third.

    **There is no `train`.** A train split in the same directory invites
    fine-tuning on the measurement set, and that contamination is silent - the
    numbers get better and nothing says why (plan 23 row #P2 decision 1, owner,
    2026-09-10).
    """

    DEV = "dev"
    TEST = "test"


class ReferenceLabels(Model):
    """One person's reading of one article. Every field is empty when the set is built.

    The vocabularies are `config/taxonomy.json`, so nothing here enumerates a
    member: a label is a slug the taxonomy names, and adding a word to the
    taxonomy may not be a schema change (plan 23 section 0.1).

    `reference_summary` is the one field with no writer. **The human faithfulness
    ledger was dropped and its contract kept** (plan 23 row #P2 decision 6, owner,
    2026-09-10), so the ledger can return without a schema argument. A
    model-written summary is a legitimate reference for classification labels a
    person confirmed, and is **never** a faithfulness reference.
    """

    desk: Slug | None = Field(
        default=None, description="Which desk the article belongs to, read from the text."
    )
    lenses: list[Slug] = Field(
        default_factory=list, description="Every lens the article carries. May be empty."
    )
    article_kind: Slug | None = Field(
        default=None, description="What kind of writing it is - a report, an analysis, a notice."
    )
    stances: dict[Slug, Slug] = Field(
        default_factory=dict,
        description="One stance per political question the article takes a position on.",
    )
    sentiment: Slug | None = Field(
        default=None, description="Sentiment about one named subject, not about the article."
    )
    reference_summary: str | None = Field(
        default=None,
        description=(
            "Kept shape with no writer. Never a faithfulness reference - "
            "plan 23 row #P2 decision 6."
        ),
    )
    labelled_by: str | None = Field(
        default=None, max_length=64, description="Who read it. A person, never a model."
    )
    labelled_on: DateStamp | None = Field(default=None, description="The day they read it.")
    definition_version: DateStamp | None = Field(
        default=None,
        description=(
            "Which `config/taxonomy.json` definition text the label was taken against. "
            "A label taken against last month's definition measures a different question."
        ),
    )

    @property
    def is_empty(self) -> bool:
        """True while nobody has read this article yet."""
        return (
            self.desk is None
            and not self.lenses
            and self.article_kind is None
            and not self.stances
            and self.sentiment is None
            and self.labelled_by is None
        )


class ReferenceDatasetRow(Contract):
    """One article of `corpus/reference-dataset-1/dataset.jsonl`."""

    __schema_stem__: ClassVar[str] = "reference-dataset-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13",
            change=(
                "Initial shape: the article's identity and provenance, the text file's "
                "digest and word count, and two empty label slots - one per rater."
            ),
            why=(
                "Plan 23 measures a classifier against a frozen labelled set, and the set "
                "needs a declared shape before anything writes one (Guardrail #3). The "
                "split is deliberately absent: `splits/dev.txt` and `splits/test.txt` are "
                "the split, and a copy of it here is a second thing that can disagree. "
                "`second_labels` is here from the first commit because row #P3 double-"
                "labels 60 dev items for a Cohen's kappa, and a field added later would "
                "make that a schema argument in the middle of a labelling pass."
            ),
        ),
    )

    url_key: UrlKey = Field(
        description=(
            "sha256 of the canonical URL, recomputed on read. It is the join to "
            "`splits/*.txt`, to `articles/<url_key>.txt`, and to every collection this "
            "set must not overlap."
        )
    )
    canonical_url: Url = Field(
        description="What `url_key` is derived from, never trusted from a payload."
    )
    source_url: Url = Field(
        description="The address the feed carried, kept so a person can open it."
    )
    source_domain: str = Field(
        min_length=3,
        max_length=253,
        description=(
            "The registrable domain, which is the unit the split is drawn on. Two "
            "articles from one outlet share boilerplate, a house style and often a wire "
            "original, so a split that separates rows rather than outlets flatters every "
            "number taken on it."
        ),
    )
    source_id: Slug = Field(description="Which feed in `config/sources.json` carried it.")
    vertical: Slug = Field(
        description="The vertical the pipeline published it under, kept as context."
    )
    published_date: DateStamp = Field(description="The day the article was published.")
    title: str = Field(min_length=1, max_length=512, description="The headline, as published.")
    article_words: int = Field(
        ge=1, description="Words in the article file. Recomputed by `verify`, never trusted."
    )
    article_sha256: Sha256 = Field(
        description=(
            "sha256 of `articles/<url_key>.txt`. What detects a text edited in place, "
            "which would silently move what a label was taken against."
        )
    )
    extractor_version: str = Field(
        min_length=1, max_length=64, description="Which extractor produced the text."
    )
    sanitizer_version: str = Field(
        min_length=1,
        max_length=64,
        description="Which sanitizer the text crossed the trust boundary through.",
    )
    fetched_on: DateStamp = Field(
        description="The day the text was taken. The set is frozen from here."
    )
    labels: ReferenceLabels = Field(
        default_factory=ReferenceLabels, description="The first rater's reading."
    )
    second_labels: ReferenceLabels | None = Field(
        default=None,
        description=(
            "An independent second reading, on the 60 dev items row #P3 double-labels. "
            "Null everywhere else, and null is not a disagreement."
        ),
    )

    @model_validator(mode="after")
    def _identity_is_owned_rather_than_asserted(self) -> Self:
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("a reference row arrived with an identity it does not own")
        return self


# The shapes below belong to `corpus/reference-dataset-2/`, which is a different
# collection from the frozen set above. It is built from a URL list somebody
# supplied rather than from the digest archive, it carries no label, and its
# settings live in its own `config.json` rather than in `config/idhazh.json`.
# The two share this module because they share a vocabulary, not because a row
# of one is ever a row of the other.


class ReferenceGroupBy(StrEnum):
    """Which field a balanced sample counts as one outlet.

    `PUBLISHER` is the default because the registered domain merges every
    newsletter on a shared platform into one allocation: 50 articles from
    `bengoertzel.substack.com` and 50 from `chipbriefing.substack.com` are two
    outlets to a reader and one `substack.com` to the public suffix list.
    """

    PUBLISHER = "publisher"
    SOURCE_DOMAIN = "source_domain"
    HOST = "host"


class ReferencePublisherPart(StrEnum):
    """What a publisher key is lengthened with when two hosts produce the same one.

    Tried in the configured order and no further than uniqueness needs, so a key
    nobody collides with keeps its short form.
    """

    REGISTERED_NAME = "registered_name"
    PUBLIC_SUFFIX = "public_suffix"
    HOST = "host"


class ReferenceFailureCode(StrEnum):
    """Why one URL produced no article text.

    `ArticleStatus` says which stage ended it; this says what happened there. A
    truncated body is its own member rather than a success with less text,
    because a download stopped by its byte limit looks exactly like a short
    article once the reason is thrown away.
    """

    ROBOTS_DENIED = "robots_denied"
    ROBOTS_UNREACHABLE = "robots_unreachable"
    BLOCKED_ADDRESS = "blocked_address"
    FETCH_PERMANENT = "fetch_permanent"
    FETCH_TRANSIENT = "fetch_transient"
    BODY_TRUNCATED = "body_truncated"
    PAYWALLED = "paywalled"
    EMPTY_TEXT = "empty_text"


class ReferencePhase(StrEnum):
    """Which of the three writers produced a metadata file."""

    IMPORT = "import"
    EXTRACTION = "extraction"
    SELECTION = "selection"


class ReferenceSelectionSettings(Model):
    """How many articles a sample takes, and what it counts as one outlet.

    Every number here is a knob rather than a literal in the selection loop
    (Guardrail #6): changing the file changes the sample with no source edit.
    """

    rows_per_domain_target: int = Field(
        default=20,
        ge=1,
        description=(
            "Articles wanted per group. An initial allocation, not a ceiling - a deep "
            "group may pass it while filling places a short group cannot use."
        ),
    )
    rows_max: int = Field(
        default=1000,
        ge=1,
        description="A hard total cap, and never a promise to produce this many rows.",
    )
    fill_shortfall: bool = Field(
        default=True,
        description="Whether places a short group cannot use move to groups with articles left.",
    )
    group_by: ReferenceGroupBy = Field(
        default=ReferenceGroupBy.PUBLISHER, description="Which field counts as one outlet."
    )
    publisher_disambiguation: list[ReferencePublisherPart] = Field(
        default_factory=lambda: [
            ReferencePublisherPart.REGISTERED_NAME,
            ReferencePublisherPart.PUBLIC_SUFFIX,
            ReferencePublisherPart.HOST,
        ],
        min_length=1,
        description="The parts a colliding publisher key is lengthened with, in order.",
    )
    generic_host_labels: list[Slug] = Field(
        default_factory=lambda: [
            "blog",
            "feed",
            "feeds",
            "mail",
            "news",
            "newsletter",
            "rss",
            "stories",
            "web",
            "www2",
        ],
        description=(
            "Leftmost labels that name a subdomain rather than an outlet. "
            "`newsletter.semianalysis.com` is `semianalysis`, not `newsletter`."
        ),
    )


class ReferenceDatasetLocalConfig(Contract):
    """Every setting `corpus/reference-dataset-2/` is built with, and it reads no other.

    It is deliberately not a block of `config/idhazh.json`. This collection is
    built by hand once or twice a year and the pipeline runs every day, so a
    knob that only this tool reads does not belong in the file every stage
    loads (owner decision, 2026-09-13).

    Paths are relative to the repository root, POSIX-separated, with no `..`
    segment (`CLAUDE.md` section 2). A path relative to this file would have to
    climb out of the collection to name the taxonomy, and a stored `..` is the
    one form that stops meaning the same thing when a file moves.
    """

    __schema_stem__: ClassVar[str] = "reference-dataset-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13T10:20",
            change="Added selection.generic_host_labels.",
            why=(
                "The first import over the supplied list produced the outlet key "
                "`newsletter` for `newsletter.semianalysis.com`, which names a subdomain "
                "rather than a publisher. The list of labels that fall back to the "
                "registered name is a knob rather than a literal, because which words "
                "read as generic is a judgement that will change (Guardrail #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13",
            change=(
                "Initial shape: the input and vocabulary paths, the fetch settings, the "
                "request delay, and the selection block."
            ),
            why=(
                "The collection needs a declared, validated settings file before anything "
                "writes into it (Guardrail #3), and the owner ruled on 2026-09-13 that "
                "these settings stay local rather than joining AppConfig. The selection "
                "numbers are here rather than in the loop so a different sample size is a "
                "config edit (Guardrail #6)."
            ),
        ),
    )

    input_file: RelPath = Field(
        default="corpus/reference-dataset-2/urls.txt",
        description="The snapshotted URL list, one address a line.",
    )
    taxonomy_file: RelPath = Field(
        default="config/taxonomy.json",
        description="Read-only. The vertical vocabulary, never copied into this file.",
    )
    sources_file: RelPath = Field(
        default="config/sources.json",
        description="Read-only. What a host has to match before a row claims a source id.",
    )
    extract: ExtractConfig = Field(
        default_factory=ExtractConfig,
        description=(
            "The settings `fetch.fetch` already consumes. `truncation_cap_tokens` caps "
            "what a model reads and is never applied to saved text."
        ),
    )
    request_delay_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="Seconds between two requests to one host. The existing builder's name.",
    )
    selection: ReferenceSelectionSettings = Field(
        default_factory=ReferenceSelectionSettings,
        description="How a balanced sample is drawn from the finished extraction.",
    )


class ReferenceManifestRow(Contract):
    """One line of the supplied URL list, as one element of `manifest.json`.

    `source_line` is here because the list is the deliverable's input and a
    person reading a refusal needs the line to look at. Two lines carrying
    equivalent addresses keep both rows and share one `url_key`, so the count of
    rows and the count of identities are different numbers on purpose.
    """

    __schema_stem__: ClassVar[str] = "reference-dataset-manifest"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13",
            change=(
                "Initial shape: the input position, the three addresses, the registered "
                "domain, the host, the frozen publisher key, and the optional source id "
                "and vertical."
            ),
            why=(
                "The import needs a declared row before it writes one (Guardrail #3). "
                "`publisher` is stored rather than derived on read because its length "
                "depends on which other hosts are in the pool, so recomputing it over a "
                "later pool could rename an outlet that nothing changed."
            ),
        ),
    )

    source_line: int = Field(
        ge=1, description="The 1-based line of the input file this row came from."
    )
    source_url: Url = Field(description="The address as supplied, kept so a person can open it.")
    canonical_url: Url = Field(
        description="What `url_key` is derived from, never trusted from a payload."
    )
    url_key: UrlKey = Field(description="sha256 of the canonical URL, recomputed on read.")
    source_domain: str = Field(
        min_length=3,
        max_length=253,
        description="The registered domain, which is the unit the frozen set separates on.",
    )
    host: str = Field(min_length=3, max_length=253, description="The host, lower case.")
    publisher: Slug = Field(
        description=(
            "The outlet key a balanced sample groups on, frozen at import. Derived from "
            "the host rather than the registered domain, and lengthened only where two "
            "hosts would otherwise share it."
        )
    )
    source_id: Slug | None = Field(
        default=None,
        description=(
            "Which feed in `config/sources.json` this host is, when exactly one is. Null "
            "is 'we do not know', and a host shared by feeds in two verticals stays null."
        ),
    )
    vertical: Slug | None = Field(
        default=None,
        description=(
            "Source context from the feed's declaration, never a reading of the article. "
            "Null rather than a word invented for the taxonomy."
        ),
    )

    @model_validator(mode="after")
    def _identity_is_owned_rather_than_asserted(self) -> Self:
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("a manifest row arrived with an identity it does not own")
        return self


class ReferenceExtractionRow(Contract):
    """What one manifest identity produced, as one element of `articles.json`.

    A failure is a row, not an absence. It carries `text: null` with a typed
    reason, so the count of URLs that were tried and the count that worked are
    both readable from the file instead of one being inferred from the other.
    """

    __schema_stem__: ClassVar[str] = "reference-dataset-extractions"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13",
            change=(
                "Initial shape: the manifest identity, the full sanitized text with its "
                "digest and word count, the two timestamps, the two tool versions, and "
                "the outcome with its typed reason."
            ),
            why=(
                "The extraction needs a declared row before it writes one (Guardrail #3). "
                "The text is the untruncated sanitized prose rather than the capped "
                "`Article.text`, because a classifier reading a 2,500-token excerpt is "
                "reading a different article from the one a person opened."
            ),
        ),
    )

    source_line: int = Field(ge=1, description="The input line, carried from the manifest row.")
    source_url: Url = Field(description="The address as supplied.")
    canonical_url: Url = Field(description="What `url_key` is derived from.")
    url_key: UrlKey = Field(description="sha256 of the canonical URL, recomputed on read.")
    source_domain: str = Field(min_length=3, max_length=253, description="The registered domain.")
    host: str = Field(min_length=3, max_length=253, description="The host, lower case.")
    publisher: Slug = Field(description="The frozen outlet key, carried from the manifest row.")
    vertical: Slug | None = Field(default=None, description="Source context, or null.")
    status: ArticleStatus = Field(
        description="Which stage ended this attempt, in the vocabulary the pipeline uses."
    )
    failure_code: ReferenceFailureCode | None = Field(
        default=None, description="What happened there. Null on a success, and only then."
    )
    failure_detail: str | None = Field(
        default=None,
        max_length=512,
        description="One sentence a person can act on. Never a page's own words.",
    )
    text: str | None = Field(
        default=None,
        description=(
            "The full sanitized article prose, paragraph breaks kept. Null on a failure, "
            "and never an empty string standing in for one."
        ),
    )
    article_words: int | None = Field(
        default=None, ge=0, description="Words in `text`. Null where there is no text."
    )
    article_sha256: Sha256 | None = Field(
        default=None, description="sha256 of `text`. Null where there is no text."
    )
    fetched_at: Timestamp | None = Field(
        default=None, description="When the request was made. Null where none was."
    )
    extracted_at: Timestamp | None = Field(
        default=None, description="When the text was taken. Null where none was."
    )
    extractor_version: str | None = Field(
        default=None, min_length=1, max_length=64, description="Which extractor produced the text."
    )
    sanitizer_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Which sanitizer the text crossed the trust boundary through.",
    )

    @model_validator(mode="after")
    def _identity_is_owned_rather_than_asserted(self) -> Self:
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("an extraction row arrived with an identity it does not own")
        return self

    @model_validator(mode="after")
    def _an_outcome_carries_what_that_outcome_implies(self) -> Self:
        succeeded = self.status is ArticleStatus.OK
        if succeeded and self.failure_code is not None:
            raise ValueError("a successful extraction carries no failure code")
        if not succeeded and self.failure_code is None:
            raise ValueError("a failed extraction has to say why")
        text_fields = (
            self.text,
            self.article_words,
            self.article_sha256,
            self.extracted_at,
            self.extractor_version,
            self.sanitizer_version,
        )
        if succeeded and any(field is None for field in text_fields):
            raise ValueError("a successful extraction carries its text and its provenance")
        if not succeeded and any(field is not None for field in text_fields):
            raise ValueError("a failed extraction carries no text and no text provenance")
        if succeeded and not self.text:
            raise ValueError("an empty string is a failure, not a short article")
        return self


class ReferenceSelectionRow(Contract):
    """One chosen article, as one element of `urls.json`.

    It holds the identity and the text digest, never the text. The sample points
    at one named extraction through its metadata, so an article edited after the
    sample was drawn stops matching instead of quietly becoming what was chosen.
    """

    __schema_stem__: ClassVar[str] = "reference-dataset-selection"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13",
            change="Initial shape: the identity, the grouping fields and the text digest.",
            why=(
                "The sample needs a declared row before one is written (Guardrail #3). The "
                "text is not copied: two copies of an article in one collection are two "
                "things that can disagree, and the digest is what proves they have not."
            ),
        ),
    )

    url_key: UrlKey = Field(description="sha256 of the canonical URL, recomputed on read.")
    source_url: Url = Field(description="The address as supplied.")
    canonical_url: Url = Field(description="What `url_key` is derived from.")
    source_domain: str = Field(min_length=3, max_length=253, description="The registered domain.")
    host: str = Field(min_length=3, max_length=253, description="The host, lower case.")
    publisher: Slug = Field(description="The frozen outlet key this row was allocated under.")
    vertical: Slug | None = Field(default=None, description="Source context, or null.")
    article_sha256: Sha256 = Field(
        description="sha256 of the chosen article's text, as the named extraction holds it."
    )

    @model_validator(mode="after")
    def _identity_is_owned_rather_than_asserted(self) -> Self:
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("a selection row arrived with an identity it does not own")
        return self


class ReferenceImportTotals(Model):
    """What the input held, counted at import."""

    input_lines: int = Field(ge=0, description="Lines in the input file, blank ones included.")
    blank_lines: int = Field(ge=0, description="Lines that held no address.")
    valid_urls: int = Field(ge=0, description="Lines that held a usable http or https address.")
    unique_urls: int = Field(ge=0, description="Distinct `url_key` values among them.")
    equivalent_urls: int = Field(
        ge=0, description="Rows whose identity another row already carried."
    )
    invalid_lines: int = Field(
        ge=0, description="Lines that held something else. They block the manifest."
    )
    unassigned_vertical: int = Field(ge=0, description="Rows whose vertical stayed null.")


class ReferenceExtractionTotals(Model):
    """What the extraction attempted and what it got."""

    started_at: Timestamp = Field(description="When the run began.")
    finished_at: Timestamp = Field(description="When it stopped.")
    manifest_sha256: Sha256 = Field(description="Which manifest bytes this run read.")
    extractor_version: str = Field(min_length=1, max_length=64, description="The extractor.")
    sanitizer_version: str = Field(min_length=1, max_length=64, description="The sanitizer.")
    attempts: int = Field(ge=0, description="Requests made, retries included.")
    unique_attempted: int = Field(
        ge=0,
        description="Distinct identities tried. Separate from attempts so a retry "
        "cannot inflate the pool.",
    )
    succeeded: int = Field(ge=0, description="Distinct identities that produced text.")
    failed: int = Field(ge=0, description="Distinct identities that produced a typed reason.")
    pending: int = Field(ge=0, description="Distinct identities with no final result yet.")
    rows_succeeded: int = Field(ge=0, description="Input rows covered by a success.")
    rows_failed: int = Field(ge=0, description="Input rows covered by a failure.")
    failure_codes: dict[ReferenceFailureCode, int] = Field(
        default_factory=dict, description="How many identities ended on each reason."
    )
    succeeded_by_publisher: dict[Slug, int] = Field(
        default_factory=dict, description="Successes per outlet, which is the sampling pool."
    )


class ReferenceSelectionTotals(Model):
    """What a sample asked for and what it got, per group and overall."""

    extraction_sha256: Sha256 = Field(description="Which extraction bytes this sample read.")
    group_by: ReferenceGroupBy = Field(description="Which field counted as one outlet.")
    groups: int = Field(ge=0, description="Groups the pool held, empty ones included.")
    requested: int = Field(ge=0, description="min(rows_max, target * groups).")
    selected: int = Field(ge=0, description="Distinct articles chosen.")
    shortfall: int = Field(ge=0, description="Requested places nothing could fill.")
    available_by_group: dict[str, int] = Field(
        default_factory=dict, description="Usable articles each group held."
    )
    selected_by_group: dict[str, int] = Field(
        default_factory=dict, description="Articles each group contributed, zeros included."
    )
    extra_by_group: dict[str, int] = Field(
        default_factory=dict, description="Allocations above the target, so a fill is visible."
    )
    shortfall_by_group: dict[str, int] = Field(
        default_factory=dict, description="Target places a group could not fill."
    )


class ReferenceCollectionMetadata(Contract):
    """The `.meta.json` beside one collection file: what wrote it, from what, and how much.

    One model for the three phases, with one block each and a refusal when the
    block does not match the phase. Three near-identical models would drift, and
    a single flat model would let an import file carry a selection's counts.

    Every count here is read back off the written file rather than carried from
    the loop that produced it: two numbers computed from one variable agree by
    construction and prove nothing (Guardrail #10).
    """

    __schema_stem__: ClassVar[str] = "reference-dataset-metadata"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13",
            change=(
                "Initial shape: the phase, the input and output identity, the count maps, "
                "the frozen publisher map, the resolved settings, and one totals block per "
                "phase."
            ),
            why=(
                "A collection file is a bare JSON array, so the provenance it cannot carry "
                "lives beside it (Guardrail #3). The resolved settings are recorded per run "
                "because a later edit to `config.json` must not change what an earlier "
                "result claims to have been built with."
            ),
        ),
    )

    phase: ReferencePhase = Field(description="Which writer produced this file.")
    generated_at: Timestamp = Field(description="When the file beside this one was written.")
    collection_schema: Slug = Field(
        description="The `schemas/<stem>.schema.json` the file beside this one validates against."
    )
    input_path: RelPath = Field(description="What this phase read.")
    input_sha256: Sha256 = Field(description="The bytes it read.")
    output_path: RelPath = Field(description="What it wrote.")
    output_sha256: Sha256 = Field(description="The bytes it wrote, digested after writing.")
    rows: int = Field(ge=0, description="Elements in the file beside this one.")
    verticals: dict[Slug, int] = Field(
        default_factory=dict, description="Rows per vertical. The project's existing count map."
    )
    domains: dict[str, int] = Field(default_factory=dict, description="Rows per registered domain.")
    hosts: dict[str, int] = Field(default_factory=dict, description="Rows per host.")
    publishers: dict[Slug, int] = Field(default_factory=dict, description="Rows per outlet key.")
    publisher_hosts: dict[Slug, list[str]] = Field(
        default_factory=dict,
        description=(
            "The frozen key-to-hosts map. Every later phase reads this rather than "
            "deriving a key again over a pool that may have changed."
        ),
    )
    lengthened_publishers: dict[Slug, ReferencePublisherPart] = Field(
        default_factory=dict,
        description=(
            "Keys that collided and what settled them. Empty means every key stayed "
            "short, which is the common case and worth being able to see."
        ),
    )
    settings: ReferenceDatasetLocalConfig = Field(
        description="The fully resolved settings this phase ran with."
    )
    import_totals: ReferenceImportTotals | None = Field(
        default=None, description="Present on an import file, absent on the other two."
    )
    extraction_totals: ReferenceExtractionTotals | None = Field(
        default=None, description="Present on an extraction file, absent on the other two."
    )
    selection_totals: ReferenceSelectionTotals | None = Field(
        default=None, description="Present on a selection file, absent on the other two."
    )

    @model_validator(mode="after")
    def _the_totals_match_the_phase_that_claims_them(self) -> Self:
        blocks = {
            ReferencePhase.IMPORT: self.import_totals,
            ReferencePhase.EXTRACTION: self.extraction_totals,
            ReferencePhase.SELECTION: self.selection_totals,
        }
        if blocks[self.phase] is None:
            raise ValueError(f"a {self.phase.value} file carries no {self.phase.value} totals")
        strangers = [
            name.value for name, block in blocks.items() if name is not self.phase and block
        ]
        if strangers:
            raise ValueError(
                f"a {self.phase.value} metadata file carries totals it did not produce: "
                + ", ".join(sorted(strangers))
            )
        return self
