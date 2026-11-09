"""How do saved article classifications retain their taxonomy, order and native scores?"""

from dataclasses import dataclass

from render_tables import (
    read_list,
    read_object,
    read_score,
    read_text,
    render_cell,
    render_error,
    render_table,
)

# These names and cardinalities implement the article taxonomy contract.
ARTICLE_TASKS = (
    ("desk", "verticals", False),
    ("lenses", "lenses", True),
    ("events", "events", True),
)


@dataclass(frozen=True)
class ClassificationReport:
    request: dict[str, object] | None
    result: dict[str, object] | None
    content: str


def active_classification_tasks(taxonomy: dict[str, object]) -> dict[str, object]:
    """Project the native-validated taxonomy, never a private vocabulary or schema."""
    tasks: dict[str, object] = {}
    for name, vocabulary, multi_label in ARTICLE_TASKS:
        labels: dict[str, str] = {}
        for value in read_list(taxonomy[vocabulary]):
            entry = read_object(value)
            if entry.get("status", "active") != "active":
                continue
            label = read_text(entry["id"], nonblank=True)
            if label in labels:
                raise ValueError(f"Classification task {name} has duplicate active IDs.")
            definition = read_text(entry["definition"], nonblank=True)
            labels[label] = definition
        if not labels:
            raise ValueError(f"Classification task {name} has no active labels.")
        tasks[name] = {"labels": labels, "multi_label": multi_label}
    return tasks


def read_classification_tasks(value: object) -> dict[str, dict[str, object]]:
    tasks = {}
    for name, raw_task in read_object(value).items():
        read_text(name, nonblank=True)
        task = read_object(raw_task, {"labels", "multi_label"})
        labels = read_object(task["labels"])
        if not labels or type(task["multi_label"]) is not bool:
            raise ValueError("Classification tasks require labels and a boolean mode.")
        for label, definition in labels.items():
            read_text(label, nonblank=True)
            read_text(definition, nonblank=True)
        tasks[name] = task
    if not tasks:
        raise ValueError("Classification requires at least one task.")
    return tasks


def read_classification_selections(
    result: dict[str, object], tasks: dict[str, dict[str, object]]
) -> dict[str, list[dict[str, object]]]:
    """Validate request membership and cardinality as well as native score shape."""
    native = read_object(read_object(result, {"classifications"})["classifications"])
    if native.keys() != tasks.keys():
        raise ValueError("Classification results must retain every requested task.")
    selections = {}
    for name, task in tasks.items():
        labels = read_object(task["labels"])
        selected = [read_object(value, {"id", "score"}) for value in read_list(native[name])]
        if not task["multi_label"] and len(selected) > 1:
            raise ValueError("A single-label task returned multiple selections.")
        ids = [read_text(value["id"], nonblank=True) for value in selected]
        if len(set(ids)) != len(ids) or any(label not in labels for label in ids):
            raise ValueError("Classification selections must be unique requested IDs.")
        for value in selected:
            read_score(value["score"], confidence=True)
        selections[name] = selected
    return selections


def render_classifications(
    source: str,
    response: dict[str, object] | None,
    *,
    request: dict[str, object] | None = None,
    taxonomy: dict[str, object] | None = None,
    error: str | None = None,
) -> ClassificationReport:
    """Render one independent operation using only its saved native evidence."""
    tasks: dict[str, dict[str, object]] = {}
    names: dict[str, dict[str, str]] = {}
    if request is not None:
        read_object(request, {"text", "tasks"})
        if read_text(request["text"], nonblank=True) != source:
            raise ValueError("Classification source differs from the displayed source.")
        tasks = read_classification_tasks(request["tasks"])
        if taxonomy is None:
            raise ValueError("Classification requires its saved taxonomy.")
        expected = read_classification_tasks(active_classification_tasks(taxonomy))
        if tasks != expected:
            raise ValueError("Classification offerings differ from the saved taxonomy.")
        if list(tasks) != [name for name, _, _ in ARTICLE_TASKS]:
            raise ValueError("Classification tasks must retain taxonomy task order.")
        if any(
            list(read_object(task["labels"])) != list(read_object(expected[name]["labels"]))
            for name, task in tasks.items()
        ):
            raise ValueError("Classification labels must retain taxonomy vocabulary order.")
        for name, vocabulary, _ in ARTICLE_TASKS:
            entries = [read_object(value) for value in read_list(taxonomy[vocabulary])]
            names[name] = {
                read_text(entry["id"]): read_text(entry["display_name"], nonblank=True)
                for entry in entries
                if entry.get("status", "active") == "active"
            }
    result = None
    selections: dict[str, list[dict[str, object]]] = {}
    if error is not None:
        if response is not None:
            raise ValueError("Classification cannot have both a response and a transport error.")
        outcome = "Classification error: " + render_cell(read_text(error, nonblank=True))
    elif response is None:
        outcome = "Classification unavailable: no response was saved."
    elif "error" in response:
        outcome = "Classification error: " + render_error(read_object(response, {"error"})["error"])
    else:
        if not tasks:
            raise ValueError("Classification results require their saved request and taxonomy.")
        selections = read_classification_selections(response, tasks)
        result = response
        outcome = "Classification status: complete."
    rows = []
    for name in tasks:
        for selection in selections.get(name, []):
            label = read_text(selection["id"])
            rows.append(
                [
                    render_cell(name),
                    render_cell(label),
                    render_cell(names[name][label]),
                    render_cell(selection["score"]),
                ]
            )
        if not selections.get(name):
            rows.append(
                [
                    render_cell(name),
                    "No label selected" if result is not None else "Unavailable",
                    "-",
                    "-",
                ]
            )
    content = render_table(
        "L",
        "Article classification",
        ["Task", "Selected label ID", "Display name", "Native score"],
        rows,
        outcome + "\n\nGLiNER native scores range from zero to one; higher means stronger model "
        "confidence, not calibrated correctness percentages. Long-text classifier scores "
        "can aggregate chunks. Task order follows classification/request.json; each task "
        "keeps returned selection order. Empty native selections remain empty, not errors "
        "or invented labels. The native multi-label policy can retain its strongest label "
        "even when none meets its internal selection threshold; it does not guarantee abstention.",
        empty="No classification selections are available; see the operation outcome.",
    )
    return ClassificationReport(request, result, content)
