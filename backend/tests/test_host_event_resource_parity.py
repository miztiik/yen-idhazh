"""Do compiled Rust resource files match unchanged Python readers on the exact same population?"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from idhazh.contracts.host_events import HostEvent, HostSessionManifest, WindowResultBody
from idhazh.telemetry import host
from utilities import memory_sampler

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
    # This is the actual Python reference worker, not a dummy sampler or extra process.
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


def write_frame(root: Path, frame: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)

    def write(path: Path, value: str) -> None:
        staged = path.with_name(path.name + ".new")
        staged.write_text(value, encoding="utf-8", newline="\n")
        staged.replace(path)

    for leaf, key in (("loadavg", "loadavg"), ("meminfo", "meminfo")):
        write(root / leaf, frame[key]["value"])
    processes = {
        process["target"]["pid"]: process
        for process in [
            *frame["processes"],
            *frame["population"]["value"],
        ]
    }
    for pid, process in processes.items():
        entry = root / str(pid)
        entry.mkdir(exist_ok=True)
        for leaf, key in (
            ("stat", "stat_after"),
            ("status", "status"),
            ("comm", "comm"),
            ("cmdline", "cmdline"),
        ):
            value = process[key]["value"]
            if value is not None:
                write(entry / leaf, value)
    write(root / "stat", frame["proc_stat"]["value"])


@contextmanager
def reference_paths(root: Path) -> Iterator[None]:
    names = ("PROC", "PROC_STAT", "LOADAVG", "MEMINFO")
    paths = {name: vars(host)[name] for name in names}
    vars(host).update(
        dict(zip(names, (root, root / "stat", root / "loadavg", root / "meminfo"), strict=True))
    )
    try:
        yield
    finally:
        vars(host).update(paths)


def reference_cells(root: Path, frames: list[dict[str, Any]], periodic: bool) -> dict[str, Any]:
    # Immutable frame directories avoid replacing a file while Windows has it open.
    sources = [root / str(index) for index in range(4)]
    for source, frame in zip(sources, frames, strict=True):
        write_frame(source, frame)
    with reference_paths(sources[0]):
        watch = host.Watch(interval_s=0.01 if periodic else 0.0, server_pid=100)
        watch.__enter__()
        try:
            if periodic:
                for index in (1, 2):
                    # Real Python sampling thread reads the generated kernel files.
                    before = len(watch._busy)
                    source = sources[index]
                    vars(host).update(
                        PROC=source,
                        PROC_STAT=source / "stat",
                        LOADAVG=source / "loadavg",
                        MEMINFO=source / "meminfo",
                    )
                    available = host._kb_keys(frames[index]["meminfo"]["value"], ("MemAvailable",))[
                        "MemAvailable"
                    ]
                    deadline = time.monotonic() + 5
                    while (
                        len(watch._busy) == before
                        or watch._last.cpu_stat != frames[index]["proc_stat"]["value"]
                        or watch._last.mem_available_bytes != available
                    ) and time.monotonic() < deadline:
                        time.sleep(0.005)
                    assert len(watch._busy) > before, "unchanged Python reference did not sample"
                    assert watch._last.mem_available_bytes == available
                watch._stop.set()
                assert watch._thread is not None
                watch._thread.join(timeout=5)
                assert not watch._thread.is_alive()
            source = sources[3]
            vars(host).update(
                PROC=source,
                PROC_STAT=source / "stat",
                LOADAVG=source / "loadavg",
                MEMINFO=source / "meminfo",
            )
            return watch.close().cells()
        finally:
            watch._stop.set()
            if watch._thread is not None:
                watch._thread.join(timeout=5)


@pytest.mark.parametrize(
    ("memory", "periodic"), [(True, True), (True, False), (False, True), (False, False)]
)
def test_native_windows_and_plain_artifacts_match_unchanged_real_python_reads(
    memory: bool,
    periodic: bool,
) -> None:
    root = ROOT / "backend/var/d4-python" / str(uuid4())
    m, recorded = prepare(root, memory=memory, periodic=periodic)
    result = run(root, "resource-replay", "--snapshot", "resources", "--artifact-root", "artifacts")
    assert result.returncode == 0, result.stderr.decode()
    events = [HostEvent.model_validate(value) for value in json.loads(result.stdout)]
    windows = [value.body for value in events if isinstance(value.body, WindowResultBody)]
    assert len(windows) == 2
    first = next(value for value in windows if str(value.window_id) == m["windows"][0]["window_id"])
    native_cells = first.cells.model_dump()
    reference = reference_cells(root / "reference-proc", recorded["frames"], periodic)
    write_frame(root / "reference-workers", recorded["frames"][3])
    for window in windows:
        worker = next(
            m["workers"][index]
            for index, declared in enumerate(m["windows"])
            if declared["window_id"] == str(window.window_id)
        )
        expected = dict(reference)
        if memory:
            with reference_paths(root / "reference-workers"):
                status = host.status_bytes(worker["target"]["pid"])
            expected["python_rss_bytes"] = status["VmRSS"]
            expected["python_rss_anon_bytes"] = status["RssAnon"]
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
        assert native_cells == reference
        if periodic:
            assert native_cells == fixture()["expected_periodic"]
        proc = root / "reference-job-proc"
        write_frame(proc, recorded["frames"][0])
        cgroup = root / "reference-cgroup-current"
        cgroup.write_text(recorded["frames"][0]["cgroup_current"]["value"], encoding="utf-8")
        sample, rollcall = memory_sampler.sample_once(
            100,
            proc_root=proc,
            cgroup_paths=(cgroup,),
            now="2026-10-10T12:00:00Z",
        )
        native_sample = json.loads((root / "artifacts/rss-samples.jsonl").read_bytes())
        native_rollcall = [
            json.loads(line)
            for line in (root / "artifacts/python-procs.jsonl").read_text().splitlines()
        ]
        assert native_sample == sample
        assert native_rollcall == rollcall
        assert native_sample["python_procs"] == 3
        assert "-u -m idhazh" in {row["args"] for row in native_rollcall}
        assert "secret-not-exported" not in json.dumps(native_rollcall)
        statuses = [
            json.loads(line)
            for line in (root / "artifacts/server-rss-samples.jsonl").read_text().splitlines()
        ]
        expected_statuses = []
        for index in (0, 1, 2, 3):
            write_frame(proc, recorded["frames"][index])
            expected_statuses.append(memory_sampler.read_status(100, proc_root=proc))
        assert statuses == expected_statuses
        assert (root / "artifacts/cgroup-memory-peak.txt").read_text().strip() == recorded[
            "frames"
        ][3]["cgroup_peak"]["value"].strip()
        summary = subprocess.run(
            [sys.executable, str(ROOT / "backend/utilities/memory_sampler.py"), "summarize"],
            cwd=root / "artifacts",
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert summary.returncode == 0, summary.stderr.decode()
        assert b"peak llama VmHWM 500 kB, peak python VmHWM 420 kB" in summary.stderr
        assert b"most the two held at once 750 kB, n=1 samples" in summary.stderr
    else:
        assert not (root / "artifacts").exists()
        assert not any(value.kind in ("job.sample", "process.rollcall") for value in events)
        for key in ("cpu_busy_pct", "cpu_busy_max", "cpu_busy_min", "cpu_steal_pct", "load_1m"):
            assert native_cells[key] == reference[key]
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


@pytest.mark.parametrize(("busy", "idle"), [(107, 3893), (45, 3955), (115, 3885)])
def test_native_decimal_half_cpu_results_match_unchanged_python(busy: int, idle: int) -> None:
    root = ROOT / "backend/var/d4-python" / str(uuid4())
    m, recorded = prepare(root, memory=False, periodic=False)
    first = "cpu 0 0 0 0 0 0 0 0\n"
    last = f"cpu {busy} 0 0 {idle} 0 0 0 0\n"
    recorded["frames"][0]["proc_stat"]["value"] = first
    recorded["frames"][3]["proc_stat"]["value"] = last
    (root / m["event_root"] / "captures/resources.json").write_bytes(json.dumps(recorded).encode())
    result = run(root, "resource-replay", "--snapshot", "resources")
    assert result.returncode == 0, result.stderr.decode()
    expected = host.cpu_shares_between(first, last)
    assert expected is not None
    windows = [
        value["body"] for value in json.loads(result.stdout) if value["kind"] == "window.result"
    ]
    assert len(windows) == 2
    for window in windows:
        assert window["cells"]["cpu_busy_pct"] == expected.busy_pct
