"""What the extractor found, what the page drew, and the gap between the two.

The oracle is one number re-derived two ways. `extractable_but_unused_rate` is
worked out here from a built run's own element tables and the visuals its day
published, and it has to equal what the producer reports off the committed
census. A rate computed by a second copy of the producer proves nothing, so the
derivation here reads the tables and the visuals and never the record.

The classification query is pinned at both ends the row names: an article
stating three quantities that share a unit is `chartable`, and an article
stating none is `narrative`. The middle is its own class and is not either of
them.

Every article here is built from one paragraph through the real extractor, so
the cost is the run this file writes and never the archive behind it
(`CLAUDE.md` Rule #12). Nothing reads a committed day.
"""

from __future__ import annotations

import html
from collections import Counter
from typing import Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import config, elements, extract, publish_day_metrics, telemetry
from idhazh.contracts.app_config import ModelRef
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.day_metrics import DayMetrics
from idhazh.contracts.digest_day import (
    DigestDay,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
    DigestVisual,
)
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.item_health import ElementClass, ItemHealthRow
from idhazh.contracts.run_manifest import (
    ModelRole,
    ModelUse,
    RunManifest,
    RunRecord,
    RunStatus,
)
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import SourceTier
from idhazh.contracts.visual_decision import VisualKind, VisualState
from idhazh.evals import metrics
from idhazh.fetch import FetchResult

APP: Final = config.load(CONFIG_DIR).app
ELEMENTS: Final = APP.elements
MIN_CHART_POINTS: Final = APP.visuals.min_chart_points
_SUMMARY_OK: Final = Summary.from_json(
    read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json")
)

DATE: Final = "2026-08-20"
RUN_ID: Final = f"{DATE}-1"

#: Four articles whose class a person can read off the sentence. The first two
#: state three megawatt figures each, which is what the row calls chartable; the
#: third states no quantity at all; the fourth states one, which is neither.
BODIES: Final[tuple[tuple[str, ElementClass, bool], ...]] = (
    (
        "The plant produced 1,200 MW in the first year, 1,450 MW in the second "
        "and 1,610 MW in the third.",
        ElementClass.CHARTABLE,
        True,
    ),
    (
        "Demand reached 820 MW on Monday, 910 MW on Tuesday and 975 MW on Wednesday.",
        ElementClass.CHARTABLE,
        False,
    ),
    (
        "The minister said the review would report before the summer recess.",
        ElementClass.NARRATIVE,
        False,
    ),
    (
        "The plant produced 1,200 MW last year, the operator said.",
        ElementClass.UNCLASSIFIED,
        False,
    ),
)


def _planned(item_id: str, url: str) -> PlannedItem:
    return PlannedItem(
        item_id=item_id,
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="probe",
        tier=SourceTier.INSTITUTION,
        vertical="energy",
        rank_score=0.0,
        title="A grid story",
    )


def _article(body: str, *, item_id: str) -> Article:
    """One paragraph through the real extractor and the real sanitizer (Rule #7)."""
    page = (
        "<!DOCTYPE html><html><head><title>probe</title></head>"
        f"<body><article><p>{html.escape(body)}</p></article></body></html>"
    )
    url = f"https://probe.example/{item_id}"
    return extract.to_article(
        _planned(item_id, url),
        FetchResult(outcome=FetchOutcome.OK, status=200, body=page.encode("utf-8")),
        config=APP.extract,
        fetched_at=f"{DATE}T06:00:00Z",
    )


def _summary(item_id: str) -> Summary:
    """The committed OK summary, re-addressed to this built item."""
    payload = _SUMMARY_OK.model_dump(mode="json")
    payload["item_id"] = item_id
    payload["url_key"] = derive_url_key(f"https://probe.example/{item_id}")
    return Summary.model_validate(payload)


def _item_id(index: int) -> str:
    return f"energy-{index:02d}"


def _run() -> list[tuple[str, Article, ElementClass, bool]]:
    """The built run: one article per body, with the class a person read off it."""
    return [
        (_item_id(index), _article(body, item_id=_item_id(index)), expected, charted)
        for index, (body, expected, charted) in enumerate(BODIES, start=1)
    ]


def _health_rows() -> list[ItemHealthRow]:
    return [
        telemetry.classify_item(
            planned=_planned(item_id, f"https://probe.example/{item_id}"),
            article=article,
            summary=_summary(item_id),
            date=DATE,
            run_id=RUN_ID,
            extraction=elements.extraction_health(
                article, config=ELEMENTS, min_chart_points=MIN_CHART_POINTS
            ),
        )
        for item_id, article, _, _ in _run()
    ]


def _day() -> DigestDay:
    items = [
        DigestItem(
            item_id=item_id,
            vertical="energy",
            title="A grid story",
            source_url=f"https://probe.example/{item_id}",
            source_id="probe",
            source_name="Probe",
            summary="A short summary of one grid story.",
            key_points=["The reserve margin held."],
            band=ConfidenceBand.HIGH,
            visual=(
                DigestVisual(
                    kind=VisualKind.CHART,
                    state=VisualState.RENDERED,
                    path=f"digest/2026/08/20/{item_id}/chart.svg",
                )
                if charted
                else None
            ),
            introduced_by_run=1,
        )
        for item_id, _, _, charted in _run()
    ]
    return DigestDay(
        version=DigestDay.schema_version(),
        date=DATE,
        generated_at=f"{DATE}T18:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[DigestRunRef(n=1, at=f"{DATE}T06:00:00Z", items_added=len(items))],
        verticals=[
            DigestVerticalRef(
                id="energy",
                display_name="Energy",
                count=len(items),
                considered=len(items),
                too_old=0,
                below_feed_floor=False,
            )
        ],
        items=items,
    )


def _manifest() -> RunManifest:
    return RunManifest(
        version=RunManifest.schema_version(),
        date=DATE,
        runs=[
            RunRecord(
                run_id=RUN_ID,
                n=1,
                started_at=f"{DATE}T06:00:00Z",
                completed_at=f"{DATE}T06:30:00Z",
                status=RunStatus.COMPLETED,
                commit_sha="0" * 40,
                runner="test-cpu",
                items_planned=len(BODIES),
                items_succeeded=len(BODIES),
                items_failed=0,
                items_skipped=0,
                models=[
                    ModelUse(
                        role=ModelRole.SUMMARIZE,
                        model_ref=ModelRef(
                            id="energy-model",
                            repo="acme/energy",
                            file="w.gguf",
                            quantisation="Q4_K_M",
                        ),
                    )
                ],
                pipeline_fingerprints=["a" * 64],
                site_bytes=1000,
                site_files=10,
            )
        ],
    )


def _record() -> DayMetrics:
    return publish_day_metrics.build(
        date=DATE,
        day=_day(),
        manifest=_manifest(),
        score_rows=[],
        health_rows=[row.csv_row() for row in _health_rows()],
    )


# --- the classification query, pinned at both ends -------------------------


@pytest.mark.parametrize(
    ("body", "expected"),
    [(body, expected) for body, expected, _ in BODIES],
    ids=[expected.value for _, expected, _ in BODIES] + [],
)
def test_the_class_is_the_one_a_person_reads_off_the_sentence(
    body: str, expected: ElementClass
) -> None:
    table = elements.element_table(_article(body, item_id="energy-01"), config=ELEMENTS)
    assert elements.classify(table, min_chart_points=MIN_CHART_POINTS) is expected


def test_the_chartable_end_really_does_state_three_quantities_of_one_unit() -> None:
    """The counter-oracle. A class read off an empty table proves the table, not the query."""
    table = elements.element_table(_article(BODIES[0][0], item_id="energy-01"), config=ELEMENTS)
    units = [element.unit for element in table.elements if element.unit is not None]
    assert units == ["mw", "mw", "mw"]


def test_the_narrative_end_really_does_state_no_quantity() -> None:
    table = elements.element_table(_article(BODIES[2][0], item_id="energy-03"), config=ELEMENTS)
    assert table.elements == []


# --- the oracle -------------------------------------------------------------


def test_the_rate_the_record_reports_is_the_one_the_tables_and_the_visuals_give() -> None:
    """Re-derived from the run's own tables and its day's visuals, never from the record."""
    charted = {item_id for item_id, _, _, drew in _run() if drew}
    chartable = {
        item_id
        for item_id, article, _, _ in _run()
        if elements.classify(
            elements.element_table(article, config=ELEMENTS), min_chart_points=MIN_CHART_POINTS
        )
        is ElementClass.CHARTABLE
    }
    expected = metrics.extractable_but_unused_rate(
        chartable_published=len(chartable),
        chartable_charted=len(chartable & charted),
    )

    extraction = _record().extraction
    assert extraction is not None
    reported = metrics.extractable_but_unused_rate(
        chartable_published=extraction.chartable_published,
        chartable_charted=extraction.chartable_charted,
    )
    assert reported == expected
    assert expected == pytest.approx(0.5)


def test_every_span_re_sliced_so_the_integrity_rate_is_whole() -> None:
    extraction = _record().extraction
    assert extraction is not None
    assert metrics.span_integrity_rate(
        items=extraction.items, passed=extraction.span_integrity_pass
    ) == pytest.approx(1.0)


def test_the_block_counts_the_run_the_way_the_bodies_were_written() -> None:
    """The counter-oracle on the join. A rate can be right while both counts are wrong."""
    expected = Counter(element_class for _, element_class, _ in BODIES)
    found = sum(
        len(elements.element_table(article, config=ELEMENTS).elements)
        for _, article, _, _ in _run()
    )

    extraction = _record().extraction
    assert extraction is not None
    assert extraction.items == len(BODIES)
    assert extraction.span_integrity_pass == len(BODIES)
    assert extraction.elements_found == found
    assert extraction.chartable == expected[ElementClass.CHARTABLE]
    assert extraction.narrative == expected[ElementClass.NARRATIVE]
    assert extraction.unclassified == expected[ElementClass.UNCLASSIFIED]
    assert extraction.chartable_published == expected[ElementClass.CHARTABLE]
    assert extraction.chartable_charted == sum(1 for _, cls, drew in BODIES if drew and cls)


def test_a_day_whose_rows_never_ran_the_pass_carries_no_block() -> None:
    """A block of zeros would report an extractor that found nothing (Rule #10)."""
    blank = [
        {**row.csv_row(), "span_integrity": "", "elements_found": "", "element_class": ""}
        for row in _health_rows()
    ]
    record = publish_day_metrics.build(
        date=DATE,
        day=_day(),
        manifest=_manifest(),
        score_rows=[],
        health_rows=blank,
    )
    assert record.extraction is None


def test_a_rate_over_nothing_is_not_zero() -> None:
    assert metrics.extractable_but_unused_rate(chartable_published=0, chartable_charted=0) is None
    assert metrics.span_integrity_rate(items=0, passed=0) is None
