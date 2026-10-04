"""Decide whether the Pages workflow publishes, and which commit it builds.

The Pages workflow runs this on a bare checkout before anything is installed, so
it imports only the standard library. It reads the run that woke the workflow
from its environment and prints `ref=`, `publish=` and `reason=` as step outputs.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

#: Paths the site build never reads. Every other path is a build input, so an
#: input nobody listed here publishes rather than being missed.
NOT_BUILD_INPUTS: Final = (
    ".claude/",
    ".github/",
    "TODO/",
    "backend/",
    "corpus/",
    "docs/",
    "frontend/tests/",
    "notebooks/",
    "tests/",
)

#: The one file under `.github/` that changes how the site is built.
PAGES_WORKFLOW: Final = ".github/workflows/pages.yml"

#: Build inputs that data runs write. A build input anywhere else is site code.
DATA_ROOTS: Final = ("frontend/public/", "state/")

#: Where the daily run puts a published day.
PUBLISHED_ROOT: Final = "frontend/public/"

#: The `before` of a push that created its branch: there is no earlier commit.
NO_COMMIT: Final = "0" * 40

_COMMIT_ID: Final = re.compile(r"[0-9a-f]{40}")

#: Paths that differ between two named commits, or None when they cannot be read.
Changes = Callable[[str, str], list[str] | None]


@dataclass(frozen=True)
class Decision:
    publish: bool
    ref: str
    reason: str


def is_build_input(path: str) -> bool:
    """Whether the site build reads this path. A file at the root is never read."""
    return path == PAGES_WORKFLOW or ("/" in path and not path.startswith(NOT_BUILD_INPUTS))


def is_site_code(path: str) -> bool:
    return is_build_input(path) and not path.startswith(DATA_ROOTS)


def decide(
    *,
    event_name: str,
    trigger: str,
    trigger_event: str,
    conclusion: str,
    checked: str,
    before: str,
    tip: str,
    dispatched_ref: str,
    default_branch: str,
    changes: Changes,
) -> Decision:
    """One rule a trigger. Every publish builds `tip`, and a diff that cannot be read publishes."""
    if event_name == "workflow_dispatch":
        if dispatched_ref != default_branch:
            return Decision(False, tip, f"a manual publish runs from {default_branch} only")
        return Decision(True, tip, "a person asked for a publish")
    if event_name != "workflow_run":
        return Decision(False, tip, f"a {event_name} event does not publish")
    if trigger == "CI":
        return _decide_after_ci(trigger_event, conclusion, checked, before, tip, changes)
    if trigger == "Content refresh":
        landed = changes(checked, tip)
        if landed is None:
            return Decision(True, tip, "what the daily run landed could not be read")
        if any(path.startswith(PUBLISHED_ROOT) for path in landed):
            return Decision(True, tip, "the daily run landed a published change")
        return Decision(False, tip, "the daily run landed nothing the site serves")
    return Decision(False, tip, f"a {trigger} run does not publish")


def _decide_after_ci(
    trigger_event: str, conclusion: str, checked: str, before: str, tip: str, changes: Changes
) -> Decision:
    if trigger_event != "push":
        return Decision(False, tip, f"CI ran for a {trigger_event}, which is not a merged commit")
    if conclusion != "success":
        return Decision(False, tip, f"CI on the push ended {conclusion}")
    pushed = None if before in ("", NO_COMMIT) else changes(before, checked)
    if pushed is not None and not any(is_build_input(path) for path in pushed):
        return Decision(False, tip, "the push changed nothing the site is built from")
    newer = [] if checked == tip else changes(checked, tip)
    if newer and any(is_site_code(path) for path in newer):
        return Decision(False, tip, "a newer push changed site code, and its own CI publishes")
    if pushed is None or newer is None:
        return Decision(True, tip, "CI passed, and a range it needed could not be read")
    return Decision(True, tip, "CI passed on a push that changed what the site is built from")


def read_changes(older: str, newer: str) -> list[str] | None:
    """Paths that differ between two named commits, fetching either one if it is missing."""
    for commit in (older, newer):
        if not _COMMIT_ID.fullmatch(commit) or not (_has_commit(commit) or _fetch_commit(commit)):
            return None
    shown = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", older, newer],
        capture_output=True,
        text=True,
        check=False,
    )
    if shown.returncode != 0:
        return None
    return [line for line in shown.stdout.splitlines() if line]


def _has_commit(commit: str) -> bool:
    found = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True, check=False
    )
    return found.returncode == 0


def _fetch_commit(commit: str) -> bool:
    fetched = subprocess.run(
        ["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", commit],
        capture_output=True,
        check=False,
    )
    return fetched.returncode == 0


def main() -> None:
    env = os.environ
    decision = decide(
        event_name=env.get("EVENT_NAME", ""),
        trigger=env.get("TRIGGER", ""),
        trigger_event=env.get("TRIGGER_EVENT", ""),
        conclusion=env.get("CONCLUSION", ""),
        checked=env.get("CHECKED", ""),
        before=env.get("BEFORE", ""),
        tip=env["TIP"],
        dispatched_ref=env.get("DISPATCHED_REF", ""),
        default_branch=env.get("DEFAULT_BRANCH", ""),
        changes=read_changes,
    )
    print(f"ref={decision.ref}")
    print(f"publish={'true' if decision.publish else 'false'}")
    print(f"reason={decision.reason}")
    verb = "Publishing" if decision.publish else "Not publishing"
    print(f"{verb} {decision.ref}: {decision.reason}", file=sys.stderr)


if __name__ == "__main__":
    main()
