"""Score the day's own planned articles with whichever model is served.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from idhazh import (
    assemble,
    config,
    summarize,
    telemetry,
)
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import canonical_json
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.evals import golden
from idhazh.evals.hhem import (
    score_over_chunks,
)
from idhazh.fingerprint import (
    text_digest,
)
from idhazh.llm.server import (
    DEFAULT_ENDPOINT,
)
from idhazh.stages import common
from idhazh.stages.common import LOG, Fetcher, _ask_the_model, _fetch_one, _load_plan, silent_tracer


def _summarize_one(
    article: Article,
    settings: config.Settings,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    run_id: str | None = None,
    tracer: telemetry.Tracer | None = None,
) -> Summary:
    """One article becomes one summary, in three steps a single column hides.

    `summarize_ms` covers all three. Rendering the prompt builds a JSON schema
    from a Pydantic model; parsing the reply validates it back and then runs the
    verbatim check over the whole source, which is the longest string comparison
    in the pipeline. So an item that got slow is either the model, our schema
    work or our own checking, and until these spans existed the three were one
    number.
    """
    trace = tracer if tracer is not None else silent_tracer()
    inference = settings.models.summarize.inference
    turns = settings.models.summarize.turns
    model_id = settings.models.summarize.id
    with trace.span(telemetry.SpanName.SUMMARIZE) as stage_span:
        stage_span.set(telemetry.AttrKey.MODEL_ID, model_id)
        with trace.span(telemetry.SpanName.RENDER_PROMPT) as span:
            payload = summarize.build_request(
                article,
                model_id=model_id,
                inference=inference,
                turns=turns,
                prompt_config=settings.app.summarize,
            )
            rendered = canonical_json(payload)
            prompt_digest = text_digest(rendered)
            span.set(telemetry.AttrKey.PROMPT_DIGEST, prompt_digest)
            span.set(telemetry.AttrKey.PROMPT_CHARS, len(rendered))
        completion, no_reply = _ask_the_model(
            payload,
            article,
            model_id=model_id,
            endpoint=endpoint,
            timeout=inference.request_timeout_minutes * 60,
            prompt_digest=prompt_digest,
            run_id=run_id,
            trace=trace,
        )
        with trace.span(telemetry.SpanName.PARSE_REPLY) as span:
            summary = summarize.to_summary(
                article,
                completion,
                model_id=model_id,
                generated_at=assemble.utc_now(),
                prompt_config=settings.app.summarize,
                evaluation=settings.app.evaluation,
                no_reply=no_reply,
                thinking=turns.thinks,
            )
            telemetry.summary_attributes(span, summary)
        telemetry.summary_attributes(stage_span, summary)
    return summary


def stage_validate(
    *,
    settings: config.Settings,
    date: str,
    leaderboard: float,
    scorer: object,
    fetcher: Fetcher | None = None,
) -> None:
    """Score the day's own planned articles with whichever model is served.

    The corpus is the run plan, not a curated list. A hand-picked set of
    addresses decays the moment it is written - the first one this project had
    lost three of twenty within hours, and the gate correctly refused to judge on
    seventeen. The plan is regenerated per validation, so it never rots, needs no
    curation, and is the real corpus rather than a proxy for it.

    Both models read the same committed plan file, so the only thing differing
    between their two numbers is the weights.
    """
    if scorer is None:
        raise SystemExit("validation without a faithfulness scorer measures nothing")

    read_url = fetcher or common.live_fetcher(settings)
    plan = _load_plan(date)
    model_id = settings.models.summarize.id
    scores: list[float] = []

    for index, item in enumerate(plan.items, start=1):
        article = _fetch_one(item, settings, read_url).article
        if article.status is not ArticleStatus.OK:
            LOG.warning("validation article unavailable url=%s", item.canonical_url)
            continue
        summary = _summarize_one(article, settings)
        if summary.status is not SummaryStatus.OK:
            LOG.warning("validation article did not summarize url=%s", item.canonical_url)
            continue
        text = article.text or ""
        # One score, asked for as one score. Validation compares against a
        # leaderboard number and has no use for a truncation gap.
        hhem = score_over_chunks(
            scorer,  # type: ignore[arg-type]
            text,
            summary.summary or "",
            evaluation=settings.app.evaluation,
        )
        scores.append(hhem)
        LOG.info("validation scored %s/%s hhem=%.3f", index, len(plan.items), hhem)

    result = golden.GoldenResult(
        model_id=model_id,
        leaderboard_hhem=leaderboard,
        scores=scores,
        attempted=len(plan.items),
    )
    common.VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    assemble.write_atomic(common.VALIDATION_ROOT / f"{model_id}.json", result.to_json())
    LOG.info(
        "validated model=%s scored=%s/%s mean_hhem=%.4f",
        model_id,
        result.articles,
        result.attempted,
        result.measured_hhem,
    )
