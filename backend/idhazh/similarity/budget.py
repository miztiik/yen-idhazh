"""Does a night's draw of pairs fit the unit of work the council hands out?

This judge's own arithmetic over this judge's own measured cost. It asks the
council for one number - how long a unit has to work in - and reads the rest
from its own block, so neither side holds the other's figure.

**It is here and not on `AppConfig` because the cost below is one judge's
reading.** A validator on the shared config put a measured per-pair figure in
the import closure of every module that reads config, the council's own included
(`docs/architecture/publishing/llm-council.md`). A second tenant's unit of work
costs something else entirely, so there is nothing for it to share.
"""

from __future__ import annotations

import math
from typing import Final

from idhazh.contracts.app_config import AppConfig
from idhazh.council.deadline import compute_shard_deadline

#: Wall clock for one judged pair - both readings of it - in seconds. The worst
#: pair measured rather than the average one, because a bound has to survive a
#: bad night: 110.98 s against a mean of 94.53 and a best of 72.80, population sd
#: 7.84, over the 82 pairs of run 2026-09-18-35339202390. Judged 2026-09-18
#: across four stock ubuntu-latest runners on Qwen3.5-9B-Q4_K_M, and the four
#: shards' means spread 88.24 to 99.89 s - a 13.2 percent difference from the
#: machine alone (docs/reference/benchmarks/what-a-judge-pair-costs.md).
#: Denominated in pairs and not calls: a pair's second call re-reads the first
#: one's prompt prefix, so halving this would be a guess with the direction known
#: and the size unknown.
SECONDS_A_JUDGED_PAIR: Final = 110.98


def refuse_a_night_this_tenant_cannot_finish(app: AppConfig) -> None:
    """A draw a unit cannot finish is a job GitHub kills with nothing uploaded.

    Read when the council resolves this tenant, which the planning job does
    before it can build its matrix - so a budget that cannot fit stops the night
    before a runner has restored any weights.

    Against the window a unit really has rather than against the whole bound.
    The venue spends the preamble before the judging process exists and keeps the
    reserve back for the records and the upload, so a draw sized against the
    bound is accepted here and cut off at runtime. The window comes from the
    council's own clock function rather than from a second copy of the
    subtraction.

    The refusal prints the arithmetic and names the three knobs, because a person
    raising the budget has to choose between them and a bare comparison says
    which one it is not.
    """
    knobs = app.assemble.same_story.adaptive_dedup_threshold
    if knobs is None:
        return
    council = app.council
    a_shard = math.ceil(knobs.pair_budget / council.shards)
    seconds = a_shard * SECONDS_A_JUDGED_PAIR
    window = compute_shard_deadline(council, started=0.0)
    if seconds <= window:
        return
    raise ValueError(
        f"pair_budget {knobs.pair_budget} over {council.shards} shards is {a_shard} pairs "
        f"a shard, which at {SECONDS_A_JUDGED_PAIR} s a pair is {seconds:.0f} s against "
        f"the {window:.0f} s a unit has to work in - council.shard_timeout_minutes of "
        f"{council.shard_timeout_minutes} less shard_preamble_minutes "
        f"{council.shard_preamble_minutes} and shard_wrap_up_minutes "
        f"{council.shard_wrap_up_minutes}. Lower pair_budget, raise council.shards, or "
        "raise the timeout - which may not go past GitHub's 6 h job ceiling"
    )
