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
    TurnMarkers,
    completion_payload,
    continued_completion_payload,
    grammar_completion_payload,
    request_payload,
    thinking_span,
    turn_markers_from_renderings,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "config" / "models"
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "request-bodies"
#: The renderings each model's own template made, recorded once. A golden body
#: carries a prompt and a prompt is built from markers the server derives, so
#: this is where an offline capture gets them.
RENDERINGS = REPO_ROOT / "tests" / "fixtures" / "llm" / "derived-turn-markers.json"

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


def markers_for(model_file: str) -> TurnMarkers:
    """The markers one model's own template writes, off its recorded renderings."""
    recorded = json.loads(RENDERINGS.read_text(encoding="utf-8"))["entries"][model_file]
    return turn_markers_from_renderings(
        model_id=str(recorded["model_id"]),
        plain=str(recorded["plain"]),
        thinking=str(recorded["thinking"]),
        history=str(recorded["history"]),
        thinking_close=recorded["thinking_close"],
        thinking_kwarg=recorded["thinking_kwarg"],
    )


def bodies(config: ModelsConfig, *, markers: TurnMarkers) -> dict[str, Any]:
    """Every route's body for one entry, keyed by the route that posts it."""
    entry = config.summarizer
    server, sampling = entry.server, entry.sampling
    completion = completion_payload(
        model_id=entry.id,
        system=SYSTEM,
        user=USER,
        output_schema=SCHEMA,
        server=server,
        sampling=sampling,
        markers=markers,
        max_answer_tokens=BUDGET,
    )
    captured: dict[str, Any] = {
        "chat": request_payload(
            model_id=entry.id,
            system=SYSTEM,
            user=USER,
            output_schema=SCHEMA,
            sampling=sampling,
            markers=markers,
        ),
        "completion": completion,
        "grammar": grammar_completion_payload(
            model_id=entry.id,
            system=SYSTEM,
            user=USER,
            grammar=GRAMMAR,
            server=server,
            sampling=sampling,
            markers=markers,
            max_answer_tokens=BUDGET,
            first_token_alternatives=ALTERNATIVES,
        ),
        "continued": continued_completion_payload(
            completion,
            reply='{"title": "a bridge"}',
            user="Now the picture.",
            output_schema=SCHEMA,
            markers=markers,
            max_answer_tokens=CONTINUED_BUDGET,
        ),
    }
    if markers.thinks:
        captured["thinking_span"] = thinking_span(completion, markers=markers)
    return captured


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(MODELS_DIR.glob("*.json")):
        config = ModelsConfig.model_validate_json(path.read_text(encoding="utf-8"))
        written = GOLDEN_DIR / path.name
        written.write_text(
            json.dumps(
                bodies(config, markers=markers_for(path.name)),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"wrote {written.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
