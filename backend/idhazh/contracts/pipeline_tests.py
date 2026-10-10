"""`config/pipeline-tests.json` - what one dispatch of the pipeline test workflow runs.

**The whole point of this file is a fast check of a model on the production
path.** A production run takes hours, so a model or a pipeline change is checked
here instead: a few articles down the real fetcher, extractor, prompts and model
server. It is a check, not a benchmark - measuring and tuning a server is
`measure.yml`'s job - so everything here is shaped for the shortest wait: the
articles split into shards the way production splits a day, and every shard of
every test case runs at once, each on a runner of its own.

**A test case is switched on or off here, and nowhere else.** The workflow asks
this file which test cases are enabled and starts one job for each runner they
need, so turning a test case off is a one-word edit, and keeping one that a
model or a runner cannot serve yet costs nothing.

**Addresses are candidates, never a fixed pair.** A fixed pair would be the
worst kind of test: it passes for as long as those two pages stay up and stays
silent about everything else the extractor meets. A dispatch draws its articles
from this list, seeded from the run id it was allocated, so two dispatches read
different articles and the seed says which - and the draw is made once, before
any test case starts, so every test case reads the same articles.

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

#: The shared root used by the bench and `Model validation`, with each pipeline
#: test case's own validated slug beneath it.
TRIAL_STATE_PREFIX: str = "pipeline-tests"


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
            "fills it in exactly where `discover` would have. Required to keep the "
            "declared benchmark input complete, even though production can summarize "
            "an article whose source headline is absent."
        )
    )


class PipelineTestCase(Model):
    """One pass over the drawn articles, and what it changes about the run.

    A test case is a whole pass rather than a knob, because what a person reads
    off a dispatch - did every article come back summarized, and how long did
    the slowest one take - is per pass. Every test case reads the same articles
    on model servers of its own, so no test case inherits another's warm cache.
    """

    id: Slug = Field(description="What the test case is called in the log and in the artifact.")
    enabled: bool = Field(
        description=(
            "Whether a dispatch runs this test case. Off keeps the definition for the "
            "day a model or a runner can serve it, and turning it back on is this one "
            "word: the workflow starts a job for every runner an enabled test case "
            "needs and none for the rest."
        ),
    )
    n_parallel: int | None = Field(
        default=None,
        ge=1,
        le=8,
        description=(
            "How many requests one model server works on at once in this test case, "
            "and so how many shards share each runner - each one a `work` process "
            "posting to that server at the same time. None is one, which is what "
            "production serves. Every slot holds a window of its own, so a test case "
            "that raises this needs a machine with the memory for all of them, and "
            "it needs at least as many shards as slots to put them to work."
        ),
    )
    n_ctx: int | None = Field(
        default=None,
        ge=512,
        description=(
            "The window for this test case. None leaves the committed value. A test case "
            "that raises the slot count raises this with it: llama-server divides the "
            "window it is given between its slots, so two slots on the committed "
            "window is a 32,768-token slot rather than the 65,536 the production "
            "gate admits articles against - and the worst article the truncation cap "
            "admits needs 64,699. Leaving it alone would make the test case a test of a "
            "smaller window wearing a concurrency test case's name."
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

    @property
    def slots(self) -> int:
        """How many shards share one of this test case's model servers at a time."""
        return self.n_parallel or 1

class PipelineTestsConfig(Contract):
    """`config/pipeline-tests.json` - the candidate addresses and the test cases."""

    __schema_stem__: ClassVar[str] = "pipeline-tests-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-29",
            change="A test case carries `enabled`, and the articles split into shards.",
            why="A dispatch runs what config switches on, every shard at once.",
        ),
        ChangelogEntry(
            version="2026-09-28",
            change="`cases` is now `test_cases`.",
            why="Each tests the pipeline under one setting, and its item class already said so.",
        ),
        ChangelogEntry(
            version="2026-09-15T12:00",
            change="`arms` is now `cases`.",
            why="`arm` was benchmarking's word and reads as a limb everywhere else.",
        ),
        ChangelogEntry(
            version="2026-09-15",
            change="A candidate carries the page's headline, and a blank one is refused.",
            why="The plan step built items with no title, so every dispatch died downstream.",
        ),
        ChangelogEntry(
            version="2026-09-14",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    articles_a_dispatch: int = Field(
        default=2,
        ge=1,
        le=8,
        description=(
            "How many addresses one dispatch draws. Every test case reads all of "
            "them, split into shards that run at once, so another article costs "
            "another runner rather than a longer wait."
        ),
    )
    articles_a_shard: int = Field(
        default=1,
        ge=1,
        le=8,
        description=(
            "How many of those articles one shard works through, one after another. "
            "One is the fastest: every article gets a worker of its own, the way a "
            "production day is split across workers, and a test case takes as long "
            "as its slowest article. Raise it to spend fewer runners on a large draw."
        ),
    )
    budget_minutes: int = Field(
        default=45,
        ge=1,
        le=350,
        description=(
            "What one runner of a test case is allowed. The workflow's own "
            "`timeout-minutes` is this number, and a test holds the two together so "
            "the bound lives in config rather than in the YAML."
        ),
    )
    candidates: list[PipelineTestCandidate] = Field(
        min_length=MINIMUM_CANDIDATES,
        description="The addresses a dispatch draws from. One per feed, all distinct.",
    )
    test_cases: list[PipelineTestCase] = Field(
        min_length=1,
        description=(
            "The passes a dispatch may run. Only the enabled ones start, and one is "
            "enough: checking that a model walks the production path compares it "
            "with nothing."
        ),
    )

    def to_json(self) -> str:
        """One candidate a line, one test case a line - see `records_json`.

        The same reason `config/sources.json` has: a person curates it, and a
        record's five short fields are read together or not at all. At a field a
        line, adding an address is a four-line diff over a file nobody can scan.
        """
        return records_json(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def _the_list_can_answer_the_draw(self) -> Self:
        """Distinct addresses, distinct feeds, distinct test case names, enough to draw from.

        Two candidates on one feed would let a draw take two articles off the same
        site and call that a spread, and the point of the list is that it is not.
        A config with every test case switched off would start a dispatch that
        runs nothing, so it is refused here rather than on a runner.
        """
        urls = [candidate.url for candidate in self.candidates]
        if len(set(urls)) != len(urls):
            raise ValueError("a candidate address appears twice")
        feeds = [candidate.source_id for candidate in self.candidates]
        if len(set(feeds)) != len(feeds):
            raise ValueError("two candidates name one feed, so a draw could take both")
        names = [test_case.id for test_case in self.test_cases]
        if len(set(names)) != len(names):
            raise ValueError("two test cases share a name, so their results cannot be told apart")
        if not any(test_case.enabled for test_case in self.test_cases):
            raise ValueError("no test case is enabled, so a dispatch would run nothing")
        if self.articles_a_dispatch > len(self.candidates):
            raise ValueError("the draw asks for more addresses than the list holds")
        return self

    def shard_count(self) -> int:
        """How many shards a dispatch's articles split into, for every test case alike."""
        return -(-self.articles_a_dispatch // self.articles_a_shard)

    def runners(self, test_case: PipelineTestCase) -> int:
        """How many machines one test case needs: each serves one model to `slots` shards."""
        return -(-self.shard_count() // test_case.slots)

    def shards_on(self, test_case: PipelineTestCase, runner: int) -> tuple[int, ...]:
        """Which shards one runner of a test case works, all at once against its server.

        Consecutive shard numbers, so a two-slot runner holds two shards and the
        production round-robin in `stages.common.shard_of` hands each of them its
        own articles. A runner past the last shard holds none.
        """
        first = runner * test_case.slots
        return tuple(range(first, min(first + test_case.slots, self.shard_count())))

    def runs(self) -> tuple[tuple[PipelineTestCase, int], ...]:
        """Every enabled test case and runner a dispatch starts a job for, in config order."""
        return tuple(
            (test_case, runner)
            for test_case in self.test_cases
            if test_case.enabled
            for runner in range(self.runners(test_case))
        )

    def draw(self, seed: str) -> tuple[PipelineTestCandidate, ...]:
        """The addresses this dispatch reads, decided once by the seed it was given.

        The seed is the CI run id, which GitHub allocates and nothing in the run
        can compute, so two dispatches read different articles and the log can say
        which ones a result belongs to. The ordering is a digest of the seed and
        the address rather than `random.shuffle`, so it does not depend on which
        Python built the runner, and re-running this function with the same seed
        and the same list returns the same articles anywhere.
        """

        def rank(candidate: PipelineTestCandidate) -> str:
            payload = f"{seed}\n{candidate.url}".encode()
            return hashlib.sha256(payload).hexdigest()

        return tuple(sorted(self.candidates, key=rank)[: self.articles_a_dispatch])
