"""The entity watchlist (`config/watchlist.json`).

An entity is followed by name rather than by feed list. Where it has feeds at
all there is roughly one, against roughly twenty-five for a vertical. That
asymmetry is the whole reason entities are a separate primitive.

The registry holds two kinds of entry. An organisation is a standing name - a
company or an institution - and it is in the news most weeks. A subject is a
running story: a pandemic, a tournament, an export-control regime. It has no
filer id, often no feed, and it goes quiet between instalments. `EntityKind` is
what tells the two apart.

US filers additionally resolve through EDGAR, which needs no key but does
require a declared contact address in the `User-Agent`. Non-US entities have no
EDGAR coverage at all, so the watchlist needs both layers.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Model, Slug, Url
from idhazh.contracts.taxonomy import Lifecycled, LifecycleStatus, SourceTier

Cik = Annotated[str, StringConstraints(pattern=r"^[0-9]{10}$")]
ContactEmail = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class EntityKind(StrEnum):
    """What the entry names: a standing organisation, or a running subject."""

    ORGANISATION = "organisation"
    SUBJECT = "subject"


class EntityFeed(Lifecycled):
    """A newsroom or blog feed belonging to one entity."""

    id: Slug
    title: str = Field(min_length=1)
    url: Url
    tier: SourceTier = SourceTier.INSTITUTION


class EntityDef(Lifecycled):
    """One entry in the registry: a named organisation, or a running subject."""

    id: Slug
    display_name: str = Field(min_length=1)
    kind: EntityKind = Field(
        default=EntityKind.ORGANISATION,
        description=(
            "Whether this entry names a standing organisation or a running subject. A "
            "subject - a pandemic, a tournament, an export-control regime - has no filer "
            "id and often no feed, so the registry has to say which kind it holds. "
            "Absent means organisation, which is what every entry written before the "
            "field existed was."
        ),
    )
    aliases: list[str] = Field(
        default_factory=list,
        description=(
            "Every name this entity is called. An item is tagged with the entity when "
            "one of these appears in its words as a whole-word phrase, case-folded, and "
            "the same set decides the watchlist ranking bonus against a candidate's feed "
            "title. Nothing is derived from the id or the display name. An entity with "
            "no alias is never matched and never lifts a score."
        ),
    )
    cik: Cik | None = Field(
        default=None,
        description=(
            "Ten-digit, zero-padded SEC filer id. Null for a non-US entity, and null "
            "for every subject, because only an organisation files with the SEC."
        ),
    )
    feeds: list[EntityFeed] = Field(default_factory=list)

    @model_validator(mode="after")
    def _only_an_organisation_files_with_the_sec(self) -> Self:
        if self.kind is not EntityKind.ORGANISATION and self.cik is not None:
            raise ValueError("a cik belongs to an organisation, never to a subject")
        return self


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
            version="2026-08-31",
            change=(
                "EntityDef gained kind, so an entry can be a subject and not only "
                "an organisation."
            ),
            why=(
                "A running story - a pandemic, a tournament, an export-control regime - "
                "has no SEC filer id and no feed of its own, and the registry described "
                "itself as a list of named organisations, so nothing could hold one. The "
                "field defaults to organisation, which is what all 30 committed entries "
                "are, so the change is additive and no payload needs a migration."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change="Stated the match rule on EntityDef.aliases.",
            why=(
                "The field was declared on day one and read nowhere, so entities were "
                "empty on every committed item and the watchlist ranking bonus had never "
                "moved a score. The rule is now written where the terms live. "
                "Description-only, so no payload changes and none needs a migration."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: entities with their own feeds, plus the EDGAR policy.",
            why="Contracts before logic - the entity bonus is computed against a fixed shape.",
        ),
    )

    entities: list[EntityDef]
    edgar: EdgarPolicy = Field(default_factory=EdgarPolicy)

    def entity_terms(self) -> dict[str, list[str]]:
        """The entity match surface. A retired entity keeps its tombstone and stops matching."""
        return {
            entity.id: entity.aliases
            for entity in self.entities
            if entity.status is not LifecycleStatus.RETIRED
        }

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
