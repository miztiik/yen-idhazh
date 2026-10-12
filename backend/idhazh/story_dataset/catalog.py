"""Which identity proposals have an explicit reviewed canonical meaning?"""

from __future__ import annotations

from idhazh.contracts.story_annotation import (
    AnnotationRecord,
    ArticleDecision,
    CatalogReview,
    CatalogSnapshot,
    IdentityProposal,
)
from idhazh.story_dataset.catalog_context import CatalogContext, ResolvedPath
from idhazh.story_dataset.storage import Store, digest


def empty_catalog() -> CatalogSnapshot:
    return CatalogSnapshot(revision=digest([]), entities=[])


def read_catalog(store: Store) -> CatalogSnapshot:
    revision = store.setting("catalog")
    return store.get("catalog", revision, CatalogSnapshot) if revision else empty_catalog()


def identity_id(kind: str, identity_key: str) -> str:
    """A key must describe the global identity, not an article or display-name match."""
    return kind + "-" + digest({"kind": kind, "identity_key": identity_key})


def validate_catalog(catalog: CatalogSnapshot, article_ids: set[str]) -> None:
    entities = {item.id: item for item in catalog.entities}
    if len(entities) != len(catalog.entities):
        raise ValueError("duplicate catalog identities")
    for item in catalog.entities:
        if item.id != identity_id(item.kind, item.identity_key):
            raise ValueError("canonical ID differs from its explicit identity key")
        if not set(item.evidence_article_ids) <= article_ids:
            raise ValueError("catalog evidence names an unknown article")
        parents = [entities.get(parent) for parent in item.parent_ids]
        if any(parent is None for parent in parents):
            raise ValueError("unknown catalog parent")
        kinds = {parent.kind for parent in parents if parent is not None}
        expected = {"topic": set(), "event": {"topic"}, "story": {"event"}, "occurrence": {"story"}}
        if kinds != expected[item.kind] or len(item.parent_ids) != len(set(item.parent_ids)):
            raise ValueError("catalog parents do not form Topic > Event > Story > occurrence")
    context = CatalogContext(catalog)
    for old, new in catalog.aliases.items():
        if old not in entities or new not in entities or entities[old].kind != entities[new].kind:
            raise ValueError("alias endpoints must be known identities of the same kind")
        context.resolve_ref("", old)
    for target in catalog.proposal_resolutions.values():
        if target not in entities:
            raise ValueError("proposal resolution names an unknown identity")


def resolve_ref(catalog: CatalogSnapshot, batch_id: str, ref: str) -> str | None:
    return CatalogContext(catalog).resolve_ref(batch_id, ref)


def validate_decision(
    decision: ArticleDecision,
    catalog: CatalogSnapshot,
    proposals: list[IdentityProposal],
    article_ids: set[str],
) -> None:
    CatalogContext(catalog).validate_decision(decision, proposals, article_ids)


def resolved_paths(
    record: AnnotationRecord, catalog: CatalogSnapshot
) -> list[ResolvedPath] | None:
    return CatalogContext(catalog).resolved_paths(record)


def review_catalog(store: Store, review: CatalogReview, article_ids: set[str]) -> CatalogSnapshot:
    with store.transaction():
        current = read_catalog(store)
        if current.revision != review.expected_revision:
            raise ValueError("catalog changed; reread and review against the new revision")
        entities = {item.id: item for item in current.entities}
        for item in review.entities:
            if item.id in entities and entities[item.id] != item:
                raise ValueError(
                    "existing identities are immutable; review a new identity and alias"
                )
            entities[item.id] = item
        aliases = {**current.aliases, **review.aliases}
        resolutions = {**current.proposal_resolutions, **review.proposal_resolutions}
        for key, target in review.proposal_resolutions.items():
            batch, _, ref = key.partition(":proposal:")
            from idhazh.contracts.story_annotation import WorkerSubmission

            submission = store.get("batch-submission", batch, WorkerSubmission)
            proposal = next((p for p in submission.proposals if p.ref == "proposal:" + ref), None)
            if proposal is None or target not in entities or proposal.kind != entities[target].kind:
                raise ValueError("resolution does not name a submitted proposal of the same kind")
        revision = digest({"previous": current.revision, "review": review})
        updated = CatalogSnapshot(
            revision=revision,
            entities=list(entities.values()),
            aliases=aliases,
            proposal_resolutions=resolutions,
        )
        validate_catalog(updated, article_ids)
        context = CatalogContext(updated)
        for kind in ("annotation", "review"):
            for record in store.records(kind, AnnotationRecord):
                context.resolved_paths(record)
        store.save("catalog", revision, updated)
        store.append("catalog-review", digest(review), revision, review)
        store.set_setting("catalog", revision)
    return updated
