"""How does each requested stage consume and persist its named typed artifacts?"""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import TypeAdapter

from idhazh.contracts.story_annotation import (
    AnnotationRecord,
    CatalogReview,
    CatalogSnapshot,
    DatasetCheckpoint,
    WorkerBatch,
    WorkerSubmission,
)
from idhazh.contracts.story_candidate_evaluation import CandidateEvaluationSnapshot
from idhazh.contracts.story_candidates import (
    ChallengeAddition,
    PairFrame,
    PairRecord,
    PairSubmission,
    PairWorkerBatch,
    VectorExtension,
    VectorManifest,
)
from idhazh.contracts.story_evaluation import (
    ClusterRun,
    DevelopmentConfig,
    EvaluationReport,
    Partition,
    RetrievalRun,
    StoryPolicy,
)
from idhazh.contracts.story_source import SourceFreeze
from idhazh.contracts.story_vector_derivation import DerivedVectorSnapshot
from idhazh.contracts.story_vectors import VectorExtensionSnapshot, VectorSnapshot
from idhazh.story_dataset.catalog import read_catalog, review_catalog
from idhazh.story_dataset.checkpoints import export_checkpoint, restore_checkpoint
from idhazh.story_dataset.encoding import encode_selected
from idhazh.story_dataset.evaluation import evaluate
from idhazh.story_dataset.pair_workers import export_pairs, import_pairs
from idhazh.story_dataset.partitions import build_partition
from idhazh.story_dataset.predictions import freeze_development, predict
from idhazh.story_dataset.sampling import add_challenges, build_pairs
from idhazh.story_dataset.source import article_id, freeze, load_policy, validate_freeze
from idhazh.story_dataset.status import dataset_status
from idhazh.story_dataset.storage import Store, canonical, digest, read_model, write_model
from idhazh.story_dataset.vector_files import read_vectors, relocate_vectors
from idhazh.story_dataset.vectors import register_extension, register_vectors
from idhazh.story_dataset.workers import export_batch, import_submission
from utilities.record_encoder_judgments import read_frame, read_judgments


def ids(path: Path | None) -> list[str] | None:
    return TypeAdapter(list[str]).validate_json(path.read_bytes()) if path else None


def write_batch(store: Store, batch: WorkerBatch, output: Path) -> None:
    write_model(output, batch)
    write_model(
        output.with_suffix(".catalog.json"),
        store.get("catalog", batch.catalog_revision, CatalogSnapshot),
    )


def execute(args: argparse.Namespace) -> None:
    repository = Path(args.repository).resolve()
    root = Path(args.root).resolve()
    policy = load_policy(args.policy)
    if args.command == "freeze":
        print(freeze(root, repository, policy, args.examples).model_dump_json(indent=2))
        return
    if args.command == "schema":
        args.output.mkdir(parents=True, exist_ok=True)
        for model in (
            SourceFreeze,
            WorkerBatch,
            WorkerSubmission,
            CatalogSnapshot,
            CatalogReview,
            DatasetCheckpoint,
            PairFrame,
            PairWorkerBatch,
            PairSubmission,
            VectorManifest,
            VectorSnapshot,
            Partition,
            RetrievalRun,
            ClusterRun,
            EvaluationReport,
            StoryPolicy,
            VectorExtension,
            VectorExtensionSnapshot,
            DevelopmentConfig,
            ChallengeAddition,
        ):
            (args.output / (model.__name__ + ".json")).write_bytes(
                canonical(model.model_json_schema())
            )
        return
    manifest, articles = validate_freeze(root, repository, policy)
    if args.command == "checkpoint":
        print(export_checkpoint(root, args.output, manifest, policy).model_dump_json(indent=2))
        return
    store = Store(root)
    try:
        if args.command == "restore-checkpoint":
            restore_checkpoint(store, args.input, manifest, policy)
            print("restored immutable checkpoint into an empty local index")
            return
        if store.setting("source") != manifest.source_sha256:
            raise ValueError("local state is not initialized against this freeze")
        command = args.command
        if command == "status":
            print(dataset_status(store, manifest).model_dump_json(indent=2))
        elif command == "resume":
            resumed = store.get("batch", args.batch_id, WorkerBatch)
            write_model(args.output, resumed)
            write_model(
                args.output.with_suffix(".catalog.json"),
                store.get(
                    "catalog",
                    resumed.catalog_revision,
                    CatalogSnapshot,
                ),
            )
        elif command == "export":
            batch = export_batch(store, manifest, articles, policy, args.operation, ids(args.ids))
            # Catalog definitions are separate, never acquisition ranks/groups in the article view.
            write_batch(store, batch, args.output)
            print(
                f"exported {len(batch.articles)} {batch.operation} articles; batch {batch.batch_id}"
            )
        elif command == "import":
            count = import_submission(
                store, manifest, articles, read_model(args.input, WorkerSubmission)
            )
            print(f"appended {count} model article records")
        elif command == "catalog":
            write_model(args.output, read_catalog(store))
        elif command == "catalog-review":
            catalog_result = review_catalog(
                store, read_model(args.input, CatalogReview), set(articles)
            )
            print(
                f"catalog revision {catalog_result.revision}; "
                f"{len(catalog_result.entities)} explicit identities"
            )
        elif command == "vectors":
            vector_result = register_vectors(
                store,
                manifest,
                articles,
                repository / "corpus" / "encoder-comparison-1" / "pairs.json",
                repository / "corpus" / "encoder-comparison-1" / "readings" / "encoders.json",
                {
                    slug: args.vector_root / filename
                    for slug, filename in policy.vector_files.items()
                },
                repository / "config" / "encoder-comparison.json",
            )
            write_model(args.output, vector_result)
            print(
                f"{len(vector_result.article_ids)} cached URLs; "
                f"{len(vector_result.missing_article_ids)} missing; "
                f"{len(vector_result.text_conflict_article_ids)} text conflicts excluded"
            )
        elif command == "relocate-vectors":
            replacements: dict[str, Path] = {}
            for item in args.file:
                sha256, separator, path = item.partition("=")
                if not separator or not path or sha256 in replacements:
                    raise ValueError("each --file must be a distinct SHA256=PATH mapping")
                replacements[sha256] = Path(path)
            relocated = relocate_vectors(store, args.expected_revision, replacements, args.output)
            print(f"portable vector revision {digest(relocated)}; no input or vector bytes changed")
        elif command == "pairs":
            revision = store.setting("vectors")
            vectors = read_vectors(store, revision) if revision and not args.metadata_only else None
            pair_result = build_pairs(
                manifest, articles, policy, vectors, ids(args.queries), store.root
            )
            with store.transaction():
                store.save("pair-frame", digest(pair_result), pair_result)
                store.set_setting("pair-frame", digest(pair_result))
            write_model(args.output, pair_result)
            representative = sum(
                row.representative_probability is not None for row in pair_result.pairs
            )
            challenge = sum(bool(row.challenge_tags) for row in pair_result.pairs)
            print(f"{representative} representative; {challenge} challenge; streams may overlap")
        elif command == "pair-add":
            vector_id = store.setting("vectors")
            vector_manifest = read_vectors(store, vector_id) if vector_id else None
            extended_frame = add_challenges(
                read_model(args.frame, PairFrame),
                read_model(args.input, ChallengeAddition),
                articles,
                vector_manifest,
            )
            with store.transaction():
                store.save("pair-frame", digest(extended_frame), extended_frame)
                store.set_setting("pair-frame", digest(extended_frame))
            write_model(args.output, extended_frame)
        elif command == "pair-export":
            pair_batch = export_pairs(
                store,
                read_model(args.frame, PairFrame),
                articles,
                policy.batch_size,
                ids(args.ids),
                args.operation,
                policy.random_audit_fraction,
                policy.seed,
            )
            write_model(args.output, pair_batch)
        elif command == "pair-import":
            print(
                "appended "
                f"{import_pairs(store, read_model(args.input, PairSubmission))} pair records"
            )
        elif command == "split":
            old_path = repository / "corpus" / "encoder-comparison-1" / "judgments"
            regression, regression_hash = read_frame(old_path / "pairs.json")
            read_judgments(old_path / "verdicts.jsonl", regression, regression_hash)
            regression_ids = {
                article_id(article.url) for pair in regression.rows for article in (pair.a, pair.b)
            }
            previous = read_model(args.previous, Partition) if args.previous else None
            current = store.setting("partition")
            if current and previous is None:
                previous = store.get("partition", current, Partition)
            partition_result = build_partition(
                store,
                manifest,
                set(articles),
                policy,
                regression_ids,
                read_model(args.frame, PairFrame) if args.frame else None,
                previous,
            )
            write_model(args.output, partition_result)
            print(f"partition fixed; {len(partition_result.blocked_reasons)} blockers")
        elif command == "evaluate":
            split_id, vector_id = store.setting("partition"), store.setting("vectors")
            report_result = evaluate(
                store,
                manifest,
                store.get("partition", split_id, Partition) if split_id else None,
                read_model(args.vectors, TypeAdapter(
                    CandidateEvaluationSnapshot | DerivedVectorSnapshot | VectorSnapshot
                ))
                if args.vectors else (read_vectors(store, vector_id) if vector_id else None),
                read_model(args.frame, PairFrame) if args.frame else None,
                read_model(args.retrieval, RetrievalRun) if args.retrieval else None,
                read_model(args.clusters, ClusterRun) if args.clusters else None,
            )
            write_model(args.output, report_result)
            print(report_result.model_dump_json(indent=2))
        elif command == "history":
            # Each line is one declared record, in append order; no old record is rewritten.
            args.output.mkdir(parents=True, exist_ok=True)
            for kind, record_model in (
                ("annotation", AnnotationRecord),
                ("review", AnnotationRecord),
                ("pair", PairRecord),
                ("pair-review", PairRecord),
                ("catalog-review", CatalogReview),
            ):
                path = args.output / (kind + ".jsonl")
                raw = b"".join(canonical(row) for row in store.records(kind, record_model))
                path.write_bytes(raw)
            print("exported actual immutable history records")
        elif command == "freeze-development":
            partition_id = store.setting("partition")
            if partition_id is None:
                raise ValueError("fix a partition before freezing development settings")
            freeze_development(
                store,
                read_model(args.input, DevelopmentConfig),
                store.get("partition", partition_id, Partition),
            )
        elif command in ("predict", "encode", "vector-import"):
            vector_id = store.setting("vectors")
            if vector_id is None:
                raise ValueError("register saved vectors first")
            vector_manifest = read_vectors(store, vector_id)
            if command == "predict" and args.vectors:
                vector_manifest = read_model(
                    args.vectors, TypeAdapter(
                        CandidateEvaluationSnapshot | DerivedVectorSnapshot | VectorSnapshot
                    )
                )
            if command == "vector-import":
                extended = register_extension(
                    store,
                    vector_manifest,
                    articles,
                    read_model(args.input, TypeAdapter(VectorExtensionSnapshot | VectorExtension)),
                )
                write_model(args.output, extended)
            elif command == "encode":
                extension_result = encode_selected(
                    articles,
                    vector_manifest,
                    ids(args.ids) or [],
                    args.model,
                    policy,
                    args.output,
                    store.root,
                )
                print(extension_result.model_dump_json(indent=2))
            else:
                partition_id = store.setting("partition")
                if partition_id is None:
                    raise ValueError("fix a partition before prediction")
                predicted = predict(
                    store,
                    store.get("partition", partition_id, Partition),
                    vector_manifest,
                    read_model(args.config, DevelopmentConfig),
                    ids(args.ids) or [],
                    args.model,
                    args.partition,
                    args.relation,
                    policy.top_k,
                    cluster=args.cluster,
                    block_size=policy.block_size,
                )
                write_model(args.output, predicted)
        else:
            raise ValueError(f"unknown command: {command}")
    finally:
        store.close()
