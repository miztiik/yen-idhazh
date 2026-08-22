"""Decide whether an item gets a chart, a diagram, or nothing.

The control that matters is not the prompt. It is that **the model never emits a
number**. Numbers are pulled out of the article text deterministically, and the
model is only allowed to choose which of them to plot, by index. A chart value
that is not in the article is therefore unreachable rather than unlikely, and
the oracle for this stage is a contract test rather than a hope.

"Nothing" is the common and correct answer. Two items in three carry no visual,
so `none` is the default that everything else has to earn its way past.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from idhazh.contracts.app_config import InferenceConfig, VisualsConfig
from idhazh.contracts.article import Article
from idhazh.contracts.route import Route, SpecFormat, VisualKind, VisualState
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.llm.server import Completion, request_payload
from idhazh.sanitize import sanitize, untrusted_block

PROMPT_PATH: Final = Path(__file__).parent / "prompts" / "route.txt"

_THINK = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

# A number with optional thousands separators, an optional decimal part, an
# optional magnitude word, and the one word that follows it. The leading
# lookbehind excludes a hyphen so `COVID-19`, `GPT-4` and `Qwen3-4B` do not read
# as quantities.
_NUMBER = re.compile(
    r"(?<![\w.-])"
    r"(?P<currency>[$\u00a3\u20ac\u20b9]\s?)?"
    r"(?P<sign>-)?"
    r"(?P<value>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s*"
    r"(?P<magnitude>percent|per cent|%|billion|bn|million|mn|thousand|trillion|tn)?"
    r"\s*"
    r"(?P<unit>[a-zA-Z][a-zA-Z-]*)?",
    re.IGNORECASE,
)

# `m` and `k` are deliberately absent. The model never writes a number, but the
# extractor does, and reading `15 m` as fifteen million is a one-million-fold
# error on a published bar decided by a guess about metres.
_MAGNITUDE: Final[dict[str, Decimal]] = {
    "thousand": Decimal(1_000),
    "million": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "billion": Decimal(1_000_000_000),
    "bn": Decimal(1_000_000_000),
    "trillion": Decimal(1_000_000_000_000),
    "tn": Decimal(1_000_000_000_000),
}

_PERCENT: Final[frozenset[str]] = frozenset({"percent", "per cent", "%"})

# The word after a number is a unit only sometimes. These are the ones that
# never are, so a quantity does not end up measured in "of".
_NOT_A_UNIT: Final[frozenset[str]] = frozenset(
    """a an and are as at be been before but by during for from had has have he her his in is it
    its more most of on or over per said says she should such than that the their then there these
    they this to under until up was we were what when which while who will with would you""".split()
)

# A number small enough to be a date, a count of paragraphs, or a list marker
# carries no information as a bar. Charting them is how a chart becomes noise.
_TRIVIAL_MAX: Final = Decimal(2)

# A bare four-digit integer in this range, carrying no unit, is a year. A year
# is a label, not a bar height. Dropping it costs nothing, because a label is a
# free string the model can still write.
_YEAR_MIN: Final = 1900
_YEAR_MAX: Final = 2100


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


def normalise_unit(unit: str) -> str:
    """Lowercase and de-pluralised, so `Megawatts` and `megawatt` are one unit."""
    lowered = unit.strip().lower()
    if len(lowered) > 3 and lowered.endswith("s") and not lowered.endswith("ss"):
        return lowered[:-1]
    return lowered


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
    """
    facts: list[NumericFact] = []
    seen: set[tuple[Decimal, str]] = set()
    for match in _NUMBER.finditer(text):
        digits = match.group("value")
        try:
            magnitude = Decimal(digits.replace(",", ""))
        except InvalidOperation:
            continue

        suffix = (match.group("magnitude") or "").strip().lower()
        word = normalise_unit(match.group("unit") or "")
        if word in _NOT_A_UNIT:
            word = ""

        unit = ""
        if suffix in _PERCENT:
            unit = "%"
        else:
            if suffix in _MAGNITUDE:
                magnitude *= _MAGNITUDE[suffix]
            currency = (match.group("currency") or "").strip()
            unit = currency or word

        if not unit and "," not in digits and "." not in digits:
            plain = int(magnitude)
            if _YEAR_MIN <= plain <= _YEAR_MAX and len(digits) == 4:
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


class RouteDraft(BaseModel):
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
    return RouteDraft.model_json_schema()


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
    article: Article, summary: Summary, facts: list[NumericFact], *, lead_words: int = 150
) -> str:
    """The summary, the article's own opening, and the indexed numbers - all fenced.

    The article lead is here because the quantities are extracted from the
    article while the summary is a compression of it. Judging "is this
    comparison the point of the story" against text that may have dropped the
    whole series is judging the wrong document, and it would let a chart carry
    numbers no sentence beside it mentions.
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
    routing = inference.model_copy(update={"max_output_tokens": visuals.max_output_tokens})
    return request_payload(
        model_id=model_id,
        system=system_prompt(),
        user=user_turn(article, summary, facts),
        output_schema=output_schema(),
        inference=routing,
        schema_name="route",
    )


def parse_draft(raw: str) -> RouteDraft:
    content = _THINK.sub("", raw).strip()
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    return RouteDraft.model_validate_json(content)


def _nothing(
    summary: Summary, *, model_id: str, reason: str, routed_at: str, version: str
) -> Route:
    return Route(
        version=version,
        item_id=summary.item_id,
        url_key=summary.url_key,
        kind=VisualKind.NONE,
        rationale=sanitize(reason)[:200] or None,
        model_id=model_id,
        routed_at=routed_at,
    )


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
    the caller still routes to nothing.

    Ties resolve to the group whose first bar came earliest, so the same input
    always produces the same chart.
    """
    groups: dict[str, list[ChartPoint]] = {}
    for point in points:
        groups.setdefault(facts[point.fact_index].unit, []).append(point)
    unit = max(groups, key=lambda key: (len(groups[key]), -points.index(groups[key][0])))
    return unit, groups[unit]


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


def diagram_spec(steps: list[str], *, caption: str) -> str:
    """Mermaid source. Persisted as the record, rendered by our own layout.

    Mermaid is the interchange format so anyone can re-render this with the real
    Mermaid toolchain. We do not run that toolchain: it needs a headless browser,
    and a linear chain of labelled boxes does not.

    Top-down rather than left-right: at six steps a horizontal chain gives each
    box about 130 px inside our canvas, which is narrower than most of the labels.
    """
    lines = ["flowchart TD"]
    if caption:
        lines.insert(0, f"%% {sanitize(caption)[:120]}")
    for index, step in enumerate(steps):
        label = sanitize(step)[:60].replace('"', "'")
        lines.append(f'    n{index}["{label}"]')
    for index in range(len(steps) - 1):
        lines.append(f"    n{index} --> n{index + 1}")
    return "\n".join(lines)


def alt_text(draft: RouteDraft, facts: list[NumericFact]) -> str:
    """What a screen reader gets. The visual is never the only carrier of a fact."""
    if draft.kind == "chart":
        parts = [
            f"{sanitize(point.label)[:40]} "
            f"{facts[point.fact_index].raw} {facts[point.fact_index].unit}".strip()
            for point in draft.points
        ]
        return f"Bar chart. {'; '.join(parts)}."[:300]
    labels = " then ".join(sanitize(step)[:60] for step in draft.steps)
    return f"Flow diagram. {labels}."[:300]


def to_route(
    article: Article,
    summary: Summary,
    completion: Completion,
    *,
    model_id: str,
    routed_at: str,
    visuals: VisualsConfig,
    facts: list[NumericFact] | None = None,
) -> Route:
    """One completion becomes exactly one routing decision, or becomes `none`.

    Every rejection path lands on `none` with a rationale. A visual is never
    allowed to be the reason an item does not publish.
    """
    version = Route.schema_version()
    available = facts if facts is not None else numeric_facts(article.text or "")

    if summary.status is not SummaryStatus.OK:
        return _nothing(
            summary,
            model_id=model_id,
            reason="the item has no summary, so there is nothing to illustrate",
            routed_at=routed_at,
            version=version,
        )
    if completion.hit_the_budget:
        return _nothing(
            summary,
            model_id=model_id,
            reason="the routing reply was cut off by the output budget",
            routed_at=routed_at,
            version=version,
        )
    try:
        draft = parse_draft(completion.content)
    except (ValidationError, ValueError, json.JSONDecodeError) as error:
        return _nothing(
            summary,
            model_id=model_id,
            reason=f"the routing reply did not hold its shape: {type(error).__name__}",
            routed_at=routed_at,
            version=version,
        )

    if draft.kind == "none":
        return _nothing(
            summary,
            model_id=model_id,
            reason=draft.reason,
            routed_at=routed_at,
            version=version,
        )

    kind = VisualKind(draft.kind)
    if kind not in visuals.enabled_kinds:
        return _nothing(
            summary,
            model_id=model_id,
            reason=f"{kind.value} has no renderer switched on",
            routed_at=routed_at,
            version=version,
        )

    if kind is VisualKind.CHART:
        if any(point.fact_index >= len(available) for point in draft.points):
            return _nothing(
                summary,
                model_id=model_id,
                reason="the chart pointed at a quantity the article does not contain",
                routed_at=routed_at,
                version=version,
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
                routed_at=routed_at,
                version=version,
            )
        draft = draft.model_copy(update={"points": bars})
        # A caption written about five bars is a false statement about three.
        # The live 4B captioned a chart "Solar Capacity and Employment" and then
        # had its employment bar dropped, which is exactly the kind of small lie
        # that costs a reader their trust in every other number on the page.
        caption = draft.caption if len(bars) == kept_from else ""
        spec: str = json.dumps(
            chart_spec(bars, available, caption=caption, unit=unit, visuals=visuals),
            separators=(",", ":"),
            sort_keys=True,
        )
        spec_format = SpecFormat.VEGA_LITE
    else:
        if not visuals.min_diagram_steps <= len(draft.steps) <= visuals.max_diagram_steps:
            return _nothing(
                summary,
                model_id=model_id,
                reason=f"{len(draft.steps)} steps is outside the publishable range",
                routed_at=routed_at,
                version=version,
            )
        spec = diagram_spec(draft.steps, caption=draft.caption)
        spec_format = SpecFormat.MERMAID

    return Route(
        version=version,
        item_id=summary.item_id,
        url_key=summary.url_key,
        kind=kind,
        rationale=sanitize(draft.reason)[:200] or None,
        spec=spec,
        spec_format=spec_format,
        alt_text=sanitize(alt_text(draft, available))[:300] or None,
        visual_state=VisualState.ABSENT,
        model_id=model_id,
        routed_at=routed_at,
    )
