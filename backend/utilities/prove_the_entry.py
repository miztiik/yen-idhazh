"""Does the server the run is about to use agree with the entry describing it?"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from idhazh import config
from idhazh.classify.calls import summarize_and_plan_schema
from idhazh.llm.server import prove_the_entry

WEIGHTS_ENV = "LLAMA_WEIGHTS"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    args = parser.parse_args(argv)

    entry = config.load(args.config_root).models.summarize
    prove_the_entry(
        model=entry,
        weights=Path(os.environ[WEIGHTS_ENV]),
        output_schema=summarize_and_plan_schema(),
        timeout=entry.inference.request_timeout_minutes * 60,
    )
    print("the entry and the server agree on all five")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
