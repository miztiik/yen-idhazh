"""Which source elements and visual rules can this item's planning request use?"""

from __future__ import annotations

import json
from typing import Any

from idhazh.contracts.element import (
    ELEMENT_ID_PATTERN,
    JUDGED_FIELDS,
    TIER_ONE_FIELDS,
    ElementTable,
)
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import EncodingRole, VisualType
from idhazh.contracts.whowhat_grid import MAX_WHOWHAT_ROWS
from idhazh.render.chart import can_compile
from idhazh.sanitize import untrusted_block
from idhazh.visual_vocabulary import ROLE_KINDS, TYPE_RULES, VALUE_ROLES


def planning_menu(table: ElementTable) -> str:
    """Project the exact finalized table into compact, fenced item data."""
    rows = []
    labels = {}
    for element in table.elements:
        cells = element.model_dump(mode="json")
        rows.append([cells[name] for name in TIER_ONE_FIELDS])
        judged = {name: cells[name] for name in JUDGED_FIELDS if cells[name] is not None}
        if judged:
            labels[element.element_id] = judged
    data = {"columns": TIER_ONE_FIELDS, "rows": rows, "labels": labels}
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
    roles = "; ".join(
        f"{role.value}={','.join(sorted(kind.value for kind in ROLE_KINDS[role]))}"
        for role in EncodingRole
    )
    lines = [
        "Type/role guide. Request names are not a promise that a compiler exists.",
        "Channel kinds: " + roles + ".",
        "Measured channels: "
        + ", ".join(sorted(role.value for role in VALUE_ROLES))
        + "; values within each must have convertible units.",
    ]
    for visual_type in visuals.select_types():
        rules = TYPE_RULES.get(visual_type)
        if rules is None:
            lines.append(f"{visual_type.value}: no role rule or compiler.")
            continue
        required = ",".join(role.value for role in EncodingRole if role in rules.required)
        optional = ",".join(role.value for role in EncodingRole if role in rules.optional) or "none"
        if visual_type is VisualType.WHOWHAT:
            marks = (
                f"1..{MAX_WHOWHAT_ROWS} actor/claim rows, not a numeric chart; "
                "entity accepts entity only, event_label accepts claim only; "
                "select one actor and one claim from the same sentence per row; "
                "multiple selected actors or claims in one sentence are ambiguous"
            )
        elif visual_type is VisualType.HISTOGRAM:
            marks = (
                f"at least {visuals.histogram_bins} bins values for "
                f"{visuals.histogram_bins} code-computed bins"
            )
        else:
            ceiling = (
                visuals.max_pie_parts if visual_type is VisualType.PIE else visuals.max_chart_points
            )
            marks = f"{visuals.min_chart_points}..{ceiling} marks in {rules.marks.value}"
        capability = (
            "" if visual_type is VisualType.WHOWHAT or can_compile(visual_type) else "; no compiler"
        )
        lines.append(
            f"{visual_type.value}: required {required}; optional {optional}; {marks}{capability}."
        )
    lines.extend(
        (
            "Chart example: bar pairs source category ids with comparable quantity ids; "
            "use the configured mark floor and leave unused channels empty.",
            "Grid example: whowhat pairs an entity id with a claim id in their shared sentence; "
            "no quantity is required.",
            "Decline example: decision none; purpose, type, declared_whole_element_id, title "
            "and caption null; every encoding and reference list empty; why explains "
            "unsupported evidence or a picture that would only repeat the prose.",
        )
    )
    return "\n".join(lines)
