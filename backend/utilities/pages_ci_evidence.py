"""Find bounded CI and deployment evidence for scheduled Pages publication."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Final

# The Actions and deployments APIs return at most 100 records per page.
PAGE_SIZE: Final = 100
COMMIT_ID: Final = re.compile(r"[0-9a-f]{40}")
RUN_FIELDS: Final = (
    '.workflow_runs[] | [.id, .run_number, .head_sha, .status, '
    '(.conclusion // ""), .event] | @tsv'
)


@dataclass(frozen=True)
class CiRun:
    run_id: int
    number: int
    sha: str
    status: str
    conclusion: str
    event: str
    gates: str = ""


@dataclass(frozen=True)
class CiEvidence:
    sha: str
    blocked: bool
    reason: str


def select_ci_anchor(runs: Iterable[CiRun]) -> CiEvidence:
    """Choose the newest full CI result without passing a failed push."""
    for run in runs:
        if run.status != "completed" or run.conclusion != "success":
            if run.event == "push":
                return CiEvidence("", True, "A default-branch push CI is pending or failed")
            continue
        if run.gates == "skipped":
            continue
        if run.gates != "success":
            return CiEvidence("", True, "The CI code gate did not pass")
        return CiEvidence(run.sha, False, "A full default-branch CI run passed")
    return CiEvidence("", False, "No recent full CI run passed; dispatch CI on the default branch")


def _api(endpoint: str, fields: tuple[str, ...], query: str) -> list[str]:
    args = ["gh", "api", endpoint, "--method", "GET"]
    for field in fields:
        args.extend(("-f", field))
    args.extend(("--jq", query))
    result = subprocess.run(args, check=True, stdout=subprocess.PIPE, text=True)
    return result.stdout.splitlines()


def _commit(value: str) -> str:
    if not COMMIT_ID.fullmatch(value):
        raise ValueError("The API returned an invalid commit ID")
    return value


def _runs(repository: str, branch: str, event: str, *, successful: bool = False) -> list[CiRun]:
    fields = [
        f"branch={branch}",
        f"event={event}",
        f"per_page={PAGE_SIZE if event == 'push' else 1}",
    ]
    if successful:
        fields.append("status=success")
    rows = _api(f"repos/{repository}/actions/workflows/ci.yml/runs", tuple(fields), RUN_FIELDS)
    runs = []
    for row in rows:
        parts = row.split("\t")
        if len(parts) != 6:
            raise ValueError("The API returned an invalid CI run")
        run_id, number, sha, status, conclusion, held_event = parts
        if held_event != event:
            raise ValueError("The API returned a CI run for another event")
        runs.append(CiRun(int(run_id), int(number), _commit(sha), status, conclusion, held_event))
    return runs


def _observe_gates(repository: str, runs: Iterable[CiRun]) -> Iterator[CiRun]:
    for run in runs:
        if run.status != "completed" or run.conclusion != "success":
            yield run
            continue
        query = (
            '[.jobs[] | select(.name == "gates") | .conclusion] | '
            'if length == 1 then (.[0] // "pending") else "missing" end'
        )
        values = _api(
            f"repos/{repository}/actions/runs/{run.run_id}/jobs",
            (f"per_page={PAGE_SIZE}",),
            query,
        )
        if len(values) != 1:
            raise ValueError("The API returned an invalid CI code-gate result")
        yield CiRun(
            run.run_id, run.number, run.sha, run.status, run.conclusion, run.event, values[0]
        )


def _deployed_anchor(repository: str, branch: str) -> str:
    rows = _api(
        f"repos/{repository}/deployments",
        ("environment=github-pages", f"per_page={PAGE_SIZE}"),
        '.[] | [.id, .sha, .ref] | @tsv',
    )
    for row in rows:
        parts = row.split("\t")
        if len(parts) != 3:
            raise ValueError("The API returned an invalid Pages deployment")
        deployment_id, sha, ref = parts
        if ref != branch:
            continue
        deployment_id = str(int(deployment_id))
        statuses = _api(
            f"repos/{repository}/deployments/{deployment_id}/statuses",
            (f"per_page={PAGE_SIZE}",),
            '[.[] | select(.state == "success")] | length',
        )
        if len(statuses) != 1:
            raise ValueError("The API returned invalid Pages deployment statuses")
        if int(statuses[0]) > 0:
            return _commit(sha)
    return ""


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ["DEFAULT_BRANCH"]
    pushes = _runs(repository, branch, "push")
    manual = _runs(repository, branch, "workflow_dispatch", successful=True)
    runs = sorted((*pushes, *manual), key=lambda run: run.number, reverse=True)
    evidence = select_ci_anchor(_observe_gates(repository, runs))
    deployed = _deployed_anchor(repository, branch)
    print(f"checked={evidence.sha}")
    print(f"deployed={deployed}")
    conclusion = "blocked" if evidence.blocked else "success" if evidence.sha else "not_verified"
    print(f"conclusion={conclusion}")
    print(evidence.reason, file=sys.stderr)


if __name__ == "__main__":
    main()
