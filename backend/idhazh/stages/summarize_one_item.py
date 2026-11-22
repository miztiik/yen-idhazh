"""How does one article become a summary and a picture, in one call?

The model reads the item once. The same reply carries the summary first, then
its chart choice when source readings are available.
"""


from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from idhazh import (
    assemble,
    atomic_write,
    capture,
    config,
    elements,
    summarize,
    telemetry,
    visual_planner,
)
from idhazh.anchor_mentions import Mention
from idhazh.classify import calls, dag
from idhazh.classify.plan_visual_request import chart_forms
from idhazh.classify.resolve_visual_choice import resolve_visual_choice
from idhazh.contracts.article import Article
from idhazh.contracts.call_cost import COST_FIELDS, CallCost, CallKind
from idhazh.contracts.element import ElementKind, ElementTable
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual import VisualPlan, VisualType
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.contracts.visual_telemetry import ValidatorCheck
from idhazh.fingerprint import (
    text_digest,
)
from idhazh.llm.server import (
    Completion,
    completion_url,
    derive_turn_markers,
    request_timeout_seconds,
    resolve_endpoint,
    response_limit,
    window,
)
from idhazh.render import (
    asset_relpath,
    can_compile,
    render_planned_visual,
)
from idhazh.stages import common
from idhazh.stages.common import (
    LOG,
    _ask_the_model,
    _run_dir,
    silent_tracer,
)
from idhazh.telemetry.record import Flags, ItemRecorder
from idhazh.visual_validator import Rejection, validate_plan

#: The column prefix the one call writes under. `ItemHealthRow` names its two call
#: slots after the calls the stage once made: `label_*` for the first and `summary_*`
#: for the second. The call that remains is the second one, so the `summary_*` series
#: stays one continuous series across the change and `label_*` stays empty.
CALL_SLOT = "summary"



def _call_cells(slot: str, kind: CallKind, reply: Completion, *, wall_ms: int) -> dict[str, Any]:
    """One model call's numbers, under the slot's own column names.

    Six the server reported, one wall clock, two rates and a cache share, under
    the kind of call that spent them. **The kind is passed rather than read off
    the slot**: a slot says which call ran first and only the kind says what it
    was. It also fills or the census row cannot be built - `ItemHealthRow` holds
    a slot to filling whole or not at all, and a slot with five numbers and no
    kind is half a call.

    **`{slot}_ms` is our own stopwatch around the request, and the wait is in
    it.** It used to be `prefill_ms + decode_ms`, which is a column that agrees
    with its two neighbours by construction and therefore measures nothing they
    do not: subtracting them from it gave zero on every row, so a server that
    made an item queue read exactly like a server that answered at once. What
    the subtraction gives now is the wait - transport, JSON, and any time the
    server spent that its own `timings` block does not name.

    The rates are derived here rather than left to whoever reads the row,
    because a reader deriving them is a reader who has to know which
    milliseconds go with which token count - and the regression this exists to
    catch is exactly a decode rate moving while a wall clock stayed put. They
    are taken over the server's own two clocks and not over `wall_ms`: a rate
    that charges the queue to the decoder reads as a slow model.

    **The prefill rate counts only the tokens the server really evaluated.**
    Dividing the whole prompt by the prefill clock counts a cache hit as work
    done: the summarize call reported 787 tokens a second on 2026-09-14 while
    evaluating 52 real tokens in 6.2 seconds, which is 8.4. The cache share is
    the column that says how much was skipped, so a rate that also claims it is
    the same number twice (Guardrail #10).
    """
    prefill_s = reply.prefill_ms / 1000
    decode_s = reply.decode_ms / 1000
    cached = min(reply.cached_tokens, reply.prompt_tokens)
    evaluated = reply.prompt_tokens - cached
    return {
        f"{slot}_kind": kind.value,
        f"{slot}_prefill_ms": reply.prefill_ms,
        f"{slot}_decode_ms": reply.decode_ms,
        f"{slot}_input_tokens": reply.prompt_tokens,
        f"{slot}_output_tokens": reply.completion_tokens,
        f"{slot}_cached_tokens": cached,
        f"{slot}_finish_reason": reply.finish_reason,
        f"{slot}_ms": wall_ms,
        f"{slot}_cache_pct": (
            round(100 * cached / reply.prompt_tokens, 2) if reply.prompt_tokens else None
        ),
        f"{slot}_prefill_tokens_per_s": (
            round(evaluated / prefill_s, 2) if prefill_s > 0 else None
        ),
        f"{slot}_decode_tokens_per_s": (
            round(reply.completion_tokens / decode_s, 2) if decode_s > 0 else None
        ),
    }


def _item_cells(reply: Completion) -> dict[str, Any]:
    """The three cells that belong to the ITEM rather than to its call.

    Which prefix-cache slot served the item, what that slot held once the item's
    prompt had been prefilled, and whether the call read anything out of it. The
    row holds one set of them, and the item's one call is the only call whose slot
    was last touched by the item BEFORE this one, so its reuse says how the system
    turn the items share fared across the boundary between two items. They are
    read straight off the reply - `server.parse_completion` derives them, this
    carries them.
    """
    return {
        "slot_id": reply.slot_id,
        "kv_tokens_at_start": reply.slot_tokens_held,
        "prefix_shared_with_previous": reply.prefix_reused,
    }


class _ItemResult(NamedTuple):
    """What one item's call settled: the summary, and the picture or none.

    `decision` is None when the summary is not publishable. The pipeline has
    never written a decision for an item that carries no summary - `plannable_items`
    skips one - and a decision about a story no reader will see is a payload
    `assemble` would have to throw away.

    **The reply comes back with it, for the caller that is measuring this path
    rather than publishing from it.** `_recorded_as_the_one_call` folds the call's
    five numbers into the summary, which is the right shape for a ledger row and
    the wrong one for a gate: a sum cannot say whether a decode was cut, and the
    reasoning channel leaves no trace in it at all. It is None when the call never
    happened, so a caller reads what ran and never a zero for a call that did.
    """

    summary: Summary
    decision: VisualDecision | None
    reply: Completion | None = None


def _cost(kind: CallKind, reply: Completion) -> CallCost:
    """One reply's five numbers, under the kind of call that spent them.

    The kind is passed rather than read off the slot the reply arrived in: a
    slot says which call ran first and only the kind says what it was.
    """
    return CallCost(
        kind=kind,
        prefill_ms=reply.prefill_ms,
        decode_ms=reply.decode_ms,
        input_tokens=reply.prompt_tokens,
        output_tokens=reply.completion_tokens,
        cached_tokens=min(reply.cached_tokens, reply.prompt_tokens),
    )


def _recorded_as_the_one_call(summary: Summary, reply: Completion) -> Summary:
    """The item's five numbers, recorded as the call that really spent them.

    `to_summary` sizes one call and records it in slot 1 under the kind the
    standalone summarizer has. Here the call is the digest's own, and it is
    recorded in slot 2 with slot 1 empty: the call that remains is the second one
    of the two this stage used to make, so the `summary_*` series stays continuous
    across the change and `label_*` goes quiet. The flat five are that call's, and
    `Summary` enforces that, so this goes through the contract rather than around
    it with `model_copy`.

    **A failed summary is stamped too.** The call really spent what it spent, and
    an item that failed on its shape is exactly the item whose cost a reader of
    the ledger wants: leaving it at zero would make a bad day look like a cheap
    one. An item whose call never returned has no reply and is not stamped at all.
    """
    cost = _cost(CallKind.SUMMARIZE_AND_PLAN, reply)
    return Summary.model_validate(
        summary.model_dump(mode="json")
        | {
            "call_1": None,
            "call_2": cost.model_dump(mode="json"),
            **{field: getattr(cost, field) for field in COST_FIELDS},
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
    render_root: Path | None = None,
    published_marks: Mapping[VisualType, Sequence[int]] | None = None,
) -> VisualDecision:
    """Validate and deliver one typed request, preserving its original choice on refusal."""
    visuals = settings.app.visuals
    if visuals.downgrade_enabled and published_marks is None:
        raise ValueError("enabled visual downgrade requires the shard's published mark population")
    if plan.type is None:
        raise ValueError("a typed visual request requires its original type")
    outcome: dict[str, object] = {
        "planned_type": plan.type,
        "downgrade_depth": 0,
        "deepest_downgrade_depth": 0,
    }
    if visuals.type_selection_enabled and plan.type not in visuals.select_types():
        refused = visual_planner.not_drawable_here(
            summary, why=f"{plan.type.value} is not selected in visuals.enabled_types", **stamp
        )
        return VisualDecision.model_validate(refused.model_dump(mode="json") | outcome)
    rejections = validate_plan(plan, table, visuals=visuals)
    if rejections:
        outcome["rejection_reason"] = rejections[0].check
    drawable = plan
    reason = plan.why
    if rejections or not can_compile(plan.type):
        replacement_rejections: list[Rejection] = []
        cause = (
            "the plan was refused on "
            + ", ".join(rejection.check.value for rejection in rejections)
            if rejections else f"{plan.type.value} has no compiler"
        )
        downgrade_evidence = visual_planner.DowngradeEvidence()
        step = (
            visual_planner.downgrade(
                plan,
                table,
                visuals=visuals,
                published_marks=published_marks,
                rejected=replacement_rejections,
                evidence=downgrade_evidence,
            )
            if published_marks is not None and visuals.downgrade_enabled else None
        )
        outcome["deepest_downgrade_depth"] = downgrade_evidence.deepest_depth
        if downgrade_evidence.gate_floor_applied is not None:
            outcome["gate_floor_applied"] = downgrade_evidence.gate_floor_applied
        if step is None:
            if any(
                rejection.check is ValidatorCheck.STACKED_BAR_EXHAUSTIVE
                for rejection in replacement_rejections
            ):
                cause += (
                    "; stacked_bar fallback was refused on "
                    f"{ValidatorCheck.STACKED_BAR_EXHAUSTIVE.value}"
                )
            refused = visual_planner.not_drawable_here(
                summary,
                why=f"{cause}; no safe supported replacement cleared validation and its floor"
                if visuals.downgrade_enabled else f"{cause}; replacement is switched off",
                **stamp,
            )
            return VisualDecision.model_validate(refused.model_dump(mode="json") | outcome)
        drawable = step.plan
        outcome["downgrade_depth"] = step.depth
        reason = (
            f"{cause}; replaced with {drawable.type} at depth {step.depth}; "
            f"mark-count floor {step.floor}"
        )
    return render_planned_visual(
        VisualDecision.model_validate(
            visual_planner.not_drawable_here(summary, why=reason, **stamp).model_dump(mode="json")
            | outcome
        ),
        drawable,
        table,
        public_root=render_root if render_root is not None else common.PUBLIC_ROOT.parent,
        relpath=asset_relpath(date, summary.item_id),
        visuals=visuals,
        run_id=run_id,
    )


def _silent_recorder() -> ItemRecorder:
    """A recorder that collects cells and emits nothing.

    `summarize_one_item` is called directly by tests and by the replay utility,
    which have no shard around them to open a real one. Every flag off rather
    than a null object, so the same code path runs and there is no second
    implementation to keep in step (Guardrail #7).
    """
    return ItemRecorder(
        run_id="",
        flags=Flags(
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
    """The first native field/rule refusal, without rejected values or unknown keys."""
    if isinstance(error, PydanticCustomError):
        visual_field = f"visual.{error.context['field']}" if error.context else "visual"
        detail = f"{visual_field}: {error.type}; {error.message()}"
        return {
            "detail": telemetry.detail_cell(detail),
            "failed_field": visual_field,
            "failed_rule": error.type,
        }
    detail = type(error).__name__
    if not isinstance(error, ValidationError):
        return {"detail": detail, "failed_field": None, "failed_rule": None}
    first = next(iter(error.errors(include_input=False, include_url=False)), None)
    if first is None:
        return {"detail": detail, "failed_field": None, "failed_rule": None}
    rule = first["type"]
    location = first["loc"]
    if (
        len(location) > 1 and location[0] == "visual"
        and location[1] in VisualType._value2member_map_
    ):
        location = (location[0], *location[2:])
    field = first.get("ctx", {}).get("field")
    if isinstance(field, str):
        location = (*location, field)
    elif rule == "extra_forbidden":
        location = location[:-1]
    failed_field = ".".join(str(part) for part in location) or None
    detail = f"{failed_field or 'reply'}: {rule}"
    if isinstance(field, str):
        detail += f"; {first['msg']}"
    return {
        "detail": telemetry.detail_cell(detail),
        "failed_field": failed_field,
        "failed_rule": rule,
    }


def _split_cells(split: calls.DecodeSplit | None) -> dict[str, Any]:
    """The picture's share of the summarize-and-plan call, apportioned.

    The two halves are decoded one after the other and never at once, so the
    boundary in the bytes is a boundary in time - `calls.split_the_decode` owns
    the arithmetic and this is where its answer lands on the row.

    `visual_plan_ms_is_estimate` is always True and is written anyway. A column
    that is filled only when a number is doubtful reads as clean data on every
    row where somebody forgot it (Guardrail #10).
    """
    if split is None:
        return {}
    return {
        "visual_plan_ms": split.plan_ms,
        "visual_plan_ms_is_estimate": split.is_estimate,
        "visual_plan_tokens_written": split.plan_tokens,
    }


def _kept_call(
    recorder: ItemRecorder,
    date: str,
    article: Article,
    *,
    call: str,
    kind: CallKind,
    prompt: str,
    reply: Completion | None,
    split: calls.DecodeSplit | None = None,
    capture_root: Path | None = None,
) -> None:
    """Measure one call's text, keep whichever halves the flags allow, and say so.

    Called on the path where the reply never came back as well as the one where
    it did, because a call that timed out is exactly the call whose prompt is
    worth reading - and `reply=None` is what tells the two apart in the record.

    The default root is derived from the run directory rather than from the
    repository, so a test that redirects `VAR_ROOT` redirects this with it - the
    same root every other output of this stage is written under. A caller that
    reads one article several times hands in its own, because the file is named
    for the item and the call and a second reading would otherwise overwrite the
    first.
    """
    kept = capture.of(
        root=capture_root if capture_root is not None else _run_dir(date) / common.CAPTURES_DIRNAME,
        item_id=article.item_id,
        call=call,
        prompt=prompt,
        reply="" if reply is None else reply.content,
        keep_prompt=recorder.flags.capture_prompts,
        keep_reply=recorder.flags.capture_replies and reply is not None,
        write=atomic_write.write_atomic,
        cost=None if reply is None else _cost(kind, reply),
        decode_split=None if split is None else split._asdict(),
        finish_reason="" if reply is None else reply.finish_reason or "",
        about=capture.About(
            canonical_url=str(article.canonical_url),
            source_id=article.source_id,
            title=article.title or "",
        ),
    )
    recorder.call_done(call, kept.cells())


def summarize_one_item(
    article: Article,
    settings: config.Settings,
    *,
    date: str,
    mentions: Sequence[Mention] = (),
    endpoint: str | None = None,
    run_id: str | None = None,
    tracer: telemetry.Tracer | None = None,
    recorder: ItemRecorder | None = None,
    capture_root: Path | None = None,
    render_root: Path | None = None,
    published_marks: Mapping[VisualType, Sequence[int]] | None = None,
) -> _ItemResult:
    """One article read once by the model, summarized and drawn - in one call.

    **The table the call is built over comes from the patterns and from the
    service.** `mentions` are the labelled spans the text-analysis service found
    in `Article.text`, asked for before this runs; `elements.element_table` turns
    them into the item's names and places and drops the figures they show were
    never figures. A caller with none - the service was down, or this is a replay
    with no service - gets the table the patterns alone make, and the item still
    publishes.

    **An article the call cannot hold is refused before it is sent.**
    `dag.fits_the_window` sizes the prompt and the model file's response limit
    against `n_ctx`, and an article over it lands as `FailureCode.CONTEXT_EXCEEDED`.
    Admitting it would cost the picture rather than the item: `--no-context-shift`
    means the decode stops at the wall on an ordinary HTTP 200,
    `recovered_completion` salvages the summary, and the item publishes with
    `window_exhausted` recorded where the picture would have been. Refusing it up
    front is still the better answer, because the whole decode is paid for before
    that reason can be written. An item that only fits without the chart
    instructions is asked for the summary alone.

    **The reply is read whole, and the summary survives the plan.** The summary
    is decoded first and closed before the plan starts, so a decode the output
    budget cuts is cut in the plan and the summary behind it is recovered; the
    picture is lost either way. A reply this build cannot read costs the item as
    `bad_shape`, and one the budget cut inside the summary as `output_truncated`.
    Both are a cell in the census rather than a silence.

    **No call is made for the names.** The first of the two calls this stage used
    to make read the article only to find them, and the service finds them in
    seconds and with exact offsets, so the model reads the article once.
    """
    if settings.app.visuals.downgrade_enabled and published_marks is None:
        raise ValueError("enabled visual downgrade requires the shard's published mark population")
    endpoint = endpoint or resolve_endpoint(settings.app.model_server.base_url)
    trace = tracer if tracer is not None else silent_tracer()
    kept = recorder if recorder is not None else _silent_recorder()
    model = settings.models.summarizer
    model_id = model.id
    # The call renders its own prompt bytes, so it goes to the completions
    # route and never to the chat one - which accepts `response_format` and
    # ignores it, losing the only control that survives an injection.
    rendered_endpoint = completion_url(endpoint)
    timeout = request_timeout_seconds(model)
    markers = derive_turn_markers(endpoint, entry=model, timeout=timeout)
    generated_at = assemble.utc_now()
    stamp = {
        "model_id": model_id,
        "decided_at": generated_at,
        "version": VisualDecision.schema_version(),
    }

    def failed(no_reply: FailureCode) -> _ItemResult:
        """The item, lost before a reply came back, and so carrying no cost."""
        return _ItemResult(
            summarize.to_summary(
                article,
                None,
                model_id=model_id,
                generated_at=generated_at,
                no_reply=no_reply,
            ),
            None,
        )

    with trace.span(telemetry.SpanName.SUMMARIZE) as stage_span:
        stage_span.set(telemetry.AttrKey.MODEL_ID, model_id)
        with trace.span(telemetry.SpanName.RENDER_PROMPT) as span:
            # A table that cannot re-slice its own output raises here rather
            # than degrading, which is `elements.element_table`'s own ruling:
            # at this point the text is in hand and it is the string the
            # excerpts came from, so a mismatch is this process's arithmetic
            # being wrong on every article that took the same path, not this
            # item being odd.
            table = elements.element_table(
                article, config=settings.app.elements, mentions=mentions
            )
            visuals = settings.app.visuals
            if not dag.fits_the_window(article, model.server, sampling=model.sampling):
                LOG.warning(
                    "the call would not fit the window id=%s tokens=%s",
                    article.item_id,
                    article.token_count,
                )
                return failed(FailureCode.CONTEXT_EXCEEDED)
            forms = chart_forms(table, visuals=visuals)
            chart_bytes = len(calls.chart_addendum(
                forms, prompt_files=settings.app.prompt_files, config_dir=settings.config_dir,
            ).encode("utf-8"))
            if forms and not dag.fits_the_window(
                article, model.server, addendum_bytes=chart_bytes, sampling=model.sampling
            ):
                LOG.warning(
                    "the chart instructions would not fit the window "
                    "id=%s tokens=%s chart_bytes=%s",
                    article.item_id,
                    article.token_count,
                    chart_bytes,
                )
                forms = ()
            quantities = tuple(e for e in table.elements if e.kind is ElementKind.QUANTITY)
            if forms and not dag.fits_the_window(
                article, model.server,
                addendum_bytes=chart_bytes + calls.chart_highlight_bytes(quantities),
                sampling=model.sampling,
            ):
                LOG.warning("the chart highlights would not fit the window id=%s", article.item_id)
                quantities = ()
            request = calls.build_summary_request(
                article,
                forms,
                model_id=model_id,
                server=model.server,
                sampling=model.sampling,
                markers=markers,
                chart_quantities=quantities,
                prompt_config=settings.app.summarize,
                prompt_files=settings.app.prompt_files,
                config_dir=settings.config_dir,
            )
            rendered = str(request["prompt"])
            digest = text_digest(rendered)
            span.set(telemetry.AttrKey.PROMPT_DIGEST, digest)
            span.set(telemetry.AttrKey.PROMPT_CHARS, len(rendered))
        kept.calling(CALL_SLOT)
        # The stopwatch starts before the request and stops when the reply is
        # in hand, so the wait is inside it. The server's own two clocks are
        # recorded beside it and the difference is what they cannot say.
        asked_at = time.monotonic()
        reply, no_reply = _ask_the_model(
            request,
            article,
            model_id=model_id,
            endpoint=rendered_endpoint,
            timeout=timeout,
            prompt_digest=digest,
            run_id=run_id,
            trace=trace,
            markers=markers,
        )
        summary_ms = int((time.monotonic() - asked_at) * 1000)
        if reply is None:
            _kept_call(
                kept,
                date,
                article,
                call=CALL_SLOT,
                kind=CallKind.SUMMARIZE_AND_PLAN,
                prompt=rendered,
                reply=None,
                capture_root=capture_root,
            )
            return failed(no_reply)
        split = calls.split_the_decode(reply)
        kept.note(
            run_visual_decision=bool(forms),
            **_call_cells(CALL_SLOT, CallKind.SUMMARIZE_AND_PLAN, reply, wall_ms=summary_ms),
            **_item_cells(reply),
            **_split_cells(split),
        )
        _kept_call(
            kept,
            date,
            article,
            call=CALL_SLOT,
            kind=CallKind.SUMMARIZE_AND_PLAN,
            prompt=rendered,
            reply=reply,
            split=split,
            capture_root=capture_root,
        )

        with trace.span(telemetry.SpanName.PARSE_REPLY) as span:
            half = calls.recovered_completion(reply)
            if reply.hit_the_budget and half is not None:
                # The seatbelt the reply shape's field order buys, spent. The
                # picture is gone either way; without this the summary went
                # with it.
                LOG.warning(
                    "the reply was cut and its summary recovered id=%s tokens=%s",
                    article.item_id,
                    reply.completion_tokens,
                )
            # Filled on every item and not only on the cut ones, because
            # `recovered` answers "was this summary salvaged" and an empty
            # cell makes an ordinary item and an unmigrated row look alike.
            kept.note(recovered=bool(reply.hit_the_budget and half is not None))
            summary = _recorded_as_the_one_call(
                summarize.to_summary(
                    article,
                    half if half is not None else reply,
                    model_id=model_id,
                    generated_at=generated_at,
                    no_reply=no_reply,
                    thinking=model.thinks,
                ),
                reply,
            )
            telemetry.summary_attributes(span, summary)
        telemetry.summary_attributes(stage_span, summary)

    if summary.status is not SummaryStatus.OK:
        return _ItemResult(summary, None, reply)

    with trace.span(telemetry.SpanName.VISUAL_PLANNER) as span:
        # The picture's own clock, and never the call's. `decision_ms` means the
        # planner call plus the render, and under this flag the planner call is
        # the one call - which also wrote the summary. Charging the picture for
        # that would make the console's slowest-decision reading the slowest ITEM.
        started = time.monotonic()
        decision = _decide_the_visual(
            summary,
            reply,
            table,
            forms=forms,
            text=article.text or "",
            settings=settings,
            date=date,
            stamp=stamp,
            run_id=run_id,
            recorder=kept,
            render_root=render_root,
            published_marks=published_marks,
        )
        decision = decision.model_copy(
            update={"decision_ms": int((time.monotonic() - started) * 1000)}
        )
        span.set(telemetry.AttrKey.MODEL_ASKED, decision.asked_the_model)
        span.set(telemetry.AttrKey.DRAFTED_CHART, decision.drafted_chart)
        span.set(telemetry.AttrKey.VISUAL_KIND, decision.kind.value)
        span.set(telemetry.AttrKey.VISUAL_STATE, decision.visual_state.value)
    return _ItemResult(summary, decision, reply)


def _decide_the_visual(
    summary: Summary,
    completion: Completion,
    table: ElementTable,
    *,
    forms: tuple[VisualType, ...],
    text: str,
    settings: config.Settings,
    date: str,
    stamp: Mapping[str, str],
    run_id: str | None,
    recorder: ItemRecorder | None = None,
    render_root: Path | None = None,
    published_marks: Mapping[VisualType, Sequence[int]] | None = None,
) -> VisualDecision:
    """Which of the routes to a picture, or to none, this reply took.

    Six outcomes and five `none_reason` members, because the member names the
    gate rather than the call site: an answer about a chart that breaks one of
    its rules and a plan the compiler could not draw are one answer to an
    operator - a chart was chosen and this build refuses it.

    **A cut reply is two different findings and the server reports one.** Under
    `--no-context-shift` a decode that runs into the end of the window stops
    exactly as a decode that spends its output budget does, on an ordinary HTTP
    200 with `finish_reason` of `length`. Only the arithmetic tells them apart,
    and it needs nothing this function does not already hold: the server counted
    the prompt, and the call's response limit is the model file's. Less room
    left than that limit means the window was the wall.
    """
    if not forms:
        return visual_planner.suppressed_by_the_gate(summary, **stamp)
    if completion.hit_the_budget:
        n_ctx = window(settings.models.summarizer.server)
        asked_for = response_limit(settings.models.summarizer.sampling)
        if completion.prompt_tokens + asked_for > n_ctx:
            LOG.warning(
                "the window stopped the plan id=%s prompt=%s budget=%s n_ctx=%s",
                summary.item_id,
                completion.prompt_tokens,
                asked_for,
                n_ctx,
            )
            return visual_planner.plan_lost_to_the_window(summary, **stamp)
        return visual_planner.plan_lost_to_the_budget(summary, **stamp)
    try:
        choice = calls.parse_summarize_and_plan(completion.content).visual
        if choice is None:
            return visual_planner.declined_by_the_model(summary, **stamp)
        plan, grounded = resolve_visual_choice(choice, forms, text, table)
    except (ValidationError, ValueError, json.JSONDecodeError) as error:
        shape = _shape_cells(error)
        LOG.warning(
            "the plan half did not hold its shape id=%s reason=%s detail=%s",
            summary.item_id,
            type(error).__name__,
            shape["detail"],
        )
        if recorder is not None:
            recorder.note(
                failed_field=shape["failed_field"], failed_rule=shape["failed_rule"]
            )
        return visual_planner.not_drawable_here(
            summary,
            why=f"the plan half did not hold its shape: {shape['detail']}",
            **stamp,
        )
    return _drawn(
        summary, plan, grounded, settings=settings, date=date, stamp=stamp,
        run_id=run_id, render_root=render_root, published_marks=published_marks,
    )
