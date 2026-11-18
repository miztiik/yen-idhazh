"""How are one completed workflow attempt's retained recovery artifacts obtained?"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import ConfigDict, PositiveInt, TypeAdapter

from idhazh.contracts.base import CommitSha, Model, Timestamp
from utilities.digest_recovery_refusal import RecoveryRefusalError, RefusalReason

type PlatformCall = Callable[[str, str], bytes]


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


def pages(repository: str, path: str, key: str, call_api: PlatformCall = api) -> list[object]:
    """Page only the selected run's finite artifact or job inventory."""
    rows: list[object] = []
    page = 1
    while True:
        payload = json.loads(call_api(repository, f"{path}?per_page=100&page={page}"))
        batch = payload[key]
        if not isinstance(batch, list):
            raise RecoveryRefusalError(RefusalReason.PLATFORM_LIST_MISSING, (key,))
        rows.extend(batch)
        if len(rows) >= payload["total_count"]:
            return rows
        if not batch:
            raise RecoveryRefusalError(RefusalReason.PAGINATION_ENDED_EARLY)
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
            raise RecoveryRefusalError(
                RefusalReason.ARTIFACT_EXPIRED_FOREIGN_OR_AMBIGUOUS, (artifact.name,)
            )
        selected[artifact.name] = artifact
    if "plan" not in selected:
        raise RecoveryRefusalError(RefusalReason.NO_PLAN_ARTIFACT)
    return selected


def fetch_source(
    execution: str, repository: str, call_api: PlatformCall
) -> tuple[SourceRun, dict[str, bytes], frozenset[int]]:
    """Fetch and checksum one run's saved plan and items through the given platform client."""
    source = SourceRun.model_validate_json(call_api(repository, f"actions/runs/{execution}"))
    if source.id != int(execution):
        raise RecoveryRefusalError(RefusalReason.ANOTHER_SOURCE_RUN)
    jobs = TypeAdapter(list[SourceJob]).validate_python(
        pages(
            repository,
            f"actions/runs/{execution}/attempts/{source.run_attempt}/jobs",
            "jobs",
            call_api,
        )
    )
    if not any(job.name == "plan" and job.conclusion == "success" for job in jobs):
        raise RecoveryRefusalError(RefusalReason.NO_SUCCESSFUL_PLAN_JOB)
    failed = frozenset(
        int(match[1])
        for job in jobs
        if (match := re.fullmatch(r"work \(([0-9]+)\)", job.name)) and job.conclusion != "success"
    )
    selected = select_artifacts(
        source,
        pages(repository, f"actions/runs/{execution}/artifacts", "artifacts", call_api),
    )
    archives: dict[str, bytes] = {}
    for name, artifact in selected.items():
        data = call_api(repository, f"actions/artifacts/{artifact.id}/zip")
        if f"sha256:{hashlib.sha256(data).hexdigest()}" != artifact.digest:
            raise RecoveryRefusalError(RefusalReason.CHECKSUM_DIFFERS_FROM_DIGEST, (name,))
        archives[name] = data
    return source, archives, failed


def download(execution: str) -> tuple[SourceRun, dict[str, bytes], frozenset[int]]:
    """Download and checksum the saved plan and items, not evidence or model captures."""
    if not re.fullmatch(r"[1-9][0-9]*", execution):
        raise RecoveryRefusalError(RefusalReason.RUN_ID_NOT_POSITIVE)
    repository = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    return fetch_source(execution, repository, api)
