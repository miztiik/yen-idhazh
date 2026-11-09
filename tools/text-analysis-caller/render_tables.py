"""How are untrusted native values rendered in escaped, expandable Markdown tables?"""

import html
import math
import string


def read_object(value: object, keys: set[str] | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("Expected a JSON object")
    if keys is not None and set(value) != keys:
        raise ValueError(f"Expected an object with fields {sorted(keys)}")
    return value


def read_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("Expected a JSON array")
    return value


def read_text(value: object, *, nonblank: bool = False) -> str:
    if not isinstance(value, str) or (nonblank and not value.strip()):
        raise ValueError("Expected text" + (" that is not blank" if nonblank else ""))
    value.encode("utf-8")
    return value


def read_integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Expected a nonnegative integer")
    return value


def read_score(value: object, *, confidence: bool = False) -> int | float:
    if (
        type(value) not in (int, float)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("Expected a finite nonnegative score")
    if confidence and value > 1:
        raise ValueError("Expected a score between zero and one")
    return value


def escape_text(value: str) -> str:
    """Keep Markdown syntax and HTML from turning native text into markup."""
    escaped = html.escape(value, quote=True)
    return "".join(
        f"&#{ord(char)};" if char in string.punctuation and char not in "&;#" else char
        for char in escaped
    )


def render_cell(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) in (int, float):
        return str(value)
    return (
        escape_text(read_text(value))
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
        .replace("\r", "<br>")
    )


def render_error(value: object, *, feature: str | None = None, spacy: bool = False) -> str:
    keys = {"code", "message", "retryable"} | ({"feature"} if spacy else set())
    error = read_object(value, keys)
    code = read_text(error["code"], nonblank=True)
    message = read_text(error["message"])
    if type(error["retryable"]) is not bool:
        raise ValueError("Expected a boolean retryable field")
    if spacy and error["feature"] != feature:
        raise ValueError("Error feature does not match its outcome")
    if feature is not None and code not in {"FEATURE_FAILED", "FEATURE_UNAVAILABLE"}:
        raise ValueError("Invalid feature error code")
    return f"{render_cell(code)}: {render_cell(message)}"


def render_table(
    letter: str,
    title: str,
    columns: list[str],
    rows: list[list[str]],
    note: str = "",
    *,
    empty: str = "No results were returned.",
    row_ids: list[int] | None = None,
    expanded: bool = False,
) -> str:
    """Give each table its own letter and deterministic, addressable row IDs."""
    if row_ids is not None and len(row_ids) != len(rows):
        raise ValueError("Every table row must have one identifier")
    opening = "<details open>" if expanded else "<details>"
    lines = [f"{opening}<summary>{render_cell(title)}</summary>", ""]
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
        for index, row in enumerate(rows):
            number = row_ids[index] if row_ids is not None else index + 1
            lines.append(f"| {letter}{number} | " + " | ".join(row) + " |")
    else:
        lines.append(empty)
    lines.extend(["", "</details>"])
    return "\n".join(lines)
