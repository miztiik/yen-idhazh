"""Which Uvicorn settings keep one loopback server and its diagnostics private?"""

import logging
import sys
from typing import TextIO

import uvicorn
from fastapi import FastAPI
from local_api_host.configure_server import create_server_config as create_host_server_config

from summary_evaluator.serve_http.compose_api import create_host_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData, ServerEvent
from summary_evaluator.serve_http.emit_events import JsonEventFormatter
from summary_evaluator.shared.write_event_records import StrictEventHandler


def create_server_config(app: FastAPI, settings: ApiSettings) -> uvicorn.Config:
    return create_host_server_config(app, create_host_settings(settings))


def report_startup_failure(code: str, stream: TextIO | None = None) -> None:
    """Keep failures before valid configuration safe and machine-readable too."""
    logger = logging.Logger("summary_evaluator.startup")
    handler = StrictEventHandler(sys.stderr if stream is None else stream)
    handler.setFormatter(JsonEventFormatter())
    logger.addHandler(handler)
    logger.error(
        ServerEvent.diagnostic(
            ApiDiagnosticData(component="api", action="failed", level="ERROR", code=code)
        )
    )
