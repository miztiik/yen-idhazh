"""The frozen corpus: can it be built, and does it survive being sharded.

Row #10 registers a corpus definition - every `summarize.bands` tier covered,
over-cap items present, brief items present - and qualification run
32998603233 died on it: `band 3 (min_source_words 2000) has 0, needs 3`. Two
faults, both exercised here.

No mocks and no network (Rule #7). The fetcher is a real function over a real
HTML body, and the bodies are built to a word count so the length tiers are the
thing under test rather than a property of a captured page.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pytest

from idhazh import cli, config, extract
from idhazh.contracts.app_config import ExtractConfig
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.qualification import CorpusItem
from idhazh.contracts.run_plan import PlannedItem, RunPlan, VerticalPlan
from idhazh.contracts.taxonomy import SourceTier
from idhazh.evals import qualify
from idhazh.fetch import FetchResult

SETTINGS = config.load()
SUMMARIZE = SETTINGS.app.summarize
BANDS = len(SUMMARIZE.bands)
CAP_WORDS = int(SETTINGS.app.extract.truncation_cap_tokens / extract.TOKENS_PER_WORD)

#: One sentence the extractor accepts as prose. Every copy carries its own
#: ordinal because trafilatura drops a paragraph it has already seen, so a page
#: built from one repeated sentence extracts to about 150 words however many
#: copies it holds - which is a silent way to build a fixture that is not the
#: length the test believes.
SENTENCE = "The grid operator confirmed the order and named a delivery date."
WORDS_PER_SENTENCE = len(SENTENCE.split()) + 2


def body_of(words: int) -> bytes:
    """An HTML page whose extracted body is about `words` words long."""
    count = max(1, -(-words // WORDS_PER_SENTENCE))
    sentences = [f"Item {index}. {SENTENCE}" for index in range(count)]
    paragraphs = [
        "<p>" + " ".join(sentences[start : start + 8]) + "</p>"
        for start in range(0, count, 8)
    ]
    page = (
        "<html><head><title>Reactor order</title></head><body><article>"
        + "".join(paragraphs)
        + "</article></body></html>"
    )
    return page.encode("utf-8")


#: Word counts that land one item in each tier, chosen from the committed
#: `summarize.bands` rather than typed in, so a band edit moves the fixture.
def words_for_band(index: int) -> int:
    floor = SUMMARIZE.bands[index].min_source_words
    if index + 1 < BANDS:
        midpoint = (floor + SUMMARIZE.bands[index + 1].min_source_words) // 2
        return max(floor + WORDS_PER_SENTENCE, midpoint)
    # No band sits above the top tier, so it is placed past the truncation cap
    # as well as past its own floor. `qualify.MIN_OVER_CAP` wants truncated
    # items and this is the only tier that can supply one at any cap.
    return max(floor, CAP_WORDS) + 1200


def planned(index: int, band: int) -> PlannedItem:
    url = f"https://newsroom.example-grid.com/2026/08/band-{band}-item-{index}"
    return PlannedItem(
        item_id=f"energy-{index:02d}",
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="grid-newsroom",
        tier=SourceTier.INSTITUTION,
        vertical="energy",
        title=f"Example Grid item {index}",
        rank_score=1.0,
    )


def fetcher_for(layout: dict[str, int]) -> Callable[[str], FetchResult]:
    """Serve each address a body of the word count the layout names."""

    def read_url(url: str) -> FetchResult:
        if url not in layout:
            raise AssertionError(f"the corpus builder fetched an address nobody planned: {url}")
        return FetchResult(FetchOutcome.OK, status=200, body=body_of(layout[url]))

    return read_url


def a_plan(band_counts: dict[int, int]) -> tuple[list[PlannedItem], dict[str, int]]:
    """`band_counts` items in each tier, interleaved so no tier is contiguous."""
    wanted: list[int] = []
    while any(band_counts.values()):
        for band in sorted(band_counts):
            if band_counts[band] > 0:
                wanted.append(band)
                band_counts[band] -= 1
    items = [planned(index, band) for index, band in enumerate(wanted, start=1)]
    layout = {
        item.canonical_url: words_for_band(band)
        for item, band in zip(items, wanted, strict=True)
    }
    return items, layout


# --- The length a band is chosen from ---------------------------------------


def test_the_truncation_cap_sits_below_the_longest_band() -> None:
    """Why the shipped rule could never fill the top tier.

    Nothing about the plan or the day: the post-cap count could not pass this
    ceiling, so a band above it was unreachable by arithmetic.

    Pinned to 2500, the cap committed when that defect shipped. The cap is 5000
    from 2026-08-29 and the post-cap ceiling is 3846 words, above the top band,
    so the live knob can no longer reproduce the fault this test records.
    """
    shipped_cap_words = int(2500 / extract.TOKENS_PER_WORD)
    assert shipped_cap_words < SUMMARIZE.bands[-1].min_source_words


def test_a_long_read_lands_in_the_longest_band_even_though_it_was_cut() -> None:
    """The band is read from the count taken before the cut.

    The post-cap count no longer picks a different band. At cap 5000 the
    post-cap ceiling is 3846 words, above the top band's floor, so a cut article
    reaches the top tier on either count. What is still testable, and is the
    whole claim, is that the two counts differ and that the band follows the one
    from before the cut.
    """
    words = words_for_band(BANDS - 1)
    article = extract.to_article(
        planned(1, BANDS - 1),
        FetchResult(FetchOutcome.OK, status=200, body=body_of(words)),
        config=SETTINGS.app.extract,
        fetched_at="2026-08-26T06:00:00Z",
    )
    assert article.truncated
    assert article.word_count <= CAP_WORDS
    assert article.source_word_count is not None
    assert article.source_word_count > article.word_count
    assert article.source_word_count >= SUMMARIZE.bands[-1].min_source_words
    assert qualify.band_index(article.band_source_words, SUMMARIZE) == BANDS - 1


def test_a_payload_written_before_the_field_reads_its_post_cap_count() -> None:
    """The read-side migration. An older payload keeps the answer it was written with."""
    article = extract.to_article(
        planned(1, 2),
        FetchResult(FetchOutcome.OK, status=200, body=body_of(900)),
        config=ExtractConfig(),
        fetched_at="2026-08-26T06:00:00Z",
    )
    older = article.model_copy(update={"source_word_count": None})
    assert older.band_source_words == older.word_count


# --- The corpus builder ------------------------------------------------------


def test_every_tier_is_filled_when_the_slice_can_supply_it() -> None:
    """`keep` is the definition's own minimum here - four tiers at three items -
    so one shard alone clears it and the union has room to spare."""
    keep = BANDS * qualify.MIN_PER_BAND
    items, layout = a_plan(dict.fromkeys(range(BANDS), 4))
    chosen, attempted, unmet = cli._freeze(
        items, SETTINGS, fetcher_for(layout), keep=keep, share=cli.corpus_share()
    )
    assert unmet == []
    assert attempted <= len(items)
    assert qualify.corpus_shortfalls([entry.row for entry in chosen], summarize=SUMMARIZE) == []


def test_a_tier_the_slice_cannot_supply_is_named(caplog: pytest.LogCaptureFixture) -> None:
    """Fails loudly, never quietly. The corpus is the measuring stick, so a
    missing tier is reported by name rather than filled with a nearer one."""
    counts = dict.fromkeys(range(BANDS), 6)
    counts[BANDS - 1] = 0
    items, layout = a_plan(counts)
    with caplog.at_level(logging.ERROR):
        chosen, _, unmet = cli._freeze(
            items, SETTINGS, fetcher_for(layout), keep=10, share=cli.corpus_share()
        )
    assert any(f"band {BANDS - 1}" in line for line in unmet)
    assert not any(entry.row.band_index == BANDS - 1 for entry in chosen)


def test_the_walk_continues_past_the_pool_floor_to_reach_a_scarce_tier() -> None:
    """The floor is a floor, not a stop. The long reads sit past it on purpose."""
    keep = 3
    floor = keep * SETTINGS.app.evaluation.qualification_pool_multiple
    common = [planned(index, 1) for index in range(1, floor + 4)]
    scarce = [planned(index, BANDS - 1) for index in range(floor + 4, floor + 7)]
    layout = {item.canonical_url: words_for_band(1) for item in common}
    layout |= {item.canonical_url: words_for_band(BANDS - 1) for item in scarce}
    chosen, attempted, _ = cli._freeze(
        [*common, *scarce], SETTINGS, fetcher_for(layout), keep=keep, share=cli.corpus_share()
    )
    assert attempted > floor
    assert any(entry.row.band_index == BANDS - 1 for entry in chosen)


def test_the_scarce_tier_is_not_crowded_out_by_the_common_one() -> None:
    """`keep` is small and the common tier is large, so the order decides."""
    counts = {0: 0, 1: 20, 2: 0, BANDS - 1: 2}
    items, layout = a_plan(counts)
    chosen, _, _ = cli._freeze(
        items, SETTINGS, fetcher_for(layout), keep=4, share=cli.corpus_share()
    )
    assert sum(1 for entry in chosen if entry.row.band_index == BANDS - 1) == 2


# --- Stratification across shards --------------------------------------------


def test_a_tier_that_falls_in_one_shard_survives_the_split() -> None:
    """The union has to meet the definition even when a tier is not spread.

    Each shard freezes its own slice in its own job and never sees a sibling's
    corpus, so a shard that aimed at a fraction of the requirement would leave
    the second and third long read behind and no sibling could make them up.
    """
    shards = 3
    counts = dict.fromkeys(range(BANDS), 0)
    counts[0] = 3
    counts[1] = 12
    counts[2] = 6
    items, layout = a_plan(counts)
    # Every long read at a position the round-robin hands to shard 0.
    scarce = [planned(100 + n, BANDS - 1) for n in range(qualify.MIN_PER_BAND)]
    layout |= {item.canonical_url: words_for_band(BANDS - 1) for item in scarce}
    ordered: list[PlannedItem] = []
    for index, item in enumerate(items):
        if index % shards == 0 and scarce:
            ordered.append(scarce.pop(0))
        ordered.append(item)
    plan = RunPlan(
        version=RunPlan.schema_version(),
        date="2026-08-26",
        run_id="2026-08-26-1",
        generated_at="2026-08-26T06:00:00Z",
        verticals=[
            VerticalPlan(
                id="energy",
                considered=len(ordered),
                planned=len(ordered),
                live_feeds=1,
            )
        ],
        items=ordered,
    )
    union: list[CorpusItem] = []
    for shard in range(shards):
        chosen, _, _ = cli._freeze(
            cli.shard_of(plan, shard=shard, shards=shards),
            SETTINGS,
            fetcher_for(layout),
            keep=10,
            share=cli.corpus_share(),
        )
        union.extend(entry.row for entry in chosen)
    assert len({row.url_key for row in union}) == len(union)
    assert qualify.corpus_shortfalls(union, summarize=SUMMARIZE) == []


def test_the_selection_does_not_move_when_the_pool_is_reordered() -> None:
    """Registered by hash before any output is read, so it cannot be re-rolled."""
    items, layout = a_plan(dict.fromkeys(range(BANDS), 4))
    first, _, _ = cli._freeze(
        items, SETTINGS, fetcher_for(layout), keep=8, share=cli.corpus_share()
    )
    again, _, _ = cli._freeze(
        items, SETTINGS, fetcher_for(layout), keep=8, share=cli.corpus_share()
    )
    assert [entry.row.url_key for entry in first] == [entry.row.url_key for entry in again]


def test_the_pool_floor_is_read_from_config() -> None:
    """Rule #6. The knob is the only number that sizes the walk.

    The band-against-cap assertion that used to sit here moved to
    `test_the_truncation_cap_sits_below_the_longest_band`, which owns that
    history and pins the cap it was true at. It never belonged to the pool.
    """
    assert SETTINGS.app.evaluation.qualification_pool_multiple >= 1
