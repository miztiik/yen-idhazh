"""Resolve the workflow host-telemetry choice against its master switch."""

from __future__ import annotations

import argparse
from pathlib import Path

from idhazh.contracts.app_config import AppConfig
from idhazh.telemetry.host_control import HOST_TELEMETRY_MODES, MODE_ENV, mode


def resolve(request: str, config_root: Path) -> str:
    if request not in HOST_TELEMETRY_MODES:
        raise ValueError("host telemetry must be python, typescript or off")
    app = AppConfig.from_json((config_root / "idhazh.json").read_text(encoding="utf-8"))
    return mode(app.observability, {MODE_ENV: request})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", choices=HOST_TELEMETRY_MODES, nargs="?", default="python")
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    args = parser.parse_args()
    print(resolve(args.request, args.config_root))


if __name__ == "__main__":
    main()
