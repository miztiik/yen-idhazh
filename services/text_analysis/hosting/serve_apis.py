"""How do the independent text-analysis APIs start on their existing listener?"""

import argparse
import os
from pathlib import Path
from typing import TextIO

import uvicorn
from gliner_api.create_api_component import create_app as create_gliner_app
from gliner_api.load_settings import SettingsLoadError, load_settings
from local_api_host.compose_api import bind_application
from local_api_host.compose_applications import ComposedApplication, compose_applications
from local_api_host.configure_server import create_server_config
from local_api_host.run_server import run_server
from text_analysis.create_api_component import create_app as create_spacy_app
from text_analysis.load_service_settings import (
    ServiceSettingsLoadError,
    load_service_settings,
)


def create_app(root: Path, *, stream: TextIO | None = None) -> ComposedApplication:
    """Read the existing listener authority and retain both complete native APIs."""
    settings = load_service_settings(root)
    gliner_settings = load_settings(root)
    spacy = create_spacy_app(settings)
    gliner = create_gliner_app(
        gliner_settings,
        bind_application(spacy).host_settings,
        root=root,
        stream=stream,
    )
    return compose_applications((spacy, gliner))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    root = parser.parse_args().root.resolve()
    try:
        app = create_app(root)
    except (ServiceSettingsLoadError, SettingsLoadError):
        parser.exit(2, "Text-analysis API settings are invalid.\n")
    os.chdir(root)
    config = create_server_config(app, app.application_bindings[0].host_settings)
    try:
        listener = config.bind_socket()
    except (OSError, SystemExit):
        parser.exit(2, "Text-analysis API listener could not start.\n")
    server = uvicorn.Server(config)
    try:
        run_server(server, [listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
