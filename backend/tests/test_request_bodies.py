"""Does every committed entry post the body it posted yesterday, minus the caps?

Two questions, and they are one question asked at two grains. The golden files
hold each route's whole body for each committed model file, so a knob that
reaches a request reaches a reviewable diff. The span count holds the shape one
level up: a thinking entry is two POSTs and a plain entry is one, driven over a
real socket rather than inferred from what came back.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, RecordedEndpoint, read_text

from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.llm.server import answer_span, post, thinking_span
from utilities import capture_request_bodies

pytestmark = pytest.mark.contract

GOLDEN_DIR = FIXTURES_DIR / "request-bodies"

#: Every spelling of a decode cap either route has ever sent. A body carrying
#: one of these is a cap that came back, whichever key it came back under.
CAP_KEYS = ("max_tokens", "n_predict")


def model_files() -> list[Path]:
    """Every committed model file, which is bounded by how many models this
    project supports rather than by what the archive has piled up
    (`CLAUDE.md` Guardrail #12)."""
    return sorted((CONFIG_DIR / "models").glob("*.json"))


def model_id(path: Path) -> str:
    return path.stem


@pytest.mark.parametrize("path", model_files(), ids=model_id)
def test_every_route_posts_the_body_the_golden_file_holds(path: Path) -> None:
    """The bodies are pinned whole, so a knob that moves one is a reviewable diff.

    Regenerate with `python backend/utilities/capture_request_bodies.py` and
    read the diff - that is the review, and it is the only thing that can say a
    change to a builder moved a body nobody meant to move.
    """
    golden = GOLDEN_DIR / path.name
    assert golden.exists(), (
        f"{path.name} has no golden body - run backend/utilities/capture_request_bodies.py"
    )

    config = ModelsConfig.model_validate_json(read_text(path))
    built = capture_request_bodies.bodies(
        config, markers=capture_request_bodies.markers_for(path.name)
    )

    assert built == json.loads(read_text(golden))


@pytest.mark.parametrize("path", model_files(), ids=model_id)
def test_no_route_sends_a_token_cap_for_any_committed_entry(path: Path) -> None:
    """The row's oracle. Neither cap left a spelling behind on any route.

    The thinking span is the one body that still names `n_predict`, and it names
    llama.cpp's own word for infinity rather than a budget - the key is written
    there so span one cannot inherit the answer's grammar-derived number.
    """
    golden: dict[str, Any] = json.loads(read_text(GOLDEN_DIR / path.name))

    assert "max_tokens" not in golden["chat"], "the chat route sends no cap on either envelope"
    assert not set(CAP_KEYS) & golden["chat"].keys()
    assert golden.get("thinking_span", {"n_predict": -1})["n_predict"] == -1


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
    assert thinking.summarize.thinks, "the fixture entry stopped declaring a marker"
    assert not plain.summarize.thinks

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
