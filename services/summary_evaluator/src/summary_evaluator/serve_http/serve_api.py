"""Which declared native components are registered with the shared FastAPI host?"""

from functools import partial
from pathlib import Path

from fastapi import FastAPI

from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.hhem.create_api_component import (
    create_api_component as create_hhem_component,
)
from summary_evaluator.hhem.maintain_worker import WorkerSupervisor
from summary_evaluator.serve_http.compose_api import ComponentRegistration, compose_app
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.contracts.error_detail import ApiErrorResult
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.refuse_request import refuse_request
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings
from summary_evaluator.source_coverage.create_api_component import (
    create_api_component as create_coverage_component,
)
from summary_evaluator.source_coverage.maintain_worker import CoverageSupervisor
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.create_api_component import (
    create_api_component as create_unieval_component,
)
from summary_evaluator.unieval.maintain_unieval_worker import UnievalSupervisor


def create_app(
    api: ApiSettings,
    settings: ServiceSettings | None,
    root: Path,
    context: StartupContext | None = None,
    *,
    supervisor: WorkerSupervisor | None = None,
    writer: EventWriter | None = None,
    unieval_settings: UnievalSettings | None = None,
    unieval_supervisor: UnievalSupervisor | None = None,
    coverage_settings: CoverageSettings | None = None,
    coverage_supervisor: CoverageSupervisor | None = None,
) -> FastAPI:
    return compose_app(
        api,
        root,
        context,
        writer=writer,
        registrations=(
            ComponentRegistration(
                name="hhem",
                state_attribute="controller",
                create=lambda host, events: create_hhem_component(
                    host, settings, supervisor=supervisor, writer=events.write
                ),
            ),
            ComponentRegistration(
                name="unieval",
                state_attribute="unieval",
                create=lambda host, events: create_unieval_component(
                    host,
                    settings=unieval_settings,
                    supervisor=unieval_supervisor,
                    writer=partial(events.component_diagnostic, "unieval"),
                ),
            ),
            ComponentRegistration(
                name="coverage",
                state_attribute="coverage",
                create=lambda host, events: create_coverage_component(
                    host,
                    settings=coverage_settings,
                    supervisor=coverage_supervisor,
                    writer=partial(events.component_diagnostic, "coverage"),
                    render_refusal=refuse_request,
                    refusal_schema=ApiErrorResult.model_json_schema(),
                ),
            ),
        ),
    )
