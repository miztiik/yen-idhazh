"""Freeze this shard's slice of the corpus, then replay it N times.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is not a worker").
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import NamedTuple

from idhazh import (
    assemble,
    config,
    extract,
    summarize,
)
from idhazh.contracts.app_config import (
    EvaluationConfig,
    InferenceConfig,
)
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import canonical_json
from idhazh.contracts.qualification import (
    CandidateIdentity,
    CorpusItem,
    ItemObservation,
    ItemScore,
    QualificationShard,
    ScorerIdentity,
)
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.evals import metrics, qualify
from idhazh.evals.hhem import (
    HHEM_REVISION,
    HHEM_SCORER_ID,
    HhemScorer,
    dual_score,
    is_pinned,
    weights_digest,
)
from idhazh.fingerprint import (
    UNRECORDED_TEMPLATE,
    build_inputs,
    runner_class,
    text_digest,
)
from idhazh.llm.server import (
    DEFAULT_ENDPOINT,
    Completion,
    props,
)
from idhazh.sanitize import SANITIZER_VERSION
from idhazh.stages import common
from idhazh.stages.common import (
    LOG,
    Fetcher,
    _fetch_one,
    _load_plan,
    _one_call,
    _run_canaries,
    shard_of,
)


class _Frozen(NamedTuple):
    """One captured article and the row that describes it."""

    row: CorpusItem
    item: PlannedItem
    article: Article
    seen_text: str
    full_text: str


class _Share(NamedTuple):
    """What ONE shard tries to find, so the shards together meet the definition.

    Every shard runs in its own job and cannot see a sibling's corpus, so each
    one aims at the whole requirement rather than at a fraction of it. Aiming at
    a fraction is what loses a tier: a shard that stopped at its 1-in-3 share
    would walk away from the second long read in its slice, and a sibling whose
    slice held none could not make it up. Aiming high costs nothing - the corpus
    is still `corpus_per_shard` articles, and a tier nobody found is named
    rather than replaced.
    """

    per_band: int
    over_cap: int
    brief: int


def corpus_share() -> _Share:
    """The registered definition, as one shard's target."""
    return _Share(
        per_band=qualify.MIN_PER_BAND,
        over_cap=qualify.MIN_OVER_CAP,
        brief=qualify.MIN_BRIEF,
    )


def _unmet(offered: Sequence[_Frozen], *, share: _Share, bands: int) -> list[str]:
    """Which tiers this slice could not offer. The union is decided elsewhere."""
    short = []
    for index in range(bands):
        found = sum(1 for entry in offered if entry.row.band_index == index)
        if found < share.per_band:
            short.append(f"band {index}: {found}, the definition asks for {share.per_band}")
    over_cap = sum(1 for entry in offered if entry.row.truncated)
    if over_cap < share.over_cap:
        short.append(
            f"over the truncation cap: {over_cap}, the definition asks for {share.over_cap}"
        )
    briefs = sum(1 for entry in offered if entry.row.brief)
    if briefs < share.brief:
        short.append(f"brief-path items: {briefs}, the definition asks for {share.brief}")
    return short


def _freeze(
    items: Sequence[PlannedItem],
    settings: config.Settings,
    read_url: Fetcher,
    *,
    keep: int,
    share: _Share,
) -> tuple[list[_Frozen], int, list[str]]:
    """Fetch, extract and sanitize once, then hash what came back.

    Once, and never again: the three deterministic repeats have to see identical
    bytes, and a publisher rewriting a page between two of them would read as a
    decoding drift. The bytes stay on this job's own disk - only the hashes and
    the measurements travel, because an article body is not ours to move
    (`CLAUDE.md` section 0a).

    The walk stops at the LATER of two floors: a pool wide enough to choose from
    at all, and a pool that already holds every tier the definition asks for.
    Otherwise it walks the whole slice. A long read is the scarce shape -
    measured on 2026-08-26 at 3 of 109 extracted articles, under 3 in 100 - so a
    walk that stopped at the first floor met its item count every time while the
    tier that decides whether the corpus can speak at all stayed empty. Walking
    further costs fetch seconds and never model minutes: the model still sees
    `keep` articles, and one address measured 2.1 s over 150 of them.

    Returns the selected corpus, how many addresses were consumed, and the tiers
    this slice could not offer. The second number is the honest attempted
    denominator: an address that would not fetch measured nothing, and dropping
    it from the record would let a bad day look like a good one.
    """
    bands = len(settings.app.summarize.bands)
    floor = keep * settings.app.evaluation.qualification_pool_multiple
    pool: list[_Frozen] = []
    attempted = 0
    for item in items:
        if len(pool) >= floor and not _unmet(pool, share=share, bands=bands):
            break
        attempted += 1
        article, source_text, _, _ = _fetch_one(item, settings, read_url)
        if article.status is not ArticleStatus.OK or not article.text:
            LOG.info("corpus item unavailable url=%s", item.canonical_url)
            continue
        seen = article.text
        whole = source_text or seen
        pool.append(
            _Frozen(
                row=CorpusItem(
                    item_id=item.item_id,
                    url_key=item.url_key,
                    canonical_url=item.canonical_url,
                    source_id=item.source_id,
                    vertical=item.vertical,
                    band_index=qualify.band_index(
                        article.band_source_words, settings.app.summarize
                    ),
                    brief=article.brief,
                    truncated=article.truncated,
                    source_word_count=article.band_source_words,
                    seen_word_count=len(seen.split()),
                    seen_token_count=article.token_count,
                    seen_text_sha256=text_digest(seen),
                    full_text_sha256=text_digest(whole),
                ),
                item=item,
                article=article,
                seen_text=seen,
                full_text=whole,
            )
        )
    chosen = _stratified(pool, keep=keep, bands=bands, share=share)
    return chosen, attempted, _unmet(pool, share=share, bands=bands)


def _stratified(
    pool: Sequence[_Frozen], *, keep: int, bands: int, share: _Share
) -> list[_Frozen]:
    """Reserve the scarce tiers first, then fill the rest in turn.

    Deterministic, and it needs to be: the corpus is registered by hash before
    any output is looked at, so a selection that varied would let somebody
    re-roll a corpus until the answer improved.

    Scarcest tier first, and one at a time. A plain round-robin spends its early
    slots on whichever tier the index order reaches first, and taking a whole
    tier's quota before moving on starves the last tier when `keep` is smaller
    than every tier's quota added up. Measured on 2026-08-26 over 109 extracted
    articles, the long-read tier held 3 and the 60-to-699-word tier held 67, so
    the order is not a detail. Ties break on the band index, so two tiers of
    equal size always resolve the same way.

    Within a tier the scarce shapes go first: a brief item and an over-cap item
    each exercise a path nothing else reaches, and both are rarer than an
    ordinary article.
    """
    buckets: dict[int, list[_Frozen]] = {index: [] for index in range(bands)}
    for entry in pool:
        buckets.setdefault(entry.row.band_index, []).append(entry)
    for bucket in buckets.values():
        bucket.sort(key=lambda entry: (not entry.row.brief, not entry.row.truncated))
    scarcest = sorted(buckets, key=lambda key: (len(buckets[key]), key))
    chosen: list[_Frozen] = []
    for _ in range(share.per_band):
        for index in scarcest:
            if len(chosen) < keep and buckets[index]:
                chosen.append(buckets[index].pop(0))
    while len(chosen) < keep and any(buckets.values()):
        for index in sorted(buckets):
            if len(chosen) >= keep:
                break
            if buckets[index]:
                chosen.append(buckets[index].pop(0))
    return chosen


def _observe(
    article: Article,
    summary: Summary,
    completion: Completion | None,
    *,
    repeat: int,
    inference: InferenceConfig,
    seconds: float,
) -> ItemObservation:
    reply = completion or Completion(content="")
    inline = summarize.split_thinking(reply.content)[1] or ""
    return ItemObservation(
        item_id=article.item_id,
        repeat=repeat,
        ok=summary.status is SummaryStatus.OK,
        failure_code=summary.failure_code.value if summary.failure_code else None,
        finish_reason=reply.finish_reason,
        reasoning_channel_used=bool(reply.reasoning.strip()),
        think_block_words=len(inline.split()),
        schema_valid=summary.status is SummaryStatus.OK,
        # One call, one reply. The gate wants zero repair attempts, so the
        # column exists to be asserted rather than to be filled in later.
        repaired=summary.attempt > 1,
        output_digest=summary.output_digest,
        summary_word_count=len((summary.summary or "").split()),
        prompt_tokens=reply.prompt_tokens,
        completion_tokens=reply.completion_tokens,
        fits_context_predicted=summarize.fits_context(article, inference),
        summarize_seconds=seconds,
    )


def _score_item(
    frozen: _Frozen, summary: Summary, scorer: object, evaluation: EvaluationConfig
) -> ItemScore:
    text = summary.summary or ""
    hhem, hhem_full = dual_score(
        scorer,  # type: ignore[arg-type]
        seen_text=frozen.seen_text,
        full_text=frozen.full_text,
        summary=text,
        evaluation=evaluation,
    )
    return ItemScore(
        item_id=frozen.row.item_id,
        brief=frozen.article.brief,
        hhem=hhem,
        hhem_full=hhem_full,
        verbatim_run=metrics.verbatim_run(text, frozen.full_text),
        extractiveness=metrics.extractiveness(text, frozen.full_text),
        compression=metrics.compression(text, frozen.full_text),
        lead_coverage=metrics.lead_coverage(text, frozen.full_text),
        unsupported_numbers=metrics.unsupported_numbers(text, frozen.full_text),
        hedge_dropped=metrics.hedge_dropped(text, frozen.full_text),
        evidential_density=metrics.evidential_density(frozen.full_text),
        speculative_density=metrics.speculative_density(frozen.full_text),
        title_fell_back=summary.title is None,
    )


def stage_qualify(
    *,
    settings: config.Settings,
    date: str,
    shard: int,
    shards: int,
    repeats: int,
    corpus_per_shard: int,
    candidate: CandidateIdentity,
    scorer: object,
    commit_sha: str,
    runner: str,
    fetcher: Fetcher | None = None,
    model_endpoint: str = DEFAULT_ENDPOINT,
) -> QualificationShard:
    """Freeze this shard's slice of the corpus, then replay it N times.

    Capture once and replay is the whole design. The old validation arm replanned
    and refetched for every model it scored, so two numbers could differ because
    a publisher edited a page rather than because the weights differed. There is
    only one model here now, and the same argument still holds against the three
    repeats.
    """
    if scorer is None:
        raise SystemExit("a qualification without a faithfulness scorer measures nothing")
    if not isinstance(scorer, HhemScorer):
        raise SystemExit("the faithfulness gate needs the pinned HHEM scorer")

    started = time.monotonic()
    read_url = fetcher or common.live_fetcher(settings)
    inference = settings.models.summarize.inference
    model = settings.models.summarize
    observed = props(model_endpoint, timeout=inference.request_timeout_minutes * 60)
    inputs = build_inputs(
        model=model,
        model_sha256=candidate.sha256_observed,
        inference=inference,
        truncation_cap_tokens=settings.app.extract.truncation_cap_tokens,
        runtime_build=candidate.runtime_build,
        chat_template=str(observed.get("chat_template") or UNRECORDED_TEMPLATE),
        prompt=summarize.prompt_inputs(settings.app.summarize),
        output_schema=summarize.output_schema_text(settings.app.summarize),
        runner_class=runner_class(),
        extractor_version=extract.EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
    )

    plan = _load_plan(date)
    mine = shard_of(plan, shard=shard, shards=shards)
    share = corpus_share()
    frozen, attempted, unmet = _freeze(mine, settings, read_url, keep=corpus_per_shard, share=share)

    root = common.QUALIFICATION_ROOT / date / f"shard-{shard}"
    for entry in frozen:
        assemble.write_atomic(
            root / "items" / f"{entry.row.item_id}.article.json", entry.article.to_json()
        )
    registered_at = assemble.utc_now()
    assemble.write_atomic(
        root / "corpus.json",
        canonical_json([entry.row.model_dump(mode="json") for entry in frozen]),
    )
    # Loud here, decided at `decide`. A shard cannot see its siblings, so it
    # never rules on the union - it only says which tier its own slice never
    # offered, while the addresses are still in this job's log.
    for shortfall in unmet:
        LOG.error("shard %s was offered no such tier: %s", shard, shortfall)
    LOG.info(
        "corpus frozen shard=%s items=%s attempted=%s handed=%s registered_at=%s",
        shard,
        len(frozen),
        attempted,
        len(mine),
        registered_at,
    )

    scorer_identity = ScorerIdentity(
        scorer_id=HHEM_SCORER_ID,
        revision=HHEM_REVISION,
        pinned=is_pinned(HHEM_REVISION),
        weights_sha256=weights_digest(scorer),
        scorer_version=metrics.scorer_version(
            scorer_id=HHEM_SCORER_ID,
            scorer_revision=HHEM_REVISION,
            weights_sha256=weights_digest(scorer),
            evaluation=settings.app.evaluation,
        ),
    )

    observations: list[ItemObservation] = []
    scores: list[ItemScore] = []
    # Repeats on the outside, items on the inside. The other order would let
    # each repeat land on a warm prompt cache, and an identical reply that
    # skipped its own prefill is weaker evidence of determinism than one that
    # did the arithmetic again.
    for repeat in range(1, repeats + 1):
        for entry in frozen:
            summary, completion, seconds = _one_call(
                entry.article, settings, endpoint=model_endpoint
            )
            observations.append(
                _observe(
                    entry.article,
                    summary,
                    completion,
                    repeat=repeat,
                    inference=inference,
                    seconds=seconds,
                )
            )
            LOG.info(
                "qualify call item=%s repeat=%s ok=%s seconds=%.1f",
                entry.row.item_id,
                repeat,
                summary.status is SummaryStatus.OK,
                seconds,
            )
            if repeat == 1 and summary.status is SummaryStatus.OK:
                scores.append(_score_item(entry, summary, scorer, settings.app.evaluation))

    canaries = _run_canaries(settings, endpoint=model_endpoint) if shard == 0 else []

    result = QualificationShard(
        version=QualificationShard.schema_version(),
        date=date,
        commit_sha=commit_sha,
        runner=runner,
        shard=shard,
        shards=shards,
        repeats=repeats,
        candidate=candidate,
        scorer=scorer_identity,
        inputs=inputs,
        corpus_registered_at=registered_at,
        planned=attempted,
        corpus=[entry.row for entry in frozen],
        observations=observations,
        scores=scores,
        canaries=canaries,
        elapsed_seconds=time.monotonic() - started,
    )
    assemble.write_atomic(common.QUALIFICATION_ROOT / f"shard-{shard}.json", result.to_json())
    LOG.info(
        "qualification shard done shard=%s frozen=%s calls=%s scored=%s minutes=%.1f",
        shard,
        len(frozen),
        len(observations),
        len(scores),
        result.elapsed_seconds / 60.0,
    )
    return result
