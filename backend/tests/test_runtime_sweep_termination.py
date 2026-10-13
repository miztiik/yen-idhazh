"""Does cancellation reap only the sweep's owned processes and keep its failed status?"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from idhazh import config
from utilities.runtime_sweep import _cleanup_owned_processes, _termination_signals


@pytest.fixture
def owned_processes() -> Iterator[list[subprocess.Popen[bytes]]]:
    processes = [
        subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(60)"])
        for _ in range(3)
    ]
    try:
        yield processes
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)


def _handlers() -> tuple[object, object]:
    return signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)


def test_normal_cleanup_reaps_children_and_restores_handlers(
    owned_processes: list[subprocess.Popen[bytes]],
) -> None:
    before = _handlers()
    with _termination_signals():
        _cleanup_owned_processes(owned_processes[0], owned_processes[1:])
    assert all(process.returncode is not None for process in owned_processes)
    assert _handlers() == before


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_cancellation_reaps_owned_processes_and_restores_handlers(
    owned_processes: list[subprocess.Popen[bytes]], signum: int
) -> None:
    before = _handlers()
    with pytest.raises(SystemExit) as caught:
        with _termination_signals():
            try:
                signal.raise_signal(signum)
            finally:
                signal.raise_signal(signum)  # A repeated request cannot interrupt cleanup.
                _cleanup_owned_processes(owned_processes[0], owned_processes[1:])
    assert caught.value.code == 128 + signum
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
                        [sys.executable, "-B", "-c", "import time; time.sleep(60)"]
                    )
                    signal.raise_signal(signal.SIGTERM)
                    workers.append(process)
            finally:
                _cleanup_owned_processes(None, workers)
    assert caught.value.code == 128 + signal.SIGTERM
    assert len(workers) == 1
    assert workers[0].returncode is not None
    assert _handlers() == before


@pytest.mark.parametrize("failure", [RuntimeError("work failed"), SystemExit(143)])
def test_cleanup_keeps_the_active_failure_and_reaps_every_child(
    owned_processes: list[subprocess.Popen[bytes]], failure: BaseException
) -> None:
    before = _handlers()
    with pytest.raises(type(failure)) as caught:
        with _termination_signals():
            try:
                raise failure
            finally:
                _cleanup_owned_processes(owned_processes[0], owned_processes[1:])
    assert caught.value is failure
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
                _cleanup_owned_processes(owned_processes[0], owned_processes[1:])
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
            Path("health.entered").touch()
            status = 503 if os.environ["SCENARIO"] == "health" else 200
            body = b"{}"
        else:
            status = 200
            name = "wrong-model" if os.environ["SCENARIO"] == "failure" else alias
            body = json.dumps({"data": [{"id": name}]}).encode()
        self.send_response(status)
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

# These launchers own actual fixture workers. They run no Rust collector and
# write no telemetry receipts; their final marker proves wait() reaped the child.
_LAUNCHER = """\
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

shard = sys.argv[sys.argv.index("--shard") + 1]
def stop(signum, frame):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise SystemExit(128 + signum)

signal.signal(signal.SIGTERM, stop)
child = subprocess.Popen(sys.argv[sys.argv.index("--") + 1:])
Path(f"launcher-{shard}.pid").write_text(str(os.getpid()))
try:
    raise SystemExit(child.wait())
finally:
    child.terminate()
    child.wait(timeout=5)
    Path(f"launcher-{shard}.draining").touch()
    deadline = time.monotonic() + 5
    while not Path("release-drain").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    Path(f"launcher-{shard}.reaped").touch()
"""

_SWEEP = """\
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from utilities import runtime_sweep
before = tuple(signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT))
try:
    if os.environ["FIXTURE_NATIVE"] == "1":
        with runtime_sweep._termination_signals():
            runtime_sweep.run_once(
                "baseline", {}, 1, 2, date="2026-10-13", execution=1,
                candidate="baseline", candidate_file="fixture.gguf",
                candidate_id=sys.argv[3], port=int(sys.argv[2]),
                config_root=Path("candidate"),
            )
    else:
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
    if not path.exists() and producer.poll() is not None:
        stdout, stderr = producer.communicate(timeout=5)
        pytest.fail(
            f"fixture never reached {path.name}; exit={producer.returncode}\n"
            f"{stdout.decode()}\n{stderr.decode()}"
        )
    assert path.exists(), f"fixture never reached {path.name}; exit={producer.poll()}"


def _fixture_sweep(root: Path, scenario: str, *, native: bool) -> subprocess.Popen[bytes]:
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
    app["model_server"]["base_url"] = f"http://127.0.0.1:{port}"
    _write(root / "candidate/idhazh.json", json.dumps(app))
    _write(root / "backend/bin/llama-server", f"#!{sys.executable}\n{_SERVER}")
    (root / "backend/bin/llama-server").chmod(0o755)
    _write(root / "idhazh/__init__.py", "")
    _write(root / "idhazh/__main__.py", _WORKER)
    _write(root / "backend/utilities/digest_publish.py", _WORKER)
    _write(root / "backend/utilities/d7_host_telemetry.py", _LAUNCHER)
    (root / "backend/var/runtime-sweep").mkdir(parents=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("IDHAZH_HOST_TELEMETRY_")
    }
    if native:
        # run_once exercises nested process ownership, not admission of a host session.
        env["IDHAZH_HOST_TELEMETRY_MODE"] = "rust"
    env.update(
        FIXTURE_NATIVE="1" if native else "0",
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
    ("scenario", "native", "signum"),
    [
        ("setup", False, signal.SIGTERM),
        ("health", False, signal.SIGTERM),
        ("work", False, signal.SIGINT),
        ("work", True, signal.SIGTERM),
        ("failure", False, None),
    ],
)
def test_sweep_cli_and_nested_launchers_reap_generated_processes(
    tmp_path: Path, scenario: str, native: bool, signum: int | None
) -> None:
    producer = _fixture_sweep(tmp_path, scenario, native=native)
    try:
        marker = {"setup": "server.pid", "health": "health.entered"}.get(
            scenario, "worker-1.pid" if native else "worker-0.pid"
        )
        if signum is not None:
            _wait_for_file(tmp_path / marker, producer)
            if native:
                _wait_for_file(tmp_path / "worker-0.pid", producer)
            producer.send_signal(signum)
            if native:
                _wait_for_file(tmp_path / "launcher-0.draining", producer)
                producer.send_signal(signum)
                (tmp_path / "release-drain").touch()
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
        if native:
            for shard in range(2):
                assert (tmp_path / f"launcher-{shard}.reaped").exists()
                assert (tmp_path / f"worker-{shard}.stopped").exists()
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
