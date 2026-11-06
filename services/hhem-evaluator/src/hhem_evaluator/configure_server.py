"""Which Uvicorn settings keep one loopback server and its diagnostics private?"""

import logging
import math
import sys
from typing import TextIO

import uvicorn
from fastapi import FastAPI

from .contracts.api_settings import ApiSettings
from .contracts.server_event import ApiDiagnosticData, ServerEvent
from .emit_events import JsonEventFormatter
from .write_event_records import StrictEventHandler


def create_server_config(app: FastAPI, settings: ApiSettings) -> uvicorn.Config:
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).disabled = True
    return uvicorn.Config(
        app,
        host=settings.listener.host,
        port=settings.listener.port,
        workers=1,
        reload=False,
        access_log=False,
        log_config=None,
        proxy_headers=False,
        server_header=False,
        lifespan="on",
        timeout_graceful_shutdown=math.ceil(settings.shutdown_timeout_ms / 1000),
    )


def report_startup_failure(code: str, stream: TextIO | None = None) -> None:
    """Keep failures before valid configuration safe and machine-readable too."""
    logger = logging.Logger("hhem_evaluator.startup")
    handler = StrictEventHandler(sys.stderr if stream is None else stream)
    handler.setFormatter(JsonEventFormatter())
    logger.addHandler(handler)
    logger.error(
        ServerEvent.diagnostic(
            ApiDiagnosticData(component="api", action="failed", level="ERROR", code=code)
        )
    )
