"""Judged pair rows for the tests that read a night's pairs.

A row is built through the contract, in the slice the committed draw would have cut for its
score, so every check the contract makes on a bucket, a slice and a score is the one that
runs. The file-level builders at the end write what a unit leaves behind, in the contract's
own columns.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Sequence
from typing import Any, Final

from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.base import ServerJob, derive_text_digest, derive_url_key
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.story_similarity_pair_verdict import (
    JUDGE_POLICY_VERSION,
    StorySimilarityPairVerdict,
)
from idhazh.similarity.sampling_chance import with_sampling_chance
from idhazh.similarity.slices import slice_grid
from support.ledger import SEED_COMMIT
from support.paths import CONFIG_DIR

DATE: Final = "2026-11-18"

#: The committed config's own draw, so a row lands in the slice the draw would give it.
DRAW: Final = judge_settings.load(CONFIG_DIR).draw

#: The committed config's revision dates, as the nights of these tests read them.
CONFIG_VERSIONS: Final = judge_settings.config_versions(CONFIG_DIR)


def a_night_of_pairs(
    pairs: Sequence[tuple[float, str | tuple[str, str]]],
    *,
    date: str = DATE,
    run_id: str | None = None,
    lower: float = 0.7,
    upper: float = 0.93,
    first_index: int = 0,
    pool_factor: int = 3,
    answered: bool = True,
    **cells: Any,
) -> list[StorySimilarityPairVerdict]:
    """A night's rows for `pairs`, each a score and the answer to it, as the collecting job files them.

    The draw judged every pair here, and every slice held `pool_factor` times as many pairs
    as the draw took from it, so each row names the counts of its own slice and the sampling
    chance is filled in the way the filing stage fills it. `first_index` keeps the pairs of
    one night from being the pairs of another. With `answered` false the rows are the draw
    file's: the same pairs and slices, no answer and no chance yet.
    """
    grid = slice_grid(lower, upper, draw=DRAW)
    held = Counter(grid.index_of(max(-1.0, min(1.0, score))) for score, _ in pairs)
    rows = [
        a_judged_pair(
            first_index + step,
            score=score,
            answer=answer if answered else None,
            date=date,
            run_id=run_id,
            lower=lower,
            upper=upper,
            available=pool_factor * held[grid.index_of(max(-1.0, min(1.0, score)))],
            judged=held[grid.index_of(max(-1.0, min(1.0, score)))],
            **cells,
        )
        for step, (score, answer) in enumerate(pairs)
    ]
    return with_sampling_chance(rows) if answered else rows


def a_judged_pair(
    index: int,
    *,
    score: float,
    answer: str | tuple[str, str] | None = "YES",
    date: str = DATE,
    run_id: str | None = None,
    lower: float = 0.7,
    upper: float = 0.93,
    available: int = 10,
    judged: int = 4,
    shard: int = 0,
    pair: int | None = None,
    **cells: Any,
) -> StorySimilarityPairVerdict:
    """One judged pair at `score`, in the slice thresholds `lower` and `upper` would cut for it.

    `answer` is the word both readings gave, or the two words when they differ, which makes
    the pair unusable, or none for a pair the draw took and no unit has read. `pair` names the
    pair the row is about when it is not `index`, so two rows of one pair - a re-run - share
    their address keys. `cells` replaces any cell of the row, which is how a test changes the
    judge, the prompt or the scorer.
    """
    grid = slice_grid(lower, upper, draw=DRAW)
    one = grid.slices[grid.index_of(max(-1.0, min(1.0, score)))]
    name = index if pair is None else pair
    left, right = sorted(
        (derive_url_key(f"https://left.example/{name}"), derive_url_key(f"https://right.example/{name}"))
    )
    raw: dict[str, Any] = {
        "date": date,
        "run_id": run_id or f"{date}-9",
        "work_part_index": shard,
        "pair_key": derive_text_digest(left + right),
        "left_url_key": left,
        "right_url_key": right,
        "similarity_score": score,
        "cosine": score,
        "headline": False,
        "scorer_model": "all-minilm-l6-v2-quantized",
        "cosine_weight": 1.0,
        "bucket": one.bucket,
        "slice_low": one.low,
        "slice_high": one.high,
        "slice_pairs_available": available,
        "slice_pairs_judged": judged,
        "lower_threshold_in_force": lower,
        "upper_threshold_in_force": upper,
        "config_versions": CONFIG_VERSIONS,
    }
    if answer is not None:
        forward, swapped = (answer, answer) if isinstance(answer, str) else answer
        raw |= {
            "verdict": forward,
            "verdict_swapped": swapped,
            "readings_agree": forward == swapped,
            "judge_model": "qwen3-5-9b-q4-k-m",
            "prompt_digest": "a" * 64,
            "grammar_digest": "b" * 64,
            "judge_temperature": 0.0,
            "thinking_spans": 0,
            "grammar_applied": True,
            "judge_policy_version": JUDGE_POLICY_VERSION,
        }
    return StorySimilarityPairVerdict.model_validate(raw | cells)


def a_verdict_file(rows: Sequence[StorySimilarityPairVerdict]) -> str:
    """What a unit leaves behind, or the draw file the planning job writes: rows in the contract's columns."""
    out = io.StringIO()
    writer = csv.DictWriter(
        out, fieldnames=StorySimilarityPairVerdict.csv_columns(), lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row.csv_row())
    return out.getvalue()


def a_reading(*, shard: int, dealt: int, date: str, run_id: str) -> ContentSimilarityJudgeMetrics:
    """One unit's reading of its own instrument, with a funnel that closes."""
    return ContentSimilarityJudgeMetrics.model_validate(
        {
            "date": date,
            "run_id": run_id,
            "work_part_index": shard,
            "pairs_dealt": dealt,
            "pairs_read": dealt,
            "pairs_agreed": dealt,
            "pairs_unreadable": 0,
            "pairs_refused": 0,
            "pairs_abandoned": 0,
            "disagreement_rate": 0.0,
            "unclear_rate": 0.0,
            "first_token_margin_median": 0.5,
            "decode_seconds_total": 3.5 + shard,
            "decode_seconds_max": 2.0,
        }
    )


def a_saver(run_id: str) -> WriterIdentity:
    """The writer the council hands a tenant: the job that saves the night's results."""
    return WriterIdentity(
        run_id=run_id,
        attempt=1,
        job=ServerJob.SAVE_COUNCIL_RESULTS,
        shard=0,
        producer="council.session",
        git_sha=SEED_COMMIT,
    )
