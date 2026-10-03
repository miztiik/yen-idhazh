"""Does every committed entry post the body it posted yesterday, minus the caps?

Two questions, and they are one question asked at two grains. The golden files
hold each route's whole body for each committed model file, so a knob that
reaches a request reaches a reviewable diff. The span count holds the shape one
level up: a thinking entry is two POSTs and a plain entry is one, driven over a
real socket rather than inferred from what came back.
"""

from __future__ import annotations

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, RecordedEndpoint, read_text

from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.llm.server import answer_span, post, thinking_span
from utilities import capture_request_bodies

pytestmark = pytest.mark.contract

def test_a_thinking_entry_makes_two_requests_and_a_plain_one_makes_one() -> None:
    """The two-call split stays, and the count is read off the socket.

    A reply-driven assertion cannot see this: both shapes read back a parseable
    answer, and the one that skipped its reasoning span differs only in how many
    times it posted. `RecordedEndpoint` is a real local server replaying
    recorded llama-server bodies, so this counts POSTs rather than mocking one
    (Guardrail #7).
    """
    recorded = FIXTURES_DIR / "completions" / "rendered"
    first = read_text(recorded / "thinking-span-one.json").encode("utf-8")
    second = read_text(recorded / "thinking-span-two.json").encode("utf-8")

    thinking = ModelsConfig.model_validate_json(
        read_text(CONFIG_DIR / "models" / "qwen3.5-9b-q4km-thinking.json")
    )
    plain = ModelsConfig.model_validate_json(
        read_text(CONFIG_DIR / "models" / "qwen3.5-9b-q4km.json")
    )
    thinking_markers = capture_request_bodies.markers_for("qwen3.5-9b-q4km-thinking.json")
    assert thinking.summarizer.thinks, "the fixture entry stopped declaring a marker"
    assert not plain.summarizer.thinks

    body = capture_request_bodies.bodies(thinking, markers=thinking_markers)["completion"]
    with RecordedEndpoint(200, first, second) as served:
        thought = post(
            thinking_span(body, markers=thinking_markers),
            endpoint=served.endpoint,
            timeout=5.0,
        )
        post(
            answer_span(body, thought=thought.content, markers=thinking_markers),
            endpoint=served.endpoint,
            timeout=5.0,
        )
    assert len(served.sent) == 2, "a declared closing marker is two spans on one slot"

    with RecordedEndpoint(200, second) as alone:
        post(
            capture_request_bodies.bodies(
                plain, markers=capture_request_bodies.markers_for("qwen3.5-9b-q4km.json")
            )["completion"],
            endpoint=alone.endpoint,
            timeout=5.0,
        )
    assert len(alone.sent) == 1, "no closing marker is one span and no reasoning"
