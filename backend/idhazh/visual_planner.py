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

from collections.abc import Mapping, Sequence
from math import ceil
from typing import NamedTuple

from idhazh.contracts.element import (
    Element,
    ElementTable,
)
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.summary import Summary
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
)
from idhazh.elements import (
    read_value,
)
from idhazh.sanitize import sanitize
from idhazh.visual_validator import Rejection, validate_plan
from idhazh.visual_vocabulary import (
    DOWNGRADE_EDGES,
    ROLE_KINDS,
    TYPE_RULES,
    VALUE_ROLES,
    commensurable,
)


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


def plan_lost_to_the_window(
    summary: Summary, *, model_id: str, decided_at: str, version: str
) -> VisualDecision:
    """The same cut reply, when the window and not the budget is what stopped it.

    Both arrive as one thing - a reply that stopped because it hit a wall - and
    the server reports them identically, so only arithmetic tells them apart:
    a prompt with less room left in front of it than the summarize-and-plan call's grammar may write
    ran into the window. The caller does that comparison; this writes the answer.

    It is a separate member because it asks an operator for different work. A
    budget cut is the reply shape's own arithmetic and the fix is in the
    grammar. This one is the article in front of the reply, and the fix is
    `models.summarize.inference.n_ctx` beside `extract.truncation_cap_tokens` -
    two knobs, one decision. A run of these says the window is too narrow for
    the cap, which is a sentence no count of `output_budget_cut` can make.
    """
    return _nothing(
        summary,
        model_id=model_id,
        reason=(
            "the article and the labelling reply filled the window, so the reply "
            "was cut at the wall before the plan was written"
        ),
        decided_at=decided_at,
        version=version,
        none_reason=NoneReason.WINDOW_EXHAUSTED,
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
    count, so a stranger's page cannot steer our control flow (Guardrail #11) - the
    same property the single-call gate above holds and for the same reason.
    """
    # Every type in the vocabulary is a chart, so an operator who takes `chart`
    # out of `enabled_kinds` has said no picture is reachable at all. Read here
    # rather than at the call site because this is the one function the gate and
    # the budget sizing both go through.
    if VisualKind.CHART not in visuals.enabled_kinds:
        return ()
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

    False suppresses the plan fields inside the summarize-and-plan call and never skips the call,
    because the summarize-and-plan call is the call that writes the summary (O43). What is saved is
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
    did not write (Guardrail #11).
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


def not_drawable_here(
    summary: Summary, *, why: str, model_id: str, decided_at: str, version: str
) -> VisualDecision:
    """The `none` an item gets when a plan was drafted and this build drew nothing.

    Its sibling above is for a plan the validator refused by name. This one is
    for the two ways a drafted plan reaches no picture with no rejection to
    quote, and both are reachable only from a stage that dispatches the summarize-and-plan call:

    - the reply's plan half will not hold `VisualPlan`'s own rules, which a
      grammar cannot enforce because they read one field against another;
    - every check passed and the compiler still could not draw it.

    One `none_reason` between them, and the same one the validator's refusal
    records. `decided_without_the_model` states the rule this follows: one
    member per gate, never one per call site - what an operator acts on is the
    gate, and the gate here is "a plan was drafted and this build refuses it".
    `why` is ours rather than the model's, so the rationale says which of the
    two it was.
    """
    return _nothing(
        summary,
        model_id=model_id,
        reason=why,
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


