"""Which command line starts llama-server for one config root?

Names no flag itself: `idhazh.llm.server.server_argv` is the one place a
llama-server flag may be spelled (Guardrail #6).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from idhazh import config
from idhazh.llm.server import server_argv

#: The port every workflow that stands a server up declares once, at workflow
#: level. Read back rather than written, so a server on one port and a stage
#: posting to another cannot happen.
PORT_ENV = "LLAMA_PORT"

#: The weights file, already resolved by the step that fetched and checked it.
WEIGHTS_ENV = "LLAMA_WEIGHTS"


def argv_for(*, config_root: Path, weights: Path, role: str, port: int) -> list[str]:
    """The command line, built from the config root's own entry for that role."""
    settings = config.load(config_root)
    entry = getattr(settings.models, role)
    return server_argv(
        binary=Path("backend/bin/llama-server"),
        weights=weights,
        model=entry,
        server=entry.server,
        port=port,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--role", default="summarize")
    args = parser.parse_args(argv)

    # Both come from the environment rather than the command line. An argument
    # spelled `--port` would be a second spelling of a llama-server flag, which
    # is the one thing this file exists to prevent.
    built = argv_for(
        config_root=args.config_root,
        weights=Path(os.environ[WEIGHTS_ENV]),
        role=args.role,
        port=int(os.environ[PORT_ENV]),
    )
    sys.stdout.write("\0".join(built) + "\0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
