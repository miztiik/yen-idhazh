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

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    Sha256,
    Slug,
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
