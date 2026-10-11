"""How many actual archive rows are qualified, pending, unresolved or independently reviewed?"""

from idhazh.contracts.story_annotation import AnnotationRecord
from idhazh.contracts.story_candidates import PairRecord
from idhazh.contracts.story_evaluation import DatasetStatus
from idhazh.contracts.story_source import SourceFreeze
from idhazh.story_dataset.catalog import read_catalog, resolved_paths
from idhazh.story_dataset.storage import Store
from idhazh.story_dataset.vector_files import read_vectors
from idhazh.story_dataset.vectors import covered_ids
from idhazh.story_dataset.workers import latest_annotations


def dataset_status(store: Store, manifest: SourceFreeze) -> DatasetStatus:
    catalog = read_catalog(store)
    latest = latest_annotations(store)
    reviews = store.records("review", AnnotationRecord)
    pending = unresolved = annotated = 0
    for record in latest.values():
        if record.decision.state == "unresolved":
            unresolved += 1
        elif resolved_paths(record, catalog) is None:
            pending += 1
        else:
            annotated += 1
    by_record = {row.record_id: row for row in store.records("annotation", AnnotationRecord)}
    conflicts = 0
    for review in reviews:
        original = by_record[str(review.review_target)]
        if latest[review.article_id].record_id != review.review_target:
            continue
        a = resolved_paths(original, catalog)
        b = resolved_paths(review, catalog)
        if (
            a is None
            or b is None
            or a != b
            or original.decision.state != review.decision.state
            or review.decision.state == "unresolved"
        ):
            conflicts += 1
    vector_revision = store.setting("vectors")
    covered = 0
    if vector_revision:
        vectors = read_vectors(store, vector_revision)
        covered = len(covered_ids(vectors))
    latest_pairs = {r.pair_id: r for r in store.records("pair", PairRecord)}
    pair_reviews = [
        r
        for r in store.records("pair-review", PairRecord)
        if r.pair_id in latest_pairs and latest_pairs[r.pair_id].record_id == r.review_target
    ]
    pair_conflicts = 0
    for pair_review in pair_reviews:
        prior = latest_pairs[pair_review.pair_id]
        fields = ("topic", "event", "story", "occurrence", "coverage")
        if (
            any(getattr(prior.decision, f) != getattr(pair_review.decision, f) for f in fields)
            or pair_review.decision.unresolved_reasons
        ):
            pair_conflicts += 1
    return DatasetStatus(
        source_sha256=manifest.source_sha256,
        total_articles=manifest.articles,
        rows_visited=len(latest),
        annotated=annotated,
        unresolved=unresolved,
        catalog_pending=pending,
        unvisited=manifest.articles - len(latest),
        independently_reviewed=len(
            {r.article_id for r in reviews if latest[r.article_id].record_id == r.review_target}
        ),
        review_conflicts=conflicts,
        history_records=len(by_record) + len(reviews),
        pairs_judged=len(latest_pairs),
        pairs_independently_reviewed=len({r.pair_id for r in pair_reviews}),
        pair_review_conflicts=pair_conflicts,
        vector_covered=covered,
        vector_missing=manifest.articles - covered,
    )
