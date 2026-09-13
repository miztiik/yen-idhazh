"""The review tree: three populations, and never a published surface.

The oracle this module exists for is the second half of its title. `review/` is
gitignored, so the ordinary defences - the commit's staged path list, the CI
scope selector, a reviewer reading a diff - cannot see it at all. What stops it
becoming a published surface is a refusal in the writer and a scan over a built
tree, and both are asserted here.

Every case is driven from a day built in this module, never from the committed
archive (`CLAUDE.md` section 13, Guardrail #12). The built day also carries two shapes
no committed day holds: a render that failed after its plan passed, and a
decision for a story the day did not publish.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.digest_day import (
    DigestDay,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
    DigestVisual,
)
from idhazh.contracts.review_queue import ReviewPopulation, ReviewQueue
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    NoneReason,
    VisualDecision,
    VisualKind,
    VisualState,
)
from utilities import review_queue

pytestmark = pytest.mark.visual

DATE: Final = "2026-08-21"
#: One published visual, as the day directory holds it. Three bars the sheet
#: draws itself: nothing renders an SVG any more, so the reviewer reads the
#: comparison off marks this file states rather than off a picture.
DRAWING: Final = (
    '{"version":"2026-09-13T20:00","item_id":"ai-01","type":"bar",'
    '"renderer_version":"2026-09-13",'
    '"marks":['
    '{"mark_id":"m0","text":"Denmark","value":null,"unit":null,'
    '"element_id":"wind-1-0","derived":null},'
    '{"mark_id":"m1","text":"Norway","value":null,"unit":null,'
    '"element_id":"wind-1-1","derived":null},'
    '{"mark_id":"m2","text":null,"value":"12","unit":"gw",'
    '"element_id":"wind-1-2","derived":null},'
    '{"mark_id":"m3","text":null,"value":"6","unit":"gw",'
    '"element_id":"wind-1-3","derived":null}],'
    '"encoding":{"category":["m0","m1"],"quantity":["m2","m3"],"quantity_x":[],'
    '"time":[],"series":[],"size":[],"bins":[],"entity":[],"event_label":[]}}'
)


def _decision(item_id: str, **changes: object) -> VisualDecision:
    """One committed decision, moved to this day and this item."""
    base = VisualDecision.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json")
    )
    return base.model_copy(update={"item_id": item_id, **changes})


def _item(day: DigestDay, item_id: str, *, title: str, visual: DigestVisual | None) -> DigestItem:
    return day.items[0].model_copy(
        update={
            "item_id": item_id,
            "title": title,
            "visual": visual,
            "vertical": "ai",
            "desk": None,
            "introduced_by_run": 1,
            "updated_by_run": None,
            "updated_at": None,
            "same_story_as": None,
        }
    )


def _rendered(item_id: str) -> VisualDecision:
    return _decision(
        item_id,
        visual_state=VisualState.RENDERED,
        data_path=f"digest/2026/08/21/{item_id}.json",
    )


def _refused(item_id: str) -> VisualDecision:
    """A chart was drafted and the validator threw it out, so there is no spec."""
    return _decision(
        item_id,
        kind=VisualKind.NONE,
        spec=None,
        data_path=None,
        visual_state=VisualState.ABSENT,
        drafted_chart=True,
        none_reason=NoneReason.VALIDATION_FAILED,
    )


def _render_failed(item_id: str) -> VisualDecision:
    """The plan compiled and its file did not land. The reader got nothing either way."""
    return _decision(
        item_id,
        data_path=None,
        visual_state=VisualState.RENDER_FAILED,
        failure_detail="the data file could not be written: OSError",
    )


def _never_drafted(item_id: str) -> VisualDecision:
    return _decision(
        item_id,
        kind=VisualKind.NONE,
        spec=None,
        data_path=None,
        visual_state=VisualState.ABSENT,
        drafted_chart=False,
        none_reason=NoneReason.MODEL_DECLINED,
    )


def build_a_day(
    root: Path,
    *,
    decisions: dict[str, VisualDecision],
    titles: dict[str, str] | None = None,
    unpublished: str | None = None,
    drawing: str = DRAWING,
) -> tuple[Path, Path]:
    """Write one published day and the run payloads behind it. Returns both roots.

    Built rather than sampled: the archive has never produced a render that
    failed after its plan passed, and it cannot produce a decision for a story
    that did not publish at all.
    """
    digest_root = root / "public" / "digest"
    run_root = root / "run"
    day = DigestDay.from_json(read_text(next((CONTRACT_FIXTURES_DIR / "digest-day").glob("*.json"))))
    named = titles or {}

    items = [
        _item(
            day,
            item_id,
            title=named.get(item_id, f"Story {item_id}"),
            visual=(
                DigestVisual(
                    kind=VisualKind.CHART,
                    state=VisualState.RENDERED,
                    data_path=decision.data_path,
                    alt=decision.alt_text,
                )
                if decision.visual_state is VisualState.RENDERED
                else None
            ),
        )
        for item_id, decision in decisions.items()
        if item_id != unpublished
    ]
    published = day.model_copy(
        update={
            "version": DigestDay.schema_version(),
            "date": DATE,
            "items": items,
            "items_planned": len(items),
            "items_failed": 0,
            "partial": False,
            "runs": [DigestRunRef(n=1, at=f"{DATE}T06:00:00Z", items_added=len(items))],
            "verticals": [DigestVerticalRef(id="ai", display_name="AI", count=len(items))],
            "leads": [],
            "embeddings": None,
        }
    )
    day_directory = digest_root / "2026" / "08" / "21"
    day_directory.mkdir(parents=True)
    (day_directory / "digest.json").write_text(published.to_json(), encoding="utf-8", newline="\n")

    items_dir = run_root / DATE / "items"
    items_dir.mkdir(parents=True)
    for item_id, decision in decisions.items():
        (items_dir / f"{item_id}{PAYLOAD_SUFFIX}").write_text(
            decision.to_json(), encoding="utf-8", newline="\n"
        )
        if decision.data_path is not None:
            (digest_root.parent / decision.data_path).write_text(
                drawing, encoding="utf-8", newline="\n"
            )
    return digest_root, run_root


def an_ordinary_day(root: Path, **kwargs: object) -> tuple[Path, Path]:
    """One of each population, plus the render that failed after its plan passed."""
    return build_a_day(
        root,
        decisions={
            "ai-01": _rendered("ai-01"),
            "ai-02": _refused("ai-02"),
            "ai-03": _render_failed("ai-03"),
            "ai-04": _never_drafted("ai-04"),
        },
        **kwargs,  # type: ignore[arg-type]
    )


def _build(tmp_path: Path, *, budget_bytes: int = 5_000_000) -> ReviewQueue:
    digest_root, run_root = an_ordinary_day(tmp_path)
    return review_queue.build(
        date=DATE,
        digest_root=digest_root,
        run_root=run_root,
        out_root=tmp_path / "review",
        budget_bytes=budget_bytes,
    )


# --- The populations ------------------------------------------------------


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (_rendered("ai-01"), ReviewPopulation.PUBLISHED),
        (_refused("ai-02"), ReviewPopulation.REJECTED),
        (_render_failed("ai-03"), ReviewPopulation.REJECTED),
        (_never_drafted("ai-04"), ReviewPopulation.NONE),
    ],
    ids=["rendered", "validator refused", "render failed", "never drafted"],
)
def test_the_population_is_read_off_the_decision(
    decision: VisualDecision, expected: ReviewPopulation
) -> None:
    """The published day cannot answer this, which is why the decisions are the source.

    A day payload carries `visual: null` for every item without a picture, so
    from it alone a chart the validator refused and a story nobody drafted one
    for are the same absence. Telling those apart is most of the point.
    """
    assert review_queue.population_of(decision) is expected


def test_a_day_of_four_decisions_lands_one_in_each_place(tmp_path: Path) -> None:
    queue = _build(tmp_path)
    seen = {entry.population: entry.seen for entry in queue.census}
    assert seen == {
        ReviewPopulation.PUBLISHED: 1,
        ReviewPopulation.REJECTED: 2,
        ReviewPopulation.NONE: 1,
    }
    assert [row.item_id for row in queue.rows] == ["ai-01", "ai-02", "ai-03", "ai-04"]


def test_a_decision_for_a_story_the_day_did_not_publish_is_not_reviewed(tmp_path: Path) -> None:
    """The question is about the visuals a reader met."""
    digest_root, run_root = an_ordinary_day(tmp_path, unpublished="ai-04")
    queue = review_queue.build(
        date=DATE,
        digest_root=digest_root,
        run_root=run_root,
        out_root=tmp_path / "review",
        budget_bytes=5_000_000,
    )
    assert "ai-04" not in {row.item_id for row in queue.rows}
    assert {entry.population for entry in queue.census} == set(ReviewPopulation)


def test_the_tree_carries_its_own_copy_of_every_drawing_it_names(tmp_path: Path) -> None:
    """A tree that pointed back at the repository would be unreadable after a zip."""
    queue = _build(tmp_path)
    out_dir = tmp_path / "review" / DATE
    drawn = [row for row in queue.rows if row.asset_relpath is not None]
    assert [row.item_id for row in drawn] == ["ai-01"]
    for row in drawn:
        assert row.asset_relpath is not None
        copied = out_dir / row.asset_relpath
        assert copied.read_text(encoding="utf-8") == DRAWING
    assert json.loads((out_dir / "queue.json").read_text(encoding="utf-8"))["date"] == DATE


# --- The oracle: never a published surface --------------------------------


@pytest.mark.parametrize("tree", ["frontend/public", "frontend/build"])
def test_the_writer_refuses_an_output_directory_inside_a_published_tree(
    tmp_path: Path, tree: str
) -> None:
    """The control, and the reason it is a refusal rather than a review note.

    `review/` is gitignored, so a path that drifted under the published tree
    would be staged by nothing, shown in no diff, and found by nobody until it
    was serving.
    """
    digest_root, run_root = an_ordinary_day(tmp_path)
    with pytest.raises(SystemExit, match="build artifact"):
        review_queue.build(
            date=DATE,
            digest_root=digest_root,
            run_root=run_root,
            out_root=Path(tree) / "review",
            budget_bytes=5_000_000,
        )


def test_nothing_in_the_published_tree_names_the_review_tree(tmp_path: Path) -> None:
    """The row's oracle: after a build, `review/` exists and the day does not know it.

    Driven from the day built above rather than from the committed archive, so
    the cost follows the code this checks and not what the pipeline has piled up.
    """
    queue = _build(tmp_path)
    out_dir = tmp_path / "review" / DATE
    assert out_dir.is_dir() and (out_dir / "index.html").is_file()
    assert queue.rows

    published = tmp_path / "public"
    named = [
        path.relative_to(published).as_posix()
        for path in published.rglob("*")
        if path.is_file() and "review" in path.read_text(encoding="utf-8")
    ]
    assert named == [], f"the published tree names the review tree in {named}"


def test_the_review_tree_is_written_where_git_already_ignores_it() -> None:
    """One default, so the artifact door and the local door cannot disagree."""
    assert review_queue.DEFAULT_OUT.as_posix().startswith("backend/var/")


# --- Untrusted text, and the budget ---------------------------------------


def test_a_title_carrying_markup_reaches_the_sheet_as_words(tmp_path: Path) -> None:
    """Fetched text is data (Guardrail #11). The sheet is HTML, so it is escaped here."""
    digest_root, run_root = an_ordinary_day(
        tmp_path, titles={"ai-01": "<script>alert(1)</script> & more"}
    )
    review_queue.build(
        date=DATE,
        digest_root=digest_root,
        run_root=run_root,
        out_root=tmp_path / "review",
        budget_bytes=5_000_000,
    )
    sheet = (tmp_path / "review" / DATE / "index.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in sheet
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in sheet
    assert "Denmark" in sheet, "the sheet draws the bars it copied"


def test_a_tree_over_budget_caps_every_population_and_records_both_numbers(
    tmp_path: Path,
) -> None:
    """Degrade, do not fail: the job that builds this one also publishes the day.

    Proportional rather than truncating, because an artifact that looks complete
    and is a biased sample is worse than a smaller honest one - nobody can see
    it happened.
    """
    decisions = {f"ai-{n:02d}": _never_drafted(f"ai-{n:02d}") for n in range(1, 21)}
    decisions["ai-21"] = _rendered("ai-21")
    digest_root, run_root = build_a_day(tmp_path, decisions=decisions)
    queue = review_queue.build(
        date=DATE,
        digest_root=digest_root,
        run_root=run_root,
        out_root=tmp_path / "review",
        budget_bytes=5_000,
    )
    counted = {entry.population: entry for entry in queue.census}
    assert counted[ReviewPopulation.NONE].seen == 20
    assert 0 < counted[ReviewPopulation.NONE].kept < 20
    assert counted[ReviewPopulation.PUBLISHED].kept == 1, "a population with rows keeps one"
    assert counted[ReviewPopulation.REJECTED].seen == 0


def test_a_day_inside_its_budget_keeps_everything(tmp_path: Path) -> None:
    """The other arm, so the cap above is the budget and not the arithmetic."""
    queue = _build(tmp_path)
    assert all(entry.kept == entry.seen for entry in queue.census)
    assert queue.bytes_written > 0
