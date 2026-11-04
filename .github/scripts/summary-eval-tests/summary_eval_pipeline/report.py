"""How are the saved answer and real phase outcomes shown without rerunning work?"""

import html
from collections.abc import Sequence
from decimal import ROUND_CEILING, Decimal

from hhem_evaluator.contracts.evaluation_result import EvaluationResult
from hhem_evaluator.contracts.service_settings import ServiceSettings

from .contracts import PhaseEvidence, PhaseName, PipelineError, PipelineEvidence
from .host_reader import measurement_complete
from .inputs import ManualInputs
from .report_models import model_rows


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


def describe_error(error: PipelineError, task: PhaseName | None = None) -> str:
    location: list[str] = [task] if task is not None else []
    if error.phase != task:
        location.append(error.phase)
    location.append(error.service)
    if error.http_status is not None:
        location.append(f"HTTP {error.http_status}")
    cause = f" (cause {error.source_code})" if error.source_code is not None else ""
    return f"- {' / '.join(location)}: {error.code}{cause} - {error.message}"


def describe_evaluator(status: str | None, phase: PhaseEvidence | None, service: str) -> str:
    if status is not None:
        return status
    failures = (
        [
            error
            for error in phase.errors
            if error.service == service and error.phase == "evaluation"
        ]
        if phase
        else []
    )
    if any(error.code == "TASK_CANCELLED" for error in failures):
        return "Cancelled - no result"
    return "Failed - no valid result" if failures else "Not run"


def describe_hhem(result: EvaluationResult | None) -> str:
    if result is None:
        return "-"
    score = (
        f"{result.hhem} source support (0-1)" if result.hhem is not None else "Score unavailable"
    )
    windows = result.windows.primary
    work = (
        f"{windows.scored} / {windows.planned} source windows complete"
        if windows is not None
        else "Source windows not planned"
    )
    return f"{score}; {work}"


def render_report(
    evidence: PipelineEvidence,
    inputs: ManualInputs,
    settings: ServiceSettings,
    config_url: str,
) -> str:
    generation, evaluation = evidence.generation, evidence.evaluation_phase
    result = evaluation.evaluation if evaluation is not None else None
    unieval = evaluation.unieval if evaluation is not None else None
    work_rows = [
        ("Preparation", evidence.prepared.status if evidence.prepared else "Not run", "-", "-"),
        (
            "Generation",
            generation.status if generation else "Not run",
            "Saved final answer" if generation and generation.status == "complete" else "-",
            format_seconds(None),
        ),
        (
            "HHEM",
            describe_evaluator(result.status if result else None, evaluation, "hhem"),
            describe_hhem(result),
            format_seconds(result.timings_ms.total if result else None),
        ),
        (
            "UniEval",
            describe_evaluator(unieval.status if unieval else None, evaluation, "unieval"),
            (
                f"{sum(value is not None for value in unieval.scores.model_dump().values())}"
                " of 4 dimensions complete"
            )
            if unieval
            else "-",
            format_seconds(unieval.timings_ms.total if unieval else None),
        ),
    ]
    score_rows = []
    for dimension, meaning in (
        ("fluency", "Natural wording; mean across summary sentences."),
        ("coherence", "Logical flow of the complete summary with the complete source."),
        ("consistency", "Support for summary claims under the recorded source mode."),
        ("relevance", "Agreement with the independent reference, not source coverage."),
    ):
        dimension_work = getattr(unieval.work, dimension) if unieval else None
        score_rows.append(
            (
                dimension,
                getattr(unieval.scores, dimension) if unieval else None,
                meaning,
                (
                    f"{dimension_work.completed} / {dimension_work.planned}"
                    if dimension_work and dimension_work.planned is not None
                    else "Not planned"
                ),
            )
        )
    readings: list[tuple[object, ...]] = []
    servers: list[tuple[object, ...]] = []
    errors = [describe_error(error) for error in evidence.errors]
    if evidence.prepared is not None:
        errors.extend(describe_error(error) for error in evidence.prepared.errors)
    if generation is not None:
        errors.extend(describe_error(error, "generation") for error in generation.errors)
    for phase in (evidence.generation_phase, evaluation):
        if phase is None:
            continue
        errors.extend(describe_error(error, phase.phase) for error in phase.errors)
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
                    f"process ID {worker.pid}; worker start number {worker.generation}; "
                    f"kernel start ticks {worker.start_ticks}",
                )
            )
        if phase.unieval is not None and phase.unieval.worker is not None:
            worker = phase.unieval.worker
            readings.append(
                (
                    phase.phase,
                    "UniEval worker",
                    f"process ID {worker.pid}; worker start number {worker.generation}; "
                    f"kernel start ticks {worker.start_ticks}",
                )
            )
        if phase.api_health is not None:
            readings.extend(
                (phase.phase, f"{name} startup state", getattr(phase.api_health, name).status)
                for name in ("hhem", "unieval")
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
                (phase.phase, "HHEM worker exit confirmed", phase.shutdown.worker_exit_confirmed),
                (
                    phase.phase,
                    "UniEval worker exit confirmed",
                    phase.shutdown.unieval_worker_exit_confirmed,
                ),
            ]
        )
        for server in phase.servers:
            if server.error_code is not None:
                errors.append(f"- {phase.phase} / {server.server_name}: {cell(server.error_code)}")
            if server.cleanup_error_code is not None:
                errors.append(
                    f"- {phase.phase} / cleanup / {server.server_name}: "
                    f"{cell(server.cleanup_error_code)}"
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
        "## Actual work",
        table("A", ("Task", "Status", "Result", "Time (seconds)"), work_rows),
        "HHEM reports source support from zero to one: the best completed source window, "
        "not proof that every claim is true.",
    ]
    if result is not None:
        errors.extend(
            f"- evaluation / hhem / {error.phase}: {error.code} - {error.message}"
            for error in result.errors
        )
    if unieval is not None:
        errors.extend(
            f"- evaluation / unieval / {error.dimension or 'request'}: "
            f"{error.code} - {error.message}"
            for error in unieval.errors
        )
    if errors:
        sections.extend(["## Errors", "\n".join(dict.fromkeys(errors))])
    sections.extend(
        [
            "## UniEval scores",
            table(
                "B",
                ("Dimension", "Score (0-1)", "Meaning", "Completed / planned comparisons"),
                score_rows,
            ),
            "All four scores are required. Missing work is not zero. Segmented consistency "
            "checks every source window for every summary sentence, then averages each "
            "sentence's best score. It cannot join evidence across windows and may miss "
            "contradictions outside the best match. Coherence and relevance each use one "
            "complete prompt, not window averages. Longer prompts do not establish "
            "judging accuracy.",
            "## Model configuration",
            table("C", ("Setting", "Value"), model_rows(evidence, settings)),
            f"[Committed evaluator settings]({config_url})",
            "## Hardware",
            "CPU and RAM readings cover the whole machine, including background work.",
            table("D", ("Phase", "Reading", "Value"), readings),
            "## Owned servers",
            (
                "For failed or cancelled runs, open this run's **Artifacts -> "
                "summary-eval-tests-server-logs** and choose the matching filename "
                "from **Log file** in Table E."
                if servers
                else "No server log files were recorded. The server-log artifact is absent "
                "when no server starts."
            ),
            table(
                "E",
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
            "<details>\n<summary>Independent reference summary</summary>\n\n"
            "Supplied before generation; sent only to UniEval.\n\n<pre>"
            + html.escape(inputs.reference_summary_text)
            + "</pre>\n</details>",
        ]
    )
    return "\n\n".join(sections) + "\n"
