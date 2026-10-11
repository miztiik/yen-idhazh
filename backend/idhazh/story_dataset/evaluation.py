"""Which declared pilot can be measured without hiding missing labels, vectors or qrels?"""

from __future__ import annotations

from idhazh.contracts.story_annotation import AnnotationRecord
from idhazh.contracts.story_candidate_evaluation import CandidateEvaluationSnapshot
from idhazh.contracts.story_candidates import PairFrame, PairRecord, VectorManifest
from idhazh.contracts.story_evaluation import (
    ClusterRun,
    DevelopmentConfig,
    EvaluationReport,
    Partition,
    RetrievalRun,
)
from idhazh.contracts.story_source import SourceFreeze
from idhazh.contracts.story_vector_derivation import DerivedVectorSnapshot
from idhazh.story_dataset.catalog import read_catalog, resolved_paths
from idhazh.story_dataset.metrics import neighbor_metrics, overlap_pair_metrics
from idhazh.story_dataset.sampling import pair_id
from idhazh.story_dataset.storage import Store, digest
from idhazh.story_dataset.vectors import covered_ids, validate_vectors
from idhazh.story_dataset.workers import latest_annotations

LIMITATIONS = [
    "Model labels are not human labels; review agreement is not accuracy.",
    "No owner-approved random-audit rate, quality acceptance bound or minimum model difference.",
    "Representative and challenge pair streams are reported separately, even when IDs overlap.",
    "Recall/NDCG cover only the completely judged candidate universe, not archive retrieval.",
    "This report cannot qualify adoption, fine-tuning or full-archive completion.",
]


def evaluate(
    store: Store,
    manifest: SourceFreeze,
    partition: Partition | None,
    vectors: VectorManifest | None,
    frame: PairFrame | None,
    retrieval: RetrievalRun | None = None,
    clusters: ClusterRun | None = None,
) -> EvaluationReport:
    blockers = []
    metrics: dict[str, float] = {}
    records = latest_annotations(store)
    catalog = read_catalog(store)
    pair_records = {row.pair_id: row for row in store.records("pair", PairRecord)}
    representative = challenge = 0
    if frame:
        for row in frame.pairs:
            if row.id in pair_records:
                representative += row.representative_probability is not None
                challenge += bool(row.challenge_tags)
    if partition is None:
        blockers.append("no outcome-blind event/article partition has been fixed")
    elif (
        partition.source_sha256 != manifest.source_sha256
        or partition.catalog_revision != catalog.revision
        or partition.annotation_state_sha256
        != digest({key: row.record_id for key, row in sorted(records.items())})
    ):
        blockers.append(
            "partition source/catalog/annotation snapshot changed; rebuild with quarantine"
        )
    if vectors is None:
        blockers.append("no validated vector manifest")
    else:
        validate_vectors(vectors, store.root)
        if vectors.source_sha256 != manifest.source_sha256:
            blockers.append("vectors belong to another source")
    if retrieval is None and clusters is None:
        blockers.append("no declared retrieval rankings or predicted overlapping clusters")
    evaluated_queries = evaluated_articles = 0
    for run in (retrieval, clusters):
        if run is None or partition is None or vectors is None:
            continue
        try:
            config = store.get(
                "development-config", run.development_config_sha256, DevelopmentConfig
            )
            if config.partition_sha256 != digest(partition):
                raise ValueError("development config belongs to a different partition")
            if isinstance(vectors, (DerivedVectorSnapshot, CandidateEvaluationSnapshot)):
                selected = config.parameters.get("vector_candidates")
                candidate_slug = (
                    vectors.derivation.slug if isinstance(vectors, DerivedVectorSnapshot)
                    else vectors.candidate.slug
                )
                if (
                    not isinstance(selected, dict)
                    or selected.get(run.model) != digest(vectors)
                    or run.model != candidate_slug
                ):
                    raise ValueError("vector candidate was not frozen in development")
            opened = store.setting("confirmation-opened")
            if run.partition == "confirmation" and opened not in (None, digest(config)):
                raise ValueError(
                    "confirmation was already opened with different development settings"
                )
        except ValueError as error:
            blockers.append(str(error))
            continue
        if (
            run.source_sha256 != manifest.source_sha256
            or run.partition_sha256 != digest(partition)
            or run.vector_manifest_sha256 != digest(vectors)
        ):
            blockers.append("prediction provenance differs from fixed evaluation inputs")
            continue
        ids = (
            set(run.candidate_article_ids) | set(run.rankings)
            if isinstance(run, RetrievalRun)
            else set(run.memberships)
        )
        usable = covered_ids(vectors, run.model)
        if not ids <= usable:
            blockers.append(f"{len(ids - usable)} prediction articles lack text-matched vectors")
            continue
        if any(partition.article_partitions.get(identity) != run.partition for identity in ids):
            blockers.append(
                "prediction includes cross-partition, regression or quarantined articles"
            )
            continue
        if run.partition == "confirmation":
            with store.transaction():
                store.set_setting("confirmation-opened", run.development_config_sha256)
        if any(
            identity not in records
            or records[identity].decision.state != "annotated"
            or resolved_paths(records[identity], catalog) is None
            for identity in ids
        ):
            blockers.append(
                "prediction universe has incomplete or catalog-pending article annotations"
            )
            continue
        conflicts = []
        for review in store.records("review", AnnotationRecord):
            primary = records.get(review.article_id)
            if (
                primary is None
                or primary.record_id != review.review_target
                or review.article_id not in ids
            ):
                continue
            if (
                resolved_paths(primary, catalog) != resolved_paths(review, catalog)
                or primary.decision.state != review.decision.state
                or review.decision.state == "unresolved"
            ):
                conflicts.append(review.article_id)
        if conflicts:
            blockers.append("independent article-review conflicts remain uncorrected")
            continue
        if isinstance(run, RetrievalRun):
            if run.model not in {cache.slug for cache in vectors.caches}:
                blockers.append("retrieval model is absent from the validated vector manifest")
                continue
            if len(set(run.candidate_article_ids)) != len(run.candidate_article_ids):
                blockers.append("duplicate candidate-universe IDs")
                continue
            results = []
            for query, ranking in run.rankings.items():
                if query not in run.candidate_article_ids:
                    blockers.append("query lies outside the declared article universe")
                    continue
                relevance = {}
                complete = True
                for other in run.candidate_article_ids:
                    if query == other:
                        continue
                    judgment = pair_records.get(pair_id(query, other))
                    if judgment is None:
                        complete = False
                        break
                    reviews = [
                        r
                        for r in store.records("pair-review", PairRecord)
                        if r.review_target == judgment.record_id
                    ]
                    if any(
                        getattr(
                            r.decision, run.relation if run.relation != "duplicate" else "coverage"
                        )
                        != getattr(
                            judgment.decision,
                            run.relation if run.relation != "duplicate" else "coverage",
                        )
                        for r in reviews
                    ):
                        complete = False
                        blockers.append("independent pair-review conflicts remain uncorrected")
                        break
                    value = getattr(
                        judgment.decision,
                        "coverage" if run.relation == "duplicate" else run.relation,
                    )
                    if value == "unresolved":
                        complete = False
                        break
                    relevance[other] = value in ("shared", "same", "duplicate")
                    if run.relation == "occurrence" and value == "partial":
                        # Partial occurrence overlap is relevant here, not at duplicate level.
                        relevance[other] = True
                if not complete:
                    blockers.append(
                        "incomplete qrels; unjudged/unresolved candidates are not negatives"
                    )
                    continue
                try:
                    results.append(neighbor_metrics(ranking, relevance, run.k))
                except ValueError as error:
                    blockers.append(str(error))
            if len(results) == len(run.rankings) and results:
                metrics.update(
                    {
                        f"{run.relation}:{name}": sum(row[name] for row in results) / len(results)
                        for name in results[0]
                    }
                )
                evaluated_queries = len(results)
                evaluated_articles = len(run.candidate_article_ids)
        else:
            if run.development_config_partition_sha256 != run.partition_sha256:
                blockers.append(
                    "cluster algorithm was not frozen against this development partition"
                )
                continue
            index = {"topic": 0, "event": 1, "story": 2}[run.level]
            gold = {}
            for identity in ids:
                paths = resolved_paths(records[identity], catalog)
                assert paths is not None
                gold[identity] = {str(path[index]) for path in paths}
            try:
                metrics.update(
                    {
                        f"{run.level}:{name}": value
                        for name, value in overlap_pair_metrics(
                            gold,
                            {identity: set(labels) for identity, labels in run.memberships.items()},
                        ).items()
                    }
                )
                evaluated_articles = max(evaluated_articles, len(ids))
            except ValueError as error:
                blockers.append(str(error))
    if blockers:
        metrics = {}
        evaluated_queries = evaluated_articles = 0
    return EvaluationReport(
        source_sha256=manifest.source_sha256,
        state="blocked" if blockers else "pilot-measured",
        scope="declared-candidate-article-universe-not-full-archive",
        blockers=sorted(set(blockers)),
        metrics=metrics,
        evaluated_queries=evaluated_queries,
        evaluated_articles=evaluated_articles,
        representative_pairs_judged=representative,
        challenge_pairs_judged=challenge,
        limitations=LIMITATIONS,
    )
