"""How is the shared Python API bound before any enabled model starts?"""

import argparse
from pathlib import Path

import uvicorn

from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.serve_http.configure_server import (
    create_server_config,
    report_startup_failure,
)
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.serve_http.run_server import run_server
from summary_evaluator.serve_http.serve_api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--api-settings", type=Path)
    parser.add_argument("--routes", nargs="*", choices=("hhem", "unieval", "coverage"))
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        api = load_api_settings(args.api_settings or root / "config" / "summary-evals" / "api.json")
        if args.routes is not None:
            api = ApiSettings.model_validate_json(
                api.model_copy(update={"enabled_routes": tuple(args.routes)}).model_dump_json()
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
