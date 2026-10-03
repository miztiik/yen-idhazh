"""The retrieval eval: proving the arithmetic, never measuring the archive.

Every test here fixes behaviour: the ranking order, the capped denominator, the
split between a miss and an absence, and which exact days or month shards a
named read opens. Vectors are built by hand and archives are built under
`tmp_path`, so every test here says the same thing on any corpus and on any
day - none of them opens the committed archive, and none of them runs the
real encoder.

**Whether archive search is actually any GOOD never lands here.** That is a
quality measurement on published data, not a behaviour this code can get
wrong on its own (CLAUDE.md section 13 rule 2), so it is an operator's job,
run by hand with `backend/utilities/measure_retrieval.py`, and it is never
gated in a test run. The Playwright suite's own five-query fixture stays the
wiring check it always was.

The static query fixture under `tests/fixtures/` is read here - a named file
of fixed size, not the archive - because its own shape (at least fifty
queries, each with more than one right answer) is the arithmetic the
instrument's precision depends on, not a measurement of the archive's content.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from idhazh.evals import retrieval
from idhazh.evals.retrieval import (
    Corpus,
    CorpusItem,
    LabelledQuery,
    QueryOutcome,
    RetrievalReport,
)


def unit(*values: float) -> tuple[float, ...]:
    length = math.sqrt(sum(value * value for value in values)) or 1.0
    return tuple(value / length for value in values)


def item(date: str, item_id: str, vector: tuple[float, ...] | None) -> CorpusItem:
    return CorpusItem(date=date, item_id=item_id, entities=(), vector=vector)


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
    corpus = retrieval.load_corpus(tmp_path, days=["2026-08-21"])
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


def test_load_corpus_reads_exactly_the_named_days_and_no_other(tmp_path: Path) -> None:
    """Three days on disk; only the named ones are read, and an unnamed one is never opened.

    The unnamed day's `digest.json` is replaced by bytes no JSON parser accepts.
    Naming it would raise; leaving it unnamed must not - the only way to prove
    the loader never opened the file rather than merely ignoring its content. A
    named day with no file at all is skipped the same quiet way: an evaluation
    set can outlive the day it names.
    """
    for date in ("2026-08-25", "2026-08-26", "2026-08-27"):
        write_day(tmp_path, date, day_payload(date))

    assert len(retrieval.load_corpus(tmp_path, days=["2026-08-25", "2026-08-26"]).items) == 2
    assert len(retrieval.load_corpus(tmp_path, days=["2026-08-25", "2099-01-01"]).items) == 1

    later = tmp_path / "frontend/public/digest/2026/08/27/digest.json"
    later.write_text("not json at all", encoding="utf-8")
    assert len(retrieval.load_corpus(tmp_path, days=["2026-08-25", "2026-08-26"]).items) == 2
    with pytest.raises(json.JSONDecodeError):
        retrieval.load_corpus(tmp_path, days=["2026-08-27"])


def test_the_days_on_file_are_read_off_their_own_names(tmp_path: Path) -> None:
    """Which days exist is a listing off the path. Opening one to find out would be the cost."""
    assert retrieval.digest_days(tmp_path) == ()
    write_day(tmp_path, "2026-08-22", "not json at all")
    write_day(tmp_path, "2026-08-21", "not json at all")
    assert retrieval.digest_days(tmp_path) == ("2026-08-21", "2026-08-22")


def test_load_index_corpus_reads_exactly_the_named_months_and_no_other(tmp_path: Path) -> None:
    """Two shards on disk; only the named month is read, and the other is never opened.

    The unnamed shard is bytes no JSON parser accepts, so reading it would
    raise. A named month with no committed shard is skipped the same way a
    missing day is in `load_corpus`.
    """
    directory = tmp_path / retrieval.INDEX_RELDIR
    directory.mkdir(parents=True)
    (directory / "2026-08.json").write_text(
        '{"entries": [{"date": "2026-08-26", "item_id": "ai-01", "vector": null}, '
        '{"date": "2026-08-27", "item_id": "ai-02", "vector": null}]}',
        encoding="utf-8",
    )
    (directory / "2026-09.json").write_text("not json at all", encoding="utf-8")

    named = retrieval.load_index_corpus(tmp_path, months=["2026-08"])
    assert [row.item_id for row in named.items] == ["ai-01", "ai-02"]
    assert retrieval.load_index_corpus(tmp_path, months=["2026-07"]).items == ()
    with pytest.raises(json.JSONDecodeError):
        retrieval.load_index_corpus(tmp_path, months=["2026-09"])


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


# --------------------------------------------------------------------------
# The entity tier
# --------------------------------------------------------------------------


def test_the_entity_tier_builds_one_query_per_slug_that_clears_the_floor() -> None:
    """One query per entity slug carried by enough items, built generically.

    The real archive's entity counts shift with every publish, so the property
    asserted here is the one that has to hold regardless of which slugs clear
    the floor on any given day: built from a hand-made corpus rather than the
    committed archive, it says the same thing on any corpus.
    """
    corpus = Corpus(
        items=(
            CorpusItem("2026-08-21", "ai-01", ("acme", "beta"), unit(1.0, 0.0)),
            CorpusItem("2026-08-21", "ai-02", ("acme",), unit(1.0, 0.1)),
            CorpusItem("2026-08-22", "ai-03", ("acme", "beta"), unit(1.0, 0.2)),
            CorpusItem("2026-08-22", "ai-04", ("beta",), unit(1.0, 0.3)),
            CorpusItem("2026-08-23", "ai-05", ("gamma",), unit(1.0, 0.4)),
        )
    )
    counts = Counter(slug for item in corpus.items for slug in item.entities)
    expected = sorted(slug for slug, carried in counts.items() if carried >= 3)
    queries = retrieval.entity_queries(corpus, min_items=3)

    assert [query.id for query in queries] == [f"entity-{slug}" for slug in expected]
    for query in queries:
        slug = query.id.removeprefix("entity-")
        assert len(query.relevant) >= 3, "a query below the floor must not be built"
        assert len(query.relevant) == counts[slug], "the relevant set is every item carrying it"
        assert query.query == slug.replace("-", " ")
