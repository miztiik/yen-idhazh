"""How does each selected spaCy feature retain its native fields in a report?"""

from render_entities import (
    project_spacy_groups,
    read_span,
    render_entity_tables,
    render_evidence,
    render_offset,
)
from render_tables import (
    read_integer,
    read_list,
    read_object,
    read_score,
    read_text,
    render_cell,
    render_table,
)

TERM_NOTE = (
    "Native term order is retained. Lower YAKE scores rank higher within the same "
    "article and settings; they are not percentages, confidence probabilities or "
    "editorial quality grades. Occurrence counts are frequency, not weights."
)


def render_terms(data: object, source: str, *, empty: str = "No results were returned.") -> str:
    rows = []
    if data is not None:
        terms = read_object(data, {"terms"})
        for rank, value in enumerate(read_list(terms["terms"]), 1):
            term = read_object(value, {"text", "score", "occurrences"})
            text = read_text(term["text"], nonblank=True)
            occurrences = [read_span(span, source) for span in read_list(term["occurrences"])]
            if not occurrences or occurrences[0]["text"] != text:
                raise ValueError("Ranked terms must retain their first source spelling")
            occurrences.sort(
                key=lambda span: (read_integer(span["start_char"]), read_integer(span["end_char"]))
            )
            rows.append(
                [
                    str(rank),
                    render_cell(text),
                    str(len(occurrences)),
                    render_cell(read_score(term["score"])),
                    "<br>".join(map(render_evidence, occurrences)),
                ]
            )
    return render_table(
        "C",
        "Important Terms",
        ["Rank", "Phrase", "Occurrence count", "Native YAKE score", "Source positions"],
        rows,
        TERM_NOTE,
        empty=empty,
    )


def render_feature(name: str, data: object, source: str, types: list[str] | None) -> str:
    if name == "named_entities":
        data = read_object(data, {"entities"})
        return render_entity_tables(
            project_spacy_groups(data["entities"], source), types, prefix="B"
        )
    if name == "important_terms":
        return render_terms(data, source)
    if name in {"entities", "sentences", "noun_phrases"}:
        key, letter, title = {
            "entities": ("mentions", "D", "Raw entities"),
            "sentences": ("sentences", "E", "Sentences"),
            "noun_phrases": ("phrases", "F", "Noun phrases"),
        }[name]
        data = read_object(data, {key})
        rows = []
        for item in read_list(data[key]):
            span = read_span(item, source, label=name == "entities")
            row = [render_cell(span["text"])]
            if name == "entities":
                row.append(render_cell(span["label"]))
            rows.append([*row, render_offset(span), render_cell(span["sentence_index"])])
        columns = ["Text"] + (["Label"] if name == "entities" else []) + ["Offsets", "Sentence"]
        return render_table(letter, title, columns, rows)
    if name == "relations":
        data = read_object(data, {"relations"})
        rows = []
        for item in read_list(data["relations"]):
            item = read_object(
                item, {"sentence_index", "action", "actors", "objects", "times", "places"}
            )
            sentence = read_integer(item["sentence_index"])
            action = read_span(item["action"], source)
            groups = [
                [read_span(span, source) for span in read_list(item[key])]
                for key in ("actors", "objects", "times", "places")
            ]
            if not groups[0] or any(
                span["sentence_index"] != sentence
                for span in [action, *(span for group in groups for span in group)]
            ):
                raise ValueError("Relation evidence must remain in one sentence and have an actor")
            rows.append(
                [render_evidence(action)]
                + ["<br>".join(map(render_evidence, group)) for group in groups]
                + [render_cell(sentence)]
            )
        return render_table(
            "G", "Relations", ["Action", "Actors", "Objects", "Times", "Places", "Sentence"], rows
        )
    if name == "linguistic_tokens":
        data = read_object(data, {"tokens"})
        rows = []
        annotations = {"lemma", "part_of_speech", "dependency", "head_index", "morphology"}
        for item in read_list(data["tokens"]):
            item = read_object(
                item, {"text", "start_char", "end_char", "sentence_index"} | annotations
            )
            span = read_span(
                {key: item[key] for key in ("text", "start_char", "end_char", "sentence_index")},
                source,
            )
            for key in annotations - {"head_index"}:
                if item[key] is not None:
                    read_text(item[key])
            if item["head_index"] is not None and type(item["head_index"]) is not int:
                raise ValueError("Expected an integer or null head index")
            rows.append(
                [
                    render_cell(span["text"]),
                    render_offset(span),
                    render_cell(span["sentence_index"]),
                ]
                + [
                    render_cell(item[key])
                    for key in ("lemma", "part_of_speech", "dependency", "head_index", "morphology")
                ]
            )
        return render_table(
            "H",
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
        data = read_object(data, keys)
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
                read_integer(data[key])
            rows.append([render_cell(key), render_cell(data[key])])
        return render_table("I", "Document metrics", ["Metric", "Native value"], rows)
    raise ValueError(f"Unknown spaCy feature: {name}")


def render_missing_feature(name: str, source: str, types: list[str] | None, state: str) -> str:
    if name == "named_entities":
        return render_entity_tables([], types, prefix="B", state=state)
    return render_terms(None, source, empty=state)
