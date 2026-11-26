"""How does the final gardener job append only verified control readings?"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import config, run_context
from idhazh.contracts.task_performance import TaskPerformanceRow
from idhazh.gardener.control_fingerprints import (
    OPERATIONS,
    Job,
    Operation,
    artifact,
    expected,
    recording,
    task_file,
)
from idhazh.telemetry import machine_api, machine_evidence, task_probe
from utilities.publication_evidence import confirmed
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, PublicationRequest, safe_file
from utilities.publish_to_repo import PublicationResult, publish
from utilities.push_retry import DEFAULT_CONFIG, load_retry

CONTROL_JOBS = (Job.PLAN, Job.HISTORY)


def _readings(
    incoming: Path, *, run_id: str, attempt: int, revision: str,
    plan_attempt: int | None, history_attempt: int | None,
) -> Iterator[machine_evidence.VerifiedFile]:
    named: list[tuple[Job, int]] = []
    for job, actual_attempt in zip(CONTROL_JOBS, (plan_attempt, history_attempt), strict=True):
        if actual_attempt is None:
            machine_api.warn(f"Gardener {job} supplied no control evidence")
            continue
        if not 1 <= actual_attempt <= attempt:
            raise IntegrityError("gardener producing attempt is outside the workflow run")
        named.append((job, actual_attempt))
    for job, actual_attempt in named:
        name = artifact(job, run_id, actual_attempt)
        wanted = expected(job, run_id=run_id, attempt=actual_attempt, revision=revision)
        tasks = tuple(task_file(wanted, operation) for operation in OPERATIONS[job])
        root = incoming / name
        # A singleton download may not retain its artifact-directory level.
        if any(
            safe_file(incoming, item.receipt, exists=False).exists() for item in (wanted, *tasks)
        ):
            if len(named) != 1 or root.exists() or root.is_symlink() or root.is_junction():
                raise IntegrityError("mixed gardener control evidence download layout")
            root = incoming
        opening = machine_evidence.read_receipt(root, wanted)
        proofs = [] if opening is None else [opening]
        for task in tasks:
            proof = machine_evidence.read_receipt(root, task)
            if proof is not None:
                machine_evidence.verify_host_link(proof, opening)
                proofs.append(proof)
        if not proofs:
            raise IntegrityError("gardener artifact did not contain its named evidence", (name,))
        yield from proofs


def _place(
    reading: machine_evidence.VerifiedFile, repo: Path, cleanup: ExitStack, hashes: dict[str, str],
) -> None:
    if reading.path in hashes:
        raise IntegrityError("duplicate gardener control evidence path", (reading.path,))
    if (created := reading.place(repo)) is not None:
        cleanup.callback(created.unlink, missing_ok=True)
    hashes[reading.path] = reading.sha256


def land(
    repo: Path, incoming: Path, local: Path, *, run_id: str, attempt: int, revision: str,
    plan_attempt: int | None, history_attempt: int | None,
) -> PublicationResult:
    own = expected(Job.APPEND, run_id=run_id, attempt=attempt, revision=revision)
    preparation = task_file(own, Operation.PREPARE_APPEND)
    scopes = tuple(
        machine_evidence.raw_scope(ledger, own.date)
        for ledger in (machine_evidence.HOST, machine_evidence.TASK)
    )
    with ExitStack() as cleanup:
        with task_probe.profile(recording(repo, local, own), preparation, local):
            git = Repository(repo)
            source = git.git("rev-parse", "HEAD").strip()
            if source != revision:
                raise IntegrityError("gardener publisher is not on the workflow revision")
            hashes: dict[str, str] = {}
            for reading in _readings(
                incoming, run_id=run_id, attempt=attempt, revision=revision,
                plan_attempt=plan_attempt, history_attempt=history_attempt,
            ):
                _place(reading, repo, cleanup, hashes)
            opening = machine_evidence.read_receipt(local, own)
            if opening is None:
                machine_api.warn("Gardener publisher supplied no opening fingerprint")
            else:
                _place(opening, repo, cleanup, hashes)
            retry = load_retry(repo / DEFAULT_CONFIG)
            writes = confirmed(git, hashes, source=source, permissions=scopes)
            request = PublicationRequest(
                own.writer, f"gardener control evidence: {own.date}", source, scopes, (), writes,
            )
            request.validate(repo)
        # The closed preparation can join the request, but cannot measure its own push.
        proof = machine_evidence.read_receipt(local, preparation)
        if proof is not None:
            machine_evidence.verify_host_link(proof, opening)
            if not isinstance(proof.row, TaskPerformanceRow) or proof.row.outcome != "success":
                raise IntegrityError("only completed gardener append preparation may land")
            _place(proof, repo, cleanup, hashes)
            writes.update(confirmed(
                git, {proof.path: proof.sha256}, source=source, permissions=scopes,
            ))
        return publish(request, repo=repo, retry=retry)


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
        print(f"gardener control evidence refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "landing": result.status, "detail": result.detail, "paths": result.refusal_paths,
    }))
    return result.exit_code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
