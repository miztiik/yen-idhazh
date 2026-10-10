"""A selected comparison leaves saved controls alone and keeps task settings."""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from utilities.compare_summary_encoders import (
    read_config,
    select_encoders,
    stage_collect,
    stage_render,
)
from utilities.encoder_reading_table import render_readings

CONFIG = Path(__file__).resolve().parents[2] / "config" / "encoder-comparison.json"
WORKFLOW = CONFIG.parent.parent / ".github" / "workflows" / "encoder-comparison.yml"


def test_runtime_installs_cpu_image_dependencies_before_loading_the_model() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    install = next(
        step["run"] for step in workflow["jobs"]["score"]["steps"]
        if step.get("name") == "Install the encoder runtime"
    )
    assert "torch torchvision --index-url https://download.pytorch.org/whl/cpu" in install
    assert "sentence-transformers[image]>=6.1" in install
    assert "from PIL import Image" in install
    assert "from transformers import EmbeddingGemma2Processor" in install


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


def test_reading_table_uses_standard_terms_without_changing_saved_numbers() -> None:
    readings = [{
        "slug": "recorded-encoder", "state": "measured", "numbers_an_article": 384,
        "parameters_millions": 33, "separation": 0.91, "spread": 0.7,
        "same_mean": 0.9, "different_mean": 0.2, "ambiguous_mean": 0.5,
        "ambiguous_lean": 0.4, "related_mean": 0.8, "related_lean": 0.9,
        "articles_a_second": 12.0, "minutes_for_whole_archive": 2.0,
        "minutes_for_one_day": 0.1, "peak_memory_gb": 0.75,
    }]
    original = deepcopy(readings)
    table = render_readings(readings, archive_articles=1440, batch_articles=72)
    assert readings == original
    assert "Proxy ROC AUC" in table and "Mean cosine difference" in table
    assert "1440" not in table and "1,440 archive articles" in table
    assert "72 articles per batch" in table
    assert "Fraction above midpoint" in table and "not a standard selection metric" in table
    assert "not standard deviation, Cohen's d" in table
    assert "| `recorded-encoder` | 0.900 | 0.200 | 0.700 | 0.500 | 0.400 | 0.800 | 0.900 |" in table
    assert "**Spread**" not in table and "**Middle lean**" not in table
    assert "will join too much" not in table and "cannot tell an update" not in table


def test_render_saved_readings_leaves_the_measurement_and_manifest_unchanged(
    tmp_path: Path,
) -> None:
    readings = tmp_path / "encoders.json"
    readings.write_text(json.dumps({"encoders": [{
        "slug": "unavailable-encoder", "state": "unavailable",
        "articles_done": 0, "articles_to_encode": 10,
    }]}), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"run": "recorded"}', encoding="utf-8")
    original_readings, original_manifest = readings.read_bytes(), manifest.read_bytes()
    output = tmp_path / "encoders.md"
    stage_render(argparse.Namespace(config=CONFIG, readings=readings, out=output))
    assert readings.read_bytes() == original_readings
    assert manifest.read_bytes() == original_manifest
    assert "| `unavailable-encoder` | | | unavailable 0/10 | | | | |" in output.read_text()
    assert "\r\n" not in output.read_bytes().decode("utf-8")
