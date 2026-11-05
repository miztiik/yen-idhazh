"""Can declared opaque work cross runners without admitting foreign or changed bytes?"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from idhazh.contracts.council_invocation import (
    PreparationReceipt,
    SelectedJudge,
    Selection,
    ShardFiles,
)
from idhazh.contracts.knobs.council import JudgeLifecycleStatus
from idhazh.council import work_files

DAY = "2026-11-04"
NAME = "paper-judge"


def selection() -> Selection:
    return Selection(
        version=Selection.schema_version(),
        run_id="2026-11-05-1",
        attempt=1,
        git_sha="a" * 40,
        mode="manual",
        anchor_date=DAY,
        window=(DAY,),
        judges=(
            SelectedJudge(
                tenant=NAME,
                status=JudgeLifecycleStatus.ACTIVE,
                dates=(DAY,),
                shards=1,
            ),
        ),
    )


def prepared(root: Path, selected: Selection) -> PreparationReceipt:
    base = work_files.invocation_root(root, selected, NAME)
    task = base / DAY / "tasks" / NAME / "task.json"
    task.parent.mkdir(parents=True)
    task.write_text("{}", encoding="ascii")
    receipt = PreparationReceipt(
        version=PreparationReceipt.schema_version(),
        run_id=selected.run_id,
        attempt=selected.attempt,
        git_sha=selected.git_sha,
        judge_id=NAME,
        date=DAY,
        state="ready",
        shards=1,
        files=work_files.evidence(base, (f"{DAY}/tasks/{NAME}/task.json",), day=DAY, judge_id=NAME),
    )
    work_files.write_document(work_files.preparation_path(root, selected, NAME, DAY), receipt)
    return receipt


def test_opaque_named_file_round_trips_between_isolated_roots(tmp_path: Path) -> None:
    selected = selection()
    receipt = prepared(tmp_path / "planner", selected)
    bundle = tmp_path / "bundle"
    work_files.export(tmp_path / "planner", bundle, selected, receipt)
    landed = work_files.import_preparation(tmp_path / "worker", bundle, selected, NAME, DAY)
    assert landed == receipt
    target = work_files.invocation_root(tmp_path / "worker", selected, NAME)
    assert (target / DAY / "tasks" / NAME / "task.json").read_text(encoding="ascii") == "{}"


@pytest.mark.parametrize("change", ["run", "attempt", "revision", "width", "bytes", "missing"])
def test_foreign_or_changed_preparation_is_refused_before_install(
    tmp_path: Path,
    change: str,
) -> None:
    selected = selection()
    receipt = prepared(tmp_path / "planner", selected)
    bundle = tmp_path / "bundle"
    work_files.export(tmp_path / "planner", bundle, selected, receipt)
    path = work_files.preparation_path(bundle, selected, NAME, DAY)
    base = work_files.invocation_root(bundle, selected, NAME)
    task = base / receipt.files[0].path
    updates: dict[str, dict[str, Any]] = {
        "run": {"run_id": "2026-11-05-2"},
        "attempt": {"attempt": 2},
        "revision": {"git_sha": "b" * 40},
        "width": {"shards": 2},
    }
    if change in updates:
        path.write_text(receipt.model_copy(update=updates[change]).to_json(), encoding="ascii")
    elif change == "bytes":
        task.write_text('{"changed":true}', encoding="ascii")
    else:
        task.unlink()
    with pytest.raises(work_files.FileIntegrityError):
        work_files.import_preparation(tmp_path / "worker", bundle, selected, NAME, DAY)
    assert not work_files.preparation_path(tmp_path / "worker", selected, NAME, DAY).exists()


def test_destination_collisions_and_cross_judge_files_are_refused(tmp_path: Path) -> None:
    selected = selection()
    receipt = prepared(tmp_path / "planner", selected)
    base = work_files.invocation_root(tmp_path / "planner", selected, NAME)
    with pytest.raises(work_files.FileIntegrityError, match="duplicate"):
        work_files.evidence(base, (receipt.files[0].path,) * 2, day=DAY, judge_id=NAME)
    with pytest.raises(work_files.FileIntegrityError):
        work_files.evidence(base, (receipt.files[0].path,), day=DAY, judge_id="other-judge")
    bundle = tmp_path / "bundle"
    work_files.export(tmp_path / "planner", bundle, selected, receipt)
    work_files.import_preparation(tmp_path / "worker", bundle, selected, NAME, DAY)
    with pytest.raises(work_files.FileIntegrityError, match="duplicate"):
        work_files.import_preparation(tmp_path / "worker", bundle, selected, NAME, DAY)


def test_symlink_is_refused_without_reading_its_target(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="ascii")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("host cannot create file symlinks")
    with pytest.raises(work_files.FileIntegrityError, match="symlink"):
        work_files.checked_file(tmp_path, "link.json")


def test_shard_declaration_cannot_overwrite_an_installed_file(tmp_path: Path) -> None:
    selected = selection()
    receipt = prepared(tmp_path / "worker", selected)
    document = ShardFiles(
        version=ShardFiles.schema_version(),
        run_id=selected.run_id,
        attempt=1,
        git_sha=selected.git_sha,
        judge_id=NAME,
        date=DAY,
        shard=0,
        shards=1,
        files=receipt.files,
    )
    work_files.write_document(
        work_files.shard_path(tmp_path / "worker", selected, NAME, DAY, 0),
        document,
    )
    work_files.export(tmp_path / "worker", tmp_path / "bundle", selected, document)
    prepared(tmp_path / "collector", selected)
    with pytest.raises(work_files.FileIntegrityError):
        work_files.import_shard(tmp_path / "collector", tmp_path / "bundle", selected, NAME, DAY, 0)


def test_fatal_exception_group_members_are_not_contained() -> None:
    assert work_files.fatal(
        ExceptionGroup(
            "recording also failed",
            [ValueError(), work_files.FileIntegrityError()],
        )
    )
    assert work_files.fatal(BaseExceptionGroup("cancelled", [KeyboardInterrupt(), ValueError()]))
    assert work_files.fatal(TimeoutError())
    assert not work_files.fatal(ExceptionGroup("ordinary", [ValueError(), OSError()]))


def test_present_local_shard_files_are_rechecked_before_collection(tmp_path: Path) -> None:
    selected = selection()
    root = tmp_path / "worker"
    base = work_files.invocation_root(root, selected, NAME)
    relative = f"{DAY}/results/{NAME}/result.json"
    result = base / relative
    result.parent.mkdir(parents=True)
    result.write_text("{}", encoding="ascii")
    document = ShardFiles(
        version=ShardFiles.schema_version(),
        run_id=selected.run_id,
        attempt=selected.attempt,
        git_sha=selected.git_sha,
        judge_id=NAME,
        date=DAY,
        shard=0,
        shards=1,
        files=work_files.evidence(base, (relative,), day=DAY, judge_id=NAME),
    )
    work_files.write_document(work_files.shard_path(root, selected, NAME, DAY, 0), document)
    assert work_files.read_shard(root, selected, NAME, DAY, 0) == document
    result.write_text('{"changed":true}', encoding="ascii")
    with pytest.raises(work_files.FileIntegrityError):
        work_files.read_shard(root, selected, NAME, DAY, 0)
