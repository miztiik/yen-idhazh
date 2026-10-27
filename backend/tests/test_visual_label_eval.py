"""Does one reviewer contribute only one non-conflicting answer per visual?"""

from __future__ import annotations

import pytest
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.visual_label import VisualLabel, VisualLabelRow
from idhazh.evals.visual_labels import collapse_visual_label_rows

pytestmark = pytest.mark.visual


def _label_row() -> VisualLabelRow:
    return VisualLabelRow.from_json(
        read_text(
            CONTRACT_FIXTURES_DIR
            / "visual-label-row"
            / "one-reviewer-keeps-a-pie.json"
        )
    )


def test_identical_reviewer_answers_collapse_to_one_response() -> None:
    row = _label_row()

    assert collapse_visual_label_rows((row, row)) == (row,)


def test_one_reviewer_cannot_give_conflicting_labels_for_a_visual() -> None:
    row = _label_row()
    conflict = row.model_copy(update={"label": VisualLabel.DISCARD})

    with pytest.raises(ValueError, match="conflicting labels"):
        collapse_visual_label_rows((row, conflict))
