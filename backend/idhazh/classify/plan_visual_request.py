"""Which source elements and visual rules can this item's planning request use?"""

from __future__ import annotations

import json
from typing import Any, Final

from idhazh.contracts.element import (
    ELEMENT_ID_PATTERN,
    ElementTable,
)
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import EncodingRole, VisualType
from idhazh.sanitize import untrusted_block
from idhazh.visual_vocabulary import ROLE_KINDS, TYPE_RULES, VALUE_ROLES

#: What the model is shown of each element: its address, what kind of fact it is, the
#: article's own words and the reading code took from them. No sentence address, and
#: no judgement: nothing in the pipeline labels an element any more, so the menu is
#: the table and nothing the table does not hold.
PLANNING_COLUMNS: Final = ("element_id", "kind", "span_excerpt", "value", "unit")


def planning_menu(table: ElementTable) -> str:
    """Project the exact table into compact, fenced item data."""
    rows = []
    for element in table.elements:
        cells = element.model_dump(mode="json")
        rows.append([cells[name] for name in PLANNING_COLUMNS])
    data = {"columns": PLANNING_COLUMNS, "rows": rows}
    return untrusted_block(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def bind_reference_choices(schema: dict[str, Any], table: ElementTable) -> None:
    """Bind only the derived request's reference leaves, never its persisted model."""
    ids = [element.element_id for element in table.elements]
    definitions = schema["$defs"]
    plan = definitions["VisualPlanDraft"]["properties"]
    encodings = definitions["PlanEncodings"]["properties"]
    for field in [*plan.values(), *encodings.values()]:
        if field.get("type") != "array" or field["items"].get("pattern") != ELEMENT_ID_PATTERN:
            continue
        if ids:
            field["items"] = {"type": "string", "enum": ids}
        else:
            field["maxItems"] = 0
    whole = plan["declared_whole_element_id"]
    if ids:
        whole["anyOf"] = [{"type": "string", "enum": ids}, {"type": "null"}]
    else:
        whole.pop("anyOf")
        whole["type"] = "null"


def type_role_guide(visuals: VisualsConfig) -> str:
    """Read the configured request vocabulary and evidence floors."""
    selected = visuals.select_types()
    used = {
        role
        for visual_type in selected
        for role in TYPE_RULES[visual_type].required | TYPE_RULES[visual_type].optional
    }
    roles = "; ".join(
        f"{role.value}={','.join(sorted(kind.value for kind in ROLE_KINDS[role]))}"
        for role in EncodingRole
        if role in used
    )
    lines = [
        "Numeric chart guide.",
        "Channel kinds: " + roles + ".",
        "Measured channels: "
        + ", ".join(sorted(role.value for role in VALUE_ROLES))
        + "; units within each must be convertible, but units alone do not prove comparability.",
    ]
    for visual_type in selected:
        rules = TYPE_RULES[visual_type]
        required = ",".join(role.value for role in EncodingRole if role in rules.required)
        optional = ",".join(role.value for role in EncodingRole if role in rules.optional) or "none"
        if visual_type is VisualType.HISTOGRAM:
            marks = (
                f"at least {visuals.histogram_bins} source quantities for "
                f"{visuals.histogram_bins} code-computed bins"
            )
        else:
            ceiling = (
                visuals.max_pie_parts if visual_type is VisualType.PIE else visuals.max_chart_points
            )
            marks = f"{visuals.min_chart_points}..{ceiling} marks in {rules.marks.value}"
        lines.append(
            f"{visual_type.value}: required {required}; optional {optional}; {marks}."
        )
    return "\n".join(lines)
