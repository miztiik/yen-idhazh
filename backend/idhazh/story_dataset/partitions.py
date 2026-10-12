"""Can event-linked articles be split without leaking groups or redrawing a held-out split?"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from idhazh.contracts.story_candidates import PairFrame
from idhazh.contracts.story_evaluation import Partition, StoryPolicy
from idhazh.contracts.story_source import SourceFreeze
from idhazh.story_dataset.catalog import read_catalog
from idhazh.story_dataset.catalog_context import CatalogContext
from idhazh.story_dataset.storage import Store, digest
from idhazh.story_dataset.workers import latest_annotations


def build_partition(
    store: Store,
    manifest: SourceFreeze,
    article_ids: set[str],
    policy: StoryPolicy,
    regression_ids: set[str],
    frame: PairFrame | None = None,
    previous: Partition | None = None,
) -> Partition:
    catalog = read_catalog(store)
    context = CatalogContext(catalog)
    records = latest_annotations(store)
    parents = {identity: identity for identity in article_ids}

    def find(identity: str) -> str:
        while parents[identity] != identity:
            parents[identity] = parents[parents[identity]]
            identity = parents[identity]
        return identity

    def join(a: str, b: str) -> None:
        parents[find(a)] = find(b)

    # Every membership contributes; overlapping events join the complete article component.
    first_by_event: dict[str, str] = {}
    unqualified = set(article_ids) - records.keys()
    for identity, record in records.items():
        if identity not in article_ids:
            continue
        paths = context.resolved_paths(record)
        if paths is None or record.decision.state != "annotated":
            unqualified.add(identity)
        # Qualification requires the whole path; leakage only needs its known Event.
        for membership in record.decision.memberships:
            event = context.resolve_ref(record.batch_id, membership.event)
            if event is None:
                continue
            if event in first_by_event:
                join(identity, first_by_event[event])
            first_by_event[event] = identity
    if frame:
        if frame.source_sha256 != manifest.source_sha256:
            raise ValueError("pair links belong to another source")
        for pair in frame.pairs:
            if pair.a not in article_ids or pair.b not in article_ids:
                raise ValueError("foreign pair-link article")
            join(pair.a, pair.b)
    components: dict[str, list[str]] = defaultdict(list)
    for identity in sorted(article_ids):
        components[find(identity)].append(identity)
    assignments: dict[str, Literal["development", "confirmation", "quarantine"]] = {}
    component_ids = {}
    crossings = 0
    quarantine_reasons: dict[
        str, list[Literal["unknown-membership", "regression-exposure", "new-crossing-link"]]
    ] = {}
    partition: Literal["development", "confirmation", "quarantine"]
    exposure = dict(previous.article_exposure) if previous else {}
    if previous:
        if previous.source_sha256 != manifest.source_sha256 or previous.seed != policy.seed:
            raise ValueError("previous split belongs to another source")
        regression_ids = regression_ids | set(previous.regression_article_ids)
        for identity, assignment in previous.article_partitions.items():
            if assignment != "quarantine":
                exposure.setdefault(identity, assignment)
    regression_exposed = regression_ids | {
        identity
        for identity, reasons in (previous.quarantine_reasons.items() if previous else [])
        if "regression-exposure" in reasons
    }
    for members in components.values():
        component = digest(members)
        prior = set()
        if previous:
            prior = {
                previous.article_partitions[identity]
                for identity in members
                if identity in previous.article_partitions
                and (
                    previous.article_partitions[identity] != "quarantine"
                    or set(previous.quarantine_reasons.get(identity, ["new-crossing-link"]))
                    - {"unknown-membership"}
                )
            }
            prior.update(exposure[identity] for identity in members if identity in exposure)
        crossing = len(prior - {"quarantine"}) > 1
        if crossing:
            crossings += 1
        if set(members) & (regression_exposed | unqualified) or crossing or "quarantine" in prior:
            partition = "quarantine"
        elif prior:
            partition = next(iter(prior))
        else:
            draw = int(digest({"component": component, "seed": policy.seed}), 16) / (1 << 256)
            partition = "development" if draw < policy.development_fraction else "confirmation"
        for identity in members:
            assignments[identity] = partition
            if partition != "quarantine":
                exposure.setdefault(identity, partition)
            component_ids[identity] = component
            reasons: list[
                Literal[
                    "unknown-membership",
                    "regression-exposure",
                    "new-crossing-link",
                ]
            ] = []
            if set(members) & unqualified:
                reasons.append("unknown-membership")
            if set(members) & regression_exposed:
                reasons.append("regression-exposure")
            if crossing or "quarantine" in prior:
                reasons.append("new-crossing-link")
            if reasons:
                quarantine_reasons[identity] = reasons
    blockers = []
    if unqualified:
        blockers.append(f"{len(unqualified)} articles unvisited, unresolved or catalog-pending")
    if crossings:
        blockers.append(f"{crossings} newly crossing components quarantined; split never redrawn")
    if not {"development", "confirmation"} <= set(assignments.values()):
        blockers.append("fresh development and confirmation event components not both available")
    result = Partition(
        source_sha256=manifest.source_sha256,
        catalog_revision=catalog.revision,
        annotation_state_sha256=digest(
            {key: row.record_id for key, row in sorted(records.items())}
        ),
        seed=policy.seed,
        article_partitions=assignments,
        component_ids=component_ids,
        regression_article_ids=sorted(regression_ids & article_ids),
        blocked_reasons=blockers,
        quarantine_reasons=quarantine_reasons,
        article_exposure=exposure,
    )
    with store.transaction():
        store.save("partition", digest(result), result)
        store.set_setting("partition", digest(result))
    return result
