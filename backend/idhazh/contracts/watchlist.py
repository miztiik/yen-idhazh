"""The entity watchlist (`config/watchlist.json`).

An entity is followed by name and carries its own primary feeds - roughly one
feed each, against roughly twenty-five for a vertical. That asymmetry is the
whole reason entities are a separate primitive rather than a vertical.

US filers additionally resolve through EDGAR, which needs no key but does
require a declared contact address in the `User-Agent`. Non-US entities have no
EDGAR coverage at all, so the watchlist needs both layers.
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Model, Slug, Url
from idhazh.contracts.taxonomy import Lifecycled, SourceTier

Cik = Annotated[str, StringConstraints(pattern=r"^[0-9]{10}$")]
ContactEmail = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class EntityFeed(Lifecycled):
    """A newsroom or blog feed belonging to one entity."""

    id: Slug
    title: str = Field(min_length=1)
    url: Url
    tier: SourceTier = SourceTier.INSTITUTION


class EntityDef(Lifecycled):
    """One named organisation."""

    id: Slug
    display_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    cik: Cik | None = Field(
        default=None,
        description="Ten-digit, zero-padded SEC filer id. Null for a non-US entity.",
    )
    feeds: list[EntityFeed] = Field(default_factory=list)


class EdgarPolicy(Model):
    """How the SEC submissions endpoint is consulted, when it is."""

    enabled: bool = False
    contact_email: ContactEmail | None = Field(
        default=None,
        description="Declared in the User-Agent. SEC refuses the request without one.",
    )
    requests_per_second: int = Field(default=10, ge=1, le=10)
    submissions_url_template: str = "https://data.sec.gov/submissions/CIK{cik}.json"
    company_tickers_url: Url = "https://www.sec.gov/files/company_tickers.json"

    @model_validator(mode="after")
    def _contact_is_declared_when_enabled(self) -> Self:
        if self.enabled and self.contact_email is None:
            raise ValueError("EDGAR requires a declared contact_email before it may be enabled")
        return self


class Watchlist(Contract):
    """`config/watchlist.json` - the entities whose news gets a ranking bonus."""

    __schema_stem__: ClassVar[str] = "watchlist"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: entities with their own feeds, plus the EDGAR policy.",
            why="Contracts before logic - the entity bonus is computed against a fixed shape.",
        ),
    )

    entities: list[EntityDef]
    edgar: EdgarPolicy = Field(default_factory=EdgarPolicy)

    @model_validator(mode="after")
    def _ids_are_distinct(self) -> Self:
        entity_ids = [entity.id for entity in self.entities]
        if len(set(entity_ids)) != len(entity_ids):
            raise ValueError("entity ids must be distinct")
        feed_ids = [feed.id for entity in self.entities for feed in entity.feeds]
        if len(set(feed_ids)) != len(feed_ids):
            raise ValueError("entity feed ids must be distinct across the watchlist")
        ciks = [entity.cik for entity in self.entities if entity.cik is not None]
        if len(set(ciks)) != len(ciks):
            raise ValueError("a CIK may name only one entity")
        return self
