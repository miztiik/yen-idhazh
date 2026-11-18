"""Can saved worker output complete real assembly and Git delivery without another worker?"""

from __future__ import annotations

from pathlib import Path

import pytest
from gardener._garden import an_origin, git, quiet_git
from support.paths import CONFIG_DIR

from idhazh import config
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.contracts.run_manifest import RunManifest
from idhazh.stages import common
from utilities import digest_publish, digest_recover, publication_evidence
from utilities.digest_recovery_inputs import plan_import, restore
from utilities.publication_git import Repository
from utilities.publication_request import PublicationRequest, contains
from utilities.publish_to_repo import Status

from ._harness import _copy_config
from ._recovery_inputs import saved_inputs

pytestmark = pytest.mark.workflow


def test_real_partial_assembly_and_delivery_keep_source_and_writer_separate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            "frontend/public/publication.json": PublicationInventory(
                version=PublicationInventory.schema_version(),
                dates=[],
            ).to_json(),
        },
    )
    _copy_config(repo / "config")
    for name in ("gardener/config/idhazh_gardener.json",):
        (repo / "config" / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / "config" / name).write_bytes((CONFIG_DIR / name).read_bytes())
    git(repo, "add", "config")
    git(repo, "commit", "--quiet", "-m", "fixture config")
    git(repo, "push", "--quiet", "origin", "main")
    source_commit = git(repo, "rev-parse", "HEAD").strip()
    saved, source_run, archives = saved_inputs(tmp_path, source_commit)
    (repo / "current-code").write_text("recovery code\n")
    git(repo, "add", "current-code")
    git(repo, "commit", "--quiet", "-m", "current recovery code")
    current_commit = git(repo, "rev-parse", "HEAD").strip()
    scratch = tmp_path / "restore"
    scratch.mkdir()
    restored = restore(
        repo,
        scratch,
        archives,
        execution="1",
        attempt=1,
        commit=source_commit,
        failed_shards=frozenset({1}),
    )
    assert restored.plan == saved
    # Restoring again is safe only when every retained byte is unchanged.
    assert (
        restore(
            repo,
            scratch,
            archives,
            execution="1",
            attempt=1,
            commit=source_commit,
            failed_shards=frozenset({1}),
        )
        == restored
    )
    monkeypatch.setattr(config, "REPO_ROOT", repo)
    monkeypatch.setattr(common, "VAR_ROOT", repo / "backend" / "var" / "run")
    monkeypatch.setattr(common, "STATE_ROOT", repo / "state")
    monkeypatch.setattr(common, "PUBLIC_ROOT", repo / "frontend" / "public" / "digest")
    settings = config.load(repo / "config")
    identity = WriterIdentity(
        run_id=f"{saved.date}-99",
        attempt=2,
        job=ServerJob.ASSEMBLE,
        shard=0,
        producer="utilities.digest_recover",
        git_sha=current_commit,
    )
    digest_recover.assemble_outputs(
        repo,
        restored.plan,
        source=source_run,
        identity=identity,
        settings=settings,
    )
    manifest_path = f"frontend/public/digest/{saved.date.replace('-', '/')}/run.json"
    manifest = RunManifest.read(repo / manifest_path)
    record = next(run for run in manifest.runs if run.run_id == saved.run_id)
    assert record.commit_sha == source_commit
    assert record.items_succeeded == 1
    assert record.items_failed == 1
    assert record.shards == 2
    # A gate failure before delivery leaves a local fragment; retry must carry it into preparation.
    digest_recover.assemble_outputs(
        repo,
        restored.plan,
        source=source_run,
        identity=identity,
        settings=settings,
    )
    hashes = publication_evidence.read(repo, identity, digest_publish.VERBS["assemble"])
    assert hashes
    publication_evidence.identified(repo, identity, hashes)
    result = digest_recover.publish_outputs(
        repo,
        restored,
        source=source_run,
        identity=identity,
    )
    assert result.status is Status.LANDED, result
    remote = Repository(origin, git_dir=origin)
    original_plan = remote.entry("main", restored.plan_path)
    assert original_plan is not None
    assert remote.blob(original_plan.oid) == (repo / restored.plan_path).read_bytes()
    assert not any(
        contains(scope, restored.plan_path)
        for scope in digest_publish.permissions("assemble", date=saved.date)
    ), "normal assembly authority must not expand to planning"
    entry = remote.entry("main", manifest_path)
    assert entry is not None
    published = RunManifest.model_validate_json(remote.blob(entry.oid))
    assert (
        next(run for run in published.runs if run.run_id == saved.run_id).commit_sha
        == source_commit
    )
    # A retry observes assembly again; stale pre-preparation receipts are not reused.
    digest_recover.assemble_outputs(
        repo,
        restored.plan,
        source=source_run,
        identity=identity,
        settings=settings,
    )
    repeated = digest_recover.publish_outputs(
        repo,
        restored,
        source=source_run,
        identity=identity,
    )
    assert repeated.exit_code == 0, repeated
    assert git(repo, "rev-parse", "HEAD").strip() == current_commit
    assert not (
        repo
        / "backend"
        / "var"
        / "run"
        / saved.date
        / "items"
        / f"{saved.items[1].item_id}.article.json"
    ).exists()


def test_original_plan_import_refuses_a_newer_conflicting_committed_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            "config/push-retry.json": (CONFIG_DIR / "push-retry.json").read_text(),
        },
    )
    source = git(repo, "rev-parse", "HEAD").strip()
    _, source_run, archives = saved_inputs(tmp_path, source)
    scratch = tmp_path / "restore"
    scratch.mkdir()
    restored = restore(
        repo,
        scratch,
        archives,
        execution="1",
        attempt=1,
        commit=source,
        failed_shards=frozenset({1}),
    )
    original = plan_import(
        repo,
        restored,
        execution="1",
        attempt=1,
        commit=source,
        baseline=source,
    )
    rival = tmp_path / "rival"
    git(tmp_path, "clone", "--quiet", str(origin), str(rival))
    target = rival / restored.plan_path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"foreign committed bytes\n")
    git(rival, "add", restored.plan_path)
    git(rival, "commit", "--quiet", "-m", "conflicting source plan")
    git(rival, "push", "--quiet", "origin", "main")
    request = PublicationRequest(
        WriterIdentity(
            run_id=f"{restored.plan.date}-99",
            attempt=1,
            job=ServerJob.ASSEMBLE,
            shard=0,
            producer="utilities.digest_recover",
            git_sha=source_run.head_sha,
        ),
        "recover source plan",
        source,
        (restored.plan_path,),
        (),
        {restored.plan_path: original},
    )
    result = digest_publish.deliver(repo, request)
    assert result.status is Status.INTEGRITY_REFUSED, result
    assert result.push_count == 0
    remote = Repository(origin, git_dir=origin)
    entry = remote.entry("main", restored.plan_path)
    assert entry is not None and remote.blob(entry.oid) == b"foreign committed bytes\n"
