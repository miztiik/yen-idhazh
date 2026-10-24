"""Prove active test settings and recorded templates follow the selected model."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

import pytest
from contracts._fixtures import copy_config
from support.models import (
    a_sampling,
    a_server,
    active_model_file,
    committed_markers,
    committed_renderings,
)
from support.paths import CONFIG_DIR, read_text
from support.prompts import label_payload
from support.server import RecordedEndpoint, render_template_response

from idhazh import config
from idhazh.contracts.article import Article
from idhazh.llm.server import PROBE_SYSTEM, PROBE_USER, render_prompt

pytestmark = pytest.mark.contract


def select_model(root: Path, name: str) -> Path:
    copy_config(root)
    config_dir = root / "config"
    shutil.copyfile(CONFIG_DIR / "models" / name, config_dir / "models" / name)
    app_path = config_dir / "idhazh.json"
    app = json.loads(read_text(app_path))
    app["models_file"] = f"models/{name}"
    app_path.write_text(json.dumps(app), encoding="utf-8")
    return config_dir


@pytest.mark.parametrize("name", ["gemma-4-e4b-qat.json", "qwen3.5-9b-q4km-thinking.json"])
def test_active_helpers_follow_a_changed_pointer(
    tmp_path: Path, name: str, article_ok: Article
) -> None:
    config_dir = select_model(tmp_path, name)
    settings = config.load(config_dir)
    expected = committed_renderings(name)
    markers = committed_markers(config_dir=config_dir)

    assert active_model_file(config_dir) == settings.app.models_file
    assert committed_renderings(config_dir=config_dir) == expected
    assert (
        render_prompt(system=PROBE_SYSTEM, user=PROBE_USER, markers=markers)
        == expected["prompt_today"]
    )
    assert a_server(config_dir) == settings.models.summarizer.server
    assert a_sampling(config_dir) == settings.models.summarizer.sampling
    payload = label_payload(article_ok, config_dir=config_dir)
    assert payload["model"] == settings.models.summarizer.id


def test_helpers_reread_settings_and_do_not_share_mutable_copies(tmp_path: Path) -> None:
    config_dir = select_model(tmp_path, "gemma-4-e4b-qat.json")
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
    model_path.write_text(json.dumps(raw), encoding="utf-8")
    assert a_sampling(config_dir)["temperature"] == 0.5


def test_missing_active_recording_names_the_model_instead_of_using_another(
    tmp_path: Path,
) -> None:
    config_dir = select_model(tmp_path, "gemma-4-e4b-qat.json")
    app_path = config_dir / "idhazh.json"
    app = json.loads(read_text(app_path))
    missing = "model-without-a-recording.json"
    shutil.copyfile(config_dir / app["models_file"], config_dir / "models" / missing)
    app["models_file"] = f"models/{missing}"
    app_path.write_text(json.dumps(app), encoding="utf-8")
    with pytest.raises(KeyError, match=missing):
        committed_markers(config_dir=config_dir)


def test_active_recording_must_name_the_selected_model(tmp_path: Path) -> None:
    config_dir = select_model(tmp_path, "gemma-4-e4b-qat.json")
    model_path = config_dir / active_model_file(config_dir)
    raw = json.loads(read_text(model_path))
    raw["summarizer"]["id"] = "changed-model-with-an-old-recording"
    model_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=raw["summarizer"]["id"]):
        committed_renderings(config_dir=config_dir)


@pytest.mark.parametrize("rendering", ["plain", "thinking", "history"])
def test_template_replay_selects_the_recorded_turns(tmp_path: Path, rendering: str) -> None:
    config_dir = select_model(tmp_path, "gemma-4-e4b-qat.json")
    body: dict[str, object] = {
        "messages": [
            {"role": "system", "content": PROBE_SYSTEM},
            {"role": "user", "content": PROBE_USER},
        ],
    }
    if rendering == "thinking":
        body["chat_template_kwargs"] = {"enable_thinking": True}
    if rendering == "history":
        body["messages"] = [
            {"role": "user", "content": PROBE_USER},
            {"role": "assistant", "content": "The earlier reply."},
            {"role": "user", "content": "Answer once more."},
        ]
    response = json.loads(render_template_response(body, config_dir=config_dir))
    assert response["prompt"] == committed_renderings(config_dir=config_dir)[rendering]


def test_local_endpoint_uses_selected_template_and_keeps_reply_order(tmp_path: Path) -> None:
    config_dir = select_model(tmp_path, "gemma-4-e4b-qat.json")
    messages = {
        "messages": [
            {"role": "system", "content": PROBE_SYSTEM},
            {"role": "user", "content": PROBE_USER},
        ],
    }
    replies = (b'{"answer":"first"}', b'{"answer":"second"}')
    with RecordedEndpoint(200, *replies, config_dir=config_dir) as endpoint:
        request = Request(
            endpoint.base_url + "/apply-template",
            data=json.dumps(messages).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            assert (
                json.load(response)["prompt"]
                == committed_renderings(config_dir=config_dir)["plain"]
            )
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
