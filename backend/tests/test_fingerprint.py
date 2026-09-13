"""Unit- and contract-tier tests for the pipeline stamp.

The row exists because eleven of sixteen enumerated drift sources are silent
without it, so the tests are written against blindness rather than against
happy paths: every declared input must move the digest, and a field that stops
moving it is the failure this file is here to catch.

The record gates nothing since 2026-09-10. One alarm is left - `prose_changed_alone`
- and it reports rather than blocks, so the tests below ask what it says and never
what it withholds.

The closed-world block is contract tier (`CLAUDE.md` section 13). It holds the
stamp and `InferenceConfig` to one another, so a knob added to config is either
digested or written down as undigested, and never simply forgotten.

No mocks and no network (Guardrail #7): the stamp under test is the committed
fixture, so the test and the fixture cannot drift apart.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.app_config import AppConfig, InferenceConfig, ModelRef
from idhazh.contracts.base import Contract
from idhazh.contracts.fingerprint import FingerprintRow, PipelineInputs
from idhazh.corpus import read_rows, scored_from_items
from idhazh.fingerprint import (
    MACHINE_INPUTS,
    NOT_DIGESTED,
    PLACEHOLDER_DIGEST,
    PROSE_INPUTS,
    UNRECORDED_BUILD,
    build_inputs,
    digested_inference_fields,
    host_cpu,
    prose_changed_alone,
    runner_class,
    runtime_build,
    runtime_flags_spelling,
    sampling_spelling,
)
from idhazh.ledger import load_retirements

pytestmark = pytest.mark.contract

FIXTURE = CONTRACT_FIXTURES_DIR / "fingerprint-row" / "first-seen.json"
HEX64 = re.compile(r"[0-9a-f]{64}")

#: Ruled on 2026-08-25: these five change the arithmetic, so leaving them out
#: of the stamp was a blind spot. Row #10 digested them on 2026-08-26, folded
#: into `runtime_flags`, riding the model swap's fingerprint reset rather than
#: spending a second one. This list is what stops a quiet reversal.
RULED_LOGIT_MOVERS: Final[frozenset[str]] = frozenset(
    {"cache_type_k", "cache_type_v", "flash_attention", "n_parallel", "n_threads_batch"}
)

#: `sha256` here is what config expected. What the runtime opened is the
#: separate `model_sha256` argument, and the two are deliberately unequal.
CONFIGURED_MODEL: Final = ModelRef(
    id="qwen3-8b-q4-k-m",
    repo="Qwen/Qwen3-8B-GGUF",
    file="Qwen3-8B-Q4_K_M.gguf",
    quantisation="Q4_K_M",
    sha256="a" * 64,
)


def stamp_with(model_sha256: str | None) -> PipelineInputs:
    """`build_inputs` with everything but the observed weights digest held still."""
    return build_inputs(
        model=CONFIGURED_MODEL,
        model_sha256=model_sha256,
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


def committed_row() -> FingerprintRow:
    return FingerprintRow.from_json(read_text(FIXTURE))


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


# --- Contract tier: the inference knobs are a closed world ------------------


def unclassified_knobs(knobs: Iterable[str]) -> frozenset[str]:
    """Knob names that neither reach the stamp nor sit in `NOT_DIGESTED`."""
    return frozenset(knobs) - digested_inference_fields() - frozenset(NOT_DIGESTED)


def test_every_inference_knob_is_digested_or_written_down_as_undigested() -> None:
    """A knob nobody classified is a drift source nobody recorded."""
    missing = unclassified_knobs(InferenceConfig.model_fields)
    assert not missing, (
        "classify these in idhazh.fingerprint.NOT_DIGESTED, or digest them in "
        f"PipelineInputs: {sorted(missing)}"
    )


def test_a_new_knob_nobody_classified_fails_the_check() -> None:
    """The check has to bite, or the closed world is only a comment."""
    with_an_unclassified_knob = [*InferenceConfig.model_fields, "cache_reuse"]
    assert unclassified_knobs(with_an_unclassified_knob) == {"cache_reuse"}


def test_no_knob_is_both_digested_and_written_down_as_undigested() -> None:
    """A knob in both places means one of the two statements is false."""
    assert not digested_inference_fields() & frozenset(NOT_DIGESTED)


def test_the_undigested_set_names_only_real_knobs() -> None:
    """A renamed knob leaves a stale name here, and the stale name proves nothing."""
    assert frozenset(NOT_DIGESTED) <= frozenset(InferenceConfig.model_fields)


def test_every_undigested_knob_carries_a_reason() -> None:
    assert all(entry.reason.strip() for entry in NOT_DIGESTED.values())


@pytest.mark.parametrize("knob", sorted(RULED_LOGIT_MOVERS))
def test_a_ruled_blind_spot_is_digested_or_still_flagged(knob: str) -> None:
    """Marking one of these safe would retire a known drift source without a reason."""
    entry = NOT_DIGESTED.get(knob)
    assert knob in digested_inference_fields() or (entry is not None and entry.moves_logits), (
        f"{knob} was ruled a logit mover: digest it, or keep moves_logits=True"
    )


def test_the_folded_knobs_are_digested_through_their_spellings() -> None:
    """They reach the stamp folded into two fields, not under their own names."""
    folded = digested_inference_fields() - frozenset(PipelineInputs.model_fields)
    assert folded == {
        "temperature",
        "top_p",
        "seed",
        "max_output_tokens",
        "thinking",
        *RULED_LOGIT_MOVERS,
    }


def test_every_ruled_logit_mover_now_reaches_the_stamp() -> None:
    assert RULED_LOGIT_MOVERS <= digested_inference_fields()
    assert not RULED_LOGIT_MOVERS & frozenset(NOT_DIGESTED)


@pytest.mark.parametrize(
    "moved",
    [
        InferenceConfig(cache_type_k="q8_0"),
        InferenceConfig(cache_type_v="q8_0"),
        InferenceConfig(flash_attention="on"),
        InferenceConfig(n_parallel=2),
        InferenceConfig(n_threads_batch=8),
    ],
    ids=sorted(RULED_LOGIT_MOVERS),
)
def test_a_moved_runtime_knob_moves_the_stamp(moved: InferenceConfig) -> None:
    """The whole point of digesting them: a quantised cache or a second slot can
    rewrite a summary, and the stamp used to hold still while it did."""
    assert runtime_flags_spelling(moved) != runtime_flags_spelling(InferenceConfig())


def test_a_null_runtime_knob_spells_apart_from_a_pinned_one() -> None:
    """Null means the runtime picks, which is a different choice from pinning a
    value - so it gets its own spelling rather than one of the values it may
    resolve to."""
    spelling = runtime_flags_spelling(InferenceConfig())
    assert "cache_type_k=runtime-default" in spelling
    assert "n_threads_batch=runtime-default" in spelling


# --- The one alarm that survives the retired gate ---------------------------
#
# `classify` and the four observations it returned are gone with the gate they
# fed (owner decision, 2026-09-10): the skip-if-unchanged half was never wired
# to a caller, and the eval-window half withheld a quality number until N
# consecutive run-days ran at one digest, which in a repository whose prompts
# move weekly meant never. What is left reports and never blocks.


def moved(inputs: PipelineInputs, *names: str) -> PipelineInputs:
    """The same manifest with each named input moved to a different value."""
    return inputs.model_copy(
        update={name: a_different_value(getattr(inputs, name)) for name in names}
    )


@pytest.mark.parametrize("prose", sorted(PROSE_INPUTS))
def test_a_prose_input_moving_alone_is_the_alarm(prose: str) -> None:
    """The case nobody else can see: the same weights, the same binary, and
    different words asked of them."""
    before = committed_row().inputs

    assert prose_changed_alone(before, moved(before, prose)) == (prose,)


def test_every_prose_input_that_moved_is_named() -> None:
    """Naming them is the whole of the report, so one of three is not an answer."""
    before = committed_row().inputs

    assert set(prose_changed_alone(before, moved(before, *PROSE_INPUTS))) == set(PROSE_INPUTS)


@pytest.mark.parametrize("machine", sorted(MACHINE_INPUTS))
def test_a_machine_input_moving_too_is_a_model_change_and_not_this_alarm(machine: str) -> None:
    """An operator already reads a model swap off the boundary the console draws.

    Reporting it here as well would bury the one reading nothing else carries.
    """
    before = committed_row().inputs

    assert prose_changed_alone(before, moved(before, "prompt_sha256", machine)) == ()


def test_a_first_run_has_nothing_to_compare_against() -> None:
    """No earlier manifest is not a change, and reporting one would cry wolf
    on the first run after every model swap."""
    assert prose_changed_alone(None, committed_row().inputs) == ()


def test_a_run_that_moved_nothing_is_silent() -> None:
    inputs = committed_row().inputs

    assert prose_changed_alone(inputs, inputs) == ()


def test_the_change_names_the_input_that_moved_rather_than_saying_one_did() -> None:
    """Why the record is a list of names and not one digest.

    A digest affords equality and nothing else, which is a gate's only
    operation. The names come back in declaration order, so two runs compared
    twice read the same way round.
    """
    before = committed_row().inputs

    assert moved(before, "n_ctx").changed_inputs(before) == ("n_ctx",)
    assert before.changed_inputs(before) == ()
    assert moved(before, "sanitizer_version", "model_sha256").changed_inputs(before) == (
        "model_sha256",
        "sanitizer_version",
    )


# --- The four bounds this row declares ---------------------------------------

#: Items 18 to 21 of the plan's inventory: the reads ruled deliberately
#: unbounded, and the word each one's cover turns on. They are asserted here
#: rather than beside each module because they were declared together, in one
#: row, against one rule - and a set that is checked in four places drifts.
DECLARED_BOUNDS: Final[tuple[tuple[str, object, str], ...]] = (
    ("ledger.load_retirements", load_retirements, "-1"),
    ("corpus.scored_from_items", scored_from_items, "one run"),
    ("corpus.read_rows", read_rows, "finetune.corpus_rows"),
    ("contracts.base.Contract.read", Contract.read, "one payload"),
)


@pytest.mark.parametrize(
    ("name", "read", "cover"),
    DECLARED_BOUNDS,
    ids=[name for name, _, _ in DECLARED_BOUNDS],
)
def test_a_deliberately_unbounded_read_declares_its_cover(
    name: str, read: object, cover: str
) -> None:
    """Guardrail #12's escape hatch is a person agreeing in the open, so it is written down.

    Each of these four reads was ruled unbounded on purpose. The ruling is worth
    nothing to the next reader unless it sits next to the code, so each one names
    what it covers and why a cover in days is not the answer.
    """
    doc = inspect.getdoc(read) or ""
    assert "Cover:" in doc, f"{name} was ruled unbounded on purpose and declares no cover"
    assert cover in doc, f"{name} declares a cover that does not name {cover!r}"


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
    assert CONFIGURED_MODEL.sha256 == "a" * 64
    assert stamp_with("b" * 64).model_sha256 == "b" * 64


@pytest.mark.parametrize("unmeasured", [None, "", PLACEHOLDER_DIGEST])
def test_an_unmeasured_weights_digest_raises_rather_than_stamping_zeros(
    unmeasured: str | None,
) -> None:
    """Sixty-four zeroes satisfy `Sha256`, so the old placeholder validated and lied."""
    with pytest.raises(ValueError, match="no measured weights digest"):
        stamp_with(unmeasured)


@pytest.mark.parametrize("role", ["summarize", "visual_planner"])
def test_the_committed_config_records_a_measured_digest_for_every_model(role: str) -> None:
    """An expectation the run has to meet, and the CI gate checks the bytes against it."""
    models = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).models
    recorded = getattr(models, role).sha256
    assert recorded is not None, f"config records no sha256 for models.{role}"
    assert recorded != PLACEHOLDER_DIGEST, f"models.{role} carries the placeholder"


def test_the_prompt_and_the_schema_are_digested_not_stored() -> None:
    """A prompt reaching a persisted payload would put untrusted text in the ledger."""
    inputs = committed_row().inputs
    assert HEX64.fullmatch(inputs.prompt_sha256)
    assert HEX64.fullmatch(inputs.output_schema_sha256)
    assert HEX64.fullmatch(inputs.chat_template_sha256)


# --- What the run observes about the machine it ran on ----------------------


def test_the_runtime_build_is_the_one_the_job_pinned() -> None:
    """`digest.yml` sets it beside the download it checks against a sha256."""
    assert runtime_build({"LLAMA_CPP_BUILD": "b10598"}) == "b10598"


@pytest.mark.parametrize("environ", [{}, {"LLAMA_CPP_BUILD": ""}, {"LLAMA_CPP_BUILD": "   "}])
def test_an_unpinned_build_records_the_absence_rather_than_inventing_a_tag(
    environ: dict[str, str],
) -> None:
    """The literal this replaced named a build nobody checked (Guardrail #10)."""
    assert runtime_build(environ) == UNRECORDED_BUILD


def test_an_unpinned_build_stamps_apart_from_a_pinned_one() -> None:
    """Degrading honestly is only honest if the degraded run is distinguishable."""
    inputs = committed_row().inputs
    unpinned = inputs.model_copy(update={"runtime_build": UNRECORDED_BUILD})
    pinned = inputs.model_copy(update={"runtime_build": "b10598"})
    assert unpinned.fingerprint() != pinned.fingerprint()


def test_the_runner_class_comes_from_the_runner_and_not_from_a_literal() -> None:
    environ = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
    }
    assert runner_class(environ) == "github-hosted/linux/x64"


def test_a_developer_machine_is_a_class_of_its_own() -> None:
    """It has to be, or a laptop's summaries file under the runner's stamp."""
    assert runner_class({}).startswith("local/")


def test_a_runner_that_did_not_name_its_class_is_not_called_a_laptop() -> None:
    """Inside Actions and unnamed is a third answer, not the local one."""
    assert runner_class({"GITHUB_ACTIONS": "true"}).startswith("github/")


def test_the_host_cpu_names_the_part_and_not_the_architecture(tmp_path: Path) -> None:
    """`x86_64` is the same string on every runner, so it explains no violation."""
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text(
        "processor\t: 0\nvendor_id\t: GenuineIntel\n"
        "model name\t: Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz\n"
        "cache size\t: 49152 KB\n",
        encoding="utf-8",
    )
    assert host_cpu(cpuinfo) == "Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz"


def test_a_host_that_names_no_processor_still_answers(tmp_path: Path) -> None:
    """The field is required, and an empty one would fail the row it explains."""
    assert host_cpu(tmp_path / "absent").strip()
