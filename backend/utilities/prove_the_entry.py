"""Read the turn markers off the server the run is about to use, and check the decoder."""

from __future__ import annotations

import argparse
from pathlib import Path

from idhazh import config
from idhazh.classify.calls import summarize_and_plan_schema
from idhazh.llm.server import prove_the_entry, request_timeout_seconds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    args = parser.parse_args(argv)

    entry = config.load(args.config_root).models.summarize
    prove_the_entry(
        model=entry,
        output_schema=summarize_and_plan_schema(),
        timeout=request_timeout_seconds(entry.request),
    )
    print("the markers came off this server's own template and the decoder is still bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
