"""Resolve the YAML memory choice against one validated application config."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from idhazh.contracts.app_config import AppConfig


def resolve(request: str, config_root: Path) -> bool:
    if request == "on":
        return True
    if request == "off":
        return False
    if request != "inherit":
        raise ValueError("memory profiling must be inherit, on or off")
    app = AppConfig.from_json((config_root / "idhazh.json").read_text(encoding="utf-8"))
    return app.observability.memory_profiling_enabled


def write_override(request: str, config_root: Path) -> bool:
    resolved = resolve(request, config_root)
    if request == "inherit":
        return resolved
    path = config_root / "idhazh.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["observability"]["memory_profiling_enabled"] = resolved
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    AppConfig.from_json(text)
    path.write_text(text, encoding="utf-8", newline="\n")
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", choices=("inherit", "on", "off"))
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    resolved = (
        write_override(args.request, args.config_root)
        if args.write
        else resolve(args.request, args.config_root)
    )
    print("on" if resolved else "off")


if __name__ == "__main__":
    main()
