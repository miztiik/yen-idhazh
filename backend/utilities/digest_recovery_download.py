"""How are one completed workflow attempt's retained recovery artifacts obtained?"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Sequence
from typing import Literal

from pydantic import ConfigDict, PositiveInt, TypeAdapter

from idhazh.contracts.base import CommitSha, Model, Timestamp
from utilities.publication_request import IntegrityError


class SourceRun(Model):
    """The platform's source execution metadata, not a new persisted project payload."""

    model_config = ConfigDict(extra="ignore")
    id: PositiveInt
    run_attempt: PositiveInt
    head_sha: CommitSha
    path: Literal[".github/workflows/digest.yml"]
    status: Literal["completed"]
    conclusion: Literal["success", "failure"]
    run_started_at: Timestamp


class ArtifactRun(Model):
    model_config = ConfigDict(extra="ignore")
    id: PositiveInt
    head_sha: CommitSha


class Artifact(Model):
    model_config = ConfigDict(extra="ignore")
    id: PositiveInt
    name: str
    expired: bool
    created_at: Timestamp
    digest: str
    workflow_run: ArtifactRun


class SourceJob(Model):
    model_config = ConfigDict(extra="ignore")
    name: str
    conclusion: str


def api(repository: str, path: str) -> bytes:
    """Use the authenticated platform client, never article-supplied addresses."""
    return subprocess.run(
        ["gh", "api", f"repos/{repository}/{path}"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def pages(repository: str, path: str, key: str) -> list[object]:
    """Page only the selected run's finite artifact or job inventory."""
    rows: list[object] = []
    page = 1
    while True:
        payload = json.loads(api(repository, f"{path}?per_page=100&page={page}"))
        batch = payload[key]
        if not isinstance(batch, list):
            raise IntegrityError(f"platform response has no {key} list")
        rows.extend(batch)
        if len(rows) >= payload["total_count"]:
            return rows
        if not batch:
            raise IntegrityError("platform pagination ended before its declared count")
        page += 1


def select_artifacts(source: SourceRun, values: Sequence[object]) -> dict[str, Artifact]:
    """Refuse expired, ambiguous, foreign or earlier-attempt recovery inputs."""
    selected: dict[str, Artifact] = {}
    for artifact in TypeAdapter(list[Artifact]).validate_python(values):
        if artifact.name != "plan" and not re.fullmatch(r"items-[0-9]+", artifact.name):
            continue
        if (
            artifact.expired
            or artifact.workflow_run.id != source.id
            or artifact.workflow_run.head_sha != source.head_sha
            or artifact.created_at < source.run_started_at
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", artifact.digest)
            or artifact.name in selected
        ):
            raise IntegrityError(
                "source artifacts are expired, foreign or ambiguous", (artifact.name,)
            )
        selected[artifact.name] = artifact
    if "plan" not in selected:
        raise IntegrityError("source run has no retained plan artifact")
    return selected


def download(execution: str) -> tuple[SourceRun, dict[str, bytes], frozenset[int]]:
    """Download and checksum the saved plan and items, not evidence or model captures."""
    if not re.fullmatch(r"[1-9][0-9]*", execution):
        raise ValueError("source run must be a positive platform run ID")
    repository = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    source = SourceRun.model_validate_json(api(repository, f"actions/runs/{execution}"))
    if source.id != int(execution):
        raise IntegrityError("platform returned another source run")
    jobs = TypeAdapter(list[SourceJob]).validate_python(
        pages(repository, f"actions/runs/{execution}/attempts/{source.run_attempt}/jobs", "jobs")
    )
    if not any(job.name == "plan" and job.conclusion == "success" for job in jobs):
        raise IntegrityError("source attempt has no successful planning job")
    failed = frozenset(
        int(match[1])
        for job in jobs
        if (match := re.fullmatch(r"work \(([0-9]+)\)", job.name)) and job.conclusion != "success"
    )
    selected = select_artifacts(
        source,
        pages(repository, f"actions/runs/{execution}/artifacts", "artifacts"),
    )
    archives: dict[str, bytes] = {}
    for name, artifact in selected.items():
        data = api(repository, f"actions/artifacts/{artifact.id}/zip")
        if f"sha256:{hashlib.sha256(data).hexdigest()}" != artifact.digest:
            raise IntegrityError(
                "downloaded artifact checksum differs from platform digest", (name,)
            )
        archives[name] = data
    return source, archives, failed
