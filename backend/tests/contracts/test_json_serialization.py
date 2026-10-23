"""Does each persisted-JSON writer lay out its bytes the way its callers rely on?

Each expected string is written out by hand from the layout rule the writer
states, so a change to that rule fails here with a readable difference.
"""

from __future__ import annotations

import json

import pytest

from idhazh.contracts.base import canonical_json, compact_json, records_json

pytestmark = pytest.mark.contract


def test_canonical_json_sorts_keys_and_ends_with_one_newline() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{\n  "a": 2,\n  "b": 1\n}\n'


def test_canonical_json_escapes_non_ascii_and_writes_empty_containers_inline() -> None:
    payload: dict[str, object] = {
        "name": "caf\u00e9",
        "tags": [],
        "meta": {},
        "n": None,
        "ok": True,
    }

    assert canonical_json(payload) == (
        '{\n  "meta": {},\n  "n": null,\n  "name": "caf\\u00e9",\n  "ok": true,\n  "tags": []\n}\n'
    )


def test_canonical_json_escapes_quotes_and_newlines_inside_strings() -> None:
    assert canonical_json({"q": 'say "hi"\n'}) == '{\n  "q": "say \\"hi\\"\\n"\n}\n'


def test_compact_json_removes_indent_and_separator_spaces_only() -> None:
    payload = {"b": [1, 2], "a": {"z": None, "y": "caf\u00e9"}}

    assert compact_json(payload) == '{"a":{"y":"caf\\u00e9","z":null},"b":[1,2]}\n'


def test_records_json_without_a_record_list_is_laid_out_as_canonical_json() -> None:
    payload = {"b": {"d": [1, 2], "c": None}, "a": [[1], []], "e": "x"}

    assert records_json(payload) == (
        '{\n  "a": [\n    [\n      1\n    ],\n    []\n  ],\n'
        '  "b": {\n    "c": null,\n    "d": [\n      1,\n      2\n    ]\n  },\n'
        '  "e": "x"\n}\n'
    )


def test_records_json_writes_each_object_in_a_list_on_one_line() -> None:
    assert records_json({"feeds": [{"b": 1, "a": 2}, {"a": 3, "b": 4}]}) == (
        '{\n  "feeds": [\n    {"a": 2,"b": 1},\n    {"a": 3,"b": 4}\n  ]\n}\n'
    )


def test_records_json_keeps_a_list_expanded_when_one_item_is_not_an_object() -> None:
    assert records_json({"items": [{"a": 1}, 2]}, record_lists=frozenset({"items"})) == (
        '{\n  "items": [\n    {\n      "a": 1\n    },\n    2\n  ]\n}\n'
    )


def test_records_json_puts_only_the_named_record_lists_on_one_line() -> None:
    payload = [{"runs": [{"n": 1, "verticals": [{"id": "ai", "published": 2}]}]}]
    record_lists = frozenset({"verticals"})

    text = records_json(payload, record_lists=record_lists)

    assert text == (
        '[\n  {\n    "runs": [\n      {\n        "n": 1,\n        "verticals": [\n'
        '          {"id": "ai","published": 2}\n        ]\n      }\n    ]\n  }\n]\n'
    )
    assert json.loads(text) == payload
    assert records_json(json.loads(text), record_lists=record_lists) == text


def test_an_empty_named_record_list_stays_an_empty_pair_of_brackets() -> None:
    assert records_json({"items": []}, record_lists=frozenset({"items"})) == (
        '{\n  "items": []\n}\n'
    )
