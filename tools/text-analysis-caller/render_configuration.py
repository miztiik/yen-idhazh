"""Which effective settings explain each saved provider result?"""

import json
import re

from render_classifications import ClassificationReport
from render_tables import read_list, read_object, read_text, render_cell, render_table


def render_settings_link(repository: str | None, *, gliner: bool = False) -> str:
    if repository is None:
        return "Current settings link unavailable: repository context was not provided."
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None or any(
        part in {".", ".."} for part in repository.split("/")
    ):
        raise ValueError("Invalid report repository identifier")
    path = "config/text-analysis/" + ("gliner/" if gliner else "") + "settings.json"
    return f"Current settings: [settings.json](/{repository}/blob/main/{path})"


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


def _row(setting: str, effective: object) -> list[str]:
    return [render_cell(setting), render_cell(effective)]


def _render_operation(
    name: str,
    request: dict[str, object] | None,
    result: dict[str, object] | None,
    *,
    prefix: str = "",
) -> str:
    if result is not None:
        return f"{name} ({prefix}response.json)"
    if request is not None:
        return f"{name} ({prefix}request.json; no successful response)"
    return f"Not confirmed; no successful {prefix}response.json"


def render_spacy_configuration(
    request: dict[str, object] | None,
    result: dict[str, object] | None,
    settings: dict[str, object] | None,
) -> str:
    response = "Not confirmed; no successful response.json"
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
            _render_operation("run-ner-spacy", request, result),
        ),
        _row("Language", result["language"] if result is not None else response),
        _row(
            "Model profile",
            model["profile"] if model is not None else response,
        ),
        _row(
            "Features (ordered)",
            _native(effective_features) + " (response.json)"
            if effective_features is not None
            else response,
        ),
        _row(
            "Model identity",
            _native(model) + " (response.json)" if model is not None else response,
        ),
    ]
    if settings is not None and "named_entities" in settings:
        policy = read_object(settings["named_entities"])
        ignore_case = policy["ignore_case"]
        if type(ignore_case) is not bool:
            raise ValueError("Expected a boolean native case rule")
        rows.extend(
            [
                _row(
                    "Entity label mapping",
                    _native(policy["label_map"]),
                ),
                _row(
                    "Entity case grouping",
                    "Casefold; retain first spelling (ignore_case=true)"
                    if ignore_case
                    else "Exact case; retain first spelling (ignore_case=false)",
                ),
            ]
        )
    else:
        rows.append(_row("Entity grouping", "Not recorded; no saved grouping settings"))
    if settings is not None and "important_terms" in settings:
        for setting, value in read_object(settings["important_terms"]).items():
            rows.append(
                _row(
                    "Important Terms: " + setting,
                    _native(value),
                )
            )
    else:
        rows.append(_row("Important Terms settings", "Not recorded"))
    rows.append(_row("Entity result limit", "All returned groups retained"))
    return render_table(
        "A",
        "spaCy configuration",
        ["Setting", "Effective value"],
        rows,
    )


def render_gliner_configuration(
    request: dict[str, object] | None,
    result: dict[str, object] | None,
    settings: dict[str, object] | None,
    labels: list[str] | None,
    *,
    classification: ClassificationReport | None = None,
) -> str:
    rows = [
        _row(
            "NER operation",
            _render_operation("run-ner-gliner", request, result),
        ),
        _row(
            "Entity labels (ordered)",
            _native(labels) + (" (request.json)" if request is not None else "")
            if labels is not None
            else "Not recorded; no saved label selection",
        ),
        _row(
            "Configured model identity",
            _native(read_object(settings["model"]))
            if settings is not None
            else "Not recorded; no saved model settings",
        ),
        _row("Report grouping", "Exact entity text and requested label (report projection only)"),
        _row("Entity result limit", "All returned mentions retained"),
    ]
    rows.append(
        _row(
            "Classification",
            _render_operation(
                "classify-text-gliner",
                classification.request,
                classification.result,
                prefix="classification/",
            )
            if classification is not None
            else "Not requested",
        )
    )
    if classification is not None and classification.request is not None:
        for name, value in read_object(classification.request["tasks"]).items():
            task = read_object(value)
            mode = "multi-label" if task["multi_label"] else "single-label"
            rows.append(
                _row(
                    "Classification task: " + name,
                    mode + "; " + _native(task["labels"]) + " (classification/request.json)",
                )
            )
    return render_table(
        "J",
        "GLiNER configuration",
        ["Setting", "Effective value"],
        rows,
        "Model identity comes from the saved configuration, not NER response metadata.",
    )
