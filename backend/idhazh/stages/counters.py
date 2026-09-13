"""Commit what this shard's model server counted, so the ledger can be checked.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is not a worker").
"""

from __future__ import annotations

from pathlib import Path

from idhazh import (
    assemble,
    ledger,
)
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.runtime_counters import WORK_JOB, RuntimeCountersRow
from idhazh.stages import common
from idhazh.stages.common import LOG


def stage_counters(
    plan: RunPlan,
    *,
    metrics_path: Path,
    shard: int = 0,
    shards: int = 1,
    job: str = WORK_JOB,
    job_started_at: int | None = None,
    cpu_model: str | None = None,
    cpu_stat_at_start: str | None = None,
    cpu_stat_at_end: str | None = None,
    rss_samples_path: Path | None = None,
    server_log_path: Path | None = None,
    memory_peak_path: Path | None = None,
) -> RuntimeCountersRow:
    """Commit what this shard's model server counted, so the ledger can be checked.

    Every timing on the item-health ledger is a field the summarize stage copied
    out of one model reply. The server's own counters are the second instrument,
    and until now they reached only a job log that keeps them for two days - so
    the rates two published surfaces quote could not be reconciled with anything
    (Guardrail #10).

    Both counters are cumulative for the server process and a shard runs one
    server for its whole job, so this one read covers the shard entirely.

    The same row carries the job's own facts as well as the server's: the clock,
    the host, how busy that host was, the window one sequence got, three memory
    high points and what the weights cost to open. None of them is the server's
    to report, so each arrives as an argument. A stage reads a file and writes a
    file, so it does not go looking for `/proc` or `/sys` itself - those trees
    exist on the runner and on no developer machine this project is written on.
    What it does do is the arithmetic, so the derivation behind a cell is in the
    contract rather than in a shell.

    A missing or empty body still writes a row, with every counter null. A shard
    whose server was already gone and a shard that never ran are different facts,
    and pooling a run needs to see the shard that contributed nothing.

    `job` is which of the two model-server jobs this is. It is on the row because
    the two serve different weights, so nothing downstream can pool them and
    nothing can tell them apart without it.
    """
    row = RuntimeCountersRow.from_metrics_text(
        _text_if_readable(metrics_path),
        date=plan.date,
        run_id=plan.run_id,
        shard=shard,
        shards=shards,
        scraped_at=assemble.utc_now(),
        job=job,
        job_started_at=job_started_at,
        cpu_model=cpu_model,
        cpu_stat_at_start=cpu_stat_at_start,
        cpu_stat_at_end=cpu_stat_at_end,
        rss_samples=_text_if_readable(rss_samples_path),
        server_log=_text_if_readable(server_log_path),
        memory_peak=_text_if_readable(memory_peak_path),
    )
    landed = ledger.append_runtime_counters(common.STATE_ROOT, [row])
    LOG.info(
        "counted job=%s shard=%s/%s run=%s read_tokens=%s read_seconds=%s job_seconds=%s "
        "cpu=%s cpu_busy_pct=%s peak_rss_bytes=%s model_load_ms=%s n_ctx_configured=%s "
        "python_peak_rss_bytes=%s cgroup_peak_bytes=%s rows=%s",
        row.job,
        shard,
        shards,
        plan.run_id,
        row.prompt_tokens_total,
        row.prompt_seconds_total,
        row.job_seconds,
        row.cpu_model,
        row.cpu_busy_pct,
        row.peak_rss_bytes,
        row.model_load_ms,
        row.n_ctx_configured,
        row.python_peak_rss_bytes,
        row.cgroup_peak_bytes,
        landed,
    )
    return row


def _text_if_readable(path: Path | None) -> str:
    """A file the job may not have written is absent text, never a failed stage."""
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
