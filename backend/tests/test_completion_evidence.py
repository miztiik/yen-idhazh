"""Does native selected-token evidence survive parsing without changing other consumers?"""

from __future__ import annotations

import dataclasses
import json

import pytest
from support.judge_reader import native_reply

from idhazh.llm import server
from idhazh.llm.server import Completion, one_reply, parse_completion


def test_selected_positions_are_not_ranked_alternatives() -> None:
    """Sorting the alternatives must not replace the token the decoder emitted."""
    raw = native_reply(
        "UNCLEAR", pieces=(" ", "UN", "CLEAR"),
        alternatives=(("Sure", -0.01), (" UN", -2.0)),
    ).decode()
    reply = parse_completion(raw)

    assert reply.emitted_tokens == (
        server.EmittedToken(0, " ", (32,)),
        server.EmittedToken(1, "UN", (85, 78)),
        server.EmittedToken(2, "CLEAR", (67, 76, 69, 65, 82)),
    )
    assert reply.first_token_choices[0].token == "Sure"
    assert reply.raw_response == raw


@pytest.mark.parametrize(
    "position",
    [
        {},
        {"id": -1, "token": "YES", "bytes": [89]},
        {"id": True, "token": "YES", "bytes": [89]},
        {"id": "1", "token": "YES", "bytes": [89]},
        {"id": 1, "token": None, "bytes": [89]},
        {"id": 1, "token": "YES", "bytes": [256]},
        {"id": 1, "token": "YES", "bytes": [True]},
        {"id": 1, "token": "YES", "bytes": "YES"},
    ],
)
def test_invalid_optional_emission_does_not_fail_an_unrelated_completion(
    position: dict[str, object],
) -> None:
    reply = parse_completion(json.dumps({
        "content": "ordinary summary",
        "tokens_predicted": 3,
        "completion_probabilities": [position],
    }))

    assert reply.content == "ordinary summary"
    assert reply.completion_tokens == 3
    assert reply.emitted_tokens is None


def test_unreported_evidence_retains_compatible_defaults() -> None:
    assert Completion("ordinary summary").emitted_tokens is None
    assert Completion("ordinary summary").raw_response is None
    assert parse_completion('{"content":"ordinary summary"}').emitted_tokens is None
    assert parse_completion('{"choices":[{"message":{"content":"ordinary summary"}}]}').content == (
        "ordinary summary"
    )


def test_one_reply_keeps_answer_evidence_and_both_spans_costs() -> None:
    thought = parse_completion(native_reply("Reasoning", completion_tokens=5).decode())
    answer = parse_completion(native_reply("NO", completion_tokens=2).decode())
    reply = one_reply(thought=thought, answer=answer)

    assert reply.content == "NO"
    assert reply.emitted_tokens == answer.emitted_tokens
    assert reply.raw_response == answer.raw_response
    assert reply.completion_tokens == 7


def test_an_explicit_answer_offset_excludes_earlier_positions() -> None:
    reply = parse_completion(native_reply("YES", pieces=("thought", "Y", "ES")).decode(), answer_at=1)
    assert reply.emitted_tokens == (
        server.EmittedToken(1, "Y", (89,)), server.EmittedToken(2, "ES", (69, 83))
    )


def test_selected_token_values_are_validated_and_frozen() -> None:
    token = server.EmittedToken(1, "N", (78,))
    with pytest.raises(dataclasses.FrozenInstanceError):
        token.text = "Y"  # type: ignore[misc]
    with pytest.raises(ValueError, match="nonnegative"):
        server.EmittedToken(-1, "N", (78,))
    with pytest.raises(ValueError, match="byte range"):
        server.EmittedToken(1, "N", (256,))
