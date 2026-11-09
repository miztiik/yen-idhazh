"""Decide whether a scheduled or manual Pages run publishes."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Final

# These are fixed repository ownership boundaries; unknown entries are code.
TREE_MODE: Final = "040000"
FILE_MODE: Final = "100644"
MISSING_MODE: Final = "000000"
NON_CODE_ENTRIES: Final = {
    "": {
        "frontend": TREE_MODE,
        "corpus": TREE_MODE,
        ".github": TREE_MODE,
        "state": TREE_MODE,
        "docs": TREE_MODE,
        "TODO": TREE_MODE,
        ".claude": TREE_MODE,
        "README.md": FILE_MODE,
        "CLAUDE.md": FILE_MODE,
        "AGENTS.md": FILE_MODE,
    },
    "frontend": {"public": TREE_MODE},
    "corpus": {"corpus.jsonl": FILE_MODE, "corpus.meta.json": FILE_MODE},
    ".github": {
        "agents": TREE_MODE,
        "instructions": TREE_MODE,
        "prompts": TREE_MODE,
        "skills": TREE_MODE,
    },
}
COMMIT_ID: Final = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class Decision:
    publish: bool
    ref: str
    reason: str


def decide(
    *,
    event_name: str,
    conclusion: str,
    checked: str,
    deployed: str,
    tip: str,
    dispatched_ref: str,
    default_branch: str,
) -> Decision:
    """Apply the publication rule for the workflow's two supported triggers."""
    if event_name == "workflow_dispatch":
        if dispatched_ref != default_branch:
            return Decision(False, tip, f"a manual publish runs from {default_branch} only")
        return Decision(True, tip, "a person asked for a publish")
    if event_name == "schedule":
        if dispatched_ref != default_branch:
            return Decision(False, tip, f"a scheduled publish runs from {default_branch} only")
        if conclusion not in {"success", "not_verified", "blocked"} or (
            (conclusion == "success") != bool(checked)
        ):
            raise ValueError("Invalid publication CI evidence")
        if conclusion == "blocked":
            return Decision(False, tip, "a default-branch push CI is pending or failed")
        if deployed and same_code(deployed, tip):
            return Decision(True, tip, "the code matches the last successful deployment")
        if conclusion != "success" or not checked:
            return Decision(False, tip, "no successful CI verified the changed code")
        if same_code(checked, tip):
            return Decision(True, tip, "CI verified the code; only data or documentation changed")
        return Decision(False, tip, "the current code differs from the code CI verified")
    return Decision(False, tip, f"a {event_name} event does not publish")


def same_code(anchor: str, tip: str) -> bool:
    """Compare named tree entries without traversing generated data or source trees."""
    if not COMMIT_ID.fullmatch(anchor) or not COMMIT_ID.fullmatch(tip):
        raise ValueError("Publication evidence must name full commit IDs")
    if anchor == tip:
        return True
    present = subprocess.run(
        ["git", "cat-file", "-e", f"{anchor}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if present.returncode != 0:
        fetched = subprocess.run(
            ["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", anchor],
            check=False,
        )
        if fetched.returncode != 0:
            print(f"Publication evidence {anchor} is unavailable", file=sys.stderr)
            return False
    changes = _tree_changes(f"{anchor}^{{tree}}", f"{tip}^{{tree}}", NON_CODE_ENTRIES[""])
    if changes is None:
        return False
    for path in ("frontend", "corpus", ".github"):
        if path not in changes:
            continue
        older, newer = changes[path]
        if older == "0" * 40 or newer == "0" * 40:
            empty_tree = subprocess.run(
                ["git", "mktree"], input="", capture_output=True, text=True, check=True
            ).stdout.strip()
            older = empty_tree if older == "0" * 40 else older
            newer = empty_tree if newer == "0" * 40 else newer
        if _tree_changes(older, newer, NON_CODE_ENTRIES[path]) is None:
            return False
    return True


def _tree_changes(
    older: str, newer: str, allowed: dict[str, str]
) -> dict[str, tuple[str, str]] | None:
    # One shallow tree comparison emits at most one entry per allowed name;
    # the first unknown name is enough to refuse the comparison.
    limit = 2 * max(len(older), len(newer)) + max(map(len, allowed)) + 32
    changes: dict[str, tuple[str, str]] = {}
    process = subprocess.Popen(
        [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--no-abbrev",
            "--no-renames",
            "--no-ext-diff",
            older,
            newer,
        ],
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        assert process.stdout is not None
        for _ in range(len(allowed) + 1):
            line = process.stdout.readline(limit)
            if not line:
                break
            if not line.endswith("\n"):
                return None
            try:
                metadata, name = line.rstrip("\n").split("\t", 1)
                old_mode, new_mode, old_id, new_id, _status = metadata.split()
            except ValueError as exc:
                raise RuntimeError("Could not read the publication tree comparison") from exc
            old_mode = old_mode.removeprefix(":")
            if (
                name not in allowed
                or name in changes
                or old_mode not in (allowed[name], MISSING_MODE)
                or new_mode not in (allowed[name], MISSING_MODE)
                or not COMMIT_ID.fullmatch(old_id)
                or not COMMIT_ID.fullmatch(new_id)
            ):
                return None
            changes[name] = (old_id, new_id)
        else:
            return None
        if process.wait() != 0:
            raise RuntimeError("Could not compare publication code with its evidence")
        return changes
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait()
        if process.stdout is not None:
            process.stdout.close()


def main() -> None:
    env = os.environ
    decision = decide(
        event_name=env.get("EVENT_NAME", ""),
        conclusion=env.get("CONCLUSION", ""),
        checked=env.get("CHECKED", ""),
        deployed=env.get("DEPLOYED", ""),
        tip=env["TIP"],
        dispatched_ref=env.get("DISPATCHED_REF", ""),
        default_branch=env.get("DEFAULT_BRANCH", ""),
    )
    print(f"ref={decision.ref}")
    print(f"publish={'true' if decision.publish else 'false'}")
    print(f"reason={decision.reason}")
    verb = "Publishing" if decision.publish else "Not publishing"
    print(f"{verb} {decision.ref}: {decision.reason}", file=sys.stderr)


if __name__ == "__main__":
    main()
