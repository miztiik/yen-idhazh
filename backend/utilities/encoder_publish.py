"""How does one encoder comparison publish only its completed pair, readings and logs?"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import TypeAdapter

from idhazh import completed_writes, run_context
from idhazh.atomic_write import write_atomic_bytes
from idhazh.contracts.base import ServerJob, Slug
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.publication_receipt import PublicationReceipt
from utilities import publication_evidence
from utilities.compare_summary_encoders import read_config, select_encoders, stage_collect
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, PublicationRequest, relative, safe_file
from utilities.publish_to_repo import PublicationResult, publish
from utilities.push_retry import DEFAULT_CONFIG, load_retry

# These names are the comparison's existing file format, not tunable output roots.
OUTPUTS = ("pairs.json", "manifest.json", "readings/encoders.json", "readings/encoders.md")
VERB = "encoder-comparison"
PRODUCER = "utilities.encoder_publish"


def declarations(repo: Path, directory: str, selected: str) -> tuple[str, ...]:
    """Name the comparison's authority from its format and configured shard list."""
    relative(directory)
    if not directory.startswith("corpus/"):
        raise IntegrityError("comparison output must be a named corpus directory", (directory,))
    encoders = select_encoders(read_config(repo / "config/encoder-comparison.json"), selected)
    slugs = [TypeAdapter(Slug).validate_python(encoder["slug"]) for encoder in encoders]
    return tuple(
        f"{directory}/{name}"
        for name in (*OUTPUTS, "logs/pair-build.log", *(f"logs/{slug}.log" for slug in slugs))
    )


def collect(
    repo: Path,
    directory: str,
    *,
    identity: WriterIdentity,
    readings_from: Path,
    logs_from: Path,
    pair_log: Path,
    selected: str,
    preserve_existing: bool,
    run_url: str,
) -> None:
    scopes = declarations(repo, directory, selected)
    for path in scopes:
        safe_file(repo, path, exists=False)
    pairs = safe_file(repo, f"{directory}/pairs.json", exists=True)
    pair_bytes = pairs.read_bytes()
    with completed_writes.collect() as evidence:
        stage_collect(argparse.Namespace(
            config=repo / "config/encoder-comparison.json",
            pairs=pairs,
            readings_from=readings_from,
            out=repo / directory / "readings",
            commit=identity.git_sha,
            run_url=run_url,
            selected=selected,
            preserve_existing=preserve_existing,
        ))
        # Downloaded input is part of this run's output, even when reused unchanged.
        completed_writes.record(pairs, pair_bytes)
        for path in scopes[len(OUTPUTS):]:
            name = Path(path).name
            source = pair_log if name == "pair-build.log" else logs_from / name
            if not source.exists():
                print(f"comparison log not reported: {name}", file=sys.stderr)
                continue
            source = safe_file(repo, source.absolute().relative_to(repo).as_posix(), exists=True)
            write_atomic_bytes(repo / path, source.read_bytes())
    publication_evidence.save(repo, identity, VERB, evidence)


def land(
    repo: Path,
    directory: str,
    *,
    execution: str,
    attempt: int,
    code_sha: str,
    selected: str,
) -> PublicationResult:
    scopes = declarations(repo, directory, selected)
    receipt = PublicationReceipt.read(
        repo / publication_evidence.ROOT / ServerJob.COLLECT / f"{VERB}-0.json"
    )
    identity = receipt.identity
    if (
        identity.job is not ServerJob.COLLECT
        or identity.shard != 0
        or identity.producer != PRODUCER
        or identity.run_id.split("-", 3)[-1] != execution
        or identity.attempt != attempt
        or identity.git_sha != code_sha
    ):
        raise IntegrityError("comparison receipt does not belong to this executed invocation")
    hashes = publication_evidence.read(repo, identity, (VERB,))
    missing = set(scopes[:len(OUTPUTS)]) - hashes.keys()
    foreign = hashes.keys() - set(scopes)
    if missing or foreign:
        raise IntegrityError(
            "comparison receipt must contain complete declared output only",
            tuple(sorted(missing | foreign)),
        )
    git = Repository(repo)
    source = git.git("rev-parse", "HEAD").strip()
    if source != code_sha:
        raise IntegrityError("comparison checkout no longer matches its executed source")
    writes = publication_evidence.confirmed(
        git, hashes, source=source, permissions=scopes, mutable=scopes,
    )
    return publish(
        PublicationRequest(
            identity, "Encoder readings, taken on the runner", source, scopes, (), writes,
        ),
        repo=repo,
        retry=load_retry(repo / DEFAULT_CONFIG),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "land"))
    parser.add_argument("--set-directory", required=True)
    parser.add_argument("--selected", default="")
    parser.add_argument("--execution", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--attempt", type=int, default=run_context.run_attempt())
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--readings-from", type=Path, default=Path("downloaded/readings"))
    parser.add_argument("--logs-from", type=Path, default=Path("downloaded/logs"))
    parser.add_argument("--pair-log", type=Path, default=Path("pair-build.log"))
    parser.add_argument("--preserve-existing", action="store_true")
    parser.add_argument("--run-url", default="")
    args = parser.parse_args(argv)
    repo = Path.cwd()
    try:
        if args.action == "run":
            collect(
                repo, args.set_directory,
                identity=WriterIdentity(
                    run_id=f"{datetime.now(UTC).date().isoformat()}-{args.execution}",
                    attempt=args.attempt, job=ServerJob.COLLECT, shard=0,
                    producer=PRODUCER, git_sha=args.commit,
                ),
                readings_from=args.readings_from, logs_from=args.logs_from,
                pair_log=args.pair_log, selected=args.selected,
                preserve_existing=args.preserve_existing, run_url=args.run_url,
            )
            return 0
        result = land(
            repo, args.set_directory, execution=args.execution, attempt=args.attempt,
            code_sha=args.commit, selected=args.selected,
        )
        print(json.dumps(dataclasses.asdict(result), default=str))
        return result.exit_code
    except (ValueError, OSError, RuntimeError) as error:
        print(f"encoder publication integrity-refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
