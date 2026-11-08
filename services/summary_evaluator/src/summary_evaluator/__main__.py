"""How is exactly one scorer API bound before its model starts?"""

import argparse
from pathlib import Path
from typing import get_args

import uvicorn

from summary_evaluator.serve_http.api_settings import load_selected_api_settings
from summary_evaluator.serve_http.configure_server import (
    create_server_config,
    report_startup_failure,
)
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.serve_http.run_server import run_server
from summary_evaluator.serve_http.serve_api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--api-settings", type=Path)
    parser.add_argument("--routes", nargs="*", choices=get_args(ApiComponent))
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        api = load_selected_api_settings(
            args.api_settings or root / "config" / "summary-evals" / "api.json",
            tuple(args.routes) if args.routes is not None else None,
        )
        app = create_app(
            api,
            load_settings(
                args.settings
                or root / "config" / "summary-evals" / "hhem-evaluator" / "settings.json",
                api,
            )
            if "hhem" in api.enabled_routes
            else None,
            root,
            writer=EventWriter(
                api.logging,
                directory=root / api.log_directory,
                scorer=api.enabled_routes[0],
                propagate_trace_context=api.propagate_trace_context,
            ),
        )
    except ValueError:
        report_startup_failure("INVALID_SERVER_SETTINGS")
        parser.exit(2)
    config = create_server_config(app, api)
    try:
        listener = config.bind_socket()
    except (OSError, SystemExit):
        app.state.events.diagnostic(
            ApiDiagnosticData(
                component="api", action="failed", level="ERROR", code="LISTENER_BIND_FAILED"
            )
        )
        app.state.events.close()
        parser.exit(2)
    server = uvicorn.Server(config)
    try:
        run_server(server, [listener])
    finally:
        listener.close()
        app.state.events.close()


if __name__ == "__main__":
    main()
