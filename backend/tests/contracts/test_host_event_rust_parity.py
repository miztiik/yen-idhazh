"""Do real native producer files match independent CPU expectations and unchanged Python instruments?"""

from __future__ import annotations

import copy
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
        for name, key in [("cgroup.controllers", "controllers"), ("cgroup.subtree_control", "subtree_control"),
                          ("cpuset.cpus.effective", "cpuset"), ("cpu.max", "quota")]:
            if entry[key]["value"] is not None:
                _write(root, f"namespace{entry['directory']}/{name}", entry[key]["value"])
    _write(root, "affinity.json", json.dumps(target["affinity"]))
    _write(root, "hierarchy.json", json.dumps({
        "source_context": target["source_context"],
        "root_evidence": [entry.get("root_evidence") for entry in target["constraints"]["value"]],
    }))


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
        {"name": "hierarchy", "source": "cgroup.cpu_quota", "relative_path": "hierarchy.json"},
    ]
    _write(workspace, "manifest.json", json.dumps(manifest))
    command = {
        key: manifest[key] for key in ["version", "date", "run_id", "attempt", "job", "shard", "session_id"]
    } | {
        "kind": "host.probe", "event_id": str(uuid4()), "reply_to": None, "sequence": 1,
        "emitter_id": "operator", "emitted_at": "2026-10-10T12:00:00Z",
        "body": {"controls": manifest["controls"], "input_names": ["affinity", "metadata", "hierarchy"],
                 "target": manifest["cpu_target"]},
    }
    _write(workspace, "command.json", json.dumps(command))
    args = [
        str(native()), "probe", "--workspace", str(workspace), "--manifest", "manifest.json",
        "--command", "command.json", "--config", "config.json", "--proc-root", str(workspace / "proc"),
        "--cpu-root", str(workspace / "cpu"), "--namespace-root", str(workspace / "namespace"),
        "--affinity-input", "affinity", "--metadata-input", "metadata", "--hierarchy-input", "hierarchy",
        "--cache-multiple", "2",
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
            assert body.row.cpu_quota_cores is None and body.row.cpu_quota_state == "unavailable"
            assert next(s for s in body.cpu.sources if s.source == "cgroup.cpu_quota").reason == "incomplete_coverage"
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


def _run_recorded_capture(capture: dict[str, Any]) -> HostResultBody:
    workspace = ROOT / "backend" / "var" / "d3-python-hierarchy" / str(uuid4())
    replay = json.loads(FIXTURE.read_bytes())
    replay["attempts"] = [capture]
    manifest = json.loads((ROOT / "tests/fixtures/host-events/manifest.json").read_bytes())
    manifest["output_roots"] = ["output/state"]
    manifest["named_inputs"] = [{"name": "snapshot", "source": "proc.cpuinfo", "relative_path": "capture.json"}]
    command = {
        key: manifest[key] for key in ["version", "date", "run_id", "attempt", "job", "shard", "session_id"]
    } | {
        "kind": "host.probe", "event_id": str(uuid4()), "reply_to": None, "sequence": 1,
        "emitter_id": "operator", "emitted_at": "2026-10-10T12:00:00Z",
        "body": {"controls": manifest["controls"], "input_names": ["snapshot"], "target": manifest["cpu_target"]},
    }
    for name, value in [
        ("capture.json", replay), ("manifest.json", manifest), ("command.json", command), ("config.json", _config()),
    ]:
        _write(workspace, name, json.dumps(value))
    result_id = str(uuid4())
    args = [
        str(native()), "probe", "--workspace", str(workspace), "--manifest", "manifest.json",
        "--command", "command.json", "--config", "config.json", "--snapshot", "snapshot",
        "--cache-multiple", "2", "--format", "json", "--result-id", result_id,
    ]
    output = subprocess.run(args, cwd=ROOT, capture_output=True, check=False, timeout=60)
    assert output.returncode == 0, output.stderr.decode()
    event = json.loads((workspace / output.stdout.decode().strip()).read_bytes())
    body = HostResultBody.model_validate(event["body"])
    evidence = workspace / manifest["event_root"] / "writes"
    plan = HostWritePlan.model_validate_json((evidence / f"{command['event_id']}.plan.json").read_bytes())
    completion = HostWriteCompletion.model_validate_json(
        (evidence / f"{command['event_id']}.completed-1.json").read_bytes(),
    )
    verified = verify_host_output(
        plan, completion, workspace_root=workspace, target_root=plan.target_root,
        publication_identity=plan.publication_identity, limits=VerificationLimits(**_config()["verification_limits"]),
    )
    assert verified.complete
    assert verified.files[0].rows[0].model_dump(include=set(type(body.row).model_fields)) == body.row.model_dump()
    return body


@pytest.mark.parametrize("mode", [
    "actual", "hidden", "legacy", "denied", "wrong_fs", "covering_mount", "context_changed", "root_changed",
    "partition_empty", "partition_disjoint", "partition_parent_changed", "inherit", "required_missing",
    "unknown_applicability", "finite_ancestor", "unlimited", "v1", "v1_hidden", "hybrid",
])
def test_native_structural_hierarchy_and_partition_semantics_have_exact_python_cells(mode: str) -> None:
    capture = json.loads(FIXTURE.read_bytes())["attempts"][0]
    expected_quota: float | None = 0.5
    expected_state = "finite"
    expected_allowed: int | None = 2
    expected_reason = None
    for target in [capture["target_before"], capture["target_after"]]:
        rows = target["constraints"]["value"]
        proof = rows[-1]["root_evidence"]
        if mode in {"hidden", "v1_hidden"}:
            proof["marker"] = copy.deepcopy(proof["cgroup_procs"])
        elif mode == "legacy":
            target.pop("source_context")
            rows[-1].pop("root_evidence")
        elif mode == "denied":
            proof["marker"] = {"failed": "permission_denied"}
        elif mode == "wrong_fs":
            proof["directory"]["value"]["filesystem_type"] = 0x01021994
        elif mode == "covering_mount":
            target["mountinfo"]["value"] += "40 29 0:40 / /sys/fs/cgroup/slice rw - tmpfs tmpfs rw\n"
        elif mode.startswith("partition_"):
            rows[1]["cpuset"]["value"] = "" if mode == "partition_empty" else "3"
            rows[2]["cpuset"]["value"] = ""
        elif mode in {"inherit", "required_missing", "unknown_applicability"}:
            rows[0]["cpuset"] = {"value": None, "reason": "missing"}
            rows[0]["quota"] = {"value": None, "reason": "missing"}
            if mode == "inherit":
                rows[1]["subtree_control"]["value"] = ""
                rows[0]["controllers"]["value"] = ""
                rows[1]["cpuset"]["value"] = "2,7"
                rows[1]["quota"]["value"] = "25000 100000"
            elif mode == "unknown_applicability":
                rows[1]["subtree_control"] = {"value": None, "reason": "missing"}
        elif mode in {"finite_ancestor", "unlimited"}:
            rows[0]["quota"]["value"] = "max 100000"
            rows[1]["quota"]["value"] = "25000 100000" if mode == "finite_ancestor" else "max 100000"
        if mode in {"v1", "v1_hidden", "hybrid"}:
            def v1_rows(
                controller: str, mount_id: int, minor: int, template: dict[str, Any], root_template: dict[str, Any],
            ) -> list[dict[str, Any]]:
                result = []
                for path in [f"/{controller}/slice/job", f"/{controller}/slice", f"/{controller}"]:
                    entry = copy.deepcopy(template)
                    entry.update(controller=controller, directory=path, root=path == f"/{controller}")
                    entry["quota"] = {"value": "-1" if entry["root"] else "75000", "reason": None}
                    entry["period"] = {"value": "100000", "reason": None}
                    entry["cpuset"] = {"value": "" if path.endswith("/job") else "0,2,7", "reason": None}
                    if entry["root"]:
                        root_proof = copy.deepcopy(root_template)
                        root_proof["selected_mount"].update(
                            id=mount_id, minor=minor, mountpoint=f"/{controller}",
                        )
                        root_proof["directory"]["value"].update(
                            filesystem_type=0x27E0EB, mount_id=mount_id, minor=minor,
                        )
                        root_proof["directory"]["value"]["identity"]["device"] = minor
                        root_proof["cgroup_procs"]["present"].update(mount_id=mount_id)
                        root_proof["cgroup_procs"]["present"]["identity"]["device"] = minor
                        root_proof["marker"] = "exact_enoent" if mode == "v1_hidden" else copy.deepcopy(
                            root_proof["cgroup_procs"],
                        )
                        entry["root_evidence"] = root_proof
                    result.append(entry)
                return result

            target["cgroup"]["value"] = ("0::/slice/job\n" if mode == "hybrid" else "") \
                + "4:cpu:/slice/job\n3:cpuset:/slice/job\n"
            target["mountinfo"]["value"] = (
                "29 23 0:26 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n" if mode == "hybrid" else ""
            ) + "30 23 0:27 / /cpu rw - cgroup cgroup rw,cpu\n31 23 0:28 / /cpuset rw - cgroup cgroup rw,cpuset\n"
            target["constraints"]["value"] = (rows if mode == "hybrid" else []) \
                + v1_rows("cpu", 30, 27, rows[0], proof) + v1_rows("cpuset", 31, 28, rows[0], proof)
    if mode in {"hidden", "legacy", "denied", "wrong_fs", "covering_mount", "required_missing",
                "unknown_applicability", "v1_hidden"}:
        expected_quota, expected_state, expected_allowed = None, "unavailable", None
        expected_reason = "permission_denied" if mode == "denied" else (
            "missing" if mode in {"required_missing", "unknown_applicability"} else "incomplete_coverage"
        )
    elif mode in {"context_changed", "root_changed"}:
        after = capture["target_after"]
        if mode == "context_changed":
            after["source_context"]["value"]["target_mountns"]["inode"] += 1
        else:
            after["constraints"]["value"][-1]["root_evidence"]["directory"]["value"]["identity"]["inode"] += 1
        expected_quota, expected_state, expected_allowed, expected_reason = None, "unavailable", None, "snapshot_changed"
    elif mode == "partition_parent_changed":
        capture["target_after"]["constraints"]["value"][1]["cpuset"]["value"] = "6"
    elif mode in {"inherit", "finite_ancestor"}:
        expected_quota = 0.25
    elif mode == "unlimited":
        expected_quota, expected_state = None, "unlimited"
    elif mode == "v1":
        expected_quota = 0.75
    body = _run_recorded_capture(capture)
    assert (body.row.cpu_quota_cores, body.row.cpu_quota_state) == (expected_quota, expected_state)
    assert body.row.cpu_allowed_processors == expected_allowed
    assert next(s for s in body.cpu.sources if s.source == "cgroup.cpu_quota").reason == expected_reason
    assert body.row.cpu_logical_processors == 4 and body.row.cpu_physical_cores == 3
