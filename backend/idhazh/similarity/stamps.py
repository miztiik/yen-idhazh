"""What ruler a pair was scored under, as the values rather than as a digest.

A digest says that an input moved. These say WHICH one, which is what a reader
of a line the run refused to move needs to know: the encoder changed, or a
weight did. `scorer_stamp` in the contract folds the same three values into the
one digest the places that need one use, so the two can never disagree.

The judge half of this question - which model read the pair, under which prompt
and grammar - arrives with the step that calls a model. Nothing here calls one.
"""

from __future__ import annotations

from dataclasses import dataclass

from idhazh import config
from idhazh.contracts.story_similarity_pair import ScorerModelId
from idhazh.embed import EMBEDDER_ID


@dataclass(frozen=True, slots=True)
class ScorerStamp:
    """The three values that decide what a similarity score means."""

    scorer_model: ScorerModelId
    cosine_weight: float
    key_point_weight: float


def scorer_inputs(settings: config.Settings) -> ScorerStamp:
    """The ruler this run scores with, read off the committed config.

    The encoder is the one the pipeline already encoded the day's vectors with,
    so a stamp taken here describes the vectors a pair was actually scored over
    rather than a model somebody could point the stamp at.
    """
    same_story = settings.app.assemble.same_story
    return ScorerStamp(
        scorer_model=EMBEDDER_ID,
        cosine_weight=same_story.cosine_weight,
        key_point_weight=same_story.key_point_weight,
    )
