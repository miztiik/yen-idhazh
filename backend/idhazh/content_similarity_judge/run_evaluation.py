"""How is the unchanged production judge captured without losing completed readings on failure?"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from idhazh import config, event_lines
from idhazh.atomic_write import write_atomic
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge.evaluation_events import (
    EvaluationCaptureStarted,
    EvaluationReadingRefused,
)
from idhazh.content_similarity_judge.freeze_evaluation import (
    private_output,
    validate_inputs,
)
from idhazh.content_similarity_judge.model_reader import ModelReader
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.content_similarity_judge_evaluation import (
    EvaluationCase,
    EvaluationCaseRun,
    EvaluationReading,
    EvaluationRun,
    EvaluationSet,
    EvaluationSplit,
    document_sha256,
)
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.knobs.models import ModelRef
from idhazh.contracts.story_similarity_pair import JUDGE_POLICY_VERSION
from idhazh.llm.server import Completion, turn_markers_digest
from idhazh.similarity import judge, prompt

LOG = logging.getLogger("idhazh")


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def config_sha256(settings: config.Settings) -> str:
    """Bind the loaded config snapshot and the judge-owned settings actually consulted."""
    return derive_text_digest(canonical_json({
        "inputs": [digest.model_dump(mode="json") for digest in settings.digests],
        "judge": judge_settings.load(settings.config_dir).model_dump(mode="json"),
    }))


def selected_cases(
    evaluation: EvaluationSet, split: EvaluationSplit,
) -> tuple[EvaluationCase, ...]:
    selected = tuple(case for case in evaluation.cases if case.split == split)
    if not selected:
        raise ValueError("the selected evaluation split has no cases")
    return selected


def start_run(
    evaluation: EvaluationSet, *, split: EvaluationSplit, settings: config.Settings,
    reader: ModelReader, host: HostFingerprintRow, git_sha: str, started_at: str,
) -> EvaluationRun:
    """Declare the complete selected universe before its first reading."""
    tuning = judge_settings.load_evaluation(settings.config_dir)
    validate_inputs(evaluation, max_cases=tuning.max_cases)
    selected = selected_cases(evaluation, split)
    entry = judge.entry_of(settings)
    return EvaluationRun(
        version=EvaluationRun.schema_version(),
        set_sha256=document_sha256(evaluation),
        split=split,
        model=ModelRef.model_validate(entry.model_dump(include=set(ModelRef.model_fields))),
        config_sha256=config_sha256(settings),
        prompt_digest=prompt.prompt_digest(
            prompt_files=settings.app.prompt_files, config_dir=settings.config_dir
        ),
        grammar_digest=prompt.grammar_digest(),
        judge_policy_version=JUDGE_POLICY_VERSION,
        envelope_sha256=turn_markers_digest(reader.markers),
        git_sha=git_sha,
        started_at=started_at,
        finished_at=None,
        host=host,
        state="not_run",
        cases=tuple(
            EvaluationCaseRun(case_id=case.case_id, input_sha256=case.input_sha256)
            for case in selected
        ),
    )


class ReadingCapture:
    """Trace the existing client boundary, retaining exact ordered request/response bytes."""

    def __init__(self, client: judge.Client) -> None:
        self.client = client
        self.requests: list[str] = []
        self.responses: list[str] = []

    def __call__(self, body: dict[str, Any]) -> Completion:
        # server.post uses this exact JSON serialization for the wire body.
        request_json = json.dumps(body)
        reply = self.client(body)
        if reply.raw_response is None:
            raise ValueError("the model boundary did not retain its actual raw response")
        self.requests.append(request_json)
        self.responses.append(reply.raw_response)
        return reply


def capture_reading(
    case: EvaluationCase, *, reverse: bool, reader: ModelReader, settings: config.Settings,
) -> EvaluationReading:
    """Run the real request/decode/parser/policy path, not a second judge implementation."""
    trace = ReadingCapture(reader.client)
    left, right = (case.right, case.left) if reverse else (case.left, case.right)
    reading = judge.read_once(
        left, right, client=trace, settings=settings, markers=reader.markers,
    )
    if reading.refusal_reason is not None:
        event_lines.emit(
            EvaluationReadingRefused(
                case_id=case.case_id, order="reverse" if reverse else "forward",
                reason=reading.refusal_reason,
            ),
            logger=LOG, level=logging.WARNING,
        )
    return EvaluationReading(
        verdict=reading.verdict,
        grammar_applied=reading.grammar_applied,
        refusal_reason=reading.refusal_reason,
        prompt_tokens=reading.prompt_tokens,
        completion_tokens=reading.completion_tokens,
        elapsed_seconds=reading.decode_seconds,
        first_token_margin=reading.first_token_margin,
        first_token_window=reading.first_token_window or None,
        thinking_spans=reading.thinking_spans,
        request_json=tuple(trace.requests),
        raw_response=tuple(trace.responses),
    )


def capture(
    evaluation: EvaluationSet, *, split: EvaluationSplit, settings: config.Settings,
    reader: ModelReader, host: HostFingerprintRow, git_sha: str, output_root: Path,
    now: Callable[[], str] = utc_now,
) -> tuple[EvaluationRun, Path]:
    """Atomically save after each reading; a raised transport failure remains incomplete."""
    run = start_run(
        evaluation, split=split, settings=settings, reader=reader,
        host=host, git_sha=git_sha, started_at=now(),
    )
    output = capture_path(run, output_root)
    if output.exists():
        raise ValueError("this capture identity already exists; no automatic retry or overwrite")
    write_atomic(output, run.to_json())
    event_lines.emit(EvaluationCaptureStarted(file=output.name), logger=LOG)
    run = EvaluationRun.model_validate(run.model_dump() | {"state": "incomplete"})
    write_atomic(output, run.to_json())
    cases = {case.case_id: case for case in evaluation.cases}
    for index, case_run in enumerate(run.cases):
        case = cases[case_run.case_id]
        for reverse in (False, True):
            if config_sha256(settings) != run.config_sha256:
                raise ValueError("judge configuration changed during capture")
            reading = capture_reading(case, reverse=reverse, reader=reader, settings=settings)
            changed = EvaluationCaseRun.model_validate(case_run.model_dump() | {
                "reverse" if reverse else "forward": reading,
            })
            rows = list(run.cases)
            rows[index] = changed
            run = EvaluationRun.model_validate(run.model_dump() | {"cases": tuple(rows)})
            write_atomic(output, run.to_json())
            case_run = changed
    run = EvaluationRun.model_validate(run.model_dump() | {
        "state": "captured", "finished_at": now(),
    })
    write_atomic(output, run.to_json())
    return run, output


def capture_path(run: EvaluationRun, output_root: Path) -> Path:
    """A stable address while cases arrive; the final document has its own complete hash."""
    identity = derive_text_digest(canonical_json(run.model_dump(
        mode="json", exclude={"state", "finished_at", "cases"},
    )))
    return private_output(output_root, f"run-{identity}.json")


def capture_file(
    *, set_path: Path, split: EvaluationSplit, config_dir: Path, host_path: Path,
    git_sha: str, output_root: Path,
) -> tuple[EvaluationRun, Path]:
    """Only this explicit operation creates the production model reader."""
    evaluation = EvaluationSet.read(set_path)
    settings = config.load(config_dir)
    validate_inputs(
        evaluation, max_cases=judge_settings.load_evaluation(config_dir).max_cases,
    )
    selected_cases(evaluation, split)
    private_output(output_root, f"run-{document_sha256(evaluation)}.json")
    host = HostFingerprintRow.read(host_path)
    reader = ModelReader.from_settings(settings)
    return capture(
        evaluation, split=split, settings=settings, reader=reader,
        host=host, git_sha=git_sha, output_root=output_root,
    )
