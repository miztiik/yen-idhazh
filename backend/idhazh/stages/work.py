"""Fetch, extract, summarize and score one item at a time, writing as it goes.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import ValidationError

from idhazh import (
    assemble,
    capture,
    config,
    elements,
    extract,
    fingerprint,
    itemrecord,
    ledger,
    machine,
    summarize,
    telemetry,
    visual_planner,
)
from idhazh.classify import calls, dag
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import canonical_json
from idhazh.contracts.call_cost import COST_FIELDS, CallCost, CallKind
from idhazh.contracts.element import ElementTable
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.item_health import FailureCode, ItemOutcome, ItemStage
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual import PlanDecision, VisualPlan
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision
from idhazh.evals import evidence, metrics, score
from idhazh.evals.hhem import (
    HHEM_REVISION,
    HHEM_SCORER_ID,
    HhemScorer,
    dual_score,
    weights_digest,
)
from idhazh.fingerprint import (
    UNRECORDED_TEMPLATE,
    build_inputs,
    runner_class,
    runtime_build,
    text_digest,
)
from idhazh.llm.server import (
    DEFAULT_ENDPOINT,
    Completion,
    completion_url,
    props,
)
from idhazh.render import asset_relpath, render_planned_visual
from idhazh.sanitize import SANITIZER_VERSION
from idhazh.stages import common
from idhazh.stages.common import (
    INPUTS_PAYLOAD,
    LOG,
    Fetcher,
    _ask_the_model,
    _fetch_one,
    _run_dir,
    shard_of,
    silent_tracer,
)
from idhazh.visual_validator import validate_plan


def _evidence_dir(date: str) -> Path:
    return common.EVIDENCE_ROOT / date


def _trace_id(run_id: str, item: PlannedItem) -> str:
    """One item on one run. The work stage opens it twice and the planner opens it again."""
    return f"{run_id}-{item.item_id}"


def trace_sink(
    settings: config.Settings, *, run_id: str, shard: int
) -> telemetry.SpanSink:
    """Where this shard's spans go: nowhere, a committed file, or a file and a host.

    A file by default and a host only when the environment names one, with its
    key pair (owner decision, 2026-08-30). No workflow sets those, so a daily
    run reaches no third party and needs no secret; a developer who wants the
    hosted view exports three variables and gets both. The host is added to the
    file and never instead of it, so the record a test reads and the record a
    host receives are the same record.

    The file is the committed trace under `state/traces/`, not a gitignored one,
    so a recent run stays openable from the repository; `retention.prune_traces`
    bounds the rolling window (CLAUDE.md section 1b, docs/concepts/telemetry.md).
    """
    if not settings.app.observability.tracing_enabled:
        return telemetry.NullSink()
    local = telemetry.FileSink(telemetry.committed_trace_path(common.STATE_ROOT, run_id, shard))
    host = os.environ.get("LANGFUSE_HOST", "").strip()
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not (host and public_key and secret_key):
        return local
    remote = telemetry.langfuse_sink(host=host, public_key=public_key, secret_key=secret_key)
    if remote is None:
        LOG.warning("a langfuse host is named but the package is absent; tracing to the file")
        return local
    return telemetry.FanOut((local, remote))


class _FetchedWorkItem(NamedTuple):
    item: PlannedItem
    article: Article
    source_text: str
    fetch_ms: int
    extract_ms: int
    started: float
    original_index: int
    #: The item's own record, opened when it was fetched and still open. The
    #: model loop runs in a different order from the fetch loop, so an item's
    #: cells have to travel with the item rather than sitting in a list the
    #: second loop indexes by position.
    recorder: itemrecord.ItemRecorder


def _summarize_band_sort_key(work: _FetchedWorkItem, settings: config.Settings) -> tuple[int, int]:
    band = settings.app.summarize.band_for(work.article.band_source_words)
    return band.min_source_words, work.original_index


def _shard_cells(settings: config.Settings, *, shard: int, shard_item_count: int) -> dict[str, Any]:
    """What was true of this shard before it read a single article.

    Read once and noted on every item, because the question these answer is
    asked of ONE row: a reader looking at a 475,890 ms item wants the context
    size and the output budget that item ran under, and a shard-grain ledger
    somewhere else makes them join two files to get it.

    **Every one of them is config, so none of them is a measurement.** They are
    the settings the run was given, which is exactly what a person comparing two
    runs needs - the readings are the machine cells beside them.
    """
    model = settings.models.summarize
    inference = model.inference
    return {
        "shard": shard,
        "shard_item_count": shard_item_count,
        "cpu_model": fingerprint.host_cpu() or None,
        "runner_name": machine.runner_name(),
        "model_id": model.id,
        "model_quantisation": model.quantisation,
        "n_ctx_configured": inference.n_ctx,
        "n_parallel": inference.n_parallel,
        "n_threads": inference.n_threads,
        "n_batch": inference.n_batch,
        "max_output_tokens": inference.max_answer_tokens,
        "label_budget_tokens": calls.label_budget_tokens(),
        "summary_budget_tokens": calls.summarize_and_plan_budget_tokens(settings.app.summarize),
        "temperature": inference.temperature,
    }


def _planned_cells(item: PlannedItem, *, index: int) -> dict[str, Any]:
    """Which item this is, and every term that put it in the run.

    The ranker computes these and throws all but the total away, so an item that
    published for one reason and an item that published for another are
    indistinguishable afterwards. Carried onto the record they are the answer to
    "why was this one here at all" - which is the first question asked of an
    item that cost eight minutes.
    """
    return {
        "item_id": item.item_id,
        "url_key": item.url_key,
        "canonical_url": item.canonical_url,
        "vertical": item.vertical.value if hasattr(item.vertical, "value") else item.vertical,
        "source_id": item.source_id,
        "item_index": index,
        "selection_score": item.rank_score,
        "authority_score": item.authority_score,
        "tier_score": item.tier_score,
        "feed_weight": item.feed_weight,
        "feed_reliability": item.feed_reliability,
        "lens_bonus": item.lens_bonus,
        "recency_bonus": item.recency_bonus,
        "carriage_step": item.carriage_step,
        "watchlist_bonus": item.watchlist_bonus,
        "carried_by": item.carried_by,
        "watchlist_hit": item.watchlist_hit,
        "on_front_page": item.on_front_page,
        "tier": item.tier,
        "source_form": item.source_form,
        "published_at": item.published_at,
        "time_source": item.time_source,
    }


def _article_cells(article: Article) -> dict[str, Any]:
    """What the fetch and the extract settled about the text.

    `truncation_cap_tokens` is the article's own `truncated_at_tokens` and never
    the configured cap, because the two disagree the moment the cap moves and
    the row has to say which one did the cutting. It is null on an uncut item,
    which is what the column declares.
    """
    text = article.text or ""
    return {
        "source_chars": len(text),
        "source_words": article.word_count,
        "source_words_before_cap": article.source_word_count,
        "truncation_cap_tokens": article.truncated_at_tokens,
    }


def _call_cells(slot: str, reply: Completion) -> dict[str, Any]:
    """One model call's numbers, under the slot's own column names.

    Six the server reported, one wall clock, two rates and a cache share. The
    rates are derived here rather than left to whoever reads the row, because a
    reader deriving them is a reader who has to know which milliseconds go with
    which token count - and the regression this exists to catch is exactly a
    decode rate moving while a wall clock stayed put.
    """
    prefill_s = reply.prefill_ms / 1000
    decode_s = reply.decode_ms / 1000
    return {
        f"{slot}_prefill_ms": reply.prefill_ms,
        f"{slot}_decode_ms": reply.decode_ms,
        f"{slot}_input_tokens": reply.prompt_tokens,
        f"{slot}_output_tokens": reply.completion_tokens,
        f"{slot}_cached_tokens": min(reply.cached_tokens, reply.prompt_tokens),
        f"{slot}_finish_reason": reply.finish_reason,
        f"{slot}_ms": reply.prefill_ms + reply.decode_ms,
        f"{slot}_cache_pct": (
            round(100 * min(reply.cached_tokens, reply.prompt_tokens) / reply.prompt_tokens, 2)
            if reply.prompt_tokens
            else None
        ),
        f"{slot}_prefill_tokens_per_s": (
            round(reply.prompt_tokens / prefill_s, 2) if prefill_s > 0 else None
        ),
        f"{slot}_decode_tokens_per_s": (
            round(reply.completion_tokens / decode_s, 2) if decode_s > 0 else None
        ),
    }


def _ms(cell: object) -> int:
    """One duration cell as a number, and zero where the stage never filled it."""
    return cell if isinstance(cell, int) else 0


def _heartbeat(recorder: itemrecord.ItemRecorder) -> Callable[[float], None]:
    """The tick this item's watch calls while a model call is in flight.

    A function that closes over one recorder rather than a lambda in the loop,
    because a lambda in a loop closes over the LOOP VARIABLE - every item's
    watch would tick the last item's record, and a heartbeat naming the wrong
    item is worse than no heartbeat.
    """

    def tick(seconds: float) -> None:
        recorder.waiting("summarize", seconds)

    return tick


def _slowest(finished: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The item that cost the shard most, and enough to find it again.

    Four cells and not the row: a shard record carrying 113 columns of one item
    buries the totals beside it, and the item's own completion record is already
    in the log for anyone who wants the rest.

    **The address is the URL and the source, never the title.** A title is
    fetched text and a log line is read by a person, which is the one place
    untrusted text most wants to be believed (Guardrail #11).
    """
    timed_items = [cells for cells in finished if isinstance(cells.get("item_total_ms"), int)]
    if not timed_items:
        return None
    worst = max(timed_items, key=lambda cells: int(cells["item_total_ms"]))
    return {
        "item_id": worst.get("item_id"),
        "canonical_url": worst.get("canonical_url"),
        "source_id": worst.get("source_id"),
        "item_total_ms": worst.get("item_total_ms"),
    }


def stage_work(
    plan: RunPlan,
    *,
    settings: config.Settings,
    scorer: object | None,
    shard: int = 0,
    shards: int = 1,
    fetcher: Fetcher | None = None,
    model_endpoint: str = DEFAULT_ENDPOINT,
) -> None:
    """Fetch, extract, summarize and score one item at a time, writing as it goes."""
    shard_started = time.monotonic()
    tracing = settings.app.observability.tracing_enabled
    collector = telemetry.CollectingSink()
    base_sink = trace_sink(settings, run_id=plan.run_id, shard=shard)
    tracer = telemetry.Tracer(
        sink=telemetry.FanOut((base_sink, collector)) if tracing else base_sink,
        now=assemble.utc_now,
    )
    read_url = fetcher or common.live_fetcher(settings, tracer=tracer)
    inference = settings.models.summarize.inference
    model = settings.models.summarize
    observed = props(model_endpoint, timeout=inference.request_timeout_minutes * 60)
    inputs = build_inputs(
        model=model,
        model_sha256=model.sha256,
        inference=inference,
        truncation_cap_tokens=settings.app.extract.truncation_cap_tokens,
        runtime_build=runtime_build(),
        chat_template=str(observed.get("chat_template") or UNRECORDED_TEMPLATE),
        # The two calls render their own bytes, so the chat template above no
        # longer reaches what the model reads and the entry's turn envelope
        # does. Handing over the rendered pair is what digests the envelope, all
        # four prompt files and the turn order together.
        prompt=calls.prompt_inputs(settings.app.summarize, turns=model.turns),
        output_schema=summarize.output_schema_text(settings.app.summarize),
        runner_class=runner_class(),
        extractor_version=extract.EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
        turns=model.turns,
    )
    scorer_version = metrics.scorer_version(
        scorer_id=HHEM_SCORER_ID,
        scorer_revision=HHEM_REVISION,
        weights_sha256=weights_digest(scorer) if isinstance(scorer, HhemScorer) else "0" * 64,
        evaluation=settings.app.evaluation,
    )

    items_dir = _run_dir(plan.date) / "items"
    _write_inputs(items_dir, inputs=inputs)
    mine = shard_of(plan, shard=shard, shards=shards)
    LOG.info(
        "working shard=%s/%s items=%s model=%s",
        shard,
        shards,
        len(mine),
        model.id,
    )
    flags = itemrecord.Flags.of(settings.app.logging)
    # Read once per shard and noted on every item. The process table scan and
    # the CPU model read are each a few file opens; doing them per item would be
    # 80 scans for an answer that cannot change inside a shard.
    server_pid = machine.llama_server_pid()
    shard_cells = _shard_cells(settings, shard=shard, shard_item_count=len(mine))
    failures: dict[str, int] = {}
    finished: list[dict[str, Any]] = []
    ready: list[_FetchedWorkItem] = []
    for original_index, item in enumerate(mine):
        started = time.monotonic()
        recorder = itemrecord.ItemRecorder(
            run_id=plan.run_id, flags=flags, now=assemble.utc_now, log=LOG
        )
        recorder.note(
            date=plan.date,
            run_id=plan.run_id,
            item_started_at=assemble.utc_now(),
            **shard_cells,
            **_planned_cells(item, index=original_index),
        )
        recorder.start()
        with (
            tracer.trace(_trace_id(plan.run_id, item)),
            tracer.span(telemetry.SpanName.ITEM) as span,
        ):
            telemetry.item_attributes(span, item, run_id=plan.run_id, shard=shard)
            article, source_text, fetch_ms, extract_ms = _fetch_one(
                item, settings, read_url, tracer
            )
        # One reading of the pair, split across the two cells the stage records
        # separately, so the stage lines and the census row cannot disagree about
        # which milliseconds belonged to which half.
        recorder.note(fetch_ms=fetch_ms, extract_ms=extract_ms, **_article_cells(article))
        recorder.stage_done(ItemStage.FETCH, fetch_ms)
        recorder.stage_done(ItemStage.EXTRACT, extract_ms)
        assemble.write_atomic(items_dir / f"{item.item_id}.article.json", article.to_json())
        if article.status is not ArticleStatus.OK:
            LOG.info("item degraded id=%s reason=%s", item.item_id, article.failure_detail)
            recorder.note(
                stage=ItemStage.EXTRACT.value,
                outcome=ItemOutcome.FAILED.value,
                code=article.failure_code.value if article.failure_code else None,
                detail=telemetry.detail_cell(article.failure_detail)
                if article.failure_detail
                else None,
            )
            finished.append(recorder.done())
            code = str(recorder.get("code") or FailureCode.UNKNOWN.value)
            failures[code] = failures.get(code, 0) + 1
            continue
        ready.append(
            _FetchedWorkItem(
                item=item,
                article=article,
                source_text=source_text,
                fetch_ms=fetch_ms,
                extract_ms=extract_ms,
                started=started,
                original_index=original_index,
                recorder=recorder,
            )
        )

    for work in sorted(ready, key=lambda candidate: _summarize_band_sort_key(candidate, settings)):
        item = work.item
        article = work.article
        recorder = work.recorder
        # The gap between the fetch loop finishing this item and the model loop
        # reaching it. The two loops run in different orders, so this is real
        # time an item spent on a list and it is the only place it is visible.
        recorder.note(queue_wait_ms=int((time.monotonic() - work.started) * 1000) - work.fetch_ms)
        with (
            tracer.trace(_trace_id(plan.run_id, item)),
            tracer.span(telemetry.SpanName.ITEM) as item_span,
            machine.Watch(
                interval_s=flags.waiting_heartbeat_seconds,
                server_pid=server_pid,
                on_tick=_heartbeat(recorder),
            ) as watch,
        ):
            telemetry.item_attributes(item_span, item, run_id=plan.run_id, shard=shard)
            model_started = time.monotonic()
            summary, decision = _two_calls_one_item(
                article,
                settings,
                date=plan.date,
                endpoint=model_endpoint,
                run_id=plan.run_id,
                tracer=tracer,
                recorder=recorder,
            )
            summarize_ms = int((time.monotonic() - model_started) * 1000)
            # What the stage spent NOT being served: the window check, the
            # prompt render, the parse, the element anchoring and the draw. The
            # two calls report their own prefill and decode, so anything left is
            # this process rather than the server, and a regression in one looks
            # nothing like a regression in the other.
            served = _ms(recorder.get("label_ms")) + _ms(recorder.get("summary_ms"))
            recorder.note(
                summarize_ms=summarize_ms, model_wait_ms=max(summarize_ms - served, 0)
            )
            recorder.stage_done(ItemStage.SUMMARIZE, summarize_ms)
            summary = summary.model_copy(
                update={
                    "duration_ms": int((time.monotonic() - work.started) * 1000),
                    "fetch_ms": work.fetch_ms,
                    "extract_ms": work.extract_ms,
                    "summarize_ms": summarize_ms,
                }
            )
            assemble.write_atomic(items_dir / f"{item.item_id}.summary.json", summary.to_json())
            recorder.note(
                summary_words=len((summary.summary or "").split()),
                model_calls=2 if summary.call_2 is not None else 1,
                stage=ItemStage.SUMMARIZE.value,
                outcome=(
                    ItemOutcome.OK.value
                    if summary.status is SummaryStatus.OK
                    else ItemOutcome.FAILED.value
                ),
                code=summary.failure_code.value if summary.failure_code else None,
                # The shape failure already wrote a detail naming the field and
                # the rule; the summary's own is the generic one behind it. The
                # narrower answer wins, and an item that did not fail carries
                # neither - `detail_cell("")` is the string "unspecified
                # failure", which on a passing row reads as a failure nobody had.
                detail=recorder.get("detail")
                or (
                    telemetry.detail_cell(summary.failure_detail)
                    if summary.failure_detail
                    else None
                ),
                prefill_ms=summary.prefill_ms,
                decode_ms=summary.decode_ms,
                input_tokens=summary.input_tokens,
                output_tokens=summary.output_tokens,
                cached_tokens=summary.cached_tokens,
            )
            if decision is not None:
                assemble.write_atomic(
                    items_dir / f"{item.item_id}{PAYLOAD_SUFFIX}", decision.to_json()
                )
                LOG.info(
                    "item decided id=%s kind=%s state=%s reason=%s decision_ms=%s",
                    item.item_id,
                    decision.kind.value,
                    decision.visual_state.value,
                    decision.none_reason.value if decision.none_reason else "-",
                    decision.decision_ms,
                )
            if summary.status is not SummaryStatus.OK or scorer is None:
                recorder.note(**watch.close().cells())
                finished.append(recorder.done())
                code = str(recorder.get("code") or FailureCode.UNKNOWN.value)
                failures[code] = failures.get(code, 0) + 1
                continue

            seen = article.text or ""
            # The article before the cap, so hhem_full answers a different question
            # from hhem. Falls back to the cut text when nothing was cut away.
            whole = work.source_text or seen
            with tracer.span(telemetry.SpanName.SCORE) as score_span:
                score_started = time.monotonic()
                hhem, hhem_full = dual_score(
                    scorer,  # type: ignore[arg-type]
                    seen_text=seen,
                    full_text=whole,
                    summary=summary.summary or "",
                    evaluation=settings.app.evaluation,
                )
                score_ms = int((time.monotonic() - score_started) * 1000)
                row = score.to_eval_row(
                    item=item,
                    article=article,
                    summary=summary,
                    full_text=whole,
                    premise=seen,
                    hhem=hhem,
                    hhem_full=hhem_full,
                    config=settings.app.evaluation,
                    restatement_ceiling=settings.app.summarize.key_point_restatement_ceiling,
                    date=plan.date,
                    run_id=plan.run_id,
                    scorer_version=scorer_version,
                    scored_at=assemble.utc_now(),
                )
                row = row.model_copy(update={"score_ms": score_ms})
                score_span.set(telemetry.AttrKey.BAND, row.band.value)
            recorder.note(faithfulness_ms=score_ms, stage=ItemStage.PUBLISH.value)
            recorder.stage_done(ItemStage.PUBLISH, score_ms)
            assemble.write_atomic(items_dir / f"{item.item_id}.eval.json", row.to_json())
            _write_evidence(row, premise=seen, summary=summary.summary or "")
            LOG.info(
                "item scored id=%s band=%s fetch=%sms extract=%sms model=%sms score=%sms",
                item.item_id,
                row.band.value,
                work.fetch_ms,
                work.extract_ms,
                summarize_ms,
                score_ms,
            )
            recorder.note(**watch.close().cells())
            finished.append(recorder.done())
    # Every item that was fetched, never reached by the loop above and therefore
    # never closed. Today the loop cannot exit early, so this is empty on every
    # run - and it is what makes an early exit added later say so rather than
    # dropping the items silently.
    for work in ready:
        if work.recorder.get("item_ended_at") is None:
            work.recorder.abandoned("the shard ended before this item ran")
            failures["abandoned"] = failures.get("abandoned", 0) + 1
    itemrecord.shard_done(
        run_id=plan.run_id,
        shard=shard,
        flags=flags,
        now=assemble.utc_now,
        log=LOG,
        items=len(mine),
        failures=failures,
        slowest=_slowest(finished),
    )
    tracer.flush()
    if tracing:
        # Fed by every span (the CollectingSink saw them all), reconciled to the
        # shard's own monotonic wall clock so the item spans plus the residual it
        # leaves add up to it - the invariant roll_up_spans enforces.
        rows = telemetry.roll_up_spans(
            collector.spans(),
            date=plan.date,
            run_id=plan.run_id,
            shard=shard,
            wall_clock_ms=int((time.monotonic() - shard_started) * 1000),
        )
        landed = ledger.append_span_rollup(common.STATE_ROOT, plan.date, rows)
        LOG.info("rolled up spans shard=%s span_rows=%s", shard, landed)


def _write_evidence(row: EvalRow, *, premise: str, summary: str) -> Path:
    """Leave the two texts this row was judged on where a person can read them.

    Outside `items/` on purpose. That directory is downloaded whole by the visual
    planner and by assemble and kept for a day; this one is read by nobody in the
    run, is never committed, and needs to outlive the day so a labeller has time
    to work (`docs/how-to/label-the-faithfulness-queue.md`).
    """
    item = evidence.of(row, premise=premise, summary=summary)
    path = evidence.path_for(_evidence_dir(row.date), item)
    assemble.write_atomic(path, item.to_json())
    return path


def _write_inputs(items_dir: Path, *, inputs: PipelineInputs) -> None:
    """Leave this run's recorded input manifest beside the items it produced.

    The work stage is the only one that can observe these inputs - the weights
    the runtime opened, the build that decoded them, the template the server
    will apply - and its checkout is thrown away when the shard ends. The
    artifact it uploads is this directory, so the manifest travels as a payload
    and `stage_assemble`, which owns the run record, is what hangs it on the run
    (section 1a).

    One name, not one per shard. Every shard of a run observes the same
    configuration and writes the same bytes, so the atomic rename settles it and
    there is nothing to reconcile.
    """
    assemble.write_atomic(
        items_dir / INPUTS_PAYLOAD, canonical_json(inputs.model_dump(mode="json"))
    )


class _TwoCalls(NamedTuple):
    """What one item's pair of calls settled: the summary, and the picture or none.

    `decision` is None when the summary is not publishable. The pipeline has
    never written a decision for an item that carries no summary - `plannable_items`
    skips one - and a decision about a story no reader will see is a payload
    `assemble` would have to throw away.
    """

    summary: Summary
    decision: VisualDecision | None


def _watchlist_slugs(settings: config.Settings) -> dict[str, str]:
    """Every alias this project tracks, folded to the id it groups under.

    The label call names an entity in the item's own words and this is what turns that
    into the slug `Element.entity` groups by. A name the watchlist does not
    carry is a name we do not track yet, and `_judgements` drops it rather than
    minting one.
    """
    return {
        alias.casefold(): slug
        for slug, aliases in settings.watchlist.entity_terms().items()
        for alias in aliases
    }


def _split_the_cost(summary: Summary, one: Completion, two: Completion | None) -> Summary:
    """The item's five numbers, recorded as the calls that really spent them.

    `to_summary` sizes one call and records it in slot 1, because the stage it
    was written for makes one. Here the calls are in hand, so the slots are
    rewritten and the flat five become their sum - which `Summary` enforces, so
    this goes through the contract rather than around it with `model_copy`.

    **A failed summary is stamped too, and the single call does not do that.**
    Both calls really spent what they spent, and an item that failed on its
    length or its shape is exactly the item whose cost a reader of the ledger
    wants: leaving it at zero would make a bad day look like a cheap one.

    **`two` is None when the item died between the calls.** The label call still ran, so
    slot 2 is left empty and the flat five are the label call's alone. The alternative -
    the zeros an unstamped failure records - reads as an item that cost nothing,
    and the items that die here are the expensive ones: a labelling reply is cut
    off precisely because the article was long.
    """
    first = CallCost(
        kind=CallKind.LABEL,
        prefill_ms=one.prefill_ms,
        decode_ms=one.decode_ms,
        input_tokens=one.prompt_tokens,
        output_tokens=one.completion_tokens,
        cached_tokens=min(one.cached_tokens, one.prompt_tokens),
    )
    spent = [first]
    if two is not None:
        spent.append(
            CallCost(
                kind=CallKind.SUMMARIZE_AND_PLAN,
                prefill_ms=two.prefill_ms,
                decode_ms=two.decode_ms,
                input_tokens=two.prompt_tokens,
                output_tokens=two.completion_tokens,
                cached_tokens=min(two.cached_tokens, two.prompt_tokens),
            )
        )
    return Summary.model_validate(
        summary.model_dump(mode="json")
        | {
            "call_1": first.model_dump(mode="json"),
            "call_2": spent[1].model_dump(mode="json") if len(spent) > 1 else None,
            **{
                field: sum(getattr(call, field) for call in spent) for field in COST_FIELDS
            },
        }
    )


def _drawn(
    summary: Summary,
    plan: VisualPlan,
    table: ElementTable,
    *,
    settings: config.Settings,
    date: str,
    stamp: Mapping[str, str],
    run_id: str | None,
) -> VisualDecision:
    """One drafted plan becomes a picture on disk, or the reason it did not.

    The order is row #4's: validate, and only a plan no depth of the ladder can
    rescue is refused. `published_marks` is empty because the depth-0 population
    the floors read is a ledger no row has built, and row #4 decision 8 already
    rules what that means - a floor that cannot be computed is not cleared, so
    the ladder is wired and inert rather than wired and lenient.
    """
    visuals = settings.app.visuals
    rejections = validate_plan(plan, table, visuals=visuals)
    drawable = plan
    if rejections:
        step = visual_planner.downgrade(plan, table, visuals=visuals, published_marks={})
        if step is None:
            return visual_planner.refused_by_the_validator(summary, rejections, **stamp)
        drawable = step.plan
    return render_planned_visual(
        visual_planner.not_drawable_here(
            summary,
            why="the plan passed every check and this build could not draw it",
            **stamp,
        ),
        drawable,
        table,
        public_root=common.PUBLIC_ROOT.parent,
        relpath=asset_relpath(date, summary.item_id),
        visuals=visuals,
        run_id=run_id,
    )


@dataclass(slots=True)
class _Progress:
    """What one item has produced so far, as the walk moves through the nodes.

    Mutable and opened per item on purpose: the sequence is item-major, so
    nothing here outlives the article it was opened for. Each node reads what
    the node before it left, which is the dependency the order exists to honour
    - the summarize-and-plan prompt IS the label prompt plus the label reply,
    so that call cannot be built until the label call has answered and its reply
    has been held to a schema.



    `table` is written twice: the element table the extractor cut, and then the
    same table with the label call's labels anchored into it. One field rather than two
    because the second is the first, corrected - and a node behind this one that
    read the unlabelled copy would be reading a table the model has already
    improved on.
    """

    first: dict[str, Any] | None = None
    one: Completion | None = None
    two: Completion | None = None
    table: ElementTable | None = None
    wants_a_plan: bool = False
    summary: Summary | None = None


#: One node of the sequence, run. It returns nothing when the item may go on,
#: and the answer that ends the item when it may not - which is what `dag.walk`
#: stops on.
_NodeBody = Callable[[dag.CallNode], "_TwoCalls | None"]


def _silent_recorder() -> itemrecord.ItemRecorder:
    """A recorder that collects cells and emits nothing.

    `_two_calls_one_item` is called directly by tests and by the canary runner,
    which have no shard around them to open a real one. Every flag off rather
    than a null object, so the same code path runs and there is no second
    implementation to keep in step (Guardrail #7).
    """
    return itemrecord.ItemRecorder(
        run_id="",
        flags=itemrecord.Flags(
            item_lines=False,
            stage_lines=False,
            waiting_heartbeat_seconds=0,
            capture_prompts=False,
            capture_replies=False,
        ),
        now=assemble.utc_now,
        log=LOG,
    )


def _shape_cells(error: Exception) -> dict[str, Any]:
    """Which field of a reply broke which rule, out of the exception that says so.

    Pydantic already knows both and puts them in `errors()`; until now the stage
    threw that away and logged the class name. `ValidationError` on twenty-two
    items is a count, not a diagnosis, and the reply that would have explained it
    has been discarded by the time anybody reads the row.

    The first error rather than all of them, because the columns are singular and
    a reply that broke five rules broke the first one first. A plain `ValueError`
    carries no structure, so the field and the rule stay empty and `detail`
    carries the message - which is still the whole of what is knowable.
    """
    detail = telemetry.detail_cell(str(error))
    if not isinstance(error, ValidationError):
        return {"detail": detail, "failed_field": None, "failed_rule": None}
    first = next(iter(error.errors()), None)
    if first is None:
        return {"detail": detail, "failed_field": None, "failed_rule": None}
    return {
        "detail": detail,
        "failed_field": ".".join(str(part) for part in first.get("loc", ())) or None,
        "failed_rule": str(first.get("type") or "") or None,
    }


def _split_cells(two: Completion) -> dict[str, Any]:
    """The picture's share of the summarize-and-plan call, apportioned.

    The two halves are decoded one after the other and never at once, so the
    boundary in the bytes is a boundary in time - `calls.split_the_decode` owns
    the arithmetic and this is where its answer lands on the row.

    `visual_plan_ms_is_estimate` is always True and is written anyway. A column
    that is filled only when a number is doubtful reads as clean data on every
    row where somebody forgot it (Guardrail #10).
    """
    split = calls.split_the_decode(two)
    if split is None:
        return {}
    return {
        "visual_plan_ms": split.plan_ms,
        "visual_plan_ms_is_estimate": split.is_estimate,
        "visual_plan_tokens_written": split.plan_tokens,
    }


def _kept_call(
    recorder: itemrecord.ItemRecorder,
    call: str,
    date: str,
    item_id: str,
    prompt: str,
    reply: str | None,
) -> None:
    """Measure one call's text, keep whichever halves the flags allow, and say so.

    Called on the path where the reply never came back as well as the one where
    it did, because a call that timed out is exactly the call whose prompt is
    worth reading - and `reply=None` is what tells the two apart in the record.

    The root is derived from the run directory rather than from the repository,
    so a test that redirects `VAR_ROOT` redirects this with it - the same root
    every other output of this stage is written under.
    """
    kept = capture.of(
        root=_run_dir(date) / common.CAPTURES_DIRNAME,
        item_id=item_id,
        call=call,
        prompt=prompt,
        reply=reply or "",
        keep_prompt=recorder.flags.capture_prompts,
        keep_reply=recorder.flags.capture_replies and reply is not None,
        write=assemble.write_atomic,
    )
    recorder.call_done(call, kept.cells())


def _two_calls_one_item(
    article: Article,
    settings: config.Settings,
    *,
    date: str,
    endpoint: str = DEFAULT_ENDPOINT,
    run_id: str | None = None,
    tracer: telemetry.Tracer | None = None,
    recorder: itemrecord.ItemRecorder | None = None,
) -> _TwoCalls:
    """One article read once, labelled, summarized and drawn - in two adjacent calls.

    **The order is `classify.dag.NODES` and this function does not own it.** The
    sequence is declared once, as data, with each node's decode budget beside
    it, because the window has to hold the whole thing and a sequence assembled
    a statement at a time is a budget nobody ever checks whole. Adding a call
    here is not possible without adding a node there, where the import-time
    guard prices it.

    **An article the sequence cannot hold is refused before the label call is sent.**
    `dag.fits_the_window` sizes the label call's prompt, both decode budgets and the
    seam between the turns against `n_ctx`, and an article over it lands as
    `FailureCode.CONTEXT_EXCEEDED`. Admitting it would cost the picture rather
    than the item: `--no-context-shift` means the decode stops at the wall on an
    ordinary HTTP 200, `recovered_completion` salvages the summary, and the item
    publishes with `window_exhausted` recorded where the picture would have been.
    Refusing it up front is still the better answer, because the whole decode is
    paid for before that reason can be written.

    **Adjacent per item, and that is a correctness rule rather than a layout
    taste.** `models.summarize.inference` pins `n_parallel` to 1, so the server
    holds one cache slot: every label call first and every summarize-and-plan call
    afterwards would evict the prefix before it was reused, on every item, with nothing in any
    log to say so. The summarize-and-plan prompt IS the label prompt plus the label
    reply,
    so the slot answers for the system turn, the article and the reply, and only
    the new turn is prefilled.

    **A labelling reply this build cannot read costs the item rather than
    degrading it, and that is deliberate.** The summarize-and-plan call's prompt replays the label
    call's reply verbatim, and the reason that is safe is that the reply has already
    been held to a closed schema. A reply that did not parse has not been, so
    sending it would put unchecked model text into a prompt on the argument that
    it is probably fine.

    **The two ways that happens are two codes, because they are two fixes.** A
    reply the output budget cut is read off `finish_reason` before anything
    tries to parse it and lands as `labels_truncated`; the budget it met is
    derived from the label call's own grammar. A reply that answered inside its budget
    and still could not be read lands as `bad_shape`. Both lose the item, and
    both are a cell in the census rather than a silence.
    """
    trace = tracer if tracer is not None else silent_tracer()
    kept = recorder if recorder is not None else _silent_recorder()
    model = settings.models.summarize
    inference = model.inference
    model_id = model.id
    # Both calls render their own prompt bytes, so they go to the completions
    # route and never to the chat one - which accepts `response_format` and
    # ignores it, losing the only control that survives an injection.
    rendered_endpoint = completion_url(endpoint)
    timeout = inference.request_timeout_minutes * 60
    generated_at = assemble.utc_now()
    stamp = {
        "model_id": model_id,
        "decided_at": generated_at,
        "version": VisualDecision.schema_version(),
    }

    def failed(no_reply: FailureCode, one: Completion | None = None) -> _TwoCalls:
        """The item, lost, with whatever the run really spent on it.

        `one` is the labelling reply when there was one. Three of the four ways
        this item can die happen after the label call answered, so without it the ledger
        records a zero for a call that ran - and the three are truncation, a
        reply that would not parse, and a second call that never came back.
        """
        summary = summarize.to_summary(
            article,
            None,
            model_id=model_id,
            generated_at=generated_at,
            prompt_config=settings.app.summarize,
            evaluation=settings.app.evaluation,
            no_reply=no_reply,
        )
        return _TwoCalls(summary if one is None else _split_the_cost(summary, one, None), None)

    with trace.span(telemetry.SpanName.SUMMARIZE) as stage_span:
        stage_span.set(telemetry.AttrKey.MODEL_ID, model_id)
        so_far = _Progress()

        def label(_node: dag.CallNode) -> _TwoCalls | None:
            """The label call: the element table, and every label and score over it."""
            with trace.span(telemetry.SpanName.RENDER_PROMPT) as span:
                # A table that cannot re-slice its own output raises here rather
                # than degrading, which is `elements.element_table`'s own ruling:
                # at this point the text is in hand and it is the string the
                # excerpts came from, so a mismatch is this process's arithmetic
                # being wrong on every article that took the same path, not this
                # item being odd.
                table = elements.element_table(article, config=settings.app.elements)
                so_far.table = table
                if not dag.fits_the_window(
                    article,
                    inference,
                    menu_rows=len(table.elements),
                    prompt_config=settings.app.summarize,
                ):
                    LOG.warning(
                        "the sequence would not fit the window id=%s tokens=%s menu=%s",
                        article.item_id,
                        article.token_count,
                        len(table.elements),
                    )
                    return failed(FailureCode.CONTEXT_EXCEEDED)
                first = calls.build_label_request(
                    article,
                    table,
                    model_id=model_id,
                    inference=inference,
                    turns=model.turns,
                    prompt_config=settings.app.summarize,
                )
                so_far.first = first
                rendered = str(first["prompt"])
                first_digest = text_digest(rendered)
                span.set(telemetry.AttrKey.PROMPT_DIGEST, first_digest)
                span.set(telemetry.AttrKey.PROMPT_CHARS, len(rendered))
            one, no_reply = _ask_the_model(
                first,
                article,
                model_id=model_id,
                endpoint=rendered_endpoint,
                timeout=timeout,
                prompt_digest=first_digest,
                run_id=run_id,
                trace=trace,
                turns=model.turns,
                max_think_tokens=inference.max_think_tokens,
            )
            if one is None:
                _kept_call(kept, "label", date, article.item_id, rendered, None)
                return failed(no_reply)
            so_far.one = one
            kept.note(**_call_cells("label", one))
            _kept_call(kept, "label", date, article.item_id, rendered, one.content)
            if one.hit_the_budget:
                LOG.warning(
                    "the labelling reply ran out of its output budget id=%s tokens=%s",
                    article.item_id,
                    one.completion_tokens,
                )
                return failed(FailureCode.LABELS_TRUNCATED, one)

            text = article.text or ""
            try:
                so_far.table = calls.anchored(
                    table,
                    text,
                    calls.parse_label(one.content),
                    config=settings.app.elements,
                    label_source=model_id,
                    entity_slugs=_watchlist_slugs(settings),
                )
            except (ValidationError, ValueError, json.JSONDecodeError) as error:
                # The exception's own message, and the field and the rule it
                # names. Until 2026-09-15 this printed the class name alone -
                # `ValidationError` on 22 items with 22 different causes, which
                # is a count rather than a diagnosis, and the reply that would
                # have explained it was already gone.
                LOG.warning(
                    "the labelling reply did not hold its shape id=%s reason=%s detail=%s",
                    article.item_id,
                    type(error).__name__,
                    telemetry.detail_cell(str(error)),
                )
                kept.note(**_shape_cells(error))
                return failed(FailureCode.BAD_SHAPE, one)
            return None

        def summarize_and_plan(_node: dag.CallNode) -> _TwoCalls | None:
            """The summary and the visual plan, on the label call's own prompt."""
            first, one, labelled = so_far.first, so_far.one, so_far.table
            if first is None or one is None or labelled is None:
                raise TypeError(
                    "the summary node ran without the label call's prompt, reply and anchored "
                    "table - `dag.walk` stops at the first node that ends the item, so "
                    "reaching here means a node returned None after a failure"
                )
            so_far.wants_a_plan = visual_planner.plan_is_reachable(
                labelled, visuals=settings.app.visuals
            )
            with trace.span(telemetry.SpanName.RENDER_PROMPT) as span:
                second = calls.build_summarize_and_plan_request(
                    first,
                    one.content,
                    turns=model.turns,
                    prompt_config=settings.app.summarize,
                    source_words=article.band_source_words,
                    brief=article.brief,
                    plan=so_far.wants_a_plan,
                )
                second_rendered = str(second["prompt"])
                span.set(telemetry.AttrKey.PROMPT_CHARS, len(second_rendered))
            two, no_reply = _ask_the_model(
                second,
                article,
                model_id=model_id,
                endpoint=rendered_endpoint,
                timeout=timeout,
                prompt_digest=text_digest(second_rendered),
                run_id=run_id,
                trace=trace,
                turns=model.turns,
                max_think_tokens=inference.max_think_tokens,
            )
            if two is None:
                _kept_call(kept, "summary", date, article.item_id, second_rendered, None)
                return failed(no_reply, one)
            so_far.two = two
            kept.note(
                run_visual_decision=so_far.wants_a_plan,
                **_call_cells("summary", two),
                **_split_cells(two),
            )
            _kept_call(kept, "summary", date, article.item_id, second_rendered, two.content)

            with trace.span(telemetry.SpanName.PARSE_REPLY) as span:
                half = calls.recovered_completion(two)
                if two.hit_the_budget and half is not None:
                    # The seatbelt the reply shape's field order buys, spent. The
                    # picture is gone either way; without this the summary went
                    # with it.
                    LOG.warning(
                        "the summarize-and-plan reply was cut and its summary recovered "
                        "id=%s tokens=%s",
                        article.item_id,
                        two.completion_tokens,
                    )
                # Filled on every item and not only on the cut ones, because
                # `recovered` answers "was this summary salvaged" and an empty
                # cell makes an ordinary item and an unmigrated row look alike.
                kept.note(recovered=bool(two.hit_the_budget and half is not None))
                so_far.summary = _split_the_cost(
                    summarize.to_summary(
                        article,
                        half if half is not None else two,
                        model_id=model_id,
                        generated_at=generated_at,
                        prompt_config=settings.app.summarize,
                        evaluation=settings.app.evaluation,
                        no_reply=no_reply,
                        thinking=model.turns.thinks,
                    ),
                    one,
                    two,
                )
                telemetry.summary_attributes(span, so_far.summary)
            return None

        bodies: Mapping[dag.CallName, _NodeBody] = {
            dag.CallName.LABEL: label,
            dag.CallName.SUMMARIZE_AND_PLAN: summarize_and_plan,
        }
        lost = dag.walk(lambda node: bodies[node.name](node))
        if lost is not None:
            return lost
        summary, two, labelled = so_far.summary, so_far.two, so_far.table
        wants_a_plan = so_far.wants_a_plan
        if summary is None or two is None or labelled is None:
            raise TypeError(
                "every node of the sequence answered and the item is still empty - "
                "a node returned None without leaving its product behind"
            )
        telemetry.summary_attributes(stage_span, summary)

    if summary.status is not SummaryStatus.OK:
        return _TwoCalls(summary, None)

    with trace.span(telemetry.SpanName.VISUAL_PLANNER) as span:
        # The picture's own clock, and never the pair's. `decision_ms` means the
        # planner call plus the render, and under this flag the planner call is
        # the summarize-and-plan call - which also wrote the summary. Charging the picture for that
        # would make the console's slowest-decision reading the slowest ITEM.
        started = time.monotonic()
        decision = _decide_the_visual(
            summary,
            article,
            two,
            labelled,
            settings=settings,
            date=date,
            stamp=stamp,
            wants_a_plan=wants_a_plan,
            run_id=run_id,
            recorder=kept,
        )
        decision = decision.model_copy(
            update={"decision_ms": int((time.monotonic() - started) * 1000)}
        )
        span.set(telemetry.AttrKey.MODEL_ASKED, decision.asked_the_model)
        span.set(telemetry.AttrKey.DRAFTED_CHART, decision.drafted_chart)
        span.set(telemetry.AttrKey.VISUAL_KIND, decision.kind.value)
        span.set(telemetry.AttrKey.VISUAL_STATE, decision.visual_state.value)
    return _TwoCalls(summary, decision)


def _decide_the_visual(
    summary: Summary,
    article: Article,
    two: Completion,
    table: ElementTable,
    *,
    settings: config.Settings,
    date: str,
    stamp: Mapping[str, str],
    wants_a_plan: bool,
    run_id: str | None,
    recorder: itemrecord.ItemRecorder | None = None,
) -> VisualDecision:
    """Which of the routes to a picture, or to none, this reply took.

    Six outcomes and five `none_reason` members, because the member names the
    gate rather than the call site: a reply whose plan half will not hold
    `VisualPlan`'s own rules and a plan the compiler could not draw are one
    answer to an operator - a plan was drafted and this build refuses it.

    **A cut reply is two different findings and the server reports one.** Under
    `--no-context-shift` a decode that runs into the end of the window stops
    exactly as a decode that spends its output budget does, on an ordinary HTTP
    200 with `finish_reason` of `length`. Only the arithmetic tells them apart,
    and it needs nothing this function does not already hold: the server counted
    the prompt, and the summarize-and-plan call's budget is derived from its own grammar. Less room
    left than the grammar may write means the window was the wall.
    """
    if not wants_a_plan:
        return visual_planner.suppressed_by_the_gate(summary, **stamp)
    if two.hit_the_budget:
        inference = settings.models.summarize.inference
        asked_for = calls.summarize_and_plan_budget_tokens(settings.app.summarize)
        if two.prompt_tokens + asked_for > inference.n_ctx:
            LOG.warning(
                "the window stopped the plan id=%s prompt=%s budget=%s n_ctx=%s",
                summary.item_id,
                two.prompt_tokens,
                asked_for,
                inference.n_ctx,
            )
            return visual_planner.plan_lost_to_the_window(summary, **stamp)
        return visual_planner.plan_lost_to_the_budget(summary, **stamp)
    try:
        reply = calls.parse_summarize_and_plan(
            two.content,
            settings.app.summarize,
            source_words=article.band_source_words,
            brief=article.brief,
        )
    except (ValidationError, ValueError, json.JSONDecodeError) as error:
        # The message, the field and the rule, for the reason written over the
        # labelling reply's own shape failure: a class name is a count and not a
        # diagnosis, and the reply it came from is already gone.
        LOG.warning(
            "the plan half did not hold its shape id=%s reason=%s detail=%s",
            summary.item_id,
            type(error).__name__,
            telemetry.detail_cell(str(error)),
        )
        if recorder is not None:
            recorder.note(**_shape_cells(error))
        return visual_planner.not_drawable_here(
            summary,
            why="the plan half of the reply did not hold the shape a plan has to hold",
            **stamp,
        )
    plan = reply.visual
    if plan is None or plan.decision is not PlanDecision.VISUAL:
        return visual_planner.declined_by_the_model(
            summary, why=plan.why if plan is not None else "the reply carried no plan", **stamp
        )
    return _drawn(summary, plan, table, settings=settings, date=date, stamp=stamp, run_id=run_id)
