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
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.digest_day import (
    DigestDay,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
    DigestVisual,
)
from idhazh.contracts.review_queue import ReviewPopulation, ReviewQueue
from idhazh.contracts.visual import EncodingRole, VisualType
from idhazh.contracts.visual_data import RENDERER_VERSION, MarkId, VisualData
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    NoneReason,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.contracts.visual_label import VisualLabel
from idhazh.evals.visual_labels import summarize_visual_labels
from utilities import review_queue
from utilities.visual_labels import (
    append_visual_label,
    create_visual_label_draw,
    load_named_visual_label_rows,
    next_unlabelled_visual,
    published_item_url,
    read_visual_label_draw,
)

pytestmark = pytest.mark.visual

DATE: Final = "2026-08-21"


def _drawing(item_id: str) -> str:
    """Build two bars through the current published chart contract."""
    encoding: dict[str, list[MarkId]] = {role.value: [] for role in EncodingRole}
    encoding[EncodingRole.CATEGORY.value] = ["m0", "m1"]
    encoding[EncodingRole.QUANTITY.value] = ["m2", "m3"]
    return VisualData.model_validate(
        {
            "version": VisualData.schema_version(),
            "item_id": item_id,
            "type": VisualType.BAR,
            "renderer_version": RENDERER_VERSION,
            "declared_whole_element_id": None,
            "declared_whole": None,
            "title": None,
            "caption": None,
            "emphasized_mark_id": encoding[EncodingRole.QUANTITY.value][0],
            "marks": [
                {
                    "mark_id": f"m{index}",
                    "text": text,
                    "value": value,
                    "unit": "gw" if value is not None else None,
                    "source_text": None,
                    "element_id": f"wind-1-{index}",
                    "derived": None,
                }
                for index, (text, value) in enumerate(
                    [("Denmark", None), ("Norway", None), (None, "12"), (None, "6")]
                )
            ],
            "encoding": encoding,
        }
    ).to_json()


def _drawing_for_type(item_id: str, visual_type: VisualType | None) -> str:
    """Use a real visual-data fixture when a test needs a non-bar publication."""
    if visual_type not in {VisualType.PIE, VisualType.BUBBLE}:
        return _drawing(item_id)
    fixture_name = (
        "pie-from-declared-whole.json"
        if visual_type is VisualType.PIE
        else "bubble-relationship.json"
    )
    data = VisualData.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "visual-data" / fixture_name)
    )
    return data.model_copy(update={"item_id": item_id}).to_json()


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


def _measured_rendered(
    item_id: str,
    *,
    planned_type: VisualType,
    rendered_type: VisualType,
    downgrade_depth: int,
) -> VisualDecision:
    decision = _rendered(item_id)
    return VisualDecision.model_validate(
        decision.model_dump(mode="json")
        | {
            "planned_type": planned_type.value,
            "rendered_type": rendered_type.value,
            "downgrade_depth": downgrade_depth,
            "marks": 4,
        }
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
) -> tuple[Path, Path]:
    """Write one published day and the run payloads behind it. Returns both roots.

    Built rather than sampled: the archive has never produced a render that
    failed after its plan passed, and it cannot produce a decision for a story
    that did not publish at all.
    """
    digest_root = root / "public" / "digest"
    run_root = root / "run"
    day = DigestDay.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    )
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
                _drawing_for_type(item_id, decision.rendered_type),
                encoding="utf-8",
                newline="\n",
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
        assert copied.read_text(encoding="utf-8") == _drawing(row.item_id)
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
    """The other case, so the cap above is the budget and not the arithmetic."""
    queue = _build(tmp_path)
    assert all(entry.kept == entry.seen for entry in queue.census)
    assert queue.bytes_written > 0


def test_published_pie_and_bubble_queue_links_labels_and_reports_by_exact_type(
    tmp_path: Path,
) -> None:
    """The real queue, dated links and local labels keep machine and human evidence apart."""
    decisions = {
        "ai-31": _measured_rendered(
            "ai-31",
            planned_type=VisualType.PIE,
            rendered_type=VisualType.PIE,
            downgrade_depth=0,
        ),
        "ai-32": _measured_rendered(
            "ai-32",
            planned_type=VisualType.BUBBLE,
            rendered_type=VisualType.BUBBLE,
            downgrade_depth=0,
        ),
        "ai-33": _measured_rendered(
            "ai-33",
            planned_type=VisualType.PIE,
            rendered_type=VisualType.BAR,
            downgrade_depth=1,
        ),
    }
    digest_root, run_root = build_a_day(tmp_path, decisions=decisions)
    queue_path = tmp_path / "review" / DATE / "queue.json"
    queue = review_queue.build(
        date=DATE,
        digest_root=digest_root,
        run_root=run_root,
        out_root=tmp_path / "review",
        budget_bytes=5_000_000,
    )
    draw_root = tmp_path / "backend" / "var" / "visual-labels"
    bundle = create_visual_label_draw(
        queue_path,
        published_base_url="https://published.example/",
        root=draw_root,
    )
    resumed_bundle = create_visual_label_draw(
        queue_path,
        published_base_url="https://published.example/",
        root=draw_root,
    )
    pie = next(row for row in queue.rows if row.item_id == "ai-31")
    bubble = next(row for row in queue.rows if row.item_id == "ai-32")
    downgraded = next(row for row in queue.rows if row.item_id == "ai-33")

    assert pie.visual_id is not None
    assert bubble.visual_id is not None
    assert downgraded.visual_id is not None
    assert pie.visual_id == decisions["ai-31"].visual_id
    assert pie.planned_type is VisualType.PIE
    assert pie.rendered_type is VisualType.PIE
    assert bubble.visual_id == decisions["ai-32"].visual_id
    assert bubble.rendered_type is VisualType.BUBBLE
    assert downgraded.planned_type is VisualType.PIE
    assert downgraded.rendered_type is VisualType.BAR
    assert resumed_bundle.draw == bundle.draw
    assert published_item_url(bundle, pie.visual_id) == (
        f"https://published.example/{DATE}/#ai-31"
    )
    with pytest.raises(ValueError, match="not in this draw"):
        published_item_url(bundle, downgraded.visual_id)
    with pytest.raises(ValueError, match="not in this draw"):
        append_visual_label(
            draw_root,
            draw_id=bundle.draw.draw_id,
            reviewer_id="reviewer-one",
            visual_id=downgraded.visual_id,
            label=VisualLabel.KEEP,
            labelled_at="2026-10-27T11:32:00Z",
            page_is_live=True,
        )

    labelled_at = "2026-10-27T11:32:00Z"
    answers_by_item = {
        "ai-31": (VisualLabel.KEEP, VisualLabel.DISCARD),
        "ai-32": (VisualLabel.KEEP, VisualLabel.KEEP),
    }
    for reviewer_number, reviewer_id in enumerate(("reviewer-one", "reviewer-two")):
        while candidate := next_unlabelled_visual(
            draw_root, bundle, reviewer_id=reviewer_id
        ):
            _, visual_id, row = candidate
            assert append_visual_label(
                draw_root,
                draw_id=bundle.draw.draw_id,
                reviewer_id=reviewer_id,
                visual_id=visual_id,
                label=answers_by_item[row.item_id][reviewer_number],
                labelled_at=labelled_at,
                page_is_live=True,
            )
        assert next_unlabelled_visual(draw_root, bundle, reviewer_id=reviewer_id) is None

    assert not append_visual_label(
        draw_root,
        draw_id=bundle.draw.draw_id,
        reviewer_id="reviewer-one",
        visual_id=pie.visual_id,
        label=VisualLabel.KEEP,
        labelled_at=labelled_at,
        page_is_live=True,
    )
    with pytest.raises(ValueError, match="cannot change a label"):
        append_visual_label(
            draw_root,
            draw_id=bundle.draw.draw_id,
            reviewer_id="reviewer-one",
            visual_id=pie.visual_id,
            label=VisualLabel.DISCARD,
            labelled_at=labelled_at,
            page_is_live=True,
        )

    (draw_root / bundle.draw.draw_id / "not-requested.csv").write_text(
        "not,a,label,file\n", encoding="utf-8"
    )
    labels = load_named_visual_label_rows(
        draw_root,
        draw_id=bundle.draw.draw_id,
        reviewer_ids=("reviewer-one", "reviewer-two"),
    )
    evidence = summarize_visual_labels(
        bundle.queue,
        labels,
        draw_id=bundle.draw.draw_id,
        reviewer_ids=("reviewer-one", "reviewer-two"),
    )

    pie_result, bubble_result = evidence
    assert pie_result.machine_planned == 2
    assert pie_result.machine_rendered == 1
    assert pie_result.keep_rate == 0.5
    assert (
        pie_result.overlap_visuals,
        pie_result.agreeing_pairs,
        pie_result.reviewer_pairs,
    ) == (1, 0, 1)
    assert bubble_result.machine_planned == 1
    assert bubble_result.machine_rendered == 1
    assert bubble_result.keep_rate == 1.0
    assert (
        bubble_result.overlap_visuals,
        bubble_result.agreeing_pairs,
        bubble_result.reviewer_pairs,
    ) == (1, 1, 1)


def test_a_draw_directory_cannot_be_read_as_a_different_draw(tmp_path: Path) -> None:
    queue_path = CONTRACT_FIXTURES_DIR / "review-queue" / "published-pie-and-bubble.json"
    first = create_visual_label_draw(
        queue_path,
        published_base_url="https://published.example",
        root=tmp_path,
    )
    second = create_visual_label_draw(
        queue_path,
        published_base_url="https://elsewhere.example",
        root=tmp_path,
    )
    first_dir = tmp_path / first.draw.draw_id
    second_dir = tmp_path / second.draw.draw_id
    (second_dir / "draw.json").write_bytes((first_dir / "draw.json").read_bytes())
    (second_dir / "queue.json").write_bytes((first_dir / "queue.json").read_bytes())

    with pytest.raises(ValueError, match="does not match the requested draw"):
        read_visual_label_draw(tmp_path, second.draw.draw_id)


def test_a_human_rate_is_not_quotable_without_reviewer_overlap(tmp_path: Path) -> None:
    decision = _measured_rendered(
        "ai-34",
        planned_type=VisualType.PIE,
        rendered_type=VisualType.PIE,
        downgrade_depth=0,
    )
    digest_root, run_root = build_a_day(tmp_path, decisions={"ai-34": decision})
    queue = review_queue.build(
        date=DATE,
        digest_root=digest_root,
        run_root=run_root,
        out_root=tmp_path / "review",
        budget_bytes=5_000_000,
    )
    queue_path = tmp_path / "review" / DATE / "queue.json"
    draw_root = tmp_path / "labels"
    bundle = create_visual_label_draw(
        queue_path,
        published_base_url="https://published.example",
        root=draw_root,
    )
    row = queue.rows[0]
    assert row.visual_id is not None
    with pytest.raises(ValueError, match="exact published page is live"):
        append_visual_label(
            draw_root,
            draw_id=bundle.draw.draw_id,
            reviewer_id="reviewer-one",
            visual_id=row.visual_id,
            label=VisualLabel.KEEP,
            labelled_at="2026-10-27T11:32:00Z",
            page_is_live=False,
        )
    assert append_visual_label(
        draw_root,
        draw_id=bundle.draw.draw_id,
        reviewer_id="reviewer-one",
        visual_id=row.visual_id,
        label=VisualLabel.KEEP,
        labelled_at="2026-10-27T11:32:00Z",
        page_is_live=True,
    )

    labels = load_named_visual_label_rows(
        draw_root,
        draw_id=bundle.draw.draw_id,
        reviewer_ids=("reviewer-one", "reviewer-two"),
    )
    evidence = summarize_visual_labels(
        bundle.queue,
        labels,
        draw_id=bundle.draw.draw_id,
        reviewer_ids=("reviewer-one", "reviewer-two"),
    )

    assert evidence[0].overlap_visuals == 0
    assert evidence[0].reviewer_pairs == 0
    assert evidence[0].keep_rate is None
