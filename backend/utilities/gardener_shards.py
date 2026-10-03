"""Which shard runs which gardener task at this wake, worked out with nothing of ours installed?

The gardener's plan job runs this before the package is installed, so it is
the standard library alone. It reads `config/idhazh_gardener.json` and every
declaration under `config/gardener/`, and prints the plan the matrix reads:

    python backend/utilities/gardener_shards.py           three lines for $GITHUB_OUTPUT
    python backend/utilities/gardener_shards.py --json    the whole plan on one line

**It opens nothing outside `config/`, and reads two keys of a declaration.**
`lifecycle_status` and `kind` say whether the matrix runs a task - an active one
whose kind is not `history`, which has a job of its own. No folder is read: a
shard checks out only its code and config, and lists what its tasks own or read
from the commit. Every other key is the typed loader's to validate:
`idhazh gardener plan-shards` reads the same files through it, and a test holds
the two to one payload for one config.

**The split is round-robin over sorted names**, into the smaller of `shards` and
the number of tasks, so no shard is ever empty and every task is in one. It is
written out twice, here and in `idhazh.gardener.shards`, because this side
cannot import that one - which is why the test exists.

No state is read, no clock is read and nothing is written, so what this costs
is the number of declarations and nothing that grows with the archive
(Guardrail #12).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

#: The gardener's own knobs, and the folder of declarations beside them.
GARDENER_FILE = "idhazh_gardener.json"
TASKS_DIR = "gardener"
DECLARATION_SUFFIX = ".json"

#: The two words a declaration is read for.
ACTIVE = "active"
HISTORY = "history"


def _key(declaration: dict[str, Any], key: str, name: str) -> Any:
    if key not in declaration:
        raise SystemExit(
            f"config/{TASKS_DIR}/{name}{DECLARATION_SUFFIX} is refused: it names no {key}"
        )
    return declaration[key]


def declarations(config_root: Path, names: list[str]) -> dict[str, dict[str, Any]]:
    """The configured declarations, opened by name rather than discovered from a directory."""
    folder = config_root / TASKS_DIR
    return {
        name: json.loads((folder / f"{name}{DECLARATION_SUFFIX}").read_text(encoding="utf-8"))
        for name in sorted(names)
    }


def plan(config_root: Path) -> dict[str, Any]:
    """The plan payload: every shard and its tasks, and the matrix that runs them."""
    knobs = json.loads((config_root / GARDENER_FILE).read_text(encoding="utf-8"))
    tasks = declarations(config_root, knobs["task_names"])
    names = sorted(
        name
        for name, declared in tasks.items()
        if _key(declared, "lifecycle_status", name) == ACTIVE
        and _key(declared, "kind", name) != HISTORY
    )
    count = min(int(knobs["shards"]), len(names))
    dealt: list[list[str]] = [[] for _ in range(count)]
    for position, name in enumerate(names):
        dealt[position % count].append(name)
    shards = [{"index": index, "task_names": held} for index, held in enumerate(dealt)]
    legs = [{"shard": shard["index"]} for shard in shards]
    return {
        "any_active_task": bool(shards),
        "shard_count": count,
        "shards": shards,
        "matrix": {"include": legs},
    }


def payload(planned: dict[str, Any]) -> str:
    """The plan as one line: compact, keys sorted, ASCII."""
    return json.dumps(planned, separators=(",", ":"), sort_keys=True)


def outputs(planned: dict[str, Any]) -> list[str]:
    """The three step outputs a workflow gates and fans out on."""
    return [
        f"any_active_task={'true' if planned['any_active_task'] else 'false'}",
        f"shard_count={planned['shard_count']}",
        f"matrix={payload(planned['matrix'])}",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument(
        "--json", action="store_true", help="Print the whole plan payload on one line."
    )
    args = parser.parse_args(argv)
    planned = plan(args.config_root)
    print(payload(planned) if args.json else "\n".join(outputs(planned)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
