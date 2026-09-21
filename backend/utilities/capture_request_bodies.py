"""Write one golden request body per committed model file, per route.

Run it, commit what it writes, and `backend/tests/test_request_bodies.py` then
holds every route's body to those bytes minus the keys a change is allowed to
move. The bodies are built from the committed entries rather than from a
literal, so a knob that reaches a request reaches the golden file too.

    python backend/utilities/capture_request_bodies.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.llm.server import (
    completion_payload,
    continued_completion_payload,
    grammar_completion_payload,
    request_payload,
    thinking_span,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "config" / "models"
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "request-bodies"

#: Fixed inputs, so the only thing that moves between two captures is the entry
#: and the builder. Short enough to read in a diff.
SYSTEM = "You summarize one article."
USER = "An article about a bridge."
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
    "additionalProperties": False,
}
GRAMMAR = 'root ::= "same" | "different" | "unclear"'
BUDGET = 512
CONTINUED_BUDGET = 1024
ALTERNATIVES = 3


def bodies(config: ModelsConfig) -> dict[str, Any]:
    """Every route's body for one entry, keyed by the route that posts it."""
    entry = config.summarize
    inference, turns = entry.inference, entry.turns
    completion = completion_payload(
        model_id=entry.id,
        system=SYSTEM,
        user=USER,
        output_schema=SCHEMA,
        inference=inference,
        turns=turns,
        max_answer_tokens=BUDGET,
    )
    captured: dict[str, Any] = {
        "chat": request_payload(
            model_id=entry.id,
            system=SYSTEM,
            user=USER,
            output_schema=SCHEMA,
            inference=inference,
            turns=turns,
        ),
        "completion": completion,
        "grammar": grammar_completion_payload(
            model_id=entry.id,
            system=SYSTEM,
            user=USER,
            grammar=GRAMMAR,
            inference=inference,
            turns=turns,
            max_answer_tokens=BUDGET,
            first_token_alternatives=ALTERNATIVES,
        ),
        "continued": continued_completion_payload(
            completion,
            reply='{"title": "a bridge"}',
            user="Now the picture.",
            output_schema=SCHEMA,
            turns=turns,
            max_answer_tokens=CONTINUED_BUDGET,
        ),
    }
    if turns.thinks:
        captured["thinking_span"] = thinking_span(completion, turns=turns)
    return captured


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(MODELS_DIR.glob("*.json")):
        config = ModelsConfig.model_validate_json(path.read_text(encoding="utf-8"))
        written = GOLDEN_DIR / path.name
        written.write_text(
            json.dumps(bodies(config), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"wrote {written.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
