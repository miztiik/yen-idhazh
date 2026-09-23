"""Fetch, extract, summarize and score one item at a time, writing as it goes.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

from idhazh import (
    assemble,
    config,
    extract,
    ledger,
    run_context,
    summarize,
    telemetry,
)
from idhazh.classify import calls
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import ServerJob, canonical_json
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX
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
)
from idhazh.llm.server import (
    derive_turn_markers,
    props,
    request_timeout_seconds,
    resolve_endpoint,
    setting,
    window,
)
from idhazh.sanitize import SANITIZER_VERSION
from idhazh.stages import common
from idhazh.stages.common import (
    INPUTS_PAYLOAD,
    LOG,
    Fetcher,
    _fetch_one,
    _run_dir,
    shard_of,
)
from idhazh.stages.two_calls import two_calls_one_item
from idhazh.telemetry import census, host
from idhazh.telemetry.record import Flags, ItemRecorder, persist, shard_done


def _evidence_dir(date: str) -> Path:
    return common.EVIDENCE_ROOT / date


def _trace_id(run_id: str, item: PlannedItem) -> str:
    """One item on one run. The work stage opens it twice and the planner opens it again."""
    return f"{run_id}-{item.item_id}"


def trace_sink(
    settings: config.Settings, *, run_id: str, shard: int
) -> telemetry.SpanSink:
    """Where this shard's spans go: nowhere, or a committed file.

    A file, and nothing else. Nothing this pipeline traces leaves the machine
    that traced it, so a run needs no secret and reaches no third party
    (Guardrail #1, CLAUDE.md section 1b).

    The file is the committed trace under `state/traces/`, not a gitignored one,
    so a recent run stays openable from the repository; `retention.prune_traces`
    bounds the rolling window (CLAUDE.md section 1b, docs/concepts/telemetry.md).

    The file carries this writer's identity, so two shards and two attempts at
    one shard never open one path.
    """
    if not settings.app.observability.tracing_enabled:
        return telemetry.NullSink()
    return telemetry.FileSink(
        telemetry.committed_trace_path(
            common.STATE_ROOT,
            run_id=run_id,
            attempt=run_context.run_attempt(),
            job=ServerJob.WORK,
            shard=shard,
        )
    )


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
    recorder: ItemRecorder


def _summarize_band_sort_key(work: _FetchedWorkItem, settings: config.Settings) -> tuple[int, int]:
    band = settings.app.summarize.band_for(work.article.band_source_words)
    return band.min_source_words, work.original_index


def _shard_cells(
    settings: config.Settings,
    *,
    shard: int,
    shard_item_count: int,
    facts: host.HostFacts,
) -> dict[str, Any]:
    """What was true of this shard before it read a single article.

    Read once and noted on every item, because the question these answer is
    asked of ONE row: a reader looking at a 475,890 ms item wants the context
    size and the output budget that item ran under, and a shard-grain ledger
    somewhere else makes them join two files to get it.

    **Every one of them is config except the three `facts` carries**, so none of
    them is a measurement. They are the settings the run was given, which is
    exactly what a person comparing two runs needs - the readings are the machine
    cells beside them. The processor and the runner label come from the one
    `host_facts` call this shard's counters row reads as well, so the two rows
    cannot name two different machines. `job` rides with them for the same
    reason: with `shard` it is the key that reaches this job's host record, and a
    key filled from two places is a key that can disagree with itself.
    """
    model = settings.models.summarizer
    return {
        "shard": shard,
        "shard_item_count": shard_item_count,
        **facts.shard_cells(),
        "model_id": model.id,
        "model_quantisation": model.quantisation,
        "n_ctx_configured": window(model.server),
        "n_parallel": setting(model.server, "n_parallel"),
        "n_threads": setting(model.server, "n_threads"),
        "n_batch": setting(model.server, "n_batch"),
        "weights_pinned": setting(model.server, "load_mode") == "mmap+mlock",
        "label_budget_tokens": calls.label_budget_tokens(),
        "summary_budget_tokens": calls.summarize_and_plan_budget_tokens(settings.app.summarize),
        "temperature": model.sampling.get("temperature"),
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


def _ms(cell: object) -> int:
    """One duration cell as a number, and zero where the stage never filled it."""
    return cell if isinstance(cell, int) else 0


def _heartbeat(recorder: ItemRecorder) -> Callable[[float], None]:
    """The tick this item's watch calls while a model call is in flight.

    A function that closes over one recorder rather than a lambda in the loop,
    because a lambda in a loop closes over the LOOP VARIABLE - every item's
    watch would tick the last item's record, and a heartbeat naming the wrong
    item is worse than no heartbeat.
    """

    def tick(seconds: float) -> None:
        recorder.waiting(seconds)

    return tick


def _failure_code(summary: Summary) -> FailureCode:
    """The code a refused summary is filed under, and never nothing.

    `unknown` where the stage left its own refusal untyped. A failed row with no
    code at all is a row the census cannot be built from, and it is also the
    least useful thing a failure can say to the person reading it.
    """
    return summary.failure_code or FailureCode.UNKNOWN


def _failure_detail(recorder: ItemRecorder, summary: Summary) -> str | None:
    """What a refused item says about itself, narrowest answer first.

    The shape failure already named the field and the rule it broke, so its
    detail beats the generic message sitting behind it. An untyped refusal has
    to say something either way - `unknown` with an empty detail is a row the
    census refuses - so the last answer names the fault as an untyped one.
    """
    recorded = recorder.get("detail")
    if isinstance(recorded, str) and recorded:
        return recorded
    if summary.failure_detail:
        return telemetry.detail_cell(summary.failure_detail)
    if _failure_code(summary) is FailureCode.UNKNOWN:
        return telemetry.detail_cell("summary failure was not typed")
    return None


def _slowest(finished: list[ItemHealthRow]) -> dict[str, Any] | None:
    """The item that cost the shard most, and enough to find it again.

    Four cells and not the row: a shard record carrying 123 columns of one item
    buries the totals beside it, and the item's own completion record is already
    in the log for anyone who wants the rest.

    **The address is the URL and the source, never the title.** A title is
    fetched text and a log line is read by a person, which is the one place
    untrusted text most wants to be believed (Guardrail #11).
    """
    if not finished:
        return None
    worst = max(finished, key=lambda row: row.item_total_ms or 0)
    return {
        "item_id": worst.item_id,
        "canonical_url": worst.canonical_url,
        "source_id": worst.source_id,
        "item_total_ms": worst.item_total_ms,
    }


def stage_work(
    plan: RunPlan,
    *,
    settings: config.Settings,
    scorer: object | None,
    shard: int = 0,
    shards: int = 1,
    fetcher: Fetcher | None = None,
    model_endpoint: str | None = None,
) -> None:
    """Fetch, extract, summarize and score one item at a time, writing as it goes."""
    model_endpoint = model_endpoint or resolve_endpoint(settings.app.model_server.base_url)
    shard_started = time.monotonic()
    tracing = settings.app.observability.tracing_enabled
    collector = telemetry.CollectingSink()
    base_sink = trace_sink(settings, run_id=plan.run_id, shard=shard)
    tracer = telemetry.Tracer(
        sink=telemetry.FanOut((base_sink, collector)) if tracing else base_sink,
        now=assemble.utc_now,
    )
    read_url = fetcher or common.live_fetcher(settings, tracer=tracer)
    model = settings.models.summarizer
    observed = props(model_endpoint, timeout=request_timeout_seconds(model))
    markers = derive_turn_markers(
        model_endpoint, entry=model, timeout=request_timeout_seconds(model)
    )
    inputs = build_inputs(
        model=model,
        model_sha256=model.sha256,
        server=model.server,
        sampling=model.sampling,
        truncation_cap_tokens=settings.app.extract.truncation_cap_tokens,
        runtime_build=runtime_build(base_url=settings.app.model_server.base_url),
        chat_template=str(observed.get("chat_template") or UNRECORDED_TEMPLATE),
        # The two calls render their own bytes, so the chat template above no
        # longer reaches what the model reads and the markers the server derived
        # do. Handing over the rendered pair is what digests the envelope, all
        # four prompt files and the turn order together.
        prompt=calls.prompt_inputs(settings.app.summarize, markers=markers),
        output_schema=summarize.output_schema_text(settings.app.summarize),
        runner_class=runner_class(),
        extractor_version=extract.EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
        markers=markers,
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
    flags = Flags.of(settings.app.logging)
    # Read once per shard and noted on every item. The process table scan and
    # the CPU model read are each a few file opens; doing them per item would be
    # 80 scans for an answer that cannot change inside a shard.
    server_pid = host.llama_server_pid()
    shard_facts = host.host_facts(job=ServerJob.WORK)
    shard_cells = _shard_cells(
        settings, shard=shard, shard_item_count=len(mine), facts=shard_facts
    )
    failures: dict[str, int] = {}
    finished: list[ItemHealthRow] = []
    ready: list[_FetchedWorkItem] = []
    for original_index, item in enumerate(mine):
        started = time.monotonic()
        recorder = ItemRecorder(
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
            fetched = _fetch_one(item, settings, read_url, tracer)
        article, source_text = fetched.article, fetched.source_text
        fetch_ms, extract_ms = fetched.fetch_ms, fetched.extract_ms
        # One reading of the pair, split across the two cells the stage records
        # separately, so the stage lines and the census row cannot disagree about
        # which milliseconds belonged to which half. The fetch's own split -
        # handshake, first byte, robots, retries - rides in beside them, so a
        # slow item says which of those it was rather than only that it was slow.
        recorder.note(
            fetch_ms=fetch_ms,
            extract_ms=extract_ms,
            **fetched.timings.cells(),
            **_article_cells(article),
        )
        recorder.stage_done(ItemStage.FETCH, fetch_ms)
        recorder.stage_done(ItemStage.EXTRACT, extract_ms)
        assemble.write_atomic(items_dir / f"{item.item_id}.article.json", article.to_json())
        if article.status is not ArticleStatus.OK:
            LOG.info("item degraded id=%s reason=%s", item.item_id, article.failure_detail)
            # The census's own reading of this article rather than a second one
            # here. This branch named `extract` whatever had really failed, so a
            # fetch code landed on an extract row - a pairing the census row
            # refuses - and an article with no typed code left the record saying
            # an item failed for no reason at all.
            code, stopped_at, http_status, untyped = census.classify_article(article)
            recorder.note(
                stage=stopped_at.value,
                outcome=ItemOutcome.FAILED.value,
                code=code.value,
                http_status=http_status,
                detail=telemetry.detail_cell(article.failure_detail)
                if article.failure_detail
                else untyped,
            )
            recorded = recorder.done()
            persist(items_dir, recorded)
            finished.append(recorded)
            failures[code.value] = failures.get(code.value, 0) + 1
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

    # The worker's own clock. `run.shard_timeout_minutes` is the platform's, and
    # a job killed on that one uploads nothing - so every item this shard had
    # already finished dies with the ones it never started. Stopping here
    # instead means the shard writes what it has and says what it skipped.
    #
    # The gate is the slowest item this shard has already finished, which needs
    # no estimate and calibrates itself to whichever processor the shard drew.
    # Before the first item finishes it is zero, so the first item always runs.
    deadline = shard_started + max(
        settings.app.run.shard_timeout_minutes - settings.app.run.shard_wrap_up_minutes, 0
    ) * 60
    slowest_item_s = 0.0

    for work in sorted(ready, key=lambda candidate: _summarize_band_sort_key(candidate, settings)):
        left_s = deadline - time.monotonic()
        if left_s < slowest_item_s:
            LOG.warning(
                "the shard stopped starting items shard=%s left_s=%.0f slowest_item_s=%.0f "
                "not_started=%s",
                shard,
                left_s,
                slowest_item_s,
                sum(1 for rest in ready if rest.recorder.get("item_ended_at") is None),
            )
            break
        item_started = time.monotonic()
        item = work.item
        article = work.article
        recorder = work.recorder
        # The gap between the fetch loop finishing this item and the model loop
        # reaching it. The two loops run in different orders, so this is real
        # time an item spent on a list and it is the only place it is visible.
        # Its own fetch and extract are subtracted because both are work rather
        # than waiting, and `parked` takes the same number back out of the item
        # clock so a shard's items do not each count the queue ahead of them.
        queue_wait_ms = (
            int((time.monotonic() - work.started) * 1000) - work.fetch_ms - work.extract_ms
        )
        recorder.note(queue_wait_ms=queue_wait_ms)
        recorder.parked(queue_wait_ms)
        with (
            tracer.trace(_trace_id(plan.run_id, item)),
            tracer.span(telemetry.SpanName.ITEM) as item_span,
            host.Watch(
                interval_s=flags.waiting_heartbeat_seconds,
                server_pid=server_pid,
                on_tick=_heartbeat(recorder),
            ) as watch,
        ):
            telemetry.item_attributes(item_span, item, run_id=plan.run_id, shard=shard)
            model_started = time.monotonic()
            summary, decision, _, _ = two_calls_one_item(
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
            # prompt render, the parse, the element anchoring and the draw,
            # plus the transport around each request. The server's own two
            # clocks are what it claims for itself, so anything left is not the
            # decoder, and a regression in one looks nothing like a regression
            # in the other.
            #
            # The four slot cells and not `label_ms` plus `summary_ms`: those
            # two became our stopwatch around each request on 2026-09-16, and
            # subtracting them would leave this cell holding local work alone
            # under a name that says model wait.
            served = sum(
                _ms(recorder.get(cell))
                for cell in (
                    "label_prefill_ms",
                    "label_decode_ms",
                    "summary_prefill_ms",
                    "summary_decode_ms",
                )
            )
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
            published = summary.status is SummaryStatus.OK
            # A call that never returned is absent on both sides rather than
            # zero: the census row holds the flat five to the sum over the slots
            # it records, so a total beside no recorded call is a row that
            # cannot be built at all.
            spent = [call for call in (summary.call_1, summary.call_2) if call is not None]
            recorder.note(
                summary_words=len((summary.summary or "").split()),
                model_calls=len(spent) or None,
                stage=ItemStage.SUMMARIZE.value,
                outcome=(ItemOutcome.OK if published else ItemOutcome.FAILED).value,
                code=None if published else _failure_code(summary).value,
                # The shape failure already wrote a detail naming the field and
                # the rule; the summary's own is the generic one behind it. The
                # narrower answer wins, and an item that published carries
                # neither - a detail on an `ok` row reads as a failure nobody
                # had, which is why the census row refuses one.
                detail=None if published else _failure_detail(recorder, summary),
                prefill_ms=summary.prefill_ms if spent else None,
                decode_ms=summary.decode_ms if spent else None,
                input_tokens=summary.input_tokens if spent else None,
                output_tokens=summary.output_tokens if spent else None,
                cached_tokens=summary.cached_tokens if spent else None,
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
                recorded = recorder.done()
                persist(items_dir, recorded)
                finished.append(recorded)
                tally = str(recorder.get("code") or FailureCode.UNKNOWN.value)
                failures[tally] = failures.get(tally, 0) + 1
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
            recorded = recorder.done()
            persist(items_dir, recorded)
            finished.append(recorded)
        slowest_item_s = max(slowest_item_s, time.monotonic() - item_started)
    # Every item that was fetched and never reached by the loop above, because
    # the worker's clock ran out before it could start work it could finish.
    #
    # The refusal is written as a summary payload as well as a record, because
    # the census row is built from the payloads (`telemetry.classify_item`) and
    # not from these records. An article with no summary beside it is filed
    # `unknown` carrying "summary payload missing" - a throughput problem
    # reported as a mystery, which is the reading `shard_out_of_time` exists to
    # replace. Nothing is asked of the model here; the cost cells stay null
    # because no call returned.
    for work in ready:
        if work.recorder.get("item_ended_at") is None:
            abandoned = summarize.to_summary(
                work.article,
                None,
                model_id=model.id,
                generated_at=assemble.utc_now(),
                no_reply=FailureCode.SHARD_OUT_OF_TIME,
            ).model_copy(
                update={
                    "duration_ms": int((time.monotonic() - work.started) * 1000),
                    "fetch_ms": work.fetch_ms,
                    "extract_ms": work.extract_ms,
                }
            )
            assemble.write_atomic(
                items_dir / f"{work.item.item_id}.summary.json", abandoned.to_json()
            )
            work.recorder.note(
                stage=ItemStage.SUMMARIZE.value,
                outcome=ItemOutcome.FAILED.value,
                code=FailureCode.SHARD_OUT_OF_TIME.value,
                detail=telemetry.detail_cell(abandoned.failure_detail)
                if abandoned.failure_detail
                else None,
            )
            persist(
                items_dir,
                work.recorder.abandoned(
                    "the shard ran out of its own clock before this item ran"
                ),
            )
            failures["abandoned"] = failures.get("abandoned", 0) + 1
    shard_done(
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
        # Into this shard's own segment, not into the month head every other
        # shard opens. Eight shards folding one month file is the collision the
        # segment store exists to stop, and the attempt is in the name, so a
        # re-run corrects its first try rather than adding a second fold of the
        # same spans. `stage_compact` merges them into the month the rows name.
        landed = ledger.write_segment(
            common.STATE_ROOT,
            ledger.SegmentLedger.SPAN_ROLLUP,
            rows,
            run_id=plan.run_id,
            attempt=run_context.run_attempt(),
            job=ServerJob.WORK,
            shard=shard,
        )
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
