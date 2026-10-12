"""Which exact source and evidence does an archive annotation describe?"""

from typing import Annotated, Literal

from pydantic import Field

from idhazh.contracts.base import DateStamp, Model, Sha256, Timestamp, Url

Nonempty = Annotated[str, Field(min_length=1)]
ArticleId = Annotated[str, Field(pattern=r"^a-[0-9a-f]{64}$")]


class ArchiveArticle(Model):
    domain: Nonempty
    first_day: DateStamp
    item_id: Nonempty
    published_at: Timestamp
    time_source: Nonempty | None
    title: Nonempty
    summary: Nonempty
    url: Url


class ArticleEvidence(Model):
    article_id: ArticleId
    input_sha256: Sha256
    source: ArchiveArticle


class SourceCheck(Model):
    url: Url
    checked_at: Timestamp | None
    state: Literal["read", "redirect", "inaccessible"]
    finding: Nonempty
    evidence_sha256: Sha256 | None = None
    final_url: Url | None = None
    evidence_reference: Nonempty | None = None


class SourceFreeze(Model):
    version: Literal["2026-10-09"] = "2026-10-09"
    source_file: Literal["articles.jsonl"] = "articles.jsonl"
    source_sha256: Sha256
    source_bytes: Annotated[int, Field(gt=0)]
    articles: Annotated[int, Field(gt=0)]
    first_days: list[DateStamp]
    frozen_at: Timestamp
    source_description: Nonempty
    regression_hashes: dict[str, Sha256]
    approved_examples_sha256: Sha256
    identity: Literal["sha256-exact-url;sha256-canonical-source-row"] = (
        "sha256-exact-url;sha256-canonical-source-row"
    )
