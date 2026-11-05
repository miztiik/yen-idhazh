"""How does the configured model produce both readings of one article pair?"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from idhazh import config
from idhazh.contracts.digest_day import DigestItem
from idhazh.llm.server import (
    TurnMarkers,
    completion_url,
    derive_turn_markers,
    post,
    request_timeout_seconds,
    resolve_endpoint,
    token_pieces,
)
from idhazh.similarity import judge, prompt


@dataclass(frozen=True, slots=True)
class ModelReader:
    """The model boundary, with the same judge logic for production and replay."""

    client: judge.Client
    markers: TurnMarkers

    @classmethod
    def from_settings(
        cls, settings: config.Settings, *, base_url: str | None = None
    ) -> ModelReader:
        base_url = base_url or resolve_endpoint(settings.app.model_server.base_url)
        entry = judge.entry_of(settings)
        timeout = request_timeout_seconds(entry)
        prompt.first_token_openings(partial(token_pieces, base_url, timeout=timeout))
        markers = derive_turn_markers(base_url, entry=entry, timeout=timeout)
        client = partial(
            post,
            endpoint=completion_url(base_url),
            timeout=timeout,
            reasoning_delimiters=entry.reasoning_delimiters,
        )
        return cls(client, markers)

    def read_pair(
        self, left: DigestItem, right: DigestItem, *, settings: config.Settings
    ) -> judge.Judged:
        return judge.judge_pair(
            left, right, client=self.client, markers=self.markers, settings=settings
        )
