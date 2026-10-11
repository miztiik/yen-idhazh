"""Can frozen settings produce rankings and clusters without reading gold labels?"""

from __future__ import annotations

from typing import Literal

import numpy as np

from idhazh.contracts.story_candidates import VectorManifest
from idhazh.contracts.story_evaluation import ClusterRun, DevelopmentConfig, Partition, RetrievalRun
from idhazh.story_dataset.storage import Store, digest
from idhazh.story_dataset.vectors import covered_ids, model_matrix, validate_vectors


def freeze_development(store: Store, config: DevelopmentConfig, partition: Partition) -> None:
    if (
        config.partition_sha256 != digest(partition)
        or config.source_sha256 != partition.source_sha256
    ):
        raise ValueError("development settings belong to another fixed partition")
    if not {"development", "confirmation"} <= set(partition.article_partitions.values()):
        raise ValueError("need fresh qualified development and confirmation event groups")
    with store.transaction():
        if store.setting("confirmation-opened"):
            raise ValueError(
                "confirmation was already opened; cannot retrofit development settings"
            )
        store.save("development-config", digest(config), config)


def predict(
    store: Store,
    partition: Partition,
    vectors: VectorManifest,
    config: DevelopmentConfig,
    universe: list[str],
    model: str,
    selected_partition: Literal["development", "confirmation"],
    relation: Literal["topic", "event", "story", "occurrence", "duplicate"],
    k: int,
    cluster: bool = False,
    block_size: int = 32,
) -> RetrievalRun | ClusterRun:
    saved_config = store.get("development-config", digest(config), DevelopmentConfig)
    if saved_config != config or config.partition_sha256 != digest(partition):
        raise ValueError("prediction configuration was not frozen against this partition")
    validate_vectors(vectors, store.root)
    if len(universe) < 2 or len(set(universe)) != len(universe) or k >= len(universe):
        raise ValueError("need distinct candidate articles and k < universe size")
    if any(partition.article_partitions.get(i) != selected_partition for i in universe):
        raise ValueError("candidate universe crosses held-out partitions or quarantine")
    model_ids, matrix = model_matrix(vectors, model, store.root)
    usable = covered_ids(vectors, model)
    valid = {identity: i for i, identity in enumerate(model_ids) if identity in usable}
    if not set(universe) <= valid.keys():
        raise ValueError("prediction universe lacks text-matched vectors")
    cache = next((cache for cache in vectors.caches if cache.slug == model), None)
    if cache is None:
        raise ValueError("unknown saved encoder")
    selected = np.asarray(matrix[[valid[i] for i in universe]], dtype=np.float64)
    selected /= np.linalg.norm(selected, axis=1, keepdims=True)
    common = {
        "source_sha256": vectors.source_sha256,
        "partition_sha256": digest(partition),
        "vector_manifest_sha256": digest(vectors),
        "partition": selected_partition,
        "development_config_sha256": digest(config),
    }
    rankings = {}
    parents = list(range(len(universe)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    threshold = config.parameters.get("cosine_threshold")
    if cluster and (
        not isinstance(threshold, (float, int))
        or isinstance(threshold, bool)
        or not -1 <= threshold <= 1
    ):
        raise ValueError("clustering requires a development-frozen cosine_threshold in [-1,1]")
    for start in range(0, len(universe), block_size):
        scores = selected[start : start + block_size] @ selected.T
        for offset in range(len(scores)):
            index = start + offset
            scores[offset, index] = -np.inf
            if cluster:
                assert isinstance(threshold, (float, int))
                for other in np.flatnonzero(scores[offset] >= threshold):
                    parents[find(index)] = find(int(other))
            else:
                rankings[universe[index]] = [
                    universe[int(i)] for i in np.argsort(-scores[offset], kind="stable")[:k]
                ]
    if selected_partition == "confirmation":
        with store.transaction():
            store.set_setting("confirmation-opened", digest(config))
    if cluster:
        if relation not in ("topic", "event", "story"):
            raise ValueError("cluster evaluation requires an explicit hierarchy level")
        return ClusterRun.model_validate(
            {
                **common,
                "level": relation,
                "model": model,
                "memberships": {
                    identity: ["predicted-component-" + str(find(index))]
                    for index, identity in enumerate(universe)
                },
                "algorithm": "development-frozen-cosine-connected-components",
                "development_config_partition_sha256": digest(partition),
                "parameters_frozen_before_confirmation": True,
            }
        )
    return RetrievalRun.model_validate(
        {
            **common,
            "model": model,
            "relation": relation,
            "k": k,
            "candidate_article_ids": universe,
            "rankings": rankings,
        }
    )
