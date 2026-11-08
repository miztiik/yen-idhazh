"""Decide whether a scheduled or manual Pages run publishes."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    publish: bool
    ref: str
    reason: str


def decide(
    *,
    event_name: str,
    conclusion: str,
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
        if conclusion != "success":
            return Decision(False, tip, "CI has not passed on the default branch tip")
        return Decision(True, tip, "CI passed on the default branch tip for a scheduled publish")
    return Decision(False, tip, f"a {event_name} event does not publish")


def main() -> None:
    env = os.environ
    decision = decide(
        event_name=env.get("EVENT_NAME", ""),
        conclusion=env.get("CONCLUSION", ""),
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
