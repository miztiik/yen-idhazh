"""Unit-tier tests for the pipeline stamp.

The row exists because eleven of sixteen enumerated drift sources are silent
without it, so the tests are written against blindness rather than against
happy paths: every declared input must move the digest, and a field that stops
moving it is the failure this file is here to catch.

No mocks and no network (Rule #7): the stamp under test is the committed
fixture, so the test and the fixture cannot drift apart.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, STATE_DIR, read_text

from idhazh.contracts.app_config import InferenceConfig, ModelRef
from idhazh.contracts.fingerprint import FingerprintRow, PipelineInputs
from idhazh.fingerprint import (
    LEDGER_RELPATH,
    Observation,
    append_new,
    build_inputs,
    classify,
    read_ledger,
    sampling_spelling,
    text_digest,
)

FIXTURE = CONTRACT_FIXTURES_DIR / "fingerprint-row" / "first-seen.json"
HEX64 = re.compile(r"[0-9a-f]{64}")


def committed_row() -> FingerprintRow:
    return FingerprintRow.from_json(read_text(FIXTURE))


def restamp(inputs: PipelineInputs, **changes: Any) -> FingerprintRow:
    """A row for a mutated input set, with the digest rebuilt to match."""
    moved = inputs.model_copy(update=changes)
    template = committed_row()
    return template.model_copy(
        update={"inputs": moved, "pipeline_fingerprint": moved.fingerprint()}
    )


def a_different_value(value: object) -> object:
    if isinstance(value, int):
        return value + 1
    text = str(value)
    if HEX64.fullmatch(text):
        return ("1" if text.startswith("0") else "0") + text[1:]
    return f"{text}-moved"


# --- The Oracle: the stamp is not blind ------------------------------------


@pytest.mark.parametrize("field", sorted(PipelineInputs.model_fields))
def test_every_declared_input_moves_the_fingerprint(field: str) -> None:
    """A declared input that does not move the digest is a silent drift source."""
    inputs = committed_row().inputs
    moved = inputs.model_copy(update={field: a_different_value(getattr(inputs, field))})
    assert moved.fingerprint() != inputs.fingerprint(), f"{field} does not reach the digest"


def test_the_truncation_cap_alone_moves_the_fingerprint() -> None:
    """The named trap: a cap change is a config edit that rewrites every summary."""
    inputs = committed_row().inputs
    widened = inputs.model_copy(update={"truncation_cap_tokens": inputs.truncation_cap_tokens * 2})
    assert widened.fingerprint() != inputs.fingerprint()


def test_host_cpu_is_recorded_but_never_digested() -> None:
    """Including it would make every runner a different stamp, hiding the violation."""
    assert "host_cpu" not in PipelineInputs.model_fields
    row = committed_row()
    elsewhere = row.model_copy(update={"host_cpu": "Intel Xeon Platinum 8370C"})
    assert elsewhere.pipeline_fingerprint == row.pipeline_fingerprint


def test_the_fingerprint_is_rebuilt_not_trusted() -> None:
    payload = committed_row().model_dump(mode="json")
    payload["pipeline_fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="rebuilt on read"):
        FingerprintRow.model_validate(payload)


def test_the_digest_is_stable_across_construction_order() -> None:
    inputs = committed_row().inputs
    rebuilt = PipelineInputs.model_validate(
        dict(reversed(list(inputs.model_dump(mode="json").items())))
    )
    assert rebuilt.fingerprint() == inputs.fingerprint()


# --- What a prior stamp means ----------------------------------------------


def test_no_prior_stamp_is_a_first_run() -> None:
    assert classify(prior_fingerprint=None, current_fingerprint="a" * 64) is Observation.FIRST_RUN


def test_a_different_stamp_runs_the_work() -> None:
    assert (
        classify(prior_fingerprint="a" * 64, current_fingerprint="b" * 64)
        is Observation.INPUTS_CHANGED
    )


def test_a_matching_stamp_does_no_work() -> None:
    """Identical inputs measured nothing, so they write no eval row."""
    observation = classify(prior_fingerprint="a" * 64, current_fingerprint="a" * 64)
    assert observation is Observation.UNCHANGED


def test_a_matching_stamp_with_unequal_output_is_recorded_not_raised() -> None:
    observation = classify(
        prior_fingerprint="a" * 64,
        prior_output_digest=text_digest("one"),
        current_fingerprint="a" * 64,
        current_output_digest=text_digest("another"),
    )
    assert observation is Observation.DETERMINISM_VIOLATION


def test_a_matching_stamp_with_equal_output_is_unchanged() -> None:
    digest = text_digest("the same words")
    observation = classify(
        prior_fingerprint="a" * 64,
        prior_output_digest=digest,
        current_fingerprint="a" * 64,
        current_output_digest=digest,
    )
    assert observation is Observation.UNCHANGED


# --- The ledger -------------------------------------------------------------


def test_a_changed_cap_records_a_second_observation(tmp_path: Path) -> None:
    """The row's acceptance gate, end to end."""
    ledger = tmp_path / LEDGER_RELPATH
    first = committed_row()

    assert append_new(ledger, [first]) == [first]
    assert append_new(ledger, [first]) == [], "a known stamp is never appended twice"

    widened = restamp(first.inputs, truncation_cap_tokens=first.inputs.truncation_cap_tokens * 2)
    assert append_new(ledger, [widened]) == [widened]

    stored = read_ledger(ledger)
    assert set(stored) == {first.pipeline_fingerprint, widened.pipeline_fingerprint}


def test_the_ledger_round_trips_through_flat_columns(tmp_path: Path) -> None:
    ledger = tmp_path / LEDGER_RELPATH
    row = committed_row()
    append_new(ledger, [row])
    assert read_ledger(ledger)[row.pipeline_fingerprint] == row


def test_an_absent_ledger_reads_as_empty(tmp_path: Path) -> None:
    assert read_ledger(tmp_path / LEDGER_RELPATH) == {}


def test_the_committed_ledger_carries_the_declared_columns() -> None:
    """A hand-edited header would silently reorder every future row."""
    committed = STATE_DIR / "fingerprints.csv"
    with committed.open("r", encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    assert tuple(header) == FingerprintRow.csv_columns()


def test_every_column_is_a_scalar() -> None:
    row = committed_row()
    assert set(row.csv_row()) == set(FingerprintRow.csv_columns())
    assert all(isinstance(value, str) for value in row.csv_row().values())


# --- Building the stamp -----------------------------------------------------


def test_sampling_has_exactly_one_spelling() -> None:
    assert sampling_spelling(InferenceConfig()) == sampling_spelling(InferenceConfig())


def test_a_moved_decoding_knob_moves_the_sampling_spelling() -> None:
    assert sampling_spelling(InferenceConfig(temperature=0.7)) != sampling_spelling(
        InferenceConfig()
    )
    assert sampling_spelling(InferenceConfig(thinking=True)) != sampling_spelling(InferenceConfig())


def test_the_stamp_digests_the_weights_that_loaded_not_the_ones_configured() -> None:
    """Config records an expectation; the stamp records what the runtime opened."""
    configured = ModelRef(
        id="qwen3-8b-q4-k-m",
        repo="Qwen/Qwen3-8B-GGUF",
        file="Qwen3-8B-Q4_K_M.gguf",
        quantisation="Q4_K_M",
        sha256="a" * 64,
    )
    inputs = build_inputs(
        model=configured,
        model_sha256="b" * 64,
        inference=InferenceConfig(),
        truncation_cap_tokens=2500,
        runtime_build="llama.cpp-b4200",
        chat_template="{{ messages }}",
        prompt="Summarize the delimited article.",
        output_schema='{"type":"object"}',
        runner_class="ubuntu-latest-4vcpu",
        extractor_version="trafilatura-2.0.0",
        sanitizer_version="idhazh-sanitizer-1",
    )
    assert inputs.model_sha256 == "b" * 64


def test_the_prompt_and_the_schema_are_digested_not_stored() -> None:
    """A prompt reaching a persisted payload would put untrusted text in the ledger."""
    inputs = committed_row().inputs
    assert HEX64.fullmatch(inputs.prompt_sha256)
    assert HEX64.fullmatch(inputs.output_schema_sha256)
    assert HEX64.fullmatch(inputs.chat_template_sha256)
