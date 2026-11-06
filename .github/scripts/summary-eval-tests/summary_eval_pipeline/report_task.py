"""How are the current saved results validated and published without repeating model work?"""

import argparse
import json
import os
from pathlib import Path

from hhem_evaluator.load_settings import load_settings

from .contracts import (
    WORKFLOW_VERSION,
    GenerationReceipt,
    PhaseEvidence,
    PipelineError,
    PipelineEvidence,
    has_completed_score,
    text_sha256,
)
from .failures import WorkflowError
from .inputs import read_manual_inputs
from .preparation import read_prepared
from .report import render_report
from .settings import load_pipeline_settings
from .storage import read_result, write_result

# The platform refuses a step summary larger than one MiB.
MAX_STEP_SUMMARY_BYTES = 1 << 20


def collect_results(root: Path) -> PipelineEvidence:
    pipeline = load_pipeline_settings(root)
    directory = root / pipeline.output_directory
    prepared, _ = read_prepared(root)
    if prepared.status != "complete":
        return PipelineEvidence(
            version=WORKFLOW_VERSION,
            status="failed",
            prepared=prepared,
            generation=None,
            generation_phase=None,
            evaluation_phase=None,
            errors=(),
        )
    errors: list[PipelineError] = []
    generation = None
    generated_phase = None
    evaluation_phase = None
    try:
        generation = read_result(
            directory / "generation.json", GenerationReceipt, pipeline.max_response_bytes
        )
        if (
            generation.run != prepared.run
            or generation.selected != prepared.selected
            or generation.source_sha256 != prepared.source_sha256
            or generation.reference_summary_sha256 != prepared.reference_summary_sha256
        ):
            generation = None
            raise WorkflowError("RECEIPT_INVALID", "report")
    except WorkflowError as error:
        errors.append(error.error)
    for filename, phase in (
        ("generation-phase.json", "generation"),
        ("evaluation.json", "evaluation"),
    ):
        try:
            result = read_result(directory / filename, PhaseEvidence, pipeline.max_response_bytes)
            if (
                result.run != prepared.run
                or result.phase != phase
                or result.reference_summary_sha256 != prepared.reference_summary_sha256
                or (
                    generation is not None
                    and result.generation_sha256 != text_sha256(generation.model_dump_json())
                )
            ):
                raise WorkflowError("RECEIPT_INVALID", "report")
            if (
                phase == "evaluation"
                and (result.evaluation is not None or result.unieval is not None)
                and (
                    generation is None
                    or generation.status != "complete"
                    or generated_phase is None
                    or generated_phase.shutdown.llama_stopped is not True
                    or generated_phase.shutdown.api_stopped is not None
                )
            ):
                raise WorkflowError("RECEIPT_INVALID", "report")
            if phase == "generation":
                generated_phase = result
            else:
                evaluation_phase = result
        except WorkflowError as error:
            errors.append(error.error)
    complete = (
        generation is not None
        and generation.status == "complete"
        and generated_phase is not None
        and generated_phase.status == "complete"
        and evaluation_phase is not None
        and evaluation_phase.status == "complete"
        and not errors
    )
    score = evaluation_phase is not None and has_completed_score(
        evaluation_phase.evaluation, evaluation_phase.unieval
    )
    return PipelineEvidence(
        version=WORKFLOW_VERSION,
        status="complete" if complete else "partial" if score else "failed",
        prepared=prepared,
        generation=generation,
        generation_phase=generated_phase,
        evaluation_phase=evaluation_phase,
        errors=tuple(errors),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    root = parser.parse_args().root.resolve()
    try:
        pipeline = load_pipeline_settings(root)
        settings = load_settings(root / "config" / "hhem-evaluator" / "settings.json")
        directory = root / pipeline.output_directory
        evidence = collect_results(root)
        write_result(directory / "results.json", evidence)
        inputs = read_manual_inputs(pipeline)
        if evidence.prepared is not None and (
            text_sha256(inputs.source_text) != evidence.prepared.source_sha256
            or text_sha256(inputs.reference_summary_text)
            != evidence.prepared.reference_summary_sha256
        ):
            raise WorkflowError("RECEIPT_INVALID", "report")
        config_url = (
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
            f"/blob/{os.environ['GITHUB_SHA']}/config/hhem-evaluator/settings.json"
        )
        markdown = render_report(evidence, inputs, settings, config_url)
        temporary = directory / "report.md.tmp"
        temporary.write_text(markdown, encoding="utf-8", newline="\n")
        temporary.replace(directory / "report.md")
        report_bytes = markdown.encode("utf-8")
        summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"])
        existing_size = summary_path.stat().st_size if summary_path.exists() else 0
        if existing_size + len(report_bytes) > MAX_STEP_SUMMARY_BYTES:
            print(json.dumps({"event": "summary_report_failed", "reason": "summary_size_exceeded"}))
            raise SystemExit(1)
        with summary_path.open("ab") as summary:
            summary.write(report_bytes)
    except (OSError, ValueError, KeyError, WorkflowError):
        print(json.dumps({"event": "summary_report_failed", "reason": "invalid_report_input"}))
        raise SystemExit(1) from None
    print(json.dumps({"event": "summary_report_created", "status": evidence.status}))
    raise SystemExit(0 if evidence.status == "complete" else 1)
