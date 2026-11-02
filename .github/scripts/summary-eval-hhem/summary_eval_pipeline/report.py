"""How is collected evidence shown in one Markdown summary and artifact?"""

import argparse
import html
import json
import os
from collections.abc import Sequence
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from hhem_evaluator.contracts.evaluate_request import EvaluateRequest
from hhem_evaluator.contracts.service_settings import ServiceSettings
from hhem_evaluator.load_settings import load_settings

from .contracts import PipelineEvidence
from .host_reader import measurement_complete
from .inputs import read_manual_inputs
from .settings import load_pipeline_settings

# GitHub rejects a step-summary upload above one MiB without failing the job.
MAX_STEP_SUMMARY_BYTES = 1 << 20


def format_seconds(milliseconds: float | None) -> str:
    if milliseconds is None:
        return "Not available"
    rounded = Decimal(str(milliseconds)).to_integral_value(rounding=ROUND_CEILING) / 1000
    return f"{rounded:.3f}"


def cell(value: object) -> str:
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", "<br>")


def table(letter: str, headings: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = [
        f"**Table {letter}**",
        "",
        "| ID | " + " | ".join(headings) + " |",
        "| --- | " + " | ".join("---" for _ in headings) + " |",
    ]
    lines.extend(
        f"| {letter}{index} | " + " | ".join(cell(value) for value in row) + " |"
        for index, row in enumerate(rows, 1)
    )
    return "\n".join(lines)


def render_report(
    evidence: PipelineEvidence,
    request: EvaluateRequest,
    settings: ServiceSettings,
    config_url: str,
) -> str:
    result = evidence.evaluation
    model = result.model if result is not None else None
    effective = result.effective_settings if result is not None else None
    hardware, machine = evidence.hardware, evidence.machine
    missing_host = next(
        (error.code for error in evidence.errors if error.service == "host"),
        "Not run",
    )
    worker = result.worker if result is not None else None
    score = str(result.hhem) if result is not None and result.hhem is not None else "Not available"
    elapsed = result.timings_ms.total if result is not None else None
    window = effective.chunk_words if effective else settings.scoring.chunk_words
    overlap = effective.chunk_overlap_words if effective else settings.scoring.chunk_overlap_words
    config_rows: list[tuple[object, object]] = [
        ("Model", model.reference if model is not None else "Not loaded"),
        ("Loaded revision", model.loaded_revision if model is not None else "Not loaded"),
        ("Foundation", model.foundation_reference if model is not None else "Not loaded"),
        ("Foundation revision", model.foundation_revision if model is not None else "Not loaded"),
        (
            "Runtime",
            (
                f"Python {model.runtime_versions.python}; "
                f"PyTorch {model.runtime_versions.pytorch}; "
                f"Transformers {model.runtime_versions.transformers}"
            )
            if model is not None
            else "Not loaded",
        ),
        (
            "Source window",
            f"{window} words",
        ),
        (
            "Overlap",
            f"{overlap} words",
        ),
        ("CPU threads", "Runtime managed; no workflow CPU, memory or thread caps"),
        ("Second HHEM comparison", "Off"),
    ]
    hardware_rows: list[tuple[object, object]] = []
    for label, name, suffix in (
        ("CPU model", "cpu_model", ""),
        ("Logical CPUs", "cpu_logical_processors", " logical CPUs"),
        ("Physical cores", "cpu_physical_cores", " cores"),
        ("Total machine RAM", "machine_memory_total_mib", " MiB"),
    ):
        value = getattr(hardware, name) if hardware is not None else None
        reason = (
            hardware.unavailable.get(name)
            or hardware.reason
            or "collector did not state a field reason"
            if hardware is not None
            else missing_host
        )
        hardware_rows.append(
            (label, str(value) + suffix if value is not None else f"Unavailable - {reason}")
        )
    cpu = machine.cpu.value if machine is not None else None
    cpu_reason = machine.cpu.root.reason if machine is not None else missing_host
    hardware_rows.append(
        (
            "Whole-machine CPU usage",
            f"{cpu.user + cpu.system:.3f}%" if cpu is not None else f"Unavailable - {cpu_reason}",
        )
    )
    memory_total = machine.samples[-1].memory_kb.total if machine is not None else None
    available = machine.samples[-1].memory_kb.available if machine is not None else None
    memory_reason = (
        missing_host
        if machine is None
        else (
            machine.samples[-1].unavailable.get("memory_kb.available")
            or machine.samples[-1].unavailable.get("memory_kb.total")
        )
    )
    hardware_rows.extend(
        [
            (
                "Machine RAM in use (closing)",
                f"{(memory_total - available) / 1024:.3f} MiB"
                if memory_total is not None and available is not None
                else f"Unavailable - {memory_reason or 'missing_field'}",
            ),
            (
                "Measurement interval (s)",
                format_seconds(machine.elapsed_ms) if machine is not None else "Not available",
            ),
            (
                "Measurement start (UTC)",
                machine.started_at.isoformat().replace("+00:00", "Z")
                if machine
                else "Not available",
            ),
            (
                "Measurement end (UTC)",
                machine.finished_at.isoformat().replace("+00:00", "Z")
                if machine
                else "Not available",
            ),
            (
                "Measurement coverage",
                "Complete"
                if measurement_complete(machine)
                else f"Incomplete - {machine.end_reason}"
                if machine is not None and machine.outcome == "cancelled"
                else "Incomplete - readings unavailable"
                if machine is not None
                else "Unavailable",
            ),
            (
                "HHEM worker",
                f"PID {worker.pid}; generation {worker.generation}; "
                f"start ticks {worker.start_ticks}"
                if worker
                else "Not available",
            ),
        ]
    )
    for label, observed in (
        ("Worker exit confirmed", evidence.shutdown.worker_exit_confirmed),
        ("HHEM API stopped cleanly", evidence.shutdown.hhem_stopped),
        ("Host helper stopped cleanly", evidence.shutdown.host_stopped),
    ):
        hardware_rows.append(
            (
                label,
                "Yes" if observed is True else "No" if observed is False else "Not observed",
            )
        )
    sections = [
        "# summary-eval-hhem",
        f"**Result:** {evidence.status}",
        "## Model configuration",
        table("A", ("Setting", "Value"), config_rows),
        f"[config/hhem-evaluator/settings.json]({config_url})",
        "## Actual work",
        table(
            "B",
            ("Evaluator", "Status", "Source support (0-1)", "Time (s)"),
            [
                (
                    "summary-eval-hhem",
                    result.status if result is not None else "Not completed",
                    score,
                    format_seconds(elapsed),
                ),
                ("summary-eval-unieval", "Not run - future task", "-", "-"),
            ],
        ),
        "## Hardware and worker",
        "CPU and RAM usage cover the whole machine, including background work.",
        table("C", ("Reading", "Value"), hardware_rows),
        "## Supplied texts",
        "<details>\n<summary>Source text</summary>\n\n<pre>"
        + html.escape(request.source_text)
        + "</pre>\n</details>",
        "<details>\n<summary>Summary text</summary>\n\n<pre>"
        + html.escape(request.summary_text)
        + "</pre>\n</details>",
    ]
    errors = [f"- {error.phase}: {error.code} - {error.message}" for error in evidence.errors]
    if result is not None:
        errors.extend(f"- HHEM: {error.code} - {error.message}" for error in result.errors)
    if errors:
        sections.extend(["## Errors", "\n".join(errors)])
    return "\n\n".join(sections) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    root = parser.parse_args().root.resolve()
    try:
        pipeline = load_pipeline_settings(root)
        settings = load_settings(root / "config" / "hhem-evaluator" / "settings.json")
        directory = root / pipeline.output_directory
        with (directory / "evaluation.json").open("rb") as stream:
            encoded = stream.read(pipeline.max_response_bytes + 1)
        if len(encoded) > pipeline.max_response_bytes:
            raise ValueError("Evidence exceeds its declared byte allowance")
        evidence = PipelineEvidence.model_validate_json(encoded)
        request = read_manual_inputs(settings, pipeline)
        config_url = (
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
            f"/blob/{os.environ['GITHUB_SHA']}/config/hhem-evaluator/settings.json"
        )
        markdown = render_report(evidence, request, settings, config_url)
        temporary = directory / "report.md.tmp"
        temporary.write_text(markdown, encoding="utf-8")
        temporary.replace(directory / "report.md")
        report_bytes = (directory / "report.md").read_bytes()
        summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"])
        existing_size = summary_path.stat().st_size if summary_path.exists() else 0
        if existing_size + len(report_bytes) > MAX_STEP_SUMMARY_BYTES:
            print(
                json.dumps(
                    {
                        "event": "summary_report_failed",
                        "reason": "summary_size_exceeded",
                    }
                )
            )
            raise SystemExit(1)
        with summary_path.open("ab") as summary:
            summary.write(report_bytes)
    except (OSError, ValueError, KeyError):
        print(json.dumps({"event": "summary_report_failed", "reason": "invalid_report_input"}))
        raise SystemExit(1) from None
    print(json.dumps({"event": "summary_report_created", "status": evidence.status}))
