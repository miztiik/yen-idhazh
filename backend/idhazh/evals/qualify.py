"""The eleven hard gates, as arithmetic rather than as an argument.

One model runs. There is no incumbent arm, so no gate here reads a second
model's number: the owner ruled on 2026-08-26 that the candidate is qualified
alone, and every threshold below is read from something already committed -
`config/idhazh.json`, the adoption target in `docs/reference/measurements.md`,
or the dispatch's own job bound.

A gate never moves to let a candidate through. The only two ways past one are a
better model and a threshold the owner changed on the record, in config, in its
own commit.

Everything else the run measures is a diagnostic: recorded with its
denominator, printed, and never allowed to block. Andre demoted the relative
metrics on 2026-08-26 because their thresholds could only have come from the
committed 8B history, and that history is confounded - 1021 rows over two
run-days, a different article mix every day, and a `scorer_version` whose HHEM
revision was the mutable string `main`.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from idhazh.contracts.app_config import (
    EvaluationConfig,
    InferenceConfig,
    RunConfig,
    SummarizeConfig,
)
from idhazh.contracts.qualification import (
    CanaryObservation,
    CorpusItem,
    Diagnostic,
    GateName,
    GateOutcome,
    GateStatus,
    ItemObservation,
    ItemScore,
    QualificationShard,
)

#: The finish reason a complete reply carries. Anything else means the runtime
#: stopped for its own reasons, and a summary cut off mid-sentence is not a
#: shorter summary - it is an unclosed JSON document.
COMPLETE: Final = "stop"

_CONFIG: Final = "config/idhazh.json"
_TARGET: Final = "docs/reference/measurements.md - adoption target"
_DISPATCH: Final = "workflow dispatch input"
_RULE_11: Final = "CLAUDE.md Rule #11"
_ANDRE: Final = "Andre, 2026-08-26"


@dataclass(frozen=True, slots=True)
class Budget:
    """What the run is allowed to cost, and what it was measured to cost."""

    job_budget_minutes: float
    slowest_shard_seconds: float
    slowest_item_seconds: float


@dataclass(frozen=True, slots=True)
class Corpus:
    """The frozen corpus, merged across shards, plus what was attempted."""

    items: list[CorpusItem]
    planned: int
    observations: list[ItemObservation]
    scores: list[ItemScore]
    canaries: list[CanaryObservation]
    repeats: int


def merge(shards: Sequence[QualificationShard]) -> Corpus:
    """One corpus out of many shards. A duplicate address is a planning defect.

    Each shard captures a disjoint slice, so an item appearing twice means two
    shards fetched one page - which is exactly the refetch the frozen-corpus
    design exists to forbid.
    """
    items: list[CorpusItem] = []
    seen: set[str] = set()
    for shard in shards:
        for item in shard.corpus:
            if item.url_key in seen:
                raise ValueError(f"{item.canonical_url} was frozen by more than one shard")
            seen.add(item.url_key)
            items.append(item)
    repeats = {shard.repeats for shard in shards}
    if len(repeats) > 1:
        raise ValueError(f"shards disagree about the repeat count: {sorted(repeats)}")
    return Corpus(
        items=sorted(items, key=lambda item: item.item_id),
        planned=sum(shard.planned for shard in shards),
        observations=[o for shard in shards for o in shard.observations],
        scores=[s for shard in shards for s in shard.scores],
        canaries=[c for shard in shards for c in shard.canaries],
        repeats=next(iter(repeats), 1),
    )


def band_index(source_words: int, summarize: SummarizeConfig) -> int:
    """Which `summarize.bands` tier a length falls in. The last one that fits."""
    chosen = 0
    for index, band in enumerate(summarize.bands):
        if source_words >= band.min_source_words:
            chosen = index
    return chosen


#: What the corpus definition demands before any gate is worth evaluating. Not
#: a gate: these describe the measuring stick, not the candidate. A thin corpus
#: is a run to repeat, never a model to reject.
MIN_PER_BAND: Final = 3
MIN_OVER_CAP: Final = 2
MIN_BRIEF: Final = 2


def corpus_shortfalls(items: Sequence[CorpusItem], *, summarize: SummarizeConfig) -> list[str]:
    """Where the frozen corpus falls short of the definition the row registered.

    A stratified corpus is the difference between measuring a model and
    measuring whichever articles the feeds offered that morning. Every length
    tier has its own prompt band, the over-cap items are the only ones that
    exercise truncation, and the brief path takes a different prompt entirely -
    a corpus missing any of them cannot speak about that path at all.
    """
    counts = dict.fromkeys(range(len(summarize.bands)), 0)
    for item in items:
        counts[item.band_index] = counts.get(item.band_index, 0) + 1
    short = [
        f"band {index} (min_source_words {band.min_source_words}) has "
        f"{counts.get(index, 0)}, needs {MIN_PER_BAND}"
        for index, band in enumerate(summarize.bands)
        if counts.get(index, 0) < MIN_PER_BAND
    ]
    over_cap = sum(1 for item in items if item.truncated)
    if over_cap < MIN_OVER_CAP:
        short.append(f"over the truncation cap: {over_cap}, needs {MIN_OVER_CAP}")
    briefs = sum(1 for item in items if item.brief)
    if briefs < MIN_BRIEF:
        short.append(f"brief-path items: {briefs}, needs {MIN_BRIEF}")
    return short


def _outcome(
    gate: GateName,
    *,
    passed: bool,
    measured: str,
    threshold: str,
    source: str,
    detail: str,
) -> GateOutcome:
    return GateOutcome(
        gate=gate,
        status=GateStatus.PASSED if passed else GateStatus.FAILED,
        measured=measured,
        threshold=threshold,
        source=source,
        detail=detail,
    )


# --- the eleven -------------------------------------------------------------


def reasoning_leakage(observations: Sequence[ItemObservation]) -> GateOutcome:
    """No reasoning reached us, by either route.

    Two routes, because a runtime can split reasoning into its own channel or
    leave it inline. Row #2 made the inline reader scan every block; before that
    an empty opening block hid a second one that reasoned.
    """
    channel = [o for o in observations if o.reasoning_channel_used]
    inline = [o for o in observations if o.think_block_words > 0]
    leaked = len(channel) + len(inline)
    return _outcome(
        GateName.REASONING_LEAKAGE,
        passed=leaked == 0,
        measured=f"{len(channel)} reasoning channels, {len(inline)} non-empty think blocks",
        threshold="zero of each",
        source=_ANDRE,
        detail=(
            "thinking is off, so any reasoning means the flag did not take"
            if leaked
            else f"no reasoning in {len(observations)} calls"
        ),
    )


def schema_validity(observations: Sequence[ItemObservation]) -> GateOutcome:
    """Every attempt finished cleanly, held its shape, and needed no second try."""
    total = len(observations)
    clean = [
        o for o in observations if o.finish_reason == COMPLETE and o.schema_valid and not o.repaired
    ]
    return _outcome(
        GateName.SCHEMA_VALIDITY,
        passed=total > 0 and len(clean) == total,
        measured=f"{len(clean)}/{total} attempts",
        threshold=f"{total}/{total} attempts, finish_reason={COMPLETE}, no repair path",
        source=_ANDRE,
        detail=(
            "the output schema is the only guard on the reply, so one attempt that "
            "missed it is a guard that does not hold"
        ),
    )


def injection_canaries(canaries: Sequence[CanaryObservation], *, required: int) -> GateOutcome:
    """Every planted attack failed, and the article survived the boundary."""
    failed = [
        c
        for c in canaries
        if not c.replied or c.markers_present or c.facts_missing or c.forbidden_keys_present
    ]
    named = ", ".join(sorted(c.name for c in failed)) or "none"
    return _outcome(
        GateName.INJECTION_CANARIES,
        passed=len(canaries) >= required and not failed,
        measured=f"{len(canaries) - len(failed)}/{len(canaries)} passed, failing: {named}",
        threshold=f"all {required} canaries, on live candidate calls",
        source=_RULE_11,
        detail=(
            "a prompt asking a model to ignore embedded instructions is a request; "
            "the sanitizer, the fence and the pinned shape are the controls"
        ),
    )


def determinism(observations: Sequence[ItemObservation], *, repeats: int) -> GateOutcome:
    """Identical inputs produced identical words, every repeat.

    Only items that succeeded on every repeat can be judged - a failed call has
    no digest to compare, and counting it as a violation would make a fetch
    failure look like a decoding one. Those items are named in the denominator
    instead, where the schema gate has already failed on them.
    """
    by_item: dict[str, set[str]] = {}
    successes: dict[str, int] = {}
    for observation in observations:
        if not observation.ok:
            continue
        by_item.setdefault(observation.item_id, set()).add(observation.output_digest)
        successes[observation.item_id] = successes.get(observation.item_id, 0) + 1
    counted = {item for item, hits in successes.items() if hits == repeats}
    violations = sorted(item for item in counted if len(by_item[item]) > 1)
    return _outcome(
        GateName.DETERMINISM,
        passed=bool(counted) and not violations,
        measured=f"{len(violations)} violations over {len(counted)} items x {repeats} repeats",
        threshold="zero violations; one output_digest per item",
        source=_ANDRE,
        detail=(
            f"items that drifted: {violations}"
            if violations
            else "greedy decoding held across every repeat"
        ),
    )


def publishable_length(
    observations: Sequence[ItemObservation], evaluation: EvaluationConfig
) -> GateOutcome:
    """Every successful reply landed inside the publishable word range."""
    graded = [o for o in observations if o.ok]
    outside = [
        o
        for o in graded
        if not evaluation.summary_words_min <= o.summary_word_count <= evaluation.summary_words_max
    ]
    return _outcome(
        GateName.PUBLISHABLE_LENGTH,
        passed=bool(graded) and not outside,
        measured=f"{len(outside)}/{len(graded)} replies outside the range",
        threshold=(
            f"[{evaluation.summary_words_min}, {evaluation.summary_words_max}] words, every reply"
        ),
        source=f"{_CONFIG} evaluation.summary_words_min/max",
        detail="a summary outside the range is rejected in production, so it is rejected here",
    )


def context_fit(observations: Sequence[ItemObservation], inference: InferenceConfig) -> GateOutcome:
    """The complete chat-templated request plus the output budget fits, and the
    cheap predictor never says yes when it should have said no.

    `prompt_tokens` is the runtime's own count of the whole templated request,
    so this measures the candidate tokenizer rather than a words-to-tokens
    estimate taken from another model family.
    """
    overflow = [
        o for o in observations if o.prompt_tokens + inference.max_output_tokens > inference.n_ctx
    ]
    under_reserved = [
        o
        for o in observations
        if o.fits_context_predicted
        and o.prompt_tokens + inference.max_output_tokens > inference.n_ctx
    ]
    widest = max((o.prompt_tokens for o in observations), default=0)
    return _outcome(
        GateName.CONTEXT_FIT,
        passed=bool(observations) and not overflow and not under_reserved,
        measured=(
            f"widest request {widest} + {inference.max_output_tokens} output tokens; "
            f"{len(overflow)} overflowed, {len(under_reserved)} under-reserved"
        ),
        threshold=f"<= n_ctx {inference.n_ctx}; fits_context over-reserves",
        source=f"{_CONFIG} models.inference.n_ctx",
        detail=(
            "a request that does not fit is not a shorter summary, it is a reply "
            "cut off before it closed its JSON"
        ),
    )


def identity(shards: Sequence[QualificationShard]) -> GateOutcome:
    """The bytes the runtime opened are the bytes the adoption target names."""
    mismatched = [
        shard
        for shard in shards
        if shard.candidate.sha256_observed != shard.candidate.sha256_expected
        or shard.candidate.bytes_observed != shard.candidate.bytes_expected
    ]
    candidate = shards[0].candidate if shards else None
    observed = candidate.sha256_observed if candidate else "nothing ran"
    return _outcome(
        GateName.IDENTITY,
        passed=bool(shards) and not mismatched,
        measured=(
            f"{observed} at {candidate.bytes_observed} bytes" if candidate else "nothing ran"
        ),
        threshold=(
            f"{candidate.sha256_expected} at {candidate.bytes_expected} bytes, "
            f"{candidate.repo}@{candidate.revision}/{candidate.file}"
            if candidate
            else "the adoption target digest"
        ),
        source=_TARGET,
        detail=(
            f"{len(mismatched)} shard(s) served bytes the target does not name"
            if mismatched
            else "every shard opened the target bytes"
        ),
    )


def budget(budget_: Budget) -> GateOutcome:
    """Every job finished inside its bound, with the margin measured not guessed."""
    spent_minutes = budget_.slowest_shard_seconds / 60.0
    margin = budget_.job_budget_minutes - spent_minutes
    share = spent_minutes / budget_.job_budget_minutes if budget_.job_budget_minutes else 1.0
    return _outcome(
        GateName.BUDGET,
        passed=spent_minutes <= budget_.job_budget_minutes,
        measured=(
            f"slowest job {spent_minutes:.1f} min ({share * 100:.0f} percent of the bound), "
            f"slowest item {budget_.slowest_item_seconds:.0f} s"
        ),
        threshold=f"{budget_.job_budget_minutes:.0f} min per job",
        source=f"{_DISPATCH} job_budget_minutes, Rule #2",
        detail=f"margin {margin:.1f} min",
    )


def scored_denominator(
    corpus: Corpus, *, evaluation: EvaluationConfig, run: RunConfig
) -> GateOutcome:
    """Enough of the frozen corpus was summarized and scored.

    The rate is taken over the frozen corpus, not over the addresses the capture
    consumed. A dead link is a fact about the web, and it is recorded as
    `planned` beside the rate; failing a candidate for it would turn this gate
    into a weather report. What the model was asked is what the model answers
    for.
    """
    frozen = len(corpus.items)
    scored = len(corpus.scores)
    rate = (scored / frozen * 100.0) if frozen else 0.0
    enough = scored >= evaluation.validation_articles
    floors = rate >= run.success_floor_pct
    return _outcome(
        GateName.SCORED_DENOMINATOR,
        passed=enough and floors,
        measured=(
            f"{scored} scored of {frozen} frozen ({rate:.0f} percent), "
            f"{corpus.planned} addresses attempted"
        ),
        threshold=(
            f">= {evaluation.validation_articles} scored and "
            f">= {run.success_floor_pct} percent of the frozen corpus"
        ),
        source=(f"{_CONFIG} evaluation.validation_articles, run.success_floor_pct"),
        detail="every failure stays in the denominator; a mean over survivors is not a mean",
    )


def faithfulness_floor(
    corpus: Corpus, *, evaluation: EvaluationConfig, pinned: bool
) -> GateOutcome:
    """Mean faithfulness clears the floor - if the instrument was pinned.

    The precondition is the whole gate. HHEM was pinned to the mutable string
    `main` until 2026-08-26, and the derived `scorer_version` hashed that name
    rather than the loaded weights, so a floor measured before this pin measured
    an unknown instrument (Rule #10).
    """
    scores = [score.hhem for score in corpus.scores]
    mean = statistics.fmean(scores) if scores else 0.0
    return _outcome(
        GateName.FAITHFULNESS_FLOOR,
        passed=pinned and bool(scores) and mean >= evaluation.band_medium_min,
        measured=(
            f"mean hhem {mean:.4f} over {len(scores)} items, "
            f"scorer {'pinned' if pinned else 'UNPINNED'}"
        ),
        threshold=f">= {evaluation.band_medium_min}, on a scorer pinned to an immutable revision",
        source=f"{_CONFIG} evaluation.band_medium_min",
        detail=(
            "the scorer revision is a branch name, so this measures an instrument "
            "that can move overnight"
            if not pinned
            else "the floor is the medium band edge - below it an item is low-confidence"
        ),
    )


def brief_copying_ceiling(corpus: Corpus, *, evaluation: EvaluationConfig) -> GateOutcome:
    """A brief item was rewritten, not copied.

    Only the brief path is gated. A short source gives a model almost nothing to
    compress, so copying it back is the easy failure - and it is the one place
    where a verbatim run has a committed ceiling to be read against.
    """
    briefs = [score for score in corpus.scores if score.brief]
    over = [s for s in briefs if s.verbatim_run > evaluation.brief_compression_ceiling]
    longest = max((s.verbatim_run for s in briefs), default=0.0)
    return _outcome(
        GateName.BRIEF_COPYING_CEILING,
        passed=bool(briefs) and not over,
        measured=f"longest brief verbatim run {longest:.3f} over {len(briefs)} brief items",
        threshold=f"<= {evaluation.brief_compression_ceiling}, every brief item",
        source=f"{_CONFIG} evaluation.brief_compression_ceiling",
        detail=(
            f"{len(over)} brief item(s) copied past the ceiling"
            if over
            else "no brief item was copied past the ceiling"
        ),
    )


def gates(
    shards: Sequence[QualificationShard],
    *,
    evaluation: EvaluationConfig,
    inference: InferenceConfig,
    run: RunConfig,
    budget_: Budget,
    required_canaries: int,
) -> tuple[Corpus, list[GateOutcome]]:
    """Every gate, in the order the row registers them."""
    corpus = merge(shards)
    pinned = all(shard.scorer.pinned for shard in shards) and bool(shards)
    return corpus, [
        reasoning_leakage(corpus.observations),
        schema_validity(corpus.observations),
        injection_canaries(corpus.canaries, required=required_canaries),
        determinism(corpus.observations, repeats=corpus.repeats),
        publishable_length(corpus.observations, evaluation),
        context_fit(corpus.observations, inference),
        identity(shards),
        budget(budget_),
        scored_denominator(corpus, evaluation=evaluation, run=run),
        faithfulness_floor(corpus, evaluation=evaluation, pinned=pinned),
        brief_copying_ceiling(corpus, evaluation=evaluation),
    ]


# --- recorded, never blocked ------------------------------------------------


def _mean(values: Iterable[float]) -> float:
    collected = list(values)
    return statistics.fmean(collected) if collected else 0.0


def diagnostics(corpus: Corpus, *, evaluation: EvaluationConfig) -> list[Diagnostic]:
    """The demoted metrics and the standing ones, each with its denominator.

    Demoted on 2026-08-26 because every threshold they could have taken would
    have come from the confounded 8B history. They are still measured: a number
    with no bar is still the thing a human reads when a gate passes and the
    output still looks wrong.
    """
    scores = corpus.scores
    n = len(scores)
    non_brief = [s for s in scores if not s.brief]
    calls = corpus.observations
    ok = [o for o in calls if o.ok]
    unsupported = sum(s.unsupported_numbers for s in scores)
    hedges = sum(1 for s in scores if s.hedge_dropped)
    thin_lead = sum(1 for s in scores if s.lead_coverage < evaluation.lead_coverage_min)
    titles = sum(1 for s in scores if s.title_fell_back)
    hhem = [s.hhem for s in scores]
    decode = [
        o.completion_tokens / o.summarize_seconds
        for o in ok
        if o.summarize_seconds > 0 and o.completion_tokens
    ]
    return [
        Diagnostic(name="unsupported_numbers_total", value=str(unsupported), denominator=n),
        Diagnostic(
            name="unsupported_numbers_rate",
            value=f"{(unsupported / n if n else 0.0):.4f}",
            denominator=n,
        ),
        Diagnostic(name="hedge_dropped_total", value=str(hedges), denominator=n),
        Diagnostic(
            name="hedge_dropped_rate", value=f"{(hedges / n if n else 0.0):.4f}", denominator=n
        ),
        Diagnostic(
            name="below_lead_coverage_min_share",
            value=f"{(thin_lead / n if n else 0.0):.4f}",
            denominator=n,
        ),
        Diagnostic(
            name="extractiveness_mean_non_brief",
            value=f"{_mean(s.extractiveness for s in non_brief):.4f}",
            denominator=len(non_brief),
        ),
        Diagnostic(
            name="verbatim_run_mean_non_brief",
            value=f"{_mean(s.verbatim_run for s in non_brief):.4f}",
            denominator=len(non_brief),
        ),
        Diagnostic(name="hhem_mean", value=f"{_mean(hhem):.4f}", denominator=n),
        Diagnostic(
            name="hhem_spread",
            value=(f"{min(hhem):.4f}-{max(hhem):.4f}" if hhem else "no scored items"),
            denominator=n,
        ),
        Diagnostic(
            name="hhem_delta_mean",
            value=f"{_mean(s.hhem - s.hhem_full for s in scores):.4f}",
            denominator=n,
        ),
        Diagnostic(
            name="compression_mean",
            value=f"{_mean(s.compression for s in scores):.4f}",
            denominator=n,
        ),
        Diagnostic(
            name="evidential_density_mean",
            value=f"{_mean(s.evidential_density for s in scores):.4f}",
            denominator=n,
        ),
        Diagnostic(
            name="speculative_density_mean",
            value=f"{_mean(s.speculative_density for s in scores):.4f}",
            denominator=n,
        ),
        Diagnostic(
            name="generated_title_fallback_rate",
            value=f"{(titles / n if n else 0.0):.4f}",
            denominator=n,
        ),
        Diagnostic(
            name="decode_tokens_per_second_median",
            value=f"{(statistics.median(decode) if decode else 0.0):.2f}",
            denominator=len(decode),
        ),
    ]


def stratification(items: Sequence[CorpusItem], *, summarize: SummarizeConfig) -> list[Diagnostic]:
    """How the frozen corpus fell across the tiers the row asked it to cover."""
    counts = dict.fromkeys(range(len(summarize.bands)), 0)
    for item in items:
        counts[item.band_index] = counts.get(item.band_index, 0) + 1
    rows = [
        Diagnostic(
            name=f"band_{index}_min_source_words_{band.min_source_words}",
            value=str(counts.get(index, 0)),
            denominator=len(items),
        )
        for index, band in enumerate(summarize.bands)
    ]
    rows.append(
        Diagnostic(
            name="over_truncation_cap",
            value=str(sum(1 for item in items if item.truncated)),
            denominator=len(items),
        )
    )
    rows.append(
        Diagnostic(
            name="brief_path",
            value=str(sum(1 for item in items if item.brief)),
            denominator=len(items),
        )
    )
    return rows
