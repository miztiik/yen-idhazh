"""Pass one named planner period to the TypeScript ledger owner."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal

from idhazh import config
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths

MaintenancePeriod = Literal["daily", "monthly", "yearly"]
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_REFUSALS: Final = frozenset({
    "missing-local-member",
    "changed-member",
    "malformed-member",
    "unsupported-member",
    "revision-changed",
    "target-conflict",
})
_WRITER_DIRECTORY: Final = Path(__file__).resolve().parents[3] / "packages" / "ledger-file-writer"
_WRITER_CLI: Final = _WRITER_DIRECTORY / "src" / "planner-maintenance-cli.ts"


class PlannerMaintenanceRefusalError(ValueError):
    """A named planner period the TypeScript writer could not safely replace."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class PlannerPeriodResult:
    """Verified compact bytes and exact source paths for the gardener to schedule."""

    status: Literal["written", "empty", "unchanged"]
    target_path: Path | None = None
    data: bytes | None = None
    file_sha256: str | None = None
    input_paths: tuple[Path, ...] = ()
    delete_paths: tuple[Path, ...] = ()
    row_count: int = 0
    carried_over: bool = False
    reason: str | None = None


def _relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError("planner maintenance receipt contains an invalid relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("planner maintenance receipt contains an invalid relative path")
    if path.as_posix() != value:
        raise ValueError("planner maintenance receipt contains a noncanonical relative path")
    return value


def _sha256(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("planner maintenance receipt contains an invalid digest")
    return value


def _receipt_base(
    value: object, *, ledger: LedgerName, period: MaintenancePeriod, covers: str
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("planner maintenance adapter returned no result object")
    if (
        not isinstance(value.get("version"), str)
        or not isinstance(value.get("revision"), str)
        or value.get("ledger") != ledger.value
        or value.get("period") != period
        or value.get("covers") != covers
    ):
        raise ValueError("planner maintenance adapter returned a mismatched result")
    return value


def _stage_directory(repository: Path) -> tuple[str, Path, tuple[int, int]]:
    for _attempt in range(8):
        name = f".planner-maintenance-{uuid.uuid4().hex}"
        path = repository / name
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            continue
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise RuntimeError("planner maintenance staging path is not a directory")
        return name, path, (info.st_dev, info.st_ino)
    raise RuntimeError("could not reserve a unique planner maintenance staging directory")


def _remove_stage(path: Path, owner: tuple[int, int]) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (info.st_dev, info.st_ino) != owner
    ):
        raise RuntimeError("planner maintenance staging directory changed before cleanup")
    shutil.rmtree(path)


def _git_revision(repository: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ | {"GIT_NO_LAZY_FETCH": "1"},
    )
    revision = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("planner maintenance requires one full Git revision")
    return revision


def _registered_request(ledger: LedgerName) -> tuple[dict[str, Any], dict[str, Any]]:
    entry = paths.entry(ledger)
    family = paths.family_of(ledger)
    app_config = AppConfig.from_json(
        (config.DEFAULT_CONFIG_DIR / "idhazh.json").read_text(encoding="utf-8")
    )
    configured_settings = app_config.ledger.model_dump(mode="json")
    if configured_settings.get("format") != Format.PARQUET.value:
        raise ValueError("planner maintenance requires the configured Parquet format")
    settings = {
        key: configured_settings[key]
        for key in ("format", "compression_raw", "compression_compact")
    }
    return (
        {
            "name": ledger.value,
            "family": family.name,
            "grain": entry.grain.value,
            "lifecycle_status": family.lifecycle_status.value,
            "prefix": list(entry.prefix),
        },
        settings,
    )


def _checked_source_paths(
    value: object,
    *,
    repository: Path,
    ledger: LedgerName,
    prefix: tuple[str, ...],
    period: MaintenancePeriod,
    covers: str,
) -> tuple[list[dict[str, Any]], list[Path]]:
    if not isinstance(value, list):
        raise ValueError("planner maintenance receipt has no input file list")
    raw_root = PurePosixPath("state/raw", *prefix)
    days = _period_days(period, covers)
    compact_members: dict[str, tuple[Period, str]] = {}
    for day in days:
        for compact_period in Period:
            compact_covers = (
                day[:4]
                if compact_period is Period.YEARLY
                else day[:7]
                if compact_period is Period.MONTHLY
                else day
            )
            path = paths.compact_path(
                repository / "state",
                ledger,
                compact_period,
                compact_covers,
                fmt=Format.PARQUET,
            ).relative_to(repository).as_posix()
            compact_members[path] = (compact_period, compact_covers)
    sources: list[dict[str, Any]] = []
    local_paths: list[Path] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("planner maintenance receipt contains an invalid input file")
        path = _relative_path(item.get("path"))
        parts = PurePosixPath(path).parts
        if path in seen:
            raise ValueError("planner maintenance receipt names an unregistered input file")
        raw_day: str | None = None
        if (
            len(parts) == len(raw_root.parts) + 4
            and PurePosixPath(*parts[: len(raw_root.parts)]) == raw_root
        ):
            raw_day = f"{parts[-4]}-{parts[-3]}-{parts[-2]}"
            try:
                valid_day = date.fromisoformat(raw_day).isoformat() == raw_day
            except ValueError:
                valid_day = False
            if (
                not valid_day
                or raw_day not in days
                or re.fullmatch(
                    r"[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.parquet",
                    parts[-1],
                )
                is None
                or item.get("tier") != "raw"
                or item.get("period") is not None
                or item.get("covers") != raw_day
            ):
                raise ValueError("planner maintenance receipt names an invalid raw input")
        elif path in compact_members:
            compact_period, compact_covers = compact_members[path]
            if (
                item.get("tier") != "compact"
                or item.get("period") != compact_period.value
                or item.get("covers") != compact_covers
            ):
                raise ValueError("planner maintenance receipt names an invalid compact input")
        else:
            raise ValueError("planner maintenance receipt names an unregistered input file")
        if type(item.get("bytes")) is not int or item["bytes"] < 1:
            raise ValueError("planner maintenance receipt contains an invalid input size")
        digest = _sha256(item.get("file_sha256"))
        local = repository.joinpath(*PurePosixPath(path).parts)
        data = _read_regular_beneath(
            repository,
            path,
            missing_reason="missing-local-member",
            malformed_reason="malformed-member",
        )
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != digest:
            raise PlannerMaintenanceRefusalError("changed-member")
        seen.add(path)
        sources.append(item)
        local_paths.append(local)
    return sources, local_paths


def _read_regular_beneath(
    root: Path,
    relative: str,
    *,
    missing_reason: str,
    malformed_reason: str,
) -> bytes:
    """Read one regular file whose path and every parent remain beneath a named root."""
    parts = PurePosixPath(_relative_path(relative)).parts
    current = root.resolve(strict=True)
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError as missing:
            raise PlannerMaintenanceRefusalError(missing_reason) from missing
        final = index == len(parts) - 1
        if stat.S_ISLNK(info.st_mode) or (
            final and not stat.S_ISREG(info.st_mode)
        ) or (not final and not stat.S_ISDIR(info.st_mode)):
            raise PlannerMaintenanceRefusalError(malformed_reason)
    return current.read_bytes()


def _period_days(period: MaintenancePeriod, covers: str) -> list[str]:
    """The UTC days one requested period may name, in ascending order."""
    if period == "daily":
        first = date.fromisoformat(covers)
        if first.isoformat() != covers:
            raise ValueError("planner maintenance day is not canonical")
        return [covers]
    if period == "monthly":
        first = date.fromisoformat(f"{covers}-01")
        if first.strftime("%Y-%m") != covers:
            raise ValueError("planner maintenance month is not canonical")
        after = (
            date(first.year + 1, 1, 1)
            if first.month == 12
            else date(first.year, first.month + 1, 1)
        )
    else:
        first = date.fromisoformat(f"{covers}-01-01")
        if first.strftime("%Y") != covers:
            raise ValueError("planner maintenance year is not canonical")
        after = date(first.year + 1, 1, 1)
    return [
        (first + timedelta(days=offset)).isoformat()
        for offset in range((after - first).days)
    ]


def maintain_period(
    repository: Path,
    ledger: LedgerName,
    period: MaintenancePeriod,
    covers: str,
    *,
    max_raw_files_per_period: int,
) -> PlannerPeriodResult:
    """Validate a TypeScript receipt and return only verified bytes and exact paths."""
    if max_raw_files_per_period < 1:
        raise ValueError("planner maintenance raw-file limit must be positive")
    repository = repository.resolve()
    registration, settings = _registered_request(ledger)
    stage_name, stage_path, owner = _stage_directory(repository)
    try:
        request = {
            "revision": _git_revision(repository),
            "staging_root": stage_name,
            "ledger": ledger.value,
            "period": period,
            "covers": covers,
            "max_raw_files_per_period": max_raw_files_per_period,
            "registry_entry": registration,
            "ledger_settings": settings,
        }
        revision = request["revision"]
        completed = subprocess.run(
            ["bun", "run", str(_WRITER_CLI)],
            cwd=repository,
            input=json.dumps(request, separators=(",", ":")),
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {"GIT_NO_LAZY_FETCH": "1"},
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip()
            raise RuntimeError(
                f"planner maintenance adapter exited with status {completed.returncode}"
                + (f": {detail}" if detail else "")
            )
        try:
            raw_result = json.loads(completed.stdout)
        except json.JSONDecodeError as refusal:
            raise ValueError("planner maintenance adapter returned invalid JSON") from refusal
        receipt = _receipt_base(raw_result, ledger=ledger, period=period, covers=covers)
        if receipt["revision"] != revision:
            raise PlannerMaintenanceRefusalError("revision-changed")
        status = receipt.get("status")
        if status in {"empty", "unchanged"}:
            return PlannerPeriodResult(
                status=status,
                reason=receipt.get("reason"),
            )
        if status == "refused":
            reason = receipt.get("reason")
            if reason not in _REFUSALS:
                raise ValueError("planner maintenance adapter returned an unknown refusal")
            raise PlannerMaintenanceRefusalError(reason)
        if status != "written":
            raise ValueError("planner maintenance adapter returned an unknown result")

        target = _relative_path(receipt.get("target_path"))
        output = _relative_path(receipt.get("output_path"))
        expected_target = paths.compact_path(
            repository / "state",
            ledger,
            Period(period),
            covers,
            fmt=Format.PARQUET,
        ).relative_to(repository).as_posix()
        expected_output = f"{stage_name}/state/{target.removeprefix('state/')}"
        if target != expected_target or output != expected_output:
            raise ValueError("planner maintenance receipt names an unexpected output path")
        if type(receipt.get("row_count")) is not int or receipt["row_count"] < 1:
            raise ValueError("planner maintenance receipt contains an invalid row count")
        if type(receipt.get("target_bytes")) is not int or receipt["target_bytes"] < 1:
            raise ValueError("planner maintenance receipt contains an invalid output size")
        target_digest = _sha256(receipt.get("target_file_sha256"))
        _sha256(receipt.get("content_sha256"))
        expected_digest = receipt.get("expected_target_sha256")
        if expected_digest is not None:
            _sha256(expected_digest)
        sources, _local_paths = _checked_source_paths(
            receipt.get("input_files"),
            repository=repository,
            ledger=ledger,
            prefix=tuple(registration["prefix"]),
            period=period,
            covers=covers,
        )
        source_by_path = {source["path"]: source for source in sources}
        target_source = source_by_path.get(target)
        if (None if target_source is None else target_source["file_sha256"]) != expected_digest:
            raise ValueError("planner maintenance receipt has a mismatched target guard")
        delete_paths = receipt.get("delete_paths")
        if (
            not isinstance(delete_paths, list)
            or any(not isinstance(path, str) for path in delete_paths)
            or len(delete_paths) != len(set(delete_paths))
            or set(map(_relative_path, delete_paths)) != set(source_by_path) - {target}
        ):
            raise ValueError("planner maintenance receipt has an invalid deletion set")
        if not isinstance(receipt.get("carried_over"), bool):
            raise ValueError("planner maintenance receipt has an invalid carry-over flag")
        output_bytes = _read_regular_beneath(
            stage_path,
            output.removeprefix(f"{stage_name}/"),
            missing_reason="missing-local-member",
            malformed_reason="malformed-member",
        )
        if (
            len(output_bytes) != receipt["target_bytes"]
            or hashlib.sha256(output_bytes).hexdigest() != target_digest
        ):
            raise ValueError("planner maintenance output differs from its receipt")
        if _git_revision(repository) != revision:
            raise PlannerMaintenanceRefusalError("revision-changed")
        return PlannerPeriodResult(
            status="written",
            target_path=repository.joinpath(*PurePosixPath(target).parts),
            data=output_bytes,
            file_sha256=target_digest,
            input_paths=tuple(_local_paths),
            delete_paths=tuple(
                repository.joinpath(*PurePosixPath(path).parts)
                for path in delete_paths
            ),
            row_count=receipt["row_count"],
            carried_over=receipt["carried_over"],
        )
    finally:
        _remove_stage(stage_path, owner)
