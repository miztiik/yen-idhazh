"""How is the one-process loopback HTTP service started from committed settings?"""

import argparse
import logging
import math
from pathlib import Path

import uvicorn

from .contracts.service_settings import ServiceSettings
from .load_settings import SettingsLoadError, load_settings
from .serve_api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--enable", action="store_true")
    args = parser.parse_args()
    try:
        settings = load_settings(args.settings)
    except SettingsLoadError:
        parser.exit(2, "The service settings could not be loaded.\n")
    if args.enable:
        settings = ServiceSettings.model_validate_json(
            settings.model_copy(update={"enabled": True}).model_dump_json()
        )
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).disabled = True
    app = create_app(settings, args.root.resolve())
    # One HTTP process is part of the service's execution protocol.
    uvicorn.run(
        app,
        host=settings.listener.host,
        port=settings.listener.port,
        workers=1,
        reload=False,
        access_log=False,
        log_config=None,
        proxy_headers=False,
        server_header=False,
        timeout_graceful_shutdown=math.ceil(settings.worker.shutdown_timeout_ms / 1000),
    )


if __name__ == "__main__":
    main()
