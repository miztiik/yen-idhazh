"""How do only the named gardener opening captures append after history ends?"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import config, run_context
from idhazh.gardener.control_fingerprints import Job, artifact, expected
from idhazh.telemetry import machine_api, machine_evidence
from utilities.publication_evidence import confirmed
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, PublicationRequest, safe_file
from utilities.publish_to_repo import PublicationResult, publish
from utilities.push_retry import DEFAULT_CONFIG, load_retry

CONTROL_JOBS = (Job.PLAN, Job.HISTORY)


def _readings(
    incoming: Path, local: Path, *, run_id: str, attempt: int, revision: str,
    plan_attempt: int | None, history_attempt: int | None,
) -> Iterator[machine_evidence.VerifiedFile]:
    # A missing output is not evidence that a job started and captured.
    named: list[tuple[str, machine_evidence.ExpectedFile]] = []
    for job, actual_attempt in zip(CONTROL_JOBS, (plan_attempt, history_attempt), strict=True):
        if actual_attempt is None:
            machine_api.warn(f"Gardener {job} supplied no opening fingerprint")
            continue
        if not 1 <= actual_attempt <= attempt:
            raise IntegrityError("gardener producing attempt is outside the workflow run")
        name = artifact(job, run_id, actual_attempt)
        wanted = expected(job, run_id=run_id, attempt=actual_attempt, revision=revision)
        named.append((name, wanted))
    for name, wanted in named:
        root = incoming / name
        # A singleton download may not retain its artifact-directory level.
        if safe_file(incoming, wanted.receipt, exists=False).exists():
            if len(named) != 1 or root.exists() or root.is_symlink() or root.is_junction():
                raise IntegrityError("mixed gardener fingerprint download layout")
            root = incoming
        proof = machine_evidence.read_receipt(root, wanted)
        if proof is None:
            raise IntegrityError("gardener artifact did not contain its declared reading", (name,))
        yield proof
    own = expected(Job.APPEND, run_id=run_id, attempt=attempt, revision=revision)
    proof = machine_evidence.read_receipt(local, own)
    if proof is None:
        raise IntegrityError("gardener publisher did not produce its opening fingerprint")
    yield proof


def land(
    repo: Path, incoming: Path, local: Path, *, run_id: str, attempt: int, revision: str,
    plan_attempt: int | None, history_attempt: int | None,
) -> PublicationResult:
    own = expected(Job.APPEND, run_id=run_id, attempt=attempt, revision=revision)
    scopes = (machine_evidence.raw_scope(machine_evidence.HOST, own.date),)
    readings = tuple(_readings(
        incoming, local, run_id=run_id, attempt=attempt, revision=revision,
        plan_attempt=plan_attempt, history_attempt=history_attempt,
    ))
    git = Repository(repo)
    source = git.git("rev-parse", "HEAD").strip()
    with ExitStack() as cleanup:
        hashes: dict[str, str] = {}
        for reading in readings:
            if reading.path in hashes:
                raise IntegrityError("duplicate gardener fingerprint path", (reading.path,))
            created = reading.place(repo)
            if created is not None:
                cleanup.callback(created.unlink, missing_ok=True)
            hashes[reading.path] = reading.sha256
        writes = confirmed(git, hashes, source=source, permissions=scopes)
        return publish(
            PublicationRequest(
                own.writer, f"gardener fingerprints: {own.date}", source, scopes, (), writes,
            ),
            repo=repo, retry=load_retry(repo / DEFAULT_CONFIG),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--plan-attempt", type=int)
    parser.add_argument("--history-attempt", type=int)
    parser.add_argument("--incoming", type=Path, required=True)
    parser.add_argument("--local", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not args.run_id.endswith(f"-{os.environ['GITHUB_RUN_ID']}"):
            raise IntegrityError("gardener run ID differs from the workflow execution")
        result = land(
            config.REPO_ROOT, args.incoming, args.local,
            run_id=args.run_id, attempt=run_context.run_attempt(),
            revision=os.environ["GITHUB_SHA"],
            plan_attempt=args.plan_attempt, history_attempt=args.history_attempt,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"gardener fingerprints refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "landing": result.status, "detail": result.detail, "paths": result.refusal_paths,
    }))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
