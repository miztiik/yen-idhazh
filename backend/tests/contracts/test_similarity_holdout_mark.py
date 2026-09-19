"""Does a holdout mark survive the trip to CSV and back, and does a bad cell say so?"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair

pytestmark = pytest.mark.contract


def _row(mark: str) -> dict[str, str]:
    """One complete row with the `same_story` cell spelled however the caller asks."""
    return {
        "version": "2026-09-19",
        "left_url": "https://example.com/one",
        "right_url": "https://example.com/two",
        "left_date": "2026-09-18",
        "right_date": "2026-09-18",
        "left_title": "A lake is renamed",
        "right_title": "The lake gets its old name back",
        "same_story": mark,
        "marked_on": "2026-09-19",
        "note": "a judge read both summaries",
    }


@pytest.mark.parametrize("mark", ["True", "true", "TRUE", " True "])
def test_every_spelling_of_one_story_reads_as_one_story(mark: str) -> None:
    """The writer emits `True`, but a person editing the file may not."""
    assert SimilarityHoldoutPair.from_csv_row(_row(mark)).same_story is True


@pytest.mark.parametrize("mark", ["False", "false", "FALSE"])
def test_every_spelling_of_two_stories_reads_as_two_stories(mark: str) -> None:
    """The false rows are the load-bearing ones, so they are the ones worth proving."""
    assert SimilarityHoldoutPair.from_csv_row(_row(mark)).same_story is False


@pytest.mark.parametrize("mark", ["", "yes", "1", "Y", "same"])
def test_a_mark_nobody_recognises_refuses_instead_of_reading_as_two_stories(mark: str) -> None:
    """The defect this guards: an unknown spelling compared against one literal is false.

    Read that way a whole file becomes two-story pairs, and the floor fitted from
    it refuses every merge - with no error anywhere to say the file was misread.
    """
    with pytest.raises((ValueError, ValidationError), match="same_story"):
        SimilarityHoldoutPair.from_csv_row(_row(mark))


@pytest.mark.parametrize("same_story", [True, False])
def test_a_mark_written_out_reads_back_as_the_same_mark(same_story: bool) -> None:
    """Writer and reader agree on the spelling, which is what the round trip checks."""
    pair = SimilarityHoldoutPair.from_csv_row(_row(str(same_story)))
    assert SimilarityHoldoutPair.from_csv_row(pair.csv_row()).same_story is same_story
