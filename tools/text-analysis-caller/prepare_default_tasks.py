"""How is the optional default classification request built from current taxonomy labels?"""

from render_tables import read_list, read_object, read_text


def _active_labels(values: object, text_field: str) -> dict[str, str]:
    labels = {}
    for value in read_list(values):
        entry = read_object(value)
        if entry.get("status", "active") != "active":
            continue
        label = read_text(entry["id"], nonblank=True)
        if label in labels:
            raise ValueError("Default classification labels have duplicate active IDs.")
        labels[label] = read_text(entry[text_field], nonblank=True)
    if not labels:
        raise ValueError("Default classification has no active labels.")
    return labels


def default_classification_tasks(taxonomy: dict[str, object]) -> dict[str, object]:
    """Build convenience request data, never an allowed or required task list."""
    verticals = _active_labels(taxonomy["verticals"], "definition")
    return {
        "vertical": {"labels": verticals, "multi_label": False},
        "desk": {"labels": verticals, "multi_label": False},
        "lenses": {
            "labels": _active_labels(taxonomy["lenses"], "definition"),
            "multi_label": True,
        },
        "source_kind": {
            "labels": _active_labels(taxonomy["source_kinds"], "display_name"),
            "multi_label": False,
        },
    }
