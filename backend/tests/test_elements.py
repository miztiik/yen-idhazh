"""The candidate pass: every quantity, and the characters that prove each one.

The oracle is one comparison and it is asserted over every element the pass
emits: `article.text[span_start:span_end] == span_excerpt`. It runs over the
five committed injection canaries and the three captured pages - eight bounded
fixtures, none of which a run appends to (Rule #12) - because a span that only
holds on a hand-written string proves the string, not the pass.

The second half of the oracle is that the candidate table is not the
deduplicated fact list. An article stating one figure in two periods keeps both
here and collapses to one in `visual_planner.numeric_facts`, and that
difference is the whole reason this pass exists.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Final

import pytest
import test_canaries as canaries
from conftest import CONFIG_DIR, FIXTURES_DIR
from pydantic import ValidationError

from idhazh import config, extract
from idhazh.contracts.app_config import ElementsConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_text_digest, derive_url_key
from idhazh.contracts.element import Element, ElementKind, ElementTable, Extractor
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.taxonomy import SourceTier
from idhazh.elements import Candidates, element_table, quantity_elements
from idhazh.fetch import FetchResult
from idhazh.visual_planner import numeric_facts

APP: Final = config.load(CONFIG_DIR).app
ELEMENTS: Final = APP.elements
PAGES: Final = sorted((FIXTURES_DIR / "pages").glob("*.html"))

#: One figure, two periods. The article a trend chart exists for, and the one
#: `numeric_facts` is right to collapse and this pass is wrong to.
TWO_PERIODS: Final = (
    "Revenue reached 40 percent growth in 2024. "
    "It held at 40 percent growth in 2025, the company said."
)


def article_of(page: bytes, url: str) -> Article:
    """A real page through the real extractor and the real sanitizer (Rule #7)."""
    item = PlannedItem(
        item_id="probe-01",
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="probe",
        tier=SourceTier.INSTITUTION,
        vertical="probe",
        rank_score=0.0,
        title="probe",
    )
    return extract.to_article(
        item,
        FetchResult(outcome=FetchOutcome.OK, status=200, body=page),
        config=APP.extract,
        fetched_at="2026-08-27T00:00:00Z",
    )


def canary_article(canary: canaries.Canary) -> Article:
    body = "\n".join(
        f"<p>{html.escape(block)}</p>" for block in canary.raw_text.split("\n\n") if block.strip()
    )
    page = (
        f"<!DOCTYPE html><html><head><title>{html.escape(canary.raw_title)}</title></head>"
        f"<body><article>{body}</article></body></html>"
    )
    return article_of(page.encode("utf-8"), canary.source_url)


def page_article(path: Path) -> Article:
    return article_of(path.read_bytes(), f"https://probe.example/{path.name}")


def kept(text: str) -> list[Element]:
    return quantity_elements(text, limit=ELEMENTS.max_per_article).elements


def one(text: str) -> Element:
    found = kept(text)
    assert len(found) == 1, f"expected one quantity, got {[e.span_excerpt for e in found]}"
    return found[0]


# --- The Oracle: the characters prove it -----------------------------------


@pytest.mark.parametrize("canary", canaries.ALL, ids=lambda c: c.name)
def test_every_span_re_slices_to_its_own_excerpt_on_a_canary(canary: canaries.Canary) -> None:
    article = canary_article(canary)
    text = article.text or ""
    table = element_table(article, config=ELEMENTS)
    for element in table.elements:
        assert text[element.span_start : element.span_end] == element.span_excerpt


@pytest.mark.parametrize("path", PAGES, ids=lambda p: p.name)
def test_every_span_re_slices_to_its_own_excerpt_on_a_captured_page(path: Path) -> None:
    article = page_article(path)
    text = article.text or ""
    table = element_table(article, config=ELEMENTS)
    for element in table.elements:
        assert text[element.span_start : element.span_end] == element.span_excerpt


def test_the_corpus_the_oracle_runs_over_actually_carries_quantities() -> None:
    """The counter-oracle. A pass that emits nothing satisfies a re-slice trivially."""
    emitted = 0
    for canary in canaries.ALL:
        emitted += len(element_table(canary_article(canary), config=ELEMENTS).elements)
    for path in PAGES:
        emitted += len(element_table(page_article(path), config=ELEMENTS).elements)
    assert emitted == 17, "the eight bounded fixtures carried 17 quantities on 2026-09-08"


# --- The Oracle: this is a candidate set, not the fact list -----------------


def test_one_figure_in_two_periods_survives_twice() -> None:
    """Decision 2. The repeat IS the series, and a trend chart is what it is for."""
    excerpts = [element.span_excerpt for element in kept(TWO_PERIODS)]
    assert excerpts.count("40 percent") == 2
    assert [str(fact.value) for fact in numeric_facts(TWO_PERIODS)] == ["40"]


def test_the_two_repeats_are_told_apart_by_where_they_sit() -> None:
    """Two identical excerpts are two elements because their spans differ."""
    repeats = [e for e in kept(TWO_PERIODS) if e.span_excerpt == "40 percent"]
    assert [e.sentence_index for e in repeats] == [0, 1]
    assert len({e.element_id for e in repeats}) == 2


@pytest.mark.parametrize(
    ("text", "excerpts"),
    [
        ("There were 2 and then 1 more.", ["2", "1"]),
        ("The rule takes effect in 2027.", ["2027"]),
    ],
)
def test_the_pass_keeps_what_the_planner_is_right_to_drop(text: str, excerpts: list[str]) -> None:
    """A magnitude at or below two, and a bare year. Both are candidates here."""
    assert [element.span_excerpt for element in kept(text)] == excerpts
    assert numeric_facts(text) == [], "the planner's own reader still drops them"


def test_numeric_facts_still_behaves_the_way_its_own_caller_needs() -> None:
    """Decision 4. This row adds a producer; it does not repair the old one.

    Both halves matter: the repeat still collapses, and `15 m` is still fifteen
    metres rather than fifteen million.
    """
    facts = numeric_facts("Output was 4,200 units. Again, 4200 units. The tower rose 15 m.")
    assert [(str(fact.value), fact.unit) for fact in facts] == [("4200", "unit"), ("15", "m")]


# --- The count is taken before the cap -------------------------------------


def test_the_counter_holds_when_the_cap_bites() -> None:
    """Decision 3. A capped counter returns a plausible integer, which is the defect."""
    uncapped = quantity_elements(TWO_PERIODS, limit=ELEMENTS.max_per_article)
    capped = quantity_elements(TWO_PERIODS, limit=2)
    assert uncapped.found == capped.found == 4
    assert len(capped.elements) == 2


def test_the_cap_keeps_the_article_s_own_order() -> None:
    """It removes from the end, so what survives is what the article said first."""
    capped = quantity_elements(TWO_PERIODS, limit=2)
    assert [element.span_excerpt for element in capped.elements] == ["40 percent", "2024"]


def test_a_table_cannot_claim_it_kept_more_than_it_found() -> None:
    table = element_table(page_article(PAGES[0]), config=ELEMENTS)
    payload = table.model_dump(mode="json")
    payload["candidates_found"] = {"quantity": len(table.elements) - 1}
    with pytest.raises(ValidationError):
        ElementTable.model_validate(payload)


def test_a_table_that_counted_no_kind_at_all_is_refused() -> None:
    """The pair is the point: a kept element with no count is an uncountable table."""
    table = element_table(page_article(PAGES[0]), config=ELEMENTS)
    payload = table.model_dump(mode="json")
    payload["candidates_found"] = {}
    with pytest.raises(ValidationError):
        ElementTable.model_validate(payload)


def test_a_pass_that_found_more_than_it_kept_loads() -> None:
    """The cap biting is a normal table, not a broken one."""
    table = element_table(page_article(PAGES[0]), config=ElementsConfig(max_per_article=2))
    assert len(table.elements) == 2
    assert table.candidates_found[ElementKind.QUANTITY] > 2
    assert ElementTable.from_json(table.to_json()).candidates_found == table.candidates_found


# --- What one element says -------------------------------------------------


@pytest.mark.parametrize(
    ("text", "excerpt", "value", "unit"),
    [
        ("The plant produced 1,200 MW last year.", "1,200 MW", "1200", "mw"),
        ("It cost $4.5 billion to build.", "$4.5 billion", "4500000000", "$"),
        ("Costs fell 12 percent.", "12 percent", "12", "%"),
        ("Revenue reached 4.2 billion dollars.", "4.2 billion dollars", "4200000000", "dollar"),
        ("Temperatures fell -3 degrees.", "-3 degrees", "-3", "degree"),
        ("The rule takes effect in 2027.", "2027", "2027", None),
    ],
)
def test_a_quantity_reads_the_way_the_article_wrote_it(
    text: str, excerpt: str, value: str, unit: str | None
) -> None:
    element = one(text)
    assert element.span_excerpt == excerpt
    assert text[element.span_start : element.span_end] == excerpt
    assert (element.value, element.unit) == (value, unit)
    assert element.kind is ElementKind.QUANTITY
    assert element.extractor is Extractor.REGEX


def test_a_magnitude_word_and_a_plain_figure_compare_as_the_same_string() -> None:
    """The value is text so it can be compared, which it cannot be in two spellings."""
    assert one("It cost 4.2 billion.").value == one("It cost 4,200,000,000.").value


def test_a_percent_span_ends_at_the_magnitude_word() -> None:
    """`40 percent of` is not an excerpt, because `of` is not part of the reading."""
    element = one("It took 40 percent of the fleet.")
    assert element.span_excerpt == "40 percent"
    assert element.unit == "%"


def test_a_stop_listed_word_reads_as_no_unit_and_drops_nothing() -> None:
    element = one("The count reached 12 and held.")
    assert (element.span_excerpt, element.unit) == ("12", None)


@pytest.mark.parametrize(
    ("text", "indices"),
    [("One is 5 kg. Two is 6 kg. Three is 7 kg.", [0, 1, 2]), ("5 kg and 6 kg.", [0, 0])],
)
def test_sentence_index_counts_from_the_start_of_the_article(
    text: str, indices: list[int]
) -> None:
    assert [element.sentence_index for element in kept(text)] == indices


# --- Fetched bytes are data, and a pattern over them can match anything -----


def test_a_six_hundred_character_word_is_not_a_unit() -> None:
    """Rule #11. The element lands with its span; only the unit reading is refused."""
    element = one("It measured 12 " + "a" * 400 + " across.")
    assert (element.span_excerpt, element.unit) == ("12", None)


def test_a_digit_run_too_wide_to_write_is_not_a_candidate() -> None:
    """A serial number is not a quantity, and it is not counted as one either."""
    found = quantity_elements(
        "The hash was " + "9" * 80 + " and the count was 12 units.",
        limit=ELEMENTS.max_per_article,
    )
    assert found == Candidates([found.elements[0]], 1)
    assert found.elements[0].span_excerpt == "12 units"


def test_an_article_with_no_text_yields_an_empty_table() -> None:
    """Degrade, do not fail: a failed extraction is still a readable table."""
    article = article_of(b"<html><body></body></html>", "https://empty.example/")
    table = element_table(article, config=ELEMENTS)
    assert table.elements == []
    assert table.candidates_found == {ElementKind.QUANTITY: 0}
    assert table.source_text_length == 0


# --- The table names the text its spans index ------------------------------


def test_the_table_carries_the_hash_of_the_string_the_spans_index() -> None:
    article = page_article(PAGES[0])
    table = element_table(article, config=ELEMENTS)
    assert table.source_text_hash == derive_text_digest(article.text or "")
    assert table.source_text_length == len(article.text or "")
    assert table.url_key == derive_url_key(article.canonical_url)


def test_a_table_round_trips_through_its_own_contract() -> None:
    table = element_table(page_article(PAGES[0]), config=ELEMENTS)
    assert ElementTable.from_json(table.to_json()).to_json() == table.to_json()
