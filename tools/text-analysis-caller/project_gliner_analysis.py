"""How do historical and unified GLiNER wire payloads become report-only evidence?"""

from render_tables import read_integer, read_list, read_object, read_score, read_text

# These names identify the caller's linked-record protocol, not an NER vocabulary.
EVENT_FIELDS = ("action", "actors", "objects", "times", "places")
OUTPUT_CONTROLS = ("include_confidence", "include_spans")


def _native_request(request: dict[str, object]) -> dict[str, object]:
    if not {"text", "schema"}.issubset(request) or request.keys() - {
        "text", "schema", *OUTPUT_CONTROLS,
    }:
        raise ValueError("Invalid saved native request fields.")
    read_text(request["text"], nonblank=True)
    for name in OUTPUT_CONTROLS:
        if name in request and type(request[name]) is not bool:
            raise ValueError("Native output controls must be booleans.")
    return read_object(request["schema"])


def _entity_configuration(value: object) -> dict[str, dict[str, object]]:
    if isinstance(value, list):
        labels = [read_text(label, nonblank=True) for label in value]
        if not labels or len(set(labels)) != len(labels):
            raise ValueError("Entity labels must be nonempty and distinct.")
        return {label: {} for label in labels}
    entities = read_object(value)
    if not entities:
        raise ValueError("Entity labels must not be empty.")
    configurations = {}
    for label, raw in entities.items():
        read_text(label, nonblank=True)
        if isinstance(raw, str):
            configuration: dict[str, object] = {"description": read_text(raw, nonblank=True)}
        else:
            configuration = read_object(raw)
            if configuration.keys() - {"description", "dtype", "threshold"}:
                raise ValueError("Unknown native entity configuration.")
            if configuration.get("description") is not None:
                read_text(configuration["description"], nonblank=True)
            if configuration.get("dtype") not in (None, "str", "list"):
                raise ValueError("Invalid native entity dtype.")
            if configuration.get("threshold") is not None:
                read_score(configuration["threshold"], confidence=True)
        configurations[label] = configuration
    return configurations


def event_structure(request: dict[str, object] | None) -> dict[str, object] | None:
    """Read the caller's action-anchored template without loading any runtime."""
    if request is None or "schema" not in request:
        return None
    schema = _native_request(request)
    if "structures" not in schema:
        return None
    structures = read_object(schema["structures"], {"events"})
    structure = read_object(structures["events"])
    if (
        not {"fields", "mode", "anchor"}.issubset(structure)
        or structure.keys() - {"fields", "mode", "anchor", "occurrence_policy"}
        or structure["mode"] != "natural"
        or structure["anchor"] != "action"
    ):
        raise ValueError("Events require the native action-anchored structure.")
    if structure.get("occurrence_policy") not in (
        None, "all", "first", "error_on_ambiguous", "latent_all",
    ):
        raise ValueError("Invalid native occurrence policy.")
    fields = [read_object(field) for field in read_list(structure["fields"])]
    if [field.get("name") for field in fields] != list(EVENT_FIELDS):
        raise ValueError("Event fields must retain their declared role order.")
    for index, field in enumerate(fields):
        if field.keys() - {
            "name", "dtype", "description", "threshold", "cardinality", "exclusive",
        }:
            raise ValueError("Unknown native event field.")
        if (
            field.get("dtype") != ("str" if index == 0 else "list")
            or field.get("cardinality") != ("required_one" if index == 0 else "zero_or_more")
            or type(field.get("exclusive", False)) is not bool
        ):
            raise ValueError("Event roles require their native dtype and cardinality.")
        if field.get("description") is not None:
            read_text(field["description"], nonblank=True)
        if field.get("threshold") is not None:
            read_score(field["threshold"], confidence=True)
    return structure


def _output_profile(
    request: dict[str, object], leaves: list[object], *, classification: bool = False
) -> tuple[bool, bool]:
    if any(name in request for name in OUTPUT_CONTROLS):
        return (
            bool(request.get("include_confidence", False)),
            bool(request.get("include_spans", False)),
        )
    if all(isinstance(value, str) for value in leaves):
        return False, False
    keys = {"label", "confidence"} if classification else {"text", "confidence", "start", "end"}
    if all(isinstance(value, dict) and value.keys() == keys for value in leaves):
        return True, True
    raise ValueError("Flagless native evidence must be wholly historical-rich or current-compact.")


def _values(value: object, *, scalar: bool) -> list[object]:
    if scalar:
        return [] if value is None or value == "" else [value]
    return read_list(value)


def _leaf(value: object, source: str, profile: tuple[bool, bool]) -> dict[str, object]:
    confidence, spans = profile
    if not confidence and not spans:
        text = read_text(value, nonblank=True)
        if text not in source:
            raise ValueError("Native source-backed evidence must occur verbatim in the input.")
        return {"text": text}
    keys = {"text"} | ({"confidence"} if confidence else set()) | (
        {"start", "end"} if spans else set()
    )
    leaf = read_object(value, keys)
    text = read_text(leaf["text"], nonblank=True)
    if confidence:
        read_score(leaf["confidence"], confidence=True)
    if not spans and text not in source:
        raise ValueError("Native source-backed evidence must occur verbatim in the input.")
    if spans:
        start, end = read_integer(leaf["start"]), read_integer(leaf["end"])
        if start >= end or end > len(source) or source[start:end] != text:
            raise ValueError("Native evidence does not match the saved Unicode source.")
    return leaf


def _records(
    value: object, structure: dict[str, object], source: str, profile: tuple[bool, bool]
) -> list[dict[str, object]]:
    records = []
    seen_records = set()
    bound: set[tuple[int, int]] = set()
    exclusive: set[tuple[int, int]] = set()
    fields = [read_object(field) for field in read_list(structure["fields"])]
    for raw_record in read_list(value):
        raw = read_object(raw_record)
        if raw.keys() - {"confidence"} != set(EVENT_FIELDS):
            raise ValueError("Event candidates must retain exactly their declared roles.")
        record: dict[str, object] = {}
        if "confidence" in raw:
            read_score(raw["confidence"], confidence=True)
            record["confidence"] = raw["confidence"]
        record_identity = []
        for field in fields:
            name = read_text(field["name"])
            values = _values(raw[name], scalar=name == "action")
            if name == "action" and not values:
                raise ValueError("Event candidates require a nonempty action.")
            leaves = [_leaf(item, source, profile) for item in values]
            record[name] = leaves[0] if name == "action" else leaves
            seen = set()
            if profile[1]:
                for leaf in leaves:
                    identity = (read_integer(leaf["start"]), read_integer(leaf["end"]))
                    if identity in seen or identity in exclusive or (
                        field.get("exclusive", False) and identity in bound
                    ):
                        raise ValueError("Event occurrences violate native binding constraints.")
                    seen.add(identity)
                    bound.add(identity)
                    if field.get("exclusive", False):
                        exclusive.add(identity)
            record_identity.append((name, frozenset(seen)))
        identity_record = tuple(record_identity)
        if profile[1]:
            if identity_record in seen_records:
                raise ValueError("Event candidates must retain distinct source bindings.")
            seen_records.add(identity_record)
        records.append(record)
    return records


def project_entity_request(request: dict[str, object]) -> dict[str, object]:
    """Keep historical inputs readable without accepting damaged current inputs as old ones."""
    if "schema" not in request:
        return read_object(request, {"text", "labels"})
    schema = _native_request(request)
    if "entities" not in schema or schema.keys() - {"entities", "structures"}:
        raise ValueError("The caller extraction schema requires entities and optional events.")
    entities = _entity_configuration(schema["entities"])
    event_structure(request)
    return {"text": request["text"], "labels": list(entities)}


def project_entity_result(
    response: dict[str, object], request: dict[str, object] | None
) -> dict[str, object]:
    """Flatten only the caller's native entity map, leaving the saved bytes untouched."""
    if request is None or "schema" not in request:
        historical = read_object(response, {"entities"})
        for value in read_list(historical["entities"]):
            read_object(value, {"text", "label", "score", "start_char", "end_char"})
        return historical
    project_entity_request(request)
    schema = read_object(request["schema"])
    configured = _entity_configuration(schema["entities"])
    structure = event_structure(request)
    native = read_object(read_object(response, {"result"})["result"])
    if "entities" not in native or native.keys() - (
        {"entities", "events"} if structure is not None else {"entities"}
    ):
        raise ValueError("Native extraction returned missing or unknown tasks.")
    raw_entities = read_object(native["entities"])
    if raw_entities.keys() - configured.keys():
        raise ValueError("Native entity types must belong to the saved request.")
    leaves = []
    for label, values in raw_entities.items():
        leaves.extend(_values(values, scalar=configured[label].get("dtype") == "str"))
    if "events" in native:
        for value in read_list(native["events"]):
            record = read_object(value)
            if record.keys() - {"confidence"} != set(EVENT_FIELDS):
                raise ValueError("Event candidates must retain exactly their declared roles.")
            for name in EVENT_FIELDS:
                leaves.extend(_values(record[name], scalar=name == "action"))
    profile = _output_profile(request, leaves)
    source = read_text(request["text"], nonblank=True)
    entities = []
    for label, values in raw_entities.items():
        seen = set()
        for value in _values(values, scalar=configured[label].get("dtype") == "str"):
            mention = _leaf(value, source, profile)
            entity = {"text": mention["text"], "label": label}
            if profile[0]:
                entity["score"] = mention["confidence"]
            if profile[1]:
                entity |= {"start_char": mention["start"], "end_char": mention["end"]}
                identity = (read_integer(mention["start"]), read_integer(mention["end"]))
                if identity in seen:
                    raise ValueError("Native entity occurrences must be distinct.")
                seen.add(identity)
            entities.append(entity)
    projected: dict[str, object] = {"entities": entities}
    if structure is not None and "events" in native:
        projected["events"] = _records(native["events"], structure, source, profile)
    return projected


def project_classification_request(request: dict[str, object]) -> dict[str, object]:
    """Read only the caller's classification schema, preserving task and label order."""
    if "schema" not in request:
        return read_object(request, {"text", "tasks"})
    schema = read_object(_native_request(request), {"classifications"})
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
    project_classification_request(request)
    native = read_object(read_object(response, {"result"})["result"])
    leaves = [
        value
        for prediction in native.values()
        for value in ([] if prediction is None else (
            prediction if isinstance(prediction, list) else [prediction]
        ))
    ]
    profile = _output_profile(request, leaves, classification=True)
    classifications: dict[str, object] = {}
    for name, prediction in native.items():
        values = [] if prediction is None else (
            prediction if isinstance(prediction, list) else [prediction]
        )
        selections = []
        for value in values:
            if profile[0]:
                selection = read_object(value, {"label", "confidence"})
                selections.append({"id": selection["label"], "score": selection["confidence"]})
            else:
                selections.append({"id": read_text(value, nonblank=True)})
        classifications[name] = selections
    return {"classifications": classifications}
