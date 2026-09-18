"""How long may one sharded job take, read from the one file that says so?

A value Actions cannot read as a number leaves the job with no bound at all, so
it is held to a whole positive count here. Two callers ask: the work shard of a
digest run, and a judging leg. One reader and one refusal, because a second
utility would be a second answer to what a bound is.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

#: What a caller that names no key gets. `digest.yml` was the first caller and
#: still spells no key, so its step reads exactly as it always has.
KEY = "shard_timeout_minutes"


def minutes(config_root: Path, *, key: str = KEY) -> int:
    run = json.loads((config_root / "idhazh.json").read_text(encoding="utf-8"))["run"]
    value = run[key]
    if type(value) is not int or value < 1:
        raise SystemExit(f"run.{key} must be a whole number of minutes, 1 or more")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument(
        "--key",
        default=KEY,
        help=(
            "Which run knob to read. The printed name is the key, so the line lands in "
            "$GITHUB_OUTPUT under the name the workflow reads it back by."
        ),
    )
    args = parser.parse_args(argv)
    print(f"{args.key}={minutes(args.config_root, key=args.key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
