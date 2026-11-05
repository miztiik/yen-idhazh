"""How are only declared invocation files checked and transported between jobs?"""

from __future__ import annotations

import csv
import hashlib
import io
import shutil
from pathlib import Path

from pydantic import TypeAdapter

from idhazh import atomic_write
from idhazh.contracts.base import RelPath
from idhazh.contracts.council_invocation import (
    ArtifactFile,
    Cell,
    PreparationReceipt,
    Selection,
    ShardFiles,
)
from idhazh.contracts.council_run_record import CouncilRunRecord, EvaluationStep, ShardOutcome

_PATH = TypeAdapter(RelPath)


class FileIntegrityError(ValueError):
    """A fatal transport or ownership failure, never an ordinary plugin failure."""


def fatal(error: BaseException) -> bool:
    """Fatal members stay fatal even when work and recording failed together."""
    if isinstance(error, BaseExceptionGroup):
        return any(fatal(member) for member in error.exceptions)
    return not isinstance(error, Exception) or isinstance(error, (FileIntegrityError, TimeoutError))


def integrity_failure(error: BaseException) -> bool:
    if isinstance(error, BaseExceptionGroup):
        return any(integrity_failure(member) for member in error.exceptions)
    return isinstance(error, FileIntegrityError)


def invocation_root(root: Path, selected: Selection, judge_id: str) -> Path:
    if selected.trial(judge_id):
        return root / "trials" / selected.run_id / str(selected.attempt) / judge_id
    return root / "runs" / selected.run_id / str(selected.attempt)


def preparation_path(root: Path, selected: Selection, judge_id: str, day: str) -> Path:
    return (
        invocation_root(root, selected, judge_id) / day / "preparation" / judge_id / "receipt.json"
    )


def shard_path(
    root: Path,
    selected: Selection,
    judge_id: str,
    day: str,
    shard: int,
) -> Path:
    return invocation_root(root, selected, judge_id) / day / "reports" / judge_id / f"{shard}.json"


def downloaded_bundles(
    incoming: Path,
    selected: Selection,
    cells: tuple[Cell, ...] = (),
) -> dict[str, Path]:
    """Resolve flat singleton or named downloads using only expected invocation files."""
    if incoming.is_symlink() or (incoming.exists() and not incoming.is_dir()):
        raise FileIntegrityError("invalid artifact download root")
    expected = {
        f"council-selection-{selected.anchor_date}": (
            "events/planner.jsonl",
            *(
                preparation_path(Path(), selected, judge.tenant, day).as_posix()
                for judge in selected.judges
                for day in judge.dates
            ),
        ),
    }
    for cell in cells:
        expected[f"council-metrics-{cell.tenant}-{cell.date}-{cell.shard}"] = (
            shard_path(Path(), selected, cell.tenant, cell.date, cell.shard).as_posix(),
            record_path(Path(), selected, cell.tenant, cell.date, cell.shard).as_posix(),
            f"events/{cell.tenant}/{cell.date}/{cell.shard}.jsonl",
        )
    named: dict[str, Path] = {}
    flat: list[str] = []
    for name, markers in expected.items():
        target = incoming / name
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_dir():
                raise FileIntegrityError("invalid named artifact directory")
            named[name] = target
        present = tuple(
            marker
            for marker in markers
            if (incoming / marker).exists() or (incoming / marker).is_symlink()
        )
        for marker in present:
            checked_file(incoming, marker)
        if present:
            flat.append(name)
    if flat:
        if named or len(flat) != 1:
            raise FileIntegrityError("mixed or colliding artifact download layouts")
        return {flat[0]: incoming}
    return named


def checked_file(root: Path, relative: str) -> Path:
    """Refuse path aliases, symlinks and non-regular files before opening bytes."""
    try:
        _PATH.validate_python(relative, strict=True)
    except ValueError as error:
        raise FileIntegrityError("unsafe declared path") from error
    target = root / relative
    for path in (root, *target.relative_to(root).parents, target):
        candidate = path if path.is_absolute() else root / path
        if candidate.is_symlink():
            raise FileIntegrityError("symlink in declared file address")
    if not target.is_file():
        raise FileIntegrityError("declared file is missing or not regular")
    return target


def evidence(
    root: Path, names: tuple[str, ...], *, day: str, judge_id: str
) -> tuple[ArtifactFile, ...]:
    if len({Path(name) for name in names}) != len(names):
        raise FileIntegrityError("duplicate file destination")
    measured: list[ArtifactFile] = []
    for name in names:
        target = checked_file(root, name)
        parts = Path(name).parts
        offset = 1 if parts[0] == "scratch" else 0
        if (
            len(parts) < offset + 4
            or parts[offset] != day
            or parts[offset + 2] != judge_id
            or parts[offset + 1] in ("preparation", "reports", "outcomes")
        ):
            raise FileIntegrityError("file exceeds its judge/date namespace")
        data = target.read_bytes()
        measured.append(
            ArtifactFile(
                path=name,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    return tuple(measured)


def verify(root: Path, files: tuple[ArtifactFile, ...], *, day: str, judge_id: str) -> None:
    measured = evidence(root, tuple(file.path for file in files), day=day, judge_id=judge_id)
    if measured != files:
        raise FileIntegrityError("declared file bytes changed")


def identify(document: PreparationReceipt | ShardFiles, selected: Selection) -> None:
    try:
        if document.version != document.schema_version():
            raise ValueError("invocation files are not migrated")
        selected.identify(
            run_id=document.run_id,
            attempt=document.attempt,
            git_sha=document.git_sha,
        )
        judge = selected.judge(document.judge_id, document.date)
        if isinstance(document, ShardFiles) or document.state == "ready":
            if document.shards != judge.shards:
                raise ValueError("file width differs from selected width")
    except ValueError as error:
        raise FileIntegrityError("file declaration differs from selected invocation") from error


def read_preparation(
    root: Path,
    selected: Selection,
    judge_id: str,
    day: str,
) -> PreparationReceipt | None:
    target = preparation_path(root, selected, judge_id, day)
    if not target.exists() and not target.is_symlink():
        return None
    try:
        path = checked_file(root, target.relative_to(root).as_posix())
        receipt = PreparationReceipt.from_json(path.read_text(encoding="utf-8"))
        identify(receipt, selected)
        if (receipt.judge_id, receipt.date) != (judge_id, day):
            raise ValueError("receipt differs from its address")
        verify(invocation_root(root, selected, judge_id), receipt.files, day=day, judge_id=judge_id)
        return receipt
    except ValueError as error:
        raise FileIntegrityError("invalid preparation receipt") from error


def write_document(path: Path, document: PreparationReceipt | ShardFiles) -> None:
    check_destination(path)
    atomic_write.write_atomic(path, document.to_json())


def check_destination(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise FileIntegrityError("duplicate invocation destination")
    if any(parent.is_symlink() for parent in path.parents):
        raise FileIntegrityError("symlink in destination")


def export(
    root: Path,
    bundle: Path,
    selected: Selection,
    document: PreparationReceipt | ShardFiles,
) -> None:
    """Copy a named document and its validated files, never a scratch tree."""
    identify(document, selected)
    base = invocation_root(root, selected, document.judge_id)
    verify(base, document.files, day=document.date, judge_id=document.judge_id)
    manifest = (
        preparation_path(root, selected, document.judge_id, document.date)
        if isinstance(document, PreparationReceipt)
        else shard_path(root, selected, document.judge_id, document.date, document.shard)
    )
    sources = (manifest, *(base / file.path for file in document.files))
    for source in sources:
        target = bundle / source.relative_to(root)
        check_destination(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checked_file(root, source.relative_to(root).as_posix()), target)


def install(
    root: Path,
    bundle: Path,
    selected: Selection,
    document: PreparationReceipt | ShardFiles,
) -> None:
    """Verify every declared source and destination before installing any bytes."""
    identify(document, selected)
    incoming_base = invocation_root(bundle, selected, document.judge_id)
    verify(incoming_base, document.files, day=document.date, judge_id=document.judge_id)
    base = invocation_root(root, selected, document.judge_id)
    names = tuple(file.path for file in document.files)
    manifest = (
        preparation_path(root, selected, document.judge_id, document.date)
        if isinstance(document, PreparationReceipt)
        else shard_path(root, selected, document.judge_id, document.date, document.shard)
    )
    sources = (
        *((incoming_base / name, base / name) for name in names),
        (bundle / manifest.relative_to(root), manifest),
    )
    for source, target in sources:
        checked_file(bundle, source.relative_to(bundle).as_posix())
        check_destination(target)
    for source, target in sources:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def import_preparation(
    root: Path,
    bundle: Path,
    selected: Selection,
    judge_id: str,
    day: str,
) -> PreparationReceipt | None:
    receipt = read_preparation(bundle, selected, judge_id, day)
    if receipt is None:
        return None
    copy_record(root, bundle, selected, judge_id, day, None, prepared=receipt)
    install(root, bundle, selected, receipt)
    return receipt


def read_shard(
    root: Path,
    selected: Selection,
    judge_id: str,
    day: str,
    shard: int,
) -> ShardFiles | None:
    manifest = shard_path(root, selected, judge_id, day, shard)
    if not manifest.exists() and not manifest.is_symlink():
        return None
    try:
        checked_file(root, manifest.relative_to(root).as_posix())
        document = ShardFiles.from_json(manifest.read_text(encoding="utf-8"))
        if (document.judge_id, document.date, document.shard) != (judge_id, day, shard):
            raise ValueError("shard declaration differs from its address")
        identify(document, selected)
        verify(
            invocation_root(root, selected, judge_id),
            document.files,
            day=day,
            judge_id=judge_id,
        )
        return document
    except ValueError as error:
        raise FileIntegrityError("invalid shard file declaration") from error


def import_shard(
    root: Path,
    bundle: Path,
    selected: Selection,
    judge_id: str,
    day: str,
    shard: int,
) -> ShardFiles | None:
    document = read_shard(bundle, selected, judge_id, day, shard)
    if document is None:
        return None
    copy_record(root, bundle, selected, judge_id, day, shard)
    install(root, bundle, selected, document)
    return document


def record_path(
    root: Path,
    selected: Selection,
    name: str,
    day: str,
    shard: int | None,
) -> Path:
    base = invocation_root(root, selected, name)
    if selected.trial(name):
        base /= "scratch"
    unit = "select-judge-work" if shard is None else str(shard)
    return base / day / "outcomes" / name / f"{unit}.csv"


def copy_record(
    root: Path,
    bundle: Path,
    selected: Selection,
    name: str,
    day: str,
    shard: int | None,
    *,
    prepared: PreparationReceipt | None = None,
) -> None:
    """Validate a named native platform row before it enters the collecting tree."""
    source = record_path(bundle, selected, name, day, shard)
    if not source.exists() and not source.is_symlink():
        return
    target = record_path(root, selected, name, day, shard)
    try:
        checked_file(bundle, source.relative_to(bundle).as_posix())
        rows = list(csv.DictReader(io.StringIO(source.read_text(encoding="utf-8"))))
        if len(rows) != 1:
            raise ValueError("one unit must file one platform row")
        row = CouncilRunRecord.from_csv_row(rows[0])
        step = (
            EvaluationStep.SELECT_JUDGE_WORK if shard is None else EvaluationStep.EVALUATE_WORK_PART
        )
        if (row.run_id, row.judge_id, row.date, row.evaluation_step, row.work_part_index) != (
            selected.run_id,
            name,
            day,
            step,
            shard,
        ):
            raise ValueError("record differs from selected cell")
        judge = selected.judge(name, day)
        width = judge.shards if shard is not None else (prepared.shards if prepared else 0)
        if row.work_part_count != width:
            raise ValueError("record width differs from selected work")
        if (
            prepared is not None
            and row.outcome
            != {
                "ready": ShardOutcome.COMPLETED,
                "no_work": ShardOutcome.NOTHING_TO_DO,
                "failed": ShardOutcome.FAILED,
            }[prepared.state]
        ):
            raise ValueError("record differs from preparation")
        check_destination(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    except ValueError as error:
        raise FileIntegrityError("invalid platform record") from error


def copy_events(root: Path, bundle: Path, relative: str) -> None:
    """Copy one expected event file without merging unvalidated artifact paths."""
    source = bundle / "events" / relative
    if not source.exists() and not source.is_symlink():
        return
    checked_file(bundle, source.relative_to(bundle).as_posix())
    target = root / "events" / relative
    check_destination(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
