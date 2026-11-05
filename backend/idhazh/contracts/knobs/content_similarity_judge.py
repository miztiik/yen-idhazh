"""Which execution settings belong only to the content-similarity judge?"""

from pydantic import Field

from idhazh.contracts.base import Model


class ContentSimilarityJudgeConfig(Model):
    """The draw budget, verdict flush cadence and decoder temperature."""

    pair_budget: int = Field(
        ge=1,
        description=(
            "Pairs a day to judge. 200 over four shards is 50 pairs a shard, "
            "which costs 1 hour 32 minutes at the measured worst of 110.98 seconds "
            "a pair. The judge refuses a draw that cannot fit the council's window."
        ),
    )
    flush_every_pairs: int = Field(
        ge=1,
        description=(
            "Pairs completed before rewriting the verdict file. One preserves every "
            "completed pair if a shard dies; the bounded rewrite is cheap beside a call."
        ),
    )
    judge_temperature: float = Field(
        ge=0.0,
        le=2.0,
        description=(
            "Decoder temperature for both orders. Zero measures order disagreement "
            "without adding sampling noise; the summarizer's temperature stays separate."
        ),
    )


class ContentSimilarityEvaluationConfig(Model):
    """The explicit offline input ceiling and event-group interval settings."""

    max_cases: int = Field(default=200, strict=True, gt=0)
    confidence_level: float = Field(default=0.95, gt=0, lt=1, allow_inf_nan=False)
    resamples: int = Field(default=2000, strict=True, gt=0)
    resample_seed: int = Field(default=0, strict=True)
