"""How are the saved answer and real phase outcomes shown without rerunning work?"""

import html
from collections.abc import Sequence
from decimal import ROUND_CEILING, Decimal

from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.worker_exit import WorkerExit
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult

from .contracts import PhaseEvidence as LegacyPhaseEvidence
from .contracts import PhaseName, PipelineError
from .host_reader import HonoServerReader, measurement_complete
from .inputs import ManualInputs
from .phase_contracts import PhaseResult
from .report_contracts import PipelineResult
from .report_models import model_rows, scorer_health
from .run_contracts import PreparedRun


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


def describe_error(
    error: PipelineError, task: PhaseName | None = None, scorer: str | None = None
) -> str:
    location: list[str] = [task] if task is not None else []
    if scorer is not None:
        location.append(scorer)
    if error.phase != task:
        location.append(error.phase)
    if error.service != scorer:
        location.append(error.service)
    if error.http_status is not None:
        location.append(f"HTTP {error.http_status}")
    cause = f" (cause {error.source_code})" if error.source_code is not None else ""
    return f"- {' / '.join(location)}: {error.code}{cause} - {error.message}"


def describe_evaluator(status: str | None, phase: PhaseResult | None, service: str) -> str:
    if status is not None:
        return status
    failures = (
        [
            error
            for error in phase.errors
            if error.service == service
        ]
        if phase
        else []
    )
    if phase is not None and not isinstance(phase, LegacyPhaseEvidence):
        failures.extend(
            error for api in phase.scorer_apis if api.scorer == service for error in api.errors
        )
    if any(error.code == "TASK_CANCELLED" for error in failures):
        return "Cancelled - no result"
    return "Failed - no valid result" if failures else "Not run"


def describe_api_process(process: ProcessIdentity | None) -> str:
    if process is None:
        return "Not recorded"
    pin = (
        f"start ticks {process.start_ticks}" if process.start_ticks is not None
        else f"pin unavailable ({process.pin_unavailable_reason})"
    )
    return f"PID {process.pid}; {pin}"


def describe_worker_exit(exit_observed: WorkerExit) -> str:
    if exit_observed.confirmed is None:
        return "Not recorded"
    return (
        f"PID {exit_observed.pid}; exit status {exit_observed.exit_code}; "
        f"confirmed {exit_observed.confirmed}"
    )


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
    evidence: PipelineResult,
    inputs: ManualInputs,
    settings: ServiceSettings,
    config_url: str,
) -> str:
    generation, evaluation = evidence.generation, evidence.evaluation_phase
    result = evaluation.evaluation if evaluation is not None else None
    unieval = evaluation.unieval if evaluation is not None else None
    relevance_skip = (
        unieval.relevance_skip_reason if isinstance(unieval, UnievalResult) else None
    )
    applicable = 4 if relevance_skip is None else 3
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
                f" of {applicable} applicable dimensions complete"
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
        score = getattr(unieval.scores, dimension) if unieval else None
        failures = (
            [error.code for error in unieval.errors if error.dimension == dimension]
            if unieval else []
        )
        state = (
            "Skipped - disabled" if dimension == "relevance" and relevance_skip == "disabled"
            else "Skipped - reference not supplied"
            if dimension == "relevance" and relevance_skip == "reference_not_supplied"
            else "Complete" if score is not None
            else "Failed - " + ", ".join(failures) if failures
            else "Not run"
        )
        score_rows.append(
            (
                dimension,
                score,
                state,
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
        for name in ("hhem", "unieval"):
            health = scorer_health(phase, name)
            if health is not None:
                readings.append(
                    (phase.phase, f"{name} startup state", getattr(health, name).status)
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
            ]
        )
        legacy_shutdown = phase.shutdown if isinstance(phase, LegacyPhaseEvidence) else None
        if legacy_shutdown is not None and phase.phase == "evaluation":
            readings.extend(
                [
                    (
                        phase.phase,
                        "HHEM worker exit confirmed",
                        legacy_shutdown.worker_exit_confirmed,
                    ),
                    (
                        phase.phase,
                        "UniEval worker exit confirmed",
                        legacy_shutdown.unieval_worker_exit_confirmed,
                    ),
                ]
            )
        if not isinstance(phase, LegacyPhaseEvidence):
            for api in phase.scorer_apis:
                errors.extend(
                    describe_error(error, phase.phase, api.scorer) for error in api.errors
                )
                outcome = api.outcome
                for code, location in (
                    (outcome.error_code, "api"),
                    (outcome.cleanup_error_code, "cleanup"),
                ):
                    if code is not None:
                        errors.append(
                            f"- {phase.phase} / {api.scorer} / {location}: {cell(code)}"
                        )
                servers.append(
                    (
                        phase.phase,
                        f"{api.scorer} API",
                        describe_api_process(api.process),
                        api.service_instance_id or "Not recorded",
                        outcome.startup,
                        format_seconds(outcome.startup_ms),
                        outcome.shutdown,
                        outcome.exit_code,
                        describe_worker_exit(api.worker_exit),
                        outcome.log_filename or "Not recorded",
                        "Available" if outcome.log_available else "Unavailable",
                    )
                )
        shared_recorded = False
        for server in phase.servers:
            native = server if isinstance(server, HonoServerReader) else None
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
                    "Shared scorer API (legacy 2026-11-05)"
                    if server.server_name == "fastapi-server" else (
                        f"{native.group} API ({native.listener.hostname}:{native.listener.port})"
                        if native is not None else server.server_name
                    ),
                    (
                        f"PID {native.pid}" if native.pid is not None else "Not recorded"
                    ) if native is not None else (
                        "Not recorded"
                        if server.server_name in ("fastapi-server", "hono-server") else "-"
                    ),
                    (
                        phase.api_health.service_instance_id
                        if isinstance(phase, LegacyPhaseEvidence) and phase.api_health is not None
                        else "Not recorded"
                    ) if server.server_name == "fastapi-server" else (
                        str(native.identity.nonce)
                        if native is not None and native.identity is not None
                        else "Not recorded" if server.server_name == "hono-server" else "-"
                    ),
                    server.startup,
                    format_seconds(server.startup_ms),
                    server.shutdown,
                    server.exit_code,
                    (
                        f"HHEM confirmed {phase.shutdown.worker_exit_confirmed}; "
                        f"UniEval confirmed {phase.shutdown.unieval_worker_exit_confirmed}; "
                        "worker exit PIDs/statuses not recorded"
                    ) if isinstance(phase, LegacyPhaseEvidence)
                    and server.server_name == "fastapi-server" else "-",
                    server.log_filename or "Not available",
                    "Available" if server.log_available else "Unavailable",
                )
            )
            shared_recorded = shared_recorded or server.server_name == "fastapi-server"
        if (
            isinstance(phase, LegacyPhaseEvidence)
            and phase.phase == "evaluation"
            and not shared_recorded
        ):
            health = phase.api_health
            servers.append(
                (
                    phase.phase, "Shared scorer API (legacy 2026-11-05)", "Not recorded",
                    health.service_instance_id if health is not None else "Not recorded",
                    health.status if health is not None else "Not recorded",
                    "Not recorded", "Not recorded", "Not recorded",
                    f"HHEM confirmed {phase.shutdown.worker_exit_confirmed}; "
                    f"UniEval confirmed {phase.shutdown.unieval_worker_exit_confirmed}; "
                    "worker exit PIDs/statuses not recorded",
                    health.log_file if health is not None else "Not recorded",
                    "Available" if health is not None and health.log_available else "Unavailable",
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
                (
                    "Dimension", "Score (0-1)", "Status", "Meaning",
                    "Completed / planned comparisons",
                ),
                score_rows,
            ),
            "Every applicable score is required. Skipped relevance is not a failure or zero. "
            "Missing required work is not zero. Segmented consistency "
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
                    "API process / start pin",
                    "Application identity",
                    "Startup",
                    "Startup (seconds)",
                    "Shutdown",
                    "Exit status",
                    "Model worker exit",
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
            + (
                "Not supplied; relevance has no reference to evaluate."
                if inputs.reference_summary_text is None
                else "Supplied but unused; relevance is disabled."
                if isinstance(evidence.prepared, PreparedRun)
                and not evidence.prepared.evaluate_relevance
                else "Supplied before generation; available only to UniEval relevance."
            )
            + " Never sent to generation or HHEM.\n\n<pre>"
            + (
                html.escape(inputs.reference_summary_text)
                if inputs.reference_summary_text is not None else "Not supplied"
            )
            + "</pre>\n</details>",
        ]
    )
    return "\n\n".join(sections) + "\n"
