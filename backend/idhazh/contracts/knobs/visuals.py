"""Planning, rendering and serving a drawing, where nothing is the common answer by design."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final, Self

from pydantic import Field, field_validator, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.knobs.removed import refuse_a_removed_knob
from idhazh.contracts.visual_decision import VisualKind

#: The `visuals` knob this block used to carry. `canvas_width` was one fixed
#: drawing box for every visual, with a 16:10 height derived from it. The
#: reader's browser draws the chart now and takes the width the reader's screen
#: actually gives it, so there is no box to size and nothing answers the same
#: question.
SUPERSEDED_VISUALS_NAMES: Final[Mapping[str, str]] = MappingProxyType({"canvas_width": ""})


class VisualsConfig(Model):
    """Planning, rendering and serving knobs. "Nothing" is the common answer, by design.

    `enabled_kinds` is the gate that keeps an unbuilt renderer unreachable. It
    is a list rather than a flag so that a kind added later is switched on by a
    config edit rather than by a code change.

    `asset_base_url` is the same shape at the other end of the pipeline: where a
    browser asks for a drawing the pipeline already published. It ships empty,
    which means this site, and the whole point of it existing empty is that
    moving the bytes off the 1 GB Pages cap is then a config edit rather than a
    project.
    """

    enabled_kinds: list[VisualKind] = Field(
        default_factory=lambda: [VisualKind.CHART],
        description=(
            "Kinds the planner may choose. `none` is always available and never listed. "
            "Chart is the only one left: the diagram arm shipped off - the model drafted "
            "it zero times in 88 items and rendered it zero times in 703 (ubuntu-latest, "
            "2026-08-24/25), while its presence made the planner's own pre-filter "
            "unfireable, because a diagram's steps come from prose and nothing about it "
            "is decidable in advance - and its renderer was deleted with the Mermaid "
            "round trip on 2026-09-05."
        ),
    )
    min_chart_points: int = Field(
        default=3,
        ge=2,
        description="Below this a chart says less than the sentence it sits under.",
    )
    max_chart_points: int = Field(default=8, ge=2)
    histogram_bins: int = Field(
        default=3,
        ge=2,
        description=(
            "How many equal-width bins a histogram's values fall into. Binning is config "
            "and never the model's - it has no numeric field that could say. A histogram's "
            "bins ARE the marks a reader counts, so this sits inside the same "
            "min_chart_points to max_chart_points window every other type's mark count "
            "does, and a value outside it is refused here rather than left to refuse every "
            "histogram of every run for a reason no article can fix. It is also the floor "
            "on how many values a histogram may cite: fewer values than bins leaves a bin "
            "empty, and a bar counting nothing has no chain and draws nothing. The default "
            "is min_chart_points rather than a textbook rule for a sample size this stage "
            "never sees."
        ),
    )
    min_diagram_steps: int = Field(default=3, ge=2)
    max_diagram_steps: int = Field(default=6, ge=2)
    downgrade_floor_percentiles: list[int] = Field(
        default_factory=lambda: [50, 75],
        description=(
            "The ladder, as one list: how many rungs it has and how high each one is. "
            "Entry n is the percentile of depth-0 published mark counts a downgrade at "
            "depth n+1 must reach, so the length is the deepest permitted downgrade and "
            "the depth after it refuses. Two entries is the design's own ladder - the "
            "median at the first step down, the 75th percentile at the second, refuse at "
            "the third. An empty list is the ladder switched off, which is one knob doing "
            "two jobs on purpose: a separate on-off flag can disagree with the rungs "
            "beside it, and zero rungs is already an unambiguous no. It must rise, "
            "because a floor that does not is not an escalating one. The floor it reads "
            "is a mark count, which the validator already bounds to min_chart_points to "
            "max_chart_points, so two adjacent percentiles can land on one integer and "
            "the ladder quietly stops escalating - that is visible as two depths "
            "recording one floor, and the answer is to move these numbers rather than "
            "the mechanism."
        ),
    )
    max_output_tokens: int = Field(
        default=400,
        ge=1,
        description="The planner emits a small object. It does not need the summarizer's budget.",
    )
    max_facts: int = Field(
        default=16,
        ge=2,
        description=(
            "How many quantities the router may choose between. A long indexed menu is "
            "lost-in-the-middle for a small model picking an integer index."
        ),
    )
    lead_words: int = Field(
        default=150,
        ge=1,
        description=(
            "How much of the article's own opening the router reads beside the summary. "
            "This is most of each request's prefill, and prefill is most of the stage's "
            "wall-clock, so it is a measured lever rather than a literal (Guardrail #6)."
        ),
    )
    request_timeout_minutes: float = Field(
        default=2.0,
        gt=0.0,
        description=(
            "One routing POST may wait this long. Sized from the measured worst routed "
            "item - 56.0 s on ubuntu-latest, 2026-08-24 - doubled. The stage used the "
            "summarizer's 150-minute shard bound before this existed, which is longer "
            "than the job it runs in, so it could never fire."
        ),
    )
    asset_base_url: str = Field(
        default="",
        description=(
            "Where a browser asks for a published drawing. Empty means this site, and "
            "empty is what ships: the drawings sit in the bundle, and the bundle is what "
            "the 1 GB Pages ceiling counts. An absolute `https://` prefix moves the "
            "drawings a reader scrolls to off that ceiling, and the committed path is "
            "joined onto it unchanged - so which file is asked for never moves, only "
            "where it is asked for. Two costs, both measured 2026-09-02 against the "
            "candidate host: it caches for five minutes, so a repeat reader refetches, "
            "which is real on a slow connection; and the page's own `connect-src` gains "
            "that one origin, so the browser stops being the thing that makes reaching "
            "anywhere else impossible. Kept shut until the site's measured growth says "
            "otherwise."
        ),
    )

    @field_validator("asset_base_url")
    @classmethod
    def _the_valve_names_a_prefix_a_path_can_be_joined_onto(cls, value: str) -> str:
        """Empty, or an absolute `https://` prefix carrying no trailing slash.

        The value comes off our own config and never off the web (Guardrail #11), and
        it is checked all the same, because it is about to become the front half
        of every drawing address and the one origin the page's `connect-src`
        admits. A trailing slash is refused rather than trimmed: the join writes
        one, and trimming it silently is how an operator learns about the rule
        from a broken page instead of from a failed build.
        """
        if not value:
            return value
        if not value.startswith("https://"):
            raise ValueError("visuals.asset_base_url is empty or begins with https://")
        if value.endswith("/"):
            raise ValueError("visuals.asset_base_url carries no trailing slash")
        if any(character in value for character in " \t?#"):
            raise ValueError(
                "visuals.asset_base_url carries no whitespace, query or fragment"
            )
        return value

    @model_validator(mode="after")
    def _bounds_are_orderable(self) -> Self:
        """Each pair of knobs in the right order, the bin count inside the mark window,
        and the downgrade ladder's rungs rising.

        A histogram draws `histogram_bins` bars whatever any one plan says, so
        whether that many bars is readable is a question about the config and not
        about an article. Asked once here, a wrong knob names the operator who set
        it and the run never starts. The ladder's rungs are asked here for the same
        reason: a floor that falls with depth is a ladder that gets easier the
        further down it goes, which is the failure the escalating floor exists to
        prevent, and it would be found one refused item at a time.
        """
        if self.max_chart_points < self.min_chart_points:
            raise ValueError("max_chart_points is below min_chart_points")
        if self.max_diagram_steps < self.min_diagram_steps:
            raise ValueError("max_diagram_steps is below min_diagram_steps")
        if not self.min_chart_points <= self.histogram_bins <= self.max_chart_points:
            raise ValueError(
                "histogram_bins is a histogram's mark count, so it sits between "
                "min_chart_points and max_chart_points like every other type's"
            )
        rungs = self.downgrade_floor_percentiles
        if any(not 0 <= rung <= 100 for rung in rungs):
            raise ValueError("a downgrade floor is a percentile, so it is between 0 and 100")
        if rungs != sorted(set(rungs)):
            raise ValueError(
                "each rung of the downgrade ladder is higher than the one above it, or "
                "the escalating floor does not escalate"
            )
        if VisualKind.NONE in self.enabled_kinds:
            raise ValueError("`none` is always reachable and is never listed as enabled")
        return self

    @model_validator(mode="before")
    @classmethod
    def _a_removed_knob_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("visuals", data, SUPERSEDED_VISUALS_NAMES)
