"""The training corpus, the schedules that maintain it, and the frozen set its numbers come from."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.knobs.removed import refuse_a_removed_knob

#: The `finetune` roles this block used to carry. `student` named the small
#: visual planner, retired when the two calls moved onto the summarizer's
#: weights, and re-pointing it at `summarize` would make the teacher and the
#: student one model - a session that trains a model on its own output. Nothing
#: read it, so it is gone rather than moved.
SUPERSEDED_FINETUNE_NAMES: Final[Mapping[str, str]] = MappingProxyType({"student": ""})


#: What a `finetune` role may spell. A key in `models` is a Python attribute
#: name, so it is snake_case - not the kebab-case a `Slug` allows, which no key
#: could ever be. `AppConfig` checks the name against the real block; this only
#: bounds the shape, so an editor reading `schemas/` refuses a typo offline.
ModelRole = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$")]


class ReferenceDatasetConfig(Model):
    """The floors `corpus/reference-dataset-1/` is built to, and the manners it is built with.

    Every number here is a floor or a cap rather than a measurement, and the
    builder refuses loudly rather than emitting a set that misses one. They are
    config because a dataset whose floors are literals cannot be rebuilt at a
    different size without a code change (Guardrail #6).

    Nothing here runs on the runner. `build_reference_dataset.py` reads the open
    web once, by hand, off the daily path.
    """

    rows_per_split_min: int = Field(
        default=200,
        ge=1,
        description=(
            "The floor each side must clear. A disjointness test passes on an empty set, "
            "so a builder that wrote every article to one side would satisfy 'no domain on "
            "both sides' perfectly. This is what it cannot satisfy."
        ),
    )
    domains_per_split_min: int = Field(
        default=20,
        ge=1,
        description=(
            "Distinct registrable domains each side must carry. A side drawn from three "
            "outlets measures those three outlets."
        ),
    )
    rows_per_domain_max: int = Field(
        default=7,
        ge=1,
        description=(
            "How many articles one outlet may contribute. Without a cap the set is the "
            "two largest wire services and a tail."
        ),
    )
    article_words_min: int = Field(
        default=120,
        ge=1,
        description=(
            "Shorter than this and there is not enough article for a person to label, so "
            "the disagreement it produces is about the stub rather than about the words."
        ),
    )
    request_delay_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="Pause between fetches. A measurement is not a licence to hammer a server.",
    )


class FinetuneConfig(Model):
    """The training corpus and the schedules that maintain it.

    Nothing here runs on the runner. Training needs a GPU and the runner has
    none (section 0a), so these knobs size a file CI commits and a notebook
    somewhere else reads. `teacher` names a KEY in `models` rather than a model,
    because the summarizer slot has already moved twice and a knob that spells a
    model name is stale the day the config moves.

    There is no `student`. It named the small visual planner, retired when the
    two calls moved onto the summarizer's weights, and a distillation session
    needs two models: with one role left, the student could only be the teacher.

    The prune knobs live here and not in `retention`. That block is about
    published-site images and its own `site_budget_mb`; putting corpus history
    under the same name would file two unrelated retention policies together.
    """

    teacher: ModelRole = Field(
        default="summarizer",
        description="A key in `models`. The model whose outputs a session fine-tunes.",
    )
    corpus_rows: int = Field(
        default=2000,
        ge=1,
        description=(
            "The window: how many rows `corpus/corpus.jsonl` holds. It costs storage and "
            "git history only - 2.9 KB compressed per row, measured 2026-08-27 over 2,459 "
            "scored rows and the 114 published items of that day - and it buys a bigger "
            "pool to sample a diverse session from."
        ),
    )
    train_rows: int = Field(
        default=1000,
        ge=1,
        description=(
            "The sample: how many rows one session draws from the window. A CEILING, not "
            "a demand - a session takes the lesser of this and what is left once the "
            "holdout is removed, and prints both numbers. It costs GPU hours rather than "
            "storage: estimated 1.8 h for 1000 rows over 2 epochs on a free T4, and no "
            "training job has run here yet, so that is an estimate (Guardrail #10)."
        ),
    )
    min_rows: int = Field(
        default=500,
        ge=1,
        description="Below this the corpus trains nothing, and a repair refuses to cut further.",
    )
    harvest_every_days: int = Field(
        default=7,
        ge=1,
        description=(
            "How often the digest run harvests. A number and not a cron line: standard "
            "5-field cron has no every-N-days field, and `on.schedule` is parsed before "
            "any step runs, so no value in config can ever reach it. The step wakes with "
            "the daily run, reads `harvested_at` from the committed meta file and decides "
            "for itself, which also means a missed day self-corrects on the next wake."
        ),
    )
    prune_every_days: int = Field(
        default=30,
        ge=1,
        description=(
            "How often `prune.yml` fires. Each firing costs one force-push of `main` - "
            "the single exception CLAUDE.md section 8 carries, and the reason it carries "
            "one is that git history is append-only, so deleting a corpus row does not "
            "delete its bytes."
        ),
    )
    prune_keep_days: int = Field(
        default=60,
        ge=1,
        description=(
            "Where the squash boundary sits. Retention is this number, full stop, and it "
            "is not a multiple of anything. At 30 and 60 the history holds 60 to 90 days "
            "of commits - 9 to 13 weekly harvests, 25 MB to 38 MB, flat forever. Two whole "
            "datasets survive any squash for free, because the boundary commit holds a "
            "complete copy of the corpus and so does the tip."
        ),
    )
    holdout_days: int = Field(
        default=14,
        ge=1,
        description=(
            "The trailing days held out of training, by date and never at random. "
            "Production always runs on tomorrow's news; a random split puts the same "
            "story from three feeds on both sides and reports memorisation as success. "
            "It has to be shorter than the window has existed, or the split holds out "
            "every row and leaves nothing to train on."
        ),
    )
    reference_rows: int = Field(
        default=500,
        ge=1,
        description=(
            "How many ideal summaries the hand-authored reference set aims to hold. "
            "The set is authored in slices and is usable before it is full, so this is "
            "a target rather than a floor - nothing refuses to run below it."
        ),
    )
    reference_test_rows: int = Field(
        default=100,
        ge=1,
        description=(
            "How many of `reference_rows` are held back as test references and read "
            "line by line by a person. The rest are drafted with an expert model in an "
            "editor. Two numbers because they carry two standards and two costs: a "
            "drafted row is about two minutes, a read row about five, so this knob is "
            "the one that decides how many hours the set takes."
        ),
    )
    epochs: int = Field(default=2, ge=1)
    sequence_length: int = Field(
        default=16384,
        ge=1,
        description=(
            "How long a training row is allowed to be. It sizes the SINGLE call, "
            "because that is the shape a training row has: a prompt the pipeline "
            "could have sent and an answer it could have returned, and the corpus "
            "holds single-call rows. At the committed extract.truncation_cap_tokens "
            "of 30,000 the worst case is 997 tokens of prompt overhead, 34,890 for "
            "the longest and hardest-tokenizing article the cap lets through, and 4,735 "
            "of answer - 40,622 tokens, which config/idhazh.json covers at 49,152 and "
            "this default does not. It does not follow "
            "--ctx-size on the teacher entry: that window holds the two-call pair, "
            "and nothing trains on a two-call row. A row longer than this is "
            "dropped and counted by the wrangler and "
            "by the notebook, never truncated, because a truncated target teaches the "
            "model to stop mid-summary; at the committed pair nothing is over. What "
            "it costs is GPU memory on the machine "
            "that trains, quadratically in attention - that machine is not the runner "
            "(Guardrail #2 does not reach it), and a card that cannot hold the row lowers "
            "SEQUENCE_LENGTH_OVERRIDE in notebooks/finetune.ipynb, which drops the long "
            "rows for that session only and says how many it dropped."
        ),
    )
    prompt_iterations: int = Field(
        default=3,
        ge=1,
        description=(
            "How many write-critique-revise rounds the offline prompt loop runs before "
            "it stops (`backend/utilities/prompt_loop.py`). Nothing here runs on the "
            "runner or in the daily pipeline: the loop is manual, reads a frozen "
            "committed article set, and a candidate replaces the incumbent prompt only "
            "when it beats it on the deterministic, model-free scorers. More rounds cost "
            "more local model calls and buy more chances at a candidate that clears the "
            "gate; they change no digest a reader sees."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _a_removed_role_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("finetune", data, SUPERSEDED_FINETUNE_NAMES)

    @model_validator(mode="after")
    def _a_session_cannot_draw_more_than_the_window_holds(self) -> Self:
        if self.train_rows > self.corpus_rows:
            raise ValueError("finetune.train_rows cannot exceed finetune.corpus_rows")
        if self.min_rows > self.corpus_rows:
            raise ValueError("finetune.min_rows cannot exceed finetune.corpus_rows")
        if self.reference_test_rows >= self.reference_rows:
            raise ValueError(
                "finetune.reference_test_rows must leave rows to train on, "
                "so it is less than finetune.reference_rows"
            )
        return self
