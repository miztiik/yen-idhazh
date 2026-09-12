"""The chart renderer, and the rule that a picture never costs an item its place."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh.contracts.app_config import AppConfig, VisualsConfig
from idhazh.contracts.element import ElementTable
from idhazh.contracts.visual import VisualPlan, VisualType
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.render.chart import CompileError, compile_bar, render_chart
from idhazh.render.chart import RenderError as ChartError
from idhazh.render.write import (
    asset_relpath,
    drop_raced_assets,
    render_planned_visual,
    render_visual,
)

pytestmark = pytest.mark.visual

#: The one committed `bar` plan and the article table it draws from. The canary
#: day compiles the same pair, so the drawing a browser reads back and the
#: drawing asserted here cannot be two different pictures.
PLAN_FIXTURES: Final = FIXTURES_DIR / "visual-validator" / "plans"
TABLE_FIXTURES: Final = FIXTURES_DIR / "visual-validator" / "tables"
BAR_PLAN: Final = PLAN_FIXTURES / "passes.json"
BAR_TABLE: Final = TABLE_FIXTURES / "wind.json"

SPEC = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "data": {"values": [{"label": "a", "value": 3}, {"label": "b", "value": 5}]},
    "mark": "bar",
    "encoding": {
        "y": {"field": "label", "type": "nominal"},
        "x": {"field": "value", "type": "quantitative"},
    },
}


def _decision(kind: VisualKind, spec: str) -> VisualDecision:
    return VisualDecision(
        version=VisualDecision.schema_version(),
        item_id="energy-01",
        url_key="b" * 64,
        kind=kind,
        spec=spec,
        model_id="qwen3-4b",
        decided_at="2026-08-22T00:00:00Z",
    )


def committed_visuals() -> VisualsConfig:
    """The knobs the pipeline ships, never a number typed here (Guardrail #6)."""
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals


#: One drawn bar, as the Vega toolchain writes it: the name it was given, and
#: the length it was drawn at. The horizontal rectangle opens with `M0,0h<width>`
#: and the width is the only figure in the path a reader can see.
_BAR = re.compile(
    r'aria-label="(?P<label>[^"]*)"[^>]*?aria-roledescription="bar"[^>]*?\bd="M0,0h(?P<width>[0-9.]+)'
)


def drawn_bars(svg: str) -> list[tuple[str, Decimal]]:
    """Every bar in a rendered chart, named and measured off the SVG itself.

    Reading the drawn attributes rather than the spec is the whole point: a spec
    holding the right numbers proves the compiler agreed with itself, and this
    proves the picture did.
    """
    bars: list[tuple[str, Decimal]] = []
    for match in _BAR.finditer(svg):
        label = match["label"]
        name = label.split("label: ", 1)[1] if "label: " in label else label
        bars.append((name, Decimal(match["width"])))
    return bars


def bar_chart(table: ElementTable, plan: VisualPlan) -> list[tuple[str, Decimal]]:
    """Compile, draw, and hand back what ended up on the picture."""
    compiled = compile_bar(plan, table, visuals=committed_visuals())
    return drawn_bars(render_chart(json.dumps(compiled.spec)).decode("utf-8"))


class TestCompiledBar:
    """A plan with no figure in it becomes a picture full of the article's figures.

    The plan names elements and states no number - the shape refuses one - so
    every bar is as long as something the extractor cut out of the article's own
    characters. These are the tests that say so by measuring the drawing rather
    than by reading the code that made it.
    """

    def test_every_bar_is_drawn_as_long_as_the_figure_the_article_states(self) -> None:
        """The oracle: one pixel is the same quantity on every bar in the picture.

        The drawn width is divided by the figure the element table states for
        that bar, and every bar has to return the same number. A bar drawn from
        another story's figure, a channel read in the wrong order, or a mark
        whose length came from anywhere but the table puts a second entry in
        that set.
        """
        table = ElementTable.read(BAR_TABLE)
        plan = VisualPlan.read(BAR_PLAN)
        stated = {element.element_id: element for element in table.elements}
        wanted = [Decimal(str(stated[cited].value)) for cited in plan.encodings.quantity]
        named = [stated[cited].span_excerpt for cited in plan.encodings.category]

        bars = bar_chart(table, plan)

        assert [name for name, _ in bars] == named
        per_unit = {
            round(width / figure, 9)
            for (_, width), figure in zip(bars, wanted, strict=True)
        }
        assert len(per_unit) == 1, f"the bars are drawn at {len(per_unit)} different scales"

    def test_changing_one_figure_in_the_table_moves_that_bar_and_no_other(self) -> None:
        """What proportionality alone cannot say: the drawing reads THIS table.

        A picture drawn at its own invented scale is proportional to itself and
        passes the test above. So one element's figure is doubled - one that is
        not the longest bar, which leaves the axis where it was - and the
        drawing has to answer with that one bar twice as long and the other
        three untouched.

        Only `value` moves, not the `span_excerpt` beside it. Whether the two
        agree is `no_invented_values`' question and it is asked before a plan
        reaches a compiler; what is under test here is which number the picture
        was drawn from.

        The widths are rounded because the toolchain writes the geometry as a
        printed float, so an exact doubling lands one unit in the last place
        away from itself.
        """
        table = ElementTable.read(BAR_TABLE)
        plan = VisualPlan.read(BAR_PLAN)
        moved = plan.encodings.quantity[2]
        rows = table.model_dump(mode="json")["elements"]
        rewritten = ElementTable.model_validate(
            table.model_dump(mode="json")
            | {
                "elements": [
                    row
                    | (
                        {"value": str(Decimal(str(row["value"])) * 2)}
                        if row["element_id"] == moved
                        else {}
                    )
                    for row in rows
                ]
            }
        )

        before = [round(width, 9) for _, width in bar_chart(table, plan)]
        after = [round(width, 9) for _, width in bar_chart(rewritten, plan)]

        assert after[2] == round(before[2] * 2, 9)
        assert [after[0], after[1], after[3]] == [before[0], before[1], before[3]]

    def test_each_bar_carries_the_article_s_own_characters_as_its_name(self) -> None:
        """The name on a bar is a span out of the article, never a word we wrote."""
        table = ElementTable.read(BAR_TABLE)
        excerpts = {element.span_excerpt for element in table.elements}

        bars = bar_chart(table, VisualPlan.read(BAR_PLAN))

        assert {name for name, _ in bars} <= excerpts

    def test_the_alt_text_states_every_figure_the_picture_draws(self) -> None:
        """The visual is never the only carrier of a fact."""
        table = ElementTable.read(BAR_TABLE)
        plan = VisualPlan.read(BAR_PLAN)

        compiled = compile_bar(plan, table, visuals=committed_visuals())

        stated = {element.element_id: element for element in table.elements}
        for cited in plan.encodings.quantity:
            assert f"{Decimal(str(stated[cited].value)):,f}" in compiled.alt_text
        for cited in plan.encodings.category:
            assert stated[cited].span_excerpt in compiled.alt_text

    def test_a_plan_that_asks_for_no_picture_compiles_to_none(self) -> None:
        with pytest.raises(CompileError):
            compile_bar(
                VisualPlan.read(PLAN_FIXTURES / "declines.json"),
                ElementTable.read(BAR_TABLE),
                visuals=committed_visuals(),
            )

    def test_a_type_this_build_cannot_draw_is_refused_by_its_own_name(self) -> None:
        """One type. Drawing a `pie` as bars would publish a picture nobody planned."""
        plan = VisualPlan.read(BAR_PLAN)
        other = VisualPlan.model_validate(
            plan.model_dump(mode="json") | {"type": VisualType.PIE.value}
        )

        with pytest.raises(CompileError, match="pie"):
            compile_bar(other, ElementTable.read(BAR_TABLE), visuals=committed_visuals())

    def test_a_plan_the_resolver_refuses_never_becomes_a_picture(self) -> None:
        """The refusal travels with its check's name, so an operator can act on it."""
        with pytest.raises(CompileError, match="element_exists"):
            compile_bar(
                VisualPlan.read(PLAN_FIXTURES / "element-missing.json"),
                ElementTable.read(BAR_TABLE),
                visuals=committed_visuals(),
            )


class TestRenderPlannedVisual:
    """An item is decided to nothing until a plan compiles into a picture.

    `VisualDecision` refuses a `chart` that carries no spec, so the decision
    handed in is the `none` it honestly is and the compile is what promotes it.
    """

    @staticmethod
    def _nothing_yet() -> VisualDecision:
        return VisualDecision(
            version=VisualDecision.schema_version(),
            item_id="energy-01",
            url_key="b" * 64,
            kind=VisualKind.NONE,
            model_id="qwen3-4b",
            decided_at="2026-08-22T00:00:00Z",
        )

    def test_a_planned_bar_lands_on_disk_carrying_its_spec_and_its_alt_text(
        self, tmp_path: Path
    ) -> None:
        result = render_planned_visual(
            self._nothing_yet(),
            VisualPlan.read(BAR_PLAN),
            ElementTable.read(BAR_TABLE),
            public_root=tmp_path,
            relpath="digest/2026/08/22/ai-01.svg",
            visuals=committed_visuals(),
        )

        assert result.kind is VisualKind.CHART
        assert result.visual_state is VisualState.RENDERED
        assert result.asset_path == "digest/2026/08/22/ai-01.svg"
        assert result.alt_text and result.alt_text.startswith("Bar chart.")
        assert result.spec and "Denmark" in result.spec
        assert (tmp_path / "digest/2026/08/22/ai-01.svg").read_bytes().startswith(b"<svg")

    def test_a_plan_that_cannot_be_compiled_leaves_the_item_decided_to_nothing(
        self, tmp_path: Path
    ) -> None:
        """No raise, no half-written state, and no file. The story is simply shorter."""
        result = render_planned_visual(
            self._nothing_yet(),
            VisualPlan.read(PLAN_FIXTURES / "declines.json"),
            ElementTable.read(BAR_TABLE),
            public_root=tmp_path,
            relpath="digest/2026/08/22/ai-01.svg",
            visuals=committed_visuals(),
        )

        assert result.kind is VisualKind.NONE
        assert result.spec is None
        assert result.visual_state is VisualState.ABSENT
        assert not (tmp_path / "digest/2026/08/22/ai-01.svg").exists()

    def test_a_decision_that_already_carries_a_chart_is_refused(self) -> None:
        """Compiling over a drawn chart would silently replace one story's picture."""
        with pytest.raises(ValueError, match="decided to nothing"):
            render_planned_visual(
                _decision(VisualKind.CHART, json.dumps(SPEC)),
                VisualPlan.read(BAR_PLAN),
                ElementTable.read(BAR_TABLE),
                public_root=Path("unused"),
                relpath="digest/2026/08/22/ai-01.svg",
                visuals=committed_visuals(),
            )


class TestChartRenderer:
    def test_a_valid_spec_becomes_an_svg(self) -> None:
        payload = render_chart(json.dumps(SPEC))
        assert payload.startswith(b"<svg")

    def test_the_same_spec_renders_byte_identically_twice(self) -> None:
        assert render_chart(json.dumps(SPEC)) == render_chart(json.dumps(SPEC))

    def test_malformed_json_raises_rather_than_writing_a_broken_file(self) -> None:
        with pytest.raises(ChartError):
            render_chart("{not json")

    def test_a_spec_vega_lite_rejects_raises(self) -> None:
        with pytest.raises(ChartError):
            render_chart(json.dumps({"mark": "not-a-mark", "data": {"values": []}}))


class TestAssetPaths:
    def test_the_path_is_posix_dated_and_free_of_any_digest(self) -> None:
        assert (
            asset_relpath("2026-08-22", "energy-4821903756")
            == "digest/2026/08/22/energy-4821903756.svg"
        )

    def test_the_path_holds_no_backslash(self) -> None:
        assert "\\" not in asset_relpath("2026-08-22", "ai-0000000001")

    def test_a_vertical_with_a_hyphen_in_it_survives(self) -> None:
        assert (
            asset_relpath("2026-08-22", "business-economy-0000000007")
            == "digest/2026/08/22/business-economy-0000000007.svg"
        )

    def test_two_items_can_never_share_a_path(self) -> None:
        """The whole point of naming from identity rather than from a counter.

        Observed live on 2026-08-24: the day ran four times, each run numbered
        from one, and fourteen asset paths ended up referenced by two different
        items. `india-01.svg` was claimed by both "Indian stock markets open
        higher" and "Defence Stocks Rise", so one of them displayed a chart
        built from the other article's numbers, under alt text describing
        figures that were not in the picture. Every value was true and the
        picture belonged to another story.
        """
        ids = ["india-0000000001", "india-0000000002", "ai-0000000001"]
        paths = {asset_relpath("2026-08-22", item_id) for item_id in ids}
        assert len(paths) == len(ids)

    def test_the_path_depends_on_nothing_a_process_can_observe(self, tmp_path: Path) -> None:
        """A second run, a second shard and an empty checkout all agree.

        The old counter was seeded by reading the day's directory, so what a
        process saw on disk decided what it wrote. Two runs saw different
        directories and wrote one path.
        """
        folder = tmp_path / "digest" / "2026" / "08" / "22"
        folder.mkdir(parents=True)
        for name in ("india-0000000001.svg", "ai-0000000009.svg"):
            (folder / name).write_bytes(b"<svg/>")
        assert (
            asset_relpath("2026-08-22", "india-0000000002")
            == "digest/2026/08/22/india-0000000002.svg"
        )


class TestRenderVisual:
    def test_a_rendered_chart_records_where_it_landed(self, tmp_path: Path) -> None:
        result = render_visual(
            _decision(VisualKind.CHART, json.dumps(SPEC)),
            public_root=tmp_path,
            relpath="digest/2026/08/22/ai-01.svg",
        )
        assert result.visual_state is VisualState.RENDERED
        assert result.asset_path == "digest/2026/08/22/ai-01.svg"
        assert (tmp_path / "digest/2026/08/22/ai-01.svg").exists()

    def test_a_render_failure_degrades_and_never_raises(self, tmp_path: Path) -> None:
        result = render_visual(
            _decision(VisualKind.CHART, "{not json"),
            public_root=tmp_path,
            relpath="digest/2026/08/22/ai-01.svg",
        )
        assert result.visual_state is VisualState.RENDER_FAILED
        assert result.failure_detail
        assert result.asset_path is None

    def test_a_failed_render_leaves_no_file_behind(self, tmp_path: Path) -> None:
        render_visual(
            _decision(VisualKind.CHART, "{not json"),
            public_root=tmp_path,
            relpath="digest/2026/08/22/ai-01.svg",
        )
        assert not (tmp_path / "digest/2026/08/22/ai-01.svg").exists()

    def test_an_item_decided_to_nothing_is_returned_untouched(self, tmp_path: Path) -> None:
        nothing = VisualDecision(
            version=VisualDecision.schema_version(),
            item_id="energy-01",
            url_key="b" * 64,
            kind=VisualKind.NONE,
            model_id="qwen3-4b",
            decided_at="2026-08-22T00:00:00Z",
        )
        assert render_visual(nothing, public_root=tmp_path, relpath="x.svg") is nothing


DATE = "2026-08-22"
DAY = "digest/2026/08/22"


def _rendered(tmp_path: Path, item_id: str, relpath: str) -> Path:
    """One rendered chart on disk, plus the decision payload that says where it is."""
    (tmp_path / "public" / relpath).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "public" / relpath).write_bytes(f"<svg>{item_id}</svg>".encode("ascii"))
    decision = _decision(VisualKind.CHART, json.dumps(SPEC)).model_copy(
        update={
            "item_id": item_id,
            "asset_path": relpath,
            "visual_state": VisualState.RENDERED,
        }
    )
    path = tmp_path / "items" / f"{item_id}{PAYLOAD_SUFFIX}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(decision.to_json(), encoding="utf-8", newline="\n")
    return path


def _drop(tmp_path: Path, published: list[str]) -> list[str]:
    return drop_raced_assets(
        public_root=tmp_path / "public",
        items_dir=tmp_path / "items",
        published=published,
    )


class TestDropRacedAssets:
    """Two runs of one day overlap, and neither checkout sees the other's push.

    Run `32869125768` on 2026-08-25: eight workers and a visual planner finished,
    then the rebase hit `CONFLICT (add/add)` on four chart paths and the day was
    lost. Now a path names one item, so a path both sides hold is one story
    rendered twice - and the published copy is the one that stays.
    """

    def test_a_path_the_other_run_published_gives_up_this_run_s_copy(
        self, tmp_path: Path
    ) -> None:
        decision_path = _rendered(tmp_path, "energy-0000000002", f"{DAY}/energy-0000000002.svg")

        dropped = _drop(tmp_path, [f"{DAY}/energy-0000000002.svg"])

        assert dropped == [f"{DAY}/energy-0000000002.svg"]
        assert not (tmp_path / "public" / DAY / "energy-0000000002.svg").exists()
        # The payload keeps naming the path on purpose: the tip's file is there
        # after the rebase, and pointing it anywhere else would file this item's
        # picture under a name that is not this item's.
        kept = VisualDecision.from_json(decision_path.read_text(encoding="utf-8"))
        assert kept.asset_path == f"{DAY}/energy-0000000002.svg"

    def test_a_path_nobody_else_holds_is_left_alone(self, tmp_path: Path) -> None:
        decision_path = _rendered(tmp_path, "ai-0000000001", f"{DAY}/ai-0000000001.svg")

        assert _drop(tmp_path, [f"{DAY}/energy-0000000002.svg"]) == []

        assert (tmp_path / "public" / DAY / "ai-0000000001.svg").exists()
        kept = VisualDecision.from_json(decision_path.read_text(encoding="utf-8"))
        assert kept.asset_path == f"{DAY}/ai-0000000001.svg"

    def test_only_the_raced_item_loses_its_file(self, tmp_path: Path) -> None:
        """A run introduces items the tip has never seen, and those are the point."""
        _rendered(tmp_path, "energy-0000000002", f"{DAY}/energy-0000000002.svg")
        _rendered(tmp_path, "energy-0000000003", f"{DAY}/energy-0000000003.svg")

        assert _drop(tmp_path, [f"{DAY}/energy-0000000002.svg"]) == [
            f"{DAY}/energy-0000000002.svg"
        ]

        assert [path.name for path in (tmp_path / "public" / DAY).iterdir()] == [
            "energy-0000000003.svg"
        ]

    def test_a_payload_whose_file_this_checkout_lacks_is_left_alone(
        self, tmp_path: Path
    ) -> None:
        """Nothing here would commit that path, so nothing here can collide on it."""
        decision_path = _rendered(tmp_path, "ai-0000000001", f"{DAY}/ai-0000000001.svg")
        (tmp_path / "public" / DAY / "ai-0000000001.svg").unlink()

        assert _drop(tmp_path, [f"{DAY}/ai-0000000001.svg"]) == []

        kept = VisualDecision.from_json(decision_path.read_text(encoding="utf-8"))
        assert kept.asset_path == f"{DAY}/ai-0000000001.svg"

    def test_a_run_with_no_decisions_at_all_is_a_no_op(self, tmp_path: Path) -> None:
        """The planner is allowed to never start, and the day still publishes."""
        assert _drop(tmp_path, [f"{DAY}/energy-0000000002.svg"]) == []

