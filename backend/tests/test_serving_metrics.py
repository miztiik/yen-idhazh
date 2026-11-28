"""Can a closing observation claim only the readings its runtime reported?"""

from pathlib import Path

import pytest
from support.paths import FIXTURES_DIR

from idhazh.llm.serving_metrics import (
    CAPTURE_BYTES,
    legacy_model_load_ms,
    read_startup_log,
    retain_serving_capture,
    server_prompt_totals,
    serving_measurement,
)


def test_last_pair_preserves_zero_and_does_not_invent_a_weights_clock() -> None:
    text = "llamacpp:prompt_tokens_total 0\nllamacpp:prompt_seconds_total 0.0\n"
    measured = serving_measurement(text, subject_id="summary", outcome="success")
    assert measured is not None
    assert (measured["server_prompt_tokens"], measured["server_prompt_seconds"]) == (0, 0.0)
    assert measured["model_load_ms"] is None
    assert "elapsed_ms" not in measured


def test_partial_capture_preserves_legacy_diagnostics_but_not_a_serving_row(tmp_path: Path) -> None:
    raw = (
        b"llamacpp:prompt_tokens_total 100\n"
        b"llamacpp:n_tokens_max 4096\n"
        b"llamacpp:n_busy_slots_per_decode 1.0\n"
    )
    path = tmp_path / "llama-metrics.prom"
    measurement = retain_serving_capture(
        path, raw, subject_id="summary", outcome="success",
        started_at="2026-11-26T00:00:00Z", finished_at="2026-11-26T00:00:01Z",
    )
    assert measurement is None
    assert path.read_bytes() == raw
    assert server_prompt_totals(path.read_text(encoding="utf-8")) == (100, None)


def test_an_ambiguous_final_read_cannot_be_filed() -> None:
    tokens = "llamacpp:prompt_tokens_total 100\n"
    with pytest.raises(ValueError, match="duplicate llamacpp:prompt_tokens_total"):
        serving_measurement(
            tokens + tokens + "llamacpp:prompt_seconds_total 1\n",
            subject_id="summary", outcome="error",
        )
    with pytest.raises(ValueError, match="invalid llamacpp:prompt_seconds_total"):
        serving_measurement(
            tokens + "llamacpp:prompt_seconds_total Inf\n",
            subject_id="summary", outcome="error",
        )


def test_legacy_startup_markers_survive_a_long_inference_log(tmp_path: Path) -> None:
    log = tmp_path / "owned-server.log"
    log.write_bytes(
        b"0.00.100.000 I srv    load_model: loading model 'summary.gguf'\n"
        b"0.01.500.000 I srv    load_model: initializing slots\n"
        b"0.02.100.000 I srv  llama_server: model loaded\n"
        + b"x" * CAPTURE_BYTES
    )
    assert legacy_model_load_ms(read_startup_log(log)) == 2000.0


def test_recorded_server_sources_keep_load_and_prompt_values() -> None:
    runtime = FIXTURES_DIR / "runtime"
    startup = runtime / "2026-08-29-3-shard-0.server-head.txt"
    scrape = runtime / "2026-08-26-5-shard-0.prom"
    assert legacy_model_load_ms(read_startup_log(startup)) == pytest.approx(3797.640)
    assert server_prompt_totals(scrape.read_text(encoding="utf-8")) == (30538, 2795.15)
