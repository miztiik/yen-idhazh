"""How can every archive pair have a known sampling probability without an all-pairs list?"""

from __future__ import annotations

import math
import random
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

from idhazh.contracts.story_candidates import (
    CandidatePair,
    ChallengeAddition,
    PairFrame,
    VectorManifest,
)
from idhazh.contracts.story_evaluation import StoryPolicy
from idhazh.contracts.story_source import ArticleEvidence, SourceFreeze
from idhazh.story_dataset.storage import digest
from idhazh.story_dataset.vectors import covered_ids, ranked_neighbors


def pair_id(a: str, b: str) -> str:
    if a == b:
        raise ValueError("article cannot be paired with itself")
    return "pair-" + digest(sorted((a, b)))


def sample_indices(population_size: int, probability: float, seed: int) -> list[int]:
    """Geometric gaps are exactly independent Bernoulli draws over the declared frame."""
    if probability <= 0 or probability > 1:
        raise ValueError("probability must be in (0,1]")
    if probability == 1:
        return list(range(population_size))
    rng = random.Random(seed)
    denominator = math.log1p(-probability)
    result: list[int] = []
    index = -1
    while True:
        index += 1 + int(math.log1p(-rng.random()) / denominator)
        if index >= population_size:
            return result
        result.append(index)


def unrank_pair(index: int, ids: list[str], offsets: list[int]) -> tuple[str, str]:
    row = bisect_right(offsets, index) - 1
    return ids[row], ids[row + 1 + index - offsets[row]]


def build_pairs(
    manifest: SourceFreeze,
    articles: dict[str, ArticleEvidence],
    policy: StoryPolicy,
    vectors: VectorManifest | None = None,
    query_ids: list[str] | None = None,
    vector_root: Path | None = None,
) -> PairFrame:
    ids = sorted(articles)
    size = len(ids) * (len(ids) - 1) // 2
    offsets = [i * (2 * len(ids) - i - 1) // 2 for i in range(len(ids) - 1)]
    rows: dict[tuple[str, str], CandidatePair] = {}
    for index in sample_indices(size, policy.representative_pair_probability, policy.seed):
        a, b = unrank_pair(index, ids, offsets)
        rows[(a, b)] = CandidatePair(
            id=pair_id(a, b),
            a=a,
            b=b,
            representative_probability=policy.representative_pair_probability,
        )

    def add(a: str, b: str, tag: str) -> CandidatePair:
        left, right = sorted((a, b))
        key = (left, right)
        row = rows.setdefault(key, CandidatePair(id=pair_id(a, b), a=key[0], b=key[1]))
        if tag not in row.challenge_tags:
            row.challenge_tags.append(tag)
        return row

    # Independent archive-wide metadata discovery includes every uncached row.
    groups: dict[str, list[str]] = defaultdict(list)
    for identity in ids:
        groups[articles[identity].source.domain].append(identity)
    for group in groups.values():
        ordered = sorted(group, key=lambda i: (articles[i].source.first_day, i))
        for index, identity in enumerate(ordered):
            for gap in range(1, policy.metadata_neighbors + 1):
                if index + gap < len(ordered):
                    other = ordered[index + gap]
                    tag = "same-outlet-temporal-baseline"
                    if articles[identity].source.first_day != articles[other].source.first_day:
                        tag = "same-outlet-extended-time-baseline"
                    add(identity, other, tag)
    valid_ids: set[str] = set()
    if vectors:
        if vectors.source_sha256 != manifest.source_sha256:
            raise ValueError("vectors belong to another source")
        valid_ids = covered_ids(vectors)
        queries = query_ids if query_ids is not None else ids
        if not set(queries) <= articles.keys():
            raise ValueError("unknown neighbor query ID")
        union = ranked_neighbors(vectors, queries, policy.top_k, policy.block_size, vector_root)
        all_models = {cache.slug for cache in vectors.caches}
        for (a, b), ranks in union.items():
            row = add(a, b, "encoder-rank-union")
            row.ranks = ranks
            selected_by = {rank.model for rank in ranks}
            if selected_by != all_models:
                add(a, b, "encoder-rank-disagreement")
    for row in rows.values():
        row.missing_vector_articles = [i for i in (row.a, row.b) if i not in valid_ids]
    return PairFrame(
        source_sha256=manifest.source_sha256,
        population="all-unordered-distinct-frozen-archive-articles",
        population_size=size,
        sampling="independent-bernoulli-geometric-skip",
        seed=policy.seed,
        representative_probability=policy.representative_pair_probability,
        pairs=sorted(rows.values(), key=lambda row: row.id),
        vector_manifest_sha256=digest(vectors) if vectors else None,
    )


def add_challenges(
    frame: PairFrame,
    addition: ChallengeAddition,
    articles: dict[str, ArticleEvidence],
    vectors: VectorManifest | None,
) -> PairFrame:
    """Operator/source-backed candidates add acquisition evidence, never labels."""
    if addition.source_sha256 != frame.source_sha256 or addition.expected_frame_sha256 != digest(
        frame
    ):
        raise ValueError("challenge addition belongs to another source/frame revision")
    rows = {row.id: row.model_copy(deep=True) for row in frame.pairs}
    usable = covered_ids(vectors) if vectors else set()
    for proposal in addition.proposals:
        if proposal.a not in articles or proposal.b not in articles:
            raise ValueError("challenge contains foreign article IDs")
        identity = pair_id(proposal.a, proposal.b)
        if "source-backed-extended-time" in proposal.tags and not any(
            check.state in ("read", "redirect") for check in proposal.source_checks
        ):
            raise ValueError("source-backed acquisition needs actual source-check evidence")
        a, b = sorted((proposal.a, proposal.b))
        row = rows.setdefault(identity, CandidatePair(id=identity, a=a, b=b))
        row.challenge_tags = sorted(set(row.challenge_tags) | set(proposal.tags))
        if proposal.reason not in row.acquisition_notes:
            row.acquisition_notes.append(proposal.reason)
        row.source_checks.extend(
            check for check in proposal.source_checks if check not in row.source_checks
        )
        row.missing_vector_articles = [i for i in (a, b) if i not in usable]
    return frame.model_copy(update={"pairs": sorted(rows.values(), key=lambda row: row.id)})
