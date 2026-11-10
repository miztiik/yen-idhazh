"""How are native event bindings shown without treating candidates as verified events?"""

from project_gliner_analysis import EVENT_FIELDS, event_structure
from render_tables import read_list, read_object, render_cell, render_table


def _mention(value: object) -> str:
    leaf = read_object(value)
    text = render_cell(leaf["text"])
    metadata = []
    if "start" in leaf:
        metadata.append(f"[{leaf['start']}, {leaf['end']})")
    if "confidence" in leaf:
        metadata.append("score " + render_cell(leaf["confidence"]))
    return text + (" (" + "; ".join(metadata) + ")" if metadata else "")


def render_gliner_events(
    request: dict[str, object] | None, result: dict[str, object] | None
) -> str:
    """Keep candidate order, optional roles and aggregate scores separate from leaf evidence."""
    note = (
        "Linked candidates, not verified completed events. Each row keeps the native action "
        "and its own participants, times and places in returned order. Missing roles stay empty; "
        "positions and field scores appear only when returned. Record scores are native "
        "aggregates, not calibrated correctness probabilities."
    )
    if event_structure(request) is None:
        empty = "Not requested: the saved extraction schema did not select event records."
        records: list[dict[str, object]] = []
    elif result is None:
        empty = "Failed: no successful event evidence is available; see the provider outcome."
        records = []
    elif "events" not in result:
        empty = "No candidates were returned; the successful native result omitted empty records."
        records = []
    else:
        empty = "No candidates were returned for the requested event structure."
        records = [read_object(record) for record in read_list(result["events"])]
    aggregate = any("confidence" in record for record in records)
    rows = []
    for record in records:
        row = [_mention(record["action"])]
        for name in EVENT_FIELDS[1:]:
            row.append("<br>".join(_mention(value) for value in read_list(record[name])))
        if aggregate:
            row.append(render_cell(record["confidence"]) if "confidence" in record else "")
        rows.append(row)
    return render_table(
        "M", "Event candidates",
        ["Action", "Actors", "Objects", "Times", "Places"]
        + (["Record score"] if aggregate else []),
        rows, note, empty=empty,
    )
