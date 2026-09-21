"""What ruler a pair was scored and judged under, as the values rather than as a digest.

A digest says that an input moved. These say WHICH one, which is what a reader
of a line the run refused to move needs to know: the encoder changed, or a
weight did, or the judge read a reworded ask, or a reasoning span ran in front
of the verdict. `scorer_stamp` and `judge_stamp` in the contract fold the same
values into the one digest the places that need one use, so the two can never
disagree.

Nothing here calls a model. The judge half is read off what a run already holds -
which entry the config names, the two digests `similarity.prompt` takes over its
own text, and the request body the judging call would post.
"""

from __future__ import annotations

from dataclasses import dataclass

from idhazh import config
from idhazh.contracts.story_similarity_pair import ScorerModelId
from idhazh.embed import EMBEDDER_ID
from idhazh.llm.server import decode_digest
from idhazh.similarity import judge, prompt


@dataclass(frozen=True, slots=True)
class ScorerStamp:
    """The three values that decide what a similarity score means."""

    scorer_model: ScorerModelId
    cosine_weight: float
    key_point_weight: float


@dataclass(frozen=True, slots=True)
class JudgeStamp:
    """The six values that decide what a verdict means.

    `judge_model` is a plain string where its scorer twin is a literal, and the
    difference is real rather than untidy: the encoder is a constant this
    repository declares, and the judge is whichever entry `config/models/`
    names. Which of the known ids it has to be is checked where the value is
    written down, by the contract that holds the column.

    **The last three say how the verdict was decoded, and the first three say
    what was asked.** Two runs can read the identical ask under two samplers and
    two envelopes, and before these were here the record counted both as one
    population with nothing able to separate them afterwards.
    """

    judge_model: str
    prompt_digest: str
    grammar_digest: str
    judge_temperature: float
    decode_digest: str
    thinks: bool


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

    The model is `judge.entry_of`, which is the entry a judging leg decodes with.
    Both digests are taken over the rendered text rather than over a file, so a
    checkout's newline convention cannot archive a record.

    **The decode digest is taken over a real request body, built by the function
    that builds the real one.** A digest assembled from config values instead
    would agree with the config and disagree with what goes out, which is the one
    case worth seeing. The pair stands in as two empty summaries because the
    prompt is the one posted key the digest excludes, so no pair can move it.

    **The grammar is excluded from that digest and stamped beside it.**
    `grammar_digest` is its own value here and its own column on the row, so
    nothing about the shape the decoder was held to is lost - which is not true
    of a caller posting `json_schema`, where the schema is inside the decode
    digest and has no column. This judge posts a grammar and never a schema, so
    the asymmetry costs this stamp nothing.
    """
    entry = judge.entry_of(settings)
    body = judge.decode_body(
        settings, system=prompt.system_turn(), user=prompt.blank_user_turn()
    )
    return JudgeStamp(
        judge_model=entry.id,
        prompt_digest=prompt.prompt_digest(),
        grammar_digest=prompt.grammar_digest(),
        judge_temperature=float(body["temperature"]),
        decode_digest=decode_digest(body),
        thinks=entry.turns.thinks,
    )
