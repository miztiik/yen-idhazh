"""Summarize human keep labels without mixing them with machine outcomes."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from itertools import combinations
from typing import NamedTuple

from idhazh.contracts.review_queue import ReviewPopulation, ReviewQueue, ReviewRow
from idhazh.contracts.visual_decision import VisualState
from idhazh.contracts.visual_label import VISUAL_LABEL_TYPES, VisualLabel, VisualLabelRow
from idhazh.contracts.visual_type import VisualType


class VisualTypeEvidence(NamedTuple):
    """Machine counts and human evidence for one exact rendered type."""

    visual_type: VisualType
    machine_planned: int
    machine_rendered: int
    reviewed_visuals: int
    human_labels: int
    kept_labels: int
    keep_rate: float | None
    overlap_visuals: int
    agreeing_pairs: int
    reviewer_pairs: int


def collapse_visual_label_rows(
    rows: Iterable[VisualLabelRow],
) -> tuple[VisualLabelRow, ...]:
    """Collapse identical reviewer keys and refuse conflicting judgments."""
    collapsed: dict[tuple[str, str, str], VisualLabelRow] = {}
    for row in rows:
        key = (row.draw_id, row.visual_id, row.reviewer_id)
        previous = collapsed.get(key)
        if previous is None:
            collapsed[key] = row
            continue
        if previous.label is not row.label or previous.queue_position != row.queue_position:
            raise ValueError(
                "one reviewer gave conflicting labels or queue positions for a visual"
            )
    return tuple(collapsed.values())


def index_labelable_visuals(queue: ReviewQueue) -> dict[str, tuple[int, ReviewRow]]:
    """Index the exact published pie and bubble rows in draw order."""
    indexed: dict[str, tuple[int, ReviewRow]] = {}
    for row in queue.rows:
        if (
            row.population is not ReviewPopulation.PUBLISHED
            or row.visual_state is not VisualState.RENDERED
            or row.rendered_type not in VISUAL_LABEL_TYPES
            or row.visual_id is None
        ):
            continue
        if row.visual_id in indexed:
            raise ValueError("the review queue repeats a visual decision identifier")
        indexed[row.visual_id] = (len(indexed) + 1, row)
    return indexed


def summarize_visual_labels(
    queue: ReviewQueue,
    labels: Iterable[VisualLabelRow],
    *,
    draw_id: str,
    reviewer_ids: Sequence[str],
) -> tuple[VisualTypeEvidence, ...]:
    """Report exact-type human rates, requiring measurable reviewer overlap.

    The keep rate is the share of unique reviewer responses marked `keep`.
    Each `(visual, reviewer)` contributes once; repeated identical rows do not
    change the denominator. The raw agreement is pairwise agreement on visuals
    seen by at least two named reviewers.
    """
    if not reviewer_ids:
        raise ValueError("at least one reviewer must be named")
    named_reviewers = set(reviewer_ids)
    if len(named_reviewers) != len(reviewer_ids):
        raise ValueError("reviewer names must be distinct")

    eligible = index_labelable_visuals(queue)
    collapsed = collapse_visual_label_rows(labels)
    by_type: dict[VisualType, list[VisualLabelRow]] = {
        visual_type: [] for visual_type in VISUAL_LABEL_TYPES
    }
    for label in collapsed:
        if label.draw_id != draw_id:
            raise ValueError("a label belongs to a different draw")
        if label.reviewer_id not in named_reviewers:
            raise ValueError("a label belongs to a reviewer not named for this report")
        queue_entry = eligible.get(label.visual_id)
        if queue_entry is None:
            raise ValueError("a label does not join a published pie or bubble row")
        queue_position, queue_row = queue_entry
        if label.queue_position != queue_position:
            raise ValueError("a label queue position does not match the exact draw")
        if queue_row.rendered_type is None:
            raise ValueError("a labelable queue row has no rendered type")
        by_type[queue_row.rendered_type].append(label)

    results: list[VisualTypeEvidence] = []
    for visual_type in VISUAL_LABEL_TYPES:
        planned = sum(row.planned_type is visual_type for row in queue.rows)
        rendered = sum(
            row.population is ReviewPopulation.PUBLISHED
            and row.visual_state is VisualState.RENDERED
            and row.rendered_type is visual_type
            for row in queue.rows
        )
        responses = by_type[visual_type]
        by_visual: dict[str, list[VisualLabelRow]] = {}
        for response in responses:
            by_visual.setdefault(response.visual_id, []).append(response)

        overlap_visuals = 0
        agreeing_pairs = 0
        reviewer_pairs = 0
        for visual_responses in by_visual.values():
            if len(visual_responses) < 2:
                continue
            overlap_visuals += 1
            for left, right in combinations(visual_responses, 2):
                reviewer_pairs += 1
                agreeing_pairs += left.label is right.label

        kept_labels = sum(response.label is VisualLabel.KEEP for response in responses)
        keep_rate = (
            kept_labels / len(responses)
            if responses and overlap_visuals
            else None
        )
        results.append(
            VisualTypeEvidence(
                visual_type=visual_type,
                machine_planned=planned,
                machine_rendered=rendered,
                reviewed_visuals=len(by_visual),
                human_labels=len(responses),
                kept_labels=kept_labels,
                keep_rate=keep_rate,
                overlap_visuals=overlap_visuals,
                agreeing_pairs=agreeing_pairs,
                reviewer_pairs=reviewer_pairs,
            )
        )
    return tuple(results)
