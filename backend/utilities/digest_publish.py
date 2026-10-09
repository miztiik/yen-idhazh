"""How do PLAN, WORK and ASSEMBLE publish only their completed, declared outputs?"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import completed_writes, config, run_context, telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.ledger import staging
from utilities import publication_evidence
from utilities.publication_conflict import capture_publication_delta, replay_publication_delta
from utilities.publication_git import Repository
from utilities.publication_inputs import materialize, named_entries
from utilities.publication_request import IntegrityError, PublicationRequest, Write, safe_file
from utilities.publish_to_repo import PublicationResult, publish
from utilities.push_retry import DEFAULT_CONFIG, load_retry

INVENTORY = "frontend/public/publication.json"
VERBS = {
    "plan": ("plan", "fingerprint", "job-clock"),
    "work": ("fingerprint", "work", "record", "job-clock"),
    "assemble": ("fingerprint", "assemble", "harvest", "job-clock"),
}


def permissions(job: str, *, date: str) -> tuple[str, ...]:
    """Ledger registry declarations, never a blanket state staging exception."""
    ledgers = tuple(
        staging.staged_path(name)
        for name, held in staging.REGISTRY.items()
        if job in held.job_labels
    )
    if job == "assemble":
        from idhazh.path_classes import DERIVED

        day = "frontend/public/digest/" + date.replace("-", "/")
        return tuple(
            dict.fromkeys(
                (
                    *ledgers,
                    day,
                    *(path.format(day_dir=day) for path in DERIVED),
                    "corpus/corpus.jsonl",
                    "corpus/corpus.meta.json",
                )
            )
        )
    return (*ledgers, INVENTORY)


def _flag(args: list[str], name: str, default: str = "") -> str:
    return args[args.index(name) + 1] if name in args else default


def identify(args: list[str], *, job: str) -> WriterIdentity:
    date = _flag(args, "--date", os.environ.get("PUBLISH_DATE", ""))
    execution = _flag(args, "--execution", os.environ.get("GITHUB_RUN_ID", ""))
    return WriterIdentity(
        run_id=_flag(args, "--run-id", f"{date}-{execution}"),
        attempt=run_context.run_attempt(),
        job=ServerJob(job),
        shard=int(_flag(args, "--shard", os.environ.get("SHARD", "0"))),
        producer="utilities.digest_publish",
        git_sha=_flag(args, "--commit", os.environ.get("GITHUB_SHA", "")),
    )


def run(args: list[str]) -> int:
    """Observe one real producer invocation, including completed writes before failure."""
    from idhazh import cli
    from idhazh.stages import common

    verb = args[0]
    job = _flag(args, "--job", os.environ.get("GITHUB_JOB", ""))
    if job not in VERBS:
        job = "work" if verb in {"work", "record"} else "assemble" if verb == "harvest" else verb
    identity = identify(args, job=job)
    with completed_writes.collect() as writes:
        try:
            return cli.main(args)
        finally:
            if verb == "work":
                trace = telemetry.committed_trace_path(
                    common.STATE_ROOT,
                    run_id=identity.run_id,
                    attempt=identity.attempt,
                    job=identity.job,
                    shard=identity.shard,
                )
                if trace.is_file():
                    completed_writes.record(trace, trace.read_bytes())
            publication_evidence.save(config.REPO_ROOT, identity, verb, writes)


def inventory_preparation(
    repo: Path,
    original: PublicationRequest,
) -> Callable[[str, PublicationRequest], PublicationRequest]:
    """Replay named inventory deltas through the existing inventory writer."""
    git = Repository(repo)
    before_entry = git.entry(
        original.writes[INVENTORY].baseline_tip or original.source_tip, INVENTORY
    )
    before = (
        git.blob(before_entry.oid).decode()
        if before_entry
        else PublicationInventory(version=PublicationInventory.schema_version(), dates=[]).to_json()
    )
    delta = capture_publication_delta(before, (repo / INVENTORY).read_text(encoding="utf-8"))

    def replay(base: str, active: PublicationRequest, scratch: Path) -> PublicationRequest:
        materialize(git, base, (INVENTORY,), scratch)
        for path in active.writes:
            if path == INVENTORY:
                continue
            target = scratch / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((repo / path).read_bytes())
        # Some unchanged paths in a named delta are metadata-only reads.
        named = tuple(f"frontend/public/{path}" for path in delta.public_paths) + tuple(
            f"state/{path}" for path in delta.state_paths
        )
        materialize(git, base, tuple(path for path in named if path not in active.writes), scratch)
        replay_publication_delta(scratch / "frontend" / "public", scratch / "state", delta)
        data = (scratch / INVENTORY).read_bytes()
        (repo / INVENTORY).write_bytes(data)
        writes = {
            path: (
                dataclasses.replace(write, baseline=git.entry(base, path), baseline_tip=base)
                if write.immutable or path == INVENTORY
                else dataclasses.replace(
                    write,
                    baseline_tip=write.baseline_tip or active.source_tip,
                )
            )
            for path, write in active.writes.items()
        }
        writes[INVENTORY] = Write(hashlib.sha256(data).hexdigest(), git.entry(base, INVENTORY))
        return dataclasses.replace(active, source_tip=base, writes=writes)

    def prepare(base: str, active: PublicationRequest) -> PublicationRequest:
        scratch = repo / "backend" / "var" / "publication" / f"inventory-{uuid4().hex}"
        scratch.mkdir(parents=True)
        try:
            return replay(base, active, scratch)
        finally:
            shutil.rmtree(scratch)

    return prepare


def land(*, repo: Path, identity: WriterIdentity, date: str) -> PublicationResult:
    git = Repository(repo)
    head = git.git("rev-parse", "HEAD").strip()
    imported = git.run("rev-parse", "--verify", "--quiet", "refs/worktree/publication-input-state")
    source = imported.stdout.decode().strip() if imported.returncode == 0 else head
    hashes = publication_evidence.read(repo, identity, VERBS[identity.job])
    authority = permissions(identity.job, date=date)
    mutable: tuple[str, ...] = (INVENTORY,)
    if identity.job == ServerJob.ASSEMBLE:
        from idhazh.path_classes import DERIVED

        day = "frontend/public/digest/" + date.replace("-", "/")
        mutable = (
            *tuple(path.format(day_dir=day) for path in DERIVED),
            day,
            "corpus/corpus.jsonl",
            "corpus/corpus.meta.json",
        )
    writes = publication_evidence.confirmed(
        git,
        hashes,
        source=source,
        permissions=authority,
        mutable=mutable,
        code_source=head,
    )
    request = PublicationRequest(
        identity,
        os.environ.get("COMMIT_MESSAGE", f"{identity.job}: {date}"),
        source,
        authority,
        (),
        writes,
        preparation_scopes=(INVENTORY,) if INVENTORY in writes else (),
    )
    if INVENTORY in writes:
        request = dataclasses.replace(request, prepare=inventory_preparation(repo, request))
    if identity.job == ServerJob.ASSEMBLE and writes:
        from utilities import digest_assemble

        request = dataclasses.replace(request, preparation_scopes=mutable)
        request = dataclasses.replace(
            request,
            prepare=digest_assemble.preparation(
                repo,
                request,
                date=date,
                settings=config.load(),
            ),
        )
    result = publish(request, repo=repo, retry=load_retry(repo / DEFAULT_CONFIG))
    print(json.dumps(dataclasses.asdict(result), default=str))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"prepared={'true' if result.prepared else 'false'}\n")
            handle.write(f"candidate={result.observed_tip or result.candidate or ''}\n")
    return result


def published_inputs(repo: Path, tip: str) -> None:
    """Validate every named local input before importing the actual published bytes."""
    from idhazh.contracts.publication_receipt import PublicationReceipt

    git = Repository(repo)
    entry = git.entry(tip, INVENTORY)
    if entry is None:
        raise ValueError("published revision has no publication inventory")
    inventory = PublicationInventory.model_validate_json(git.blob(entry.oid, fetches=True))
    inputs = (
        INVENTORY,
        *(f"frontend/public/{held.path}" for held in inventory.entries if held.root == "public"),
    )
    known: dict[str, str] = {}
    job = os.environ.get("GITHUB_JOB", "")
    if job in VERBS:
        receipts = tuple(
            repo / publication_evidence.ROOT / job / f"{verb}-0.json" for verb in VERBS[job]
        )
    elif job == "backfill":
        receipts = (repo / publication_evidence.ROOT / ServerJob.OPERATOR / "backfill-0.json",)
    else:
        receipts = ()
    for receipt_path in receipts:
        if receipt_path.is_file():
            receipt = PublicationReceipt.read(receipt_path)
            if (
                receipt.identity.run_id.split("-", 3)[-1] != os.environ.get("GITHUB_RUN_ID", "")
                or receipt.identity.attempt != run_context.run_attempt()
                or receipt.identity.git_sha != os.environ.get("GITHUB_SHA", "")
            ):
                raise IntegrityError(
                    "build input receipt belongs to another invocation", (str(receipt_path),)
                )
            known.update(receipt.writes)
    head = git.git("rev-parse", "HEAD").strip()
    incoming = named_entries(git, tip, inputs)
    missing = set(inputs) - incoming.keys()
    if missing:
        raise IntegrityError("published inventory names absent input", tuple(sorted(missing)))
    git.prime(head, set(incoming))
    for path, (mode, kind, oid) in incoming.items():
        if mode != "100644" or kind != "blob":
            raise IntegrityError("published input is not a plain data file", (path,))
        baseline = git.entry(head, path)
        if git.index_entry(path) != baseline:
            raise IntegrityError("published input has foreign staged changes", (path,))
        target = safe_file(repo, path, exists=False)
        if not target.exists():
            continue
        local = target.read_bytes()
        if local == git.blob(oid, fetches=True):
            continue
        if hashlib.sha256(local).hexdigest() == known.get(path):
            continue
        if baseline is None or local != git.blob(baseline.oid, fetches=True):
            raise IntegrityError("published input has foreign local changes", (path,))
    materialize(git, tip, inputs, repo)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "published-inputs":
        parser = argparse.ArgumentParser(
            description="Read the published inventory's named build inputs"
        )
        parser.add_argument("action")
        parser.add_argument("--tip", required=True)
        tip = parser.parse_args(args).tip
        published_inputs(Path.cwd(), tip)
        return 0
    if args and args[0] == "run":
        return run(args[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", choices=tuple(VERBS))
    parser.add_argument("--date", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--shard", default="0")
    parsed = parser.parse_args(args)
    try:
        return land(
            repo=Path.cwd(), identity=identify(args, job=parsed.job), date=parsed.date
        ).exit_code
    except (OSError, ValueError, RuntimeError) as error:
        print(f"publication integrity refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
