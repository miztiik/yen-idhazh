"""The chart compiler, and the rule that a picture never costs an item its place.

**Nothing in this repository draws a chart.** The reader's browser draws it and
the pipeline never does (owner ruling, 2026-09-13,
`docs/architecture/publishing/visuals.md`), so what this module checks is the
last thing the pipeline writes for a picture: the marks, and where they land.

Two things went with the renderer and are worth naming. The oracle used to
measure bar widths out of a rendered SVG, because a spec holding the right
figures only proves the compiler agreed with itself. There is no SVG to measure
now, so the published marks are compared against the element table directly -
the same question one step earlier, and the browser's half of it is
`frontend/tests/item-visual.spec.ts`. And a determinism test used to assert that
one spec rendered to identical bytes twice. It passed for the wrong reason: its
inline spec carried no title, so it emitted no clip path, and the renderer's
clip-path counter was process-global - three renders of a titled plan in one
process gave three different byte strings. That test is not ported. What
replaced it is a property the data can actually carry: compiling one plan twice
gives one document.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh.contracts.app_config import AppConfig, VisualsConfig
from idhazh.contracts.element import ElementTable
from idhazh.contracts.visual import EncodingRole, VisualPlan, VisualType
from idhazh.contracts.visual_data import RENDERER_VERSION, VisualData
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.render.chart import CompileError, compile_bar
from idhazh.render.write import asset_relpath, drop_raced_assets, render_planned_visual

pytestmark = pytest.mark.visual

#: The one committed `bar` plan and the article table it draws from. The canary
#: day compiles the same pair, so the marks a browser reads back and the marks
#: asserted here cannot be two different pictures.
PLAN_FIXTURES: Final = FIXTURES_DIR / "visual-validator" / "plans"
TABLE_FIXTURES: Final = FIXTURES_DIR / "visual-validator" / "tables"
BAR_PLAN: Final = PLAN_FIXTURES / "passes.json"
BAR_TABLE: Final = TABLE_FIXTURES / "wind.json"

DAY: Final = "digest/2026/08/22"
MARKS: Final = f"{DAY}/ai-01.json"


def committed_visuals() -> VisualsConfig:
    """The knobs the pipeline ships, never a number typed here (Guardrail #6)."""
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals


def _decision(kind: VisualKind, spec: str | None) -> VisualDecision:
    return VisualDecision(
        version=VisualDecision.schema_version(),
        item_id="energy-01",
        url_key="b" * 64,
        kind=kind,
        spec=spec,
        model_id="qwen3-4b",
        decided_at="2026-08-22T00:00:00Z",
    )


def compiled_bars(table: ElementTable, plan: VisualPlan) -> tuple[list[str], list[Decimal]]:
    """What the compiler published, as names and figures in channel order."""
    data = compile_bar(plan, table, visuals=committed_visuals()).data
    held = {mark.mark_id: mark for mark in data.marks}
    names = [held[mark_id].text or "" for mark_id in data.encoding.category]
    figures = [Decimal(held[mark_id].value or "0") for mark_id in data.encoding.quantity]
    return names, figures


class TestCompiledBar:
    """A plan with no figure in it becomes marks full of the article's figures.

    The plan names elements and states no number - the shape refuses one - so
    every bar is as long as something the extractor cut out of the article's own
    characters. These are the tests that say so.
    """

    def test_every_bar_carries_the_figure_the_article_states(self) -> None:
        """The oracle: the published length of a bar is the element's own number.

        A bar built from another story's figure, a channel read in the wrong
        order, or a mark whose length came from anywhere but the table fails
        here. It is an equality rather than a ratio because the compiler
        publishes the article's own characters: a drawing scales them and the
        data may not.
        """
        table = ElementTable.read(BAR_TABLE)
        plan = VisualPlan.read(BAR_PLAN)
        stated = {element.element_id: element for element in table.elements}
        wanted = [Decimal(str(stated[cited].value)) for cited in plan.encodings.quantity]
        named = [stated[cited].span_excerpt for cited in plan.encodings.category]

        names, figures = compiled_bars(table, plan)

        assert names == named
        assert figures == wanted

    def test_changing_one_figure_in_the_table_moves_that_bar_and_no_other(self) -> None:
        """What an equality on one table cannot say: the marks read THIS table.

        One element's figure is doubled - one that is not the longest bar - and
        the published marks have to answer with that one figure doubled and the
        other three untouched.

        Only `value` moves, not the `span_excerpt` beside it. Whether the two
        agree is `no_invented_values`' question and it is asked before a plan
        reaches a compiler; what is under test here is which number the marks
        were built from.
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

        _, before = compiled_bars(table, plan)
        _, after = compiled_bars(rewritten, plan)

        assert after[2] == before[2] * 2
        assert [after[0], after[1], after[3]] == [before[0], before[1], before[3]]

    def test_each_bar_carries_the_article_s_own_characters_as_its_name(self) -> None:
        """The name on a bar is a span out of the article, never a word we wrote."""
        table = ElementTable.read(BAR_TABLE)
        excerpts = {element.span_excerpt for element in table.elements}

        names, _ = compiled_bars(table, VisualPlan.read(BAR_PLAN))

        assert set(names) <= excerpts

    def test_the_alt_text_states_every_figure_the_picture_draws(self) -> None:
        """The visual is never the only carrier of a fact.

        It is also the whole of what a reader with JavaScript off receives, so
        the sentence has to state every figure a bar is drawn at rather than
        summarise them.
        """
        table = ElementTable.read(BAR_TABLE)
        plan = VisualPlan.read(BAR_PLAN)

        compiled = compile_bar(plan, table, visuals=committed_visuals())

        stated = {element.element_id: element for element in table.elements}
        for cited in plan.encodings.quantity:
            assert f"{Decimal(str(stated[cited].value)):,f}" in compiled.alt_text
        for cited in plan.encodings.category:
            assert stated[cited].span_excerpt in compiled.alt_text

    def test_compiling_one_plan_twice_gives_one_document(self) -> None:
        """What replaced the renderer's determinism test, and it can fail.

        The old one rendered an untitled spec twice in one process and compared
        bytes. It could not see the defect it was named for: Vega's clip-path
        counter was process-global, so a titled plan's bytes depended on where
        its item sat in the render order, and an untitled spec emits no clip
        path at all. This one is about the data, which is where determinism
        moved - and a compile that reached for a clock, a counter or a set
        iteration order would fail it.
        """
        table = ElementTable.read(BAR_TABLE)
        plan = VisualPlan.read(BAR_PLAN)

        once = compile_bar(plan, table, visuals=committed_visuals())
        twice = compile_bar(plan, table, visuals=committed_visuals())

        assert once.data.to_json() == twice.data.to_json()
        assert once.alt_text == twice.alt_text

    def test_a_plan_that_asks_for_no_picture_compiles_to_none(self) -> None:
        with pytest.raises(CompileError):
            compile_bar(
                VisualPlan.read(PLAN_FIXTURES / "declines.json"),
                ElementTable.read(BAR_TABLE),
                visuals=committed_visuals(),
            )

    def test_a_type_this_build_cannot_draw_is_refused_by_its_own_name(self) -> None:
        """One type. Compiling a `pie` into bars would publish a picture nobody planned."""
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


class TestPublishedData:
    """What travels is the data and its shape, and nothing that was ever drawn.

    Built from the committed plan and table, never walked over the committed
    archive (`CLAUDE.md` section 13, Guardrail #12).
    """

    @staticmethod
    def _compiled() -> VisualData:
        return compile_bar(
            VisualPlan.read(BAR_PLAN),
            ElementTable.read(BAR_TABLE),
            visuals=committed_visuals(),
        ).data

    def test_the_published_data_carries_the_shape_and_none_of_the_geometry(self) -> None:
        """The plan may not carry geometry, a literal value or authored text.

        Publishing the compiled result must not become the hole one gets through
        (owner, 2026-09-13). So the check is against the serialised document:
        none of the words a drawing uses to say how wide, how tall, what colour
        or what font appears anywhere in it, and neither does the plan's own
        title - `title` and `caption` are plan 12 row #5's, and a compiler that
        smuggled one in would put an authored string on the wire.
        """
        document = self._compiled().to_json()

        assert self._compiled().type is VisualType.BAR
        assert self._compiled().renderer_version == RENDERER_VERSION
        for drawn in ("width", "height", "background", "fontSize", "colour", "color", "title"):
            assert drawn not in document, f"the published data carries {drawn}, which is not data"

    def test_every_published_mark_states_where_its_figure_came_from(self) -> None:
        """A drawn number with no provenance is the thing this subsystem refuses."""
        data = self._compiled()

        known = {element.element_id for element in ElementTable.read(BAR_TABLE).elements}
        for mark in data.marks:
            assert (mark.element_id is None) != (mark.derived is None)
            if mark.element_id is not None:
                assert mark.element_id in known, f"{mark.mark_id} names an element the article lacks"
            else:
                assert mark.derived is not None
                assert set(mark.derived.inputs) <= known

    def test_the_channels_pair_and_nothing_is_carried_that_is_not_drawn(self) -> None:
        """The shape the browser's refusal is written against."""
        data = self._compiled()

        assert len(data.encoding.category) == len(data.encoding.quantity)
        assert set(data.encoding.filled()) == {EncodingRole.CATEGORY, EncodingRole.QUANTITY}
        drawn = [*data.encoding.category, *data.encoding.quantity]
        assert sorted(drawn) == sorted(mark.mark_id for mark in data.marks)

    def test_a_bar_nobody_can_name_is_refused_rather_than_published_blank(self) -> None:
        """A span excerpt that sanitizes to nothing would publish an unlabelled bar.

        The excerpt keeps its width, because it is the verbatim slice and the
        table checks that. What changes is what it is made of: zero-width spaces
        are characters an article can genuinely carry and the sanitizer takes
        every one of them out, so the name arrives empty and the bar arrives
        with a length and no label.
        """
        table = ElementTable.read(BAR_TABLE)
        plan = VisualPlan.read(BAR_PLAN)
        blank = plan.encodings.category[0]
        rewritten = ElementTable.model_validate(
            table.model_dump(mode="json")
            | {
                "elements": [
                    row
                    | (
                        {"span_excerpt": "\u200b" * (row["span_end"] - row["span_start"])}
                        if row["element_id"] == blank
                        else {}
                    )
                    for row in table.model_dump(mode="json")["elements"]
                ]
            }
        )

        with pytest.raises(CompileError, match="nothing after sanitizing"):
            compile_bar(plan, rewritten, visuals=committed_visuals())


class TestRenderPlannedVisual:
    """An item is decided to nothing until a plan compiles.

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

    def test_a_planned_bar_lands_on_disk_carrying_its_marks_and_its_alt_text(
        self, tmp_path: Path
    ) -> None:
        result = render_planned_visual(
            self._nothing_yet(),
            VisualPlan.read(BAR_PLAN),
            ElementTable.read(BAR_TABLE),
            public_root=tmp_path,
            relpath=MARKS,
            visuals=committed_visuals(),
        )

        assert result.kind is VisualKind.CHART
        assert result.visual_state is VisualState.RENDERED
        assert result.data_path == MARKS
        assert result.alt_text and result.alt_text.startswith("Bar chart.")
        assert result.spec and "Denmark" in result.spec
        published = VisualData.read(tmp_path / MARKS)
        assert published.item_id == ElementTable.read(BAR_TABLE).item_id
        assert len(published.encoding.category) == len(published.encoding.quantity) == 4

    def test_the_decision_s_spec_is_the_document_that_was_published(self, tmp_path: Path) -> None:
        """One resolution, one document. Two would be two things that can disagree."""
        result = render_planned_visual(
            self._nothing_yet(),
            VisualPlan.read(BAR_PLAN),
            ElementTable.read(BAR_TABLE),
            public_root=tmp_path,
            relpath=MARKS,
            visuals=committed_visuals(),
        )
        assert result.spec is not None
        assert result.spec == (tmp_path / MARKS).read_text(encoding="utf-8")

    def test_a_plan_that_cannot_be_compiled_leaves_the_item_decided_to_nothing(
        self, tmp_path: Path
    ) -> None:
        """No raise, no half-written state, and no file. The story is simply shorter."""
        result = render_planned_visual(
            self._nothing_yet(),
            VisualPlan.read(PLAN_FIXTURES / "declines.json"),
            ElementTable.read(BAR_TABLE),
            public_root=tmp_path,
            relpath=MARKS,
            visuals=committed_visuals(),
        )

        assert result.kind is VisualKind.NONE
        assert result.spec is None
        assert result.data_path is None
        assert result.visual_state is VisualState.ABSENT
        assert not (tmp_path / MARKS).exists()

    def test_a_decision_that_already_carries_a_chart_is_refused(self, tmp_path: Path) -> None:
        """Compiling over a published chart would silently replace one story's picture."""
        with pytest.raises(ValueError, match="decided to nothing"):
            render_planned_visual(
                _decision(VisualKind.CHART, '{"marks":[]}'),
                VisualPlan.read(BAR_PLAN),
                ElementTable.read(BAR_TABLE),
                public_root=tmp_path,
                relpath=MARKS,
                visuals=committed_visuals(),
            )

    def test_marks_that_cannot_be_written_degrade_and_never_raise(self, tmp_path: Path) -> None:
        """The item still publishes, shorter, and the payload records why.

        The file's own path is occupied by a directory, so the write fails with
        an `OSError` the way a full disk or a read-only tree would. Nothing
        raises and `data_path` stays null, which every reader of the payload is
        required to read as no data carried.
        """
        (tmp_path / MARKS).mkdir(parents=True)

        result = render_planned_visual(
            self._nothing_yet(),
            VisualPlan.read(BAR_PLAN),
            ElementTable.read(BAR_TABLE),
            public_root=tmp_path,
            relpath=MARKS,
            visuals=committed_visuals(),
        )

        assert result.kind is VisualKind.CHART
        assert result.visual_state is VisualState.RENDER_FAILED
        assert result.data_path is None
        assert result.failure_detail and "could not be written" in result.failure_detail


class TestAssetPaths:
    def test_the_path_is_posix_dated_and_free_of_any_digest(self) -> None:
        assert (
            asset_relpath("2026-08-22", "energy-4821903756")
            == "digest/2026/08/22/energy-4821903756.json"
        )

    def test_the_path_holds_no_backslash(self) -> None:
        assert "\\" not in asset_relpath("2026-08-22", "ai-0000000001")

    def test_a_vertical_with_a_hyphen_in_it_survives(self) -> None:
        assert (
            asset_relpath("2026-08-22", "business-economy-0000000007")
            == "digest/2026/08/22/business-economy-0000000007.json"
        )

    def test_it_can_never_collide_with_the_day_s_own_payloads(self) -> None:
        """`digest.json` and `run.json` share this directory and are never deleted.

        An item id has to end in a hyphen and a run of digits or sixteen base32
        symbols, so no item can be called `digest` or `run` - which is what lets
        the retention prune and `validate-days` read a file's identity off its
        name instead of keeping a list of names to skip.
        """
        named = {
            asset_relpath("2026-08-22", item_id)
            for item_id in ("digest-0000000001", "run-0000000002", "ai-0000000003")
        }
        assert f"{DAY}/digest.json" not in named
        assert f"{DAY}/run.json" not in named

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
        for name in ("india-0000000001.json", "ai-0000000009.json"):
            (folder / name).write_text("{}", encoding="utf-8", newline="\n")
        assert (
            asset_relpath("2026-08-22", "india-0000000002")
            == "digest/2026/08/22/india-0000000002.json"
        )


DATE = "2026-08-22"


def _published(tmp_path: Path, item_id: str, relpath: str) -> Path:
    """One published visual on disk, plus the decision payload that says where it is."""
    file = tmp_path / "public" / relpath
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(f'{{"item_id": "{item_id}"}}', encoding="utf-8", newline="\n")
    decision = _decision(VisualKind.CHART, '{"marks":[]}').model_copy(
        update={
            "item_id": item_id,
            "data_path": relpath,
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
    lost. A path names one item, so a path both sides hold is one story compiled
    twice - and the published copy is the one that stays.

    **The renderer going did not retire this** (Fowler, 2026-09-13). It removed
    one cause of two runs writing different bytes and left the other: the marks
    come from a plan and an element table derived from text re-fetched off the
    open web, so a source page that moved between two fetches still puts two
    different blobs on one path.
    """

    def test_a_path_the_other_run_published_gives_up_this_run_s_copy(
        self, tmp_path: Path
    ) -> None:
        _published(tmp_path, "ai-0000000001", f"{DAY}/ai-0000000001.json")

        dropped = _drop(tmp_path, [f"{DAY}/ai-0000000001.json"])

        assert dropped == [f"{DAY}/ai-0000000001.json"]
        assert not (tmp_path / "public" / DAY / "ai-0000000001.json").exists()

    def test_a_path_the_tip_does_not_hold_is_left_alone(self, tmp_path: Path) -> None:
        """This run's own file is what publishes the item. Dropping it loses the picture."""
        _published(tmp_path, "ai-0000000001", f"{DAY}/ai-0000000001.json")

        dropped = _drop(tmp_path, [f"{DAY}/energy-0000000002.json"])

        assert dropped == []
        assert (tmp_path / "public" / DAY / "ai-0000000001.json").is_file()

    def test_the_decision_payload_is_left_naming_the_path_it_named(
        self, tmp_path: Path
    ) -> None:
        """After the rebase the tip's file is sitting there, so the pointer is right."""
        payload = _published(tmp_path, "ai-0000000001", f"{DAY}/ai-0000000001.json")

        _drop(tmp_path, [f"{DAY}/ai-0000000001.json"])

        assert VisualDecision.read(payload).data_path == f"{DAY}/ai-0000000001.json"

    def test_a_payload_naming_a_file_this_checkout_lacks_drops_nothing(
        self, tmp_path: Path
    ) -> None:
        """Nothing here would commit that path, so it cannot collide with anything."""
        payload = _published(tmp_path, "ai-0000000001", f"{DAY}/ai-0000000001.json")
        (tmp_path / "public" / DAY / "ai-0000000001.json").unlink()

        assert _drop(tmp_path, [f"{DAY}/ai-0000000001.json"]) == []
        assert payload.is_file()

    def test_an_item_decided_to_nothing_has_no_path_to_drop(self, tmp_path: Path) -> None:
        decision = _decision(VisualKind.NONE, None)
        items = tmp_path / "items"
        items.mkdir(parents=True)
        (items / f"energy-01{PAYLOAD_SUFFIX}").write_text(
            decision.to_json(), encoding="utf-8", newline="\n"
        )

        assert _drop(tmp_path, [f"{DAY}/energy-01.json"]) == []
