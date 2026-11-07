"""Which Uvicorn settings keep one loopback server and its diagnostics private?"""

import logging
import math

import uvicorn
from fastapi import FastAPI

from local_api_host.contracts import HostSettings


def create_server_config(app: FastAPI, settings: HostSettings) -> uvicorn.Config:
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
