"""How are the saved answer and real phase outcomes shown without rerunning work?"""

import html
from collections.abc import Sequence
from decimal import ROUND_CEILING, Decimal

from hhem_evaluator.contracts.service_settings import ServiceSettings

from .contracts import PipelineEvidence
from .host_reader import measurement_complete
from .inputs import ManualInputs


def format_seconds(milliseconds: float | None) -> str:
    if milliseconds is None:
        return "Not available"
    rounded = Decimal(str(milliseconds)).to_integral_value(rounding=ROUND_CEILING) / 1000
    return f"{rounded:.3f}"


def cell(value: object) -> str:
    if value is None:
        return "Not available"
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
    inputs: ManualInputs,
    settings: ServiceSettings,
    config_url: str,
) -> str:
    generation, evaluation = evidence.generation, evidence.evaluation_phase
    result = evaluation.evaluation if evaluation is not None else None
    selected = generation.selected if generation is not None else None
    loaded = generation.loaded if generation is not None else None
    evaluator = result.model if result is not None else None
    model_rows = [
        (
            "Summarizer declaration (relative to config/)",
            selected.models_file if selected else "Not selected",
        ),
        ("Declared summarizer", selected.model_id if selected else "Not selected"),
        ("Loaded summarizer", loaded.model_id if loaded else "Not loaded"),
        ("Native process PID", loaded.pid if loaded else "Not available"),
        ("Weight repository", selected.repo if selected else "Not available"),
        ("Weight revision", selected.revision if selected else "Not available"),
        ("Weight file", selected.filename if selected else "Not available"),
        ("Weight SHA-256 (content identity)", loaded.sha256 if loaded else "Not available"),
        (
            "Declaration SHA-256 (settings identity)",
            selected.declaration_sha256 if selected else "Not available",
        ),
        ("HHEM model", evaluator.reference if evaluator else "Not loaded"),
        ("HHEM loaded revision", evaluator.loaded_revision if evaluator else "Not loaded"),
        ("HHEM foundation", evaluator.foundation_reference if evaluator else "Not loaded"),
        ("HHEM foundation revision", evaluator.foundation_revision if evaluator else "Not loaded"),
        (
            "HHEM runtime",
            (
                f"Python {evaluator.runtime_versions.python}; "
                f"PyTorch {evaluator.runtime_versions.pytorch}; "
                f"Transformers {evaluator.runtime_versions.transformers}"
            )
            if evaluator
            else "Not loaded",
        ),
        ("HHEM source window", f"{settings.scoring.chunk_words} words"),
        ("HHEM overlap", f"{settings.scoring.chunk_overlap_words} words"),
    ]
    work_rows = [
        (
            "Generation",
            generation.status if generation else "Not run",
            "Saved final answer" if generation and generation.status == "complete" else "-",
            format_seconds(None),
        ),
        (
            "HHEM",
            result.status if result else "Not run",
            str(result.hhem) if result and result.hhem is not None else "-",
            format_seconds(result.timings_ms.total if result else None),
        ),
        ("UniEval", "Not run - separate workflow integration", "-", "-"),
    ]
    readings: list[tuple[object, ...]] = []
    servers: list[tuple[object, ...]] = []
    errors = list(evidence.errors)
    server_errors: list[str] = []
    if generation is not None:
        errors.extend(generation.errors)
    for phase in (evidence.generation_phase, evaluation):
        if phase is None:
            continue
        errors.extend(phase.errors)
        hardware, machine = phase.hardware, phase.machine
        readings.extend(
            [
                (phase.phase, "CPU model", hardware.cpu_model if hardware else "Not available"),
                (
                    phase.phase,
                    "Logical CPUs",
                    hardware.cpu_logical_processors if hardware else "Not available",
                ),
                (
                    phase.phase,
                    "Physical cores",
                    hardware.cpu_physical_cores if hardware else "Not available",
                ),
                (
                    phase.phase,
                    "Total RAM (MiB)",
                    hardware.machine_memory_total_mib if hardware else "Not available",
                ),
            ]
        )
        if phase.evaluation is not None and phase.evaluation.worker is not None:
            worker = phase.evaluation.worker
            readings.append(
                (
                    phase.phase,
                    "HHEM worker",
                    f"PID {worker.pid}; generation {worker.generation}; "
                    f"start ticks {worker.start_ticks}",
                )
            )
        cpu = machine.cpu.value if machine else None
        total = machine.samples[-1].memory_kb.total if machine else None
        available = machine.samples[-1].memory_kb.available if machine else None
        readings.extend(
            [
                (
                    phase.phase,
                    "Whole-machine CPU",
                    f"{cpu.user + cpu.system:.3f} percent"
                    if cpu
                    else (
                        f"Unavailable - {machine.cpu.root.reason}" if machine else "Not available"
                    ),
                ),
                (
                    phase.phase,
                    "Closing RAM in use",
                    f"{(total - available) / 1024:.3f} MiB"
                    if total is not None and available is not None
                    else "Not available",
                ),
                (
                    phase.phase,
                    "Measurement time (seconds)",
                    format_seconds(machine.elapsed_ms if machine else None),
                ),
                (
                    phase.phase,
                    "Measurement start (UTC)",
                    machine.started_at.isoformat().replace("+00:00", "Z")
                    if machine
                    else "Not available",
                ),
                (
                    phase.phase,
                    "Measurement end (UTC)",
                    machine.finished_at.isoformat().replace("+00:00", "Z")
                    if machine
                    else "Not available",
                ),
                (
                    phase.phase,
                    "Measurement coverage",
                    "Complete"
                    if measurement_complete(machine)
                    else f"Incomplete - {machine.end_reason}"
                    if machine
                    else "Not available",
                ),
                (phase.phase, "Model-worker exit confirmed", phase.shutdown.worker_exit_confirmed),
            ]
        )
        for server in phase.servers:
            if server.error_code is not None:
                server_errors.append(
                    f"- {phase.phase}: {server.server_name} - {cell(server.error_code)}"
                )
            if server.cleanup_error_code is not None:
                server_errors.append(
                    f"- cleanup: {server.server_name} - {cell(server.cleanup_error_code)}"
                )
            servers.append(
                (
                    phase.phase,
                    server.server_name,
                    server.startup,
                    format_seconds(server.startup_ms),
                    server.shutdown,
                    server.exit_code,
                    server.log_filename or "Not available",
                    "Available" if server.log_available else "Unavailable",
                )
            )
    sections = [
        "# summary-eval-tests",
        f"**Result:** {evidence.status}",
        "## Model configuration",
        table("A", ("Setting", "Value"), model_rows),
        f"[Committed evaluator settings]({config_url})",
        "## Actual work",
        table("B", ("Task", "Status", "Source support (0-1)", "Time (seconds)"), work_rows),
        "## Hardware",
        "CPU and RAM readings cover the whole machine, including background work.",
        table("C", ("Phase", "Reading", "Value"), readings),
        "## Owned servers",
        table(
            "D",
            (
                "Phase",
                "Server",
                "Startup",
                "Startup (seconds)",
                "Shutdown",
                "Exit status",
                "Log file",
                "Log mirror",
            ),
            servers,
        ),
        "## Texts",
        "<details>\n<summary>Source text</summary>\n\n<pre>"
        + html.escape(inputs.source_text)
        + "</pre>\n</details>",
        "<details>\n<summary>Generated summary</summary>\n\n<pre>"
        + (
            html.escape(generation.summary_text)
            if generation and generation.summary_text
            else "Not generated"
        )
        + "</pre>\n</details>",
    ]
    if errors or server_errors or (result is not None and result.errors):
        messages = [f"- {error.phase}: {error.code} - {error.message}" for error in errors]
        messages.extend(server_errors)
        if result is not None:
            messages.extend(f"- HHEM: {error.code} - {error.message}" for error in result.errors)
        sections.extend(["## Errors", "\n".join(dict.fromkeys(messages))])
    return "\n\n".join(sections) + "\n"
