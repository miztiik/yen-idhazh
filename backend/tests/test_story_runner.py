"""Exercise real typed runner files, arithmetic vectors and imports without model inference."""

import json
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pytest
import yaml  # type: ignore[import-untyped]
from test_story_dataset import articles, manifest, policy
from test_story_encoder_candidates import registered_candidate

from idhazh.contracts.story_encoder_candidate import CandidateVectorState, CandidateVectorUnit
from idhazh.contracts.story_runner import RunnerFile, RunnerPackage, RunnerResult, RunnerShard
from idhazh.story_dataset.encoder_candidates import save_immutable
from idhazh.story_dataset.runner_archive import extract_archive
from idhazh.story_dataset.runner_download import download_release_asset
from idhazh.story_dataset.runner_execution import run_shard, save_unit
from idhazh.story_dataset.runner_inputs import (
    describe_committed_code,
    describe_file,
    validate_shard,
)
from idhazh.story_dataset.runner_results import import_result, recover_result, validate_result
from idhazh.story_dataset.storage import canonical, digest, file_hash, now, write_model

pytestmark = pytest.mark.contract


def runner_fixture(root: Path) -> tuple[RunnerShard, RunnerPackage, RunnerResult, Path]:
    candidate, _ = registered_candidate(root)
    source = manifest()
    source_policy = policy().model_copy(
        update={
            "expected_articles": source.articles,
            "expected_sha256": source.source_sha256,
            "expected_bytes": source.source_bytes,
        }
    )
    selected = list(articles().values())[:4]
    shard = RunnerShard(
        shard="fixture-000",
        source=source,
        policy=source_policy,
        parent_revision="2" * 64,
        candidate=candidate,
        articles=selected,
        ordered_ids_sha256=digest([a.article_id for a in selected]),
        prefixed_texts_sha256=digest([candidate.prefix + a.source.summary for a in selected]),
        dimensions=candidate.dimensions,
        model_files=[RunnerFile(path="config.json", sha256="3" * 64, bytes=2)],
    )
    package = RunnerPackage(
        prepared_at=now(),
        source_sha256=source.source_sha256,
        code_commit="4" * 40,
        files=[],
        shards={shard.shard: "shard.json"},
        code_files=[],
        runtime_lock=RunnerFile(path="runtime.txt", sha256="5" * 64, bytes=1),
        runtime_versions={"fixture": "generated-no-model-inference"},
    )
    output = root / "downloaded"
    ids = [a.article_id for a in selected]
    unit = save_unit(
        shard,
        ids,
        np.ones((len(ids), candidate.dimensions), dtype=np.float32),
        output,
        package.runtime_versions,
    )
    result = RunnerResult(
        shard_sha256=digest(shard),
        package_sha256=digest(package),
        shard=shard.shard,
        code_commit=package.code_commit,
        run_id="1",
        run_attempt="1",
        repository="fixture/private",
        started_at=now(),
        finished_at=now(),
        runtime_versions=package.runtime_versions,
        model_files=shard.model_files,
        host={"fixture": "not-an-actual-run"},
        units=[unit],
        pending_article_ids=[],
        state="complete",
        files=[
            describe_file(output / unit.cache.file, output),
            describe_file(output / "units" / (digest(ids) + ".json"), output),
        ],
    )
    write_model(output / "result.json", result)
    return shard, package, result, output


def test_typed_result_import_and_exact_replay(tmp_path: Path) -> None:
    shard, package, result, output = runner_fixture(tmp_path)
    validate_result(result, shard, package, output)
    assert shard.candidate is not None
    state = CandidateVectorState(
        candidate_revision=digest(shard.candidate), previous_revision=None, units=[]
    )
    save_immutable(tmp_path, "candidate-vector-states", state)
    pointer = tmp_path / "state.json"
    pointer.write_bytes(canonical(state))
    imported = import_result(result, shard, package, output, tmp_path, articles(), pointer)
    assert isinstance(imported, CandidateVectorState)
    assert len(imported.units) == 1
    replayed = import_result(result, shard, package, output, tmp_path, articles(), pointer)
    assert replayed == imported


def test_recover_complete_unit_before_manifest_update_without_inference(tmp_path: Path) -> None:
    shard, package, result, output = runner_fixture(tmp_path)
    partial = result.model_copy(update={
        "units": [], "files": [],
        "pending_article_ids": [a.article_id for a in shard.articles], "state": "partial",
    })
    (output / "result.json").write_bytes(canonical(partial))
    with pytest.raises(ValueError, match="unexpected"):
        validate_result(partial, shard, package, output)
    recovered = recover_result(shard, package, output)
    assert recovered.units == result.units
    assert recovered.state == "complete"
    assert recovered.resumed_from == digest(partial)
    validate_result(recovered, shard, package, output)
    assert read_result(output) == recovered


def read_result(output: Path) -> RunnerResult:
    return RunnerResult.model_validate_json((output / "result.json").read_bytes())


@pytest.mark.parametrize("tamper", ["nan", "descriptor", "runtime", "model-files", "extra"])
def test_recovery_never_accepts_unvalidated_orphans(tmp_path: Path, tamper: str) -> None:
    shard, package, result, output = runner_fixture(tmp_path)
    partial = result.model_copy(update={
        "units": [], "files": [],
        "pending_article_ids": [a.article_id for a in shard.articles], "state": "partial",
    })
    if tamper == "nan":
        matrix = np.full((4, shard.dimensions), np.nan, dtype=np.float32)
        np.save(output / result.units[0].cache.file, matrix)
    elif tamper == "descriptor":
        (output / "units" / (digest(result.units[0].article_ids) + ".json")).write_text("{}")
    elif tamper == "runtime":
        partial.runtime_versions = {"fixture": "wrong"}
    elif tamper == "model-files":
        partial.model_files = []
    else:
        (output / "unknown.json").write_text("{}")
    (output / "result.json").write_bytes(canonical(partial))
    with pytest.raises(ValueError):
        recover_result(shard, package, output)
    assert read_result(output) == partial


def test_recovery_preserves_incomplete_files_without_claiming_rows(tmp_path: Path) -> None:
    shard, package, result, output = runner_fixture(tmp_path)
    ids = result.units[0].article_ids
    (output / "units" / (digest(ids) + ".json")).unlink()
    (output / "result.json.part").write_bytes(b"incomplete-manifest")
    partial = result.model_copy(update={
        "units": [], "files": [], "pending_article_ids": ids, "state": "partial",
    })
    (output / "result.json").write_bytes(canonical(partial))
    recovered = recover_result(shard, package, output)
    assert recovered.units == []
    assert recovered.pending_article_ids == ids
    assert (output.with_name(output.name + "-incomplete") / result.units[0].cache.file).exists()
    validate_result(recovered, shard, package, output)


def test_code_preview_requires_exact_committed_lf_bytes(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / ".gitattributes").write_bytes(b"* text eol=lf\n")
    path = tmp_path / "runner.py"
    path.write_bytes(b"print('fixture')\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "runner.py", ".gitattributes"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=fixture", "-c",
         "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "Fixture"],
        check=True,
    )
    commit = subprocess.check_output(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True
    ).strip()
    assert describe_committed_code(tmp_path, commit, "runner.py").sha256 == file_hash(path)
    for raw in (b"print('fixture')\r\n", b"print('changed')\n"):
        path.write_bytes(raw)
        with pytest.raises(ValueError, match="committed LF"):
            describe_committed_code(tmp_path, commit, "runner.py")


@pytest.mark.parametrize("repository,identity,checksum", [
    ("wrong", "1", "f" * 64), ("fixture/repository", "not-a-number", "f" * 64),
    ("fixture/repository", "1", "wrong"),
])
def test_release_input_requires_exact_recipient_id_and_checksum(
    tmp_path: Path, repository: str, identity: str, checksum: str
) -> None:
    with pytest.raises(ValueError, match="exact repository"):
        download_release_asset(repository, identity, checksum, tmp_path / "not-downloaded")


@pytest.mark.parametrize(
    "tamper",
    [
        "source",
        "order",
        "prefix",
        "article-hash",
        "summary-hash",
        "model-pin",
        "runtime",
        "candidate-lineage",
        "pending",
        "file-hash",
        "shape",
        "dtype",
        "nan",
        "zero",
        "extra-file",
        "model-files",
        "dimension",
        "descriptor",
    ],
)
def test_result_refuses_changed_evidence_or_invalid_vectors(tmp_path: Path, tamper: str) -> None:
    shard, package, result, output = runner_fixture(tmp_path)
    unit = result.units[0]
    if tamper == "source":
        unit.source_sha256 = "f" * 64
    elif tamper == "order":
        unit.article_ids.reverse()
    elif tamper == "prefix":
        assert shard.candidate is not None
        shard.candidate.prefix = "different role: "
    elif tamper == "article-hash":
        unit.article_input_sha256[0] = "f" * 64
    elif tamper == "summary-hash":
        unit.summary_sha256[0] = "f" * 64
    elif tamper == "model-pin":
        unit.cache.revision = "b" * 40
    elif tamper == "runtime":
        result.runtime_versions = {"fixture": "different"}
    elif tamper == "candidate-lineage":
        assert isinstance(unit, CandidateVectorUnit)
        unit.candidate_revision = "f" * 64
    elif tamper == "pending":
        result.pending_article_ids = unit.article_ids[:1]
    elif tamper == "file-hash":
        unit.cache.file_sha256 = "f" * 64
    elif tamper == "extra-file":
        (output / "unexpected.json").write_text("{}")
    elif tamper == "model-files":
        result.model_files = []
    elif tamper == "dimension":
        unit.cache.dimensions += 1
    elif tamper == "descriptor":
        (output / "units" / (digest(unit.article_ids) + ".json")).write_text("{}")
    else:
        matrix = np.ones((len(unit.article_ids), shard.dimensions), dtype=np.float32)
        if tamper == "shape":
            matrix = matrix[:, :1]
        elif tamper == "dtype":
            matrix = matrix.astype(np.float64)
        elif tamper == "nan":
            matrix[0, 0] = np.nan
        else:
            matrix[0] = 0
        np.save(output / unit.cache.file, matrix)
        unit.cache.file_sha256 = file_hash(output / unit.cache.file)
    with pytest.raises(ValueError):
        validate_result(result, shard, package, output)


def test_inference_refuses_local_host_before_loading_any_model(tmp_path: Path) -> None:
    shard, package, _, _ = runner_fixture(tmp_path)
    with pytest.raises(ValueError, match="GitHub-runner-only"):
        run_shard(package, tmp_path, tmp_path, shard, tmp_path / "never-encoded", 300)
    assert not (tmp_path / "never-encoded").exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/absolute", "a\\b"])
def test_artifact_extraction_refuses_unsafe_paths(tmp_path: Path, name: str) -> None:
    path = tmp_path / "artifact.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        entry = zipfile.ZipInfo("entry")
        entry.filename = name
        bundle.writestr(entry, "{}")
    with pytest.raises(ValueError):
        extract_archive(path, file_hash(path), tmp_path / "extracted")


def test_artifact_hash_and_bounded_size(tmp_path: Path) -> None:
    path = tmp_path / "artifact.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("a.json", "{}")
    with pytest.raises(ValueError, match="hash"):
        extract_archive(path, "f" * 64, tmp_path / "wrong")
    with pytest.raises(ValueError, match="size"):
        extract_archive(path, file_hash(path), tmp_path / "too-big", max_bytes=1)
    extract_archive(path, file_hash(path), tmp_path / "valid")
    assert (tmp_path / "valid" / "a.json").read_text() == "{}"


def test_shard_full_evidence_and_unknown_control_rejection(tmp_path: Path) -> None:
    shard, _, _, _ = runner_fixture(tmp_path)
    validate_shard(shard)
    shard.articles[0].input_sha256 = "f" * 64
    with pytest.raises(ValueError, match="evidence"):
        validate_shard(shard)


def test_manual_workflow_has_no_publication_and_preserves_partial_units() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/story-archive-encoding.yml").read_text())
    trigger = workflow.get("on", workflow.get(True))
    assert set(trigger) == {"workflow_dispatch"}
    assert "runner_label" not in trigger["workflow_dispatch"]["inputs"]
    assert workflow["permissions"] == {"contents": "read", "actions": "read"}
    assert workflow["jobs"]["inputs"]["runs-on"] == "ubuntu-latest"
    assert workflow["jobs"]["encode"]["runs-on"] == "ubuntu-latest"
    assert workflow["jobs"]["encode"]["timeout-minutes"] == 360
    assert workflow["jobs"]["encode"]["strategy"]["max-parallel"] == 2
    steps = workflow["jobs"]["encode"]["steps"]
    assert steps[-1]["if"] == "always()"
    assert steps[-1]["with"]["retention-days"] == 90
    assert not any("push" in s.get("run", "") for s in steps)
    assert "require-hashes" in json.dumps(steps)
    assert "private" not in json.dumps(workflow)
