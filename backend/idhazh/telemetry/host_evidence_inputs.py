"""Which named inputs and generated roots are safe for an isolated comparison?"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.base import Model
from idhazh.contracts.host_events import (
    CollectionControls,
    FiniteNonnegative,
    FinitePositive,
    HostCaptureLimits,
    HostEventLimits,
    PositiveCount,
)
from idhazh.contracts.host_evidence import EvidenceRoots, FieldBound, WorkloadResult
from idhazh.telemetry.host_output_verify import VerificationLimits

# The file cannot choose its own bootstrap allocation allowance.
CONFIG_BYTES = 65536
ROOT = Path(__file__).resolve().parents[3]


class NativeSettings(Model):
    version: str
    controls: CollectionControls
    limits: HostEventLimits
    capture_limits: HostCaptureLimits
    verification_limits: VerificationLimits


class ComparisonSettings(Model):
    source: AppConfig
    version: str
    calibration_runs: Annotated[int, Field(strict=True, ge=2, le=8)]
    paired_runs: Annotated[int, Field(strict=True, ge=2, le=4)]
    workload_memory_mib: Annotated[int, Field(strict=True, ge=1, le=128)]
    workload_iterations: Annotated[int, Field(strict=True, ge=1, le=256)]
    workload_min_seconds: Annotated[float, Field(strict=True, ge=3.0, le=10.0)]
    min_window_samples: PositiveCount
    resource_interval_seconds: FiniteNonnegative
    sample_interval_seconds: FinitePositive
    worker_timeout_seconds: FinitePositive
    build_timeout_seconds: FinitePositive
    max_artifact_files: PositiveCount
    max_artifact_bytes: PositiveCount
    max_junit_bytes: PositiveCount
    max_command_output_bytes: PositiveCount
    max_process_entries: PositiveCount
    spread_multiplier: Annotated[float, Field(strict=True, ge=1, le=3)]
    bounds: dict[str, tuple[FinitePositive, FinitePositive]]

    @model_validator(mode="after")
    def _finite_experiment(self) -> ComparisonSettings:
        if self.resource_interval_seconds != 0.0:
            raise ValueError("live comparison requires endpoint-only resource cadence")
        if self.workload_memory_mib * 1024 * 1024 > self.max_artifact_bytes * 4:
            raise ValueError("workload memory exceeds the declared bounded experiment")
        if self.sample_interval_seconds >= self.worker_timeout_seconds:
            raise ValueError("sample interval must fit the worker deadline")
        if self.workload_min_seconds < 2 + self.min_window_samples * self.sample_interval_seconds:
            raise ValueError("predeclared pacing cannot supply unambiguous sample coverage")
        if (
            self.workload_min_seconds + 2 * self.sample_interval_seconds
            >= self.worker_timeout_seconds
        ):
            raise ValueError("paced workload must fit the worker deadline")
        if set(self.bounds) != {
            "cpu_busy_pct",
            "cpu_busy_max",
            "cpu_busy_min",
            "cpu_steal_pct",
            "load_1m",
            "python_rss_bytes",
            "python_rss_anon_bytes",
            "os_mem_available_bytes",
            "os_mem_cached_bytes",
            "os_mem_available_min_bytes",
            "boot_seconds",
            "measured_at",
            "job_seconds",
        }:
            raise ValueError("every varying live field needs exactly one predeclared bound")
        if any(floor > ceiling for floor, ceiling in self.bounds.values()):
            raise ValueError("a bound floor exceeds its predeclared ceiling")
        return self


def read_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError(f"named input exceeds its byte cap: {path.name}")
    return raw


def read_model[T: Model](path: Path, model: type[T], maximum: int) -> T:
    return model.model_validate_json(read_bytes(path, maximum))


def settings() -> tuple[NativeSettings, ComparisonSettings, str]:
    native_raw = read_bytes(ROOT / "config/host-telemetry-experiment.json", CONFIG_BYTES)
    compare_raw = read_bytes(ROOT / "config/host-telemetry-comparison.json", CONFIG_BYTES)
    source_raw = read_bytes(ROOT / "config/idhazh.json", CONFIG_BYTES)
    source = AppConfig.model_validate_json(source_raw)
    return (
        NativeSettings.model_validate_json(native_raw),
        comparison_settings(compare_raw, source),
        hashlib.sha256(native_raw + compare_raw + source_raw).hexdigest(),
    )


def comparison_settings(raw: bytes, source: AppConfig) -> ComparisonSettings:
    comparison = json.loads(raw)
    if not isinstance(comparison, dict) or "source" in comparison:
        raise ValueError("comparison configuration cannot override shared application settings")
    return ComparisonSettings.model_validate({**comparison, "source": source})


def live_controls(
    native: NativeSettings,
    config: ComparisonSettings,
    memory_override: bool | None = None,
) -> CollectionControls:
    if native.controls.memcpy_enabled:
        raise ValueError("live evidence requires the bounded copy probe off")
    if config.sample_interval_seconds * 1000 < native.limits.retry_window_ms:
        raise ValueError("sample cadence cannot outrun the native immutable retry retention window")
    memory = (
        config.source.observability.memory_profiling_enabled
        if memory_override is None
        else memory_override
    )
    return CollectionControls.model_validate(
        {
            **native.controls.model_dump(),
            "memory_profiling_enabled": memory,
            "resource_interval_seconds": config.resource_interval_seconds,
            "job_sample_interval_seconds": config.sample_interval_seconds,
        }
    )


def isolated_workspace(path: Path, *, create: bool = False) -> Path:
    path = Path(path.absolute())
    if ".." in path.parts:
        raise ValueError("comparison workspace must be minimal and task-owned")
    allowed = ROOT / "backend/var"
    if not path.is_relative_to(allowed.absolute()) or path == allowed:
        raise ValueError("comparison workspace must be a new task-owned backend/var child")
    current = path
    while current != ROOT:
        if current.is_symlink() or current.is_junction():
            raise ValueError("comparison workspace contains a link or junction")
        current = current.parent
    if create:
        path.mkdir(parents=True, exist_ok=False)
    if not path.is_dir():
        raise ValueError("comparison workspace is missing")
    return path.resolve()


def resolve(workspace: Path, name: str) -> Path:
    if (
        "\\" in name
        or Path(name).is_absolute()
        or any(p in {"", ".", ".."} for p in name.split("/"))
    ):
        raise ValueError("evidence path must be minimal and relative")
    path = workspace.joinpath(*name.split("/"))
    if not path.resolve().is_relative_to(workspace.resolve()):
        raise ValueError("evidence path escapes its workspace")
    current = path
    while current != workspace:
        if current.is_symlink() or current.is_junction():
            raise ValueError("evidence path contains a link or junction")
        current = current.parent
    return path


def validate_roots(workspace: Path, roots: EvidenceRoots, *event_roots: str) -> None:
    paths = [resolve(workspace, value) for value in (*roots.model_dump().values(), *event_roots)]
    for left in paths:
        if left.relative_to(workspace).parts[0] in {"state", "corpus", "frontend"}:
            raise ValueError("production root spelling is not an isolated root")
        for right in paths:
            if left != right and (left.is_relative_to(right) or right.is_relative_to(left)):
                raise ValueError("writer and generated roots overlap")
    if len(set(paths)) != len(paths):
        raise ValueError("writer roots alias")


def write_document(path: Path, value: Model) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (
        json.dumps(value.model_dump(mode="json"), ensure_ascii=True, separators=(",", ":")) + "\n"
    ).encode("ascii")
    if path.exists():
        if read_bytes(path, len(raw)) != raw:
            raise ValueError(f"immutable evidence conflict: {path.name}")
        return
    staged = path.with_name(path.name + ".pending")
    with staged.open("xb") as stream:
        stream.write(raw)
    staged.replace(path)


def retain_native(path: Path, raw: bytes, maximum: int) -> None:
    if len(raw) > maximum:
        raise ValueError("received native document exceeds its configured cap")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if read_bytes(path, maximum) != raw:
            raise ValueError("immutable received native evidence conflicts")
        return
    with path.open("xb") as stream:
        stream.write(raw)


def freeze_bounds(
    rows: tuple[WorkloadResult, ...], config: ComparisonSettings
) -> tuple[FieldBound, ...]:
    if len(rows) < 2 or any(row.mode != "reference" for row in rows):
        raise ValueError("repeated reference-only calibration evidence is absent")
    frozen: list[FieldBound] = []
    for field, (floor, ceiling) in config.bounds.items():
        if field == "job_seconds":
            spread = max(row.clock_skew_seconds for row in rows)
        elif field in {"boot_seconds", "measured_at"}:
            clocks = [getattr(row.host, field) for row in rows if row.host is not None]
            if len(clocks) != len(rows) or any(value is None for value in clocks):
                raise ValueError(f"required calibration evidence is absent: {field}")
            values = [
                datetime.fromisoformat(value).timestamp() if isinstance(value, str) else value
                for value in clocks
            ]
            spread = float(max(values) - min(values))
        else:
            values = [getattr(row.cells, field) for row in rows if row.cells is not None]
            if len(values) != len(rows) or any(value is None for value in values):
                raise ValueError(f"required calibration evidence is absent: {field}")
            spread = float(max(values) - min(values))
        bound = max(floor, spread * config.spread_multiplier)
        if bound > ceiling:
            raise ValueError(f"reference noise exceeds the predeclared ceiling: {field}")
        frozen.append(FieldBound(field=field, absolute=bound, observed_reference_spread=spread))
    return tuple(frozen)


def write_json(path: Path, value: object) -> None:
    raw = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
