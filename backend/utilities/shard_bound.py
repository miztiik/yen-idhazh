"""How long may one work shard take, read from the one file that says so?

It travels as a job output because `timeout-minutes` resolves from `needs`
before a job's first step, where `steps` is not readable.

Asserted to be a bare positive whole number here, at the one point that writes
it: `timeout-minutes` takes whatever it is handed, so a value Actions cannot
read as a number leaves the worker with no bound at all and the run finds out
six hours later.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

KEY = "shard_timeout_minutes"


def minutes(config_root: Path) -> int:
    run = json.loads((config_root / "idhazh.json").read_text(encoding="utf-8"))["run"]
    value = run[KEY]
    if type(value) is not int or value < 1:
        raise SystemExit(f"run.{KEY} must be a whole number of minutes, 1 or more")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    args = parser.parse_args(argv)
    print(f"{KEY}={minutes(args.config_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
