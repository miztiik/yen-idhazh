"""The chart renderer, and the rule that a picture never costs an item its place."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.render.chart import RenderError as ChartError
from idhazh.render.chart import render_chart
from idhazh.render.write import (
    asset_relpath,
    drop_raced_assets,
    render_visual,
)

pytestmark = pytest.mark.visual

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

