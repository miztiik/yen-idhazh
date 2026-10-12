"""How do measurement, qualification and backfill publish their exact completed records?"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import cli, completed_writes, config, ledger, run_context
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_output import HostPublicationReceipt
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.telemetry.host_output_verify import VerificationLimits
from idhazh.telemetry.host_publication import (
    MODE_ENV,
    consume_host_publication,
    reconcile_host_writes,
)
from utilities import publication_evidence
from utilities.digest_publish import INVENTORY, _flag, inventory_preparation
from utilities.publication_git import Repository
from utilities.publication_request import PublicationRequest
from utilities.publish_to_repo import publish
from utilities.push_retry import DEFAULT_CONFIG, load_retry

POLICIES = {
    "measure": (ServerJob.RUNTIME, ("state/raw/pipeline-tests/host-fingerprint",), "fingerprint"),
    "validate": (
        ServerJob.DECIDE,
        ("state/raw/pipeline-tests/candidate-models",),
        "qualify-decide",
    ),
    "backfill": (
        ServerJob.OPERATOR,
        (
            "frontend/public/digest",
            "frontend/public/assist/index",
            INVENTORY,
        ),
        "backfill-vectors",
    ),
}


def capture(client: str, args: list[str]) -> int:
    job, _, verb = POLICIES[client]
    if client == "measure":
        job = measure_job(_flag(args, "--job", job.value))
    if args[0] != verb:
        raise ValueError("record client was not given its declared producer")
    date = _flag(args, "--date", datetime.now(UTC).date().isoformat())
    execution = _flag(args, "--execution", os.environ.get("GITHUB_RUN_ID", ""))
    identity = WriterIdentity(
        run_id=_flag(args, "--run-id", f"{date}-{execution}"),
        attempt=run_context.run_attempt(),
        job=job,
        shard=0,
        producer="utilities.record_publish",
        git_sha=_flag(args, "--commit", os.environ.get("GITHUB_SHA", "")),
    )
    with completed_writes.collect() as writes:
        try:
            return cli.main(args)
        finally:
            publication_evidence.save(config.REPO_ROOT, identity, client, writes)


def measure_job(value: str) -> ServerJob:
    job = ServerJob(value)
    if job not in {ServerJob.RUNTIME, ServerJob.COLLECT}:
        raise ValueError("measurement publication requires runtime or collect job identity")
    return job


def land(
    client: str,
    *,
    repo: Path,
    identity: WriterIdentity | None = None,
    date: str | None = None,
    host_receipt: HostPublicationReceipt | Path | None = None,
    host_limits: VerificationLimits | None = None,
    host_enabled: bool | None = None,
) -> int:
    job, scopes, _ = POLICIES[client]
    if client == "measure" and identity is not None:
        job = measure_job(identity.job.value)
    native_mode = host_receipt is not None or os.environ.get(MODE_ENV, "legacy") == "rust"
    if native_mode:
        if client != "measure":
            raise ValueError("this record client has no native host publication declaration")
        date = date or os.environ.get("PUBLISH_DATE")
        if not date:
            raise ValueError("native measurement publication requires its executed UTC date")
        if identity is None:
            identity = WriterIdentity(
                run_id=f"{date}-{os.environ.get('GITHUB_RUN_ID', '')}",
                attempt=run_context.run_attempt(),
                job=job,
                shard=0,
                producer="utilities.record_publish",
                git_sha=os.environ.get("GITHUB_SHA", ""),
            )
        job = measure_job(identity.job.value)
    else:
        receipt = PublicationReceipt.read(
            repo / publication_evidence.ROOT / job / f"{client}-0.json"
        )
        if identity is not None and receipt.identity != identity:
            raise ValueError("record receipt does not belong to the expected invocation")
        identity = receipt.identity
    if (
        identity.job != job
        or identity.attempt != run_context.run_attempt()
        or identity.run_id.split("-", 3)[-1] != os.environ.get("GITHUB_RUN_ID", "")
        or identity.git_sha != os.environ.get("GITHUB_SHA", "")
        or identity.producer != "utilities.record_publish"
        or identity.shard != 0
    ):
        raise ValueError("record receipt does not belong to this executed invocation")
    git = Repository(repo)
    source = git.git("rev-parse", "HEAD").strip()
    hashes = publication_evidence.read(repo, identity, (client,))
    registry = ledger.overlay_registry(("pipeline-tests",)) if client == "measure" else None
    if native_mode and host_enabled is None:
        host_enabled = config.load().app.observability.host_fingerprint
    native = consume_host_publication(
        repo=repo,
        identity=identity,
        date=date or identity.run_id[:10],
        receipt=host_receipt,
        limits=host_limits,
        registry=registry,
        host_enabled=True if host_enabled is None else host_enabled,
    )
    if native_mode:
        hashes = reconcile_host_writes(hashes, native, registry=registry)
    writes = publication_evidence.confirmed(
        git,
        hashes,
        source=source,
        permissions=scopes,
        mutable=scopes if client == "backfill" else (),
    )
    request = PublicationRequest(
        identity,
        os.environ.get("COMMIT_MESSAGE", client),
        source,
        scopes,
        (),
        writes,
        preparation_scopes=(INVENTORY,) if INVENTORY in writes else (),
    )
    if INVENTORY in writes:
        request = dataclasses.replace(request, prepare=inventory_preparation(repo, request))
    result = publish(request, repo=repo, retry=load_retry(repo / DEFAULT_CONFIG))
    print(json.dumps(dataclasses.asdict(result), default=str))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"candidate={result.observed_tip or result.candidate or ''}\n")
    return result.exit_code


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "land"))
    parser.add_argument("client", choices=tuple(POLICIES))
    parsed, producer_args = parser.parse_known_args(args)
    try:
        return (
            capture(parsed.client, producer_args)
            if parsed.action == "run"
            else _land(parsed.client, producer_args)
        )
    except (ValueError, OSError, RuntimeError) as error:
        print(f"record publication integrity-refused: {error}", file=sys.stderr)
        return 2


def _land(client: str, args: list[str]) -> int:
    if not args:
        return land(client, repo=Path.cwd())
    parser = argparse.ArgumentParser(description="Identify the executed record publisher")
    parser.add_argument("--date", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--job", default=POLICIES[client][0].value)
    parser.add_argument("--host-fingerprint", action=argparse.BooleanOptionalAction, default=None)
    parsed = parser.parse_args(args)
    return land(
        client,
        repo=Path.cwd(),
        date=parsed.date,
        host_enabled=parsed.host_fingerprint,
        identity=WriterIdentity(
            run_id=f"{parsed.date}-{parsed.execution}",
            attempt=run_context.run_attempt(),
            job=measure_job(parsed.job) if client == "measure" else POLICIES[client][0],
            shard=0,
            producer="utilities.record_publish",
            git_sha=parsed.commit,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
