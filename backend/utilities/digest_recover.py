"""How can a retained source run finish assembly without executing its workers again?"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import completed_writes, config, run_context
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages.assemble import stage_assemble
from idhazh.stages.harvest import stage_harvest
from utilities import digest_publish, publication_evidence
from utilities.digest_recovery_download import SourceRun, download
from utilities.digest_recovery_inputs import RestoredInputs, plan_import, restore
from utilities.publication_git import Repository
from utilities.publish_to_repo import PublicationResult

LOG = logging.getLogger(__name__)


def assemble_outputs(
    repo: Path,
    plan: RunPlan,
    *,
    source: SourceRun,
    identity: WriterIdentity,
    settings: config.Settings,
) -> None:
    """Keep content provenance on its source run; identify new writes as recovery execution."""
    with completed_writes.collect() as writes:
        try:
            stage_assemble(
                plan,
                settings=settings,
                commit_sha=source.head_sha,
                runner="ubuntu-latest" if os.environ.get("GITHUB_ACTIONS") == "true" else "local",
                writer_identity=identity,
                reuse_fragment=True,
            )
        finally:
            publication_evidence.save(repo, identity, "assemble", writes)
    with completed_writes.collect() as harvested:
        try:
            stage_harvest(plan.date, settings=settings, corpus_dir=repo / "corpus")
        except (OSError, ValueError) as error:
            # Corpus harvesting is optional on the normal publication path too.
            LOG.error("recovery corpus harvest failed: %s", error)
        finally:
            publication_evidence.save(repo, identity, "harvest", harvested)


def check_outputs(repo: Path, date: str) -> None:
    """Run the normal mandatory precommit gates over the actual assembled day and site."""
    subprocess.run(
        [sys.executable, "-m", "idhazh", "check-publication", "--day", date],
        cwd=repo,
        check=True,
    )
    build_site(repo)
    for gate in ("site-weight", "published-columns"):
        subprocess.run(
            [sys.executable, "-m", "idhazh", gate, "--site-tree", "build"],
            cwd=repo / "frontend",
            check=True,
        )


def npm(repo: Path, script: str) -> None:
    executable = shutil.which("npm")
    if executable is None:
        raise FileNotFoundError("npm is required for recovery publication checks")
    subprocess.run([executable, "run", script], cwd=repo / "frontend", check=True)


def build_site(repo: Path) -> None:
    npm(repo, "build")


def publish_outputs(
    repo: Path,
    restored: RestoredInputs,
    *,
    source: SourceRun,
    identity: WriterIdentity,
) -> PublicationResult:
    """Add independent, exact original-plan import authority to the normal assemble request."""
    request = digest_publish.request_for(
        repo=repo,
        identity=identity,
        date=restored.plan.date,
        source_plan=restored.plan,
        source_commit=source.head_sha,
    )
    original_plan = plan_import(
        repo,
        restored,
        execution=str(source.id),
        attempt=source.run_attempt,
        commit=source.head_sha,
        baseline=request.source_tip,
    )
    request = dataclasses.replace(
        request,
        write_permissions=(*request.write_permissions, restored.plan_path),
        writes={**request.writes, restored.plan_path: original_plan},
    )
    return digest_publish.deliver(repo, request)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_run", help="Completed Content refresh run ID; latest attempt only")
    parser.add_argument("--execution", default=os.environ.get("GITHUB_RUN_ID"), required=False)
    parser.add_argument("--attempt", type=int, default=run_context.run_attempt())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--restore-only",
        action="store_true",
        help="Validate and restore; do not assemble",
    )
    mode.add_argument("--check-only", action="store_true", help="Assemble and check; do not commit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    repo = Path.cwd()
    try:
        if repo.resolve() != config.REPO_ROOT.resolve():
            raise ValueError("run recovery from its own repository root")
        source, archives, failed = download(args.source_run)
        (repo / "backend" / "var").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=repo / "backend" / "var") as temporary:
            restored = restore(
                repo,
                Path(temporary),
                archives,
                execution=args.source_run,
                attempt=source.run_attempt,
                commit=source.head_sha,
                failed_shards=failed,
            )
        plan = restored.plan
        print(
            json.dumps(
                {
                    "source_run": source.id,
                    "source_attempt": source.run_attempt,
                    "source_commit": source.head_sha,
                    "date": plan.date,
                    "failed_source_shards": sorted(failed),
                }
            )
        )
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with Path(output).open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(f"date={plan.date}\n")
        if args.restore_only:
            return 0
        if not args.execution or args.execution == args.source_run:
            raise ValueError("recovery requires a new, distinct execution ID")
        identity = WriterIdentity(
            run_id=f"{plan.date}-{args.execution}",
            attempt=args.attempt,
            job=ServerJob.ASSEMBLE,
            shard=0,
            producer="utilities.digest_recover",
            git_sha=Repository(repo).git("rev-parse", "HEAD").strip(),
        )
        print(identity.model_dump_json())
        settings = config.load()
        assemble_outputs(repo, plan, source=source, identity=identity, settings=settings)
        check_outputs(repo, plan.date)
        if args.check_only:
            return 0
        result = publish_outputs(
            repo,
            restored,
            source=source,
            identity=identity,
        )
        if result.exit_code:
            return result.exit_code
        tip = result.observed_tip or result.candidate
        if tip is None:
            raise RuntimeError("successful recovery returned no published input revision")
        # Receipts identify this recovery, not the source worker execution.
        digest_publish.published_inputs(
            repo,
            tip,
            date=plan.date,
            settings=settings,
            identity=identity,
        )
        build_site(repo)
        npm(repo, "bundle-gate")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        LOG.error("assembly recovery refused: %s", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
