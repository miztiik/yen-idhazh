"""Which native version and score dimensions identify a UniEval operation?"""

from typing import Final, Literal

from pydantic import ConfigDict

from .base import NativeContract

UNIEVAL_VERSION: Final = "2026-11-04"
UnievalVersion = Literal["2026-11-04"]
Dimension = Literal["fluency", "coherence", "consistency", "relevance"]
SourceMode = Literal["all_source_windows", "full_source_prompt"]
# This order is part of the private progress protocol, not a model or quality ranking.
DIMENSIONS: Final[tuple[Dimension, ...]] = (
    "fluency",
    "coherence",
    "relevance",
    "consistency",
)


class UnievalContract(NativeContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": UNIEVAL_VERSION,
            "changelog": [
                {
                    "version": UNIEVAL_VERSION,
                    "change": "Declare four-score evaluation with complete source handling.",
                }
            ],
        }
    )
