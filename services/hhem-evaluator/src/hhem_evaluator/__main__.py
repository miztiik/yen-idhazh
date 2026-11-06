"""How is the shared Python API bound before any enabled model starts?"""

import argparse
from pathlib import Path

import uvicorn

from hhem_evaluator.api_settings import load_api_settings
from hhem_evaluator.configure_server import create_server_config, report_startup_failure
from hhem_evaluator.contracts.api_settings import ApiSettings
from hhem_evaluator.contracts.server_event import ApiDiagnosticData
from hhem_evaluator.load_settings import load_settings
from hhem_evaluator.run_server import run_server
from hhem_evaluator.serve_api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--api-settings", type=Path)
    parser.add_argument("--routes", nargs="*", choices=("hhem", "unieval"))
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        api = load_api_settings(args.api_settings or root / "config" / "fastapi-server.json")
        if args.routes is not None:
            api = ApiSettings.model_validate_json(
                api.model_copy(update={"enabled_routes": tuple(args.routes)}).model_dump_json()
            )
        app = create_app(
            api,
            load_settings(args.settings, api) if "hhem" in api.enabled_routes else None,
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
