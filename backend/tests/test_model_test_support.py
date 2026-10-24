"""Prove test settings follow any valid pointer while protocol inputs stay explicit."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

import pytest
from contracts._fixtures import copy_config, entry_with
from support.models import a_markers, a_sampling, a_server, active_model_file
from support.paths import FIXTURES_DIR, read_text
from support.prompts import label_payload
from support.server import RecordedEndpoint, render_template_response

from idhazh import config
from idhazh.contracts.article import Article
from idhazh.llm.server import (
    PROBE_FOLLOW_UP,
    PROBE_REPLY,
    PROBE_SYSTEM,
    PROBE_USER,
    derive_turn_markers,
    turn_markers_digest,
)

pytestmark = pytest.mark.contract


def select_model(root: Path) -> Path:
    """Write a valid model under a filename with no fixture entry."""
    pointer = copy_config(
        root,
        models=entry_with(
            id="a-model-without-a-recording",
            thinking_close=None,
            thinking_kwarg="reasoning",
        ),
    )
    config_dir = root / "config"
    name = "models/a-new-model.json"
    (config_dir / pointer).rename(config_dir / name)
    app_path = config_dir / "idhazh.json"
    app = json.loads(read_text(app_path))
    app["models_file"] = name
    app_path.write_text(json.dumps(app), encoding="utf-8", newline="\n")
    return config_dir


def test_active_helpers_accept_a_new_filename_without_a_recording(
    tmp_path: Path, article_ok: Article
) -> None:
    config_dir = select_model(tmp_path)
    settings = config.load(config_dir)

    assert active_model_file(config_dir) == settings.app.models_file
    assert a_server(config_dir) == settings.models.summarizer.server
    assert a_sampling(config_dir) == settings.models.summarizer.sampling
    payload = label_payload(article_ok, config_dir=config_dir)
    assert payload["model"] == settings.models.summarizer.id
    assert payload["prompt"].endswith(a_markers().reply_opening)


def test_helpers_reread_settings_and_do_not_share_mutable_copies(tmp_path: Path) -> None:
    config_dir = select_model(tmp_path)
    selected = config.load(config_dir).models.summarizer
    expected_server = selected.server.copy()
    expected_sampling = selected.sampling.copy()
    server = a_server(config_dir, **{"--ctx-size": 12345})
    sampling = a_sampling(config_dir, temperature=0.75)
    assert server["--ctx-size"] == 12345
    assert sampling["temperature"] == 0.75
    server.clear()
    sampling.clear()
    assert a_server(config_dir) == expected_server
    assert a_sampling(config_dir) == expected_sampling

    model_path = config_dir / active_model_file(config_dir)
    raw = json.loads(read_text(model_path))
    raw["summarizer"]["sampling"]["temperature"] = 0.5
    model_path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    assert a_sampling(config_dir)["temperature"] == 0.5


@pytest.mark.parametrize("rendering", ["plain", "thinking", "history"])
def test_template_response_uses_explicit_turns(rendering: str) -> None:
    markers = a_markers(thinking_close="</think>", thinking_kwarg="reasoning")
    body: dict[str, object] = {
        "messages": [
            {"role": "system", "content": PROBE_SYSTEM},
            {"role": "user", "content": PROBE_USER},
        ],
    }
    expected = markers.turn("system", PROBE_SYSTEM) + markers.turn("user", PROBE_USER)
    expected += markers.reply_opening
    if rendering == "thinking":
        body["chat_template_kwargs"] = {"reasoning": True}
        expected = markers.conversation(system=PROBE_SYSTEM, user=PROBE_USER)
        expected += markers.reply_opening_thinking
    if rendering == "history":
        body["messages"] = [
            {"role": "user", "content": PROBE_USER},
            {"role": "assistant", "content": PROBE_REPLY},
            {"role": "user", "content": PROBE_FOLLOW_UP},
        ]
        expected = (
            markers.turn("user", PROBE_USER)
            + markers.turn("assistant", PROBE_REPLY)
            + markers.turn("user", PROBE_FOLLOW_UP)
            + markers.reply_opening
        )
    assert json.loads(render_template_response(body, markers=markers))["prompt"] == expected


def test_local_endpoint_derives_explicit_markers_and_keeps_reply_order(tmp_path: Path) -> None:
    config_dir = select_model(tmp_path)
    entry = config.load(config_dir).models.summarizer
    markers = a_markers(thinking_kwarg=entry.thinking_kwarg)
    messages = {"messages": [{"role": "user", "content": "Answer once."}]}
    replies = tuple(
        (FIXTURES_DIR / "completions" / "rendered" / name).read_bytes()
        for name in ("thinking-span-one.json", "thinking-span-two.json")
    )
    with RecordedEndpoint(200, *replies, markers=markers) as endpoint:
        derived = derive_turn_markers(endpoint.base_url, entry=entry, timeout=5)
        assert turn_markers_digest(derived) == turn_markers_digest(markers)
        assert endpoint.served == 0
        for expected in (*replies, replies[0]):
            request = Request(
                endpoint.endpoint,
                data=json.dumps(messages).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=5) as response:
                assert response.read() == expected
        assert endpoint.served == 3
        assert endpoint.sent == [messages] * 3
