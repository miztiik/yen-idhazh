"""Which shard runs which gardener task at this wake, worked out with nothing of ours installed?

The planner needs only the standard library, independently of optional
fingerprint collection. It reads `config/gardener/config/idhazh_gardener.json` and the
declarations it names under `config/gardener/`, and prints the plan the matrix reads:

    python backend/utilities/gardener_shards.py           step outputs for $GITHUB_OUTPUT
    python backend/utilities/gardener_shards.py --json    the whole plan on one line

**It reads two keys of a declaration.**
`lifecycle_status` and `kind` say whether the matrix runs a task - an active one
whose kind is not `history`, which has a job of its own. The manual workflow
event may narrow that set for telemetry proof. No state folder is read: a shard
checks out only its code and config, and lists what its tasks own or read from
the commit. Every other key is the typed loader's to validate:
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
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

#: The gardener's own knobs, and the folder of named task declarations.
GARDENER_FILE = "gardener/config/idhazh_gardener.json"
TASKS_DIR = "gardener"
DECLARATION_SUFFIX = ".json"

#: The two words a declaration is read for.
ACTIVE = "active"
HISTORY = "history"
COMPACTION = "compaction"

#: This dispatch may pack only its two proof ledgers, not an operator-selected task list.
TELEMETRY_PROOF_TASKS: Final = frozenset({"compact-host-fingerprint", "compact-task-performance"})


def _dispatch_flag(inputs: dict[str, object], name: str) -> bool:
    value = inputs.get(name, False)
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    raise ValueError(f"gardener dispatch input {name} must be boolean")


def dispatch_task_filter(env: Mapping[str, str]) -> frozenset[str] | None:
    """Read the same manual dispatch selection in the plan and numbered shard jobs."""
    if env.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        return None
    try:
        event = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError):
        raise ValueError("could not read the gardener workflow dispatch event") from None
    inputs = event.get("inputs", {}) if isinstance(event, dict) else None
    if not isinstance(inputs, dict):
        raise ValueError("gardener workflow dispatch inputs must be an object")
    if not _dispatch_flag(inputs, "telemetry_proof"):
        return None
    if _dispatch_flag(inputs, "force"):
        raise ValueError("telemetry_proof cannot be combined with force")
    return TELEMETRY_PROOF_TASKS


def _key(declaration: dict[str, Any], key: str, name: str) -> Any:
    if key not in declaration:
        raise SystemExit(
            f"config/{TASKS_DIR}/{name}{DECLARATION_SUFFIX} is refused: it names no {key}"
        )
    return declaration[key]


def declarations(config_root: Path) -> dict[str, dict[str, Any]]:
    """Only declarations named by the gardener config."""
    folder = config_root / TASKS_DIR
    knobs = json.loads((config_root / GARDENER_FILE).read_text(encoding="utf-8"))
    names = knobs["task_names"]
    if not isinstance(names, list) or any(
        not isinstance(name, str) or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None
        for name in names
    ):
        raise SystemExit(f"config/{GARDENER_FILE} task_names must be a list of task slugs")
    if len(names) != len(set(names)):
        raise SystemExit(f"config/{GARDENER_FILE} task_names repeats a task")
    for name in names:
        if not (folder / f"{name}{DECLARATION_SUFFIX}").is_file():
            raise SystemExit(f"config/{TASKS_DIR}/{name}{DECLARATION_SUFFIX} is missing")
    return {
        name: json.loads((folder / f"{name}{DECLARATION_SUFFIX}").read_text(encoding="utf-8"))
        for name in sorted(names)
    }


def plan(
    config_root: Path, *, allowed_tasks: frozenset[str] | None = None,
) -> dict[str, Any]:
    """The plan payload: every shard and its tasks, and the matrix that runs them."""
    knobs = json.loads((config_root / GARDENER_FILE).read_text(encoding="utf-8"))
    tasks = declarations(config_root)
    names = sorted(
        name
        for name, declared in tasks.items()
        if _key(declared, "lifecycle_status", name) == ACTIVE
        and _key(declared, "kind", name) != HISTORY
        and (
            allowed_tasks is None
            or (name in allowed_tasks and _key(declared, "kind", name) == COMPACTION)
        )
    )
    count = min(int(knobs["shards"]), len(names))
    dealt: list[list[str]] = [[] for _ in range(count)]
    for position, name in enumerate(names):
        dealt[position % count].append(name)
    shards = [{"index": index, "task_names": held} for index, held in enumerate(dealt)]
    legs = [{"shard": shard["index"], "task_names": shard["task_names"]} for shard in shards]
    return {
        "any_active_task": bool(shards),
        "shard_count": count,
        "shards": shards,
        "matrix": {"include": legs},
    }


def payload(planned: dict[str, Any]) -> str:
    """The plan as one line: compact, keys sorted, ASCII."""
    return json.dumps(planned, separators=(",", ":"), sort_keys=True)


def outputs(planned: dict[str, Any], *, history_allowed: bool = True) -> list[str]:
    """The step outputs the workflow gates history and fans out its shards on."""
    return [
        f"any_active_task={'true' if planned['any_active_task'] else 'false'}",
        f"shard_count={planned['shard_count']}",
        f"matrix={payload(planned['matrix'])}",
        f"history_allowed={'true' if history_allowed else 'false'}",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument(
        "--json", action="store_true", help="Print the whole plan payload on one line."
    )
    args = parser.parse_args(argv)
    try:
        allowed_tasks = dispatch_task_filter(os.environ)
    except ValueError as refusal:
        parser.error(str(refusal))
    planned = plan(args.config_root, allowed_tasks=allowed_tasks)
    if args.json:
        print(payload(planned))
    else:
        print("\n".join(outputs(planned, history_allowed=allowed_tasks is None)))
    return 0


if __name__ == "__main__":
    # A crash prints where it broke, never what it said. Nothing installs the
    # package here, so the printer is imported from this checkout's `backend/`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from idhazh import crash_trace

    crash_trace.install()
    raise SystemExit(main())
