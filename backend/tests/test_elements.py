"""The candidate pass: every quantity and date, and the characters that prove each.

The oracle is one comparison and it is asserted over every element the pass
emits: `article.text[span_start:span_end] == span_excerpt`. It runs over the
five committed injection canaries and the four captured pages - nine bounded
fixtures, none of which a run appends to (Rule #12) - because a span that only
holds on a hand-written string proves the string, not the pass.

The second half of the oracle is that the candidate table is not the
deduplicated fact list. An article stating one figure in two periods keeps both
here and collapses to one in `visual_planner.numeric_facts`, and that
difference is the whole reason this pass exists.

Row 3 adds the third half. Two passes read the same bytes and both match
`2026`, so a bare year is claimed as a date and never as a quantity, and no two
elements of one table hold the same character. That is checked pair by pair on
the same nine fixtures, with a counter-oracle that they carry both kinds -
without it, a pass emitting nothing makes every pair disjoint.

Row 4 asks the oracle the other way round. The nine fixtures prove a span holds
against the text it was cut from; the run at the end proves what happens when it
does not - one item degrades with a recorded reason and its four siblings still
publish. That run is built rather than read off a committed day, because a run
whose size grows every four hours is not a fixture (Rule #12).
"""

from __future__ import annotations

import html
from collections import Counter
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
from idhazh.elements import Candidates, date_elements, element_table, quantity_elements
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

#: One built run for row 4's oracle: five articles, one span each, so a span
#: that stops pointing where it did degrades exactly one of them.
RUN_BODIES: Final = (
    "The plant produced 1,200 MW last year.",
    "It cost $4.5 billion to build.",
    "The rule takes effect on 15 March 2026.",
    "Costs fell 12 percent over the period.",
    "Output reached 4.2 billion units.",
)


def article_of(page: bytes, url: str, *, item_id: str = "probe-01") -> Article:
    """A real page through the real extractor and the real sanitizer (Rule #7)."""
    item = PlannedItem(
        item_id=item_id,
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


def prose_article(body: str, *, at: str = "prose", item_id: str = "probe-01") -> Article:
    """One paragraph through the real extractor, so a built case yields a real table."""
    page = (
        "<!DOCTYPE html><html><head><title>probe</title></head>"
        f"<body><article><p>{html.escape(body)}</p></article></body></html>"
    )
    return article_of(page.encode("utf-8"), f"https://probe.example/{at}", item_id=item_id)


def prose_run(*bodies: str) -> list[Article]:
    """One built run: several articles, each at its own address.

    Built rather than read off a committed day, because the oracle needs a run
    whose size does not change when a pipeline run appends one (Rule #12).
    """
    return [
        prose_article(body, at=f"prose/{index:02d}", item_id=f"probe-{index:02d}")
        for index, body in enumerate(bodies, start=1)
    ]


def reading_of(body: str) -> list[tuple[str, str, str | None]]:
    """What the table says one sentence holds: each kind, its slice and its value."""
    table = element_table(prose_article(body), config=ELEMENTS)
    return [(e.kind.value, e.span_excerpt, e.value) for e in table.elements]


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
    assert emitted == 17, "the nine bounded fixtures carried 17 elements on 2026-09-08"


# --- The Oracle: two passes never hold the same character ------------------


def overlaps(left: Element, right: Element) -> bool:
    """Half-open ranges share a character when each starts before the other ends."""
    return left.span_start < right.span_end and right.span_start < left.span_end


def bounded_articles() -> list[tuple[str, Article]]:
    """The nine fixtures no run appends to: five canaries and four captured pages."""
    articles = [(canary.name, canary_article(canary)) for canary in canaries.ALL]
    return articles + [(path.name, page_article(path)) for path in PAGES]


def bounded_tables() -> list[tuple[str, ElementTable]]:
    return [(name, element_table(article, config=ELEMENTS)) for name, article in bounded_articles()]


def test_a_bare_year_is_claimed_as_a_date_and_never_as_a_quantity() -> None:
    """Row 3's oracle. Both patterns match `2026`, and only one reading is true.

    The number pattern still matches it - `quantity_elements` is unchanged - and
    the table is where the two claims are settled.
    """
    assert reading_of("The rule takes effect in 2026.") == [("date", "2026", "2026")]


def test_no_two_elements_of_one_table_hold_the_same_character() -> None:
    """Every pair of spans on the nine bounded fixtures, checked for overlap.

    Pairwise is quadratic in one article's elements and bounded by
    `elements.max_per_article`, so it cannot grow with the archive (Rule #12).
    The densest of these fixtures carries seven elements, which is 21 pairs.
    """
    for name, table in bounded_tables():
        for index, left in enumerate(table.elements):
            for right in table.elements[index + 1 :]:
                assert not overlaps(left, right), (
                    f"{name}: {left.element_id} and {right.element_id} both hold "
                    f"characters {max(left.span_start, right.span_start)} onwards"
                )


def test_the_bounded_fixtures_carry_both_kinds_so_the_pair_check_can_fail() -> None:
    """The counter-oracle. One pass emitting nothing makes every pair disjoint."""
    kinds = Counter(element.kind for _, table in bounded_tables() for element in table.elements)
    assert kinds == {ElementKind.QUANTITY: 9, ElementKind.DATE: 8}, (
        "the nine bounded fixtures carried 9 quantities and 8 years on 2026-09-08"
    )


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
    """A magnitude at or below two, and a bare year. Both are candidates here.

    The number pattern is unchanged by row 3 and still matches a bare year. The
    table is where that claim loses to the date pass, not this function.
    """
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


# --- What one date says ----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "excerpt", "value"),
    [
        ("Filed 2026-03-15 by the agency.", "2026-03-15", "2026-03-15"),
        ("On 15 March 2026 the plant opened.", "15 March 2026", "2026-03-15"),
        ("Published on March 15, 2026 at the earliest.", "March 15, 2026", "2026-03-15"),
        ("Filed 15th Jan. 2026 in Delhi.", "15th Jan. 2026", "2026-01-15"),
        ("The rule takes effect in 2026.", "2026", "2026"),
    ],
)
def test_a_date_reads_the_way_the_article_wrote_it(text: str, excerpt: str, value: str) -> None:
    """Four written shapes and a bare year. The span keeps the article's spelling."""
    found = date_elements(text, limit=ELEMENTS.max_per_article).elements
    assert len(found) == 1, f"expected one date, got {[e.span_excerpt for e in found]}"
    element = found[0]
    assert element.span_excerpt == excerpt
    assert text[element.span_start : element.span_end] == excerpt
    assert (element.value, element.unit) == (value, None)
    assert element.kind is ElementKind.DATE
    assert element.extractor is Extractor.REGEX


@pytest.mark.parametrize(
    "text",
    [
        "It cost $2026 to fix.",
        "The reading was 2026.5 units.",
        "The plant produced 1,200 MW last year.",
        "It happened in 1899, before records.",
        "The serial was 2101 on the plate.",
    ],
)
def test_a_shape_the_allow_list_does_not_hold_is_not_a_date(text: str) -> None:
    """A price, a decimal, a thousands separator, and a year either side of the range."""
    assert date_elements(text, limit=ELEMENTS.max_per_article) == Candidates([], 0)


def test_a_slash_date_gives_up_its_day_and_month_and_keeps_its_year() -> None:
    """`03/04/2026` is 3 April in one country and 4 March in another.

    Choosing between them states a date the article did not (decision 4), so
    neither is read. The year is unambiguous and it is still claimed.
    """
    found = date_elements("Filed 03/04/2026 in Delhi.", limit=256)
    assert [(e.span_excerpt, e.value) for e in found.elements] == [("2026", "2026")]


def test_a_day_the_calendar_does_not_have_is_not_a_date() -> None:
    """Degrade, do not fail. The match is refused and the digits stay quantities."""
    assert date_elements("February 31, 2026 is not a day.", limit=256) == Candidates([], 0)
    assert [excerpt for _, excerpt, _ in reading_of("February 31, 2026 is not a day.")] == [
        "31",
        "2026",
    ]


def test_a_relative_date_is_never_resolved() -> None:
    """Decision 4. It resolves against a publication date the article never wrote."""
    assert date_elements("It closed three years ago, last month.", limit=256).found == 0


def test_the_date_counter_holds_when_the_cap_bites() -> None:
    """The same argument as the quantity counter: a capped count returns a plausible integer."""
    text = "It ran from 2024 to 2025 and on to 2026."
    uncapped = date_elements(text, limit=ELEMENTS.max_per_article)
    capped = date_elements(text, limit=2)
    assert uncapped.found == capped.found == 3
    assert [element.span_excerpt for element in capped.elements] == ["2024", "2025"]


# --- Two passes, one stretch of characters ---------------------------------


@pytest.mark.parametrize(
    ("text", "kept_readings"),
    [
        # The spans are equal.
        ("The rule takes effect in 2026.", [("date", "2026")]),
        # The quantity's span contains the date's: `2026 hit` reads `hit` as a unit.
        ("Revenue in 2026 hit $4.5 billion.", [("date", "2026"), ("quantity", "$4.5 billion")]),
        # The date's span contains the quantity's: `15 March` reads a month as a unit.
        ("On 15 March 2026 the plant opened.", [("date", "15 March 2026")]),
        # Neither contains the other: the date runs 4-18 and the quantity 14-27.
        ("The March 15, 2026 deadline slipped.", [("date", "March 15, 2026")]),
        # No shared character at all, so both survive.
        (
            "March 2026 revenue of $4.5 billion beat it.",
            [("date", "2026"), ("quantity", "$4.5 billion")],
        ),
    ],
)
def test_a_date_takes_the_characters_from_a_quantity_it_touches(
    text: str, kept_readings: list[tuple[str, str]]
) -> None:
    """The overlap rule, on all four ways two spans can meet plus the case they do not."""
    assert [(kind, excerpt) for kind, excerpt, _ in reading_of(text)] == kept_readings


def test_the_quantity_pass_still_matched_what_the_rule_then_dropped() -> None:
    """`candidates_found` counts what each pass matched, so the drop stays visible.

    Count it after the rule instead and a date pattern that swallowed every
    figure would report an article with no figures in it.
    """
    table = element_table(prose_article("Revenue in 2026 hit $4.5 billion."), config=ELEMENTS)
    assert table.candidates_found == {ElementKind.QUANTITY: 2, ElementKind.DATE: 1}
    assert Counter(element.kind for element in table.elements) == {
        ElementKind.QUANTITY: 1,
        ElementKind.DATE: 1,
    }


def test_a_four_digit_count_in_the_year_range_is_read_as_a_year() -> None:
    """What the rule costs, stated rather than implied.

    A real count written without a thousands separator loses to the year
    reading. The trade is deliberate: a year kept as a quantity is a bar 1,994
    units high, and a reader cannot see that it is wrong.
    """
    assert reading_of("The survey drew 1994 responses.") == [("date", "1994", "1994")]
    assert reading_of("The survey drew 1,994 responses.") == [
        ("quantity", "1,994 responses", "1994")
    ]


def test_two_dates_side_by_side_keep_their_own_characters() -> None:
    """One pattern over one string cannot return overlapping matches, and it does not."""
    readings = reading_of("Filed 2026-03-15 and again 2026-04-01 that spring.")
    assert [excerpt for _, excerpt, _ in readings] == ["2026-03-15", "2026-04-01"]


def test_the_settled_table_stays_in_the_article_s_own_order() -> None:
    """The contract requires it, and the rule sorts by precedence before it re-sorts."""
    table = element_table(page_article(PAGES[0]), config=ELEMENTS)
    starts = [element.span_start for element in table.elements]
    assert starts == sorted(starts)


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
    assert table.candidates_found == {ElementKind.QUANTITY: 0, ElementKind.DATE: 0}
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


# --- The Oracle: a span that no longer points where it did -----------------
#
# Row 4. The shape checks that an excerpt is as wide as its span, which refuses
# a cleaned string and cannot refuse a wrong one - the text is not in the
# payload, so the shape has nothing to cut. `span_drift` cuts it, and the two
# callers dispose of the answer differently: the producer raises, a consumer
# degrades that one item.


def test_every_bounded_fixture_re_slices_against_the_text_it_was_built_from() -> None:
    """The invariant at rest, on the nine fixtures no run appends to (Rule #12)."""
    for name, article in bounded_articles():
        table = element_table(article, config=ELEMENTS)
        assert table.span_drift(article.text or "") is None, name


def test_one_item_whose_text_moved_degrades_and_the_rest_of_the_run_publishes() -> None:
    """The oracle, in the shape the consumer loop has: check, record, continue.

    One article's text has moved by a single character and four have not. The
    reason names the first span that stopped pointing where it did, and it is
    recorded against that item alone - a corpus-wide refusal over one drifted
    span is the trade `CLAUDE.md` section 1a refuses.
    """
    run = prose_run(*RUN_BODIES)
    tables = [element_table(article, config=ELEMENTS) for article in run]
    held = [article.text or "" for article in run]
    moved = 2
    held[moved] = " " + held[moved]

    published: list[str] = []
    degraded: dict[str, str] = {}
    for table, text in zip(tables, held, strict=True):
        if (drift := table.span_drift(text)) is not None:
            degraded[table.item_id] = drift
            continue
        published.append(table.item_id)

    assert list(degraded) == [tables[moved].item_id]
    assert published == [table.item_id for index, table in enumerate(tables) if index != moved]
    assert degraded[tables[moved].item_id].startswith(tables[moved].elements[0].element_id)


def test_the_run_the_oracle_uses_carries_a_span_in_every_item() -> None:
    """The counter-oracle. An item with no span cannot drift, so it would publish
    for the wrong reason and the oracle would still read green."""
    tables = [element_table(article, config=ELEMENTS) for article in prose_run(*RUN_BODIES)]
    assert [len(table.elements) for table in tables] == [1, 1, 1, 1, 1]


def test_text_that_grew_after_every_span_is_not_drift() -> None:
    """What tells a re-slice apart from a hash comparison, and why it is a re-slice.

    The text moved, so the hash the table carries no longer matches it. Not one
    span moved with it, so the table is still true of this text and degrading
    the item would cost a reader a chart for nothing.
    """
    article = prose_article("The plant produced 1,200 MW in 2026.")
    table = element_table(article, config=ELEMENTS)
    grown = (article.text or "") + " The operator added a paragraph afterwards."
    assert derive_text_digest(grown) != table.source_text_hash
    assert table.span_drift(grown) is None


def test_a_table_with_no_span_has_nothing_to_drift() -> None:
    """A table of no facts is true of any text, so there is no item to degrade."""
    article = prose_article("The operator said the plant opened on schedule.")
    table = element_table(article, config=ELEMENTS)
    assert table.elements == []
    assert table.span_drift("a different article entirely") is None


def test_elements_cut_from_one_text_and_a_table_hashed_over_another_is_caught() -> None:
    """The write-time failure the shape cannot see, built the way it would happen.

    Both passes are public and take any string, so a caller can hand the pre-cap
    body to one and `Article.text` to the table. Every field validates - the
    excerpts are the right width and no span runs past the length - and the
    re-slice is the only thing that says the two describe different strings.
    """
    article = prose_article("The plant produced 1,200 MW in 2026.")
    text = article.text or ""
    pre_cap = "Reuters - " + text
    found = quantity_elements(text, limit=ELEMENTS.max_per_article)
    mismatched = ElementTable(
        version=ElementTable.schema_version(),
        item_id=article.item_id,
        url_key=derive_url_key(article.canonical_url),
        canonical_url=article.canonical_url,
        source_text_hash=derive_text_digest(pre_cap),
        source_text_length=len(pre_cap),
        elements=found.elements,
        candidates_found={ElementKind.QUANTITY: found.found},
    )
    assert mismatched.span_drift(pre_cap) is not None
    assert mismatched.span_drift(text) is None, "the elements are true of the text they were cut from"
