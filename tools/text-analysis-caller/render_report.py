"""How are native text-analysis responses composed into a safe Markdown report?

The public render_source, render_spacy_results, render_gliner_results and
render_report functions return Markdown strings and never call a provider.
Inputs are decoded native JSON objects, including saved requests and settings,
not provider model instances. Missing evidence is reported as unavailable.
Offsets are zero-based, half-open Unicode code-point offsets into source_text.
"""

from __future__ import annotations

from project_gliner_analysis import project_entity_request, project_entity_result
from render_classifications import ClassificationReport
from render_configuration import (
    configured_types,
    read_selection,
    render_gliner_configuration,
    render_settings_link,
    render_spacy_configuration,
)
from render_entities import (
    project_gliner_groups,
    render_entity_tables,
)
from render_features import render_feature, render_missing_feature
from render_tables import (
    escape_text,
)
from render_tables import (
    read_list as _list,
)
from render_tables import (
    read_object as _object,
)
from render_tables import (
    read_text as _text,
)
from render_tables import (
    render_cell as _cell,
)
from render_tables import (
    render_error as _error,
)


def _has_error(value: object) -> bool:
    return isinstance(value, dict) and "error" in value


def render_source(source_text: str) -> str:
    """Show escaped, wrapping prose in a collapsed native disclosure."""
    source = (
        escape_text(_text(source_text))
        .replace("\r\n", "&#13;&#10;<br>")
        .replace("\r", "&#13;<br>")
        .replace("\n", "&#10;<br>")
    )
    return "<details><summary><h2>Source text</h2></summary>\n\n<p>" + source + "</p>\n\n</details>"


def _validate_request(
    request: dict[str, object] | None, source: str, *, gliner: bool = False
) -> None:
    if request is None:
        return
    if gliner:
        request = project_entity_request(request)
    required = {"text", "labels"} if gliner else {"text", "language"}
    allowed = required if gliner else required | {"model_profile", "features"}
    if not required.issubset(request) or not set(request).issubset(allowed):
        raise ValueError("Invalid saved native request fields")
    if _text(request["text"]) != source:
        raise ValueError("Saved request text differs from the displayed source")
    if gliner:
        read_selection(request["labels"])
    else:
        _text(request["language"], nonblank=True)
        if "model_profile" in request:
            _text(request["model_profile"], nonblank=True)
        if "features" in request:
            read_selection(request["features"])


def _unselected_state(
    name: str,
    names: list[str] | None,
    request: dict[str, object] | None,
    settings: dict[str, object] | None,
) -> str:
    selection = names
    if selection is None and request is not None:
        if "features" in request:
            selection = read_selection(request["features"])
        elif settings is not None:
            language = _object(_object(settings["languages"])[_text(request["language"])])
            defaults = language.get("default_features", settings.get("default_features"))
            if defaults is not None:
                selection = read_selection(defaults)
    if selection is not None and name not in selection:
        return f"Not requested: {_cell(name)} was not selected."
    return "Failed: no successful feature result is available; see the provider outcome."


def render_spacy_results(
    source_text: str,
    spacy: dict[str, object] | None,
    *,
    spacy_error: str | None = None,
    spacy_request: dict[str, object] | None = None,
    spacy_settings: dict[str, object] | None = None,
    repository: str | None = None,
) -> str:
    """Render configuration and native spaCy features without regrouping evidence."""
    source = _text(source_text)
    _validate_request(spacy_request, source)
    types = configured_types(spacy_settings)
    result = None
    names: list[str] | None = None
    sections = []
    if spacy_error is not None:
        if spacy is not None:
            raise ValueError("A provider cannot have both a response and a transport error")
        outcome = "Provider error: " + _cell(_text(spacy_error, nonblank=True))
    elif spacy is None:
        outcome = "Provider unavailable: no response was provided."
    elif _has_error(spacy):
        outcome = "Provider error: " + _error(_object(spacy, {"error"})["error"], spacy=True)
    else:
        result = _object(spacy, {"status", "language", "model", "features"})
        language = _text(result["language"], nonblank=True)
        if language not in {"en", "zh"}:
            raise ValueError("Invalid spaCy result language")
        model = _object(result["model"], {"profile", "package", "model_version", "spacy_version"})
        for value in model.values():
            _text(value, nonblank=True)
        if model["profile"] not in {"sm", "md", "lg"}:
            raise ValueError("Invalid spaCy model profile")
        features = _list(result["features"])
        if not features:
            raise ValueError("spaCy results require selected features")
        names, statuses = [], []
        for feature in features:
            feature = _object(feature, {"feature", "status", "data", "error"})
            name = _text(feature["feature"], nonblank=True)
            if name in names:
                raise ValueError("Duplicate spaCy feature")
            names.append(name)
            status = feature["status"]
            if status == "complete" and feature["error"] is None:
                sections.append(render_feature(name, feature["data"], source, types))
            elif status == "failed" and feature["data"] is None:
                if name not in {
                    "named_entities",
                    "important_terms",
                    "entities",
                    "sentences",
                    "noun_phrases",
                    "relations",
                    "linguistic_tokens",
                    "document_metrics",
                }:
                    raise ValueError("Unknown spaCy feature")
                error = _error(feature["error"], feature=name, spacy=True)
                sections.append(
                    render_missing_feature(name, source, types, "Failed: " + error)
                    if name in {"named_entities", "important_terms"}
                    else f"### {_cell(name)}\n\nFeature error: " + error
                )
            else:
                raise ValueError("Invalid feature outcome")
            statuses.append(status)
        expected = (
            "complete"
            if all(s == "complete" for s in statuses)
            else ("failed" if all(s == "failed" for s in statuses) else "partial")
        )
        if result["status"] != expected:
            raise ValueError("spaCy status does not match feature outcomes")
        if (
            spacy_request is not None
            and "features" in spacy_request
            and names != read_selection(spacy_request["features"])
        ):
            raise ValueError("Returned features differ from the saved explicit selection")
        outcome = "Status: " + expected + "."
    for name in ("named_entities", "important_terms"):
        if names is None or name not in names:
            sections.append(
                render_missing_feature(
                    name,
                    source,
                    types,
                    _unselected_state(name, names, spacy_request, spacy_settings),
                )
            )
    return "\n\n".join(
        [
            "## spaCy results",
            outcome,
            render_settings_link(repository),
            render_spacy_configuration(spacy_request, result, spacy_settings),
            "### Results",
            *sections,
        ]
    )


def render_gliner_results(
    source_text: str,
    gliner: dict[str, object] | None,
    *,
    gliner_error: str | None = None,
    gliner_labels: list[str] | None = None,
    gliner_request: dict[str, object] | None = None,
    gliner_settings: dict[str, object] | None = None,
    classification: ClassificationReport | None = None,
    repository: str | None = None,
) -> str:
    """Group flat native GLiNER mentions by exact text and requested label."""
    source = _text(source_text)
    _validate_request(gliner_request, source, gliner=True)
    labels = read_selection(gliner_labels) if gliner_labels is not None else None
    if gliner_request is not None:
        requested = read_selection(project_entity_request(gliner_request)["labels"])
        if labels is not None and requested != labels:
            raise ValueError("Requested labels differ from the saved native request")
        labels = requested
    result = None
    groups = []
    state = None
    if gliner_error is not None:
        if gliner is not None:
            raise ValueError("A provider cannot have both a response and a transport error")
        outcome = "Provider error: " + _cell(_text(gliner_error, nonblank=True))
    elif gliner is None:
        outcome = "Provider unavailable: no response was provided."
    elif _has_error(gliner):
        outcome = "Provider error: " + _error(_object(gliner, {"error"})["error"])
    else:
        result = project_entity_result(gliner, gliner_request)
        groups = project_gliner_groups(result["entities"], source, labels)
        outcome = "Status: complete."
    if result is None:
        state = "Failed: no successful NER result is available; see the provider outcome."
    return "\n\n".join(
        [
            "## GLiNER results",
            outcome,
            render_settings_link(repository, gliner=True),
            render_gliner_configuration(
                gliner_request, result, gliner_settings, labels, classification=classification
            ),
            "### Results",
            "Native GLiNER confidence is between 0 and 1: higher means stronger model "
            "confidence, not calibrated correctness. It is not comparable to YAKE scores. "
            "Every occurrence retains its own score; GLiNER returns no sentence indexes.",
            render_entity_tables(groups, labels, prefix="K", state=state, gliner=True),
            *([classification.content] if classification is not None else []),
        ]
    )


def compose_report(source_text: str, *provider_sections: str) -> str:
    """Use exactly the same sections for combined and standalone provider reports."""
    return "\n\n".join((render_source(source_text), *provider_sections)) + "\n"


def render_report(
    source_text: str,
    spacy: dict[str, object] | None,
    gliner: dict[str, object] | None,
    *,
    spacy_error: str | None = None,
    gliner_error: str | None = None,
    gliner_labels: list[str] | None = None,
    spacy_request: dict[str, object] | None = None,
    spacy_settings: dict[str, object] | None = None,
    gliner_request: dict[str, object] | None = None,
    gliner_settings: dict[str, object] | None = None,
    classification: ClassificationReport | None = None,
    repository: str | None = None,
) -> str:
    """Compose the source, spaCy and GLiNER sections without truncating results."""
    return compose_report(
        source_text,
        render_spacy_results(
            source_text,
            spacy,
            spacy_error=spacy_error,
            spacy_request=spacy_request,
            spacy_settings=spacy_settings,
            repository=repository,
        ),
        render_gliner_results(
            source_text,
            gliner,
            gliner_error=gliner_error,
            gliner_labels=gliner_labels,
            gliner_request=gliner_request,
            gliner_settings=gliner_settings,
            classification=classification,
            repository=repository,
        ),
    )
