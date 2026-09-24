"""The retrieval eval: does archive search find the right thing, and how sure are we?

Two kinds of test live here and they answer different questions.

The pure-function tests fix the arithmetic: the ranking order, the capped
denominator, the split between a miss and an absence. They use vectors built by
hand, so they say the same thing on any corpus and on any day.

The measurement runs the real encoder over the committed archive and reports a
number with its spread. It is a gate on the ranking - `assist.recall_min` - and
a report on everything else. Nothing here touches the network: the encoder is
committed under `frontend/static/` and the archive is committed under
`frontend/public/` (Guardrail #7).

**Every read here carries a cover.** The gate reads the days through
`assist.eval_corpus_through`, because nothing it asks can be answered by a day
the pin excludes. The index comparison reads the shard that pin names. The knob
check and the answer-key placement below read a directory listing and open no
shard at all. The one question none of them fits - does the index name every
published item - is `backend/utilities/measure_retrieval.py`.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.embed import Embedder
from idhazh.evals import retrieval
from idhazh.evals.retrieval import (
    Corpus,
    CorpusItem,
    LabelledQuery,
    QueryOutcome,
    RetrievalReport,
)

pytestmark = pytest.mark.slow


def unit(*values: float) -> tuple[float, ...]:
    length = math.sqrt(sum(value * value for value in values)) or 1.0
    return tuple(value / length for value in values)


def item(date: str, item_id: str, vector: tuple[float, ...] | None) -> CorpusItem:
    return CorpusItem(date=date, item_id=item_id, entities=(), vector=vector)


@pytest.fixture(scope="session")
def config() -> AppConfig:
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))


# --------------------------------------------------------------------------
# The arithmetic
# --------------------------------------------------------------------------


def test_the_floor_removes_a_result_rather_than_scoring_it_low() -> None:
    corpus = Corpus(
        items=(
            item("2026-08-21", "ai-01", unit(1.0, 0.0)),
            item("2026-08-21", "ai-02", unit(0.2, 1.0)),
        )
    )
    query = list(unit(1.0, 0.0))
    assert [hit.item_id for hit in retrieval.rank(corpus, query, limit=10, floor=0.0)] == [
        "ai-01",
        "ai-02",
    ]
    assert [hit.item_id for hit in retrieval.rank(corpus, query, limit=10, floor=0.5)] == ["ai-01"]


def test_ties_break_by_newest_day_then_by_item_id() -> None:
    """The browser's order, and the reason two identical searches agree."""
    vector = unit(1.0, 0.0)
    corpus = Corpus(
        items=(
            item("2026-08-21", "ai-02", vector),
            item("2026-08-22", "ai-09", vector),
            item("2026-08-22", "ai-01", vector),
        )
    )
    hits = retrieval.rank(corpus, list(vector), limit=10, floor=0.0)
    assert [(hit.date, hit.item_id) for hit in hits] == [
        ("2026-08-22", "ai-01"),
        ("2026-08-22", "ai-09"),
        ("2026-08-21", "ai-02"),
    ]


def test_the_limit_cuts_the_list_after_the_sort_not_before() -> None:
    corpus = Corpus(
        items=tuple(
            item("2026-08-21", f"ai-{index:02d}", unit(1.0, index / 100))
            for index in range(1, 21)
        )
    )
    hits = retrieval.rank(corpus, list(unit(1.0, 0.0)), limit=3, floor=0.0)
    assert [hit.item_id for hit in hits] == ["ai-01", "ai-02", "ai-03"]


def test_an_item_with_no_vector_is_never_ranked() -> None:
    corpus = Corpus(
        items=(
            item("2026-08-21", "ai-01", None),
            item("2026-08-21", "ai-02", unit(1.0, 0.0)),
        )
    )
    hits = retrieval.rank(corpus, list(unit(1.0, 0.0)), limit=10, floor=0.0)
    assert [hit.item_id for hit in hits] == ["ai-02"]


def test_recall_denominator_is_capped_at_the_slots_that_exist() -> None:
    """Twenty right answers cannot fit in ten slots, so ten of ten is a pass.

    Without the cap the metric would report a retriever that filled every slot
    correctly as 0.5, and the score would move when a labeller was generous.
    """
    outcome = QueryOutcome(
        query_id="q", gold=20, gold_with_vector=20, found=10, slots=10, reciprocal_rank=1.0
    )
    assert outcome.recall == 1.0
    assert outcome.recall_uncapped == 0.5


def test_an_unembedded_answer_is_an_absence_and_not_a_ranking_miss() -> None:
    outcome = QueryOutcome(
        query_id="q", gold=4, gold_with_vector=1, found=1, slots=10, reciprocal_rank=1.0
    )
    assert outcome.unreachable == 3
    assert outcome.recall == 0.25
    assert outcome.recall_reachable == 1.0


def test_a_query_with_no_embedded_answer_is_excluded_from_the_ranking_number() -> None:
    """It stays in the reader-facing number, because a reader gets nothing back."""
    report = RetrievalReport(
        outcomes=(
            QueryOutcome(
                query_id="answerable",
                gold=2,
                gold_with_vector=2,
                found=2,
                slots=10,
                reciprocal_rank=1.0,
            ),
            QueryOutcome(
                query_id="unembedded",
                gold=2,
                gold_with_vector=0,
                found=0,
                slots=10,
                reciprocal_rank=0.0,
            ),
        ),
        corpus_items=10,
        corpus_searchable=2,
        result_limit=10,
        similarity_floor=0.35,
    )
    assert report.n == 2
    assert report.recall == 0.5
    assert report.recall_reachable == 1.0
    assert report.unanswerable == 1
    assert report.gold_coverage == 0.5


def test_the_standard_error_needs_more_than_one_query() -> None:
    row = QueryOutcome(
        query_id="q", gold=1, gold_with_vector=1, found=1, slots=10, reciprocal_rank=1.0
    )
    single = RetrievalReport(
        outcomes=(row,),
        corpus_items=1,
        corpus_searchable=1,
        result_limit=10,
        similarity_floor=0.0,
    )
    assert single.standard_error == 0.0


def test_the_unjudged_share_is_counted_over_filled_slots_not_over_slots() -> None:
    """A query the floor cut short did not fail to judge the slots it never used."""
    report = RetrievalReport(
        outcomes=(
            QueryOutcome(
                query_id="full",
                gold=4,
                gold_with_vector=4,
                found=4,
                slots=10,
                reciprocal_rank=1.0,
                unlabelled=6,
            ),
            QueryOutcome(
                query_id="cut-short",
                gold=2,
                gold_with_vector=2,
                found=2,
                slots=10,
                reciprocal_rank=1.0,
                unlabelled=0,
            ),
        ),
        corpus_items=100,
        corpus_searchable=100,
        result_limit=10,
        similarity_floor=0.35,
    )
    assert report.unlabelled_share == 0.5


def test_the_entity_tier_needs_a_slug_on_enough_items() -> None:
    corpus = Corpus(
        items=(
            CorpusItem("2026-08-21", "ai-01", ("acme",), unit(1.0, 0.0)),
            CorpusItem("2026-08-21", "ai-02", ("acme", "beta"), unit(1.0, 0.1)),
            CorpusItem("2026-08-22", "ai-03", ("acme",), unit(1.0, 0.2)),
        )
    )
    queries = retrieval.entity_queries(corpus, min_items=3)
    assert [query.id for query in queries] == ["entity-acme"]
    assert queries[0].query == "acme"
    assert len(queries[0].relevant) == 3
    assert retrieval.entity_queries(corpus, min_items=4) == ()


def test_a_day_written_by_another_encoder_contributes_no_vectors(tmp_path: Path) -> None:
    """A wrong-space vector decodes perfectly and every score it makes is noise."""
    day = tmp_path / "frontend/public/digest/2026/08/21"
    day.mkdir(parents=True)
    (day / "digest.json").write_text(
        '{"date": "2026-08-21", "items": [{"item_id": "ai-01", "entities": []}], '
        '"embeddings": {"model_id": "some-other-encoder", "dtype": "int8", '
        '"dimensions": 384, "vectors": {"ai-01": "AAA="}}}',
        encoding="utf-8",
    )
    corpus = retrieval.load_corpus(tmp_path)
    assert len(corpus.items) == 1
    assert corpus.searchable == ()
    assert corpus.coverage == 0.0


def write_day(root: Path, date: str, body: str) -> None:
    year, month, day = date.split("-")
    directory = root / f"frontend/public/digest/{year}/{month}/{day}"
    directory.mkdir(parents=True)
    (directory / "digest.json").write_text(body, encoding="utf-8")


def day_payload(date: str) -> str:
    return f'{{"date": "{date}", "items": [{{"item_id": "ai-01", "entities": []}}]}}'


def test_the_pin_cuts_the_read_rather_than_the_rows_it_returns(tmp_path: Path) -> None:
    """The bound has to hold when a later day lands, and cost nothing when it does.

    Three days, one of them past the pin. The pinned read returns two and the
    unpinned read returns three, so the filter is doing the work rather than the
    fixture happening to be small. Then the later day is replaced by bytes no
    JSON parser accepts: the pinned read still returns two, which it could only
    do by never opening that file, and the unpinned read fails on it.
    """
    for date in ("2026-08-25", "2026-08-26", "2026-08-27"):
        write_day(tmp_path, date, day_payload(date))

    assert len(retrieval.load_corpus(tmp_path, through="2026-08-26").items) == 2
    assert len(retrieval.load_corpus(tmp_path).items) == 3

    later = tmp_path / "frontend/public/digest/2026/08/27/digest.json"
    later.write_text("not json at all", encoding="utf-8")
    assert len(retrieval.load_corpus(tmp_path, through="2026-08-26").items) == 2
    with pytest.raises(json.JSONDecodeError):
        retrieval.load_corpus(tmp_path)


def test_the_pin_drops_a_month_shard_before_the_shard_is_opened(tmp_path: Path) -> None:
    """The index bound, proved the same way, and then narrowed to the day.

    A month shard is coarser than the pin, so the stem test alone keeps days the
    pin excludes. The rows are narrowed afterwards - which is only cheap because
    the stem test already refused every later shard.
    """
    directory = tmp_path / retrieval.INDEX_RELDIR
    directory.mkdir(parents=True)
    (directory / "2026-08.json").write_text(
        '{"entries": [{"date": "2026-08-26", "item_id": "ai-01", "vector": null}, '
        '{"date": "2026-08-27", "item_id": "ai-02", "vector": null}]}',
        encoding="utf-8",
    )
    (directory / "2026-09.json").write_text("not json at all", encoding="utf-8")

    pinned = retrieval.load_index_corpus(tmp_path, through="2026-08-26")
    assert [row.item_id for row in pinned.items] == ["ai-01"]
    with pytest.raises(json.JSONDecodeError):
        retrieval.load_index_corpus(tmp_path)


def test_the_months_on_file_are_read_off_their_own_names(tmp_path: Path) -> None:
    """Which months exist is a listing. Opening one to find out would be the cost."""
    assert retrieval.index_months(tmp_path) == ()
    directory = tmp_path / retrieval.INDEX_RELDIR
    directory.mkdir(parents=True)
    for stem in ("2026-09", "2026-08"):
        (directory / f"{stem}.json").write_text("not json at all", encoding="utf-8")
    assert retrieval.index_months(tmp_path) == ("2026-08", "2026-09")


# --------------------------------------------------------------------------
# The query set
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def corpus(config: AppConfig) -> Corpus:
    """The scored set, cut by the pin rather than filtered after the read.

    Cover: `assist.eval_corpus_through`. Nothing here asks a question a day past
    the pin can answer - the gate is pinned, the labels close on the same day,
    and the floor is measured against the set the gate scores - so opening the
    rest of the archive would cost more every week and change no number.
    """
    return retrieval.load_corpus(REPO_ROOT, through=config.assist.eval_corpus_through)


@pytest.fixture(scope="session")
def queries() -> tuple[LabelledQuery, ...]:
    return retrieval.load_queries(REPO_ROOT)


def test_the_query_set_is_an_instrument_rather_than_a_wiring_check(
    queries: tuple[LabelledQuery, ...],
) -> None:
    """At least fifty queries, or the bar cannot see a ten-point regression.

    At n=50 the standard error at recall 0.8 is 0.057. At n=5 it is 0.18, which
    is why the five-query Playwright fixture is a wiring check and stays one.
    """
    assert len(queries) >= 50
    assert len({query.id for query in queries}) == len(queries)


def test_every_query_has_more_than_one_right_answer(
    queries: tuple[LabelledQuery, ...],
) -> None:
    """Single-gold labelling makes a working system read as broken on a topic."""
    single = [query.id for query in queries if len(query.relevant) < 2]
    assert single == []


def test_every_labelled_answer_is_still_in_the_archive(
    corpus: Corpus, queries: tuple[LabelledQuery, ...]
) -> None:
    """A vanished gold item is its own failure, not a slow drop in recall.

    Published days are meant to be immutable. If one is not, the recall number
    falls for a reason that has nothing to do with retrieval, so this asks the
    question separately and answers it by name.
    """
    published = {item.address for item in corpus.items}
    missing = sorted(
        f"{query.id}: {date}/{item_id}"
        for query in queries
        for (date, item_id) in query.relevant
        if (date, item_id) not in published
    )
    assert missing == []


def test_the_frozen_answer_key_sits_inside_the_pin_the_gate_scores(
    queries: tuple[LabelledQuery, ...], config: AppConfig
) -> None:
    """Where the frozen key sits in the calendar: against the pin, and the window.

    `assist.eval_corpus_through` bounds the corpus the gate scores. Move the pin
    earlier and the judged answers past it stop being scorable, so the gate
    quietly measures a smaller key against an unchanged bar. The membership test
    above goes red on the same edit, but it names a vanished gold item, which is
    the wrong cause. This one names the pin. Measured 2026-09-23: all 297 judged
    answers fall between 2026-08-21 and 2026-08-26, against a pin of 2026-08-26.

    The printed line is the other half and carries no bar. A reader's tab reads
    the newest `assist.search_months` shards, and the key was written in one
    sitting that nobody has extended, so the overlap between the two only falls
    as the archive moves. Measured 2026-09-23 it is 0 of 297, because the key
    closes in August and the window is September - which is where the key sits
    in the calendar, not a search failure. A bar on it would gate the merge on
    the publishing date.

    Both halves are fixed cost. The months come off their own file names, so
    this opens the query fixture and nothing else. Whether `search_min_days`
    pulls one more shard in cannot be known without opening one, so the line
    names the floor rather than guessing at it.
    """
    judged = [(query.id, date, item_id) for query in queries for (date, item_id) in query.relevant]

    stems = retrieval.index_months(REPO_ROOT)
    if stems:
        days = sorted(date for (_, date, _) in judged)
        window = sorted(stems[-config.assist.search_months :])
        reachable = [row for row in judged if row[1][:7] in set(window)]
        print(
            f"\nanswer key against the reader's window: {len(reachable)} of {len(judged)} "
            f"judged answers fall in {', '.join(window)}, the newest "
            f"{config.assist.search_months} of {len(stems)} months on file, and one more "
            f"month is read when the newest holds under {config.assist.search_min_days} "
            f"days. The key runs {days[0]} to {days[-1]}, so this is where the key sits "
            "in the calendar and not a search failure."
        )

    pin = config.assist.eval_corpus_through
    if pin is None:
        pytest.skip("the gate reads every published day, so no answer can fall outside it")
    outside = sorted(
        f"{query_id}: {date}/{item_id}" for (query_id, date, item_id) in judged if date > pin
    )
    assert outside == [], (
        f"assist.eval_corpus_through is {pin} and {len(outside)} of {len(judged)} judged "
        "answers are published after it, so the gate cannot score them: " + ", ".join(outside[:5])
    )


def test_the_pin_holds_the_competitor_set_still() -> None:
    """`through` drops what was published later and keeps the boundary day."""
    corpus = Corpus(
        items=(
            item("2026-08-25", "a", unit(1.0, 0.0)),
            item("2026-08-26", "b", unit(1.0, 0.0)),
            item("2026-08-27", "c", unit(1.0, 0.0)),
        )
    )
    assert [row.item_id for row in corpus.through("2026-08-26").items] == ["a", "b"]
    assert corpus.through(None) is corpus


# --------------------------------------------------------------------------
# The measurement
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def embedded(queries: tuple[LabelledQuery, ...]) -> list[list[float]]:
    """One forward pass per query, shared by every measurement below."""
    return retrieval.embed_queries(REPO_ROOT, queries)


@pytest.fixture(scope="session")
def report(
    corpus: Corpus,
    queries: tuple[LabelledQuery, ...],
    embedded: list[list[float]],
    config: AppConfig,
) -> RetrievalReport:
    """The gated measurement, scored against the corpus the labellers saw."""
    return retrieval.evaluate(
        corpus,
        queries,
        embedded,
        limit=config.assist.result_limit,
        floor=config.assist.similarity_floor,
    )


def test_the_ranking_clears_its_bar(report: RetrievalReport, config: AppConfig) -> None:
    """recall@10 over the answers that carry a vector. The single gate metric.

    Coverage is deliberately out of it. An item the pipeline never embedded is
    invisible at every threshold, so counting it here would fail this gate for a
    defect that belongs to the embedding stage. The reader-facing number, which
    does count it, is printed beside this one on every run.

    The corpus is pinned to `assist.eval_corpus_through`. Unpinned, this gate
    scores the ranking and the publishing rate at once, and the second term is
    unbounded - see the field description.
    """
    print("\ngated  " + report.summary())
    assert report.recall_reachable >= config.assist.recall_min, (
        f"reachable recall@{report.result_limit} is {report.recall_reachable:.3f} "
        f"+/- {report.standard_error_reachable:.3f} over {len(report.answerable)} answerable "
        f"queries, below the {config.assist.recall_min} bar, measured over the "
        f"{report.corpus_items} items published through "
        f"{config.assist.eval_corpus_through}. Weakest: "
        + ", ".join(
            f"{row.query_id} {row.recall_reachable:.2f}"
            for row in sorted(report.answerable, key=lambda row: row.recall_reachable)[:5]
        )
    )


def test_the_measurement_is_precise_enough_to_see_a_regression(
    report: RetrievalReport,
) -> None:
    """An instrument whose spread is wider than the effect cannot see the effect."""
    assert report.n >= 50
    assert report.standard_error <= 0.08


def test_the_reader_facing_number_is_reported_with_its_coverage(
    report: RetrievalReport,
) -> None:
    """No assertion on the level - this measures it, and moving it is a separate job.

    What is asserted is that the two failures stay separable. If every gold item
    were reachable the distinction would collapse and the instrument would stop
    being able to say which failure it is looking at.
    """
    assert 0.0 <= report.recall <= report.recall_reachable
    assert report.gold_coverage <= 1.0
    assert report.unanswerable + len(report.answerable) == report.n


# --------------------------------------------------------------------------
# The index is what a reader actually searches
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def index_corpus(config: AppConfig) -> Corpus:
    """The pinned set again, read the way a reader's tab reads it.

    Cover: `assist.eval_corpus_through`, matched against the shard stem, so the
    comparison below opens the month the pin names and no later one.
    """
    return retrieval.load_index_corpus(REPO_ROOT, through=config.assist.eval_corpus_through)


@pytest.fixture(scope="session")
def index_report(
    index_corpus: Corpus,
    queries: tuple[LabelledQuery, ...],
    embedded: list[list[float]],
    config: AppConfig,
) -> RetrievalReport:
    """Pinned to the same day as `report`, because this case is a comparison.

    The question is what moving to the index cost, so the corpus has to be held
    still on both sides. Pin one case and the gap reads as an index defect when
    it is only the days between the pin and today.
    """
    return retrieval.evaluate(
        index_corpus,
        queries,
        embedded,
        limit=config.assist.result_limit,
        floor=config.assist.similarity_floor,
    )


def test_moving_search_to_the_index_cost_no_recall(
    report: RetrievalReport, index_report: RetrievalReport
) -> None:
    """The load-bearing half of this row's Oracle.

    A page that got lighter while search got worse is a regression, and the only
    thing that can tell the difference is this number. Both cases use the same
    queries, the same labels, the same ranking and the same embedded queries -
    the only difference is whether the vectors came out of the day payloads the
    page used to inline or out of the month shard it now fetches.

    One standard error is the band, because that is the precision the instrument
    has at n=60. Anything tighter would fail on arithmetic noise; anything wider
    would miss the effect it is here to catch.
    """
    if not index_report.outcomes or index_report.corpus_items == 0:
        pytest.skip("no committed month index in this checkout")

    print("\nday payloads: " + report.summary())
    print("month index:  " + index_report.summary())

    drift = abs(index_report.recall - report.recall)
    assert drift <= report.standard_error, (
        f"the index lost information the day payloads carried: recall@"
        f"{report.result_limit} is {index_report.recall:.3f} off the index against "
        f"{report.recall:.3f} off the payloads, a gap of {drift:.3f} against one "
        f"standard error of {report.standard_error:.3f}"
    )


def test_a_reader_only_searches_the_months_the_knob_names(config: AppConfig) -> None:
    """`assist.search_months` and `assist.search_min_days` are what a tab reads.

    The scope buys download seconds rather than compute seconds - one month is a
    2.53 MB vector file and the ranking over it is 74 to 159 milliseconds - so
    the knobs are the only thing standing between a reader and a fourteen-second
    wait at three months. The floor is the other half: a calendar shard is not a
    window, so on the first of a month `search_months` alone reaches one day.

    The set of months on file comes from a listing rather than a load. The
    question is which months exist, and a shard's own name answers it.
    """
    every = set(retrieval.index_months(REPO_ROOT))
    if not every:
        pytest.skip("no committed month index in this checkout")

    scoped = retrieval.load_index_corpus(
        REPO_ROOT,
        months=config.assist.search_months,
        min_days=config.assist.search_min_days,
    )
    assert scoped.items, "the configured scope reads no month at all"

    months = {item.date[:7] for item in scoped.items}
    # One extra shard when the floor bites, and one only. Never more.
    assert len(months) <= config.assist.search_months + 1
    assert months <= every
    # Newest first, so the scope always holds the months a reader would expect.
    assert months == set(sorted(every, reverse=True)[: len(months)])
    # And the floor is met, unless there is no older shard left to meet it with.
    days = {item.date for item in scoped.items if item.vector is not None}
    assert len(days) >= config.assist.search_min_days or months == every, (
        f"the scope covers {len(days)} days against a floor of "
        f"{config.assist.search_min_days}, with {len(every) - len(months)} shards unread"
    )


def test_the_floor_lets_the_empty_state_fire(corpus: Corpus, config: AppConfig) -> None:
    """A question the archive cannot answer must return nothing.

    'Nothing in the archive is close to that' is a promise, and a floor below the
    same-domain noise makes it one the selector cannot keep. At the floor this
    replaced, 0.20, every one of these returned a full list.

    A probe is only a probe while it stays off-domain, and the corpus decides
    that, not the person who wrote it. 'restoring a 1960s mechanical wristwatch
    movement' was one of these until 2026-08-26, when the vector backfill made
    the archive's smartwatch items reachable; it then matched a Pebble Time 2
    review at 0.413 and a Garmin deal at 0.360, which are wristwatches and not
    noise. It is retired here rather than deleted quietly, and replaced by a
    probe with more room: the four below scored 0.235, 0.295, 0.258 and 0.194
    against this corpus on 2026-08-26, so the tightest has 0.055 of margin.
    """
    probes = [
        "recipe for sourdough starter using rye flour",
        "baroque counterpoint in the fugues of Buxtehude",
        "grammar of the Basque ergative case",
        "hand-stitching a leather saddle",
    ]
    embedder = Embedder(REPO_ROOT)
    if not embedder.available:
        pytest.skip("the committed encoder is not present")
    embedder.load()
    answered = {
        text: retrieval.rank(
            corpus,
            vector,
            limit=config.assist.result_limit,
            floor=config.assist.similarity_floor,
        )
        for text, vector in zip(probes, embedder.encode(probes), strict=True)
    }
    noisy = {text: len(hits) for text, hits in answered.items() if hits}
    assert noisy == {}, f"the floor {config.assist.similarity_floor} let noise through: {noisy}"


def test_the_floor_sits_above_the_measured_noise(
    corpus: Corpus, queries: tuple[LabelledQuery, ...], config: AppConfig
) -> None:
    """The floor's real justification, asserted on the corpus rather than argued.

    The probe test above can be weakened by choosing gentle probes. This one
    cannot: it scores every real question against every real item that does not
    answer it, and requires the floor to clear the 95th percentile of that.
    Measured 2026-08-26 over 126,843 pairs the p95 is 0.2716, so 0.35 has room;
    if the archive ever grows noisier than the selector, this says so first.
    """
    embedded = retrieval.embed_queries(REPO_ROOT, queries)
    noise = retrieval.null_scores(corpus, queries, embedded)
    assert len(noise) > 10_000
    p95 = retrieval.quantile(noise, 0.95)
    assert config.assist.similarity_floor >= p95, (
        f"the floor {config.assist.similarity_floor} is under the p95 of same-domain "
        f"noise ({p95:.4f} over {len(noise)} pairs), so the empty state cannot fire"
    )


def test_the_report_says_how_much_of_the_list_nobody_judged(
    report: RetrievalReport,
) -> None:
    """The gate metric is a lower bound, and this is the size of the gap.

    Every slot held by an unjudged item counts as a wrong answer. Some of them
    are right answers: the labels were pooled from an index that could see 44.5
    percent of the corpus, and 55.5 percent of the unlabelled slot-holders were
    unembedded on labelling day (2026-08-26). No bar is set on this number - it
    is printed so that nobody reads the recall figure as the truth, and it falls
    when the labels are completed.
    """
    print(f"\nunjudged slot share {report.unlabelled_share:.1%}")
    assert 0.0 <= report.unlabelled_share <= 1.0
    assert report.unlabelled_share > 0.0, (
        "every filled slot is now a labelled answer - the label set has caught up "
        "with the corpus and the lower-bound caveat can come out of the docs"
    )


def test_the_entity_tier_builds_one_query_per_slug_that_clears_the_floor(corpus: Corpus) -> None:
    """Tier one: one query per entity slug carried by enough items, no labeller.

    Until 2026-08-26 this asserted the tier's own **emptiness**, because nothing
    wrote `entities` and the free tier had no slugs to work from. A
    deterministic tagger writes them now. No committed payload was rewritten, so
    the count climbs as new days land - which is exactly why this can no longer
    assert a number. It asserts the behaviour instead, and holds whether the
    corpus carries no slug or a hundred.
    """
    counts = Counter(slug for item in corpus.items for slug in item.entities)
    expected = sorted(slug for slug, carried in counts.items() if carried >= 3)
    queries = retrieval.entity_queries(corpus, min_items=3)

    assert [query.id for query in queries] == [f"entity-{slug}" for slug in expected]
    for query in queries:
        slug = query.id.removeprefix("entity-")
        assert len(query.relevant) >= 3, "a query below the floor must not be built"
        assert len(query.relevant) == counts[slug], "the relevant set is every item carrying it"
        assert query.query == slug.replace("-", " ")
