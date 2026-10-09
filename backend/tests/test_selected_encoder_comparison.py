"""A selected comparison leaves saved controls alone and keeps task settings."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from utilities.compare_summary_encoders import read_config, select_encoders, stage_collect

CONFIG = Path(__file__).resolve().parents[2] / "config" / "encoder-comparison.json"


def test_only_the_two_requested_shards_are_selected() -> None:
    chosen = select_encoders(read_config(CONFIG), "embeddinggemma-two,jina-v5-nano")
    assert [encoder["slug"] for encoder in chosen] == ["embeddinggemma-two", "jina-v5-nano"]


@pytest.mark.parametrize("selected", ["unknown", "gte-small,gte-small", "gte-small,"])
def test_invalid_selection_fails_before_encoding(selected: str) -> None:
    with pytest.raises(ValueError):
        select_encoders(read_config(CONFIG), selected)


def test_selected_models_use_symmetric_prompts_and_pinned_fp32_weights() -> None:
    gemma, jina = select_encoders(read_config(CONFIG), "embeddinggemma-two,jina-v5-nano")
    assert gemma["model_options"]["config_kwargs"] == {
        "vision_config": None, "audio_config": None,
    }
    assert gemma["prefix"] == "task: sentence similarity | query: "
    assert jina["model_id"] == "jinaai/jina-embeddings-v5-text-nano-text-matching"
    assert jina["prefix"] == "Document: "
    for encoder in (gemma, jina):
        assert len(encoder["model_options"]["revision"]) == 40
        assert encoder["model_options"]["model_kwargs"]["dtype"] == "float32"
        assert encoder["encode_options"] == {"prompt": ""}


def test_collect_preserves_the_saved_control(tmp_path: Path) -> None:
    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({
        "first_day": "2026-09-01", "last_day": "2026-09-01", "days_named": 1,
        "articles_read": 2, "articles_encoded": 2,
        "same_pairs": 1, "different_pairs": 1, "pair_build": {},
    }), encoding="utf-8")
    output = tmp_path / "readings"
    output.mkdir()
    old = {"slug": "minilm-l6", "model_id": "baseline", "state": "unavailable",
           "reason": "recorded fixture", "why": "a saved control",
           "pair_set_sha256": hashlib.sha256(pairs.read_bytes()).hexdigest()}
    (output / "encoders.json").write_text(
        json.dumps({"encoders": [old]}), encoding="utf-8"
    )
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    new = {"slug": "embeddinggemma-two", "model_id": "google/embeddinggemma-2",
           "state": "unavailable", "reason": "recorded fixture", "why": "a new candidate"}
    (incoming / "embeddinggemma-two.json").write_text(json.dumps(new), encoding="utf-8")
    stage_collect(argparse.Namespace(
        config=CONFIG, pairs=pairs, readings_from=incoming, out=output,
        commit="", run_url="", selected="embeddinggemma-two", preserve_existing=True,
    ))
    readings = json.loads((output / "encoders.json").read_text(encoding="utf-8"))
    assert {row["slug"]: row for row in readings["encoders"]} == {
        "minilm-l6": old, "embeddinggemma-two": new,
    }
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["encoders_asked"] == 1
    assert manifest["encoders_selected"] == ["embeddinggemma-two"]


def test_collect_rejects_a_saved_row_for_another_pair_set(tmp_path: Path) -> None:
    test_collect_preserves_the_saved_control(tmp_path)
    output = tmp_path / "readings"
    data = json.loads((output / "encoders.json").read_text(encoding="utf-8"))
    data["encoders"][1]["pair_set_sha256"] = "0" * 64
    (output / "encoders.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="saved pair set differs"):
        stage_collect(argparse.Namespace(
            config=CONFIG, pairs=tmp_path / "pairs.json",
            readings_from=tmp_path / "incoming", out=output,
            commit="", run_url="", selected="embeddinggemma-two", preserve_existing=True,
        ))
