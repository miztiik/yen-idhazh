"""The sample sheet's arithmetic: which band a pair is in, and which pairs are chosen.

`backend/utilities/` is outside `testpaths`, so nothing there is collected by
pytest. Its pure functions are still owed tests, and this is where they live -
the same arrangement `test_check_seeded_stores.py` uses.

Every case here is built in the test. Nothing reads the draw tree, the published
days or the committed sheet, so none of it gets slower as the archive grows
(CLAUDE.md section 13).
"""

from __future__ import annotations

from utilities.sample_sheet import (
    Article,
    Band,
    Pair,
    as_holdout_rows,
    band_of,
    select,
)

LINE = 0.94
CORRIDOR = 0.02


def _pair(score: float, key: str) -> Pair:
    side = Article(url=f"https://e.test/{key}", title=key, summary="", source="e", date="2026-09-01")
    return Pair(
        date="2026-09-01",
        pair_key=key,
        score=score,
        cosine=score,
        headline=False,
        band=band_of(score, LINE, corridor=CORRIDOR),
        left=side,
        right=side,
    )


def test_a_score_exactly_on_the_line_is_eligible_not_refused() -> None:
    """`assemble` refuses on `score < floor_min`, so the line itself merges.

    Filing the boundary on the refused side would put a pair in the sheet under a
    band that says the opposite of what the pipeline did with it.
    """
    assert band_of(LINE, LINE, corridor=CORRIDOR) is Band.JUST_ABOVE


def test_the_corridor_edges_belong_to_the_corridor() -> None:
    assert band_of(LINE + CORRIDOR, LINE, corridor=CORRIDOR) is Band.JUST_ABOVE
    assert band_of(LINE - CORRIDOR, LINE, corridor=CORRIDOR) is Band.JUST_BELOW
    assert band_of(LINE + CORRIDOR + 1e-6, LINE, corridor=CORRIDOR) is Band.WELL_ABOVE
    assert band_of(LINE - CORRIDOR - 1e-6, LINE, corridor=CORRIDOR) is Band.WELL_BELOW


def test_every_band_is_represented_before_any_band_takes_a_second_slot() -> None:
    """Round robin, not a quota.

    The bands are never evenly filled - one of them held 771 pairs where another
    held 105 - so a quota would hand the sheet to whichever band the draw
    happened to favour.
    """
    pairs = [_pair(0.945, "a1"), _pair(0.946, "a2"), _pair(0.935, "b1"), _pair(0.99, "c1")]
    chosen = select(pairs, line=LINE, total=3)
    assert len({pair.band for pair in chosen}) == 3


def test_a_sheet_wider_than_the_population_takes_everything_once() -> None:
    pairs = [_pair(0.945, "a1"), _pair(0.935, "b1")]
    chosen = select(pairs, line=LINE, total=50)
    assert [pair.pair_key for pair in chosen] == ["a1", "b1"]


def test_the_corridor_is_ordered_by_distance_from_the_line() -> None:
    """A label near the line can move it, so the nearest pair is read first."""
    pairs = [_pair(0.958, "far"), _pair(0.941, "near"), _pair(0.949, "mid")]
    chosen = select(pairs, line=LINE, total=3)
    assert [pair.pair_key for pair in chosen] == ["near", "mid", "far"]


def test_the_outer_bands_reach_their_far_end_instead_of_crowding_the_line() -> None:
    """THE BITE. Nearest-first everywhere gave a sheet spanning 0.9187 to 0.9719.

    A benchmark whose easiest case is a hundredth away from its hardest cannot
    tell a model that is wrong from a pair that is genuinely ambiguous.
    """
    pairs = [_pair(0.961 + index * 0.001, f"w{index:02d}") for index in range(39)]
    chosen = select(pairs, line=LINE, total=4)
    span = max(pair.score for pair in chosen) - min(pair.score for pair in chosen)
    assert span > 0.02


def test_one_populated_band_still_fills_the_whole_sheet() -> None:
    """The first spread fix capped each outer band at a quarter of the sheet.

    A draw that filled only `well-below` then returned 50 pairs when 200 were
    asked for, silently. Ordering the band rather than truncating it is what
    makes the caller's count the only thing that decides the size.
    """
    pairs = [_pair(0.90 + index * 0.0005, f"b{index:02d}") for index in range(40)]
    assert {pair.band for pair in pairs} == {Band.WELL_BELOW}
    assert len(select(pairs, line=LINE, total=20)) == 20


def test_a_pair_nobody_labelled_produces_no_row() -> None:
    """A sheet that comes back short is short. It is never filled in with a guess."""
    assert as_holdout_rows([_pair(0.95, "a1")], {}, labelled_on="2026-09-19", labeller="m") == []


def test_a_harvested_row_says_who_labelled_it() -> None:
    """A mark is worth what its labeller is worth, so the row carries the name."""
    rows = as_holdout_rows(
        [_pair(0.9606, "a1")], {"a1": False}, labelled_on="2026-09-19", labeller="a-judge"
    )
    assert rows[0]["same_story"] == "false"
    assert "a-judge" in rows[0]["note"]
    assert "0.9606" in rows[0]["note"]


def test_a_mark_survives_the_sheet_that_surfaced_it() -> None:
    """THE BITE. Harvesting from the sheet lost every mark the sheet stopped showing.

    Changing how pairs are chosen turned 200 labelled pairs into 129 committed
    rows, silently. A mark belongs to a pair, so the harvest joins against the
    whole drawn population and a pair that dropped out of the sheet keeps its
    label.
    """
    population = [_pair(0.95, "kept"), _pair(0.93, "dropped-from-the-sheet")]
    labels = {"kept": True, "dropped-from-the-sheet": False}
    rows = as_holdout_rows(population, labels, labelled_on="2026-09-19", labeller="m")
    assert len(rows) == 2
