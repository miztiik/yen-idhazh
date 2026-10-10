"""Do real native producer files match independent CPU expectations and unchanged Python instruments?"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from idhazh.contracts.host_events import HostResultBody
from idhazh.contracts.host_output import HostWriteCompletion, HostWritePlan, fingerprint_v2
from idhazh.telemetry import silicon
from idhazh.telemetry.host_output_verify import VerificationLimits, verify_host_output

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "host-events" / "probe-clock.json"
pytestmark = pytest.mark.contract


def _config() -> dict[str, Any]:
    config: dict[str, Any] = json.loads((ROOT / "config" / "host-telemetry-experiment.json").read_bytes())
    return config


def native() -> Path:
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "backend/var/rust-host-telemetry"))
    binary = target / "debug" / ("idhazh-host-telemetry.exe" if os.name == "nt" else "idhazh-host-telemetry")
    assert binary.is_file(), "Build the locked native producer before testing; missing binaries are not skips."
    return binary


@pytest.mark.parametrize("codec", ["json", "none", "snappy", "zstd"])
def test_same_cargo_harness_files_pass_read_only_verifier_and_python_instruments(codec: str) -> None:
    workspace = ROOT / "backend" / "var" / f"d3-job-{codec}"
    assert (workspace / "final-result.json").is_file(), "Run native producer tests before parity."
    body = HostResultBody.model_validate_json((workspace / "final-result.json").read_bytes())
    plan = HostWritePlan.model_validate_json((workspace / "final-plan.json").read_bytes())
    completion = HostWriteCompletion.model_validate_json((workspace / "final-completion.json").read_bytes())
    before = {path: (workspace / path).read_bytes() for path in completion.receipt.writes}
    verified = verify_host_output(
        plan, completion, workspace_root=workspace, target_root=plan.target_root,
        publication_identity=plan.publication_identity, limits=VerificationLimits(**_config()["verification_limits"]),
    )
    assert verified.complete and len(verified.files) == 1
    stored = verified.files[0].rows[0]
    assert stored.model_dump(include=set(type(body.row).model_fields)) == body.row.model_dump()
    assert verified.files[0].physical_sha256 == hashlib.sha256(next(iter(before.values()))).hexdigest()
    assert {path: (workspace / path).read_bytes() for path in before} == before
    row = body.row
    capture = json.loads(FIXTURE.read_bytes())["attempts"][0]
    cpuinfo = capture["cpuinfo"]["value"]
    fields, _ = silicon._cpuinfo_fields(cpuinfo)
    assert row.cpu_model == fields["model name"]
    assert row.cpu_vendor == fields["vendor_id"]
    assert row.cpu_family == 6 and row.cpu_model_number == 207 and row.cpu_stepping == 2
    assert row.microcode == fields["microcode"]
    assert row.flags == silicon.watched_flags(cpuinfo)
    assert row.boot_seconds == silicon.boot_seconds(capture["uptime"]["value"])
    assert (row.cpu_physical_cores, row.cpu_logical_processors, row.cpu_allowed_processors) == (3, 4, 2)
    assert (row.cpu_quota_cores, row.cpu_quota_state) == (0.5, "finite")
    assert (row.cpu_observed_mhz, row.cpu_reported_max_mhz) == (2400.0, 3600.0)
    assert row.fingerprint_version == 2 and row.fingerprint == fingerprint_v2(row)
    assert body.cpu.online_cpu_ids == (0, 2, 3, 7)
    log = (ROOT / "tests/fixtures/runtime/2026-08-29-3-shard-0.server-head.txt").read_text()
    metrics = (ROOT / "tests/fixtures/runtime/2026-08-26-5-shard-0.prom").read_text()
    assert row.model_load_ms == silicon.model_load_ms(log) == 3797.64
    assert (row.server_prompt_tokens, row.server_prompt_seconds) == silicon.server_prompt_totals(metrics)
    assert row.job_seconds == 42
    assert row.measured_at == "2026-10-10T12:00:00Z"
    assert row.cpu_target_measured_at == "2026-10-10T12:00:01Z"


def _write(root: Path, name: str, content: str | bytes) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)


def _source_tree(root: Path, capture: dict[str, Any]) -> None:
    for name, key in [("cpu/online", "online_before"), ("cpu/present", "inventory"),
                      ("proc/cpuinfo", "cpuinfo"), ("proc/uptime", "uptime")]:
        _write(root, name, capture[key]["value"])
    for entry in capture["topology"]:
        for name, key in [("physical_package_id", "package"), ("core_id", "core"),
                          ("thread_siblings_list", "thread_siblings"), ("core_siblings_list", "package_siblings")]:
            _write(root, f"cpu/cpu{entry['id']}/topology/{name}", entry[key]["value"])
    for policy in capture["policies"]["value"]:
        _write(root, f"cpu/cpufreq/{policy['name']}/related_cpus", policy["cpus"]["value"])
        _write(root, f"cpu/cpufreq/{policy['name']}/cpuinfo_max_freq", policy["maximum_khz"]["value"])
    _write(root, "cpu/cpu0/cache/index3/level", "3\n")
    _write(root, "cpu/cpu0/cache/index3/size", "32M\n")
    target = capture["target_before"]
    for name in ["cgroup", "mountinfo"]:
        _write(root, f"proc/100/{name}", target[name]["value"])
    _write(root, "proc/100/stat", "100 (Python worker) S " + "0 " * 18 + "800\n")
    for entry in target["constraints"]["value"]:
        for name, key in [("cgroup.controllers", "controllers"), ("cpuset.cpus.effective", "cpuset"), ("cpu.max", "quota")]:
            if entry[key]["value"] is not None:
                _write(root, f"namespace{entry['directory']}/{name}", entry[key]["value"])
    _write(root, "affinity.json", json.dumps(target["affinity"]))


def test_actual_generated_proc_sysfs_cli_sources_are_not_a_second_implementation() -> None:
    workspace = ROOT / "backend" / "var" / "d3-python" / str(uuid4())
    replay = json.loads(FIXTURE.read_bytes())
    _source_tree(workspace, replay["attempts"][0])
    _write(workspace, "metadata.json", replay["placement_json"]["value"])
    _write(workspace, "config.json", json.dumps(_config()))
    manifest = json.loads((ROOT / "tests/fixtures/host-events/manifest.json").read_bytes())
    manifest["output_roots"] = ["output/state"]
    manifest["named_inputs"] = [
        {"name": "affinity", "source": "sched.affinity", "relative_path": "affinity.json"},
        {"name": "metadata", "source": "proc.cpuinfo", "relative_path": "metadata.json"},
    ]
    _write(workspace, "manifest.json", json.dumps(manifest))
    command = {
        key: manifest[key] for key in ["version", "date", "run_id", "attempt", "job", "shard", "session_id"]
    } | {
        "kind": "host.probe", "event_id": str(uuid4()), "reply_to": None, "sequence": 1,
        "emitter_id": "operator", "emitted_at": "2026-10-10T12:00:00Z",
        "body": {"controls": manifest["controls"], "input_names": ["affinity", "metadata"], "target": manifest["cpu_target"]},
    }
    _write(workspace, "command.json", json.dumps(command))
    args = [
        str(native()), "probe", "--workspace", str(workspace), "--manifest", "manifest.json",
        "--command", "command.json", "--config", "config.json", "--proc-root", str(workspace / "proc"),
        "--cpu-root", str(workspace / "cpu"), "--namespace-root", str(workspace / "namespace"),
        "--affinity-input", "affinity", "--metadata-input", "metadata", "--cache-multiple", "2",
        "--format", "json", "--result-id", str(uuid4()),
    ]
    output = subprocess.run(args, cwd=ROOT, capture_output=True, check=False, timeout=60)
    assert output.returncode == 0, output.stderr.decode()
    result = json.loads((workspace / output.stdout.decode().strip()).read_bytes())
    body = HostResultBody.model_validate(result["body"])
    assert body.row.cpu_allowed_processors == 2 and body.row.cpu_quota_cores == 0.5
    assert body.row.cpu_physical_cores == 3 and body.row.cpu_logical_processors == 4
    assert body.row.cpu_observed_mhz == 2400.0 and body.row.cpu_reported_max_mhz == 3600.0
    assert body.row.cpu_target_measured_at == body.row.measured_at


def test_selected_python_worker_uses_live_linux_affinity_or_diagnoses_windows_source() -> None:
    workspace = ROOT / "backend" / "var" / "d3-python-live" / str(uuid4())
    replay = json.loads(FIXTURE.read_bytes())
    _source_tree(workspace, replay["attempts"][0])
    manifest = json.loads((ROOT / "tests/fixtures/host-events/manifest.json").read_bytes())
    manifest["output_roots"] = ["output/state"]
    manifest["named_inputs"] = [{"name": "metadata", "source": "proc.cpuinfo", "relative_path": "metadata.json"}]
    _write(workspace, "metadata.json", replay["placement_json"]["value"])
    _write(workspace, "config.json", json.dumps(_config()))
    worker = None
    if os.name != "nt":
        worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        stat = Path(f"/proc/{worker.pid}/stat").read_text()
        ticks = int(stat.rsplit(") ", 1)[1].split()[19])
        target = {"pid": worker.pid, "start_ticks": ticks}
        manifest["workers"] = [{"emitter_id": "worker-0", "target": target, "server": None}]
        manifest["windows"] = []
        manifest["cpu_target"] = target
        manifest["cpu_target_role"] = "python_worker"
        get_affinity = getattr(os, "sched_getaffinity", None)
        set_affinity = getattr(os, "sched_setaffinity", None)
        assert callable(get_affinity) and callable(set_affinity), "Linux affinity instruments must be available."
        available = sorted(get_affinity(worker.pid))
        set_affinity(worker.pid, available[:min(2, len(available))])
        roots = ["/proc", "/sys/devices/system/cpu", f"/proc/{worker.pid}/root"]
    else:
        roots = [str(workspace / "proc"), str(workspace / "cpu"), str(workspace / "namespace")]
    _write(workspace, "manifest.json", json.dumps(manifest))
    command = {
        key: manifest[key] for key in ["version", "date", "run_id", "attempt", "job", "shard", "session_id"]
    } | {
        "kind": "host.probe", "event_id": str(uuid4()), "reply_to": None, "sequence": 1,
        "emitter_id": "operator", "emitted_at": "2026-10-10T12:00:00Z",
        "body": {"controls": manifest["controls"], "input_names": ["metadata"], "target": manifest["cpu_target"]},
    }
    _write(workspace, "command.json", json.dumps(command))
    args = [
        str(native()), "probe", "--workspace", str(workspace), "--manifest", "manifest.json",
        "--command", "command.json", "--config", "config.json", "--proc-root", roots[0],
        "--cpu-root", roots[1], "--namespace-root", roots[2], "--metadata-input", "metadata",
        "--cache-multiple", "2", "--format", "json", "--result-id", str(uuid4()),
    ]
    try:
        output = subprocess.run(args, cwd=ROOT, capture_output=True, check=False, timeout=60)
        assert output.returncode == 0, output.stderr.decode()
        body = HostResultBody.model_validate(json.loads(
            (workspace / output.stdout.decode().strip()).read_bytes()
        )["body"])
        if worker is None:
            assert body.row.cpu_allowed_processors is None
            assert body.row.cpu_quota_cores == 0.5
            assert next(s for s in body.cpu.sources if s.source == "sched.affinity").reason == "missing"
        else:
            assert body.cpu.target is not None
            assert body.cpu.target.pid == worker.pid
            assert body.row.cpu_logical_processors == len(body.cpu.online_cpu_ids)
            if body.row.cpu_allowed_processors is not None:
                assert callable(get_affinity), "Linux affinity instrument must remain available."
                assert body.row.cpu_allowed_processors <= len(get_affinity(worker.pid)) <= 2
            else:
                assert next(s for s in body.cpu.sources if s.source == "sched.affinity").reason is not None
    finally:
        if worker is not None:
            worker.terminate()
            worker.wait(timeout=10)
