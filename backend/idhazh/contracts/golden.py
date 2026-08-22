"""The golden set: the fixed corpus every model candidate is judged on.

URLs, never bodies. Republishing article text is a non-goal (`CLAUDE.md`
section 0a) and storing it would be a copyright problem, so the set names
addresses and the validation stage re-fetches them through the same fetch and
extract path the pipeline uses. That is also what makes the measurement
end-to-end rather than a test of the summarizer alone.

The cost of that choice, stated rather than discovered later: **URLs rot.** An
article moves, a site redesigns, a paywall appears. A validation run that cannot
fetch enough of the set does not quietly score fewer - the decision rule refuses
an undersampled mean on both sides, so the gate reports that it could not judge
rather than judging on thin evidence.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, Model, Slug, Url


class GoldenArticle(Model):
    url: Url
    vertical: Slug
    source_id: Slug
    added_on: DateStamp
    # The feed's own headline, which the pipeline also carries into extraction.
    # A headline is metadata, not the body this file refuses to store.
    title: UntrustedLine | None = None


class GoldenSet(Contract):
    """`config/golden.json` - the corpus a model swap is argued over."""

    __schema_stem__: ClassVar[str] = "golden-set"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-22",
            change="Initial shape: addresses and their vertical, never article text.",
            why=(
                "Row #7 judges candidate models on one fixed corpus. It has to be the same "
                "corpus every time or the comparison measures the corpus, and it cannot be "
                "article bodies or the repository is republishing someone else's work."
            ),
        ),
    )

    articles: list[GoldenArticle] = Field(min_length=1)

    @model_validator(mode="after")
    def _addresses_are_distinct(self) -> Self:
        urls = [article.url for article in self.articles]
        if len(set(urls)) != len(urls):
            raise ValueError("the same article twice is one article and a wrong denominator")
        return self
