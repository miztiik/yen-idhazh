"""Refuse stale or incomplete generation and preserve the exact source and answer."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from summary_eval_pipeline.contracts import (
    GeneratedAnswer,
    text_sha256,
)
from summary_eval_pipeline.evaluation import bind_evaluations
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.generation import generate_summary
from summary_eval_pipeline.inputs import ManualInputs
from summary_eval_pipeline.model_selection import select_model, verify_staged_selection
from summary_eval_pipeline.phase_contracts import PhaseEvidence, PhaseShutdown
from summary_eval_pipeline.phase_result import build_evidence
from summary_eval_pipeline.phases import collect_phase
from summary_eval_pipeline.run_contracts import RUN_VERSION, GenerationReceipt, PreparedRun
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_eval_pipeline.storage import read_generation_result, read_result, write_result
from summary_evaluator_cases.contract_examples import REPOSITORY

from idhazh.llm.server import request_payload, server_argv
from summary_eval_tests.generation_cases import (
    chat_markers,
    handoff_case,
    native_generation_case,
    selected_root,
)
from summary_eval_tests.native_cases import RecordedLlama
from summary_eval_tests.scorer_evidence_cases import scorer_api_example


def generation_phase() -> tuple[ManualInputs, PreparedRun, GenerationReceipt, PhaseEvidence]:
    inputs, prepared, receipt = handoff_case()
    phase = build_evidence(
        None,
        None,
        None,
        PhaseShutdown(host_stopped=True, llama_stopped=True),
        [],
        run=prepared.run,
        phase="generation",
        generation_sha256=text_sha256(receipt.model_dump_json()),
        reference_summary_sha256=prepared.reference_summary_sha256,
        evaluate_relevance=prepared.evaluate_relevance,
    )
    return inputs, prepared, receipt, phase


def test_generation_schema_uses_native_string_lengths_and_keeps_final_text_validation() -> None:
    schema = GeneratedAnswer.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"title", "summary"}
    for field in ("title", "summary"):
        assert schema["properties"][field]["minLength"] == 1
        assert "pattern" not in schema["properties"][field]
    for text in ("", " \n\t", "\ud800"):
        with pytest.raises(ValidationError):
            GeneratedAnswer.model_validate_json(json.dumps({"title": "Title.", "summary": text}))
    text = "  Exact answer.\n"
    assert GeneratedAnswer(title="Title.", summary=text).summary == text


def test_two_separate_declaration_selections_change_real_assets_flags_and_requests(
    tmp_path: Path,
) -> None:
    selected_root(tmp_path)
    pointer = (tmp_path / "config" / "idhazh.json").read_bytes()
    first = select_model(tmp_path, "models/ornith-1.5-9b-q5km.json")
    second = select_model(tmp_path, "models/qwen3.5-9b-q4km.json")
    assert first.identity.models_file != second.identity.models_file
    assert first.identity.sha256 != second.identity.sha256
    assert first.entry.file != second.entry.file and first.entry.revision != second.entry.revision
    assert first.entry.id != second.entry.id
    assert (
        first.entry.server
        == json.loads((tmp_path / "config" / first.identity.models_file).read_bytes())[
            "summarizer"
        ]["server"]
    )
    assert select_model(tmp_path, "").identity == first.identity
    assert select_model(tmp_path, "  ").identity == first.identity
    assert (tmp_path / "config" / "idhazh.json").read_bytes() == pointer


@pytest.mark.parametrize(
    "name",
    [
        "models/ornith-1.5-9b-q5km.json",
        "models/qwen3.5-9b-q4km.json",
    ],
)
def test_each_declared_invocation_supplies_its_native_arguments_and_sampling(
    tmp_path: Path,
    name: str,
) -> None:
    selected_root(tmp_path)
    if "qwen" in name:
        path = tmp_path / "config" / name
        authored = json.loads(path.read_bytes())
        authored["summarizer"]["server"]["--threads"] = 2
        authored["summarizer"]["sampling"]["top_p"] = 0.7
        path.write_text(json.dumps(authored), encoding="utf-8")
    selected = select_model(tmp_path, name)
    args = server_argv(
        binary=Path("native-server"),
        weights=Path("backend/models") / selected.identity.filename,
        model=selected.entry,
        server=selected.entry.server,
        port=8080,
    )
    request = request_payload(
        model_id=selected.entry.id,
        system=load_pipeline_settings(REPOSITORY).generation_instruction,
        user="Exact source.",
        output_schema={"type": "object"},
        sampling=selected.entry.sampling,
        markers=chat_markers(selected),
    )
    assert args[args.index("--model") + 1] == str(
        Path("backend/models") / selected.identity.filename
    )
    assert args[args.index("--alias") + 1] == selected.entry.id
    assert args[args.index("--threads") + 1] == str(selected.entry.server["--threads"])
    assert (
        request["model"] == selected.entry.id
        and request["top_p"] == selected.entry.sampling["top_p"]
    )


@pytest.mark.parametrize("changed", ["destination", "declaration", "pointer"])
def test_changed_run_local_configuration_is_refused_before_model_start(
    tmp_path: Path,
    changed: str,
) -> None:
    selected_root(tmp_path)
    selected = select_model(tmp_path, "")
    verify_staged_selection(tmp_path, selected)
    filename = selected.identity.models_file if changed == "declaration" else "idhazh.json"
    path = tmp_path / "config" / filename
    value = json.loads(path.read_bytes())
    if changed == "destination":
        value["model_server"]["base_url"] = "http://127.0.0.1:8081"
    elif changed == "pointer":
        value["models_file"] = "models/qwen3.5-9b-q4km.json"
    else:
        value["summarizer"]["sampling"]["top_p"] = 0.7
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(WorkflowError):
        verify_staged_selection(tmp_path, selected)


@pytest.mark.parametrize(
    "name",
    [
        "../models/unsafe.json",
        "config/models/ornith-1.5-9b-q5km.json",
        "https://example.test/model.json",
        "a/repository",
        "C:\\model.json",
        "models\\unsafe.json",
        "models/missing.json",
        "models/../idhazh.json",
    ],
)
def test_invalid_model_paths_fail_before_startup(name: str) -> None:
    with pytest.raises(WorkflowError) as error:
        select_model(REPOSITORY, name)
    assert error.value.error.code == "MODEL_INVALID"
    assert name not in str(error.value)


def test_same_run_handoff_is_atomic_and_retains_exact_text(tmp_path: Path) -> None:
    inputs, prepared, receipt, phase = generation_phase()
    path = tmp_path / "generation.json"
    write_result(path, receipt)
    saved, saved_hash = read_generation_result(path, 2 << 20)
    request, unieval = bind_evaluations(
        prepared, inputs, saved, phase, generation_sha256=saved_hash
    )
    assert request.source_text == inputs.source_text
    assert request.summary_text == receipt.summary_text
    assert unieval.source_text == request.source_text
    assert unieval.summary_text == request.summary_text
    assert unieval.reference_summary_text == inputs.reference_summary_text
    assert "reference_summary_text" not in request.model_dump()
    assert request.request_id == unieval.request_id
    assert request.correlation_id == unieval.correlation_id
    assert saved.model_dump_json() == receipt.model_dump_json()
    assert not path.with_suffix(".json.tmp").exists()
    assert receipt.summary_text is not None
    assert receipt.summary_text not in phase.model_dump_json()


@pytest.mark.parametrize(
    "change",
    [
        "run",
        "attempt",
        "revision",
        "model",
        "source",
        "reference",
        "selection",
        "receipt_selection",
        "phase_selection",
        "summary",
        "failed",
        "unclosed",
        "host_unclosed",
        "invented_api",
        "preparation",
    ],
)
def test_stale_changed_failed_or_unclosed_generation_cannot_reach_either_evaluator(
    change: str,
) -> None:
    inputs, prepared, receipt, phase = generation_phase()
    if change == "run":
        receipt = receipt.model_copy(
            update={"run": receipt.run.model_copy(update={"run_id": "other-run"})}
        )
    elif change == "attempt":
        prepared = prepared.model_copy(
            update={"run": prepared.run.model_copy(update={"attempt": 2})}
        )
    elif change == "revision":
        prepared = prepared.model_copy(
            update={"run": prepared.run.model_copy(update={"git_sha": "b" * 40})}
        )
    elif change == "model":
        prepared = prepared.model_copy(
            update={"selected": select_model(REPOSITORY, "models/qwen3.5-9b-q4km.json").identity}
        )
    elif change == "source":
        inputs = inputs.model_copy(update={"source_text": inputs.source_text + "\n"})
    elif change == "reference":
        assert inputs.reference_summary_text is not None
        inputs = inputs.model_copy(
            update={"reference_summary_text": inputs.reference_summary_text + "\n"}
        )
    elif change == "selection":
        inputs = inputs.model_copy(update={"evaluate_relevance": False})
    elif change == "receipt_selection":
        receipt = receipt.model_copy(update={"evaluate_relevance": False})
    elif change == "phase_selection":
        phase = phase.model_copy(update={"evaluate_relevance": False})
    elif change == "summary":
        assert receipt.summary_text is not None
        receipt = receipt.model_copy(update={"summary_text": receipt.summary_text + "\n"})
    elif change == "failed":
        receipt = receipt.model_copy(update={"status": "failed"})
    elif change == "preparation":
        prepared = prepared.model_copy(update={"status": "pending"})
    elif change == "invented_api":
        phase = phase.model_copy(update={"scorer_apis": (scorer_api_example("hhem"),)})
    elif change == "host_unclosed":
        phase = phase.model_copy(
            update={
                "shutdown": phase.shutdown.model_copy(update={"host_stopped": False})
            }
        )
    else:
        phase = phase.model_copy(
            update={"shutdown": phase.shutdown.model_copy(update={"llama_stopped": False})}
        )
    with pytest.raises(WorkflowError) as failure:
        bind_evaluations(
            prepared, inputs, receipt, phase,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
    assert failure.value.error.code == "RECEIPT_INVALID"


def test_missing_generation_has_no_manual_answer_fallback(tmp_path: Path) -> None:
    with pytest.raises(WorkflowError):
        read_result(tmp_path / "generation.json", GenerationReceipt, 2 << 20)
    _, _, receipt, _ = generation_phase()
    data = receipt.model_dump(mode="json")
    data["summary_text"] = " \n"
    with pytest.raises(ValidationError):
        GenerationReceipt.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "field", ["api_stopped", "worker_exit_confirmed", "unieval_worker_exit_confirmed"]
)
def test_generation_evidence_cannot_claim_an_unstarted_evaluator_exit(field: str) -> None:
    _, _, _, phase = generation_phase()
    payload = json.loads(phase.model_dump_json())
    payload["shutdown"][field] = True
    with pytest.raises(ValidationError):
        PhaseEvidence.model_validate_json(json.dumps(payload))


def test_generation_evidence_cannot_invent_an_evaluation_application_outcome() -> None:
    _, _, _, phase = generation_phase()
    payload = json.loads(phase.model_dump_json())
    payload["servers"] = [
        {
            "server_name": "fastapi-server",
            "startup": "ready",
            "startup_ms": 0.0,
            "shutdown": "stopped",
            "exit_code": 0,
            "log_filename": None,
            "log_available": False,
        }
    ]
    with pytest.raises(ValidationError):
        PhaseEvidence.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "failure_kind", ["failed", "missing", "empty", "unfinished", "stale", "changed_reference"]
)
def test_invalid_generation_never_starts_either_evaluator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    selected_root(tmp_path)
    inputs, prepared, receipt, phase = generation_phase()
    directory = tmp_path / load_pipeline_settings(REPOSITORY).output_directory
    failure = WorkflowError("GENERATION_FAILED", "generation", "llama").error
    if failure_kind == "failed":
        receipt = GenerationReceipt(
            version=RUN_VERSION,
            run=receipt.run,
            selected=receipt.selected,
            loaded=receipt.loaded,
            source_sha256=receipt.source_sha256,
            reference_summary_sha256=receipt.reference_summary_sha256,
            evaluate_relevance=receipt.evaluate_relevance,
            summary_sha256=None,
            summary_text=None,
            status="failed",
            errors=(failure,),
        )
    elif failure_kind == "stale":
        receipt = receipt.model_copy(update={"run": receipt.run.model_copy(update={"attempt": 2})})
    elif failure_kind == "changed_reference":
        receipt = receipt.model_copy(update={"reference_summary_sha256": "b" * 64})
    write_result(directory / "run.json", prepared)
    if failure_kind != "missing":
        write_result(directory / "generation.json", receipt)
    if failure_kind == "empty":
        data = receipt.model_dump(mode="json")
        data["summary_text"] = " \n"
        (directory / "generation.json").write_text(json.dumps(data), encoding="utf-8")
    elif failure_kind == "unfinished":
        (directory / "generation.json").write_text('{"status":"complete"', encoding="utf-8")
    write_result(directory / "generation-phase.json", phase)
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"inputs": inputs.model_dump()}), encoding="utf-8")
    for key, value in {
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_RUN_ID": prepared.run.run_id,
        "GITHUB_RUN_ATTEMPT": str(prepared.run.attempt),
        "GITHUB_SHA": prepared.run.git_sha,
    }.items():
        monkeypatch.setenv(key, value)
    result = asyncio.run(collect_phase(tmp_path, "evaluation"))
    assert result.status == "failed" and result.evaluation is None and not result.servers
    assert result.unieval is None
    assert not (directory / "logs").exists()
    assert result.scorer_apis == ()


def test_independent_reference_can_coincidentally_equal_the_generated_answer() -> None:
    inputs, prepared, receipt, phase = generation_phase()
    assert receipt.summary_text is not None
    reference_hash = text_sha256(receipt.summary_text)
    inputs = inputs.model_copy(update={"reference_summary_text": receipt.summary_text})
    prepared = prepared.model_copy(update={"reference_summary_sha256": reference_hash})
    receipt = receipt.model_copy(update={"reference_summary_sha256": reference_hash})
    phase = phase.model_copy(
        update={
            "reference_summary_sha256": reference_hash,
            "generation_sha256": text_sha256(receipt.model_dump_json()),
        }
    )
    hhem, unieval = bind_evaluations(
        prepared, inputs, receipt, phase,
        generation_sha256=text_sha256(receipt.model_dump_json()),
    )
    assert hhem.summary_text == unieval.reference_summary_text == unieval.summary_text


def test_receipt_hash_uses_original_bytes_without_restamping_or_reserialization(
    tmp_path: Path,
) -> None:
    import hashlib

    inputs, prepared, receipt, phase = generation_phase()
    path = tmp_path / "generation.json"
    encoded = (json.dumps(receipt.model_dump(mode="json"), indent=2) + "\n").encode("utf-8")
    path.write_bytes(encoded)
    saved, saved_hash = read_generation_result(path, 2 << 20)
    assert saved.version == receipt.version == RUN_VERSION
    assert saved_hash == hashlib.sha256(encoded).hexdigest()
    assert saved_hash != text_sha256(saved.model_dump_json())
    bound_phase = phase.model_copy(update={"generation_sha256": saved_hash})
    hhem, unieval = bind_evaluations(
        prepared, inputs, saved, bound_phase, generation_sha256=saved_hash
    )
    assert hhem.summary_text == receipt.summary_text
    assert unieval.reference_summary_text == inputs.reference_summary_text
    assert path.read_bytes() == encoded


def test_evaluation_refuses_legacy_listener_before_any_child_launch(tmp_path: Path) -> None:
    from summary_evaluator.serve_http.api_settings import load_scorer_api_settings

    selected_root(tmp_path)
    path = tmp_path / "config" / "summary-evals" / "api.json"
    legacy = load_scorer_api_settings(path, "hhem")
    path.write_bytes(legacy.model_dump_json().encode("utf-8"))
    with pytest.raises(WorkflowError) as failure:
        asyncio.run(collect_phase(tmp_path, "evaluation"))
    assert failure.value.error.code == "INPUT_INVALID"
    directory = tmp_path / load_pipeline_settings(tmp_path).output_directory
    assert not (directory / "evaluation.json").exists()
    assert not (directory / "logs").exists()


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "length",
        "missing_finish",
        "empty",
        "wrong_model",
        "invalid",
        "multiple_choices",
        "duplicate_choices",
        "wrong_index",
    ],
)
def test_direct_native_generation_uses_selected_request_and_excludes_reasoning(
    tmp_path: Path,
    failure: str | None,
) -> None:
    async def check() -> None:
        inputs, prepared, selected, loaded = native_generation_case(tmp_path)
        recorded = RecordedLlama()
        if failure is not None:
            response = json.loads(recorded.body)
            if failure in ("length", "missing_finish"):
                response["choices"][0]["finish_reason"] = "length" if failure == "length" else None
            elif failure == "wrong_model":
                response["model"] = "another-model"
            elif failure in ("multiple_choices", "duplicate_choices"):
                response["choices"].append(
                    {
                        **response["choices"][0],
                        "index": 1 if failure == "multiple_choices" else 0,
                    }
                )
            elif failure == "wrong_index":
                response["choices"][0]["index"] = 1
            else:
                response["choices"][0]["message"]["content"] = "" if failure == "empty" else "{}"
            recorded.body = json.dumps(response).encode()
        pipeline = load_pipeline_settings(REPOSITORY)
        for name in (
            "summary-evals/api.json",
            "summary-evals/hhem-evaluator/settings.json",
            "summary-evals/unieval-evaluator/settings.json",
        ):
            (tmp_path / "config" / name).unlink()
        async with httpx.AsyncClient(
            transport=recorded.transport, trust_env=False, follow_redirects=False
        ) as client:
            call = generate_summary(
                client,
                inputs,
                prepared,
                selected,
                loaded,
                chat_markers(selected),
                pipeline,
            )
            if failure is not None:
                with pytest.raises(WorkflowError):
                    await call
            else:
                receipt = await call
                assert receipt.status == "complete" and receipt.summary_text
                assert "Let me reason" not in receipt.summary_text
                assert receipt.source_sha256 == text_sha256(inputs.source_text)
                assert receipt.reference_summary_sha256 == inputs.reference_summary_sha256
            assert len(recorded.requests) == 1
            native_url, encoded, _ = recorded.requests[0]
            body = json.loads(encoded)
            assert native_url == selected.native.base_url + "/v1/chat/completions"
            assert body["model"] == selected.entry.id
            assert body["messages"] == [
                {"role": "system", "content": pipeline.generation_instruction},
                {"role": "user", "content": inputs.source_text},
            ]
            assert body["chat_template_kwargs"]["enable_thinking"] is False
            for key, value in selected.entry.sampling.items():
                assert body[key] == value
            assert inputs.reference_summary_text is not None
            assert inputs.reference_summary_text not in encoded.decode()

    asyncio.run(check())
