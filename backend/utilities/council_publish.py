"""How does the council's one collecting job publish every tenant's completed outputs?"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import config
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import session
from idhazh.council.registry import tenants
from idhazh.council.tenancy import Tenant
from utilities.council_matrix import COUNCIL_LEDGER
from utilities.publication_evidence import identified
from utilities.publication_git import Repository
from utilities.publication_inputs import materialize
from utilities.publication_request import IntegrityError, PublicationRequest, Write, contains
from utilities.publish_to_repo import publish
from utilities.push_retry import DEFAULT_CONFIG, load_retry


def settle_and_publish(
    *, repo: Path, dates: tuple[str, ...], run_id: str, commit_sha: str, config_root: Path
) -> int:
    settings = config.load(config_root)
    hosted = tenants(settings.app.council.tenants)
    if not hosted:
        print("council: no tenants; no record or publication")
        return 0
    git = Repository(repo)
    source = git.git("rev-parse", "HEAD").strip()
    permissions = tuple(
        dict.fromkeys(
            (
                COUNCIL_LEDGER,
                *(path for host in hosted for path in host.committed_paths),
            )
        )
    )
    writes: dict[str, Write] = {}
    task_failed = False
    integrity_failed: IntegrityError | None = None
    identity = session._identify_writer(run_id=run_id, commit_sha=commit_sha)

    def completed(host: Tenant | None, evidence: dict[Path, str]) -> None:
        nonlocal integrity_failed
        allowed = (COUNCIL_LEDGER,) if host is None else host.committed_paths
        confirmed: dict[str, str] = {}
        for target, digest in evidence.items():
            path = target.relative_to(repo).as_posix()
            if path.startswith("backend/var/"):
                continue
            if not any(contains(scope, path) for scope in allowed):
                integrity_failed = IntegrityError(
                    "tenant output exceeds its own declaration", (path,)
                )
                raise integrity_failed
            confirmed[path] = digest
            writes[path] = Write(digest, git.entry(source, path), path.startswith("state/raw/"))
        # A receipt is a bounded invocation file, never a new commit ledger.
        receipt = PublicationReceipt(
            version=PublicationReceipt.schema_version(), identity=identity, writes=confirmed
        )
        try:
            identified(repo, identity, confirmed)
        except IntegrityError as error:
            integrity_failed = error
            raise
        target = repo / "backend" / "var" / "council" / "publication" / (f"{len(receipts):04}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(receipt.to_json(), encoding="utf-8", newline="\n")
        receipts.append(target)

    receipts: list[Path] = []
    for date in dates:
        try:
            for host in hosted:
                inputs = getattr(host, "publication_inputs", None)
                if inputs is None:
                    sparse = (
                        git.git("config", "--get", "core.sparseCheckout")
                        if git.run("config", "--get", "core.sparseCheckout").returncode == 0
                        else ""
                    )
                    if sparse.strip() == "true":
                        raise IntegrityError(
                            "sparse tenant has no declared input paths", (host.judge_id,)
                        )
                else:
                    materialize(
                        git,
                        source,
                        tuple(path for path in inputs(date=date) if path not in writes),
                        repo,
                        preserve_existing=True,
                    )
            session.settle(
                settings.app.council,
                date=date,
                run_id=run_id,
                state_dir=repo / "state",
                commit_sha=commit_sha,
                completed=completed,
            )
        except Exception as error:
            if isinstance(error, IntegrityError):
                integrity_failed = error
            task_failed = True
            print(f"council {date}: task failure {type(error).__name__}: {error}", file=sys.stderr)
    if integrity_failed is not None:
        print(f"council: integrity-refused: {integrity_failed}", file=sys.stderr)
        return 2
    request = PublicationRequest(
        identity,
        "council: " + " ".join(dates),
        source,
        permissions,
        (),
        writes,
    )
    result = publish(request, repo=repo, retry=load_retry(repo / DEFAULT_CONFIG))
    print(json.dumps(dataclasses.asdict(result), default=str))
    return result.exit_code or int(task_failed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", action="append", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    args = parser.parse_args(argv)
    return settle_and_publish(
        repo=args.repo_root,
        dates=tuple(args.date),
        run_id=args.run_id,
        commit_sha=args.commit,
        config_root=args.config_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
