"""How does one article become a summary and a picture, in two adjacent calls?

Production's call path, and the only one. It lived inside `work.py` until
2026-09-15, which meant `qualify` could not run it: the qualification gate
posted to the chat route with one call an item and let the model's own template
write the prompt, so a model that passed the gate could still fail in `work` on
the grammar, on the label reply's schema, or on the window check. The gate
measured a model rather than the model.

Nothing about the sequence changed when it moved. The order is still
`classify.dag.NODES`, the budget is still sized there, and the two calls are
still adjacent per item because the server holds one cache slot.
"""


from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NamedTuple

from pydantic import ValidationError

from idhazh import (
    assemble,
    capture,
    config,
    elements,
    summarize,
    telemetry,
    visual_planner,
)
from idhazh.classify import calls, dag
from idhazh.contracts.article import Article
from idhazh.contracts.call_cost import COST_FIELDS, CallCost, CallKind
from idhazh.contracts.element import ElementTable
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual import PlanDecision, VisualPlan
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.fingerprint import (
    text_digest,
)
from idhazh.llm.server import (
    DEFAULT_ENDPOINT,
    Completion,
    completion_url,
)
from idhazh.render import asset_relpath, render_planned_visual
from idhazh.stages import common
from idhazh.stages.common import (
    LOG,
    _ask_the_model,
    _run_dir,
    silent_tracer,
)
from idhazh.telemetry.record import Flags, ItemRecorder
from idhazh.visual_validator import validate_plan

#: The column prefix the item's FIRST call writes under. `ItemHealthRow` names
#: its two call slots after the calls this stage happens to make, and
#: `label_kind` is documented as "which call the stage made first" - so the slot
#: is the ordinal, and this is the name of ordinal one.
FIRST_CALL: Final = "label"


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

    **Three more cells belong to the ITEM rather than to the call**, and the row
    holds one set of them for a stage that makes two calls, so they are carried
    off the first call and no other. The first call is the only one whose slot
    was last touched by the item BEFORE this one; the second call's prompt is
    literally the first one's extended, so its reuse is true by construction and
    would say nothing about anything. They are read straight off the reply -
    `server.parse_completion` derives them, this carries them.
    """
    prefill_s = reply.prefill_ms / 1000
    decode_s = reply.decode_ms / 1000
    cached = min(reply.cached_tokens, reply.prompt_tokens)
    evaluated = reply.prompt_tokens - cached
    item_cells: dict[str, Any] = (
        {
            "slot_id": reply.slot_id,
            "kv_tokens_at_start": reply.slot_tokens_held,
            "prefix_shared_with_previous": reply.prefix_reused,
        }
        if slot == FIRST_CALL
        else {}
    )
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
        **item_cells,
    }


class _TwoCalls(NamedTuple):
    """What one item's pair of calls settled: the summary, and the picture or none.

    `decision` is None when the summary is not publishable. The pipeline has
    never written a decision for an item that carries no summary - `plannable_items`
    skips one - and a decision about a story no reader will see is a payload
    `assemble` would have to throw away.

    **The two replies come back with it, for the caller that is measuring this
    path rather than publishing from it.** `_split_the_cost` folds the pair's
    five numbers into the summary, which is the right shape for a ledger row and
    the wrong one for a gate: a sum cannot say whether a decode was cut, and the
    reasoning channel leaves no trace in it at all. Either reply is None when
    its call never happened, so a caller reads what ran and never a zero for a
    call that did.
    """

    summary: Summary
    decision: VisualDecision | None
    label_reply: Completion | None = None
    answer_reply: Completion | None = None


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
    first = _cost(CallKind.LABEL, one)
    spent = [first]
    if two is not None:
        spent.append(_cost(CallKind.SUMMARIZE_AND_PLAN, two))
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

    The order is validate first, and only a plan no depth of the ladder can
    rescue is refused. `published_marks` is empty because the depth-0 population
    the floors read is a ledger nothing has built, and a floor that cannot be
    computed is not cleared - so the ladder is wired and inert rather than wired
    and lenient.
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


def _silent_recorder() -> ItemRecorder:
    """A recorder that collects cells and emits nothing.

    `two_calls_one_item` is called directly by tests and by the canary runner,
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
        write=assemble.write_atomic,
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


def two_calls_one_item(
    article: Article,
    settings: config.Settings,
    *,
    date: str,
    endpoint: str = DEFAULT_ENDPOINT,
    run_id: str | None = None,
    tracer: telemetry.Tracer | None = None,
    recorder: ItemRecorder | None = None,
    capture_root: Path | None = None,
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
        return _TwoCalls(
            summary if one is None else _split_the_cost(summary, one, None), None, one, None
        )

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
            kept.calling("label")
            # The stopwatch starts before the request and stops when the reply
            # is in hand, so the wait is inside it. The server's own two clocks
            # are recorded beside it and the difference is what they cannot say.
            asked_at = time.monotonic()
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
            )
            label_ms = int((time.monotonic() - asked_at) * 1000)
            if one is None:
                _kept_call(
                    kept,
                    date,
                    article,
                    call="label",
                    kind=CallKind.LABEL,
                    prompt=rendered,
                    reply=None,
                    capture_root=capture_root,
                )
                return failed(no_reply)
            so_far.one = one
            kept.note(**_call_cells(FIRST_CALL, CallKind.LABEL, one, wall_ms=label_ms))
            _kept_call(
                kept,
                date,
                article,
                call="label",
                kind=CallKind.LABEL,
                prompt=rendered,
                reply=one,
                capture_root=capture_root,
            )
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
            kept.calling("summary")
            asked_at = time.monotonic()
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
            )
            summary_ms = int((time.monotonic() - asked_at) * 1000)
            if two is None:
                _kept_call(
                    kept,
                    date,
                    article,
                    call="summary",
                    kind=CallKind.SUMMARIZE_AND_PLAN,
                    prompt=second_rendered,
                    reply=None,
                    capture_root=capture_root,
                )
                return failed(no_reply, one)
            so_far.two = two
            split = calls.split_the_decode(two)
            kept.note(
                run_visual_decision=so_far.wants_a_plan,
                **_call_cells("summary", CallKind.SUMMARIZE_AND_PLAN, two, wall_ms=summary_ms),
                **_split_cells(split),
            )
            _kept_call(
                kept,
                date,
                article,
                call="summary",
                kind=CallKind.SUMMARIZE_AND_PLAN,
                prompt=second_rendered,
                reply=two,
                split=split,
                capture_root=capture_root,
            )

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
        return _TwoCalls(summary, None, so_far.one, two)

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
    return _TwoCalls(summary, decision, so_far.one, two)


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
    recorder: ItemRecorder | None = None,
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
