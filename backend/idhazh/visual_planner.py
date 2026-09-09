"""Decide whether an item gets a chart or nothing.

The control that matters is not the prompt. It is that **the model never emits a
number**. Numbers are pulled out of the article text deterministically, and the
model is only allowed to choose which of them to plot, by index. A chart value
that is not in the article is therefore unreachable rather than unlikely, and
the oracle for this stage is a contract test rather than a hope.

"Nothing" is the common and correct answer. Two items in three carry no visual,
so `none` is the default that everything else has to earn its way past.

**Call 1 is the other half of this module and it draws nothing.** It hands the
model the article itself rather than a summary of it, beside the table of
quantities and dates the candidate pass already cut, and asks what each one
means. Its reply cites addresses code minted and types nothing a reader sees.
It is built here and no stage calls it yet: call 2 is what turns the labelled
table into a summary and a plan, and it is a later row's work.
"""

from __future__ import annotations

import json
import logging
import re
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Any, Final, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from idhazh.contracts.app_config import ElementsConfig, InferenceConfig, VisualsConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.element import (
    Element,
    ElementKind,
    ElementTable,
    Extractor,
    derive_element_id,
)
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual_decision import VisualDecision, VisualKind, VisualState
from idhazh.elements import (
    MAGNITUDE,
    NOT_A_UNIT,
    NUMBER,
    PERCENT,
    YEAR_MAX,
    YEAR_MIN,
    SpanDriftError,
    normalise_unit,
    read_quantity,
    sentence_starts,
    settle,
)
from idhazh.llm.server import Completion, request_payload
from idhazh.sanitize import sanitize, untrusted_block

PROMPT_PATH: Final = Path(__file__).parent / "prompts" / "visual_planner.txt"
CALL_ONE_PROMPT_PATH: Final = Path(__file__).parent / "prompts" / "call_one.txt"

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
    )


def decided_without_the_model(
    summary: Summary, *, model_id: str, decided_at: str, facts_found: int
) -> VisualDecision:
    """The `none` a fact-poor item gets when the planner skipped the model.

    The rationale says the model never ran, so a reader of the payload is never
    left to infer it from a decision that looks like every other `none`.
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


# --- Call 1: the model reads the article and points at it --------------------
#
# One sentence governs the whole section: code finds and cuts every character a
# reader will see, and the model points at where to cut and says what the cut
# means. Everything the reply may contain is either an address code minted, a
# word from a closed list, or words the model is only allowed to describe with -
# never a figure, a position or a count.

#: The date-stamp of this labelling pass, written onto every element it judges.
#: It is `Element.ledger_version`, so a later run can tell which pass assigned a
#: judgement and re-label under a newer one without guessing. Bump it when the
#: label vocabulary or the meaning of a band changes, not when the prompt is
#: reworded - a reworded prompt still assigns the same fields.
LABEL_PASS_VERSION: Final = "2026-09-09"

#: Structural bounds on a decoder shape, in the same place and for the same
#: reason `VisualDraft` carries its own: a `maxItems` is a hard grammar stop, so
#: it bounds the reply before a byte of it is written rather than after. These
#: are not the tunables Rule #6 sends to `config/` - moving one changes what the
#: decoder can emit at all, which is a contract change and not an operator's
#: dial, and a grammar is fixed before a request is built. The per-article
#: proposal cap decision 3 asks for is `PROPOSED_MAX`.
#:
#: `LABELS_MAX` is the count `visuals.max_facts` already names, for the reason
#: that knob gives: a long indexed menu is lost-in-the-middle for a model
#: picking by address. It is not the size of the table - a dense article can
#: hold 256 candidates and the labels are for choosing between them, not for
#: covering them, so twice a full chart's width is enough to choose with. What
#: a maximal reply costs in output tokens, and what budget it needs, is derived
#: with call 2's own bounds in the row that adds the second call.
LABELS_MAX: Final = 16
PROPOSED_MAX: Final = 4
RANGES_MAX: Final = 8
KEYPHRASES_MAX: Final = 8
LEDE_MAX: Final = 2
#: An address is `quantity-118-123` or `s7`. Nothing legitimate is longer, and a
#: reply that pads one has written a string no lookup will find.
ADDRESS_MAX: Final = 48
#: Words, not sentences. A `measure` is what a figure measures and a `surface`
#: is the few words a figure was written in; either one running long is a reply
#: copying the article rather than pointing into it.
PHRASE_MAX: Final = 60

#: How much of the story one fact is, in three words rather than as a number.
#: The model may not type a figure (Rule #11 and the module docstring), so it
#: picks a band and code converts. The scores are the midpoints of three equal
#: bands over the 0..1 `Element.salience` holds - written as fractions so nobody
#: reads 0.83 as a tuned value. Nothing tunes them: they are what the three
#: words mean.
Salience = Literal["primary", "supporting", "background"]
SALIENCE_SCORE: Final[dict[str, float]] = {
    "primary": 5 / 6,
    "supporting": 1 / 2,
    "background": 1 / 6,
}

#: Who the item said it, as a type rather than as a sentence. A closed list is
#: what makes the summarizer's attribution rule mechanical instead of
#: aspirational, and it shares its vocabulary with nothing else - a free
#: sentence here would be model-authored text with an element's authority.
Attribution = Literal["named", "self_reported", "anonymous", "unattributed"]
#: The reading that assigns nothing. The article stated it in its own voice, so
#: there is no attribution to record and `Element.attribution` stays unset.
UNATTRIBUTED: Final = "unattributed"

Address = Annotated[str, StringConstraints(min_length=1, max_length=ADDRESS_MAX)]
Phrase = Annotated[str, StringConstraints(min_length=1, max_length=PHRASE_MAX)]

_SENTENCE_PREFIX: Final = "s"
_SLUG_SEPARATORS: Final = re.compile(r"[^a-z0-9]+")

if set(SALIENCE_SCORE) != set(get_args(Salience)):
    raise TypeError(
        "every salience band converts to a score, and every score is a band - "
        f"bands {get_args(Salience)}, scores {tuple(SALIENCE_SCORE)}"
    )


class Citation(BaseModel):
    """One sentence's address, and the words inside it the model means.

    The one shape whose words are *searched for* rather than kept: code reads
    only the named sentence, demands exactly one hit, and cuts the article's own
    bytes at it. Everything else in the reply that carries words carries them as
    a judgement about a fact code already cut, and none of it becomes a span. A
    surface that does not resolve drops that citation and nothing else.
    """

    model_config = ConfigDict(extra="forbid")

    sentence_id: Address
    surface: Phrase


class ElementLabel(BaseModel):
    """What one candidate the code already cut MEANS.

    **Field order is decode order and it is load-bearing here twice.**
    `element_id` is first, so every field after it is written about a fact
    rather than about the article in general. `salience` is last, so it is an
    observation of what the model has just described rather than a prior it then
    rationalises - this codebase has measured that failure once already
    (`VisualDraft`).

    **Every field is required, including the ones that are usually empty.** A
    field with a default is absent from the schema's `required` list, and a
    constrained decoder emits exactly what `required` forces.
    """

    model_config = ConfigDict(extra="forbid")

    element_id: Address
    measure: str = Field(max_length=PHRASE_MAX)
    dimension: str = Field(max_length=PHRASE_MAX)
    entity: str = Field(max_length=PHRASE_MAX)
    time_element_id: str = Field(max_length=ADDRESS_MAX)
    attribution: Attribution
    hedge: bool
    salience: Salience


class SentenceRange(BaseModel):
    """A quote or a claim, as two addresses and no text.

    Indices only, deliberately. An exact search for a long quotation rejects a
    real one over a single changed word, and it does so silently - which is
    worse than no check at all. Code slices the bytes between the two addresses.

    Here because decision 5 takes the attribution type and the hedge marker per
    claim, and the quote indices. The rule that anchors one is the row that adds
    the four kinds only a model can find.
    """

    model_config = ConfigDict(extra="forbid")

    sentence_start_id: Address
    sentence_end_id: Address
    speaker: str = Field(max_length=PHRASE_MAX)
    attribution: Attribution
    hedge: bool


class CallOneReply(BaseModel):
    """What the decoder is constrained to emit on call 1.

    Closed to unknown keys, and **no field of it accepts a number**. Not a
    value, not a unit, not a count, not a span and not a character offset: every
    position in this object is an address printed for the model by code, so a
    figure the article does not carry is unreachable by grammar rather than
    caught by a check downstream. `test_visual_planner` asserts that against the
    generated schema, which is where it can fail if somebody adds an `int`.

    Field order is decode order. What was found is written before what it means:
    the labels come first, then the figure code missed, then the sentence
    ranges, and the two article-level observations last.

    **It asks for no entity and no place, and that is not an omission.** A
    prompt in this repository may not ask a model to name an entity - a page
    choosing its own reader-facing tags steers a control, and
    `test_tag.py::test_no_prompt_asks_a_model_for_a_tag` holds every prompt to
    it. The two naming lists are not among the signals this call was authorised
    to take either, so they go to the row that builds their producers and that
    can put the collision to the person who owns the ruling.
    """

    model_config = ConfigDict(extra="forbid")

    labels: list[ElementLabel] = Field(max_length=LABELS_MAX)
    proposed: list[Citation] = Field(max_length=PROPOSED_MAX)
    quotes: list[SentenceRange] = Field(max_length=RANGES_MAX)
    claims: list[SentenceRange] = Field(max_length=RANGES_MAX)
    keyphrases: list[Phrase] = Field(max_length=KEYPHRASES_MAX)
    lede_sentence_ids: list[Address] = Field(max_length=LEDE_MAX)


def call_one_schema() -> dict[str, Any]:
    return CallOneReply.model_json_schema()


def call_one_system_prompt() -> str:
    return CALL_ONE_PROMPT_PATH.read_text(encoding="utf-8")


def sentence_id(index: int) -> str:
    """One sentence's address. A string, so no field of the reply is an integer."""
    return f"{_SENTENCE_PREFIX}{index}"


def sentence_number(address: str) -> int | None:
    """The sentence an address names, or nothing when it names none."""
    if not address.startswith(_SENTENCE_PREFIX):
        return None
    digits = address[len(_SENTENCE_PREFIX) :]
    return int(digits) if digits.isdigit() else None


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Where every sentence of the article starts and ends.

    Built from `elements.sentence_starts`, so the sentence a proposal names and
    the `sentence_index` an element carries are the same count of the same
    string. Two definitions of where a sentence begins would put a proposal in
    one sentence and its element in another.
    """
    starts = [0, *sentence_starts(text)]
    return list(zip(starts, [*starts[1:], len(text)], strict=True))


def numbered_sentences(text: str) -> str:
    """The article itself, one addressed sentence per line.

    The whole article rather than a lead excerpt, and the article rather than
    the summary: a compression cannot carry a fact it dropped, and judging what
    an item is about against text that lost the series is judging the wrong
    document. It is fenced as data by its caller - the addresses are ours, the
    sentences are a stranger's web page (Rule #11).
    """
    return "\n".join(
        f"[{sentence_id(index)}] {text[start:end].strip()}"
        for index, (start, end) in enumerate(sentence_spans(text))
    )


def candidate_menu(table: ElementTable) -> str:
    """The quantities and dates code already cut, each at the address to cite.

    The address is the element's own id, which is derived from its kind and its
    span - so a label can only ever name a fact that exists, and an id the model
    invented resolves to nothing and is dropped.
    """
    if not table.elements:
        return "(no quantities or dates were found in this item)"
    return "\n".join(
        f"[{element.element_id}] {element.span_excerpt}"
        f" = {element.value}{' ' + element.unit if element.unit else ''}"
        f" (sentence {sentence_id(element.sentence_index)})"
        for element in table.elements
    )


def call_one_user_turn(article: Article, table: ElementTable) -> str:
    """The title, the addressed article and the candidate table - all fenced.

    It refuses a table built over a different string than the article it is
    printed beside. Every address in the menu is an offset into `Article.text`,
    so a mismatch prints a menu whose rows point into a document the model is
    not reading - and every label that came back would anchor somewhere else,
    with nothing downstream able to tell.
    """
    text = article.text or ""
    if derive_text_digest(text) != table.source_text_hash:
        raise SpanDriftError(
            f"{article.item_id}: the candidate table indexes a different string than this article"
        )
    parts = [f"Title: {article.title}" if article.title else "Title: (untitled)"]
    parts.append("The item, one sentence per line:\n" + untrusted_block(numbered_sentences(text)))
    parts.append(
        "Quantities and dates already found in it:\n" + untrusted_block(candidate_menu(table))
    )
    return "\n\n".join(parts)


def build_call_one_request(
    article: Article,
    table: ElementTable,
    *,
    model_id: str,
    inference: InferenceConfig,
) -> dict[str, Any]:
    """Call 1's request body, with the reply shape enforced by the decoder.

    The output budget is the role's own and is not narrowed here. Call 2 appends
    to this message array and its budget is derived from both replies' bounds
    together, which is the row that adds the second call.
    """
    return request_payload(
        model_id=model_id,
        system=call_one_system_prompt(),
        user=call_one_user_turn(article, table),
        output_schema=call_one_schema(),
        inference=inference,
        schema_name="call_one",
    )


def parse_call_one(raw: str) -> CallOneReply:
    content = _THINK.sub("", raw).strip()
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    return CallOneReply.model_validate_json(content)


def _slug(words: str) -> str | None:
    """The controlled form of a word the model wrote, or nothing when there is none.

    `Element.dimension` and `Element.entity` are slugs, because two articles'
    words for one breakdown have to compare as a string or the field groups
    nothing. Lowercase, one separator, no padding - and a reading that empties
    is refused rather than written as an empty group.
    """
    slug = _SLUG_SEPARATORS.sub("-", words.strip().casefold()).strip("-")
    return slug or None


def _judgements(
    label: ElementLabel,
    *,
    dates: Mapping[str, str],
    entity_slugs: Mapping[str, str],
    label_source: str,
) -> dict[str, Any]:
    """The Tier 2 cells one label assigns, and none it cannot anchor.

    Each field degrades on its own: a `time_element_id` naming no date drops the
    time and keeps the measure, because a label is several judgements and one of
    them being unusable says nothing about the others.
    """
    judged: dict[str, Any] = {"salience": SALIENCE_SCORE[label.salience], "hedge": label.hedge}
    if label.attribution != UNATTRIBUTED:
        judged["attribution"] = label.attribution
    if measure := label.measure.strip():
        judged["measure"] = measure
    if (dimension := _slug(label.dimension)) is not None:
        judged["dimension"] = dimension
    # The model names an entity in the item's words; the slug it groups under is
    # the watchlist's. An unknown name is a name we do not track yet, not a new
    # entity this pass may mint - the alias ledger is a later row's work.
    if (slug := entity_slugs.get(label.entity.strip().casefold())) is not None:
        judged["entity"] = slug
    if (stated := dates.get(label.time_element_id)) is not None:
        judged["time"] = stated
    judged["label_source"] = label_source
    judged["ledger_version"] = LABEL_PASS_VERSION
    return judged


def apply_labels(
    table: ElementTable,
    reply: CallOneReply,
    *,
    label_source: str,
    entity_slugs: Mapping[str, str] | None = None,
) -> ElementTable:
    """The reply's judgements written onto the candidates they cite.

    **A label citing an address the pass never minted is dropped, and its
    siblings stand.** That is the whole adjudication for this shape: a label
    carries no location of its own, so an id that resolves to nothing leaves
    nothing to anchor and the rejection costs one label rather than the article
    (section 1a, degrade rather than fail).

    The first citation of an address wins. A second one is a second opinion
    about one fact, and taking the last would make the result depend on decode
    order for no stated reason.

    Nothing here is written with `model_copy`, which does not validate: every
    element is rebuilt through the contract, so a judgement the shape refuses
    fails here rather than at whatever reads the table next.
    """
    known = {element.element_id for element in table.elements}
    dates = {
        element.element_id: element.value
        for element in table.elements
        if element.kind is ElementKind.DATE and element.value is not None
    }
    judged: dict[str, dict[str, Any]] = {}
    for label in reply.labels:
        if label.element_id not in known or label.element_id in judged:
            continue
        judged[label.element_id] = _judgements(
            label,
            dates=dates,
            entity_slugs=entity_slugs or {},
            label_source=label_source,
        )
    elements = [
        Element.model_validate(element.model_dump() | judged[element.element_id])
        if element.element_id in judged
        else element
        for element in table.elements
    ]
    return ElementTable.model_validate(table.model_dump() | {"elements": elements})


def proposed_quantities(text: str, reply: CallOneReply) -> list[Element]:
    """The figures the pattern missed, cut out of the article's own bytes.

    The escape hatch decision 3 asks for, and the reason it is safe is that the
    model supplies no digits: it names one sentence and the words it means, code
    searches **only** that sentence, demands exactly one hit, and re-reads the
    value and the unit with the same number pattern the candidate pass uses.
    What lands is the article's characters at an offset code computed.

    Three refusals, and each one is ambiguity rather than a near miss:

    - a sentence address that names no sentence,
    - a surface that occurs twice in it or not at all - the mis-pointing failure
      no span check can see, so ambiguity is refused rather than guessed,
    - a surface holding no readable figure, or holding two. A number spelled out
      in words and a relative change stay refused here, because there is nothing
      for the pattern to parse.

    Stamped `Extractor.MODEL`, which is this contract's word for the path
    decision 3 spells `model_proposed`: the model proposed the location and code
    cut the characters at it. The later rows' kinds are model-pointed the same
    way and are not proposals, so the field names the path rather than the shape.
    """
    spans = sentence_spans(text)
    starts = sentence_starts(text)
    found: list[Element] = []
    for citation in reply.proposed:
        index = sentence_number(citation.sentence_id)
        if index is None or index >= len(spans):
            continue
        first, last = spans[index]
        sentence = text[first:last]
        surface = citation.surface.strip()
        if sentence.count(surface) != 1:
            continue
        offset = first + sentence.index(surface)
        readings = [
            (match, reading)
            for match in NUMBER.finditer(text, offset, offset + len(surface))
            if (reading := read_quantity(match)) is not None
        ]
        if len(readings) != 1:
            continue
        match, reading = readings[0]
        span_start, span_end = match.start(), reading.span_end
        found.append(
            Element(
                element_id=derive_element_id(ElementKind.QUANTITY, span_start, span_end),
                kind=ElementKind.QUANTITY,
                span_start=span_start,
                span_end=span_end,
                span_excerpt=text[span_start:span_end],
                value=reading.value,
                unit=reading.unit,
                sentence_index=bisect_right(starts, span_start),
                extractor=Extractor.MODEL,
            )
        )
    return found


def anchored(
    table: ElementTable,
    text: str,
    reply: CallOneReply,
    *,
    config: ElementsConfig,
    label_source: str,
    entity_slugs: Mapping[str, str] | None = None,
) -> ElementTable:
    """One candidate table, plus what the model recovered and what it said.

    `text` is the `Article.text` the table was built over - the same string its
    spans index. Pass anything else and every offset points somewhere else.

    A proposal that overlaps an element the pass already holds is dropped before
    anything is settled. `proposed` is the recovery for a figure the pattern
    **missed**, so a second reading of a stretch of characters code already read
    is not a recovery; leaving it to `settle` would let the later pass take a
    span off the earlier one on nothing better than which offset came first.

    **The merged table is bounded by `max_per_article` plus the proposal cap,
    not by `max_per_article` alone.** The pattern's own bound is the thing a
    recovery is most often needed past: a dense article keeps the first 256
    figures in article order and the ones after that are exactly what nobody
    can label. Spending the recovery out of the pattern's budget would make the
    escape hatch unreachable on the articles that need it, and there are at most
    four proposals, so the total is still a stated bound on work. Nothing is
    ever evicted here - the merge only adds.

    `candidates_found` counts every proposal that read as a figure, including
    the ones dropped next. It is one count per pass taken before the rules that
    remove, which is what keeps it able to say the cap bit and by how much.
    """
    proposals = proposed_quantities(text, reply)
    taken = [(element.span_start, element.span_end) for element in table.elements]
    fresh = [
        element
        for element in proposals
        if not any(start < element.span_end and element.span_start < end for start, end in taken)
    ]
    found = dict(table.candidates_found)
    found[ElementKind.QUANTITY] = found.get(ElementKind.QUANTITY, 0) + len(proposals)
    merged = ElementTable.model_validate(
        table.model_dump()
        | {
            "elements": settle([*table.elements, *fresh])[
                : config.max_per_article + PROPOSED_MAX
            ],
            "candidates_found": found,
        }
    )
    labelled = apply_labels(merged, reply, label_source=label_source, entity_slugs=entity_slugs)
    if (drift := labelled.span_drift(text)) is not None:
        raise SpanDriftError(f"call 1 cannot re-slice its own output: {drift}")
    return labelled

