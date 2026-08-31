"""Publish every injection canary as a real day, for the browser suite to attack.

The pipeline's controls sit behind this. By the time text is in a payload the
sanitizer has already run, so a canary day built from sanitized text would only
re-assert the control the backend suite already asserts.

This builds the day from the **raw** attack text instead. That is the honest
worst case for the browser boundary: suppose the sanitizer regressed, or a model
repeated an attack verbatim, and the markup reached a payload. The published
surface must still render it as words. If it does not, the page is one bad
summary away from being a click target a stranger chose.

Operator tooling. It never runs in the pipeline and never writes into the
published tree.

It also writes the run manifest, the feed-health rows and the score ledger that
day would have produced, plus a run of earlier quiet days so the console's run
strip has a real time axis to draw. The console draws all of them, and a console
with no data to draw can only be tested for the empty state. These are fixtures
under `backend/var/canary/`, reachable only because the build reads
`DIGEST_ROOT` and `STATE_ROOT` - a fixture can never reach the real ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Sequence
from datetime import date as calendar_date
from datetime import timedelta
from pathlib import Path
from typing import Final, NamedTuple

from idhazh import config
from idhazh.assemble import (
    build_embeddings,
    day_dir,
    month_of,
    reader_note,
    rebuild_search_index,
    to_digest_visual,
    write_atomic,
)
from idhazh.contracts.app_config import EvaluationConfig, ModelRef
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.route import Route, SpecFormat, VisualKind
from idhazh.contracts.run_manifest import ModelRole, ModelUse, RunManifest, RunRecord, RunStatus
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import LensId, SourceKind, SourceTier
from idhazh.embed import Embedder
from idhazh.evals import metrics, score, writer
from idhazh.ledger import append_health
from idhazh.render import asset_relpath, render_route

CANARY_DIR = Path("tests/fixtures/canaries")
DATE = "2026-08-20"
YESTERDAY = "2026-08-19"

#: Quiet days before the attack day. The console's run strip is a time axis, and
#: a time axis with one column cannot be read, scrolled or mislabelled - so it
#: cannot be tested either. Nineteen earlier days give it a week cadence, a
#: dropped label near the newest end, and more width than a phone.
HISTORY_DAYS = 19

#: A fixture commit, not a real one. Forty hex characters is the shape the
#: manifest requires, and a run of zeroes cannot be mistaken for a commit.
FIXTURE_SHA = "0" * 40

#: What the committed payload tree measured on the oldest day the fixture holds.
SITE_BYTES_FIRST_DAY = 54_230
#: What one more fixture day adds to it. A tree that measures the same on every
#: day makes the console's per-article cost zero, and zero reads as free rather
#: than as unmeasured - so the fixture has to grow for the chart to have a rate
#: at all.
SITE_BYTES_PER_DAY = 11_000

# Two items carry a real visual, so the browser suite exercises the picture path
# rather than proving it safe by never serving one. The specs are ours, not a
# model's - this file tests the surface, not the router.
CHART_SPEC = json.dumps(
    {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "background": "transparent",
        "data": {
            "values": [
                {"label": "2025", "value": 15400},
                {"label": "2024", "value": 11200},
                {"label": "2023", "value": 8600},
            ]
        },
        "encoding": {
            "x": {"axis": {"title": "megawatt"}, "field": "value", "type": "quantitative"},
            "y": {"axis": {"title": None}, "field": "label", "sort": None, "type": "nominal"},
        },
        "height": 410,
        "mark": {"color": "#4c6ef5", "type": "bar"},
        "width": 680,
    },
    separators=(",", ":"),
    sort_keys=True,
)

DIAGRAM_SPEC = (
    'flowchart TD\n    n0["Filed"]\n    n1["Reviewed"]\n    n2["Approved"]\n'
    "    n0 --> n1\n    n1 --> n2"
)

#: What the model was given on an item extract cut short, and so the length an
#: item has to pass to count as cut. A real run derives this from the token cap;
#: a fixture day states it.
SEEN_WORD_CAP: Final = 2100

#: Where that cut fell, in tokens. The article contract makes a cut name its own
#: cap, and extract counts 1.3 tokens to a word.
SEEN_TOKEN_CAP: Final = round(SEEN_WORD_CAP * 1.3)

#: The one published item whose feed declares an abstract, and which the cap also
#: cut. `assemble.reader_note` joins a sentence for each limit, and that pair had
#: a unit test and nothing that rendered it: measured 2026-08-29 over every
#: committed `frontend/public/digest/**/digest.json`, no published item carries
#: an abstract note at all. So the two sentences a reader would meet were the two
#: sentences no browser could read back.
ABSTRACT_AT: Final = 6

#: The places `EvalRow` rounds `hhem_delta` to before it re-checks it on read.
_DELTA_PLACES: Final = 6

#: The four counterweights no console surface reads back. Held flat across the
#: fixture on purpose: varying them would put a measurement in the ledger that
#: nobody made, and the columns that are varied below are varied because a page
#: draws them.
_EXTRACTIVENESS: Final = 0.22
_VERBATIM_RUN: Final = 0.07
_EVIDENTIAL_DENSITY: Final = 0.011
_SPECULATIVE_DENSITY: Final = 0.004


class _Measured(NamedTuple):
    """What one item measured. Everything a rule can derive is derived from it.

    The band, the truncation flag, the faithfulness delta and the compression
    ratio all come out of these numbers through the same functions the pipeline
    uses, so a fixture row cannot hold a combination a real run could not
    produce.
    """

    source_words: int
    summary_words: int
    hhem: float
    hhem_full: float
    coverage: float
    score_ms: int
    unsupported_numbers: int = 0
    hedge_dropped: bool = False
    #: False where the article's length before the cut was never written down.
    #: The row still scores and still counts on every table; it has no x on the
    #: compression plot, so the plot drops it and says how many it dropped.
    #: Measured over the committed ledger 2026-08-29: 142 of 2,683 rows are in
    #: this state, which is 5.3 percent of them.
    full_length_known: bool = True


#: One measured item per published canary, in the digest's own order.
#:
#: The console's compression plot draws source words against summary words on a
#: log x axis, with the configured target zone behind the marks and a diamond on
#: anything the scorer flagged as truncated. A day that scored eight items the
#: same way would leave every one of those states undrawn and so untested.
#:
#: Read down the source-word column: 38 to 6100 words is four decades of x axis
#: and at least one mark under each of the five configured target zones. Read
#: down the faithfulness columns: all three confidence bands, and every reason
#: an item can miss the top one. Two rows record no length before the cut, so
#: the plot drops them and the sentence under it has a count to print.
SCORED: Final[tuple[_Measured, ...]] = (
    # A release note. Under the shortest target zone, and left of the 100-word
    # floor the plot seeds its axis with - the one mark that can say whether the
    # axis widened to hold it or clamped it onto the edge.
    _Measured(
        source_words=38, summary_words=31,
        hhem=0.93, hhem_full=0.92, coverage=0.78, score_ms=180,
    ),
    # High confidence, second target zone.
    _Measured(
        source_words=140, summary_words=62,
        hhem=0.86, hhem_full=0.84, coverage=0.61, score_ms=240,
    ),
    # Medium on faithfulness alone, and a second mark in that zone, so the zone
    # is not a step drawn under a single point.
    _Measured(
        source_words=410, summary_words=78,
        hhem=0.71, hhem_full=0.70, coverage=0.52, score_ms=290,
    ),
    # Faithful, but the lead's names and figures did not survive, so the band is
    # capped at medium and the reason is the missing lead.
    _Measured(
        source_words=880, summary_words=96,
        hhem=0.88, hhem_full=0.87, coverage=0.22, score_ms=330,
    ),
    # Faithful, but the article hedged and the summary asserted. Its length
    # before the cut was never recorded, so it scores and counts but is not on
    # the plot - the state the sentence under the chart exists to declare.
    _Measured(
        source_words=1320, summary_words=118,
        hhem=0.90, hhem_full=0.89, coverage=0.64, score_ms=410,
        hedge_dropped=True, full_length_known=False,
    ),
    # Low on faithfulness, in the widest target zone. Longer than SEEN_WORD_CAP,
    # so it is also the shortest article the day records as cut - and it is the
    # second row recording no length before that cut, so the count in the
    # sentence under the plot is a number rather than a one a test could pass by
    # printing whatever it found. Cut and unplaceable together is the real
    # historical state: a row written before 2026-08-27 whose article was cut
    # has no full length anywhere.
    _Measured(
        source_words=2450, summary_words=164,
        hhem=0.44, hhem_full=0.43, coverage=0.48, score_ms=520,
        full_length_known=False,
    ),
    # Cut: the article is longer than what the model was given, so the plot draws
    # a diamond rather than a dot. It sits in the second-widest target zone,
    # which the ladder only gained a ceiling for when the fifth rung landed on
    # 2026-08-29 - before that this row was 4200 words and the zone above 2000
    # ran to the edge of the plot. It is also the day's abstract, so it is the
    # one item whose note has to carry two source limits at once.
    _Measured(
        source_words=2800, summary_words=205,
        hhem=0.91, hhem_full=0.78, coverage=0.57, score_ms=610,
    ),
    # Cut, and low whatever the scorer thought: the summary asserts two
    # figures the article never gave, and nothing else in the row may outvote
    # that.
    _Measured(
        source_words=6100, summary_words=190,
        hhem=0.83, hhem_full=0.69, coverage=0.55, score_ms=640,
        unsupported_numbers=2,
    ),
)


def canaries(directory: Path = CANARY_DIR) -> list[dict[str, object]]:
    """Every canary, build-time and browser, in a stable order."""
    paths = sorted(directory.glob("*.json")) + sorted((directory / "browser").glob("*.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def was_cut(measured: _Measured) -> bool:
    """An article longer than what the model was given is an article that was cut.

    The same direction the real extractor works in, and one spelling of it, so
    the digest page and the ledger row cannot disagree about the same item.
    """
    return measured.source_words > SEEN_WORD_CAP


def seen_words(measured: _Measured) -> int:
    """What the model was given: the whole body, or the cap where the body was longer."""
    return min(measured.source_words, SEEN_WORD_CAP)


def verdict_for(measured: _Measured, evaluation: EvaluationConfig) -> score.Verdict:
    """The band a reader sees and the reason under it, from the pipeline's own rule.

    One call feeds both the published item and the ledger row, so the two files
    cannot disagree about what the same item scored on the same day.
    """
    return score.verdict(
        measured.hhem,
        unsupported_numbers=measured.unsupported_numbers,
        lead_coverage=measured.coverage,
        hedge_dropped=measured.hedge_dropped,
        config=evaluation,
    )


def article_for(index: int, canary: dict[str, object], measured: _Measured) -> Article:
    """The article behind one published item, as far as its reader note reads it.

    It exists so `assemble.reader_note` composes the note. A canary builder that
    spelled the sentence itself could drift from the sentence a reader gets while
    the browser suite stayed green, which is the defect this fixture is for.

    The lengths are the ledger's own, through the same two functions: the model
    saw `seen_words`, and the length before the cut is recorded only where the
    fixture says the day has one.
    """
    url = str(canary["source_url"])
    cut = was_cut(measured)
    return Article(
        version=Article.schema_version(),
        item_id=f"ai-{index + 1:02d}",
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="canary",
        tier=SourceTier.INSTITUTION,
        source_form=SourceForm.ABSTRACT if index == ABSTRACT_AT else SourceForm.ARTICLE,
        vertical="ai",
        rank_score=0.0,
        title=str(canary["raw_title"]),
        text=str(canary["raw_text"]),
        word_count=seen_words(measured),
        source_word_count=measured.source_words if measured.full_length_known else None,
        truncated=cut,
        truncated_at_tokens=SEEN_TOKEN_CAP if cut else None,
        fetched_at=f"{DATE}T05:00:00Z",
        status=ArticleStatus.OK,
        extractor_version="canary",
        sanitizer_version="canary",
    )


def to_item(
    index: int,
    canary: dict[str, object],
    measured: _Measured,
    run_n: int,
    verdict: score.Verdict,
) -> DigestItem:
    raw_text = str(canary["raw_text"])
    source = article_for(index, canary, measured)
    return DigestItem(
        item_id=source.item_id,
        vertical="ai",
        title=str(canary["raw_title"]),
        source_url=str(canary["source_url"]),
        source_id="canary",
        source_name="Canary fixture",
        source_kind=SourceKind.REPORTING,
        summary=raw_text,
        key_points=[line for line in raw_text.splitlines() if line.strip()][:3] or ["-"],
        band=verdict.band,
        band_reason=verdict.reason,
        source_form=source.source_form,
        reader_note=reader_note(source),
        truncated=source.truncated,
        lenses=lenses_for(index),
        introduced_by_run=run_n,
    )


def lenses_for(index: int) -> list[LensId]:
    """Enough lens states for the page to be tested, planted on existing items.

    Three states and no fourth: none, one, and more than the page will show. The
    third is what proves the cap, and it has to exceed it rather than meet it.
    A new item would have been the obvious way to carry these and is the wrong
    one - the canary suite counts what is on the page.
    """
    if index == 1:
        return [LensId.WAR]
    if index == 2:
        return [LensId.CHINA, LensId.TRADE, LensId.CHIPS]
    return []


def visual_for(index: int, item_id: str, target: Path) -> Route | None:
    """A rendered chart on the first item, a rendered diagram on the second."""
    if index == 0:
        kind, spec, fmt = VisualKind.CHART, CHART_SPEC, SpecFormat.VEGA_LITE
        alt = "Bar chart. 2025 15,400 megawatt; 2024 11,200 megawatt; 2023 8,600 megawatt."
    elif index == 1:
        kind, spec, fmt = VisualKind.DIAGRAM, DIAGRAM_SPEC, SpecFormat.MERMAID
        alt = "Flow diagram. Filed then Reviewed then Approved."
    else:
        return None

    route = Route(
        version=Route.schema_version(),
        item_id=item_id,
        url_key="0" * 64,
        kind=kind,
        spec=spec,
        spec_format=fmt,
        alt_text=alt,
        model_id="canary",
        routed_at=f"{DATE}T06:00:00Z",
    )
    return render_route(
        route,
        # The payload stores `digest/<Y>/<M>/<D>/...`, so the root here is the
        # parent of the digest directory - exactly as the real pipeline does it.
        public_root=target.parent,
        relpath=asset_relpath(DATE, item_id),
    )


def published_items(
    evaluation: EvaluationConfig, directory: Path = CANARY_DIR
) -> list[DigestItem]:
    """The day's items before their visuals, composed once.

    A test reads the same list the day publishes rather than rebuilding it, so
    a fixture the suite asserts about cannot be a different fixture from the one
    the browser gets.
    """
    return [
        to_item(index, canary, measured, 1, verdict_for(measured, evaluation))
        for index, (canary, measured) in enumerate(zip(canaries(directory), SCORED, strict=True))
    ]


def build(target: Path, evaluation: EvaluationConfig) -> DigestDay:
    items = published_items(evaluation)
    items = [
        item.model_copy(
            update={"visual": to_digest_visual(visual_for(index, item.item_id, target))}
        )
        for index, item in enumerate(items)
    ]
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=DATE,
        generated_at=f"{DATE}T06:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        retention_window_months=-1,
        runs=[DigestRunRef(n=1, at=f"{DATE}T06:00:00Z", items_added=len(items))],
        verticals=[DigestVerticalRef(id="ai", display_name="AI", count=len(items))],
        items=items,
        embeddings=build_embeddings(items, Embedder(Path.cwd())),
    )
    write_atomic(day_dir(target, DATE) / "digest.json", day.to_json())
    return day


def _site_bytes(date: str) -> int:
    """The payload tree as it stood on that fixture day.

    Every run of one day reports the same figure, the way a real day does: the
    site is one thing measured once per run, and the console reads the last of
    them.
    """
    first = calendar_date.fromisoformat(DATE) - timedelta(days=HISTORY_DAYS)
    elapsed = (calendar_date.fromisoformat(date) - first).days
    return SITE_BYTES_FIRST_DAY + max(0, elapsed) * SITE_BYTES_PER_DAY


def _record(
    date: str,
    n: int,
    status: RunStatus,
    *,
    planned: int,
    succeeded: int,
    failed: int,
    skipped: int,
    routed: int = 0,
    prefiltered: int = 0,
    charts_drafted: int = 0,
    route_ms: int | None = None,
) -> RunRecord:
    hour = f"{n * 6:02d}"
    return RunRecord(
        run_id=f"{date}-{n}",
        n=n,
        started_at=f"{date}T{hour}:00:00Z",
        completed_at=f"{date}T{hour}:20:00Z",
        status=status,
        commit_sha=FIXTURE_SHA,
        runner="canary",
        models=[
            ModelUse(
                role=ModelRole.SUMMARIZE,
                model_ref=ModelRef(
                    id="canary",
                    repo="canary/none",
                    file="canary.gguf",
                    quantisation="Q4_K_M",
                ),
            )
        ],
        items_planned=planned,
        items_succeeded=succeeded,
        items_failed=failed,
        items_skipped=skipped,
        items_routed=routed,
        items_prefiltered=prefiltered,
        charts_drafted=charts_drafted,
        route_ms=route_ms,
        site_bytes=_site_bytes(date),
        site_files=4,
    )


def manifest(target: Path, published: int) -> RunManifest:
    """Three runs of one day, one of each colour the console can paint.

    The counts are consistent with the digest this file also writes: only run 1
    added items. Run 2 found nothing new and skipped everything it planned. Run
    3 broke. A fixture that claimed a later run succeeded on items the digest
    does not carry would make the two files disagree about the same day.

    Run 1 also carries the router's own counts, so the console's Charts table
    has one day with real arithmetic under it and nineteen quiet days with none.
    They are consistent with the digest too: the router reached all eight
    published items, posted five and answered three from their own numbers, and
    of its two chart drafts one is the chart the day publishes. The other died
    in the checks that run after the model answers, which is the gap the table
    exists to show.
    """
    day = RunManifest(
        version=RunManifest.schema_version(),
        date=DATE,
        runs=[
            # Green: everything planned was published.
            _record(
                DATE,
                1,
                RunStatus.COMPLETED,
                planned=published,
                succeeded=published,
                failed=0,
                skipped=0,
                routed=5,
                prefiltered=3,
                charts_drafted=2,
                route_ms=264_000,
            ),
            # Amber: nothing was attempted. Every candidate was already published.
            _record(DATE, 2, RunStatus.COMPLETED, planned=4, succeeded=0, failed=0, skipped=4),
            # Red: the run failed and added nothing.
            _record(DATE, 3, RunStatus.FAILED, planned=5, succeeded=0, failed=5, skipped=0),
        ],
    )
    write_atomic(day_dir(target, DATE) / "run.json", day.to_json())
    return day


def earlier_days() -> list[str]:
    """Every quiet day before the attack day, oldest first."""
    latest = calendar_date.fromisoformat(DATE)
    return [
        (latest - timedelta(days=HISTORY_DAYS - offset)).isoformat()
        for offset in range(HISTORY_DAYS)
    ]


def quiet_day(target: Path, date: str) -> None:
    """A day that ran, published nothing, and still wrote both files.

    It carries no items on purpose. One hostile day is the fixture; copying its
    markup nineteen times would only make the browser suite slower without
    asking the page a new question.

    One completed run that attempted nothing paints amber, which is the correct
    reading of a day the pipeline found no new article on.
    """
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=date,
        generated_at=f"{date}T06:00:00Z",
        partial=False,
        items_planned=0,
        items_failed=0,
        retention_window_months=-1,
        runs=[DigestRunRef(n=1, at=f"{date}T06:00:00Z", items_added=0)],
        verticals=[],
        items=[],
    )
    write_atomic(day_dir(target, date) / "digest.json", day.to_json())
    runs = RunManifest(
        version=RunManifest.schema_version(),
        date=date,
        runs=[_record(date, 1, RunStatus.COMPLETED, planned=0, succeeded=0, failed=0, skipped=0)],
    )
    write_atomic(day_dir(target, date) / "run.json", runs.to_json())


def _health(
    date: str,
    n: int,
    feed: str,
    outcome: FetchOutcome,
    *,
    status: int | None = None,
    items: int = 0,
    detail: str | None = None,
) -> FeedHealthRow:
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=f"{date}-{n}",
        date=date,
        feed_id=feed,
        checked_at=f"{date}T{n * 6:02d}:01:00Z",
        outcome=outcome,
        status=status,
        items=items,
        detail=detail,
    )


def health(state: Path) -> int:
    """One feed of each kind the console has to tell apart.

    Two dates, because a feed is rested after five failures and a single day of
    runs cannot reach five. The health ledger really does span a month, so this
    is the shape of the thing, not a trick to reach a number.
    """
    rows: list[FeedHealthRow] = []
    for date in (YESTERDAY, DATE):
        for n in (1, 2, 3):
            rows += [
                # Answers every time. Healthy, so the console never names it.
                _health(date, n, "canary-steady", FetchOutcome.OK, status=200, items=7),
                # Keeps timing out. Past the quarantine count by the second day.
                _health(
                    date,
                    n,
                    "canary-flaky",
                    FetchOutcome.TRANSIENT,
                    status=503,
                    detail="read timed out after 20 s",
                ),
                # Said no in robots.txt. Not a failure - honouring it is the job.
                _health(date, n, "canary-polite", FetchOutcome.ROBOTS_DENIED, status=200),
                # Never asked, so it can neither pass nor fail.
                _health(date, n, "canary-quiet", FetchOutcome.SKIPPED),
            ]
    # Answered, but with nothing. The same cost to the digest as a refusal.
    rows += [_health(DATE, n, "canary-empty", FetchOutcome.OK, status=200, items=0) for n in (2, 3)]
    rows.append(
        _health(DATE, 1, "canary-empty", FetchOutcome.OK, status=200, items=4),
    )
    # Gone for good.
    rows.append(
        _health(DATE, 1, "canary-gone", FetchOutcome.PERMANENT, status=404, detail="not found"),
    )

    for date in (YESTERDAY, DATE):
        append_health(state, date, [row for row in rows if row.date == date])
    return len(rows)


def _fixture_digest(*parts: str) -> str:
    """A stable stand-in for a field a real run fills with a real digest."""
    return hashlib.sha256("|".join(("canary", *parts)).encode("utf-8")).hexdigest()


def _scorer_version(evaluation: EvaluationConfig) -> str:
    """Spelled by the function the pipeline spells it with, and named `canary`.

    Borrowing the real scorer's id would put a measurement in the ledger that no
    model made, and every row after it would be uninterpretable.
    """
    return metrics.scorer_version(
        scorer_id="canary",
        scorer_revision=FIXTURE_SHA,
        weights_sha256=FIXTURE_SHA,
        evaluation=evaluation,
    )


def _eval_row(item: DigestItem, measured: _Measured, evaluation: EvaluationConfig) -> EvalRow:
    """One ledger row, with every derivable column derived rather than typed."""
    delta = round(measured.hhem - measured.hhem_full, _DELTA_PLACES)
    return EvalRow(
        version=EvalRow.schema_version(),
        date=DATE,
        # Run 1 is the run the manifest says added the items, so it is the run
        # that had anything to score.
        run_id=f"{DATE}-1",
        item_id=item.item_id,
        url_key=derive_url_key(item.source_url),
        source_url=item.source_url,
        title=item.title,
        vertical=item.vertical,
        model_id="canary",
        attempt=1,
        hhem=measured.hhem,
        hhem_full=measured.hhem_full,
        hhem_delta=delta,
        truncation_flagged=was_cut(measured),
        coverage=measured.coverage,
        # Summary words over source words, which is the whole of what
        # `metrics.compression` computes - done on the counts because a fixture
        # day has counts and no article behind them.
        compression=round(measured.summary_words / measured.source_words, _DELTA_PLACES),
        extractiveness=_EXTRACTIVENESS,
        verbatim_run=_VERBATIM_RUN,
        unsupported_numbers=measured.unsupported_numbers,
        hedge_dropped=measured.hedge_dropped,
        evidential_density=_EVIDENTIAL_DENSITY,
        speculative_density=_SPECULATIVE_DENSITY,
        extraction_suspect=False,
        band=item.band,
        source_word_count=measured.source_words if measured.full_length_known else None,
        source_seen_word_count=seen_words(measured),
        summary_word_count=measured.summary_words,
        pipeline_fingerprint=_fixture_digest("pipeline", DATE),
        output_digest=_fixture_digest("summary", item.item_id),
        source_digest=_fixture_digest("premise", item.item_id),
        determinism_violation=False,
        scorer_version=_scorer_version(evaluation),
        scored_at=f"{DATE}T06:12:00Z",
        score_ms=measured.score_ms,
    )


def score_rows(items: Sequence[DigestItem], evaluation: EvaluationConfig) -> list[EvalRow]:
    """The day's measurements, one row per published item.

    The band is read off the published item rather than re-derived here, so the
    ledger and the digest can only ever say the same thing about an item.
    """
    return [
        _eval_row(item, measured, evaluation)
        for item, measured in zip(items, SCORED, strict=True)
    ]


def scores(state: Path, items: Sequence[DigestItem], evaluation: EvaluationConfig) -> int:
    """Append the day's rows through the writer the pipeline appends with.

    Not a CSV written by hand: the contract validates every field, the writer
    owns the column order and the header check, and a column added to `EvalRow`
    lands here without this file being told about it.
    """
    return writer.append(state, score_rows(items, evaluation))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("backend/var/canary/digest"))
    parser.add_argument("--state", type=Path, default=Path("backend/var/canary/state"))
    args = parser.parse_args()
    # The ledgers under `--state` are append-only, so a second local run stacks
    # another copy of every row on the first. `canary-gone` is written once on
    # purpose - one permanent failure, well under the quarantine count - and by
    # the fifth run it has five and the console marks it rested. The browser
    # suite then fails against a fixture nobody edited, on a developer machine,
    # while CI stays green because its `backend/var/` is empty every time.
    # Clearing here makes the canary day a function of this file rather than of
    # how many times somebody has run it.
    if args.state.exists():
        shutil.rmtree(args.state)

    evaluation = config.load().app.evaluation
    quiet = earlier_days()
    for date in quiet:
        quiet_day(args.out, date)
    day = build(args.out, evaluation)
    runs = manifest(args.out, len(day.items))
    checks = health(args.state)
    scored = scores(args.state, day.items, evaluation)
    # Every writer of a committed day payload owes its month a rebuild
    # (docs/architecture/publishing/layout.md). The archive browses this tree in
    # the browser suite, so without the rebuild it would show days and no
    # stories - and the suite would pass on a page a reader cannot use.
    index_root = args.out.parent / "assist" / "index"
    months = sorted({month_of(date) for date in [*quiet, DATE]})
    indexed = [
        rebuild_search_index(digest_root=args.out, index_root=index_root, month=month)
        for month in months
    ]
    digest = hashlib.sha256(day.to_json().encode("utf-8")).hexdigest()[:12]
    visuals = sum(1 for item in day.items if item.visual is not None)
    print(f"canary day {DATE}: {len(day.items)} items, {visuals} visuals, payload {digest}")
    print(f"wrote {(day_dir(args.out, DATE) / 'digest.json').as_posix()}")
    print(f"wrote {(day_dir(args.out, DATE) / 'run.json').as_posix()}: {len(runs.runs)} runs")
    print(f"wrote {len(quiet)} quiet days, {quiet[0]} to {quiet[-1]}")
    print(f"wrote {args.state.as_posix()}/feed-health: {checks} feed results")
    print(f"wrote {writer.ledger_path(args.state, DATE).as_posix()}: {scored} scored items")
    print(
        f"wrote {index_root.as_posix()}: {len(indexed)} month(s), "
        f"{sum(len(index.entries) for index in indexed)} entries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
