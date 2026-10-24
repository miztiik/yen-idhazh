"""How much work one bench dispatch does, and why that number is a fit and not a taste.

The bench is `measure.yml`'s `runtime` job: a real llama-server, real fetches,
real summaries, timed. It is not the daily run and it is not the qualification,
so its size is its own knob rather than a reuse of either.
"""

from __future__ import annotations

from pydantic import Field

from idhazh.contracts.base import Model


class BenchConfig(Model):
    corpus_items: int = Field(
        default=3,
        ge=1,
        le=20,
        description=(
            "Articles one bench repeat reads. It sizes the whole dispatch: a named "
            "candidate runs a baseline case and the candidate's case, so two repeats "
            "is four passes over this many articles, and one pass is the unit the job "
            "timeout is spent in.\n\n"
            "Three because five does not fit, not because three is thrifty. Measured "
            "2026-09-17 over the four dispatches of 2026-09-16 (35086403868, "
            "35086407071, 35086409972, 35086412536) on stock ubuntu-latest: the "
            "slowest pass took 65.6 minutes for five articles, so six passes compute "
            "to 393.7 minutes against a 330-minute job timeout - over by 19 percent. "
            "Four articles is 315 minutes, which is 95.5 percent of the timeout and no "
            "headroom at all. Three is 236 minutes at three repeats, 71.6 percent, and it "
            "fits; at two repeats it is about 157. "
            "Guardrail #2: the timeout is GitHub's, so the design is what gives.\n\n"
            "Raising it costs the dispatch, and past three it costs the dispatch its "
            "result. Lowering it costs evidence: at five articles a per-article "
            "output-drift finding is p = 0.03 under an exact binomial, and at three it "
            "is p = 0.125 - still a finding, no longer overwhelming. What three buys "
            "back is a dispatch that finishes: article text drifted on 5 of 15 "
            "article-observations across three dispatches, so fewer articles means a "
            "better chance the run produces a usable reading at all.\n\n"
            "It never touches the qualification corpus, which is `validate.yml`'s own "
            "`corpus_per_shard` dispatch input and stays where it is. A bench says how "
            "fast; a qualification says how good, and the second needs its 30 articles "
            "to bound an undetected defect rate."
        ),
    )

    repeats: int = Field(
        default=2,
        ge=2,
        description=(
            "How many times a bench dispatch runs each case. Two is the floor because "
            "a spread needs two readings; one reading has nothing to be read against, "
            "and a dispatch that cannot produce a spread is refused before it starts.\n\n"
            "It lives here, beside `corpus_items`, because the two numbers multiply and "
            "the product is what the job timeout is spent on. A named candidate runs two "
            "cases, so two repeats is four passes over `corpus_items` articles - about "
            "157 minutes against a 330-minute timeout at three articles. Held in "
            "two files, the next person raises one of the two without seeing the other "
            "and finds out at 330 minutes, when GitHub kills the job (Guardrail #2).\n\n"
            "A case set costs more at the same number: `draft_depth` runs four cases, so "
            "two repeats there is eight passes rather than four. That is what "
            "`measure.yml`'s `runtime_repeats` dispatch input is for - it overrules this "
            "knob for one run without a commit. The form's default is this same number, "
            "and a test holds the two together."
        ),
    )
