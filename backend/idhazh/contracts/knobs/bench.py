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
            "candidate runs a baseline case and the candidate's case, so three repeats "
            "is six passes over this many articles, and one pass is the unit the job "
            "timeout is spent in.\n\n"
            "Three because five does not fit, not because three is thrifty. Measured "
            "2026-09-17 over the four dispatches of 2026-09-16 (35086403868, "
            "35086407071, 35086409972, 35086412536) on stock ubuntu-latest: the "
            "slowest pass took 65.6 minutes for five articles, so six passes compute "
            "to 393.7 minutes against a 330-minute job timeout - over by 19 percent. "
            "Four articles is 315 minutes, which is 95.5 percent of the timeout and no "
            "headroom at all. Three is 236 minutes, 71.6 percent, and it fits. "
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

    run_model_speed_case: bool = Field(
        default=True,
        description=(
            "Does a bench dispatch measure the model's raw speed before it measures "
            "real work? Default true, and it is removed the day the speed case stops "
            "costing a dispatch time worth saving - measured 2026-09-16 over four "
            "dispatches on stock ubuntu-latest at 9.1, 26.7, 27.2 and 87.6 minutes, "
            "so today it is worth between a tenth and a third of the whole dispatch.\n\n"
            "False runs the rest of the flow and skips that half: the fixed corpus, "
            "the real server over it, the machine record and the committed host row "
            "all still happen. What is given up is the prefill and decode rates, and "
            "with them the dossier - a dossier is both cases, so a dispatch that "
            "skipped one emits the server half and a line saying which half is "
            "missing rather than a page that reads whole.\n\n"
            "It also moves who pays for the weights. The speed case fills the cache "
            "entry the server case restores, so a dispatch that skips it downloads "
            "the candidate once in the server case instead - the same bytes, in a "
            "different job.\n\n"
            "`measure.yml`'s `model_speed_case` dispatch input overrules this for one "
            "run without a commit: `config` follows this knob, `run` and `skip` do "
            "not. This is operator control rather than a feature behind a flag, so "
            "there is no second implementation waiting behind it - the same jobs run "
            "either way and one of them is not dispatched."
        ),
    )
