"""How does one verified native model stay inside its owner's lifetime?"""

from __future__ import annotations

import ipaddress
import json
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, NoReturn, TypedDict
from urllib.parse import urlsplit
from uuid import uuid4

if TYPE_CHECKING:
    from idhazh.contracts.knobs.models import CompanionFile, ModelEntry
    from idhazh.contracts.model_server_pin import ModelServerPin
    from idhazh.contracts.task_performance import TaskPerformanceOutcome
    from utilities.model_refs import ModelFile

# Bound each readiness read, its evidence, and shutdown independently.
_PROBE_SECONDS: Final = 2.0
_POLL_SECONDS: Final = 0.2
_METADATA_BYTES: Final = 1 << 20
_SHUTDOWN_SECONDS: Final = 10.0
_FORCED_EXIT_SECONDS: Final = 5.0
_METRICS_READ_TIMEOUT_SECONDS: Final = 30
SERVING_COUNTERS_PATH: Final = Path("llama-metrics.prom")


class NativeListenerEvidenceTooLargeError(RuntimeError):
    """The bounded kernel listener evidence could not be inspected."""


def owns_listener(pid: int, port: int, limit: int, *, host: str | None = None) -> bool:
    """Prove listener ownership by inode, and optionally require the exact sole bind."""
    inodes: set[str] = set()
    with os.scandir(f"/proc/{pid}/fd") as entries:
        for entry in entries:
            try:
                target = str(Path(entry.path).readlink())
            except FileNotFoundError:
                continue
            if target.startswith("socket:[") and target.endswith("]"):
                inodes.add(target[8:-1])
    expected = None
    if host is not None:
        address = ipaddress.ip_address(host)
        packed = address.packed
        # Linux prints each address word as a host-endian integer in /proc/net/tcp{,6}.
        encoded_address = "".join(
            f"{int.from_bytes(packed[offset:offset + 4], sys.byteorder):08X}"
            for offset in range(0, len(packed), 4)
        )
        expected = ("tcp" if address.version == 4 else "tcp6", encoded_address, True)
    listeners: list[tuple[str, str, bool]] = []
    for table in ("tcp", "tcp6"):
        with Path(f"/proc/{pid}/net/{table}").open("rb") as stream:
            encoded = stream.read(limit + 1)
        if len(encoded) > limit:
            raise NativeListenerEvidenceTooLargeError("native listener evidence is too large")
        for row in encoded.decode("ascii").splitlines()[1:]:
            fields = row.split()
            if len(fields) <= 9 or fields[3] != "0A":
                continue
            address_hex, port_hex = fields[1].rsplit(":", 1)
            if int(port_hex, 16) != port:
                continue
            owned = fields[9] in inodes
            if expected is None and owned:
                return True
            listeners.append((table, address_hex, owned))
    return expected is not None and listeners == [expected]


def parent_bound_command(command: list[str]) -> list[str]:
    """Arm parent-death protection before exec, even if the owner exits during startup."""
    wrapper = shutil.which("setpriv") if sys.platform.startswith("linux") else None
    if wrapper is None:
        raise OSError("Native parent-death protection requires Linux setpriv.")
    return [
        wrapper, "--pdeathsig=KILL", "--", sys.executable,
        str(Path(__file__).resolve()), str(os.getpid()), *command,
    ]


def _exec_owned_native_child(args: list[str]) -> NoReturn:
    try:
        expected_parent = int(args[0])
        command = args[1:]
        if expected_parent > 0 and os.getppid() == expected_parent and command:
            os.execv(command[0], command)
    except (OSError, ValueError, IndexError):
        pass
    raise SystemExit(1)


def reap_owned_child(
    process: subprocess.Popen[bytes], *, shutdown_seconds: float, forced_exit_seconds: float,
) -> bool:
    """Reap only our child. Return whether graceful shutdown required escalation."""
    try:
        if process.poll() is not None:
            return False
        process.terminate()
        process.wait(timeout=shutdown_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=forced_exit_seconds)
        return True
    except BaseException:
        # A second cancellation during graceful shutdown must not abandon the child.
        process.kill()
        process.wait(timeout=forced_exit_seconds)
        raise
    return False


@dataclass(frozen=True, slots=True)
class OwnedNativeModel:
    """A live, verified child identity, valid only inside the owning context."""

    pin: ModelServerPin
    base_url: str
    model_id: str
    weights_path: Path
    weights_sha256: str
    metrics_enabled: bool

    def _owns_listener(self) -> bool:
        from idhazh.telemetry.host import process_start_ticks

        parts = urlsplit(self.base_url)
        if parts.hostname is None or parts.port is None:
            return False
        try:
            return (
                process_start_ticks(self.pin.pid) == self.pin.start_ticks
                and owns_listener(self.pin.pid, parts.port, _METADATA_BYTES, host=parts.hostname)
                and process_start_ticks(self.pin.pid) == self.pin.start_ticks
            )
        except (OSError, ValueError, NativeListenerEvidenceTooLargeError):
            return False

    def assert_owned(self) -> None:
        """Refuse to use this origin if its verified child no longer owns it."""
        if not self._owns_listener():
            raise RuntimeError("the verified native model no longer owns its listener")

    def observe(self, outcome: TaskPerformanceOutcome) -> dict[str, object] | None:
        """Capture the existing serving measurement; never signal the observed child."""
        SERVING_COUNTERS_PATH.unlink(missing_ok=True)
        observation_unavailable("weights_load_boundary_unobserved")
        return capture_serving_observation(
            self.pin, self.base_url, self.model_id, outcome, SERVING_COUNTERS_PATH,
            enabled=self.metrics_enabled, owns_port=self._owns_listener,
        )


_LifecycleAction = Literal["started", "ready", "stopped", "failed"]
_LifecycleCode = Literal["STARTUP_FAILED", "CHILD_EXITED", "CLEANUP_FAILED"]


class NativeModelLifecycleData(TypedDict):
    component: Literal["llama"]
    action: _LifecycleAction
    level: Literal["INFO", "ERROR"]
    code: _LifecycleCode | None


class NativeModelLifecycleEvent(TypedDict):
    specversion: Literal["1.0"]
    id: str
    source: Literal["/llama-server"]
    type: str
    time: str
    datacontenttype: Literal["application/json"]
    data: NativeModelLifecycleData


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _native_event(action: _LifecycleAction, code: _LifecycleCode | None = None) -> None:
    event: NativeModelLifecycleEvent = {
        "specversion": "1.0",
        "id": str(uuid4()),
        "source": "/llama-server",
        "type": f"llama-server.llama.{action}",
        "time": _utc_now(),
        "datacontenttype": "application/json",
        "data": {
            "component": "llama", "action": action,
            "level": "ERROR" if action == "failed" else "INFO", "code": code,
        },
    }
    # Losing diagnostics must not prevent cleanup or replace an actual work failure.
    with suppress(OSError, ValueError):
        print(json.dumps(event, separators=(",", ":")), file=sys.stderr, flush=True)


def _native_get(url: str, *, seconds: float, limit: int) -> bytes | None:
    """A local GET with a whole-request deadline, no redirect or ambient proxy."""
    flags = [
        "--fail", "--silent", "--noproxy", "*", "--max-time", str(seconds),
        "--max-filesize", str(limit),
    ]
    try:
        reply = subprocess.run(
            ["curl", "--disable", *flags, url], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=seconds, check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if reply.returncode or len(reply.stdout) > limit:
        return None
    return reply.stdout


def _probe_json(body: bytes | None) -> dict[str, object]:
    if body is not None:
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return parsed
        except (UnicodeError, ValueError):
            pass
    return {}


def _require_loaded_model(body: bytes, model: OwnedNativeModel) -> None:
    props = _probe_json(body)
    if (props.get("model_path"), props.get("model_alias")) != (
        str(model.weights_path), model.model_id,
    ):
        raise RuntimeError("native /props does not identify the selected model path and alias")


def _wait_for_native_model(
    process: subprocess.Popen[bytes], model: OwnedNativeModel, deadline: float,
) -> None:
    def get(route: str) -> bytes | None:
        remaining = deadline - time.monotonic()
        return _native_get(
            model.base_url + route, seconds=min(remaining, _PROBE_SECONDS), limit=_METADATA_BYTES,
        ) if remaining > 0 else None

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("the native model process exited before readiness")
        if model._owns_listener() and _probe_json(get("/health")).get("status") == "ok":
            props = get("/props")
            if props is not None:
                _require_loaded_model(props, model)
                model.assert_owned()
                if time.monotonic() < deadline:
                    return
        time.sleep(max(0.0, min(_POLL_SECONDS, deadline - time.monotonic())))
    raise TimeoutError("the native model did not prove readiness before its deadline")


def _native_origin(base_url: str) -> tuple[str, str, int]:
    from idhazh.contracts.knobs.model_server import port_of_base_url, resolve_base_url
    from idhazh.llm.server import loopback_url

    base = resolve_base_url(base_url)
    port = port_of_base_url(base)
    if port > 0 and base == loopback_url(port):
        return base, "127.0.0.1", port
    if port > 0 and base == f"http://[::1]:{port}":
        return base, "::1", port
    raise ValueError("model_server.base_url must name an explicit loopback HTTP address")


_OWNED_LAUNCH_FLAGS: Final = frozenset({
    "--host", "--port", "-m", "--model", "-a", "--alias", "-mu", "--model-url",
    "-hf", "-hfr", "--hf-repo", "--models-dir", "--models-preset",
})


def _require_matching_assets(entry: ModelEntry, files: Sequence[ModelFile]) -> None:
    declared: tuple[ModelEntry | CompanionFile, ...] = (entry, *entry.companion_files)
    if len(files) != len(declared) or any(
        (ref.repo, ref.revision, ref.file, ref.sha256, str(ref.byte_count or ""))
        != (asset.repo, asset.revision, asset.file, asset.sha256, asset.byte_count)
        for ref, asset in zip(declared, files, strict=True)
    ) or tuple(companion.flag or "" for companion in entry.companion_files) != tuple(
        asset.flag for asset in files[1:]
    ):
        raise ValueError("typed model entry differs from the assets selected for verification")
    for flag in (*entry.server, *(asset.flag for asset in files[1:])):
        if flag.partition("=")[0] in _OWNED_LAUNCH_FLAGS:
            raise ValueError("the model entry may not override native listener or model identity")


@contextmanager
def own_named_model(
    config_root: Path, *, models_file: str, startup_seconds: float, binary: Path,
    verify_files: Callable[[Sequence[ModelFile], Path], None], prepare_memlock: Callable[[], None],
) -> Iterator[OwnedNativeModel]:
    """Validate and prove a named local launch without changing the asset cache."""
    from idhazh import config
    from idhazh.llm.server import server_argv
    from utilities.model_refs import named_model_files

    if not math.isfinite(startup_seconds) or startup_seconds <= 0:
        raise ValueError("startup_seconds must be finite and positive")
    files = named_model_files(config_root, models_file)
    entry = config.load_models(config_root, models_file).summarizer
    base, host, port = _native_origin(config.load_app(config_root).model_server.base_url)
    _require_matching_assets(entry, files)
    verify_files(files, config_root)
    weights = Path(files[0].landed_path).resolve(strict=True)
    argv = server_argv(
        binary=binary.resolve(strict=True), weights=weights, model=entry, server=entry.server,
        port=port,
    )
    command = parent_bound_command([*argv, "--host", host])
    # Refuse an occupied address without attaching to or signalling its listener.
    with socket.socket(socket.AF_INET6 if host == "::1" else socket.AF_INET) as probe:
        probe.bind((host, port))
    prepare_memlock()
    binary.chmod(0o755)
    with _own_native_child(
        command, base, entry.id, weights, files[0].sha256, "--metrics" in entry.server,
        startup_seconds=startup_seconds, library_dir=binary.parent,
    ) as model:
        yield model


@contextmanager
def _own_native_child(
    command: list[str], base: str, model_id: str, weights: Path, sha256: str,
    metrics_enabled: bool, *, startup_seconds: float, library_dir: Path,
) -> Iterator[OwnedNativeModel]:
    from idhazh.contracts.model_server_pin import MODEL_SERVER_PIN_VERSION, ModelServerPin
    from idhazh.telemetry.host import process_start_ticks

    env = {key: value for key, value in os.environ.items() if not key.startswith("LLAMA_ARG_")}
    env["LD_LIBRARY_PATH"] = str(library_dir.resolve())
    process: subprocess.Popen[bytes] | None = None
    ready = False
    failure: BaseException | None = None
    try:
        started_at = _utc_now()
        deadline = time.monotonic() + startup_seconds
        # Native stdout/stderr can hold prompt text. Only emit the typed events below.
        process = subprocess.Popen(
            command, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
        )
        _native_event("started")
        ticks = process_start_ticks(process.pid)
        if ticks is None:
            raise RuntimeError("the native model's process start ticks could not be verified")
        pin = ModelServerPin(
            version=MODEL_SERVER_PIN_VERSION, pid=process.pid, start_ticks=ticks,
            started_at=started_at,
        )
        model = OwnedNativeModel(pin, base, model_id, weights, sha256, metrics_enabled)
        _wait_for_native_model(process, model, deadline)
        ready = True
        _native_event("ready")
        yield model
    except BaseException as error:
        failure = error
        if not ready:
            _native_event("failed", "STARTUP_FAILED")
        raise
    finally:
        if process is not None:
            code: _LifecycleCode = "CLEANUP_FAILED"
            try:
                early = process.poll() is not None
                forced = reap_owned_child(
                    process, shutdown_seconds=_SHUTDOWN_SECONDS,
                    forced_exit_seconds=_FORCED_EXIT_SECONDS,
                )
                if ready and early:
                    code = "CHILD_EXITED"
                    raise RuntimeError("the owned native model exited during work")
                if forced or (ready and process.returncode not in (0, -signal.SIGTERM)):
                    raise RuntimeError("the owned native model did not stop cleanly")
            except BaseException as cleanup:
                _native_event("failed", code)
                if failure is None:
                    raise
                failure.add_note(f"native model cleanup: {code} ({type(cleanup).__name__})")
            else:
                if ready:
                    _native_event("stopped")


def observation_unavailable(reason: str) -> None:
    print(f"::warning title=Model serving observation::{reason}", file=sys.stderr)


def capture_serving_observation(
    pin: ModelServerPin, base: str, model_id: str, outcome: TaskPerformanceOutcome,
    counters_path: Path, *, enabled: bool, owns_port: Callable[[], bool],
) -> dict[str, object] | None:
    """The shared counters-only operation; the owning caller decides when to stop."""
    from idhazh.llm.serving_metrics import CAPTURE_BYTES, retain_serving_capture

    if not enabled:
        observation_unavailable("metrics_configured_off")
        return None
    if not owns_port():
        observation_unavailable("metrics_listener_unverified")
        return None
    try:
        # curl applies its whole-request deadline; no redirects, ambient proxy or retries.
        flags = [
            "--fail", "--silent", "--show-error", "--noproxy", "*",
            "--max-time", str(_METRICS_READ_TIMEOUT_SECONDS),
            "--max-filesize", str(CAPTURE_BYTES),
        ]
        reply = subprocess.run(
            ["curl", "--disable", *flags, base + "/metrics"], stdout=subprocess.PIPE, check=False,
        )
    except OSError:
        observation_unavailable("metrics_unreadable")
        return None
    if reply.returncode != 0:
        observation_unavailable("metrics_unreadable")
        return None
    if not owns_port():
        observation_unavailable("metrics_listener_changed_during_read")
        return None
    if len(reply.stdout) > CAPTURE_BYTES:
        observation_unavailable("metrics_exceed_capture_bound")
        return None
    try:
        measurement: dict[str, object] | None = retain_serving_capture(
            counters_path, reply.stdout, subject_id=model_id, outcome=outcome,
            started_at=pin.started_at, finished_at=_utc_now(),
        )
    except ValueError:
        observation_unavailable("prompt_pair_invalid")
        return None
    if measurement is None:
        observation_unavailable("prompt_pair_incomplete")
    return measurement


if __name__ == "__main__":
    _exec_owned_native_child(sys.argv[1:])
