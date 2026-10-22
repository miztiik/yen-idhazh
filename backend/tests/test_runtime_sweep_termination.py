"""Does cancellation reap only the sweep's owned processes and keep its failed status?"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from idhazh import config
from utilities.runtime_sweep import _cleanup_owned_processes, _termination_signals


@pytest.fixture
def owned_processes() -> Iterator[list[subprocess.Popen[bytes]]]:
    processes = [
        subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(5)"])
        for _ in range(3)
    ]
    try:
        yield processes
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=0.2)


def _handlers() -> tuple[object, object]:
    return signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)


def test_normal_cleanup_reaps_children_joins_sampler_and_restores_handlers(
    owned_processes: list[subprocess.Popen[bytes]],
) -> None:
    before = _handlers()
    stop = threading.Event()
    sampler = threading.Thread(target=stop.wait)
    sampler.start()
    try:
        with _termination_signals():
            _cleanup_owned_processes(owned_processes[0], owned_processes[1:], stop, sampler)
        assert all(process.returncode is not None for process in owned_processes)
        assert not sampler.is_alive()
        assert _handlers() == before
    finally:
        stop.set()
        sampler.join(timeout=5)


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_cancellation_reaps_owned_processes_and_restores_handlers(
    owned_processes: list[subprocess.Popen[bytes]], signum: int
) -> None:
    before = _handlers()
    stop = threading.Event()
    with pytest.raises(SystemExit) as caught:
        with _termination_signals():
            try:
                signal.raise_signal(signum)
            finally:
                signal.raise_signal(signum)  # A repeated request cannot interrupt cleanup.
                _cleanup_owned_processes(owned_processes[0], owned_processes[1:], stop, None)
    assert caught.value.code == 128 + signum
    assert stop.is_set()
    assert all(process.returncode is not None for process in owned_processes)
    assert _handlers() == before


def test_cancellation_during_acquisition_registers_the_child_before_unwinding() -> None:
    before = _handlers()
    workers: list[subprocess.Popen[bytes]] = []
    with pytest.raises(SystemExit) as caught:
        with _termination_signals():
            try:
                with _termination_signals(defer=True):
                    process = subprocess.Popen(
                        [sys.executable, "-B", "-c", "import time; time.sleep(5)"]
                    )
                    signal.raise_signal(signal.SIGTERM)
                    workers.append(process)
            finally:
                _cleanup_owned_processes(None, workers, threading.Event(), None)
    assert caught.value.code == 128 + signal.SIGTERM
    assert len(workers) == 1
    assert workers[0].returncode is not None
    assert _handlers() == before


@pytest.mark.parametrize("failure", [RuntimeError("work failed"), SystemExit(143)])
def test_cleanup_error_keeps_the_active_failure_and_reaps_every_child(
    owned_processes: list[subprocess.Popen[bytes]], failure: BaseException
) -> None:
    before = _handlers()
    with pytest.raises(type(failure)) as caught:
        with _termination_signals():
            try:
                raise failure
            finally:
                # Joining a real, unstarted thread raises after the process reaps.
                _cleanup_owned_processes(
                    owned_processes[0], owned_processes[1:], threading.Event(), threading.Thread()
                )
    assert caught.value is failure
    assert any("cleanup also failed" in note for note in failure.__notes__)
    assert all(process.returncode is not None for process in owned_processes)
    assert _handlers() == before


def test_cleanup_error_without_a_work_failure_is_not_success(
    owned_processes: list[subprocess.Popen[bytes]],
) -> None:
    before = _handlers()
    with pytest.raises(RuntimeError, match="cannot join thread before it is started"):
        _cleanup_owned_processes(
            owned_processes[0], owned_processes[1:], threading.Event(), threading.Thread()
        )
    assert all(process.returncode is not None for process in owned_processes)
    assert _handlers() == before


def test_cancellation_during_protected_cleanup_is_not_lost(
    owned_processes: list[subprocess.Popen[bytes]],
) -> None:
    before = _handlers()
    with pytest.raises(SystemExit) as caught:
        with _termination_signals():
            with _termination_signals(defer=True):
                signal.raise_signal(signal.SIGTERM)
                _cleanup_owned_processes(
                    owned_processes[0], owned_processes[1:], threading.Event(), None
                )
                assert all(process.returncode is not None for process in owned_processes)
    assert caught.value.code == 128 + signal.SIGTERM
    assert _handlers() == before


_SERVER = """\
import json
import os
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

def stop(signum, frame):
    Path("server.stopped").touch()
    raise SystemExit(128 + signum)

signal.signal(signal.SIGTERM, stop)
Path("server.pid").write_text(str(os.getpid()))
port = int(sys.argv[sys.argv.index("--port") + 1])
alias = sys.argv[sys.argv.index("--alias") + 1]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b"{}"
        else:
            name = "wrong-model" if os.environ["SCENARIO"] == "failure" else alias
            body = json.dumps({"data": [{"id": name}]}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass

with HTTPServer(("127.0.0.1", port), Handler) as server:
    server.serve_forever()
"""

_WORKER = """\
import os
import signal
import sys
import time
from pathlib import Path

shard = sys.argv[sys.argv.index("--shard") + 1]
def stop(signum, frame):
    Path(f"worker-{shard}.stopped").touch()
    raise SystemExit(128 + signum)

signal.signal(signal.SIGTERM, stop)
Path(f"worker-{shard}.pid").write_text(str(os.getpid()))
while True:
    time.sleep(0.01)
"""

_SWEEP = """\
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from utilities import runtime_sweep
from idhazh import config
from idhazh.stages import common
config.REPO_ROOT = Path.cwd()
common.STATE_ROOT = Path.cwd() / "state"
before = tuple(signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT))
try:
    raise SystemExit(runtime_sweep.main([
        "sweep", "--config", "candidate", "--date", "2026-10-13",
        "--execution", "1", "--candidate", "baseline",
        "--candidate-file", "fixture.gguf", "--candidate-id", sys.argv[3],
        "--threads", "1", "--threads-batch", "1", "--repeats", "2",
    ]))
finally:
    assert tuple(signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)) == before
    Path("sweep.restored").touch()
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _wait_for_file(path: Path, producer: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 15
    while not path.exists() and producer.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert path.exists(), f"fixture never reached {path.name}; exit={producer.poll()}"


def _fixture_sweep(root: Path, scenario: str) -> subprocess.Popen[bytes]:
    import socket

    settings = config.load()
    for name in [*(digest.path for digest in settings.digests), "config/appearance.json"]:
        target = root / "candidate" / Path(name).relative_to("config")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.REPO_ROOT / name, target)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    app = json.loads((root / "candidate/idhazh.json").read_text(encoding="utf-8"))
    app["observability"]["memory_profiling_enabled"] = True
    app["observability"]["host_fingerprint_bandwidth_floor_mib"] = 0
    app["model_server"]["base_url"] = f"http://127.0.0.1:{port}"
    _write(root / "candidate/idhazh.json", json.dumps(app))
    _write(root / "backend/bin/llama-server", f"#!{sys.executable}\n{_SERVER}")
    (root / "backend/bin/llama-server").chmod(0o755)
    _write(root / "idhazh/__init__.py", "")
    _write(root / "idhazh/__main__.py", _WORKER)
    (root / "backend/var/runtime-sweep").mkdir(parents=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("IDHAZH_HOST_TELEMETRY_")
    }
    env.update(
        IDHAZH_HOST_TELEMETRY_MODE="python",
        SCENARIO=scenario,
        PYTHONPATH=str(root),
        PYTHONDONTWRITEBYTECODE="1",
    )
    return subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-c",
            _SWEEP,
            str(config.REPO_ROOT / "backend"),
            str(port),
            settings.models.summarizer.id,
        ],
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


@pytest.mark.skipif(
    sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true",
    reason="Linux subprocess integration runs only in Ubuntu CI",
)
@pytest.mark.parametrize(
    ("scenario", "signum"),
    [
        ("setup", signal.SIGTERM),
        ("failure", None),
    ],
)
def test_sweep_cli_reaps_generated_processes(
    tmp_path: Path, scenario: str, signum: int | None
) -> None:
    producer = _fixture_sweep(tmp_path, scenario)
    try:
        if signum is not None:
            _wait_for_file(tmp_path / "server.pid", producer)
            producer.send_signal(signum)
        stdout, stderr = producer.communicate(timeout=15)
        assert producer.returncode == (128 + signum if signum is not None else 1), (
            stdout.decode(),
            stderr.decode(),
        )
        assert (tmp_path / "sweep.restored").exists()
        assert (tmp_path / "server.stopped").exists()
        assert not (tmp_path / "backend/var/runtime-sweep/runtime-summary.json").exists()
        if signum is None:
            assert b"wrong-model" in stderr
        # The named PID files were generated by this fixture, not a process-table scan.
        for pid_file in tmp_path.glob("*.pid"):
            assert not Path(f"/proc/{pid_file.read_text(encoding='utf-8')}").exists()
    finally:
        if producer.poll() is None:
            producer.kill()
        producer.communicate(timeout=5)
        for pid_file in tmp_path.glob("*.pid"):
            pid = int(pid_file.read_text(encoding="utf-8"))
            try:
                if sys.platform != "win32":
                    os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
