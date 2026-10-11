"""Which identity proposals have an explicit reviewed canonical meaning?"""

from __future__ import annotations

from idhazh.contracts.story_annotation import (
    AnnotationRecord,
    ArticleDecision,
    CatalogReview,
    CatalogSnapshot,
    Identity,
    IdentityProposal,
)
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
    for old, new in catalog.aliases.items():
        if old not in entities or new not in entities or entities[old].kind != entities[new].kind:
            raise ValueError("alias endpoints must be known identities of the same kind")
        resolve_ref(catalog, "", old)
    for target in catalog.proposal_resolutions.values():
        if target not in entities:
            raise ValueError("proposal resolution names an unknown identity")


def resolve_ref(catalog: CatalogSnapshot, batch_id: str, ref: str) -> str | None:
    if ref.startswith("proposal:"):
        ref = catalog.proposal_resolutions.get(batch_id + ":" + ref, "")
        if not ref:
            return None
    seen = set()
    while ref in catalog.aliases:
        if ref in seen:
            raise ValueError("catalog alias cycle")
        seen.add(ref)
        ref = catalog.aliases[ref]
    if ref not in {item.id for item in catalog.entities}:
        raise ValueError(f"unknown canonical identity: {ref}")
    return ref


def validate_decision(
    decision: ArticleDecision,
    catalog: CatalogSnapshot,
    proposals: list[IdentityProposal],
    article_ids: set[str],
) -> None:
    nodes: dict[str, Identity | IdentityProposal] = {item.id: item for item in catalog.entities}
    if len({item.ref for item in proposals}) != len(proposals):
        raise ValueError("duplicate local proposal references")
    nodes.update({item.ref: item for item in proposals})
    for proposal in proposals:
        if not set(proposal.evidence_article_ids) <= article_ids:
            raise ValueError("proposal evidence contains foreign article IDs")
        kinds = {nodes[p].kind for p in proposal.parent_refs if p in nodes}
        expected = {"topic": set(), "event": {"topic"}, "story": {"event"}, "occurrence": {"story"}}
        if (
            any(p not in nodes for p in proposal.parent_refs)
            or kinds != expected[proposal.kind]
            or (proposal.kind != "topic" and not proposal.parent_refs)
        ):
            raise ValueError("proposal has unknown or wrongly typed parents")
    for path in decision.memberships:
        refs = [path.topic, path.event, path.story, *path.occurrence_refs]
        if any(ref not in nodes for ref in refs):
            raise ValueError("membership names an unknown identity")
        for ref, kind in zip(
            refs,
            ["topic", "event", "story", *["occurrence"] * len(path.occurrence_refs)],
            strict=True,
        ):
            if nodes[ref].kind != kind:
                raise ValueError("wrongly typed membership")
        for child, parent in [
            (path.event, path.topic),
            (path.story, path.event),
            *[(r, path.story) for r in path.occurrence_refs],
        ]:
            node = nodes[child]
            parents = node.parent_refs if isinstance(node, IdentityProposal) else node.parent_ids
            if parent not in parents:
                raise ValueError("membership uses an unsupported typed parent link")


def resolved_paths(
    record: AnnotationRecord, catalog: CatalogSnapshot
) -> list[tuple[str, str, str, tuple[str, ...]]] | None:
    paths = []
    entities = {item.id: item for item in catalog.entities}
    for path in record.decision.memberships:
        refs = [path.topic, path.event, path.story, *path.occurrence_refs]
        resolved = [resolve_ref(catalog, record.batch_id, ref) for ref in refs]
        if any(ref is None for ref in resolved):
            return None
        topic, event, story, *occurrences = [str(ref) for ref in resolved]
        for child, parent in [(event, topic), (story, event), *[(r, story) for r in occurrences]]:
            canonical_parents = {resolve_ref(catalog, "", p) for p in entities[child].parent_ids}
            if parent not in canonical_parents:
                raise ValueError("reviewed canonicalization breaks a membership path")
        paths.append((topic, event, story, tuple(sorted(occurrences))))
    return sorted(paths)


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
        for kind in ("annotation", "review"):
            for record in store.records(kind, AnnotationRecord):
                resolved_paths(record, updated)
        store.save("catalog", revision, updated)
        store.append("catalog-review", digest(review), revision, review)
        store.set_setting("catalog", revision)
    return updated
