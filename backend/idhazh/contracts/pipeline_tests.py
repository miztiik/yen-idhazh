"""`config/pipeline-tests.json` - what one dispatch of the pipeline test workflow runs.

**The whole point of this file is a loop a person can close in an hour.** A
production run takes about 200 minutes and has been cancelling shards, so a
change to the pipeline is tested a day after it is written, by a run whose
result is mixed in with eighty other articles. The test workflow runs two
articles down the real path three times over, on one runner, and this file is
where the two articles come from and what the three arms differ by.

**Addresses are candidates, never a fixed pair.** A fixed pair would be the
worst kind of test: it passes for as long as those two pages stay up and stays
silent about everything else the extractor meets. A dispatch draws its pair from
this list, seeded from the run id it was allocated, so two dispatches read
different articles and the seed says which - and the draw is made once, before
any arm starts, so the three arms compare like with like.

**A candidate names a feed and not a vertical.** The feed is already in
`config/sources.json` with its vertical, its tier and its form, so repeating
those here would be a second copy that drifts. What this file adds is one
address per feed that the pipeline has really fetched and summarized.

An address goes stale. A page is moved or withdrawn, and a draw that lands on it
fails to fetch. That is reported by the dispatch rather than guarded against
here: a test list that could not go stale would be a list of pages nobody
publishes.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, ClassVar, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.article import UNTRUSTED_LINE_MAX
from idhazh.contracts.base import ChangelogEntry, Contract, Model, Slug, Url, records_json

#: How many candidates the list holds at its smallest. Two articles drawn from
#: twenty is a ten percent draw, so a fortnight of dispatches reads most of the
#: list rather than the same page over and over. It is a rule of the shape
#: rather than a tunable: a list of five would make the draw decorative, and
#: nobody should be able to switch that off with a config edit.
MINIMUM_CANDIDATES: int = 20

#: A headline, capped where a feed's headline is capped. `\S` is the whole point
#: of declaring a type here rather than reusing `UntrustedLine`: a minimum length
#: of one accepts `"   "`, and a headline of three spaces is not refused anywhere
#: downstream - it reaches the summarizer's prompt and the digest's card as a
#: blank line. This file is hand-edited, so this is where that typo happens.
Headline = Annotated[
    str, StringConstraints(min_length=1, max_length=UNTRUSTED_LINE_MAX, pattern=r"\S")
]


class PipelineTestCandidate(Model):
    """One address a dispatch may draw, and the feed it came from."""

    url: Url = Field(
        description=(
            "An article this pipeline has fetched, extracted and summarized before. "
            "Real rather than synthetic: the extractor's job is other people's markup, "
            "and a page we wrote would test none of it."
        )
    )
    source_id: Slug = Field(
        description=(
            "The feed in `config/sources.json` that carried it. Everything else the "
            "run needs about the address - the vertical, the tier, the form - is read "
            "off that feed, so it is declared once and this file cannot disagree."
        )
    )
    title: Headline = Field(
        description=(
            "The page's own headline. A daily run reads this off the feed entry, and a "
            "dispatch has no feed to read - the address is pinned and has long since "
            "fallen out of its feed's window. So it is declared here, and the plan step "
            "fills it in exactly where `discover` would have. Required rather than "
            "optional: an item with no headline is one the extractor now refuses, so an "
            "optional field would let a dispatch draw a candidate it cannot summarize."
        )
    )


class PipelineTestArm(Model):
    """One pass over the two articles, and what it changes about the run.

    An arm is a whole pass rather than a knob, because the numbers that matter -
    wall clock, tokens a second, what the picture cost - are per pass. Three arms
    over the same two articles is what makes the difference between two of them
    readable; one arm over six articles is not.
    """

    id: Slug = Field(description="What the arm is called in the log and in the artifact.")
    n_parallel: int | None = Field(
        default=None,
        ge=1,
        le=8,
        description=(
            "The model server's slot count for this arm. None leaves the committed "
            "value, which is what the production run serves. An arm that moves it "
            "needs the server restarted, because the slot count is fixed when the "
            "process starts."
        ),
    )
    n_ctx: int | None = Field(
        default=None,
        ge=512,
        description=(
            "The window for this arm. None leaves the committed value. An arm that "
            "raises the slot count raises this with it: llama-server divides the "
            "window it is given between its slots, so two slots on the committed "
            "window is a 32,768-token slot rather than the 65,536 the production "
            "gate admits articles against - and the worst article the truncation cap "
            "admits needs 54,887. Leaving it alone would make the arm a test of a "
            "smaller window wearing a concurrency arm's name."
        ),
    )
    asks_for_a_visual_plan: bool = Field(
        default=True,
        description=(
            "Whether the second call may ask for a picture at all. False writes an "
            "empty `visuals.enabled_kinds`, so no picture is reachable and the gate "
            "takes the plan fields off the grammar, and it writes "
            "`summarize.asks_for_a_visual_plan` false so the window is sized for the "
            "call that is really sent. One knob, because the two have to agree: a "
            "window sized for a plan that is never asked for refuses articles that fit."
        ),
    )


class PipelineTestsConfig(Contract):
    """`config/pipeline-tests.json` - the candidate addresses and the arms."""

    __schema_stem__: ClassVar[str] = "pipeline-tests-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-15",
            change="A candidate carries the page's headline, and a blank one is refused.",
            why="The plan step built items with no title, so every dispatch died downstream.",
        ),
        ChangelogEntry(
            version="2026-09-14",
            change="Initial shape: candidate addresses, the draw size and the arms.",
            why="A production run is long, so a pipeline change was tested a day at a time.",
        ),
    )

    articles_a_dispatch: int = Field(
        default=2,
        ge=1,
        le=8,
        description=(
            "How many addresses one dispatch draws. Two is what fits the hour: the "
            "arms run in sequence over the same articles, so the cost is this number "
            "times the number of arms."
        ),
    )
    budget_minutes: int = Field(
        default=45,
        ge=1,
        le=350,
        description=(
            "What one dispatch is allowed. The workflow's own `timeout-minutes` is "
            "this number, and a test holds the two together so the bound lives in "
            "config rather than in the YAML."
        ),
    )
    candidates: list[PipelineTestCandidate] = Field(
        min_length=MINIMUM_CANDIDATES,
        description="The addresses a dispatch draws from. One per feed, all distinct.",
    )
    arms: list[PipelineTestArm] = Field(
        min_length=2,
        description=(
            "The passes, in order. The first is the baseline the rest are read "
            "against, so there are at least two: one arm measures nothing it can be "
            "compared with."
        ),
    )

    def to_json(self) -> str:
        """One candidate a line, one arm a line - see `records_json`.

        The same reason `config/sources.json` has: a person curates it, and a
        record's five short fields are read together or not at all. At a field a
        line, adding an address is a four-line diff over a file nobody can scan.
        """
        return records_json(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def _the_list_can_answer_the_draw(self) -> Self:
        """Distinct addresses, distinct feeds, distinct arm names, enough to draw from.

        Two candidates on one feed would let a draw take two articles off the same
        site and call that a spread, and the point of the list is that it is not.
        """
        urls = [candidate.url for candidate in self.candidates]
        if len(set(urls)) != len(urls):
            raise ValueError("a candidate address appears twice")
        feeds = [candidate.source_id for candidate in self.candidates]
        if len(set(feeds)) != len(feeds):
            raise ValueError("two candidates name one feed, so a draw could take both")
        names = [arm.id for arm in self.arms]
        if len(set(names)) != len(names):
            raise ValueError("two arms share a name, so their results cannot be told apart")
        if self.articles_a_dispatch > len(self.candidates):
            raise ValueError("the draw asks for more addresses than the list holds")
        return self

    def draw(self, seed: str) -> tuple[PipelineTestCandidate, ...]:
        """The addresses this dispatch reads, decided once by the seed it was given.

        The seed is the CI run id, which GitHub allocates and nothing in the run
        can compute, so two dispatches read different articles and the log can say
        which pair a result belongs to. The ordering is a digest of the seed and
        the address rather than `random.shuffle`, so it does not depend on which
        Python built the runner, and re-running this function with the same seed
        and the same list returns the same pair anywhere.
        """

        def rank(candidate: PipelineTestCandidate) -> str:
            payload = f"{seed}\n{candidate.url}".encode()
            return hashlib.sha256(payload).hexdigest()

        return tuple(sorted(self.candidates, key=rank)[: self.articles_a_dispatch])
