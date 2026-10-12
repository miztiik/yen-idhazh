"""How can one immutable catalogue index validate many historical memberships?"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from idhazh.contracts.story_annotation import (
    AnnotationRecord,
    ArticleDecision,
    CatalogSnapshot,
    IdentityProposal,
    Kind,
)

type ResolvedPath = tuple[str, str, str, tuple[str, ...]]

_PARENT_KINDS: Mapping[Kind, set[Kind]] = {
    "topic": set(), "event": {"topic"}, "story": {"event"}, "occurrence": {"story"},
}


@dataclass(frozen=True, slots=True)
class _Node:
    kind: Kind
    parent_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, init=False)
class CatalogContext:
    """Copy one exact snapshot's links; reuse only within that snapshot's operation."""

    revision: str
    _entities: Mapping[str, _Node]
    _aliases: Mapping[str, str]
    _resolutions: Mapping[str, str]
    _canonical: dict[str, str] = field(default_factory=dict)
    _parents: dict[str, frozenset[str]] = field(default_factory=dict)

    def __init__(self, catalog: CatalogSnapshot) -> None:
        object.__setattr__(self, "revision", catalog.revision)
        object.__setattr__(self, "_entities", MappingProxyType({
            item.id: _Node(item.kind, tuple(item.parent_ids)) for item in catalog.entities
        }))
        object.__setattr__(self, "_aliases", MappingProxyType(dict(catalog.aliases)))
        object.__setattr__(
            self, "_resolutions", MappingProxyType(dict(catalog.proposal_resolutions)),
        )
        object.__setattr__(self, "_canonical", {})
        object.__setattr__(self, "_parents", {})

    def resolve_ref(self, batch_id: str, ref: str) -> str | None:
        if ref.startswith("proposal:"):
            ref = self._resolutions.get(batch_id + ":" + ref, "")
            if not ref:
                return None
        return self._canonical_ref(ref)

    def _canonical_ref(self, ref: str) -> str:
        trail: set[str] = set()
        while ref in self._aliases and ref not in self._canonical:
            if ref in trail:
                raise ValueError("catalog alias cycle")
            trail.add(ref)
            ref = self._aliases[ref]
        ref = self._canonical.get(ref, ref)
        if ref not in self._entities:
            raise ValueError(f"unknown canonical identity: {ref}")
        self._canonical[ref] = ref
        for old in trail:
            self._canonical[old] = ref
        return ref

    def _canonical_parents(self, child: str) -> frozenset[str]:
        if child not in self._parents:
            # Only the resolved child's declared parents count; never historical unions.
            self._parents[child] = frozenset(
                self._canonical_ref(parent) for parent in self._entities[child].parent_ids
            )
        return self._parents[child]

    def validate_decision(
        self, decision: ArticleDecision, proposals: list[IdentityProposal], article_ids: set[str],
    ) -> None:
        local = {item.ref: item for item in proposals}
        if len(local) != len(proposals):
            raise ValueError("duplicate local proposal references")

        def known(ref: str) -> bool:
            return ref in local or ref in self._entities

        def approved_ref(ref: str) -> str:
            # Submitted proposals remain local even if another batch resolved the same ref.
            return ref if ref.startswith("proposal:") else self._canonical_ref(ref)

        def node(ref: str) -> _Node | IdentityProposal:
            return local[ref] if ref.startswith("proposal:") else self._entities[ref]

        for proposal in proposals:
            if not set(proposal.evidence_article_ids) <= article_ids:
                raise ValueError("proposal evidence contains foreign article IDs")
            kinds = {node(approved_ref(p)).kind for p in proposal.parent_refs if known(p)}
            if (
                any(not known(p) for p in proposal.parent_refs)
                or kinds != _PARENT_KINDS[proposal.kind]
                or (proposal.kind != "topic" and not proposal.parent_refs)
            ):
                raise ValueError("proposal has unknown or wrongly typed parents")
        for path in decision.memberships:
            refs = [path.topic, path.event, path.story, *path.occurrence_refs]
            if any(not known(ref) for ref in refs):
                raise ValueError("membership names an unknown identity")
            for ref, kind in zip(
                refs, ["topic", "event", "story", *["occurrence"] * len(path.occurrence_refs)],
                strict=True,
            ):
                if node(approved_ref(ref)).kind != kind:
                    raise ValueError("wrongly typed membership")
            for child, parent in [
                (path.event, path.topic), (path.story, path.event),
                *[(r, path.story) for r in path.occurrence_refs],
            ]:
                canonical_child = approved_ref(child)
                child_node = node(canonical_child)
                parents = (
                    frozenset(approved_ref(p) for p in child_node.parent_refs)
                    if isinstance(child_node, IdentityProposal)
                    else self._canonical_parents(canonical_child)
                )
                if approved_ref(parent) not in parents:
                    raise ValueError("membership uses an unsupported typed parent link")

    def resolved_paths(self, record: AnnotationRecord) -> list[ResolvedPath] | None:
        paths = []
        pending = False
        for path in record.decision.memberships:
            refs = [path.topic, path.event, path.story, *path.occurrence_refs]
            resolved = [self.resolve_ref(record.batch_id, ref) for ref in refs]
            for ref, kind in zip(
                resolved, ["topic", "event", "story", *["occurrence"] * len(path.occurrence_refs)],
                strict=True,
            ):
                if ref is not None and self._entities[ref].kind != kind:
                    raise ValueError("wrongly typed reviewed membership")
            topic, event, story, *occurrences = resolved
            for child, parent in [
                (event, topic), (story, event), *[(r, story) for r in occurrences],
            ]:
                if child is not None and parent is not None:
                    if parent not in self._canonical_parents(child):
                        raise ValueError("reviewed canonicalization breaks a membership path")
            if any(ref is None for ref in resolved):
                pending = True
            else:
                complete = [str(ref) for ref in resolved]
                paths.append((complete[0], complete[1], complete[2], tuple(sorted(complete[3:]))))
        return None if pending else sorted(paths)
