"""The visual planner, and the one property the whole row exists to guarantee.

The oracle for Row #8 is: every value in a rendered chart is present in the
source article. It is asserted here as a property over generated drafts rather
than as a spot check, because the guarantee is structural - the model chooses an
index, so a number it never saw is not reachable.
"""

from __future__ import annotations

import itertools
import json
from typing import Any

import pytest
from pydantic import ValidationError
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text
from support.prompts import (
    WIND_TEXT,
    chart_data_over,
    summary_payload,
)
from support.visual_plans import current_plan

from idhazh import config, summarize
from idhazh.classify.calls import (
    summarize_and_plan_model,
    summarize_and_plan_schema,
)
from idhazh.contracts.article import Article
from idhazh.contracts.element import ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import (
    EncodingRole,
    VisualPlan,
    VisualPurpose,
    VisualType,
)
from idhazh.contracts.visual_decision import NoneReason, VisualDecision
from idhazh.contracts.visual_telemetry import ValidatorCheck
from idhazh.render.chart import can_compile
from idhazh.visual_planner import (
    Downgrade,
    DowngradeEvidence,
    depth_floor,
    downgrade,
)
from idhazh.visual_validator import Rejection, validate_plan
from idhazh.visual_vocabulary import DowngradeEdge

pytestmark = pytest.mark.visual

# --- Row #4: the ladder, and the reason every `none` carries -------------------

VALIDATOR_FIXTURES = FIXTURES_DIR / "visual-validator"


def committed_visuals(**knobs: Any) -> VisualsConfig:
    """The knobs the pipeline ships, through validation rather than around it.

    `model_copy(update=...)` sets an attribute without running a validator, so a
    config it produces can be one the pipeline would refuse to load.
    """
    shipped = config.load(CONFIG_DIR).app.visuals
    return VisualsConfig.model_validate(shipped.model_dump(mode="json") | knobs)


def narrowed_table(name: str, *element_ids: str) -> ElementTable:
    """A committed validator table, narrowed to these elements.

    Built rather than found, so a case can name the few elements it is about
    without a fixture of its own (`CLAUDE.md` Guardrail #12).
    """
    payload = json.loads(read_text(VALIDATOR_FIXTURES / "tables" / f"{name}.json"))
    payload["elements"] = [one for one in payload["elements"] if one["element_id"] in element_ids]
    return ElementTable.model_validate(payload)


def wind_table(*element_ids: str) -> ElementTable:
    """The committed wind table, narrowed to these elements."""
    return narrowed_table("wind", *element_ids)


def wind_plan_payload() -> dict[str, Any]:
    """The committed four-bar plan as a payload, read and validated on each call."""
    return current_plan(VALIDATOR_FIXTURES / "plans" / "passes.json").model_dump(mode="json")


def wind_plan(**changed: Any) -> VisualPlan:
    """The committed four-bar plan over that table, with these fields moved."""
    return VisualPlan.model_validate(wind_plan_payload() | changed)


def downgrade_visuals(**knobs: Any) -> VisualsConfig:
    """The shipped knobs with the ladder on, the design's two rungs and type selection off.

    Selection is off so a walk is bounded by what the compiler can draw, and by
    nothing the committed `enabled_types` happens to hold.
    """
    ladder = {
        "type_selection_enabled": False,
        "downgrade_enabled": True,
        "downgrade_floor_percentiles": [50, 75],
    }
    return committed_visuals(**(ladder | knobs))


def edges_along(
    *forms: VisualType, keeping: VisualPurpose
) -> dict[VisualType, tuple[DowngradeEdge, ...]]:
    """An edge table of one path: each form steps down to the next and keeps this purpose."""
    return {
        source: (DowngradeEdge(target, frozenset({keeping})),)
        for source, target in itertools.pairwise(forms)
    }


WHOLE = (
    "date-35-39",
    "entity-41-48",
    "entity-68-75",
    "entity-86-92",
    "entity-104-111",
    "quantity-58-66",
    "quantity-76-84",
    "quantity-93-99",
    "quantity-112-120",
)


class TestAnItemWithNoChartDataIsNotAskedForAPlan:
    def test_the_suppressed_grammar_has_nowhere_to_write_a_plan(self) -> None:
        """The grammar is the control: a suppressed request cannot carry a plan.

        Every name is read from the models the grammars are derived from: the
        reply declares its summary first and its plan second, and the suppressed
        reply is the summary draft alone.
        """
        summary_field, plan_field = summarize_and_plan_model().model_fields
        whole = summarize_and_plan_schema()
        suppressed = summarize_and_plan_schema(plan=False)

        assert set(whole["properties"]) == {summary_field, plan_field}
        assert plan_field not in suppressed["properties"]
        assert set(suppressed["properties"]) == set(summarize.SummaryDraft.model_fields)

    def test_suppressing_the_plan_leaves_the_article_unchanged(
        self, article_ok: Article
    ) -> None:
        """Only the chart-capable variant has the system addendum."""
        wind = article_ok.model_copy(update={"text": WIND_TEXT})
        _, data = chart_data_over(article_ok, WIND_TEXT)
        whole = summary_payload(wind, data=data)
        suppressed = summary_payload(wind)
        assert "Available chart types:" in whole["prompt"]
        assert "Available chart types:" not in suppressed["prompt"]
        suffix = whole["prompt"].split(WIND_TEXT, 1)[1]
        assert suppressed["prompt"].split(WIND_TEXT, 1)[1] == suffix

class TestTheNoneReasonOnAStoredDecision:
    """What a stored decision may say about why it carries no picture.

    That each route to `none` records its own reason is asserted through the
    production router in `test_visual_attempts.py`.
    """

    def test_a_decision_that_carries_a_picture_carries_no_reason(self) -> None:
        rendered = VisualDecision.from_json(
            read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json")
        )
        with pytest.raises(ValidationError):
            VisualDecision.model_validate(
                rendered.model_dump(mode="json")
                | {"none_reason": NoneReason.MODEL_DECLINED.value}
            )

    def test_a_payload_written_before_the_field_existed_still_loads(self) -> None:
        """The read-side migration, proved by removing the key rather than by a date."""
        payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "none.json"))
        del payload["none_reason"]

        assert VisualDecision.model_validate(payload).none_reason is None


class TestTheDowngradeLadder:
    """The ladder's rescues and refusals: the nearest built neighbour, an unchanged
    element set, an escalating floor, and the validator's refusals.

    The shipped edge table is all one-step edges, so what a purpose, a chain, a
    walked type, an unbuilt neighbour or a channel limit does is driven through
    small tables built here and passed in.
    """

    def unruled_comparison(self) -> VisualPlan:
        """A historical comparison request with no role rule."""
        return wind_plan(type=VisualType.COMPARISON.value)

    def wind_purpose(self) -> VisualPurpose:
        """What the committed wind plan asks of its reader, which every edge built here keeps."""
        purpose = wind_plan().purpose
        assert purpose is not None
        return purpose

    def test_the_case_this_class_is_built_on_really_is_refused(self) -> None:
        table = wind_table(*WHOLE)
        assert validate_plan(self.unruled_comparison(), table, visuals=committed_visuals())
        assert not can_compile(self.unruled_comparison().type)

    def test_a_refused_plan_is_re_drawn_as_the_nearest_built_neighbour(self) -> None:
        made = downgrade(
            self.unruled_comparison(),
            wind_table(*WHOLE),
            visuals=downgrade_visuals(),
            published_marks={VisualType.BAR: [3, 4, 5, 8]},
        )

        assert made is not None
        assert made.plan.type is VisualType.BAR
        assert made.edge == (VisualType.COMPARISON, VisualType.BAR)
        assert made.depth == 1

    def test_invariance_one_the_element_set_does_not_change(self) -> None:
        """A downgrade is the same claim re-drawn. It is never permission to go
        and find something else to draw."""
        plan = self.unruled_comparison()
        made = downgrade(
            plan,
            wind_table(*WHOLE),
            visuals=downgrade_visuals(),
            published_marks={VisualType.BAR: [3, 4, 5, 8]},
        )

        assert made is not None
        assert made.plan.element_ids == plan.element_ids
        assert made.plan.labels == plan.labels
        assert made.plan.annotations == plan.annotations

    def test_a_failed_pie_whole_reenters_the_stacked_whole_check(self) -> None:
        plan = VisualPlan.from_json(
            read_text(VALIDATOR_FIXTURES / "plans" / "pie-not-exhaustive.json")
        )
        table = ElementTable.from_json(
            read_text(VALIDATOR_FIXTURES / "tables" / "pie-whole.json")
        )
        rejected: list[Rejection] = []
        made = downgrade(
            plan,
            table,
            visuals=downgrade_visuals(),
            published_marks={VisualType.STACKED_BAR: [3, 4, 5, 8]},
            rejected=rejected,
        )

        assert made is None
        assert any(
            rejection.check is ValidatorCheck.STACKED_BAR_EXHAUSTIVE
            for rejection in rejected
        )

    def test_invariance_three_a_floor_that_cannot_be_computed_is_not_cleared(self) -> None:
        """Waiving it would make depth 1 publish on the validator alone, which is
        depth 1 quietly becoming the default path."""
        assert depth_floor((), 50) is None
        assert (
            downgrade(
                self.unruled_comparison(),
                wind_table(*WHOLE),
                visuals=downgrade_visuals(),
                published_marks={},
            )
            is None
        )

    def test_invariance_three_a_thin_downgrade_does_not_clear_a_fat_corpus(self) -> None:
        made = downgrade(
            self.unruled_comparison(),
            wind_table(*WHOLE),
            visuals=downgrade_visuals(),
            published_marks={VisualType.BAR: [5, 6, 7, 8]},
        )

        assert made is None

    def test_a_downgrade_with_no_annotation_is_refused(self) -> None:
        """The machine-checkable justification: the mark that makes the weaker
        form still worth showing."""
        assert (
            downgrade(
                wind_plan(type=VisualType.COMPARISON.value, annotations=[]),
                wind_table(*WHOLE),
                visuals=downgrade_visuals(),
                published_marks={VisualType.BAR: [3, 4, 5, 8]},
            )
            is None
        )

    def test_target_validation_still_refuses_an_invented_source_figure(self) -> None:
        table = wind_table(*WHOLE).model_dump(mode="json")
        quantity = next(
            element
            for element in table["elements"]
            if element["element_id"] == self.unruled_comparison().encodings.quantity[0]
        )
        quantity["value"] = "999999"
        assert (
            downgrade(
                self.unruled_comparison(),
                ElementTable.model_validate(table),
                visuals=downgrade_visuals(),
                published_marks={VisualType.BAR: [3, 4, 5, 8]},
            )
            is None
        )

    def test_the_separate_switch_blocks_rescue_with_populated_rungs(self) -> None:
        assert (
            downgrade(
                self.unruled_comparison(),
                wind_table(*WHOLE),
                visuals=downgrade_visuals(downgrade_enabled=False),
                published_marks={VisualType.BAR: [3, 4, 5, 8]},
            )
            is None
        )

    def test_an_edge_that_leaves_out_the_plans_purpose_is_not_taken(self) -> None:
        """Invariance two for one step: the same plan is refused down an edge that keeps
        every other purpose, and re-drawn down the edge that keeps its own."""
        purpose = self.wind_purpose()

        def step_along(purposes: frozenset[VisualPurpose]) -> Downgrade | None:
            return downgrade(
                self.unruled_comparison(),
                wind_table(*WHOLE),
                visuals=downgrade_visuals(),
                published_marks={VisualType.BAR: [3, 4, 5, 8]},
                edges={VisualType.COMPARISON: (DowngradeEdge(VisualType.BAR, purposes),)},
            )

        assert step_along(frozenset(VisualPurpose) - {purpose}) is None
        kept = step_along(frozenset({purpose}))
        assert kept is not None
        assert kept.edge == (VisualType.COMPARISON, VisualType.BAR)

    def test_a_later_step_that_drops_the_plans_purpose_is_refused_though_the_first_kept_it(
        self,
    ) -> None:
        """Invariance two for a chain: every step is asked about the purpose the plan
        started with, so a step that kept it does not carry the next one through."""
        purpose = self.wind_purpose()
        keeps, drops = frozenset({purpose}), frozenset(VisualPurpose) - {purpose}

        def walk(last_step: frozenset[VisualPurpose]) -> Downgrade | None:
            return downgrade(
                self.unruled_comparison(),
                wind_table(*WHOLE),
                visuals=downgrade_visuals(),
                published_marks={VisualType.BAR: [3, 3, 3, 3]},
                edges={
                    VisualType.COMPARISON: (DowngradeEdge(VisualType.LINE, keeps),),
                    VisualType.LINE: (DowngradeEdge(VisualType.BAR, last_step),),
                },
            )

        assert walk(drops) is None
        whole_chain = walk(keeps)
        assert whole_chain is not None
        assert whole_chain.edge == (VisualType.LINE, VisualType.BAR)

    def test_the_second_step_of_a_chain_reads_the_second_rungs_percentile(self) -> None:
        """Invariance three: a form reached at depth two is held to the second rung's
        floor, and the first step, which the validator refuses, does not end the walk."""
        visuals = downgrade_visuals()
        first, second = visuals.downgrade_floor_percentiles
        population = [3, 3, 4, 8]
        assert depth_floor(population, first) != depth_floor(population, second)

        made = downgrade(
            self.unruled_comparison(),
            wind_table(*WHOLE),
            visuals=visuals,
            published_marks={VisualType.BAR: population},
            edges=edges_along(
                VisualType.COMPARISON,
                VisualType.LINE,
                VisualType.BAR,
                keeping=self.wind_purpose(),
            ),
        )

        assert made is not None
        assert made.edge == (VisualType.LINE, VisualType.BAR)
        assert made.depth == 2
        assert made.floor == depth_floor(population, second)

    def test_a_chain_longer_than_the_rungs_is_not_walked_past_the_last_rung(self) -> None:
        """The percentile list bounds the depth: the form three steps down is out of
        reach on two rungs and within it on three."""
        chain = edges_along(
            VisualType.COMPARISON,
            VisualType.LINE,
            VisualType.SCATTER,
            VisualType.BAR,
            keeping=self.wind_purpose(),
        )
        rungs = downgrade_visuals().downgrade_floor_percentiles
        assert len(chain) > len(rungs)

        def walk(percentiles: list[int], evidence: DowngradeEvidence) -> Downgrade | None:
            return downgrade(
                self.unruled_comparison(),
                wind_table(*WHOLE),
                visuals=downgrade_visuals(downgrade_floor_percentiles=percentiles),
                published_marks={VisualType.BAR: [3, 3, 3, 4]},
                edges=chain,
                evidence=evidence,
            )

        within = DowngradeEvidence()
        assert walk(rungs, within) is None
        assert within.deepest_depth == len(rungs)

        beyond = walk([*rungs, 100], DowngradeEvidence())
        assert beyond is not None
        assert beyond.edge == (VisualType.SCATTER, VisualType.BAR)
        assert beyond.depth == len(chain)

    def test_a_type_two_paths_reach_is_tried_once(self) -> None:
        """A diamond reaches its far corner by two routes in one depth. It is tried on
        the first and skipped on the second, so each of the three forms the plan is
        refused as is refused once."""
        keeps = frozenset({self.wind_purpose()})
        diamond: dict[VisualType, tuple[DowngradeEdge, ...]] = {
            VisualType.COMPARISON: (
                DowngradeEdge(VisualType.SCATTER, keeps),
                DowngradeEdge(VisualType.SLOPE, keeps),
            ),
            VisualType.SCATTER: (DowngradeEdge(VisualType.LINE, keeps),),
            VisualType.SLOPE: (DowngradeEdge(VisualType.LINE, keeps),),
        }
        forms = {VisualType.SCATTER, VisualType.SLOPE, VisualType.LINE}
        rejected: list[Rejection] = []

        made = downgrade(
            self.unruled_comparison(),
            wind_table(*WHOLE),
            visuals=downgrade_visuals(),
            published_marks={VisualType.BAR: [3, 4, 5, 8]},
            edges=diamond,
            rejected=rejected,
        )

        assert made is None
        assert len(rejected) == len(forms)

    def test_a_table_that_points_back_never_returns_to_the_type_it_started_from(self) -> None:
        """A cycle would bring the plan back to the form the validator already refused,
        one depth poorer. The source is marked walked from the start, so it is never
        tried again."""
        keeps = frozenset({self.wind_purpose()})
        table = wind_table(*WHOLE).model_dump(mode="json")
        invented = next(
            element
            for element in table["elements"]
            if element["element_id"] == wind_plan().encodings.quantity[0]
        )
        invented["value"] = "999999"
        rejected: list[Rejection] = []

        made = downgrade(
            wind_plan(),
            ElementTable.model_validate(table),
            visuals=downgrade_visuals(),
            published_marks={VisualType.BAR: [3, 4, 5, 8], VisualType.DOT: [3, 4, 5, 8]},
            edges={
                VisualType.BAR: (DowngradeEdge(VisualType.DOT, keeps),),
                VisualType.DOT: (DowngradeEdge(VisualType.BAR, keeps),),
            },
            rejected=rejected,
        )

        assert made is None
        assert [rejection.check for rejection in rejected] == [ValidatorCheck.NO_INVENTED_VALUES]

    def test_an_unbuilt_form_is_stepped_through_and_never_returned(self) -> None:
        """The compiler's capability bounds what may be returned and not what may be
        walked. A trend plan would validate as an `area`, which has role rules and no
        compiler, so it is carried on to the built form behind it."""
        trend = current_plan(VALIDATOR_FIXTURES / "plans" / "line-trend.json")
        assert trend.purpose is not None
        table = ElementTable.from_json(
            read_text(VALIDATOR_FIXTURES / "tables" / "line-trend.json")
        )
        visuals = downgrade_visuals()
        as_area = VisualPlan.model_validate(
            trend.model_dump(mode="json") | {"type": VisualType.AREA.value}
        )
        assert validate_plan(as_area, table, visuals=visuals) == []
        assert not can_compile(VisualType.AREA)

        made = downgrade(
            trend,
            table,
            visuals=visuals,
            published_marks={VisualType.AREA: [3, 3, 3, 3], VisualType.SLOPE: [3, 3, 3, 3]},
            edges=edges_along(
                VisualType.LINE, VisualType.AREA, VisualType.SLOPE, keeping=trend.purpose
            ),
        )

        assert made is not None
        assert made.edge == (VisualType.AREA, VisualType.SLOPE)
        assert made.depth == 2

    def test_a_form_the_operator_did_not_select_is_never_returned(self) -> None:
        """With selection on, a neighbour outside `enabled_types` is skipped though it
        validates and clears its floor."""
        edges = edges_along(VisualType.BAR, VisualType.DOT, keeping=self.wind_purpose())

        def walk(*selected: VisualType) -> Downgrade | None:
            return downgrade(
                wind_plan(),
                wind_table(*WHOLE),
                visuals=downgrade_visuals(
                    type_selection_enabled=True,
                    enabled_types=[one.value for one in selected],
                ),
                published_marks={VisualType.DOT: [3, 4, 5, 8]},
                edges=edges,
            )

        assert walk(VisualType.BAR) is None
        offered = walk(VisualType.BAR, VisualType.DOT)
        assert offered is not None
        assert offered.edge == (VisualType.BAR, VisualType.DOT)

    def test_a_plan_whose_own_type_is_not_selected_is_not_walked_at_all(self) -> None:
        """The shipped edge would rescue this plan as a `bar`, and `bar` is selected.
        The plan is still left alone, because its own type is not."""
        plan = self.unruled_comparison()
        visuals = downgrade_visuals(type_selection_enabled=True)
        assert plan.type not in visuals.select_types()
        assert VisualType.BAR in visuals.select_types()

        assert (
            downgrade(
                plan,
                wind_table(*WHOLE),
                visuals=visuals,
                published_marks={VisualType.BAR: [3, 4, 5, 8]},
            )
            is None
        )

    def test_a_plan_with_a_channel_a_bar_cannot_keep_is_not_made_a_bar(self) -> None:
        """The bar compiler cannot draw a grouping, so stepping a grouped plan down to a
        bar would drop a fact in silence. A dot keeps the grouping, and a bar refuses."""
        payload = wind_plan_payload()
        grouping = "date-35-39"
        grouped = wind_plan(
            type=VisualType.COMPARISON.value,
            encodings=payload["encodings"] | {EncodingRole.SERIES.value: [grouping]},
            element_ids=[*payload["element_ids"], grouping],
        )
        table = wind_table(*WHOLE)
        rejected: list[Rejection] = []

        as_bar = downgrade(
            grouped,
            table,
            visuals=downgrade_visuals(),
            published_marks={VisualType.BAR: [3, 4, 5, 8]},
            rejected=rejected,
        )
        as_dot = downgrade(
            grouped,
            table,
            visuals=downgrade_visuals(),
            published_marks={VisualType.DOT: [3, 4, 5, 8]},
            edges=edges_along(
                VisualType.COMPARISON, VisualType.DOT, keeping=self.wind_purpose()
            ),
        )

        assert as_bar is None
        assert rejected == [], "the bar passed every check, so only its channel limit refused it"
        assert as_dot is not None
        assert as_dot.plan.encodings.series == [grouping]

    def test_a_pie_refused_on_its_whole_is_not_rescued_by_a_stacked_bar_that_passes(
        self,
    ) -> None:
        """The pie's whole check is the stricter one: it needs the parts and the whole to
        state one canonical measure, which the stacked bar's check never asks. A pie
        refused there is not laundered through the looser check."""
        plan = current_plan(VALIDATOR_FIXTURES / "plans" / "pie-valid.json")
        payload = json.loads(read_text(VALIDATOR_FIXTURES / "tables" / "pie-whole.json"))
        intact = ElementTable.model_validate(payload)
        part = next(
            one for one in payload["elements"] if one["element_id"] == plan.encodings.quantity[0]
        )
        part["measure"] = part["measure_canonical"] = "capacity"
        mismatched = ElementTable.model_validate(payload)
        visuals = downgrade_visuals()
        published = {VisualType.STACKED_BAR: [3, 4, 5, 8]}
        rejected: list[Rejection] = []

        assert [one.check for one in validate_plan(plan, mismatched, visuals=visuals)] == [
            ValidatorCheck.PIE_EXHAUSTIVE
        ]
        assert (
            downgrade(
                plan, mismatched, visuals=visuals, published_marks=published, rejected=rejected
            )
            is None
        )
        assert rejected == [], "the stacked bar passed every check, so only the pie's whole refused it"
        assert downgrade(plan, intact, visuals=visuals, published_marks=published) is not None

    def test_a_floor_that_excluded_one_candidate_stays_recorded_when_a_later_one_clears(
        self,
    ) -> None:
        """Two viable targets from one source: the first is held back by its floor and
        the second clears its own, and the evidence still says a floor excluded one."""
        keeps = frozenset({self.wind_purpose()})
        evidence = DowngradeEvidence()

        made = downgrade(
            self.unruled_comparison(),
            wind_table(*WHOLE),
            visuals=downgrade_visuals(),
            published_marks={VisualType.BAR: [5, 6, 7, 8], VisualType.DOT: [3, 4, 5, 8]},
            edges={
                VisualType.COMPARISON: (
                    DowngradeEdge(VisualType.BAR, keeps),
                    DowngradeEdge(VisualType.DOT, keeps),
                )
            },
            evidence=evidence,
        )

        assert made is not None
        assert made.edge == (VisualType.COMPARISON, VisualType.DOT)
        assert evidence.gate_floor_applied is True

    @pytest.mark.parametrize(
        ("population", "percentile", "expected"),
        [
            ((3, 4, 5, 8), 50, 4),
            ((3, 4, 5, 8), 75, 5),
            ((3, 4, 5, 8), 100, 8),
            ((3, 4, 5, 8), 0, 3),
            ((6,), 50, 6),
        ],
    )
    def test_the_floor_is_nearest_rank_so_it_is_a_count_some_visual_really_had(
        self, population: tuple[int, ...], percentile: int, expected: int
    ) -> None:
        """Interpolating would put a mark count no published visual ever drew
        between two that were."""
        assert depth_floor(population, percentile) == expected

    def test_a_ladder_whose_rungs_do_not_rise_never_loads(self) -> None:
        with pytest.raises(ValidationError):
            committed_visuals(downgrade_floor_percentiles=[75, 50])
        with pytest.raises(ValidationError):
            committed_visuals(downgrade_floor_percentiles=[50, 50])
        with pytest.raises(ValidationError):
            committed_visuals(downgrade_floor_percentiles=[101])
