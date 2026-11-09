"""Which requested and effective settings explain each saved provider result?"""

import json

from render_tables import read_list, read_object, read_text, render_cell, render_table


def read_selection(value: object) -> list[str]:
    selected = [read_text(item, nonblank=True) for item in read_list(value)]
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("Selected values must be nonempty and distinct")
    return selected


def configured_types(settings: dict[str, object] | None) -> list[str] | None:
    if settings is None or "named_entities" not in settings:
        return None
    policy = read_object(settings["named_entities"])
    mapping = read_object(policy["label_map"])
    return list(dict.fromkeys(read_text(kind, nonblank=True) for kind in mapping.values()))


def _native(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _row(setting: str, requested: object, effective: object) -> list[str]:
    return [render_cell(setting), render_cell(requested), render_cell(effective)]


def render_spacy_configuration(
    request: dict[str, object] | None,
    result: dict[str, object] | None,
    settings: dict[str, object] | None,
) -> str:
    absent = "Not recorded; no saved request.json"
    response = "Not confirmed; no successful response.json"
    language = read_text(request["language"], nonblank=True) if request is not None else None
    profile = request.get("model_profile") if request is not None else None
    features = (
        _native(read_selection(request["features"]))
        if request is not None and "features" in request
        else ("Omitted (native defaults)" if request is not None else absent)
    )
    model = read_object(result["model"]) if result is not None else None
    effective_features = (
        [
            read_text(read_object(item)["feature"], nonblank=True)
            for item in read_list(result["features"])
        ]
        if result is not None
        else None
    )
    rows = [
        _row(
            "Operation",
            "run-ner-spacy (request.json)" if request is not None else absent,
            "run-ner-spacy (response.json)" if result is not None else response,
        ),
        _row("Language", language or absent, result["language"] if result else response),
        _row(
            "Model profile",
            profile if profile is not None else ("Omitted (native default)" if request else absent),
            model["profile"] if model else response,
        ),
        _row(
            "Features (ordered)",
            features,
            _native(effective_features) + " (response.json)"
            if effective_features is not None
            else response,
        ),
    ]
    configured_model: object = "Not recorded; no matching saved model configuration"
    if settings is not None and language is not None:
        languages = read_object(settings["languages"])
        selected_language = read_object(languages[language])
        selected_profile = profile or selected_language["default_profile"]
        profiles = read_object(selected_language["profiles"])
        selected_model = read_object(profiles[read_text(selected_profile)])
        identity = {
            "package": selected_model["package"],
            "model_version": selected_model["version"],
        }
        if "spacy_version" in settings:
            identity["spacy_version"] = settings["spacy_version"]
        configured_model = _native(identity) + " (settings.json)"
    rows.append(
        _row(
            "Model identity",
            configured_model,
            _native(model) + " (response.json)" if model else response,
        )
    )
    if settings is not None and "named_entities" in settings:
        policy = read_object(settings["named_entities"])
        ignore_case = policy["ignore_case"]
        if type(ignore_case) is not bool:
            raise ValueError("Expected a boolean native case rule")
        rows.extend(
            [
                _row(
                    "Entity label mapping",
                    "Native configuration, not a request selector",
                    _native(policy["label_map"]) + " (settings.json)",
                ),
                _row(
                    "Entity case grouping",
                    "Native configuration, not a request selector",
                    (
                        "Casefold; retain first spelling (ignore_case=true)"
                        if ignore_case
                        else "Exact case; retain first spelling (ignore_case=false)"
                    )
                    + " (settings.json)",
                ),
            ]
        )
    else:
        rows.append(_row("Entity grouping", "Native configuration", "No saved grouping settings"))
    if settings is not None and "important_terms" in settings:
        for setting, value in read_object(settings["important_terms"]).items():
            rows.append(
                _row(
                    "Important Terms: " + setting,
                    "Native configuration, not a request selector",
                    _native(value) + " (settings.json)",
                )
            )
    else:
        rows.append(_row("Important Terms settings", "Native configuration", "Not recorded"))
    rows.append(
        _row("Entity result limit", "No explicit result-count cap", "All returned groups retained")
    )
    return render_table(
        "A",
        "spaCy configuration",
        ["Setting", "Requested value", "Effective value / source"],
        rows,
        "Requested fields come from saved request.json; configured settings are not "
        "a substitute for metadata returned in response.json.",
    )


def render_gliner_configuration(
    request: dict[str, object] | None,
    result: dict[str, object] | None,
    settings: dict[str, object] | None,
    labels: list[str] | None,
) -> str:
    rows = [
        _row(
            "Operation",
            "run-ner-gliner (request.json)" if request is not None else "No saved request.json",
            "run-ner-gliner (response.json)"
            if result is not None
            else "Not confirmed; no successful response.json",
        ),
        _row(
            "Entity labels (ordered)",
            _native(labels) if labels is not None else "Not recorded",
            "Exact requested labels; no relabeling (request.json)"
            if request is not None
            else "No saved request.json",
        ),
        _row(
            "Configured model identity",
            _native(read_object(settings["model"])) if settings is not None else "Not recorded",
            (
                "settings.json; the native NER response returns no model identity metadata"
                if settings is not None
                else "No saved settings.json; the native NER response returns "
                "no model identity metadata"
            ),
        ),
        _row("Report grouping", "Exact entity text and requested label", "Report projection only"),
        _row(
            "Entity result limit", "No explicit result-count cap", "All returned mentions retained"
        ),
        _row("Classification", "Not requested", "No classification request was made"),
    ]
    return render_table(
        "J",
        "GLiNER configuration",
        ["Setting", "Requested value", "Effective value / source"],
        rows,
        "Model identity is configured in saved settings.json, not reported by the NER API.",
    )
