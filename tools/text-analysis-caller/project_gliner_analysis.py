"""How do historical and unified GLiNER wire payloads become report-only evidence?"""

from render_tables import read_list, read_object, read_text


def project_entity_request(request: dict[str, object]) -> dict[str, object]:
    """Keep historical inputs readable without accepting damaged current inputs as old ones."""
    if "schema" not in request:
        return read_object(request, {"text", "labels"})
    read_object(request, {"text", "schema"})
    schema = read_object(request["schema"], {"entities"})
    return {"text": request["text"], "labels": schema["entities"]}


def project_entity_result(
    response: dict[str, object], request: dict[str, object] | None
) -> dict[str, object]:
    """Flatten only the caller's native entity map, leaving the saved bytes untouched."""
    if request is None or "schema" not in request:
        return read_object(response, {"entities"})
    native = read_object(read_object(response, {"result"})["result"], {"entities"})
    entities = []
    for label, values in read_object(native["entities"]).items():
        for value in read_list(values):
            mention = read_object(value, {"text", "confidence", "start", "end"})
            entities.append(
                {
                    "text": mention["text"],
                    "label": label,
                    "score": mention["confidence"],
                    "start_char": mention["start"],
                    "end_char": mention["end"],
                }
            )
    return {"entities": entities}


def project_classification_request(request: dict[str, object]) -> dict[str, object]:
    """Read only the caller's classification schema, preserving task and label order."""
    if "schema" not in request:
        return read_object(request, {"text", "tasks"})
    read_object(request, {"text", "schema"})
    schema = read_object(request["schema"], {"classifications"})
    tasks: dict[str, object] = {}
    for value in read_list(schema["classifications"]):
        task = read_object(value, {"task", "labels", "multi_label"})
        name = read_text(task["task"], nonblank=True)
        if name in tasks:
            raise ValueError("Saved classification task names must be distinct.")
        tasks[name] = {"labels": task["labels"], "multi_label": task["multi_label"]}
    return {"text": request["text"], "tasks": tasks}


def project_classification_result(
    response: dict[str, object], request: dict[str, object]
) -> dict[str, object]:
    """Translate native selections for display without re-scoring or sorting them."""
    if "schema" not in request:
        return read_object(response, {"classifications"})
    classifications: dict[str, object] = {}
    for name, prediction in read_object(read_object(response, {"result"})["result"]).items():
        values = prediction if isinstance(prediction, list) else [prediction]
        selections = []
        for value in values:
            selection = read_object(value, {"label", "confidence"})
            selections.append({"id": selection["label"], "score": selection["confidence"]})
        classifications[name] = selections
    return {"classifications": classifications}
