"""Which unique judged pairs have unchanged saved inputs and disjoint articles?"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from idhazh.contracts.encoder_evaluation import CoverageAudit, Partition, RepeatAudit, SplitAudit
from idhazh.contracts.encoder_judgment import (
    EncoderJudgment,
    JudgmentFrame,
    JudgmentPair,
    PairVerdict,
)


@dataclass(frozen=True)
class EligiblePair:
    pair: JudgmentPair
    aliases: tuple[str, ...]
    left: int
    right: int
    label: int


def audit_pairs(
    frame: JudgmentFrame,
    judgments: list[EncoderJudgment],
    urls: list[str],
    texts: list[str],
    expected: int,
) -> tuple[CoverageAudit, list[EligiblePair]]:
    """Keep unanimous binary identities only; never replace or vote on a verdict."""
    if len(frame.rows) != expected:
        raise ValueError(f"expected {expected} frame rows, found {len(frame.rows)}")
    ids = {pair.id for pair in frame.rows}
    recorded = [judgment.pair_id for judgment in judgments]
    if len(recorded) != len(set(recorded)):
        raise ValueError(
            "evaluation requires one initial judgment per id; corrections need a policy"
        )
    if set(recorded) != ids:
        raise ValueError(
            f"judgment coverage differs: missing {sorted(ids - set(recorded))}, "
            f"unknown {sorted(set(recorded) - ids)}"
        )
    if any(
        record.label_source != "model" or record.human_verdict is not None for record in judgments
    ):
        raise ValueError("this report requires model-only judgments with zero human review")
    if len(urls) != len(texts) or len(set(urls)) != len(urls):
        raise ValueError("encoded urls must be unique and have one summary each")
    slots = {url: index for index, url in enumerate(urls)}
    decisions = {record.pair_id: record.verdict for record in judgments}
    grouped: dict[tuple[str, ...], list[JudgmentPair]] = defaultdict(list)
    missing: set[str] = set()
    changed: set[str] = set()
    for pair in frame.rows:
        if pair.a.url == pair.b.url:
            raise ValueError(f"{pair.id}: a pair cannot compare an article with itself")
        grouped[tuple(sorted((pair.a.url, pair.b.url)))].append(pair)
        for article in (pair.a, pair.b):
            if article.url not in slots:
                missing.add(pair.id)
            elif article.summary != texts[slots[article.url]]:
                changed.add(pair.id)

    eligible: list[EligiblePair] = []
    repeats: list[RepeatAudit] = []
    duplicate_ids: list[str] = []
    excluded: dict[str, list[str]] = {
        "conflicting_repeat": [], "cannot_tell": [], "missing_vector": [], "changed_summary": [],
    }
    for pairs in sorted(grouped.values(), key=lambda rows: min(row.id for row in rows)):
        pairs.sort(key=lambda pair: pair.id)
        first = pairs[0]
        verdicts = {decisions[pair.id] for pair in pairs}
        if len(pairs) > 1:
            repeats.append(RepeatAudit(
                pair_ids=[pair.id for pair in pairs],
                verdicts={pair.id: decisions[pair.id] for pair in pairs},
                agreement=len(verdicts) == 1,
                reversed_ids=[
                    pair.id for pair in pairs[1:]
                    if (pair.a.url, pair.b.url) == (first.b.url, first.a.url)
                ],
            ))
        # Reasons are mutually exclusive at unique-pair level, in this priority order.
        if len(verdicts) > 1:
            excluded["conflicting_repeat"].append(first.id)
        elif PairVerdict.CANNOT_TELL in verdicts:
            excluded["cannot_tell"].append(first.id)
        elif any(pair.id in missing for pair in pairs):
            excluded["missing_vector"].append(first.id)
        elif any(pair.id in changed for pair in pairs):
            excluded["changed_summary"].append(first.id)
        else:
            eligible.append(EligiblePair(
                pair=first, aliases=tuple(pair.id for pair in pairs),
                left=slots[first.a.url], right=slots[first.b.url],
                label=int(decisions[first.id] == PairVerdict.SAME),
            ))
            duplicate_ids.extend(pair.id for pair in pairs[1:])
    if not eligible:
        raise ValueError("no eligible unique binary pairs after coverage and consistency audit")
    return CoverageAudit(
        judged_ids=sorted(ids),
        verdict_counts=dict(Counter(decisions.values())),
        selection_strata=dict(sorted(Counter(pair.group for pair in frame.rows).items())),
        unique_pairs=len(grouped),
        repeated_rows=len(frame.rows) - len(grouped),
        repeats=repeats,
        cannot_tell_ids=sorted(
            pair_id for pair_id, verdict in decisions.items() if verdict == PairVerdict.CANNOT_TELL
        ),
        missing_vector_ids=sorted(missing),
        changed_summary_ids=sorted(changed),
        url_covered_rows=len(frame.rows) - len(missing),
        exact_text_covered_rows=len(frame.rows) - len(missing | changed),
        excluded_unique_ids=excluded,
        removed_duplicate_ids=sorted(duplicate_ids),
        eligible_ids=[item.pair.id for item in eligible],
        eligible_strata=dict(sorted(Counter(item.pair.group for item in eligible).items())),
    ), eligible


def split_components(
    frame: JudgmentFrame, eligible: list[EligiblePair], fraction: float, seed: int,
) -> tuple[SplitAudit, list[str]]:
    """Connect the entire frame, including uncertain, conflicting and uncovered links."""
    urls = sorted({article.url for pair in frame.rows for article in (pair.a, pair.b)})
    slots = {url: index for index, url in enumerate(urls)}
    left = [slots[pair.a.url] for pair in frame.rows]
    right = [slots[pair.b.url] for pair in frame.rows]
    graph = coo_matrix(
        (np.ones(len(left)), (left, right)), shape=(len(urls), len(urls)),
    ).tocsr()
    count, labels = connected_components(graph, directed=False)
    component_of = {
        url: f"c{int(label):04d}" for url, label in zip(urls, labels, strict=True)
    }
    pair_components = [component_of[item.pair.a.url] for item in eligible]
    active = sorted(set(pair_components))
    take = math.ceil(len(active) * fraction)
    if not 0 < fraction < 1 or len(active) < 2 or take >= len(active):
        raise ValueError(
            f"article-disjoint split blocked: {len(active)} active components, "
            f"{take} requested for calibration"
        )
    drawn = np.random.default_rng(seed).permutation(len(active))[:take]
    calibration = {active[int(index)] for index in drawn}
    held_out = set(active) - calibration

    def partition(components: set[str], name: str) -> Partition:
        members = [
            item for item, component in zip(eligible, pair_components, strict=True)
            if component in components
        ]
        same = sum(item.label for item in members)
        different = len(members) - same
        if same == 0 or different == 0:
            raise ValueError(
                f"{name} class coverage blocked: {len(components)} components, "
                f"{len(members)} pairs, {same} same, {different} different; no split retries"
            )
        return Partition(
            component_ids=sorted(components),
            pair_ids=[item.pair.id for item in members],
            articles=sum(component in components for component in component_of.values()),
            eligible_articles=len({
                article.url for item in members for article in (item.pair.a, item.pair.b)
            }),
            same=same, different=different, prevalence=same / len(members),
        )

    calibration_articles = {url for url, group in component_of.items() if group in calibration}
    held_articles = {url for url, group in component_of.items() if group in held_out}
    if calibration_articles & held_articles:
        raise ValueError("article-disjoint component split shares articles")
    return SplitAudit(
        method="all-frame article-connected components",
        total_components=int(count), active_components=len(active),
        excluded_only_components=int(count) - len(active), frame_articles=len(urls),
        shared_articles=0,
        calibration=partition(calibration, "calibration"),
        held_out=partition(held_out, "held-out"),
    ), pair_components
