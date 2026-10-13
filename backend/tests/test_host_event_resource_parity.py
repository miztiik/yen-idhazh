"""Do native resources match independently captured expectations and unchanged readers?"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from idhazh.contracts.host_events import HostEvent, HostSessionManifest, WindowResultBody

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.contract


def binary() -> Path:
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "backend/var/rust-host-telemetry"))
    path = (
        target
        / "debug"
        / ("idhazh-host-telemetry.exe" if os.name == "nt" else "idhazh-host-telemetry")
    )
    assert path.is_file(), (
        "Build the locked native monitor; missing binaries are failures, never skips."
    )
    return path


def fixture() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (ROOT / "tests/fixtures/host-events/resource-windows.json").read_bytes()
    )
    return value


def manifest() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (ROOT / "tests/fixtures/host-events/manifest.json").read_bytes()
    )
    return value


def event(m: dict[str, Any], kind: str, worker: int, sequence: int) -> dict[str, Any]:
    address = {
        key: m[key]
        for key in ("version", "date", "run_id", "attempt", "job", "shard", "session_id")
    }
    body: dict[str, Any]
    if kind == "monitor.stop":
        body = {"reason": "completed"}
        emitter = m["operator_emitter_id"]
    else:
        emitter = m["workers"][worker]["emitter_id"]
        body = {key: copy.deepcopy(m["workers"][worker][key]) for key in ("target", "server")}
        if kind == "worker.register":
            body["memory_profiling_enabled"] = m["controls"]["memory_profiling_enabled"]
        else:
            body.update({key: m["windows"][worker][key] for key in ("window_id", "item_id")})
    value = {
        **address,
        "kind": kind,
        "event_id": str(uuid4()),
        "reply_to": None,
        "emitter_id": emitter,
        "sequence": sequence,
        "emitted_at": "2026-10-10T12:00:00Z",
        "body": body,
    }
    HostEvent.model_validate(value)
    return value


def prepare(root: Path, *, memory: bool, periodic: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    root.mkdir(parents=True)
    m = manifest()
    m["controls"]["memory_profiling_enabled"] = memory
    m["controls"]["resource_interval_seconds"] = 1.0 if periodic else 0.0
    m["named_inputs"] = [
        {"name": "resources", "source": "proc.stat", "relative_path": "captures/resources.json"}
    ]
    recorded = fixture()["replay"]
    # Bind the captured worker to this test's process without running a reference collector.
    pid = os.getpid()
    m["workers"][0]["target"]["pid"] = pid
    for frame in recorded["frames"]:
        for process in frame["processes"]:
            if process["target"]["pid"] == 200:
                process["target"]["pid"] = pid
                for key in ("stat_before", "stat_after"):
                    process[key]["value"] = process[key]["value"].replace("200 ", f"{pid} ", 1)
        frame["population"]["value"] = [
            copy.deepcopy(process)
            for process in frame["processes"]
            if process["comm"]["value"].strip().startswith("python")
        ]
        unrelated = copy.deepcopy(frame["population"]["value"][1])
        unrelated["target"]["pid"] = 400
        for key in ("stat_before", "stat_after"):
            unrelated[key]["value"] = unrelated[key]["value"].replace("300 ", "400 ", 1)
        unrelated["status"]["value"] = "VmRSS: 100 kB\nVmHWM: 120 kB\nRssAnon: 90 kB\n"
        frame["population"]["value"].append(unrelated)
    actions: list[dict[str, Any]] = []
    for worker in range(2):
        actions.extend(
            [
                {"frame": 0, "at_ms": 0, "event": event(m, "worker.register", worker, 1)},
                {"frame": 0, "at_ms": 0, "event": event(m, "window.begin", worker, 2)},
            ]
        )
    actions.extend([{"frame": i, "at_ms": i * 1000, "event": None} for i in (1, 2)])
    for worker in range(2):
        actions.append({"frame": 3, "at_ms": 3000, "event": event(m, "window.end", worker, 3)})
    actions.append({"frame": 3, "at_ms": 3000, "event": event(m, "monitor.stop", 0, 1)})
    recorded["actions"] = actions
    HostSessionManifest.model_validate(m)
    (root / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    config = json.loads((ROOT / "config/host-telemetry-experiment.json").read_bytes())
    for key in ("controls", "limits", "capture_limits"):
        config[key] = m[key]
    (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
    capture = root / m["event_root"] / "captures/resources.json"
    capture.parent.mkdir(parents=True)
    capture.write_text(json.dumps(recorded), encoding="utf-8")
    return m, recorded


def run(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            str(binary()),
            *args,
            "--workspace",
            str(root),
            "--manifest",
            "manifest.json",
            "--config",
            "config.json",
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize(
    ("memory", "periodic"), [(True, True), (True, False), (False, True), (False, False)]
)
def test_native_windows_and_plain_artifacts_match_fixed_captured_expectations(
    memory: bool,
    periodic: bool,
) -> None:
    root = ROOT / "backend/var/d4-python" / str(uuid4())
    m, _ = prepare(root, memory=memory, periodic=periodic)
    result = run(root, "resource-replay", "--snapshot", "resources", "--artifact-root", "artifacts")
    assert result.returncode == 0, result.stderr.decode()
    events = [HostEvent.model_validate(value) for value in json.loads(result.stdout)]
    windows = [value.body for value in events if isinstance(value.body, WindowResultBody)]
    assert len(windows) == 2
    first = next(value for value in windows if str(value.window_id) == m["windows"][0]["window_id"])
    native_cells = first.cells.model_dump()
    expected_cells = fixture()["expected_periodic"]
    if not periodic:
        expected_cells.update(cpu_busy_min=50.0, os_mem_available_min_bytes=768000)
    for window in windows:
        worker = next(
            m["workers"][index]
            for index, declared in enumerate(m["windows"])
            if declared["window_id"] == str(window.window_id)
        )
        expected = dict(expected_cells)
        if memory:
            if worker["target"]["pid"] == 300:
                expected.update(python_rss_bytes=81920, python_rss_anon_bytes=71680)
        else:
            expected = {
                key: value
                if key
                in {"cpu_busy_pct", "cpu_busy_max", "cpu_busy_min", "cpu_steal_pct", "load_1m"}
                else None
                for key, value in expected.items()
            }
        assert window.cells.model_dump() == expected
    if memory:
        assert native_cells == expected_cells
        native_sample = json.loads((root / "artifacts/rss-samples.jsonl").read_bytes())
        native_rollcall = [
            json.loads(line)
            for line in (root / "artifacts/python-procs.jsonl").read_text().splitlines()
        ]
        assert native_sample == {
            "ts": "2026-10-10T12:00:00Z",
            "llama_vmrss_kb": 400,
            "llama_vmhwm_kb": 500,
            "python_vmrss_kb": 350,
            "python_vmhwm_kb": 420,
            "python_procs": 3,
            "mem_total_kb": 1000,
            "mem_available_kb": 800,
            "committed_as_kb": 900,
            "cgroup_current_bytes": 123456,
        }
        expected_rollcall = [
            {
                "ts": "2026-10-10T12:00:00Z",
                "pid": pid,
                "comm": comm,
                "vmrss_kb": rss,
                "vmhwm_kb": hwm,
                "exe": None,
                "args": args,
            }
            for pid, comm, rss, hwm, args in [
                (os.getpid(), "python3", 200, 250, "-u -m idhazh"),
                (300, "python3.12", 50, 0, None),
                (400, "python3.12", 100, 120, None),
            ]
        ]
        assert native_rollcall == sorted(expected_rollcall, key=lambda row: str(row["pid"]))
        assert "secret-not-exported" not in json.dumps(native_rollcall)
        statuses = [
            json.loads(line)
            for line in (root / "artifacts/server-rss-samples.jsonl").read_text().splitlines()
        ]
        assert statuses == [
            {"VmRSS": "400 kB", "VmHWM": "500 kB"},
            {"VmRSS": "800 kB", "VmHWM": "900 kB"},
            {"VmRSS": "250 kB", "VmHWM": "300 kB"},
            {"VmRSS": "350 kB", "VmHWM": "450 kB"},
        ]
        assert (root / "artifacts/cgroup-memory-peak.txt").read_text().strip() == "234567"
    else:
        assert not (root / "artifacts").exists()
        assert not any(value.kind in ("job.sample", "process.rollcall") for value in events)
        for key in ("cpu_busy_pct", "cpu_busy_max", "cpu_busy_min", "cpu_steal_pct", "load_1m"):
            assert native_cells[key] == expected_cells[key]
        assert all(
            value is None
            for key, value in native_cells.items()
            if key
            not in {
                "cpu_busy_pct",
                "cpu_busy_max",
                "cpu_busy_min",
                "cpu_steal_pct",
                "load_1m",
            }
        )
        assert {value.reason for value in first.unavailable} == {"disabled"}
    for value in events:
        path = root / m["event_root"] / "results" / f"{value.event_id}.json"
        raw = path.read_bytes()
        assert HostEvent.model_validate_json(raw) == value
        before = hashlib.sha256(raw).hexdigest()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert not (root / "state").exists()
    (root / "proof.json").write_bytes(result.stdout)


def test_cargo_harness_native_bytes_are_required_and_independently_readable() -> None:
    root = ROOT / "backend/var/d4-native-replay"
    proof = root / "native-proof.json"
    assert proof.is_file(), (
        "Run Cargo process_lifecycle first; native harness evidence is required."
    )
    events = [HostEvent.model_validate(value) for value in json.loads(proof.read_bytes())]
    for value in events:
        raw = (root / manifest()["event_root"] / "results" / f"{value.event_id}.json").read_bytes()
        assert HostEvent.model_validate_json(raw) == value


def test_compiled_cli_ack_timeout_returns_typed_unavailable_not_python_fallback() -> None:
    root = ROOT / "backend/var/d4-python" / str(uuid4())
    m, _ = prepare(root, memory=False, periodic=False)
    m["limits"]["ack_timeout_ms"] = 1
    m["limits"]["poll_ms"] = 1
    config = json.loads((root / "config.json").read_bytes())
    config["limits"] = m["limits"]
    (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    (root / "command.json").write_bytes(
        (json.dumps(event(m, "window.begin", 0, 2)) + "\n").encode("utf-8")
    )
    sent = run(root, "event-send", "--command", "command.json")
    assert sent.returncode == 0, sent.stderr.decode()
    command_id = json.loads((root / "command.json").read_bytes())["event_id"]
    assert sent.stdout.decode().strip() == f"{m['event_root']}/inbox/{command_id}.json"
    result = run(root, "event-wait", "--command", "command.json")
    assert result.returncode == 0, result.stderr.decode()
    unavailable = WindowResultBody.model_validate_json(result.stdout)
    assert unavailable.status == "incomplete"
    assert {value.reason for value in unavailable.unavailable} == {"disabled", "timed_out"}


def test_resource_replay_refuses_oversized_or_foreign_source_evidence() -> None:
    root = ROOT / "backend/var/d4-python" / str(uuid4())
    m, recorded = prepare(root, memory=True, periodic=True)
    recorded["frames"][0]["proc_stat"]["value"] = "x" * (
        m["capture_limits"]["max_proc_text_bytes"] + 1
    )
    path = root / m["event_root"] / "captures/resources.json"
    path.write_text(json.dumps(recorded), encoding="utf-8")
    result = run(root, "resource-replay", "--snapshot", "resources", "--artifact-root", "artifacts")
    assert result.returncode != 0
    assert b"cap" in result.stderr
    assert not (root / "artifacts").exists()


@pytest.mark.parametrize(
    ("busy", "idle", "expected"), [(107, 3893, 2.67), (45, 3955, 1.12), (115, 3885, 2.88)]
)
def test_native_decimal_half_cpu_results_match_fixed_expectations(
    busy: int, idle: int, expected: float
) -> None:
    root = ROOT / "backend/var/d4-python" / str(uuid4())
    m, recorded = prepare(root, memory=False, periodic=False)
    first = "cpu 0 0 0 0 0 0 0 0\n"
    last = f"cpu {busy} 0 0 {idle} 0 0 0 0\n"
    recorded["frames"][0]["proc_stat"]["value"] = first
    recorded["frames"][3]["proc_stat"]["value"] = last
    (root / m["event_root"] / "captures/resources.json").write_bytes(json.dumps(recorded).encode())
    result = run(root, "resource-replay", "--snapshot", "resources")
    assert result.returncode == 0, result.stderr.decode()
    windows = [
        value["body"] for value in json.loads(result.stdout) if value["kind"] == "window.result"
    ]
    assert len(windows) == 2
    for window in windows:
        assert window["cells"]["cpu_busy_pct"] == expected
