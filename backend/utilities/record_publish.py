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

from idhazh import cli, completed_writes, config, run_context
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.publication_receipt import PublicationReceipt
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
    if args[0] != verb:
        raise ValueError("record client was not given its declared producer")
    date = _flag(args, "--date", datetime.now(UTC).date().isoformat())
    execution = _flag(args, "--execution", os.environ.get("GITHUB_RUN_ID", ""))
    identity = WriterIdentity(
        run_id=f"{date}-{execution}",
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


def land(client: str, *, repo: Path) -> int:
    job, scopes, _ = POLICIES[client]
    receipt = PublicationReceipt.read(repo / publication_evidence.ROOT / job / f"{client}-0.json")
    identity = receipt.identity
    if (
        identity.job != job
        or identity.attempt != run_context.run_attempt()
        or identity.run_id.split("-", 3)[-1] != os.environ.get("GITHUB_RUN_ID", "")
        or identity.git_sha != os.environ.get("GITHUB_SHA", "")
        or identity.producer != "utilities.record_publish"
    ):
        raise ValueError("record receipt does not belong to this executed invocation")
    git = Repository(repo)
    source = git.git("rev-parse", "HEAD").strip()
    hashes = publication_evidence.read(repo, identity, (client,))
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
            else land(
                parsed.client,
                repo=Path.cwd(),
            )
        )
    except (ValueError, OSError, RuntimeError) as error:
        print(f"record publication integrity-refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
