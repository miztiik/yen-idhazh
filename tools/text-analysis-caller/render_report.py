"""How are native text-analysis responses composed into a safe Markdown report?

The public render_source, render_spacy_results, render_gliner_results and
render_report functions return Markdown strings and never call a provider.
Inputs are decoded native JSON objects, not provider model instances. A missing
response is reported as unavailable; supply an error string to explain why.
Offsets are zero-based, half-open Unicode code-point offsets into source_text.
The caller owns the GitHub summary size limit and retains the complete report.
"""

from __future__ import annotations

import html
import math
import string


def _object(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"Expected an object with fields {sorted(keys)}")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("Expected a JSON array")
    return value


def _text(value: object, *, nonblank: bool = False) -> str:
    if not isinstance(value, str) or (nonblank and not value.strip()):
        raise ValueError("Expected text" + (" that is not blank" if nonblank else ""))
    value.encode("utf-8")
    return value


def _integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Expected a nonnegative integer")
    return value


def _score(value: object, *, confidence: bool = False) -> int | float:
    if (
        not isinstance(value, (int, float))
        or type(value) not in (int, float)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("Expected a finite nonnegative score")
    if confidence and value > 1:
        raise ValueError("Expected a score between zero and one")
    return value


def _escape(value: str) -> str:
    # Entities are parsed as text, not subsequently as Markdown syntax.
    value = html.escape(value, quote=True)
    return (
        "".join(
            f"&#{ord(char)};" if char in string.punctuation and char not in "&;#" else char
            for char in value
        )
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
        .replace("\r", "<br>")
    )


def _cell(value: object) -> str:
    if value is None:
        return "null"
    if type(value) in (int, float):
        return str(value)
    return _escape(_text(value))


def _span(value: object, source: str, *, label: bool = False) -> dict[str, object]:
    keys = {"text", "start_char", "end_char", "sentence_index"}
    if label:
        keys.add("label")
    span = _object(value, keys)
    text = _text(span["text"])
    if not text:
        raise ValueError("Evidence text must not be empty")
    start = _integer(span["start_char"])
    end = _integer(span["end_char"])
    _integer(span["sentence_index"])
    if start >= end or source[start:end] != text:
        raise ValueError("Evidence span does not match the source")
    if label:
        _text(span["label"], nonblank=True)
    return span


def _offset(span: dict[str, object]) -> str:
    return f"[{span['start_char']}, {span['end_char']})"


def _evidence(span: dict[str, object]) -> str:
    return f"{_cell(span['text'])} ({_offset(span)}, sentence {span['sentence_index']})"


def _error(value: object, *, feature: str | None = None, spacy: bool = False) -> str:
    keys = {"code", "message", "retryable"} | ({"feature"} if spacy else set())
    error = _object(value, keys)
    code = _text(error["code"], nonblank=True)
    message = _text(error["message"])
    if type(error["retryable"]) is not bool:
        raise ValueError("Expected a boolean retryable field")
    if spacy and error["feature"] != feature:
        raise ValueError("Error feature does not match its outcome")
    if feature is not None and code not in {"FEATURE_FAILED", "FEATURE_UNAVAILABLE"}:
        raise ValueError("Invalid feature error code")
    return f"{_cell(code)}: {_cell(message)}"


def _has_error(value: object) -> bool:
    return isinstance(value, dict) and "error" in value


def _table(
    letter: str, title: str, columns: list[str], rows: list[list[str]], note: str = ""
) -> str:
    lines = [f"<details><summary>{title}</summary>", ""]
    if note:
        lines.extend([note, ""])
    if rows:
        lines.extend(
            [
                f"Table {letter}",
                "",
                "| Id | " + " | ".join(columns) + " |",
                "| --- | " + " | ".join("---" for _ in columns) + " |",
            ]
        )
        for index, row in enumerate(rows, 1):
            lines.append(f"| {letter}{index} | " + " | ".join(row) + " |")
    else:
        lines.append("No results were returned.")
    lines.extend(["", "</details>"])
    return "\n".join(lines)


def render_source(source_text: str) -> str:
    """Render the unchanged source once in an expanded, escaped preformatted block."""
    source = html.escape(_text(source_text), quote=True).replace("\r", "&#13;")
    return "## Source text\n\n<pre><code>" + source + "</code></pre>"


def _group_rows(items: object, source: str, *, terms: bool) -> list[list[str]]:
    rows = []
    for item in _list(items):
        key = "score" if terms else "type"
        item = _object(item, {"text", key, "occurrences"})
        text = _text(item["text"], nonblank=True)
        value = _score(item[key]) if terms else _text(item[key], nonblank=True)
        occurrences = [_span(span, source) for span in _list(item["occurrences"])]
        if not occurrences or occurrences[0]["text"] != text:
            raise ValueError("Grouped evidence must retain its first source spelling")
        rows.append([_cell(text), _cell(value), "<br>".join(map(_evidence, occurrences))])
    return rows


def _feature_table(name: str, data: object, source: str) -> str:
    if name == "named_entities":
        data = _object(data, {"entities"})
        return _table(
            "A",
            "Named Entities",
            ["Text", "Type", "Occurrences"],
            _group_rows(data["entities"], source, terms=False),
        )
    if name == "important_terms":
        data = _object(data, {"terms"})
        return _table(
            "B",
            "Important Terms",
            ["Phrase", "Native YAKE score", "Occurrences"],
            _group_rows(data["terms"], source, terms=True),
            "Lower YAKE scores rank higher; they are not confidence probabilities.",
        )
    if name in {"entities", "sentences", "noun_phrases"}:
        key, letter, title = {
            "entities": ("mentions", "C", "Raw entities"),
            "sentences": ("sentences", "D", "Sentences"),
            "noun_phrases": ("phrases", "E", "Noun phrases"),
        }[name]
        data = _object(data, {key})
        rows = []
        for item in _list(data[key]):
            span = _span(item, source, label=name == "entities")
            row = [_cell(span["text"])]
            if name == "entities":
                row.append(_cell(span["label"]))
            rows.append([*row, _offset(span), _cell(span["sentence_index"])])
        columns = ["Text"] + (["Label"] if name == "entities" else []) + ["Offsets", "Sentence"]
        return _table(letter, title, columns, rows)
    if name == "relations":
        data = _object(data, {"relations"})
        rows = []
        for item in _list(data["relations"]):
            item = _object(
                item, {"sentence_index", "action", "actors", "objects", "times", "places"}
            )
            sentence = _integer(item["sentence_index"])
            action = _span(item["action"], source)
            groups = [
                [_span(span, source) for span in _list(item[key])]
                for key in ("actors", "objects", "times", "places")
            ]
            if not groups[0] or any(
                span["sentence_index"] != sentence
                for span in [action, *(s for g in groups for s in g)]
            ):
                raise ValueError("Relation evidence must remain in one sentence and have an actor")
            rows.append(
                [_evidence(action)]
                + ["<br>".join(map(_evidence, group)) for group in groups]
                + [_cell(sentence)]
            )
        return _table(
            "F", "Relations", ["Action", "Actors", "Objects", "Times", "Places", "Sentence"], rows
        )
    if name == "linguistic_tokens":
        data = _object(data, {"tokens"})
        rows = []
        annotations = {"lemma", "part_of_speech", "dependency", "head_index", "morphology"}
        for item in _list(data["tokens"]):
            item = _object(item, {"text", "start_char", "end_char", "sentence_index"} | annotations)
            span = _span(
                {key: item[key] for key in ("text", "start_char", "end_char", "sentence_index")},
                source,
            )
            for key in annotations - {"head_index"}:
                if item[key] is not None:
                    _text(item[key])
            if item["head_index"] is not None and type(item["head_index"]) is not int:
                raise ValueError("Expected an integer or null head index")
            rows.append(
                [_cell(span["text"]), _offset(span), _cell(span["sentence_index"])]
                + [
                    _cell(item[key])
                    for key in ("lemma", "part_of_speech", "dependency", "head_index", "morphology")
                ]
            )
        return _table(
            "G",
            "Tokens",
            [
                "Text",
                "Offsets",
                "Sentence",
                "Lemma",
                "Part of speech",
                "Dependency",
                "Head",
                "Morphology",
            ],
            rows,
        )
    if name == "document_metrics":
        keys = {
            "codepoint_count",
            "utf8_byte_count",
            "token_count",
            "sentence_count",
            "entity_count",
            "relation_count",
        }
        data = _object(data, keys)
        rows = []
        for key in (
            "codepoint_count",
            "utf8_byte_count",
            "token_count",
            "sentence_count",
            "entity_count",
            "relation_count",
        ):
            if data[key] is not None or key != "relation_count":
                _integer(data[key])
            rows.append([_cell(key), _cell(data[key])])
        return _table("H", "Document metrics", ["Metric", "Native value"], rows)
    raise ValueError(f"Unknown spaCy feature: {name}")


def render_spacy_results(
    source_text: str, spacy: dict[str, object] | None, *, spacy_error: str | None = None
) -> str:
    """Render a native spaCy response, request error, or unavailable provider."""
    source = _text(source_text)
    lines = ["## spaCy results"]
    if spacy_error is not None:
        if spacy is not None:
            raise ValueError("A provider cannot have both a response and a transport error")
        lines.append("Provider error: " + _cell(_text(spacy_error, nonblank=True)))
    elif spacy is None:
        lines.append("Provider unavailable: no response was provided.")
    elif _has_error(spacy):
        lines.append("Provider error: " + _error(_object(spacy, {"error"})["error"], spacy=True))
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
        names, statuses, sections = [], [], []
        for feature in features:
            feature = _object(feature, {"feature", "status", "data", "error"})
            name = _text(feature["feature"], nonblank=True)
            if name in names:
                raise ValueError("Duplicate spaCy feature")
            names.append(name)
            status = feature["status"]
            if status == "complete" and feature["error"] is None:
                sections.append(_feature_table(name, feature["data"], source))
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
                sections.append(
                    f"### {_cell(name)}\n\nFeature error: "
                    + _error(feature["error"], feature=name, spacy=True)
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
        lines.append(
            "Language: "
            + _cell(language)
            + " | Profile: "
            + _cell(model["profile"])
            + " | Model: "
            + _cell(model["package"])
            + " ("
            + _cell(model["model_version"])
            + ") | spaCy: "
            + _cell(model["spacy_version"])
        )
        lines.append("Selected features: " + ", ".join(_cell(name) for name in names))
        if expected != "complete":
            lines.append("Result: " + expected)
        lines.extend(sections)
    return "\n\n".join(lines)


def render_gliner_results(
    source_text: str,
    gliner: dict[str, object] | None,
    *,
    gliner_error: str | None = None,
    gliner_labels: list[str] | None = None,
) -> str:
    """Render native GLiNER NER results and, when supplied, requested labels."""
    source = _text(source_text)
    lines = ["## GLiNER results"]
    if gliner_labels is not None:
        labels = [_text(label, nonblank=True) for label in _list(gliner_labels)]
        if not labels or len(set(labels)) != len(labels):
            raise ValueError("Requested labels must be nonempty and distinct")
        lines.append("Requested labels: " + ", ".join(_cell(label) for label in labels))
    else:
        labels = None
        lines.append("Requested labels: not provided.")
    if gliner_error is not None:
        if gliner is not None:
            raise ValueError("A provider cannot have both a response and a transport error")
        lines.append("Provider error: " + _cell(_text(gliner_error, nonblank=True)))
    elif gliner is None:
        lines.append("Provider unavailable: no response was provided.")
    elif _has_error(gliner):
        lines.append("Provider error: " + _error(_object(gliner, {"error"})["error"]))
    else:
        result = _object(gliner, {"entities"})
        rows = []
        for item in _list(result["entities"]):
            item = _object(item, {"text", "label", "score", "start_char", "end_char"})
            text = _text(item["text"], nonblank=True)
            label = _text(item["label"], nonblank=True)
            start, end = _integer(item["start_char"]), _integer(item["end_char"])
            if start >= end or source[start:end] != text:
                raise ValueError("GLiNER span does not match the source")
            if labels is not None and label not in labels:
                raise ValueError("GLiNER entity label was not requested")
            rows.append(
                [
                    _cell(text),
                    _cell(label),
                    _cell(_score(item["score"], confidence=True)),
                    _offset(item),
                ]
            )
        lines.append(
            _table("I", "Entities", ["Mention", "Requested label", "Native score", "Offsets"], rows)
        )
    return "\n\n".join(lines)


def render_report(
    source_text: str,
    spacy: dict[str, object] | None,
    gliner: dict[str, object] | None,
    *,
    spacy_error: str | None = None,
    gliner_error: str | None = None,
    gliner_labels: list[str] | None = None,
) -> str:
    """Compose the source, spaCy and GLiNER sections without truncating results."""
    return (
        "\n\n".join(
            (
                render_source(source_text),
                render_spacy_results(source_text, spacy, spacy_error=spacy_error),
                render_gliner_results(
                    source_text, gliner, gliner_error=gliner_error, gliner_labels=gliner_labels
                ),
            )
        )
        + "\n"
    )
