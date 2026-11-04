"""How is the shared Python API bound before any enabled model starts?"""

import argparse
from pathlib import Path

import uvicorn

from .api_settings import load_api_settings
from .configure_server import create_server_config, report_startup_failure
from .contracts.api_settings import ApiSettings
from .contracts.server_event import ApiDiagnosticData
from .load_llama_settings import load_llama_settings
from .load_settings import load_settings
from .run_server import run_server
from .serve_api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--api-settings", type=Path)
    parser.add_argument("--model-config", type=Path)
    parser.add_argument("--routes", nargs="*", choices=("hhem", "llama", "unieval"))
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        api = load_api_settings(args.api_settings or root / "config" / "fastapi-server.json")
        if args.routes is not None:
            api = ApiSettings.model_validate_json(
                api.model_copy(update={"enabled_routes": tuple(args.routes)}).model_dump_json()
            )
        selected = (
            load_llama_settings(args.model_config or root / "config" / "idhazh.json")
            if "llama" in api.enabled_routes
            else None
        )
        app = create_app(
            api,
            load_settings(args.settings, api) if "hhem" in api.enabled_routes else None,
            root,
            llama_settings=selected,
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
