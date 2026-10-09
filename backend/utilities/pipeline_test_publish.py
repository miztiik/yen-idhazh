"""How does one collecting job publish checked, immutable pipeline-test artifacts?"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import ledger, run_context
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.pipeline_tests import TRIAL_STATE_PREFIX
from utilities import pipeline_test_ledgers as artifacts
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, PublicationRequest, Write, safe_file
from utilities.publish_to_repo import PublicationResult, publish
from utilities.push_retry import DEFAULT_CONFIG, load_retry


def land(
    repo: Path, tree: Path, *, execution: str, attempt: int, code_sha: str, config_root: Path
) -> PublicationResult:
    roots = artifacts._roots(config_root)
    refused = artifacts.refusals(tree, roots=frozenset(roots))
    if refused:
        raise IntegrityError("; ".join(refused))
    scopes = tuple(
        f"state/{tier}/{TRIAL_STATE_PREFIX}/{name}"
        for name in roots
        for tier in (ledger.paths.RAW_DIRNAME, ledger.paths.TRIAL_TRACES_DIRNAME)
    )
    git = Repository(repo)
    source = git.git("rev-parse", "HEAD").strip()
    writes: dict[str, Write] = {}
    incoming: dict[str, bytes] = {}
    for artifact in sorted(tree.rglob("*")) if tree.is_dir() else ():
        if not artifact.is_file():
            continue
        safe_file(repo, artifact.absolute().relative_to(repo).as_posix(), exists=True)
        parts = artifact.relative_to(tree).parts
        name, tier, *tail = parts
        if tier == artifacts.TRACES:
            day = "-".join(tail[:3])
            own = f"{day}-{execution}-{attempt}-"
            if not artifact.name.startswith(own):
                raise IntegrityError(
                    "trace belongs to another executed invocation", (str(artifact),)
                )
            tier = ledger.paths.TRIAL_TRACES_DIRNAME
        else:
            identity = ledger.read_envelope(artifact).identity
            if (
                identity.run_id.split("-", 3)[-1] != execution
                or identity.attempt != attempt
                or identity.git_sha != code_sha
            ):
                raise IntegrityError("raw artifact belongs to another invocation", (str(artifact),))
        path = "/".join(("state", tier, TRIAL_STATE_PREFIX, name, *tail))
        data = artifact.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        baseline = git.entry(source, path)
        if baseline is not None and (
            baseline.mode != "100644"
            or hashlib.sha256(git.blob(baseline.oid, fetches=True)).hexdigest() != digest
        ):
            raise IntegrityError("immutable artifact identity already has different bytes", (path,))
        target = safe_file(repo, path, exists=False)
        if target.exists() and target.read_bytes() != data:
            raise IntegrityError("artifact would replace foreign local bytes", (path,))
        writes[path] = Write(digest, baseline, immutable=True)
        incoming[path] = data
    for path, data in incoming.items():
        target = safe_file(repo, path, exists=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    identity = WriterIdentity(
        run_id=f"{datetime.now(UTC).date().isoformat()}-{execution}",
        attempt=attempt,
        job=ServerJob.OPERATOR,
        shard=0,
        producer="utilities.pipeline_test_publish",
        git_sha=code_sha,
    )
    return publish(
        PublicationRequest(
            identity,
            os.environ.get("COMMIT_MESSAGE", "pipeline tests: completed artifacts"),
            source,
            scopes,
            (),
            writes,
        ),
        repo=repo,
        retry=load_retry(repo / DEFAULT_CONFIG),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        repo = Path.cwd()
        result = land(
            repo,
            args.tree.absolute(),
            execution=os.environ.get("GITHUB_RUN_ID", ""),
            attempt=run_context.run_attempt(),
            code_sha=os.environ.get("GITHUB_SHA", ""),
            config_root=repo / "config",
        )
        print(json.dumps(dataclasses.asdict(result), default=str))
        return result.exit_code
    except (OSError, ValueError, RuntimeError) as error:
        print(f"pipeline-test publication integrity-refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
