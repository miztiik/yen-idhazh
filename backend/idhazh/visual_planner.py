"""Decide whether an item gets a chart or nothing.

The control that matters is not the prompt. It is that **the model never emits a
number**. Numbers are pulled out of the article text deterministically, and the
model is only allowed to choose which of them to plot, by index. A chart value
that is not in the article is therefore unreachable rather than unlikely, and
the oracle for this stage is a contract test rather than a hope.

"Nothing" is the common and correct answer. Two items in three carry no visual,
so `none` is the default that everything else has to earn its way past.

The two calls that read the article are `idhazh.classify.calls`. This module
holds what happens to their answer: the gate that refuses before a plan is
drafted, the ladder that steps a plan down, and the reason every `none` carries.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from math import ceil
from pathlib import Path
from typing import Any, Final, Literal, NamedTuple

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)

from idhazh.contracts.app_config import (
    InferenceConfig,
    VisualsConfig,
)
from idhazh.contracts.article import Article
from idhazh.contracts.element import (
    Element,
    ElementTable,
)
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual import (
    EncodingRole,
    PlanDecision,
    VisualPlan,
    VisualType,
)
from idhazh.contracts.visual_decision import (
    NoneReason,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.elements import (
    MAGNITUDE,
    NOT_A_UNIT,
    NUMBER,
    PERCENT,
    YEAR_MAX,
    YEAR_MIN,
    normalise_unit,
    read_value,
)
from idhazh.llm.server import Completion, request_payload
from idhazh.sanitize import sanitize, untrusted_block
from idhazh.visual_validator import Rejection, validate_plan
from idhazh.visual_vocabulary import (
    DOWNGRADE_EDGES,
    ROLE_KINDS,
    TYPE_RULES,
    VALUE_ROLES,
    commensurable,
)

PROMPT_PATH: Final = Path(__file__).parent / "prompts" / "visual_planner.txt"

LOG: Final = logging.getLogger("idhazh")

_THINK = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

# A number small enough to be a date, a count of paragraphs, or a list marker
# carries no information as a bar. Charting them is how a chart becomes noise.
_TRIVIAL_MAX: Final = Decimal(2)


class NumericFact(BaseModel):
    """One quantity found in the article, with the words around it.

    `raw` is what the article literally said, kept verbatim so a reader can find
    it on the page. `value` is what gets plotted. `unit` is what makes "these
    measure the same thing" a string comparison instead of a judgement.
    """

    model_config = ConfigDict(frozen=True)

    value: Decimal
    raw: str
    unit: str = ""
    context: str = ""


def _clean(chunk: str) -> str:
    return re.sub(r"\s+", " ", chunk).strip()


def _snap(text: str, start: int, end: int) -> str:
    """Widen a slice to whole words, so context never begins mid-word."""
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    while end < len(text) and not text[end].isspace():
        end += 1
    return _clean(text[start:end])


def numeric_facts(text: str, *, limit: int = 16) -> list[NumericFact]:
    """Every plottable quantity in the article, in the order it was written.

    Deduplicated on the value AND its unit, because twelve percent and twelve
    people are two facts, while the same figure repeated in a lead and a body
    paragraph is one.

    The candidate table in `idhazh.elements` is the opposite trade and keeps
    both. This one is picking a few bars, and that is what these drops are for.
    """
    facts: list[NumericFact] = []
    seen: set[tuple[Decimal, str]] = set()
    for match in NUMBER.finditer(text):
        digits = match.group("value")
        try:
            magnitude = Decimal(digits.replace(",", ""))
        except InvalidOperation:
            continue

        suffix = (match.group("magnitude") or "").strip().lower()
        word = normalise_unit(match.group("unit") or "")
        if word in NOT_A_UNIT:
            word = ""

        unit = ""
        if suffix in PERCENT:
            unit = "%"
        else:
            if suffix in MAGNITUDE:
                magnitude *= MAGNITUDE[suffix]
            currency = (match.group("currency") or "").strip()
            unit = currency or word

        if not unit and "," not in digits and "." not in digits:
            plain = int(magnitude)
            # A year is a label, not a bar height. Dropping it costs nothing,
            # because a label is a free string the model can still write.
            if YEAR_MIN <= plain <= YEAR_MAX and len(digits) == 4:
                continue

        if match.group("sign"):
            magnitude = -magnitude
        if abs(magnitude) <= _TRIVIAL_MAX and not unit:
            continue
        if (magnitude, unit) in seen:
            continue
        seen.add((magnitude, unit))
        facts.append(
            NumericFact(
                value=magnitude,
                raw=_clean(f"{match.group('currency') or ''}{match.group('sign') or ''}{digits}"),
                unit=unit,
                context=_snap(text, max(match.start() - 50, 0), min(match.end() + 30, len(text))),
            )
        )
        if len(facts) >= limit:
            break
    return facts


class ChartPoint(BaseModel):
    """A bar. The label is words; the height is an index into the article's own numbers."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=40)
    fact_index: int = Field(ge=0)


class VisualDraft(BaseModel):
    """What the decoder is constrained to emit.

    Closed to unknown keys and carrying no free numeric field anywhere, so the
    worst an injection can do is pick the wrong bars.

    Two things about this class are load-bearing and neither is obvious:

    - **Field order is decode order.** Pydantic emits properties in declaration
      order and llama.cpp builds its grammar in that order, so the model commits
      to each field in the order written here. `reason` comes first so that the
      one sentence about the item grounds the choice. With `kind` first the
      choice was already made and `reason` became a rationalisation - in
      practice the model filled it by copying the prompt's own rules back.
    - **Every field is required, including the two that are usually empty.** A
      field with a default is absent from the schema's `required` list, and a
      constrained decoder emits exactly what `required` forces. Given optional
      arrays the model returned a confident `chart` with no bars in it, twice,
      on the first live run.

    `reason` is capped at 120 rather than 200 because `maxLength` is a hard
    grammar stop that truncates mid-word, and a truncated first field is an
    input to every field after it.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=120)
    kind: Literal["chart", "diagram", "none"]
    caption: str = Field(max_length=120)
    points: list[ChartPoint] = Field(max_length=8)
    steps: list[str] = Field(max_length=6)


def output_schema() -> dict[str, Any]:
    return VisualDraft.model_json_schema()


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def fact_menu(facts: list[NumericFact]) -> str:
    """The numbers on offer, indexed, with the unit that makes them comparable."""
    if not facts:
        return "(no quantities found in this article)"
    return "\n".join(
        f"[{index}] {fact.raw} {fact.unit or '(no unit)'} - {fact.context}"
        for index, fact in enumerate(facts)
    )


def user_turn(
    article: Article, summary: Summary, facts: list[NumericFact], *, lead_words: int
) -> str:
    """The summary, the article's own opening, and the indexed numbers - all fenced.

    The article lead is here because the quantities are extracted from the
    article while the summary is a compression of it. Judging "is this
    comparison the point of the story" against text that may have dropped the
    whole series is judging the wrong document, and it would let a chart carry
    numbers no sentence beside it mentions.

    `lead_words` is most of the request's prefill, and prefill is most of the
    stage's wall-clock, so it is a config knob rather than a literal (Rule #6).
    """
    parts = [f"Title: {article.title}" if article.title else "Title: (untitled)"]
    parts.append(untrusted_block(summary.summary or ""))
    lead = " ".join((article.text or "").split()[:lead_words])
    if lead:
        parts.append("How the item opens:\n" + untrusted_block(lead))
    parts.append("Quantities found in this article:\n" + untrusted_block(fact_menu(facts)))
    return "\n\n".join(parts)


def build_request(
    article: Article,
    summary: Summary,
    facts: list[NumericFact],
    *,
    model_id: str,
    inference: InferenceConfig,
    visuals: VisualsConfig,
) -> dict[str, Any]:
    planning = inference.model_copy(update={"max_output_tokens": visuals.max_output_tokens})
    return request_payload(
        model_id=model_id,
        system=system_prompt(),
        user=user_turn(article, summary, facts, lead_words=visuals.lead_words),
        output_schema=output_schema(),
        inference=planning,
        schema_name="visual_planner",
    )


def parse_draft(raw: str) -> VisualDraft:
    content = _THINK.sub("", raw).strip()
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    return VisualDraft.model_validate_json(content)


def _nothing(
    summary: Summary,
    *,
    model_id: str,
    reason: str,
    decided_at: str,
    version: str,
    drafted_chart: bool = False,
    none_reason: NoneReason | None = None,
) -> VisualDecision:
    return VisualDecision(
        version=version,
        item_id=summary.item_id,
        url_key=summary.url_key,
        kind=VisualKind.NONE,
        rationale=sanitize(reason)[:200] or None,
        model_id=model_id,
        decided_at=decided_at,
        drafted_chart=drafted_chart,
        none_reason=none_reason,
    )


def decided_without_the_model(
    summary: Summary, *, model_id: str, decided_at: str, facts_found: int
) -> VisualDecision:
    """The `none` a fact-poor item gets when the planner skipped the model.

    The rationale says the model never ran, so a reader of the payload is never
    left to infer it from a decision that looks like every other `none`.

    It records `not_reachable` because it IS the reachability gate, read over
    this flow's quantities rather than over an element table. One member per
    gate, never one per call site - what an operator acts on is the gate.
    """
    return _nothing(
        summary,
        model_id=model_id,
        reason=(
            f"no visual kind could be built from the {facts_found} quantities in this "
            "article, so the model was not asked"
        ),
        decided_at=decided_at,
        version=VisualDecision.schema_version(),
        none_reason=NoneReason.NOT_REACHABLE,
    ).model_copy(update={"asked_the_model": False})


def common_unit(points: list[ChartPoint], facts: list[NumericFact]) -> str | None:
    """The one unit every chosen bar shares, or `None` if they disagree."""
    units = {facts[point.fact_index].unit for point in points}
    if len(units) != 1:
        return None
    return units.pop()


def same_unit_bars(
    points: list[ChartPoint], facts: list[NumericFact]
) -> tuple[str, list[ChartPoint]]:
    """The largest group of chosen bars that measure the same thing.

    A price beside a headcount is not a comparison, and an axis labelled from
    the first bar would state it as one. This is the old prompt rule "do not
    chart quantities that measure different things", enforced instead of
    requested.

    Discarding the whole chart on one stray bar was the first design, and the
    live 4B showed why it is wrong: given an article about solar capacity it
    picked the three correct year-on-year megawatt bars and then appended the
    sector's headcount. Three good bars were thrown away to reject one bad one.
    Keeping the largest agreeing group never invents a bar and never mixes
    units; it only ever drops. If what remains is too small to be a comparison,
    the caller still decides nothing.

    Ties resolve to the group whose first bar came earliest, so the same input
    always produces the same chart.
    """
    groups: dict[str, list[ChartPoint]] = {}
    for point in points:
        groups.setdefault(facts[point.fact_index].unit, []).append(point)
    unit = max(groups, key=lambda key: (len(groups[key]), -points.index(groups[key][0])))
    return unit, groups[unit]


def chart_is_reachable(facts: list[NumericFact], *, visuals: VisualsConfig) -> bool:
    """Could ANY choice of indices over these facts survive `to_decision`?

    A published bar is always `facts[i]` for some `i`, every bar in a chart
    shares one unit, and the bars must be distinct quantities. So the ceiling on
    a chart's width is the size of the largest unit group in the article's own
    numbers. Below `min_chart_points` the answer is `none` before the model is
    asked, which makes asking it 21 measured seconds spent to prove something
    already proved.

    The empty string is a unit group like any other - `numeric_facts` writes it
    when nothing after the number reads as a unit, and `same_unit_bars` already
    treats it as one. Excluding it here would gate items that publish today.

    This reads the facts only - never the article's words. A predicate that
    branched on fetched prose would let a stranger's page steer our control
    flow (Rule #11).
    """
    if not facts:
        return False
    widest = Counter(fact.unit for fact in facts).most_common(1)[0][1]
    return widest >= visuals.min_chart_points


def reachable_kinds(facts: list[NumericFact], *, visuals: VisualsConfig) -> list[VisualKind]:
    """The enabled kinds this item could still produce, in config order.

    Written as a predicate over every kind rather than as a chart special case,
    so a kind added later declares its own reachability here rather than being
    let through by an `if` that only knows about charts.
    """
    survivors: list[VisualKind] = []
    for kind in visuals.enabled_kinds:
        if kind is VisualKind.CHART and not chart_is_reachable(facts, visuals=visuals):
            continue
        survivors.append(kind)
    return survivors


def chart_spec(
    points: list[ChartPoint],
    facts: list[NumericFact],
    *,
    caption: str,
    unit: str,
    visuals: VisualsConfig,
) -> dict[str, Any]:
    """A Vega-Lite spec built here, not by the model.

    The model chose labels and indices. Every number in this object is read out
    of `facts`, which came out of the article, so the oracle holds by
    construction rather than by inspection.
    """
    values = [
        {"label": sanitize(point.label)[:40], "value": float(facts[point.fact_index].value)}
        for point in points
    ]
    spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": visuals.canvas_width - 120,
        "height": visuals.canvas_height - 90,
        "background": "transparent",
        "data": {"values": values},
        "mark": {"type": "bar", "cornerRadiusEnd": 3, "color": "#4c6ef5"},
        "encoding": {
            "y": {
                "field": "label",
                "type": "nominal",
                "sort": None,
                "axis": {"title": None, "labelLimit": 220},
            },
            "x": {
                "field": "value",
                "type": "quantitative",
                "axis": {"title": unit or None, "format": "~s"},
            },
        },
        "config": {
            "view": {"stroke": None},
            "axis": {"labelFont": "sans-serif", "titleFont": "sans-serif", "grid": False},
        },
    }
    if caption:
        spec["title"] = {"text": sanitize(caption)[:120], "anchor": "start", "fontSize": 14}
    return spec


def alt_text(draft: VisualDraft, facts: list[NumericFact]) -> str:
    """What a screen reader gets. The visual is never the only carrier of a fact."""
    parts = [
        f"{sanitize(point.label)[:40]} "
        f"{facts[point.fact_index].raw} {facts[point.fact_index].unit}".strip()
        for point in draft.points
    ]
    return f"Bar chart. {'; '.join(parts)}."[:300]


def to_decision(
    article: Article,
    summary: Summary,
    completion: Completion,
    *,
    model_id: str,
    decided_at: str,
    visuals: VisualsConfig,
    facts: list[NumericFact] | None = None,
) -> VisualDecision:
    """One completion becomes exactly one visual decision, or becomes `none`.

    Every rejection path lands on `none` with a rationale. A visual is never
    allowed to be the reason an item does not publish.
    """
    version = VisualDecision.schema_version()
    available = facts if facts is not None else numeric_facts(article.text or "")

    if summary.status is not SummaryStatus.OK:
        return _nothing(
            summary,
            model_id=model_id,
            reason="the item has no summary, so there is nothing to illustrate",
            decided_at=decided_at,
            version=version,
        )
    if completion.hit_the_budget:
        return _nothing(
            summary,
            model_id=model_id,
            reason="the planner's reply was cut off by the output budget",
            decided_at=decided_at,
            version=version,
        )
    try:
        draft = parse_draft(completion.content)
    except (ValidationError, ValueError, json.JSONDecodeError) as error:
        return _nothing(
            summary,
            model_id=model_id,
            reason=f"the planner's reply did not hold its shape: {type(error).__name__}",
            decided_at=decided_at,
            version=version,
        )

    # What the model CHOSE, before any rejection folds it into `none`. Without
    # this line a diagram the model asked for and this function refused is
    # indistinguishable from a diagram it never wanted, and the arm's zero
    # production rate has no cause anyone can name.
    LOG.info(
        "planner draft id=%s kind=%s points=%s steps=%s",
        summary.item_id,
        draft.kind,
        len(draft.points),
        len(draft.steps),
    )

    if draft.kind == "none":
        return _nothing(
            summary,
            model_id=model_id,
            reason=draft.reason,
            decided_at=decided_at,
            version=version,
        )

    # The prompt and the output grammar still offer "diagram", and nothing draws
    # one since the Mermaid round trip went (pseudo-plan row 63). Refused here,
    # one line above where `enabled_kinds` refused it before and with the same
    # words, so the payload a diagram draft produces does not move.
    if draft.kind != VisualKind.CHART.value:
        return _nothing(
            summary,
            model_id=model_id,
            reason=f"{draft.kind} has no renderer switched on",
            decided_at=decided_at,
            version=version,
        )

    kind = VisualKind(draft.kind)
    # What the model asked for, kept whatever this function does with it next.
    # Every return below is a post-model check, and the difference between this
    # flag and the published kind is exactly what those checks rejected.
    drafted_chart = True
    if kind not in visuals.enabled_kinds:
        return _nothing(
            summary,
            model_id=model_id,
            reason=f"{kind.value} has no renderer switched on",
            decided_at=decided_at,
            version=version,
            drafted_chart=drafted_chart,
        )

    if any(point.fact_index >= len(available) for point in draft.points):
        return _nothing(
            summary,
            model_id=model_id,
            reason="the chart pointed at a quantity the article does not contain",
            decided_at=decided_at,
            version=version,
            drafted_chart=drafted_chart,
        )
    # One quantity may fill one bar. Without this the model can name index 3
    # three times, `same_unit_bars` groups all three under one unit, the
    # width check passes, and a chart of one number repeated under three
    # invented labels publishes - a fabricated comparison built entirely out
    # of real facts, which is the one failure this stage claims is
    # unreachable.
    if len({point.fact_index for point in draft.points}) != len(draft.points):
        return _nothing(
            summary,
            model_id=model_id,
            reason="the chart used one quantity for more than one bar",
            decided_at=decided_at,
            version=version,
            drafted_chart=drafted_chart,
        )
    unit, bars = same_unit_bars(draft.points, available)
    kept_from = len(draft.points)
    if not visuals.min_chart_points <= len(bars) <= visuals.max_chart_points:
        return _nothing(
            summary,
            model_id=model_id,
            reason=(
                f"{len(bars)} of {len(draft.points)} bars measure the same thing, "
                "which is outside the publishable range"
            ),
            decided_at=decided_at,
            version=version,
            drafted_chart=drafted_chart,
        )
    draft = draft.model_copy(update={"points": bars})
    # A caption written about five bars is a false statement about three.
    # The live 4B captioned a chart "Solar Capacity and Employment" and then
    # had its employment bar dropped, which is exactly the kind of small lie
    # that costs a reader their trust in every other number on the page.
    caption = draft.caption if len(bars) == kept_from else ""
    spec = json.dumps(
        chart_spec(bars, available, caption=caption, unit=unit, visuals=visuals),
        separators=(",", ":"),
        sort_keys=True,
    )

    return VisualDecision(
        version=version,
        item_id=summary.item_id,
        url_key=summary.url_key,
        kind=kind,
        rationale=sanitize(draft.reason)[:200] or None,
        spec=spec,
        alt_text=sanitize(alt_text(draft, available))[:300] or None,
        visual_state=VisualState.ABSENT,
        model_id=model_id,
        decided_at=decided_at,
        drafted_chart=drafted_chart,
    )


def plan_lost_to_the_budget(
    summary: Summary, *, model_id: str, decided_at: str, version: str
) -> VisualDecision:
    """The `none` an item gets when its summary survived the cut and its plan did not.

    A decision and not a failure. The item publishes; what it does not carry is
    a picture, and the rationale says which of the two ran out of budget so an
    operator reading a run of these knows to look at the budget rather than at
    the articles.
    """
    return _nothing(
        summary,
        model_id=model_id,
        reason=(
            "the reply ran out of output budget after the summary closed, "
            "so the plan was never written"
        ),
        decided_at=decided_at,
        version=version,
        none_reason=NoneReason.OUTPUT_BUDGET_CUT,
    )


# --- The gate that refuses before the plan is drafted ------------------------


def _drawable(table: ElementTable) -> list[Element]:
    """The elements a plan could cite without the validator refusing it outright.

    An element whose cell disagrees with its own characters fails
    `no_invented_values` wherever it is drawn, so counting it here would make
    the gate claim a width no plan can reach. Reading it with the producer's own
    reader is what the validator does, and asking the same question with the
    same function is what keeps the gate from drifting away from the thing it
    predicts.
    """
    seen: set[str] = set()
    kept: list[Element] = []
    for element in table.elements:
        if element.element_id in seen:
            continue
        seen.add(element.element_id)
        if read_value(element.kind, element.span_excerpt) == element.value:
            kept.append(element)
    return kept


def _widest_agreeing(elements: Sequence[Element]) -> int:
    """The largest group of these that could share one measured axis.

    The same greedy grouping `same_unit_bars` does, over `commensurable` rather
    than over string equality, because that is the question `units_convertible`
    asks. Deterministic: the groups are opened in the order the table holds.
    """
    groups: list[list[Element]] = []
    for element in elements:
        for group in groups:
            if commensurable(group[0].unit, element.unit):
                group.append(element)
                break
        else:
            groups.append([element])
    return max((len(group) for group in groups), default=0)


def reachable_types(table: ElementTable, *, visuals: VisualsConfig) -> tuple[VisualType, ...]:
    """Every type some plan over this article's elements could name and still validate.

    **This is gate 1, and it reads the validator's own tables.** A plan is a set
    of references into one table, so whether any choice of references could
    survive is a question about the table alone - which kinds it holds, how many
    of them, and how many of those measure the same thing. Asking it with
    `TYPE_RULES`, `ROLE_KINDS`, `VALUE_ROLES` and `commensurable` is what stops
    the gate and the validator answering differently: a gate written from a
    reading of the rules drifts the first time a rule moves, silently, in the
    direction that costs items their pictures.

    Three of the nine checks cannot refuse a plan the gate has admitted, so the
    gate does not ask them. `element_exists` is satisfied by choosing from the
    table. `plan_version_current` is stamped by code. `numerals_matched` is
    about prose, and a plan can always write prose with no numeral in it.

    **It reads no word of the article.** Every input is a kind, a unit or a
    count, so a stranger's page cannot steer our control flow (Rule #11) - the
    same property the single-call gate above holds and for the same reason.
    """
    drawable = _drawable(table)
    reached: list[VisualType] = []
    for visual_type, rules in TYPE_RULES.items():
        fillable = {
            role: [one for one in drawable if one.kind in ROLE_KINDS[role]]
            for role in rules.required
        }
        if any(not elements for elements in fillable.values()):
            continue
        marks = fillable[rules.marks]
        floor = (
            visuals.histogram_bins
            if visual_type is VisualType.HISTOGRAM
            else visuals.min_chart_points
        )
        width = _widest_agreeing(marks) if rules.marks in VALUE_ROLES else len(marks)
        if width >= floor:
            reached.append(visual_type)
    return tuple(reached)


def plan_is_reachable(table: ElementTable, *, visuals: VisualsConfig) -> bool:
    """Could this article carry any picture at all?

    False suppresses the plan fields inside call 2 and never skips the call,
    because call 2 is the call that writes the summary (O43). What is saved is
    the plan's decode, not the request.
    """
    return bool(reachable_types(table, visuals=visuals))


def suppressed_by_the_gate(
    summary: Summary, *, model_id: str, decided_at: str, version: str
) -> VisualDecision:
    """The `none` an item gets when no choice over its elements could have validated.

    `asked_the_model` stays true, and that is the difference between this and
    the single-call planner's prefilter above: the model WAS asked, for the
    summary, in the same request. Only the plan fields were taken off the
    grammar.
    """
    return _nothing(
        summary,
        model_id=model_id,
        reason=(
            "no picture over this article's elements could have passed the validator, "
            "so the plan was left off the request"
        ),
        decided_at=decided_at,
        version=version,
        none_reason=NoneReason.NOT_REACHABLE,
    )


def declined_by_the_model(
    summary: Summary, *, why: str, model_id: str, decided_at: str, version: str
) -> VisualDecision:
    """The `none` an item gets when the model was asked and answered `none`.

    The ordinary answer. `why` is the plan's own prose and is sanitized on the
    way into the rationale, because it is a string a model wrote about a page we
    did not write (Rule #11).
    """
    return _nothing(
        summary,
        model_id=model_id,
        reason=why,
        decided_at=decided_at,
        version=version,
        drafted_chart=False,
        none_reason=NoneReason.MODEL_DECLINED,
    )


def refused_by_the_validator(
    summary: Summary,
    rejections: Sequence[Rejection],
    *,
    model_id: str,
    decided_at: str,
    version: str,
) -> VisualDecision:
    """The `none` an item gets when a plan was drafted and no depth of it validates.

    The rationale names the checks rather than restating them, because a
    `Rejection`'s detail is built out of element ids, role names and digits and
    a rationale is a published cell.
    """
    return _nothing(
        summary,
        model_id=model_id,
        reason=(
            "the plan was refused on "
            + ", ".join(sorted({rejection.check.value for rejection in rejections}))
            + ", and the ladder reached no form that passes"
        ),
        decided_at=decided_at,
        version=version,
        drafted_chart=True,
        none_reason=NoneReason.VALIDATION_FAILED,
    )


# --- The ladder that steps down ----------------------------------------------


class Downgrade(NamedTuple):
    """One plan re-drawn in a weaker form, and the three facts that justify it.

    `floor` is the mark count this depth demanded, kept beside the plan because
    an operator reading two depths that recorded one floor is reading the
    percentiles colliding rather than a bug.
    """

    plan: VisualPlan
    depth: int
    edge: tuple[VisualType, VisualType]
    floor: int


def _restyled(plan: VisualPlan, target: VisualType) -> VisualPlan:
    """The same plan drawn as `target`: the element set unchanged, extra channels empty.

    **Emptying a channel is not dropping an element**, and the difference is the
    whole of invariance 1. `element_ids` is the set of elements the model chose,
    and it comes through untouched, so a downgrade can never reach for a fact the
    model did not pick. What a `bubble` loses on the way to a `scatter` is the
    size CHANNEL; the elements that filled it stay declared, stay checked by
    `no_invented_values`, and are simply not drawn.
    """
    rules = TYPE_RULES[target]
    legal = rules.required | rules.optional
    encodings = {
        role.value: (getattr(plan.encodings, role.value) if role in legal else [])
        for role in EncodingRole
    }
    return VisualPlan.model_validate(
        plan.model_dump(mode="json") | {"type": target.value, "encodings": encodings}
    )


def _marks(plan: VisualPlan) -> int:
    """How many marks this plan draws, counted in the channel its type counts in."""
    if plan.type is None:
        return 0
    return len(plan.encodings.filled().get(TYPE_RULES[plan.type].marks, []))


def depth_floor(published: Sequence[int], percentile: int) -> int | None:
    """The mark count a downgrade at this depth has to reach, or nothing.

    Nearest-rank over the depth-0 published mark counts for the target type, so
    an integer population gives an integer floor and nothing is interpolated
    into a number no visual ever had.

    **`None` is "there is no floor to clear", and the caller reads it as a
    refusal rather than as a pass.** A floor computed from nothing is not a
    floor, and waiving it would make depth 1 publish on the validator alone -
    which is exactly depth 1 quietly becoming the default path, the thing the
    escalating floor exists to stop.

    The population is passed in rather than read here, because where it comes
    from is a ledger this row does not build. Depth-0 published visuals only:
    including downgrades makes a loop where downgrades score lower, drag the
    floor down and admit more downgrades, so the bar loosens exactly as quality
    falls.
    """
    ordered = sorted(published)
    if not ordered:
        return None
    rank = max(1, ceil(percentile / 100 * len(ordered)))
    return ordered[rank - 1]


def downgrade(
    plan: VisualPlan,
    table: ElementTable,
    *,
    visuals: VisualsConfig,
    published_marks: Mapping[VisualType, Sequence[int]],
) -> Downgrade | None:
    """The weakest legal re-drawing of this plan that still earns its place, or nothing.

    A downgrade is the same claim re-rendered in a weaker form. It is never
    permission to go and find something else to draw, and the four invariance
    rules are what make that a property rather than an intention:

    1. **The element set is unchanged.** `_restyled` carries `element_ids`
       through and only ever empties a channel.
    2. **The purpose survives.** The plan's own `purpose` is never written, and
       every edge names the purposes it preserves - so a chain is safe as well
       as a step, which comparing each step's endpoints alone cannot give.
    3. **The floor escalates.** Each depth reads a higher percentile of the
       depth-0 published mark counts for the type being stepped down to, and a
       floor that cannot be computed is not cleared.
    4. **It re-validates.** The candidate re-enters the same validator, and a
       depth that fails falls to the next depth rather than publishing.

    The walk is breadth-first over the edge table, so the depth is the number of
    steps taken and the first candidate that clears its own depth wins. A
    candidate that fails does not end the walk - its own targets are what the
    next depth is made of, which is what "falls to the next depth" means.

    `visuals.downgrade_floor_percentiles` is the whole of the switch: its length
    is how many depths exist and an empty list is the ladder off.
    """
    rungs = visuals.downgrade_floor_percentiles
    if plan.decision is not PlanDecision.VISUAL or plan.type is None or not rungs:
        return None
    frontier: list[VisualType] = [plan.type]
    walked: set[VisualType] = {plan.type}
    for depth, percentile in enumerate(rungs, start=1):
        onward: list[VisualType] = []
        for source in frontier:
            for edge in DOWNGRADE_EDGES.get(source, ()):
                if edge.target in walked or plan.purpose not in edge.purposes:
                    continue
                walked.add(edge.target)
                onward.append(edge.target)
                candidate = _restyled(plan, edge.target)
                # A downgrade carries a machine-checkable justification, and the
                # annotation is it: the mark that makes the weaker form still
                # worth showing. Without it depth 1 is just the default path.
                if not candidate.annotations:
                    continue
                if validate_plan(candidate, table, visuals=visuals):
                    continue
                floor = depth_floor(published_marks.get(edge.target, ()), percentile)
                if floor is None or _marks(candidate) < floor:
                    continue
                return Downgrade(candidate, depth, (source, edge.target), floor)
        frontier = onward
    return None


