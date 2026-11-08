"""How is one text-analysis API bound from committed settings?"""

import argparse
import os
from pathlib import Path

import uvicorn
from local_api_host.configure_server import create_server_config
from local_api_host.run_server import run_server

from text_analysis.create_api_component import create_app
from text_analysis.load_service_settings import (
    ServiceSettingsLoadError,
    load_service_settings,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        settings = load_service_settings(root)
    except ServiceSettingsLoadError:
        parser.exit(2)
    os.chdir(root)
    app = create_app(settings)
    config = create_server_config(app, app.state.host_settings)
    try:
        listener = config.bind_socket()
    except (OSError, SystemExit):
        parser.exit(2)
    server = uvicorn.Server(config)
    try:
        run_server(server, [listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
