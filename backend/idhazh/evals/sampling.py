"""Which runs the faithfulness scorer runs on, when the rate is below one.

**The unit is the run.** Not the item, and not the shard. A run scores every
item or it scores none, so a day's eval rows are never a partial view of that
day and no page has to explain a denominator that moved under it. A day with
three of four shards scored would have a wrong denominator that nothing on any
surface could name.

Selection is a digest of the run id, so it is reproducible from the committed
manifest alone a year later, and it is blind to everything about the run - a
selector that could see an outcome would bias the ledger it is thinning.

This is collection-time thinning, not display-time thinning. An unsampled run
is never scored, so its rows do not exist and nothing is filtered in a browser.
The rule that follows from that is stated once, in
`docs/concepts/evaluation.md`: a published RATE is computed from the item-health
census, which is never sampled, and the sampled ledger publishes distributions
only. A median survives a sample; a rate does not.
"""

from __future__ import annotations

import hashlib
from typing import Final

#: The run id is hashed and its first eight bytes are read as one integer, so a
#: position is one of this many equally likely values.
POSITIONS: Final = 2**64


def position_of(run_id: str) -> float:
    """This run's fixed place in `[0, 1)`. The same id gives the same number forever."""
    digest = hashlib.sha256(run_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / POSITIONS


def run_is_sampled(run_id: str, sample_rate: float) -> bool:
    """Whether this run scores at all.

    The rate is compared against the run's own fixed position, so raising the
    rate only ever adds runs - it never swaps one run for another, and a run
    that scored yesterday under a lower rate still scores today.

    A rate of one short-circuits rather than falling through the comparison,
    because a position near enough to one rounds to exactly `1.0` as a float and
    `1.0 < 1.0` is false. The short-circuit is what makes "the default changes
    nothing" true by construction instead of by floating-point luck.
    """
    if sample_rate >= 1.0:
        return True
    return position_of(run_id) < sample_rate
