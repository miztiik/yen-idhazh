"""How long may one sharded job take, read from the one file that says so?

A value Actions cannot read as a number leaves the job with no bound at all, so
it is held to a whole positive count here. Two callers ask: the work shard of a
digest run, and a judging shard of a council night. One reader and one refusal,
because a second utility would be a second answer to what a bound is.

The key is a dotted path, because the two bounds sit in different blocks - the
work shard's in `run`, the judging shard's in `council`. What is printed is the
path's last segment: an Actions output name cannot carry a dot, and the leaf is
the name the workflow reads it back by.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

#: What a caller that names no key gets. `digest.yml` was the first caller and
#: still spells no key, so its step reads exactly as it always has.
KEY = "run.shard_timeout_minutes"


def minutes(config_root: Path, *, key: str = KEY) -> int:
    found: Any = json.loads((config_root / "idhazh.json").read_text(encoding="utf-8"))
    for step in key.split("."):
        if not isinstance(found, dict) or step not in found:
            raise SystemExit(f"{key} is not in the config file, so the job would have no bound")
        found = found[step]
    if type(found) is not int or found < 1:
        raise SystemExit(f"{key} must be a whole number of minutes, 1 or more")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument(
        "--key",
        default=KEY,
        help=(
            "Which knob to read, as a dotted path into config/idhazh.json. The printed "
            "name is the path's last segment, so the line lands in $GITHUB_OUTPUT under "
            "the name the workflow reads it back by."
        ),
    )
    args = parser.parse_args(argv)
    leaf = str(args.key).rsplit(".", 1)[-1]
    print(f"{leaf}={minutes(args.config_root, key=args.key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
