"""When do the requested type and its recorded delivery form one complete outcome?"""

from idhazh.contracts.visual_type import VisualType


def validate_visual_outcome(
    planned_type: VisualType | None,
    rendered_type: VisualType | None,
    downgrade_depth: int | None,
    marks: int | None,
) -> None:
    """Validate both the decision and its stored item-health projection."""
    if planned_type is None:
        if any(value is not None for value in (rendered_type, downgrade_depth, marks)):
            raise ValueError("visual outcome measurements require a planned_type")
        return
    if downgrade_depth is None:
        raise ValueError("a measured visual request records its downgrade_depth")
    if rendered_type is None:
        if marks is not None:
            raise ValueError("only a rendered visual records delivered marks")
        return
    if marks is None:
        raise ValueError("a rendered type records its delivered marks")
    if (planned_type is rendered_type) != (downgrade_depth == 0):
        raise ValueError("a rendered replacement changes type and has positive downgrade_depth")
