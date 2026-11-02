"""How is validated evidence rendered without either supplied text or raw child output?"""

import os
import platform
from pathlib import Path

from .collect_task_profile import TaskMeasurement
from .contracts.base import SCHEMA_VERSION
from .contracts.evaluation_result import EvaluationResult
from .contracts.worker_identity import WorkerIdentity
from .contracts.workflow_report import (
    ResourceEvidence,
    RunnerConditions,
    ServiceShutdown,
    WorkflowError,
    WorkflowReport,
)

# Linux proc kB uses 1024 bytes; this conversion changes display units only.
KIB_PER_MIB = 1024
# This output protocol matches the workflow's two-file artifact allowlist.
REPORT_DIRECTORY = "services/hhem-evaluator/var/workflow"


def runner_conditions() -> RunnerConditions:
    return RunnerConditions(
        system=platform.system(),
        release=platform.release(),
        architecture=platform.machine(),
        logical_cpu_count=os.cpu_count(),
    )


def build_resource_evidence(
    measurement: TaskMeasurement | None,
    final_worker: WorkerIdentity | None,
    shutdown: ServiceShutdown,
) -> ResourceEvidence:
    if measurement is None:
        return ResourceEvidence(
            status="unavailable",
            reason="measurement_unavailable",
            profile=None,
            initial_worker=None,
            final_worker=final_worker,
            runner=runner_conditions(),
            shutdown=shutdown,
        )
    status, reason = measurement.coverage(final_worker)
    return ResourceEvidence(
        status=status,
        reason=reason,
        profile=measurement.profile,
        initial_worker=measurement.initial_worker,
        final_worker=final_worker,
        runner=runner_conditions(),
        shutdown=shutdown,
    )


def build_report(
    evaluation: EvaluationResult | None,
    resources: ResourceEvidence,
    errors: list[WorkflowError],
) -> WorkflowReport:
    has_score = evaluation is not None and evaluation.hhem is not None
    complete = (
        evaluation is not None
        and evaluation.status == "complete"
        and resources.status == "complete"
        and not errors
    )
    return WorkflowReport(
        version=SCHEMA_VERSION,
        status="complete" if complete else "partial" if has_score else "failed",
        evaluation=evaluation,
        resources=resources,
        errors=tuple(errors),
    )


def render_report(report: WorkflowReport) -> str:
    evaluation, resources = report.evaluation, report.resources
    lines = ["# HHEM manual evaluation", "", f"Report: **{report.status}**.", ""]
    if evaluation is None:
        lines += ["No validated evaluation response was received.", ""]
    else:
        score = "unavailable" if evaluation.hhem is None else f"{evaluation.hhem:.6f}"
        lines += [
            f"Source-support score: **{score}** (zero to one).",
            "The caller enabled only its owned API invocation, without editing committed defaults.",
            "The optional second comparison was not requested.",
            f"Evaluation: `{evaluation.execution_id}`.",
            f"Terminal event: `{evaluation.terminal_event_id}`.",
            "",
        ]
        if evaluation.model is not None:
            model = evaluation.model
            lines += [
                f"Loaded model: `{model.reference}` at `{model.loaded_revision}`.",
                f"Loaded weights SHA-256: `{model.loaded_weights_sha256}`.",
                f"Loaded configuration SHA-256: `{model.loaded_config_sha256}`.",
                f"Effective service settings SHA-256: `{model.service_config_sha256}`.",
                "",
            ]
        times = evaluation.timings_ms
        lines += [
            f"Timings in milliseconds: queue {times.queue_wait}; "
            f"primary scoring {times.primary_scoring}; total {times.total}.",
            "",
        ]
    runner = resources.runner
    lines += [
        "## Worker resources",
        "",
        f"Coverage: **{resources.status}**"
        + ("." if resources.reason is None else f" (`{resources.reason}`)."),
        f"Host: {runner.system} {runner.release}, {runner.architecture}; "
        f"visible logical CPUs: {runner.logical_cpu_count}.",
        "No application CPU affinity, quota, memory cap or fixed compute thread count.",
        "The interval starts after model readiness; download and model loading are excluded.",
        "",
    ]
    for label, worker in (
        ("Initial", resources.initial_worker),
        ("Final", resources.final_worker),
    ):
        if worker is not None:
            lines.append(
                f"{label} worker: generation {worker.generation}, PID {worker.pid}, "
                f"start ticks `{worker.start_ticks}`"
                + (
                    "."
                    if worker.pin_unavailable_reason is None
                    else f"; pin unavailable: `{worker.pin_unavailable_reason}`."
                )
            )
    profile = resources.profile
    if profile is not None:
        worker_profile = profile.processes.worker
        cpu = worker_profile.cpu
        lines += [
            "",
            f"Observed interval: {profile.elapsed_ms:.3f} milliseconds; "
            f"{profile.started_at.isoformat()} to {profile.finished_at.isoformat()} UTC.",
            f"End reason: `{profile.end_reason}`; outcome: `{profile.outcome}`.",
        ]
        if cpu.value is None:
            lines.append(f"Worker CPU: unavailable (`{cpu.reason}`).")
        else:
            lines.append(
                f"Worker CPU: {cpu.value.percent_one_core:.3f} percent of one core "
                f"over {worker_profile.cpu_interval_ms:.3f} milliseconds; "
                f"CPU time {cpu.value.cpu_time_ms:.3f} milliseconds. "
                "One fully used core is 100 percent; multiple cores can exceed 100 percent."
            )
        rss = worker_profile.sampled_rss_max_kb
        lines.append(
            "Sampled worker RAM maximum: "
            + (
                f"{rss / KIB_PER_MIB:.3f} MiB ({rss} KiB)."
                if rss is not None
                else "unavailable (`" + worker_profile.unavailable["sampled_rss_max_kb"] + "`)."
            )
        )
    shutdown = resources.shutdown
    lines += [
        "",
        "## Owned shutdown",
        "",
        f"HTTP child stopped: {shutdown.hhem_stopped}; "
        f"host child stopped: {shutdown.host_stopped}; "
        f"model exit confirmed: {shutdown.worker_exit_confirmed}.",
    ]
    for phase, title in (("original", "Failures"), ("cleanup", "Cleanup failures")):
        failures = [
            error for error in report.errors if (error.phase == "cleanup") == (phase == "cleanup")
        ]
        if failures:
            lines += ["", f"## {title}", ""]
            lines += [
                f"- `{error.code}` ({error.service}, {error.phase}, "
                f"HTTP {error.http_status}): {error.message}"
                for error in failures
            ]
    return "\n".join(lines) + "\n"


def write_report(report: WorkflowReport, directory: Path) -> None:
    validated = WorkflowReport.model_validate_json(report.model_dump_json())
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in (
        ("report.json", validated.model_dump_json(indent=2) + "\n"),
        ("report.md", render_report(validated)),
    ):
        path = directory / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(body, encoding="utf-8", newline="\n")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
