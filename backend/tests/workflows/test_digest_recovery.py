"""Can saved worker output complete real assembly and Git delivery without another worker?"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import pytest
from gardener._garden import an_origin, git, quiet_git
from pipeline._builders import article, plan, summary
from support.paths import CONFIG_DIR

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages import common
from utilities import digest_publish, digest_recover, publication_evidence
from utilities.digest_recovery_download import SourceRun, select_artifacts
from utilities.digest_recovery_inputs import plan_import, restore, unpack, worker_files
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, PublicationRequest
from utilities.publish_to_repo import Status

from ._harness import _copy_config

pytestmark = pytest.mark.workflow


def zipped(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return stream.getvalue()


def saved_inputs(root: Path, source: str) -> tuple[RunPlan, SourceRun, dict[str, bytes]]:
    saved = plan(item_count=2)
    counts = Counter(item.vertical for item in saved.items)
    saved = RunPlan.model_validate(
        {
            **saved.model_dump(),
            "shards": 2,
            "verticals": [
                {**vertical.model_dump(), "planned": counts[vertical.id]}
                for vertical in saved.verticals
            ],
        }
    )
    identity = WriterIdentity(
        run_id=saved.run_id,
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
        producer="stages.plan",
        git_sha=source,
    )
    paths = ledger.persist(
        root / "saved-state",
        [saved],
        ledger=LedgerName.RUN_PLAN,
        covers=saved.date,
        identity=identity,
    )
    archives = {
        "plan": zipped({path.name: path.read_bytes() for path in paths}),
        "items-0": zipped(
            {
                f"{saved.items[0].item_id}.article.json": article().to_json().encode(),
                f"{saved.items[0].item_id}.summary.json": summary().to_json().encode(),
            }
        ),
    }
    source_run = SourceRun(
        id=1,
        run_attempt=1,
        head_sha=source,
        path=".github/workflows/digest.yml",
        status="completed",
        conclusion="failure",
        run_started_at=saved.generated_at,
    )
    return saved, source_run, archives


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
    for name in ("idhazh_gardener.json",):
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
        path.startswith("state/raw/run-plan")
        for path in digest_publish.permissions(
            "assemble",
            date=saved.date,
        )
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


@pytest.mark.parametrize(
    "failure", ["missing-plan", "missing-items", "corrupt", "run", "sha", "extra"]
)
def test_bad_saved_inputs_refuse_before_restoring_anything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    _, repo = an_origin(tmp_path, {"seed": "seed\n"})
    source = git(repo, "rev-parse", "HEAD").strip()
    saved, _, archives = saved_inputs(tmp_path, source)
    execution = "1"
    if failure == "missing-plan":
        archives.pop("plan")
    elif failure == "missing-items":
        archives.pop("items-0")
    elif failure == "corrupt":
        archives["items-0"] = zipped({f"{saved.items[0].item_id}.article.json": b"{}"})
    elif failure == "run":
        execution = "3"
    elif failure == "sha":
        source = "b" * 40
    elif failure == "extra":
        archives["items-0"] = zipped({"foreign.summary.json": b"{}"})
    scratch = tmp_path / "restore"
    scratch.mkdir()
    with pytest.raises((IntegrityError, ValueError)):
        restore(
            repo,
            scratch,
            archives,
            execution=execution,
            attempt=1,
            commit=source,
            failed_shards=frozenset({1}),
        )
    assert not (repo / "state").exists()
    assert not (repo / "backend").exists()


def test_restore_does_not_replace_foreign_local_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    _, repo = an_origin(tmp_path, {"seed": "seed\n"})
    source = git(repo, "rev-parse", "HEAD").strip()
    saved, _, archives = saved_inputs(tmp_path, source)
    target = repo / "backend" / "var" / "run" / saved.date / "items"
    target.mkdir(parents=True)
    foreign = target / f"{saved.items[0].item_id}.article.json"
    foreign.write_text("foreign")
    scratch = tmp_path / "restore"
    scratch.mkdir()
    with pytest.raises(IntegrityError, match="foreign local"):
        restore(
            repo,
            scratch,
            archives,
            execution="1",
            attempt=1,
            commit=source,
            failed_shards=frozenset({1}),
        )
    assert foreign.read_text() == "foreign"
    assert not (repo / "state").exists()


@pytest.mark.parametrize("name", ["../escape", "folder/file.json", "C:escape", "folder\\escape"])
def test_artifact_paths_are_not_trusted(name: str) -> None:
    with pytest.raises(IntegrityError, match="unsafe"):
        unpack(zipped({name: b"untrusted"}))


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


def test_wrong_item_and_missing_successful_shard_refuse() -> None:
    saved = plan(item_count=2).model_copy(update={"shards": 2})
    with pytest.raises(IntegrityError, match="successful worker"):
        worker_files(saved, {})
    archive = zipped({f"{saved.items[1].item_id}.article.json": article().to_json().encode()})
    with pytest.raises(IntegrityError, match="unplanned"):
        worker_files(saved, {"items-0": archive})


def test_unreadable_zip_is_an_explicit_integrity_refusal() -> None:
    with pytest.raises(IntegrityError, match="readable ZIP"):
        unpack(b"not a ZIP")


def test_recovery_routes_through_gates_before_delivery_and_rebuilds_afterward() -> None:
    import ast
    import inspect

    function = ast.parse(inspect.getsource(digest_recover.main))
    calls = [
        (node.lineno, ast.unparse(node.func))
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
    ]
    names = [name for _, name in sorted(calls)]
    assert names.index("assemble_outputs") < names.index("check_outputs")
    assert names.index("check_outputs") < names.index("publish_outputs")
    assert names.index("publish_outputs") < names.index("digest_publish.published_inputs")
    assert names.index("digest_publish.published_inputs") < names.index("build_site")
    assert names.index("build_site") < names.index("npm")
    gate = inspect.getsource(digest_recover.check_outputs)
    assert '"check-publication"' in gate
    assert '"site-weight", "published-columns"' in gate
    assert "check=True" in gate


@pytest.mark.parametrize("change", ["expired", "attempt", "run", "commit", "duplicate", "digest"])
def test_platform_artifacts_must_match_the_source_attempt(change: str) -> None:
    source = SourceRun(
        id=1,
        run_attempt=2,
        head_sha="a" * 40,
        path=".github/workflows/digest.yml",
        status="completed",
        conclusion="failure",
        run_started_at="2026-10-31T01:00:00Z",
    )
    artifact: dict[str, object] = {
        "id": 4,
        "name": "plan",
        "expired": False,
        "created_at": "2026-10-31T02:00:00Z",
        "digest": f"sha256:{hashlib.sha256(b'archive').hexdigest()}",
        "workflow_run": {"id": 1, "head_sha": "a" * 40},
    }
    if change == "expired":
        artifact["expired"] = True
    elif change == "attempt":
        artifact["created_at"] = "2026-10-30T02:00:00Z"
    elif change == "run":
        artifact["workflow_run"] = {"id": 2, "head_sha": "a" * 40}
    elif change == "commit":
        artifact["workflow_run"] = {"id": 1, "head_sha": "b" * 40}
    elif change == "digest":
        artifact["digest"] = ""
    values = [artifact, artifact] if change == "duplicate" else [artifact]
    with pytest.raises(IntegrityError):
        select_artifacts(source, values)
    assert json.loads(source.model_dump_json())["run_attempt"] == 2
