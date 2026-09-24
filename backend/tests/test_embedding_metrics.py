"""The coherence measure: the arithmetic, the null cases, and the real encoder.

Two tiers in one file, because they answer one question from two sides. The
arithmetic is driven from vectors written down here, so a reader can check the
mean by hand with no model in the room. The wiring is driven from the encoder
this repository commits, so nothing is proved against a stand-in the pipeline
never uses (Guardrail #7).

Nothing here reads a committed day, the ledger or the corpus, so none of it gets
slower as the archive grows (CLAUDE.md section 13).
"""

from __future__ import annotations

import math

import pytest

from idhazh import config
from idhazh.embed import encoder_if_committed
from idhazh.evals.embedding_metrics import coherence, mean_adjacent_cosine, sentences

#: Three unit vectors in the plane, chosen so both neighbouring dot products are
#: round numbers a reader can multiply out: (1,0) against (0.6,0.8) is 0.6, and
#: (0.6,0.8) against (0,1) is 0.8. Their mean is 0.7.
_EAST = [1.0, 0.0]
_NORTH_EAST = [0.6, 0.8]
_NORTH = [0.0, 1.0]
_WEST = [-1.0, 0.0]


def test_the_mean_is_the_average_of_each_neighbouring_pair() -> None:
    """Worked by hand: 0.6 and 0.8 over two pairs is 0.7.

    Neighbouring pairs only. An all-pairs mean would also take (1,0) against
    (0,1), which is 0.0, and would report 0.467 for the same three sentences -
    a different question about whether the summary is about one subject.
    """
    assert mean_adjacent_cosine([_EAST, _NORTH_EAST, _NORTH]) == pytest.approx(0.7)


def test_a_sentence_that_turns_away_from_the_one_before_it_scores_below_zero() -> None:
    """The scale runs -1 to 1, so the bottom half has to be reachable.

    Rescaling to 0-to-1 would put a summary whose sentences point away from one
    another at 0.0 and a summary of one repeated sentence at 1.0, and the reader
    could no longer tell either from the encoder's own number.
    """
    assert mean_adjacent_cosine([_EAST, _WEST]) == pytest.approx(-1.0)
    assert mean_adjacent_cosine([_EAST, _WEST, _EAST]) == pytest.approx(-1.0)


def test_fewer_than_two_vectors_is_unmeasured_rather_than_zero() -> None:
    """There is no neighbouring pair, and 0.0 would claim a reading nobody took."""
    assert mean_adjacent_cosine([]) is None
    assert mean_adjacent_cosine([_EAST]) is None


def test_the_sentence_split_drops_blanks_and_keeps_the_rest() -> None:
    """A blank fragment is not a sentence, and encoding one would score noise."""
    assert sentences("One thing happened.  Then another did!\n\nAnd a third?") == [
        "One thing happened.",
        "Then another did!",
        "And a third?",
    ]
    assert sentences("   ") == []


def test_a_checkout_without_the_weights_records_nothing_rather_than_failing() -> None:
    """Degrade, do not fail (CLAUDE.md section 1a). The item still publishes."""
    assert encoder_if_committed(config.REPO_ROOT / "does-not-exist") is None


def test_a_one_sentence_summary_has_nothing_to_compare() -> None:
    """Null and a low score are two different facts about the same summary.

    Driven through the committed encoder rather than a stand-in, so it also
    shows the shard pays nothing for a summary it cannot measure: the encoder
    this hands over has not loaded its weights and does not load them here.
    """
    encoder = encoder_if_committed(config.REPO_ROOT)
    assert encoder is not None

    assert coherence("Only one sentence here.", encoder=encoder) is None
    assert coherence("", encoder=encoder) is None


def test_the_committed_encoder_scores_a_following_sentence_above_a_turning_one() -> None:
    """The wiring, against the weights this repository ships.

    Not a threshold: the two readings are compared against each other rather
    than against a number nobody measured (Guardrail #10). What it proves is
    that the column reads the summary rather than returning a constant, and that
    the value stays on the encoder's own scale.
    """
    encoder = encoder_if_committed(config.REPO_ROOT)
    assert encoder is not None, "the encoder is committed, so a checkout has it"

    follows = coherence(
        "The council approved the tram line. The same council set a spring start date.",
        encoder=encoder,
    )
    turns = coherence(
        "The council approved the tram line. Pastry chefs gathered in Lyon for a contest.",
        encoder=encoder,
    )

    assert follows is not None and turns is not None
    assert -1.0 <= turns < follows <= 1.0


def test_the_reading_is_the_dot_product_the_encoder_itself_would_give() -> None:
    """One arithmetic, not two: the split function and the encoder are composed.

    Recomputed here from the encoder's own vectors, so a later change that
    quietly averaged all pairs, or took a cosine of the whole summary, fails.
    """
    encoder = encoder_if_committed(config.REPO_ROOT)
    assert encoder is not None

    summary = "Rain closed the airport. Flights resumed by evening. Two routes stayed shut."
    parts = sentences(summary)
    vectors = encoder.encode(parts)
    by_hand = sum(
        sum(left * right for left, right in zip(one, two, strict=True))
        for one, two in zip(vectors, vectors[1:], strict=False)
    ) / (len(vectors) - 1)

    assert coherence(summary, encoder=encoder) == pytest.approx(by_hand)
    assert math.isfinite(by_hand)
