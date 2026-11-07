"""Use real owned pipes and named proc fixtures for pipeline integration."""

import json
import queue
import subprocess
import sys
import sysconfig
import threading
from pathlib import Path

from summary_eval_pipeline.contracts import Hardware
from summary_eval_pipeline.host_reader import MachineUsage
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator_cases.contract_examples import REPOSITORY

from summary_eval_tests.test_host_profile_reader_parity import (
    bridge_path,
    mapping,
    required_bun,
)


def owned_child_command(mode: str, *, script_path: Path | None = None) -> list[str]:
    interpreter = getattr(sys, "_base_executable", None)
    if not isinstance(interpreter, str):
        raise AssertionError("The lifetime case requires the actual CPython executable.")
    script = (
        "import runpy,site,sys; packages=sys.argv.pop(1); support=sys.argv.pop(1); "
        "pipeline=sys.argv.pop(1); backend=sys.argv.pop(1); service=sys.argv.pop(1); "
        "sys.path[:0]=[support,pipeline,backend,service,packages]; "
        "site.addsitedir(packages); runpy.run_path(sys.argv.pop(1),run_name='__main__')"
    )
    return [
        interpreter,
        "-c",
        script,
        sysconfig.get_path("purelib"),
        str(REPOSITORY / "services" / "summary_evaluator" / "tests"),
        str(REPOSITORY / ".github" / "scripts" / "summary-eval-tests"),
        str(REPOSITORY / "backend"),
        str(REPOSITORY / "services" / "summary_evaluator"),
        str(script_path or Path(__file__).with_name("owned_service_child.py")),
        mode,
    ]


def prepare_proc(directory: Path, *, closing: bool = False, memory: bool = True) -> None:
    fixture = REPOSITORY / "tests" / "fixtures" / "runtime"
    (directory / "stat").write_bytes(
        (
            fixture
            / (
                "2026-08-30-probe-proc-stat-at-end.txt"
                if closing
                else "2026-08-30-probe-proc-stat-at-start.txt"
            )
        ).read_bytes()
    )
    if memory:
        # Generated named input, not a replacement collector or HTTP response.
        (directory / "meminfo").write_text(
            "MemTotal: 8192 kB\nMemFree: 1024 kB\n"
            + ("MemAvailable: 2048 kB\n" if closing else "MemAvailable: 4096 kB\n"),
            encoding="ascii",
        )
    (directory / "vmstat").write_text("pgmajfault 1\n", encoding="ascii")


class NativeHostPipe:
    def __init__(
        self,
        proc_root: Path,
        *,
        platform: str = "linux",
        task_profile: dict[str, bool | int] | None = None,
        fail_report: bool = False,
    ) -> None:
        self.limit = load_pipeline_settings(REPOSITORY).max_response_bytes
        self.process = subprocess.Popen(
            [required_bun(), "run", "--no-install", str(bridge_path())],
            cwd=REPOSITORY,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
        )
        self.messages: queue.Queue[bytes] = queue.Queue(3)

        def read_output() -> None:
            assert self.process.stdout is not None
            while line := self.process.stdout.readline(self.limit + 1):
                self.messages.put_nowait(line)
            self.messages.put_nowait(b"")

        self.reader = threading.Thread(target=read_output, daemon=True)
        self.reader.start()
        self.closed: dict[str, object] | None = None
        assert self.process.stdin is not None
        self.process.stdin.write(
            json.dumps(
                {
                    "proc_root": str(proc_root),
                    "platform": platform,
                    "task_profile": task_profile or {},
                    "fail_report": fail_report,
                }
            ).encode()
            + b"\n"
        )
        self.process.stdin.flush()
        try:
            ready = self.read()
            assert ready["kind"] == "ready", ready
            self.hardware = Hardware.model_validate_json(json.dumps(ready["hardware"]))
            self.started = ready["profile_started"]
        except BaseException:
            self.process.stdin.close()
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
            self.reader.join(timeout=5)
            if self.process.stdout is not None:
                self.process.stdout.close()
            raise

    def read(self) -> dict[str, object]:
        assert self.process.stdout is not None
        try:
            # Include cold native-package loading before the collector can announce readiness.
            line = self.messages.get(timeout=60)
        except queue.Empty:
            self.process.kill()
            self.process.wait(timeout=5)
            raise AssertionError(
                "The native pipe did not return within its test deadline"
            ) from None
        assert line and len(line) <= self.limit, "The native pipe must return bounded metadata"
        return mapping(json.loads(line))

    def close(self, *, explicit: bool = True) -> tuple[bool, MachineUsage | None]:
        if self.closed is None:
            assert self.process.stdin is not None
            if explicit:
                self.process.stdin.write(b'{"kind":"stop","outcome":"success"}\n')
                self.process.stdin.flush()
            self.process.stdin.close()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
                raise AssertionError(
                    "The native collector did not close after parent EOF"
                ) from None
            self.closed = self.read()
            for stream in (self.process.stdout, self.process.stderr):
                if stream is not None:
                    stream.close()
        assert self.closed["kind"] == "closed"
        raw = self.closed["profile"]
        return (
            self.closed["clean"] is True,
            None if raw is None else MachineUsage.model_validate_json(json.dumps(raw)),
        )
