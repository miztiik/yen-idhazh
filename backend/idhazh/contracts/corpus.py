"""One training sample: the exact exchange the summarizer was asked to produce.

The corpus is a rolling window of these rows, one JSON object per line, under
`corpus/corpus.jsonl`. A row holds the three turns of one article's exchange -
the system prompt the run rendered, the fenced article the model read, and the
JSON it wrote - plus four fields that say which article, when, which model and
which vertical.

**The file trains on its own.** `messages` is the OpenAI chat format that
`datasets.load_dataset("json", ...)` loads and that TRL, Unsloth, Axolotl and
LLaMA-Factory all read with no converter, so the corpus is portable to another
stack without a conversion script to keep in step. That is why the system prompt
is written inline on every row rather than referenced: measured 2026-08-27 over
`state/scores.csv` on `origin/main`, repeating it costs 1.95 MB raw per 500 rows
and 98 KB once git compresses it - about 3 percent of a row's compressed size.

**Committed on purpose, and it is the one payload in this project that carries
article text into git.** `CLAUDE.md` section 0a permits it by name: the corpus
holds source text as training samples, nothing renders it, and no reader-facing
page may read it. `EvidenceItem` holds the same text and is gitignored, because
it exists to be shown to a person rather than to train anything.

**A contract under Rule #3 and not a migration surface under section 11**, on
the precedent `EvidenceItem` set on 2026-08-27. The window is regenerable from
the run's own payloads, it is read by a notebook a person re-runs rather than by
a build, and the prune rewrites its history every `finetune.prune_every_days`.
So a shape change here owes a re-harvest, never a read-side migration. The
`version` field is carried because every `Contract` carries one and because it
tells a training session which build wrote the rows in front of it.

**The prompt is not restated here.** `messages[0]` and `messages[1]` are
whatever `idhazh.summarize.system_prompt` and `idhazh.summarize.user_turn`
returned for that article, called by the harvest rather than reproduced - which
is what makes the corpus the prompt we serve instead of an approximation of it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    Sha256,
    Slug,
    UrlKey,
)


class ChatRole(StrEnum):
    """The three turns of one supervised sample, in the order a trainer reads them."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


#: Exactly this, in exactly this order. A trainer masks everything before the
#: assistant turn, so a row whose turns are reordered trains on the article
#: instead of on the summary and nothing raises.
TURN_ORDER: tuple[ChatRole, ...] = (ChatRole.SYSTEM, ChatRole.USER, ChatRole.ASSISTANT)


class ChatTurn(Model):
    """One turn. `content` is text and never a structure, because that is what a trainer reads."""

    role: ChatRole
    content: str = Field(min_length=1)


class CorpusRow(Contract):
    """One article's exchange, as one line of `corpus/corpus.jsonl`."""

    __schema_stem__: ClassVar[str] = "corpus-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-28",
            change=(
                "Initial shape: the three-turn exchange, plus url_key, date, model_id "
                "and vertical."
            ),
            why=(
                "The pipeline scores 600-730 articles a day and throws the pairs away. "
                "They are training data for the exact job we run, so the window that "
                "keeps them needs a shape before anything writes one (Rule #3). Five "
                "fields and no more: prompt_fingerprint is sha256 of messages[0], "
                "source_words is a word count of messages[1], and which file a row lives "
                "in already says whether a human wrote it - a stored copy of a derivable "
                "value is a second thing that can disagree with the first."
            ),
        ),
    )

    messages: list[ChatTurn] = Field(
        min_length=len(TURN_ORDER),
        max_length=len(TURN_ORDER),
        description=(
            "The training column, and the only one a trainer reads. System, user, "
            "assistant, in that order."
        ),
    )
    url_key: UrlKey = Field(
        description="Deduplication, and what the holdout file is a set of."
    )
    date: DateStamp = Field(
        description="The run day. It drives the roll's eviction and the date-based holdout split."
    )
    model_id: Slug = Field(
        description=(
            "Which model wrote the assistant turn. A distilled corpus mixes rows from "
            "two teachers and nothing else on the row tells them apart."
        )
    )
    vertical: Slug = Field(
        description=(
            "The one diversity column a quota can act on. Measured 2026-08-27 over the "
            "114 published items of that day: present on 114 of 114, where events "
            "reached 58 percent, entities 53 and lenses 34."
        )
    )

    @model_validator(mode="after")
    def _turns_are_the_three_a_trainer_expects(self) -> Self:
        roles = tuple(turn.role for turn in self.messages)
        if roles != TURN_ORDER:
            spelled = ", ".join(role.value for role in TURN_ORDER)
            raise ValueError(f"messages must be exactly {spelled}, in that order")
        return self

    @property
    def system(self) -> str:
        return self.messages[0].content

    @property
    def user(self) -> str:
        return self.messages[1].content

    @property
    def assistant(self) -> str:
        return self.messages[2].content

    @property
    def source_words(self) -> int:
        """Derived rather than stored, so it cannot disagree with the turn it counts."""
        return len(self.user.split())


class CorpusMeta(Contract):
    """What the window holds, and when each of its two schedules last fired.

    Committed beside the rows, and it is the schedule itself rather than a
    report about one. `on.schedule` is parsed before any step runs, so no value
    in `config/` can ever reach a cron line; a cadence that has to be
    configurable is therefore a due-check in a step, and a due-check needs
    durable state to compare against. That state is this file.

    Keeping it as dates rather than as timestamps is deliberate: a due-check
    that compares two `YYYY-MM-DD` strings is a test with no clock in it, and
    when the job actually ran is already recorded by the commit it made.
    """

    __schema_stem__: ClassVar[str] = "corpus-meta"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-28",
            change=(
                "Initial shape: the census of the window, plus harvested_date and "
                "pruned_date."
            ),
            why=(
                "Two schedules need somewhere to remember when they last fired, and a "
                "cron line cannot be that place - GitHub Actions parses on.schedule "
                "before any step runs, so no config value reaches it, and 5-field cron "
                "has no every-N-days field at all. The census beside it answers the "
                "question a person asks before spending a training session: how many "
                "rows are there, over what range of days, and is it all one vertical."
            ),
        ),
    )

    rows: int = Field(default=0, ge=0, description="How many lines `corpus.jsonl` holds.")
    first_date: DateStamp | None = Field(
        default=None, description="The oldest run day in the window. None when it is empty."
    )
    last_date: DateStamp | None = Field(
        default=None, description="The newest run day in the window."
    )
    verticals: dict[Slug, int] = Field(
        default_factory=dict, description="Rows per vertical. What a diversity quota reads."
    )
    models: dict[Slug, int] = Field(
        default_factory=dict,
        description="Rows per model that wrote the assistant turn. A mixed corpus has two.",
    )
    harvested_date: DateStamp | None = Field(
        default=None,
        description=(
            "The digest day the last harvest read. The harvest step compares it against "
            "the day it is running for, so a missed day self-corrects on the next wake."
        ),
    )
    pruned_date: DateStamp | None = Field(
        default=None,
        description=(
            "The day `prune.yml` last squashed history. It is the only thing that stops "
            "a due-check from firing every day once the repository is older than "
            "`finetune.prune_keep_days`."
        ),
    )
    prompt_digest: Sha256 | None = Field(
        default=None,
        description=(
            "sha256 over `summarize.prompt_inputs` at harvest time - the template plus "
            "every number substituted into it. Not derivable from the rows, which carry "
            "rendered prompts rather than the template, and it is what tells a person "
            "that the prompt moved under the corpus they are about to train on."
        ),
    )

