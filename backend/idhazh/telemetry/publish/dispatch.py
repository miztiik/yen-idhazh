"""In what order does one run publish the instrument, and what does each step take?

Routing only. Every projection's body is in the module beside this one that owns
it (CLAUDE.md section 1a), and this file does three things: it names the order,
it hands each unit the inputs that unit takes, and it reports the route it took.
Nothing here derives a path, encodes a row or decides what a payload says.

The order is the contract. `day-metrics` writes the record the public series and
the band then read, and the band is last because it reads the run-day shards the
step above it wrote - deriving either from the day payloads instead would be the
walk those shards exist to remove (Guardrail #12).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh.assemble import TaxonomyVectors
from idhazh.config import Settings
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.source_health_view import SourceHealthView
from idhazh.telemetry.publish import (
    console_band,
    day_metrics,
    feed_health,
    machine,
    public_telemetry,
    run_days,
    scores,
    series,
    source_health,
    span_rollup,
)


@dataclass(frozen=True)
class Projection:
    """One payload a run publishes, and the module that writes it."""

    name: str
    module: str


#: Every payload a publication step writes, in the order it writes them. This
#: tuple IS the route: `publish_all` walks it and dispatches by name, so a
#: projection listed here runs exactly once and one that is not listed never
#: runs. `day_metrics` appears twice because it writes two payloads - the day's
#: record under `state/`, and the month series the console fetches.
PROJECTIONS: Final[tuple[Projection, ...]] = (
    Projection("telemetry", "public_telemetry"),
    Projection("source-health", "source_health"),
    Projection("day-metrics", "day_metrics"),
    Projection("scores", "scores"),
    Projection("feed-health", "feed_health"),
    Projection("machine", "machine"),
    Projection("span-rollup", "span_rollup"),
    Projection("public-day-metrics", "day_metrics"),
    Projection("run-days", "run_days"),
    Projection("console-band", "console_band"),
)


@dataclass(frozen=True)
class Published:
    """What one publication step did: the route it took, and the view it folded."""

    dispatched: tuple[str, ...]
    sources: SourceHealthView


def publish_all(
    *,
    state_root: Path,
    digest_root: Path,
    date: str,
    month: str,
    today: date_type,
    run_id: str,
    generated_at: str,
    day: DigestDay,
    manifest: RunManifest,
    settings: Settings,
    taxonomy_vectors: TaxonomyVectors | None,
) -> Published:
    """Dispatch every projection `PROJECTIONS` names, once each, in that order.

    `month` is the one month this run appended to, so every month-series
    projection reads that month and rebuilds any other only when its published
    file is missing. `today` is the day being published rather than the wall
    clock: a run that crosses midnight UTC would otherwise prune against one
    month and write into another.

    No projection is passed a root it did not get from this call. The module
    defaults exist for an operator running one projection by hand, and a test
    driving the pipeline from a temporary tree must never reach them - that is
    how a run over fixtures once truncated the committed telemetry projection.
    """
    observability = settings.app.observability
    #: The one projection another projection reads. Keeping the view the
    #: source-health step folded means the band opens no file for it.
    folded: list[SourceHealthView] = []

    def _fold_source_health() -> None:
        folded.append(
            source_health.publish(
                sources=settings.sources,
                taxonomy=settings.taxonomy,
                collect=settings.app.collect,
                date=date,
                run_id=run_id,
                generated_at=generated_at,
                state_root=state_root,
                path=series.console_root(digest_root) / source_health.PUBLIC_FILENAME,
            )
        )

    writers: dict[str, Callable[[], object]] = {
        "telemetry": lambda: public_telemetry.publish(
            state_root=state_root,
            public_root=(
                series.console_root(digest_root) / public_telemetry.PUBLIC_TELEMETRY_DIRNAME
            ),
            months={month},
        ),
        "source-health": _fold_source_health,
        "day-metrics": lambda: day_metrics.publish(
            state_root=state_root,
            date=date,
            day=day,
            manifest=manifest,
            taxonomy_vectors=taxonomy_vectors,
        ),
        "scores": lambda: scores.publish(
            state_root=state_root,
            digest_root=digest_root,
            keep_months=observability.public_scores_keep_months,
            today=today,
            months={month},
            ensure_month=month,
        ),
        "feed-health": lambda: feed_health.publish(
            state_root=state_root,
            digest_root=digest_root,
            keep_months=observability.public_feed_health_keep_months,
            today=today,
            months={month},
            ensure_month=month,
        ),
        "machine": lambda: machine.publish(
            state_root=state_root,
            digest_root=digest_root,
            keep_months=observability.public_machine_keep_months,
            today=today,
            months={month},
            ensure_month=month,
        ),
        "span-rollup": lambda: span_rollup.publish(
            state_root=state_root,
            digest_root=digest_root,
            keep_months=observability.public_span_rollup_keep_months,
            today=today,
            months={month},
            ensure_month=month,
        ),
        "public-day-metrics": lambda: day_metrics.publish_public(
            state_root=state_root,
            digest_root=digest_root,
            keep_months=observability.public_day_metrics_keep_months,
            today=today,
            months={month},
            ensure_month=month,
        ),
        "run-days": lambda: run_days.publish(
            digest_root=digest_root,
            keep_months=observability.public_run_days_keep_months,
            today=today,
            months={month},
            ensure_month=month,
        ),
        "console-band": lambda: console_band.publish(
            state_root=state_root,
            digest_root=digest_root,
            generated_at=generated_at,
            today=today,
            console=settings.appearance.console,
            run=settings.app.run,
            collect=settings.app.collect,
            sources=folded[0].sources,
        ),
    }

    dispatched: list[str] = []
    for projection in PROJECTIONS:
        writers[projection.name]()
        dispatched.append(projection.name)
    return Published(dispatched=tuple(dispatched), sources=folded[0])
