"""Scoring a summary, and knowing what each score cannot see.

`metrics.py` holds the model-free counterweights. They run on every item, cost
effectively nothing, and stay meaningful even if the faithfulness scorer is
swapped or dropped.
"""

from idhazh.evals.metrics import (
    METRICS_VERSION,
    compression,
    extractiveness,
    hedge_dropped,
    lead_coverage,
    scorer_version,
    unsupported_numbers,
    verbatim_run,
    word_count,
)

__all__ = [
    "METRICS_VERSION",
    "compression",
    "extractiveness",
    "hedge_dropped",
    "lead_coverage",
    "scorer_version",
    "unsupported_numbers",
    "verbatim_run",
    "word_count",
]
