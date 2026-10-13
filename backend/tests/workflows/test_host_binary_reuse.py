"""Can one run reuse its monitor only with matching native inputs and intact bytes?"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import cast

import pytest
import yaml  # type: ignore[import-untyped]

from ._harness import _bash, _mapping, requires_bash

ROOT = Path(__file__).resolve().parents[3]


def _action(name: str) -> dict[str, object]:
    return _mapping(
        yaml.safe_load(
            (ROOT / ".github" / "actions" / name / "action.yml").read_text(encoding="utf-8")
        ),
        name,
    )


def _action_steps(name: str) -> list[dict[str, object]]:
    steps = _mapping(_action(name)["runs"], "action runs")["steps"]
    assert isinstance(steps, list)
    return [_mapping(step, "action step") for step in steps]


def test_shared_monitor_identity_covers_native_inputs_not_repository_head() -> None:
    package = next(
        step for step in _action_steps("d7-host-telemetry") if step.get("id") == "package"
    )
    consumer = _action_steps("download-host-telemetry")[0]
    source = _mapping(package["env"], "package environment")["NATIVE_INPUT_HASH"]
    assert source == _mapping(consumer["env"], "consumer environment")["NATIVE_INPUT_HASH"]
    assert source == (
        "${{ hashFiles('backend/rust/host-telemetry/Cargo.toml', "
        "'backend/rust/host-telemetry/Cargo.lock', "
        "'backend/rust/host-telemetry/rust-toolchain.toml', "
        "'backend/rust/host-telemetry/src/**/*.rs') }}"
    )
    for step in (package, consumer):
        env = _mapping(step["env"], "artifact identity")
        assert env["RUNNER_OS"] == "${{ runner.os }}"
        assert env["RUNNER_ARCH"] == "${{ runner.arch }}"
        assert "github.sha" not in str(env)
        assert "NATIVE_INPUT_HASH" in str(step["run"])
    upload = next(
        step for step in _action_steps("d7-host-telemetry")
        if step.get("uses") == "actions/upload-artifact@v7"
    )
    assert _mapping(upload["with"], "immutable upload").get("overwrite", False) is False
    downloads = _action_steps("download-host-telemetry")
    assert downloads[1]["uses"] == "actions/download-artifact@v8"
    assert _mapping(downloads[1]["with"], "download")["name"] == "${{ inputs.artifact_name }}"
    assert "cargo" not in str(downloads) and "rustup" not in str(downloads)


def _shell(step: dict[str, object], root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    bash = _bash()
    assert bash is not None
    return subprocess.run(
        [bash, "-c", cast(str, step["run"])],
        cwd=root / str(step.get("working-directory", ".")),
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )


@requires_bash
@pytest.mark.parametrize(
    ("artifact", "accepted"),
    [
        (f"d7-host-31-1-Linux-X64-{'a' * 64}", True),
        (f"d7-host-31-2-Linux-X64-{'a' * 64}", True),
        (f"d7-host-31-1-Linux-X64-{'b' * 64}", False),
        (f"d7-host-31-1-Linux-ARM64-{'a' * 64}", False),
        (f"d7-host-31-1-Windows-X64-{'a' * 64}", False),
        (f"d7-host-32-1-Linux-X64-{'a' * 64}", False),
    ],
)
def test_real_download_boundary_refuses_source_platform_or_run_mismatch(
    tmp_path: Path, artifact: str, accepted: bool
) -> None:
    binding = _action_steps("download-host-telemetry")[0]
    completed = _shell(
        binding, tmp_path,
        {
            "ARTIFACT_NAME": artifact, "NATIVE_INPUT_HASH": "a" * 64,
            "RUN_ID": "31", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
        },
    )
    assert (completed.returncode == 0) is accepted, completed.stderr
    assert not (tmp_path / "backend").exists()


@requires_bash
def test_real_package_checksum_allows_intact_bytes_and_refuses_corruption(tmp_path: Path) -> None:
    binary = tmp_path / "monitor"
    binary.write_bytes(b"#!/bin/sh\nexit 0\n")
    output = tmp_path / "github-output"
    env_file = tmp_path / "github-env"
    env = {
        "BINARY": binary.as_posix(), "NATIVE_INPUT_HASH": "a" * 64,
        "RUN_ID": "31", "RUN_ATTEMPT": "1", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
        "GITHUB_OUTPUT": output.as_posix(), "GITHUB_ENV": env_file.as_posix(),
        "GITHUB_WORKSPACE": tmp_path.as_posix(),
    }
    package = next(
        step for step in _action_steps("d7-host-telemetry") if step.get("id") == "package"
    )
    completed = _shell(package, tmp_path, env)
    assert completed.returncode == 0, completed.stderr
    assert output.read_text(encoding="utf-8").strip() == (
        f"artifact_name=d7-host-31-1-Linux-X64-{'a' * 64}"
    )
    verify = _action_steps("download-host-telemetry")[2]
    completed = _shell(verify, tmp_path, env)
    assert completed.returncode == 0, completed.stderr
    assert "IDHAZH_HOST_TELEMETRY_BINARY=" in env_file.read_text(encoding="utf-8")
    env_file.unlink()
    (tmp_path / "backend" / "var" / "host-monitor-artifact" / "idhazh-host-telemetry").write_bytes(
        b"changed after upload"
    )
    completed = _shell(verify, tmp_path, env)
    assert completed.returncode != 0
    assert not env_file.exists(), "corrupt monitor was exported for a producer"
