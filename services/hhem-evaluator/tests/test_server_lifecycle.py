"""Verify standalone exit truth through the real socket-free evaluator and Uvicorn lifespans."""

import io
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import uvicorn
from fastapi import FastAPI
from uvicorn.lifespan.on import LifespanOn

from hhem_evaluator.api_settings import load_api_settings
from hhem_evaluator.configure_server import create_server_config
from hhem_evaluator.run_server import has_clean_lifespan, run_server
from hhem_evaluator.serve_api import create_app
from hhem_evaluator.serve_http.emit_events import EventWriter

from .contract_examples import API_SETTINGS_FILE, REPOSITORY


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_standalone_exit_matches_the_actual_lifespan_without_opening_a_listener(
    cleanup_failure: bool,
) -> None:
    api = load_api_settings(API_SETTINGS_FILE).model_copy(update={"enabled_routes": ()})
    stream = io.StringIO()
    evaluator = create_app(
        api,
        None,
        REPOSITORY,
        writer=EventWriter(api.logging, stream),
    )
    server: uvicorn.Server

    @asynccontextmanager
    async def lifetime(app: FastAPI) -> AsyncIterator[None]:
        async with evaluator.router.lifespan_context(evaluator):
            server.should_exit = True
            if cleanup_failure:
                stream.close()
            yield

    application = FastAPI(lifespan=lifetime, docs_url=None, redoc_url=None, openapi_url=None)
    server = uvicorn.Server(create_server_config(application, api))
    if cleanup_failure:
        with pytest.raises(SystemExit) as observed:
            run_server(server, [])
        assert observed.value.code == 1
    else:
        run_server(server, [])
    assert server.started and server.servers == []
    assert isinstance(server.lifespan, LifespanOn)
    assert server.lifespan.shutdown_failed is cleanup_failure
    assert has_clean_lifespan(server) is not cleanup_failure
    assert evaluator.state.controller is None and evaluator.state.unieval is None
