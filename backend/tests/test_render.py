"""Both renderers, and the rule that a picture never costs an item its place."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from idhazh.contracts.route import Route, SpecFormat, VisualKind, VisualState
from idhazh.render.chart import RenderError as ChartError
from idhazh.render.chart import render_chart
from idhazh.render.diagram import RenderError as DiagramError
from idhazh.render.diagram import parse_mermaid, render_diagram, wrap
from idhazh.render.write import asset_relpath, highest_ordinal, render_route

SPEC = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "data": {"values": [{"label": "a", "value": 3}, {"label": "b", "value": 5}]},
    "mark": "bar",
    "encoding": {
        "y": {"field": "label", "type": "nominal"},
        "x": {"field": "value", "type": "quantitative"},
    },
}

MERMAID = 'flowchart TD\n    n0["Filed"]\n    n1["Reviewed"]\n    n2["Approved"]\n    n0 --> n1\n    n1 --> n2'


def _route(kind: VisualKind, spec: str) -> Route:
    return Route(
        version=Route.schema_version(),
        item_id="energy-01",
        url_key="b" * 64,
        kind=kind,
        spec=spec,
        spec_format=(SpecFormat.VEGA_LITE if kind is VisualKind.CHART else SpecFormat.MERMAID),
        model_id="qwen3-4b",
        routed_at="2026-08-22T00:00:00Z",
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


class TestDiagramRenderer:
    def test_it_reads_back_the_source_route_wrote(self) -> None:
        caption, labels = parse_mermaid(MERMAID)
        assert labels == ["Filed", "Reviewed", "Approved"]
        assert caption == ""

    def test_a_comment_line_is_the_caption(self) -> None:
        caption, _ = parse_mermaid("%% How it moved\n" + MERMAID)
        assert caption == "How it moved"

    def test_a_mermaid_feature_we_do_not_draw_raises(self) -> None:
        with pytest.raises(DiagramError):
            parse_mermaid("flowchart TD\n    subgraph one\n    end")

    def test_a_one_step_diagram_raises(self) -> None:
        with pytest.raises(DiagramError):
            parse_mermaid('flowchart TD\n    n0["Only"]')

    def test_it_draws_one_box_per_step(self) -> None:
        svg = render_diagram(MERMAID).decode("utf-8")
        assert svg.count("<rect") == 3
        assert svg.count("<line") == 2

    def test_the_canvas_is_exactly_what_was_asked_for(self) -> None:
        svg = render_diagram(MERMAID, width=800, height=500).decode("utf-8")
        assert 'viewBox="0 0 800 500"' in svg

    def test_a_label_with_markup_is_escaped_not_injected(self) -> None:
        spec = 'flowchart TD\n    n0["<script>x</script>"]\n    n1["Two"]\n    n0 --> n1'
        svg = render_diagram(spec).decode("utf-8")
        assert "<script>" not in svg
        assert "&lt;script&gt;" in svg

    def test_it_renders_byte_identically_twice(self) -> None:
        assert render_diagram(MERMAID) == render_diagram(MERMAID)

    def test_a_long_label_wraps_rather_than_overflowing(self) -> None:
        lines = wrap("one two three four five six seven eight nine ten", 120)
        assert len(lines) > 1
        assert all(len(line) <= 20 for line in lines)


class TestAssetPaths:
    def test_the_path_is_posix_dated_and_free_of_any_digest(self) -> None:
        assert asset_relpath("2026-08-22", "energy", 3) == "digest/2026/08/22/energy-03.svg"

    def test_the_path_holds_no_backslash(self) -> None:
        assert "\\" not in asset_relpath("2026-08-22", "ai", 1)

    def test_a_day_with_no_assets_starts_at_one(self, tmp_path: Path) -> None:
        assert highest_ordinal(tmp_path, "2026-08-22", "ai") == 0

    def test_numbering_continues_past_what_the_day_already_holds(self, tmp_path: Path) -> None:
        """A second run must not overwrite the first run's charts.

        Observed live on 2026-08-24: the day ran four times, each run numbered
        from one, and fourteen asset paths ended up referenced by two different
        items. `india-01.svg` was claimed by both "Indian stock markets open
        higher" and "Defence Stocks Rise", so one of them displayed a chart built
        from the other article's numbers, under alt text describing figures that
        were not in the picture. Every value was true and the picture belonged to
        another story.
        """
        folder = tmp_path / "digest" / "2026" / "08" / "22"
        folder.mkdir(parents=True)
        for name in ("india-01.svg", "india-02.svg", "ai-01.svg"):
            (folder / name).write_bytes(b"<svg/>")
        assert highest_ordinal(tmp_path, "2026-08-22", "india") == 2
        assert highest_ordinal(tmp_path, "2026-08-22", "ai") == 1
        assert highest_ordinal(tmp_path, "2026-08-22", "world") == 0

    def test_a_vertical_is_not_confused_with_a_longer_one_that_starts_the_same(
        self, tmp_path: Path
    ) -> None:
        folder = tmp_path / "digest" / "2026" / "08" / "22"
        folder.mkdir(parents=True)
        (folder / "business-economy-07.svg").write_bytes(b"<svg/>")
        assert highest_ordinal(tmp_path, "2026-08-22", "business") == 0
        assert highest_ordinal(tmp_path, "2026-08-22", "business-economy") == 7

    def test_a_file_that_is_not_numbered_is_ignored(self, tmp_path: Path) -> None:
        folder = tmp_path / "digest" / "2026" / "08" / "22"
        folder.mkdir(parents=True)
        (folder / "ai-draft.svg").write_bytes(b"<svg/>")
        assert highest_ordinal(tmp_path, "2026-08-22", "ai") == 0


class TestRenderRoute:
    def test_a_rendered_chart_records_where_it_landed(self, tmp_path: Path) -> None:
        result = render_route(
            _route(VisualKind.CHART, json.dumps(SPEC)),
            public_root=tmp_path,
            relpath="digest/2026/08/22/ai-01.svg",
        )
        assert result.visual_state is VisualState.RENDERED
        assert result.asset_path == "digest/2026/08/22/ai-01.svg"
        assert (tmp_path / "digest/2026/08/22/ai-01.svg").exists()

    def test_a_rendered_diagram_records_where_it_landed(self, tmp_path: Path) -> None:
        result = render_route(
            _route(VisualKind.DIAGRAM, MERMAID),
            public_root=tmp_path,
            relpath="digest/2026/08/22/ai-01.svg",
        )
        assert result.visual_state is VisualState.RENDERED

    def test_a_render_failure_degrades_and_never_raises(self, tmp_path: Path) -> None:
        result = render_route(
            _route(VisualKind.CHART, "{not json"),
            public_root=tmp_path,
            relpath="digest/2026/08/22/ai-01.svg",
        )
        assert result.visual_state is VisualState.RENDER_FAILED
        assert result.failure_detail
        assert result.asset_path is None

    def test_a_failed_render_leaves_no_file_behind(self, tmp_path: Path) -> None:
        render_route(
            _route(VisualKind.CHART, "{not json"),
            public_root=tmp_path,
            relpath="digest/2026/08/22/ai-01.svg",
        )
        assert not (tmp_path / "digest/2026/08/22/ai-01.svg").exists()

    def test_a_routed_to_nothing_item_is_returned_untouched(self, tmp_path: Path) -> None:
        nothing = Route(
            version=Route.schema_version(),
            item_id="energy-01",
            url_key="b" * 64,
            kind=VisualKind.NONE,
            model_id="qwen3-4b",
            routed_at="2026-08-22T00:00:00Z",
        )
        assert render_route(nothing, public_root=tmp_path, relpath="x.svg") is nothing
