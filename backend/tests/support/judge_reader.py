"""Drive the real model reader through an in-memory native completion transport."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any

from idhazh.llm.server import Completion, parse_completion

from .models import a_markers

if TYPE_CHECKING:
    from idhazh.content_similarity_judge.model_reader import ModelReader


def native_reply(
    content: str,
    *,
    pieces: tuple[str, ...] | None = None,
    alternatives: tuple[tuple[str, float], ...] = (("YES", -0.1), ("NO", -2.0), ("UN", -3.0)),
    prompt_tokens: int = 7,
    completion_tokens: int = 2,
) -> bytes:
    """The smallest native protocol input that carries selected positions and costs."""
    positions: list[dict[str, Any]] = [
        {"id": index, "token": piece, "bytes": list(piece.encode("utf-8"))}
        for index, piece in enumerate((content,) if pieces is None else pieces)
    ]
    if positions:
        positions[0]["top_logprobs"] = [
            {"id": index, "token": token, "logprob": logprob}
            for index, (token, logprob) in enumerate(alternatives)
        ]
    return json.dumps({
        "content": content,
        "completion_probabilities": positions,
        "tokens_evaluated": prompt_tokens,
        "tokens_predicted": completion_tokens,
    }).encode("utf-8")


class ProtocolReplies(AbstractContextManager["ProtocolReplies"]):
    """A finite, repeatable response stream at the completion transport boundary."""

    def __init__(self, *responses: bytes) -> None:
        if not responses:
            raise ValueError("the response stream must not be empty")
        self.responses = responses
        self.decodes: list[dict[str, Any]] = []

    def __call__(self, body: dict[str, Any]) -> Completion:
        response = self.responses[len(self.decodes) % len(self.responses)]
        self.decodes.append(dict(body))
        return parse_completion(response.decode("utf-8"))

    @property
    def reader(self) -> ModelReader:
        from idhazh.content_similarity_judge.model_reader import ModelReader

        return ModelReader(self, a_markers())

    def __exit__(self, *_exc: object) -> None:
        pass
