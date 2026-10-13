"""Bounded native settings and immutable runtime document support."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from idhazh.contracts.base import Model
from idhazh.contracts.host_events import (
    CollectionControls,
    FinitePositive,
    HostCaptureLimits,
    HostEventLimits,
    PositiveCount,
)
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


class NativeCommandSettings(Model):
    worker_timeout_seconds: FinitePositive
    max_command_output_bytes: PositiveCount


def read_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError(f"named input exceeds its byte cap: {path.name}")
    return raw


def settings() -> tuple[NativeSettings, NativeCommandSettings, str]:
    native_raw = read_bytes(ROOT / "config/host-telemetry-experiment.json", CONFIG_BYTES)
    command_raw = read_bytes(ROOT / "config/host-telemetry-lifecycle.json", CONFIG_BYTES)
    command = json.loads(command_raw)
    if not isinstance(command, dict):
        raise ValueError("native command settings must be an object")
    return (
        NativeSettings.model_validate_json(native_raw),
        NativeCommandSettings.model_validate(command),
        hashlib.sha256(native_raw + command_raw).hexdigest(),
    )


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


def write_json(path: Path, value: object) -> None:
    raw = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
