"""Decide whether an item gets a chart or nothing.

The control that matters is not the prompt. It is that **the model never emits a
number**. Numbers are pulled out of the article text deterministically, and the
model is only allowed to choose which table to draw, which row to emphasise and
how to word a title, by row code. A chart value that is not in the article is
therefore unreachable rather than unlikely, and the oracle for this stage is a
contract test rather than a hope.

"Nothing" is the common and correct answer. Two items in three carry no visual,
so `none` is the default that everything else has to earn its way past.

The call that reads the article is built in `idhazh.classify.calls`. This module
holds what happens to its answer: the `none` that leaves a picture out and the
reason it carries, and the ladder that steps a refused plan down.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import ceil
from typing import NamedTuple

from idhazh.contracts.element import (
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
from idhazh.contracts.visual_telemetry import ValidatorCheck
from idhazh.render.chart import can_compile
from idhazh.sanitize import sanitize
from idhazh.visual_validator import Rejection, validate_plan
from idhazh.visual_vocabulary import (
    DOWNGRADE_EDGES,
    TYPE_RULES,
    DowngradeEdge,
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
    `--ctx-size` on the summarize entry beside `extract.truncation_cap_tokens` -
    two knobs, one decision. A run of these says the window is too narrow for
    the cap, which is a sentence no count of `output_budget_cut` can make.
    """
    return _nothing(
        summary,
        model_id=model_id,
        reason=(
            "the prompt filled the window, so the reply "
            "was cut at the wall before the plan was written"
        ),
        decided_at=decided_at,
        version=version,
        none_reason=NoneReason.WINDOW_EXHAUSTED,
    )


# --- The answers that leave a picture out --------------------------------------


def suppressed_by_the_gate(
    summary: Summary, *, model_id: str, decided_at: str, version: str
) -> VisualDecision:
    """The `none` an item gets when the request did not ask for a chart.

    Charts were disabled, there were too few readings, or the chart
    instructions would not fit the window.

    `asked_the_model` stays true: the model WAS asked, for the summary, in the same
    request. Only the answer about a chart was taken off the grammar.
    """
    return _nothing(
        summary,
        model_id=model_id,
        reason="the question about a chart was left off the request",
        decided_at=decided_at,
        version=version,
        none_reason=NoneReason.NOT_REACHABLE,
    )


def declined_by_the_model(
    summary: Summary, *, model_id: str, decided_at: str, version: str
) -> VisualDecision:
    """The `none` an item gets when the model was asked and answered null."""
    return _nothing(
        summary,
        model_id=model_id,
        reason="the model proposed no chart",
        decided_at=decided_at,
        version=version,
        drafted_chart=False,
        none_reason=NoneReason.MODEL_DECLINED,
    )


def not_drawable_here(
    summary: Summary, *, why: str, model_id: str, decided_at: str, version: str
) -> VisualDecision:
    """The `none` an item gets when a plan was drafted and this build drew nothing.

    The one answer for every route from a drafted plan to no picture, and `why` -
    ours rather than the model's - says which route it was. All of them are
    reachable only from a stage that dispatches the summarize-and-plan call:

    - the reply's plan half will not hold `VisualPlan`'s own rules, which a
      grammar cannot enforce because they read one field against another;
    - the plan names a type the operator did not select;
    - the validator refused the plan, or its type has no compiler, and no
      replacement cleared validation and its floor;
    - every check passed and the compiler still could not draw it.

    **`why` names the checks that refused a plan and never restates a
    `Rejection`'s detail**, because a detail is built out of element ids, role
    names and digits and a rationale is a published cell.

    One `none_reason` between them. `decided_without_the_model` states the rule
    this follows: one member per gate, never one per call site - what an
    operator acts on is the gate, and the gate here is "a plan was drafted and
    this build refuses it".
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


@dataclass(slots=True)
class DowngradeEvidence:
    """Evidence about rungs reached and numeric floors compared during one search."""

    deepest_depth: int = 0
    gate_floor_applied: bool | None = None

    def reach(self, depth: int) -> None:
        self.deepest_depth = max(self.deepest_depth, depth)

    def compare_floor(self, marks: int, floor: int) -> bool:
        """Return eligibility and record whether a floor excluded this candidate."""
        if self.gate_floor_applied is None:
            self.gate_floor_applied = False
        cleared = marks >= floor
        if not cleared:
            self.gate_floor_applied = True
        return cleared


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
    if plan.type is VisualType.PIE and target is VisualType.STACKED_BAR:
        encodings[EncodingRole.CATEGORY.value] = (
            [plan.declared_whole_element_id]
            if plan.declared_whole_element_id is not None
            else []
        )
        encodings[EncodingRole.SERIES.value] = list(plan.encodings.category)
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
    edges: Mapping[VisualType, tuple[DowngradeEdge, ...]] = DOWNGRADE_EDGES,
    rejected: list[Rejection] | None = None,
    evidence: DowngradeEvidence | None = None,
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

    The separate activation switch leaves this path off without reading history.
    The percentile list bounds the permitted replacement depths. `edges` is a
    parameter so that a table other than the shipped one can be driven, and
    every candidate still re-validates, so an injected table can only change
    which forms are tried.
    """
    rungs = visuals.downgrade_floor_percentiles
    if (
        not visuals.downgrade_enabled
        or VisualKind.CHART not in visuals.enabled_kinds
        or plan.decision is not PlanDecision.VISUAL
        or plan.type is None
        or (visuals.type_selection_enabled and plan.type not in visuals.select_types())
    ):
        return None
    pie_whole_rejected = plan.type is VisualType.PIE and any(
        rejection.check is ValidatorCheck.PIE_EXHAUSTIVE
        for rejection in validate_plan(plan, table, visuals=visuals)
    )
    frontier: list[VisualType] = [plan.type]
    walked: set[VisualType] = {plan.type}
    for depth, percentile in enumerate(rungs, start=1):
        onward: list[VisualType] = []
        for source in frontier:
            for edge in edges.get(source, ()):
                if edge.target in walked or plan.purpose not in edge.purposes:
                    continue
                walked.add(edge.target)
                onward.append(edge.target)
                if evidence is not None:
                    evidence.reach(depth)
                if not can_compile(edge.target) or edge.target not in visuals.select_types():
                    continue
                if edge.target is VisualType.BAR and any(
                    role not in {EncodingRole.CATEGORY, EncodingRole.QUANTITY}
                    for role in plan.encodings.filled()
                ):
                    continue
                candidate = _restyled(plan, edge.target)
                # A downgrade carries a machine-checkable justification, and the
                # annotation is it: the mark that makes the weaker form still
                # worth showing. Without it depth 1 is just the default path.
                if not candidate.annotations:
                    continue
                candidate_rejections = validate_plan(candidate, table, visuals=visuals)
                if candidate_rejections:
                    if rejected is not None:
                        rejected.extend(candidate_rejections)
                    continue
                if source is VisualType.PIE and pie_whole_rejected:
                    continue
                floor = depth_floor(published_marks.get(edge.target, ()), percentile)
                if floor is None:
                    continue
                clears_floor = (
                    evidence.compare_floor(_marks(candidate), floor)
                    if evidence is not None
                    else _marks(candidate) >= floor
                )
                if not clears_floor:
                    continue
                return Downgrade(candidate, depth, (source, edge.target), floor)
        frontier = onward
    return None
