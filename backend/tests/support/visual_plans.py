"""Build current plans from frozen source-reference examples without rewriting evidence."""

from pathlib import Path

from idhazh.contracts.visual import VisualPlan
from idhazh.visual_vocabulary import PLAN_VOCABULARY_VERSION


def current_plan(path: Path) -> VisualPlan:
    """Keep the saved references and let code stamp the vocabulary, as the producer does."""
    return VisualPlan.model_validate(
        VisualPlan.read(path).model_dump(mode="json") | {"plan_version": PLAN_VOCABULARY_VERSION}
    )
