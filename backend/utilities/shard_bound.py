"""How long may one job take, read from the one file that says so?

A value Actions cannot read as a number leaves the job with no bound at all, so
it is held to a whole positive count here. Callers ask for digest work shards,
council judging shards, and council planning and collection jobs. One reader and one refusal,
because a second utility would be a second answer to what a bound is.

The key is a dotted path within the named file. The work shard's bound sits in
`run` in `idhazh.json`; council shard and job deadlines sit in `llm_council.json`
and `llm_council_job_timeouts.json`, respectively. What is printed is the
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


def minutes(config_root: Path, *, key: str = KEY, config_file: str = "idhazh.json") -> int:
    found: Any = json.loads((config_root / config_file).read_text(encoding="utf-8"))
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
        "--config-file", default="idhazh.json", help="The named file under config/."
    )
    parser.add_argument(
        "--key",
        default=KEY,
        help=(
            "Which knob to read, as a dotted path into the named config file. The printed "
            "name is the path's last segment, so the line lands in $GITHUB_OUTPUT under "
            "the name the workflow reads it back by."
        ),
    )
    args = parser.parse_args(argv)
    leaf = str(args.key).rsplit(".", 1)[-1]
    print(f"{leaf}={minutes(args.config_root, key=args.key, config_file=args.config_file)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
