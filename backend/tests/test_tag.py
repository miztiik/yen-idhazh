"""The tagger: the match rule, the trap it exists to avoid, and the wiring.

Unit tier for the matcher (a pure function over text), contract tier for the
vocabulary the committed config carries, integration tier for the article that
comes out of extract carrying its tags.
"""

from __future__ import annotations

from pathlib import Path

from conftest import CONFIG_DIR

from idhazh import config, tag
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.taxonomy import EventType, LensId, LifecycleStatus, SourceTier

TAXONOMY = config.load(CONFIG_DIR).taxonomy


# --- The match rule ---------------------------------------------------------


def test_a_term_matches_only_as_a_whole_word() -> None:
    """The trap this whole design exists to avoid.

    Measured 2026-08-26 over 1889 published items: letting `ai` match as a
    substring tags 88.2 percent of them, because it sits inside `said`,
    `remains` and `chair`. A filter that takes nine items in ten is not a
    filter.
    """
    vocabulary = {"ai-roi": ["ai"]}
    assert tag.tags(vocabulary, "he said it remains a chair") == []
    assert tag.tags(vocabulary, "the ai model shipped") == ["ai-roi"]


def test_a_term_is_matched_case_folded_and_through_punctuation() -> None:
    vocabulary = {"ai-roi": ["ai-roi"]}
    for written in ("AI-ROI", "ai roi", "AI/ROI", "ai, roi"):
        assert tag.tags(vocabulary, written) == ["ai-roi"], written


def test_a_multi_word_term_matches_only_in_order() -> None:
    vocabulary = {"cyber": ["data breach"]}
    assert tag.tags(vocabulary, "a data breach was disclosed") == ["cyber"]
    assert tag.tags(vocabulary, "breach of the data protection rules") == []


def test_nothing_is_derived_from_the_id_or_the_display_name() -> None:
    """A tag with no curated term is never assigned, whatever its id spells."""
    assert tag.tags({"markets": []}, "the markets fell and the market cap rose") == []


def test_the_tag_list_is_sorted_so_a_rerun_cannot_reorder_it() -> None:
    vocabulary = {"markets": ["shares"], "china": ["beijing"], "cyber": ["malware"]}
    assert tag.tags(vocabulary, "malware in beijing moved the shares") == [
        "china",
        "cyber",
        "markets",
    ]


def test_several_parts_are_read_as_one_document() -> None:
    vocabulary = {"cyber": ["data breach"]}
    assert tag.tags(vocabulary, "a data", "breach happened") == ["cyber"]
    assert tag.tags(vocabulary, None, "a data breach happened") == ["cyber"]


def test_an_absent_document_earns_no_tag() -> None:
    assert tag.tags({"china": ["beijing"]}, None, None) == []


# --- The committed vocabulary ------------------------------------------------


def test_every_lens_and_event_carries_terms() -> None:
    """An empty list is legal and silent, which is exactly how this shipped unwired."""
    assert [lens.id for lens in TAXONOMY.lenses if not lens.keywords] == []
    assert [event.id for event in TAXONOMY.events if not event.keywords] == []


def test_the_committed_terms_are_all_matchable() -> None:
    """A term of no word characters would match every document. None may exist."""
    for lens in TAXONOMY.lenses:
        assert len(tag.terms_of(lens.keywords)) == len(lens.keywords), lens.id
    for event in TAXONOMY.events:
        assert len(tag.terms_of(event.keywords)) == len(event.keywords), event.id


def test_no_committed_term_is_short_enough_to_match_inside_a_word() -> None:
    """Two characters is the contract floor; one would match most English prose."""
    terms = [term for lens in TAXONOMY.lenses for term in lens.keywords]
    terms += [term for event in TAXONOMY.events for term in event.keywords]
    assert [term for term in terms if len(term.strip()) < 2] == []


def test_a_retired_lens_stops_matching_but_keeps_its_tombstone() -> None:
    retired = TAXONOMY.model_copy(
        update={
            "lenses": [
                lens.model_copy(
                    update={"status": LifecycleStatus.RETIRED, "retired_on": "2026-08-26"}
                )
                if lens.id is LensId.CHINA
                else lens
                for lens in TAXONOMY.lenses
            ]
        }
    )
    assert LensId.CHINA not in retired.lens_terms()
    assert LensId.CHINA in {lens.id for lens in retired.lenses}


def test_the_vocabularies_only_ever_name_a_member_of_the_closed_enum() -> None:
    """Rule #11: a hostile page can win a tag we publish, never invent one."""
    assert set(TAXONOMY.lens_terms()) <= set(LensId)
    assert set(TAXONOMY.event_terms()) <= set(EventType)


# --- The wiring --------------------------------------------------------------


def article(status: ArticleStatus, text: str | None) -> Article:
    url = "https://example.org/a"
    return Article(
        version=Article.schema_version(),
        item_id="ai-1234567890",
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="lab-blog",
        tier=SourceTier.INSTITUTION,
        vertical="ai",
        rank_score=1.0,
        title="A model launched in Beijing",
        text=text,
        fetched_at="2026-08-26T07:00:00Z",
        status=status,
        failure_detail=None if status is ArticleStatus.OK else "the host never answered",
        extractor_version="test-1",
        sanitizer_version="test-1",
    )


def test_an_extracted_article_carries_the_tags_its_own_words_earn() -> None:
    tagged = tag.tagged(article(ArticleStatus.OK, "Researchers in China shipped it."), taxonomy=TAXONOMY)
    assert tagged.lenses == [LensId.CHINA]
    assert EventType.RELEASE in tagged.events
    assert EventType.RESEARCH in tagged.events


def test_a_failed_article_keeps_its_empty_lists() -> None:
    """No text, never published - a tag would only be a tag on a feed title."""
    failed = tag.tagged(article(ArticleStatus.FETCH_FAILED, None), taxonomy=TAXONOMY)
    assert failed.lenses == []
    assert failed.events == []


def test_tagging_changes_nothing_else_about_the_payload() -> None:
    before = article(ArticleStatus.OK, "Researchers in China shipped it.")
    after = tag.tagged(before, taxonomy=TAXONOMY)
    assert after.model_dump(exclude={"lenses", "events"}) == before.model_dump(
        exclude={"lenses", "events"}
    )


def test_the_same_text_tags_the_same_way_twice() -> None:
    once = tag.tagged(article(ArticleStatus.OK, "A data breach in Beijing."), taxonomy=TAXONOMY)
    twice = tag.tagged(once, taxonomy=TAXONOMY)
    assert once.lenses == twice.lenses
    assert once.events == twice.events


def test_no_prompt_asks_a_model_for_a_tag() -> None:
    """Andre's ruling: a page choosing its own reader-facing tags steers a control."""
    prompts = sorted(Path("backend/idhazh/prompts").glob("*.txt"))
    assert prompts, "the prompt directory must not be empty for this to mean anything"
    for prompt in prompts:
        body = prompt.read_text(encoding="utf-8").lower()
        assert "lens" not in body, prompt.name
        assert "event type" not in body, prompt.name
        assert "entities" not in body, prompt.name
