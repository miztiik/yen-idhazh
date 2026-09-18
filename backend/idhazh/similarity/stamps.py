"""What ruler a pair was scored and judged under, as the values rather than as a digest.

A digest says that an input moved. These say WHICH one, which is what a reader
of a line the run refused to move needs to know: the encoder changed, or a
weight did, or the judge read a reworded ask. `scorer_stamp` and `judge_stamp`
in the contract fold the same values into the one digest the places that need
one use, so the two can never disagree.

Nothing here calls a model. The judge half is three values a run already holds -
which weights the config names, and the two digests `similarity.prompt` takes
over its own text.
"""

from __future__ import annotations

from dataclasses import dataclass

from idhazh import config
from idhazh.contracts.story_similarity_pair import ScorerModelId
from idhazh.embed import EMBEDDER_ID
from idhazh.similarity import prompt


@dataclass(frozen=True, slots=True)
class ScorerStamp:
    """The three values that decide what a similarity score means."""

    scorer_model: ScorerModelId
    cosine_weight: float
    key_point_weight: float


@dataclass(frozen=True, slots=True)
class JudgeStamp:
    """The three values that decide what a verdict means.

    `judge_model` is a plain string where its scorer twin is a literal, and the
    difference is real rather than untidy: the encoder is a constant this
    repository declares, and the judge is whichever entry `config/models/`
    names. Which of the known ids it has to be is checked where the value is
    written down, by the contract that holds the column.
    """

    judge_model: str
    prompt_digest: str
    grammar_digest: str


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


def judge_inputs(settings: config.Settings) -> JudgeStamp:
    """The ruler this run judges with, read off the config and the prompt's own text.

    The model is `models.summarize`, which is the entry a judging leg decodes
    with. Both digests are taken over the rendered text rather than over a file,
    so a checkout's newline convention cannot archive a record.
    """
    return JudgeStamp(
        judge_model=settings.models.summarize.id,
        prompt_digest=prompt.prompt_digest(),
        grammar_digest=prompt.grammar_digest(),
    )
