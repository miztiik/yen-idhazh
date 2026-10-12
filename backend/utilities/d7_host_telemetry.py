"""Run one producer under the D7 Rust host-telemetry lifecycle.

The workflow wrapper deliberately owns the process boundary.  The child is
created before the monitor, but is held at a gate until the monitor has
published ``monitor.ready``.  This gives the runtime an immutable PID/start
identity while keeping the monitor-before-events ordering explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import signal
import stat
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

# Workflow steps invoke this file by path, so make the source-tree packages
# available even when the caller has not exported PYTHONPATH.
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from idhazh import config, ledger  # noqa: E402
from idhazh.contracts.base import ServerJob  # noqa: E402
from idhazh.contracts.host_events import (  # noqa: E402
    CaptureSource,
    CollectionControls,
    ExpectedWindow,
    HostEvent,
    HostProducerInvocation,
    HostSessionManifest,
    NamedHostInput,
    ProcessTarget,
)
from idhazh.contracts.host_output import (  # noqa: E402
    HostPublicationReceipt,
    HostWriteCompletion,
    HostWritePlan,
    HostWriterIdentity,
)
from idhazh.contracts.ledger_name import LedgerName  # noqa: E402
from idhazh.ledger import paths  # noqa: E402
from idhazh.telemetry.host_event_files import HostEventFiles  # noqa: E402
from idhazh.telemetry.host_evidence_inputs import (  # noqa: E402
    CONFIG_BYTES,
    NativeSettings,
    read_bytes,
    retain_native,
    settings,
    write_document,
    write_json,
)
from idhazh.telemetry.host_output_verify import (  # noqa: E402
    VerificationLimits,
    load_verification_document,
    verify_host_output,
)
from utilities.host_telemetry_reference import identity  # noqa: E402

GATE_CODE = (
    "import json,os,sys\n"
    "gate,env_file=sys.argv[1:3]; argv=sys.argv[3:]\n"
    "while not os.path.exists(gate):\n"
    "    import time; time.sleep(.05)\n"
    "with open(env_file, encoding='utf-8') as stream:\n"
    "    os.environ.update(json.load(stream))\n"
    "os.execvp(argv[0], argv)\n"
)
JOB_ALIASES = {"encoder-comparison": ServerJob.COLLECT.value}


def _native_command_supported(command: list[str]) -> bool:
    return _producer(command) is not None


def _producer(command: list[str]) -> tuple[str, list[str]] | None:
    if len(command) < 2:
        return None
    script = Path(command[1]).name
    if Path(command[1]).resolve() != (ROOT / "backend" / "utilities" / script).resolve():
        return None
    tail = command[2:]
    if script == "digest_publish.py" and len(tail) >= 2 and tail[0] == "run":
        if tail[1] in {"plan", "work", "assemble", "fingerprint", "job-clock"}:
            return tail[1], tail[2:]
    if script == "record_publish.py" and tail[:3] == ["run", "measure", "fingerprint"]:
        return "fingerprint", tail[3:]
    if script == "measure_llm.py" and tail[:1] == ["bench"]:
        return "bench", tail[1:]
    if script == "runtime_sweep.py" and tail[:1] == ["sweep"]:
        return "sweep", tail[1:]
    if script == "compare_summary_encoders.py" and tail[:1] in (["score"], ["collect"]):
        return tail[0], tail[1:]
    if script in {"gardener_publish.py", "council_publish.py"}:
        return ("run-tasks" if script == "gardener_publish.py" else "save_council_results"), tail
    return None


def _flag(command: list[str], name: str) -> str | None:
    values: list[str] = []
    for index, value in enumerate(command):
        if value == name:
            if index + 1 == len(command) or command[index + 1].startswith("--"):
                raise ValueError(f"{name} requires a value")
            values.append(command[index + 1])
        elif value.startswith(name + "="):
            values.append(value.partition("=")[2])
    if len(values) > 1:
        raise ValueError(f"{name} must be given only once")
    return values[0] if values else None


def _council_has_publishable_work(flags: list[str]) -> bool:
    settings = config.load(Path(_flag(flags, "--config-root") or config.DEFAULT_CONFIG_DIR))
    from idhazh.council.registry import tenants
    from idhazh.council.selection import for_dates, from_environment

    dates: list[str] = []
    index = 0
    while index < len(flags):
        value = flags[index]
        if value == "--date":
            if index + 1 == len(flags) or flags[index + 1].startswith("--"):
                raise ValueError("--date requires a value")
            dates.append(flags[index + 1])
            index += 2
            continue
        if value.startswith("--date="):
            dates.append(value.partition("=")[2])
        index += 1
    selected = from_environment(settings.council)
    if selected is None:
        if not dates:
            return False
        selected = for_dates(settings.council, tuple(dates))
    else:
        selected = selected.check(settings.council)
        if dates and tuple(dates) != selected.dates:
            raise ValueError("council selection differs from the producer dates")
    if not selected.names(publish=True):
        return False
    return bool(
        tenants(
            selected.names(),
            app=settings.app,
            council=settings.council,
            trials=selected.trials,
        )
    )


def _invocation(
    args: argparse.Namespace, job: ServerJob, source: config.Settings
) -> HostProducerInvocation:
    producer = _producer(args.command)
    if producer is None:
        raise ValueError("D7 command is not a declared Table W producer")
    stage, flags = producer
    expected_job = {
        "plan": ServerJob.PLAN,
        "work": ServerJob.WORK,
        "assemble": ServerJob.ASSEMBLE,
        "bench": ServerJob.RUNTIME,
        "sweep": ServerJob.RUNTIME,
        "score": ServerJob.COLLECT,
        "collect": ServerJob.COLLECT,
        "run-tasks": ServerJob.RUN_TASKS,
        "save_council_results": ServerJob.SAVE_COUNCIL_RESULTS,
    }.get(stage)
    child_job = _flag(flags, "--job")
    if Path(args.command[1]).name == "record_publish.py":
        expected_job = ServerJob(child_job or ServerJob.RUNTIME.value)
        if expected_job not in {ServerJob.RUNTIME, ServerJob.COLLECT}:
            raise ValueError("measurement producer requires its runtime or collect job")
    if (expected_job is not None and expected_job != job) or (child_job and child_job != job.value):
        raise ValueError("D7 job differs from the selected producer")
    child_run = _flag(flags, "--run-id")
    child_date = _flag(flags, "--date")
    child_execution = _flag(flags, "--execution")
    given_run = args.run_id or child_run or child_execution or os.environ.get("GITHUB_RUN_ID")
    if given_run is None:
        raise ValueError("D7 native runs require an explicit run address or execution")
    date = child_date or (given_run[:10] if not given_run.isdecimal() else None)
    date = date or datetime.now(UTC).date().isoformat()
    run_id = f"{date}-{given_run}" if given_run.isdecimal() else given_run
    if child_run is not None and child_run != run_id:
        raise ValueError("D7 run address differs from the producer invocation")
    execution = int(child_execution) if child_execution is not None else None
    child_attempt = _flag(flags, "--attempt")
    child_shard = _flag(flags, "--shard")
    if child_attempt is not None and int(child_attempt) != args.attempt:
        raise ValueError("D7 attempt differs from the producer invocation")
    runner_attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    if runner_attempt is not None and int(runner_attempt) != args.attempt:
        raise ValueError("D7 attempt differs from the executed runner invocation")
    if child_shard is not None and int(child_shard) != args.shard:
        raise ValueError("D7 shard differs from the producer invocation")
    commit = _flag(flags, "--commit")
    git_sha = args.git_sha or commit or os.environ.get("GITHUB_SHA")
    if git_sha is None or (commit is not None and commit != git_sha):
        raise ValueError("D7 execution SHA differs from the producer invocation")
    if os.environ.get("GITHUB_SHA") not in (None, git_sha):
        raise ValueError("D7 execution SHA differs from the checked-out runner invocation")
    fanout = _flag(flags, "--shards")
    return HostProducerInvocation(
        date=date,
        identity=HostWriterIdentity(
            run_id=run_id,
            attempt=args.attempt,
            job=job,
            shard=args.shard,
            producer="telemetry.silicon",
            git_sha=git_sha,
        ),
        command=tuple(args.command),
        stage=stage,
        execution=execution,
        shards=int(fanout) if fanout is not None else (1 if stage == "work" else None),
        host_enabled=source.app.observability.host_fingerprint
        and ledger.accepts_new_rows(LedgerName.HOST_FINGERPRINT, 0),
    )


def _selected_plan(
    invocation: HostProducerInvocation,
    source: config.Settings,
    session: Path,
    *,
    repo: Path = ROOT,
) -> tuple[HostProducerInvocation, tuple[ExpectedWindow, ...]]:
    if invocation.stage != "work":
        return invocation, ()
    if invocation.shards is None:
        raise ValueError("work producer must declare its selected fanout")
    shards = invocation.shards
    from idhazh.stages import common

    with ledger.use_registry(_ledger_registry(source)):
        plan = common._load_plan(
            invocation.date, invocation.identity.run_id, state_dir=repo / "state"
        )
    raw = plan.to_json().encode("utf-8")
    plan_path = session / "selected-plan.json"
    plan_path.write_bytes(raw)
    invocation = invocation.model_copy(
        update={
            "plan_path": plan_path.relative_to(repo).as_posix(),
            "plan_sha256": hashlib.sha256(raw).hexdigest(),
        }
    )
    return invocation, tuple(
        ExpectedWindow(window_id=uuid4(), item_id=item.item_id, emitter_id="worker")
        for index, item in enumerate(plan.items)
        if index % shards == invocation.identity.shard
    )


def _ledger_registry(source: config.Settings) -> paths.DoorRegistry | None:
    segments = tuple(
        value
        for value in (source.app.run.trial_state_dirname, source.app.run.trial_case_dirname)
        if value is not None
    )
    return ledger.overlay_registry(segments) if segments else None


def _host_ledger_prefix(source: config.Settings) -> str:
    registry = _ledger_registry(source)
    return "/".join(paths.entry(LedgerName.HOST_FINGERPRINT, registry=registry).prefix)


def _safe_session_path(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("D7 evidence path is outside its task-owned workspace")
    path = root
    for part in relative.parts:
        path = path / part
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise ValueError("D7 evidence path contains a link or reparse point")
    if path.resolve(strict=True) != path:
        raise ValueError("D7 evidence path is not canonical")
    return path


def _verified_receipt(
    workspace: Path,
    manifest: HostSessionManifest,
    limits: VerificationLimits,
    *,
    allow_incomplete_commands: bool = False,
) -> HostPublicationReceipt:
    root = workspace.resolve(strict=True)
    evidence_root = Path(*manifest.event_root.split("/")) / "writes"
    evidence_dir = _safe_session_path(root, evidence_root)
    if not evidence_dir.is_dir():
        raise RuntimeError("D7 monitor produced no typed host write evidence")

    names: list[str] = []
    for entry in evidence_dir.iterdir():
        names.append(entry.name)
        if len(names) > manifest.limits.max_files:
            raise ValueError("D7 write evidence exceeds the session file limit")
    plans: dict[UUID, Path] = {}
    completions: dict[UUID, tuple[int, Path]] = {}
    intents: dict[UUID, Path] = {}
    for name in names:
        path = _safe_session_path(root, evidence_root / name)
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("D7 write evidence must be regular files")
        if name.endswith(".plan.json"):
            raw_id = name.removesuffix(".plan.json")
            event_id = UUID(raw_id)
            if name != f"{event_id}.plan.json" or event_id in plans:
                raise ValueError("D7 host plan name is not canonical or is duplicated")
            plans[event_id] = path
            continue
        if name.endswith(".intent.json"):
            event_id = UUID(name.removesuffix(".intent.json"))
            if name != f"{event_id}.intent.json":
                raise ValueError("D7 host intent name is not canonical")
            intents[event_id] = path
            continue
        if ".completed-" not in name or not name.endswith(".json"):
            raise ValueError("D7 write evidence contains an unknown document")
        raw_id, raw_count = name.removesuffix(".json").split(".completed-", 1)
        event_id = UUID(raw_id)
        count = int(raw_count)
        if count < 1 or name != f"{event_id}.completed-{count}.json":
            raise ValueError("D7 host completion name is not canonical")
        old = completions.get(event_id)
        if old is None or count > old[0]:
            completions[event_id] = (count, path)

    if (
        not plans
        or not completions
        or not set(completions) <= set(plans)
        or (not allow_incomplete_commands and set(plans) != set(completions))
    ):
        raise RuntimeError("D7 native output lacks a matching typed plan and completion")
    identity_value = HostWriterIdentity(
        run_id=manifest.run_id,
        attempt=manifest.attempt,
        job=manifest.job,
        shard=manifest.shard,
        producer="telemetry.silicon",
        git_sha=manifest.git_sha,
    )
    loaded: list[tuple[int, HostWritePlan, HostWriteCompletion]] = []
    for event_id, plan_path in plans.items():
        plan_doc = load_verification_document(plan_path, root=root, limits=limits)
        plan = HostWritePlan.model_validate(plan_doc)
        if plan.event_id != event_id:
            raise ValueError("D7 evidence filename conflicts with its typed event identity")
        if plan.publication_identity != identity_value:
            raise ValueError("D7 host plan belongs to another publication invocation")
        if not plan.files:
            raise ValueError("D7 host plan contains no native file")
        if any(file.envelope.covers != manifest.date for file in plan.files):
            raise ValueError("D7 host plan describes another invocation day")
        if event_id in intents:
            intended = load_verification_document(intents[event_id], root=root, limits=limits)
            if HostWritePlan.model_validate(intended.get("plan")) != plan:
                raise ValueError("D7 retained native intent differs from its write plan")
            intended_event = HostEvent.model_validate(intended.get("event"))
            if (
                intended_event.kind != "host.result"
                or any(
                    getattr(intended_event, name) != getattr(manifest, name)
                    for name in ("date", "run_id", "attempt", "job", "shard", "session_id")
                )
                or intended_event.emitter_id != manifest.monitor_emitter_id
                or intended_event.reply_to != event_id
            ):
                raise ValueError("D7 retained native intent differs from its session")
        if event_id not in completions:
            continue
        completion_path = completions[event_id][1]
        completion_doc = load_verification_document(completion_path, root=root, limits=limits)
        completion = HostWriteCompletion.model_validate(completion_doc)
        if completion.event_id != event_id:
            raise ValueError("D7 completion filename conflicts with its typed event identity")
        written_at = max(file.envelope.written_at_ms for file in plan.files)
        loaded.append((written_at, plan, completion))

    loaded.sort(key=lambda item: item[0])
    target_root = manifest.output_roots[0]
    previous: HostWritePlan | None = None
    writes: dict[str, str] = {}
    total_bytes = 0
    for _, plan, completion in loaded:
        result = verify_host_output(
            plan,
            completion,
            workspace_root=root,
            target_root=target_root,
            publication_identity=identity_value,
            limits=limits,
            previous_plan=previous,
        )
        for file in result.files:
            published_path = f"{target_root}/{file.relative_path}"
            old_hash = writes.get(published_path)
            if old_hash is not None and old_hash != file.physical_sha256:
                raise ValueError("D7 verified host file changed across its write plans")
            if old_hash is None:
                writes[published_path] = file.physical_sha256
                total_bytes += file.size_bytes
                if len(writes) > limits.max_files or total_bytes > limits.max_total_bytes:
                    raise ValueError("D7 receipt exceeds aggregate file or byte limits")
        previous = plan

    return HostPublicationReceipt(
        version="2026-10-09",
        identity=identity_value,
        writes=writes,
    )


class _CancelledError(Exception):
    pass


def _binary(explicit: str | None) -> Path:
    candidate = Path(
        explicit
        or os.environ.get("IDHAZH_HOST_TELEMETRY_BINARY", "")
        or ROOT / "backend/var/rust-host-telemetry/release/idhazh-host-telemetry"
    )
    if not candidate.is_file():
        raise SystemExit(f"D7 Rust monitor is absent: {candidate}")
    return candidate.resolve()


def _boot_id(native: object) -> UUID:
    del native
    return UUID(Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip())


def _server_target(path: str | None, native: NativeSettings) -> ProcessTarget | None:
    pid_value = (
        Path(path).read_text(encoding="ascii").strip()
        if path
        else os.environ.get("IDHAZH_MODEL_SERVER_PID")
    )
    if not pid_value:
        return None
    pid = int(pid_value)
    return identity(pid, native)


def _write_env(values: dict[str, str]) -> None:
    path = os.environ.get("GITHUB_ENV")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}<<D7_EOF\n{value}\nD7_EOF\n")


def _manifest(
    *,
    workspace: Path,
    native: NativeSettings,
    controls: CollectionControls,
    run_id: str,
    attempt: int,
    job: ServerJob,
    shard: int,
    git_sha: str,
    worker: ProcessTarget,
    server: ProcessTarget | None,
    windows: tuple[ExpectedWindow, ...] = (),
    named_inputs: tuple[NamedHostInput, ...] = (),
    boot_id: UUID | None = None,
) -> HostSessionManifest:
    session_id = uuid4()
    event_root = f"backend/var/host-events/{run_id}/{attempt}/{job.value}/{shard}/{session_id}"
    manifest = HostSessionManifest.model_validate(
        {
            "version": "2026-10-10",
            "date": run_id[:10],
            "run_id": run_id,
            "attempt": attempt,
            "job": job.value,
            "shard": shard,
            "git_sha": git_sha,
            "session_id": str(session_id),
            "operator_emitter_id": "operator",
            "monitor_emitter_id": "monitor",
            "boot_id": str(boot_id or _boot_id(native)),
            "event_root": event_root,
            "output_roots": ["state"],
            "named_inputs": [entry.model_dump(mode="json") for entry in named_inputs],
            "workers": [
                {
                    "emitter_id": "worker",
                    "target": worker.model_dump(),
                    **({"server": server.model_dump()} if server else {}),
                }
            ],
            "windows": [entry.model_dump(mode="json") for entry in windows],
            "cpu_target": (server or worker).model_dump(),
            "cpu_target_role": "model_server" if server else "python_worker",
            "controls": controls.model_dump(),
            "limits": native.limits.model_dump(),
            "capture_limits": native.capture_limits.model_dump(),
        }
    )
    write_document(workspace / "manifest.json", manifest)
    return manifest


def _invoke(root: Path, session: Path, binary: Path, verb: str, *arguments: str) -> bytes:
    native, compare, _ = settings()
    output = session / f"command-{uuid4()}.log"
    with output.open("wb") as stream:
        child = subprocess.Popen(
            [
                str(binary),
                verb,
                "--workspace",
                str(root),
                "--manifest",
                (session / "manifest.json").relative_to(root).as_posix(),
                "--config",
                (session / "native-config.json").relative_to(root).as_posix(),
                *arguments,
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + compare.worker_timeout_seconds
        try:
            while child.poll() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"native {verb} exceeded its configured deadline")
                if output.stat().st_size > compare.max_command_output_bytes:
                    raise ValueError(f"native {verb} output exceeds its configured cap")
                time.sleep(native.limits.poll_ms / 1000)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=native.limits.drain_timeout_ms / 1000)
    raw = read_bytes(output, compare.max_command_output_bytes)
    if child.returncode:
        raise ValueError(f"native {verb} failed: {raw.decode('ascii', 'replace')}")
    return raw


def _controls(
    native: NativeSettings, source: config.Settings, memory: bool | None, job: ServerJob
) -> CollectionControls:
    observed = source.app.observability
    return CollectionControls.model_validate(
        native.controls.model_dump()
        | {
            "memory_profiling_enabled": (
                observed.memory_profiling_enabled if memory is None else memory
            ),
            "resource_interval_seconds": float(source.app.logging.waiting_heartbeat_seconds),
            "memcpy_enabled": (
                job in observed.host_fingerprint_bandwidth_jobs
                and observed.host_fingerprint_bandwidth_floor_mib > 0
            ),
            "memcpy_probe_mib": (
                observed.host_fingerprint_bandwidth_floor_mib or native.controls.memcpy_probe_mib
            ),
        }
    )


def _effective_config(
    workspace: Path, native: NativeSettings, controls: CollectionControls
) -> None:
    effective = native.model_dump(mode="json")
    effective["controls"] = controls.model_dump(mode="json")
    write_json(workspace / "native-config.json", effective)
    write_json(
        workspace / "effective-config.json",
        {
            "mode": "rust",
            "controls": controls.model_dump(mode="json"),
            "limits": native.limits.model_dump(mode="json"),
            "capture_limits": native.capture_limits.model_dump(mode="json"),
        },
    )


def _stop(
    workspace: Path,
    manifest: HostSessionManifest,
    reason: str,
    *,
    root: Path,
    binary: Path,
) -> None:
    def validate_event(event: HostEvent) -> None:
        if any(
            getattr(event, name) != getattr(manifest, name)
            for name in ("version", "date", "run_id", "attempt", "job", "shard", "session_id")
        ):
            raise ValueError("D7 stop evidence contains a foreign invocation")

    def validate_stopped(event: HostEvent) -> None:
        validate_event(event)
        command = HostEvent.model_validate_json(
            read_bytes(
                _safe_session_path(workspace, Path("stop.json")), manifest.limits.max_command_bytes
            )
        )
        validate_event(command)
        if (
            event.kind != "monitor.stopped"
            or event.emitter_id != manifest.monitor_emitter_id
            or command.kind != "monitor.stop"
            or command.emitter_id != manifest.operator_emitter_id
            or event.reply_to != command.event_id
        ):
            raise ValueError("D7 retained drain differs from its named stop command")

    if (workspace / "drained.json").exists():
        stopped = HostEvent.model_validate_json(
            read_bytes(
                _safe_session_path(workspace, Path("drained.json")),
                manifest.limits.max_result_bytes,
            )
        )
        validate_stopped(stopped)
        return
    sequence = 1
    # Probe, selected-target enrichment and clock are the three operator host commands.
    for index in range(1, 4):
        retained = workspace / f"operator-{index}.json"
        if not retained.exists():
            continue
        event = HostEvent.model_validate_json(
            read_bytes(
                _safe_session_path(workspace, Path(retained.name)),
                manifest.limits.max_command_bytes,
            )
        )
        validate_event(event)
        if event.emitter_id != manifest.operator_emitter_id or event.sequence != index:
            raise ValueError("D7 retained operator command has a foreign identity")
        sequence = index + 1
    count = 0
    for direction in ("inbox", "results", "consumed"):
        directory = HostEventFiles._safe_path(root, Path(manifest.event_root) / direction)
        if not directory.exists():
            continue
        for entry in directory.iterdir():
            count += 1
            if count > manifest.limits.max_files:
                raise ValueError("D7 stop evidence exceeds the session file cap")
            if entry.name.startswith("."):
                continue
            if not stat.S_ISREG(entry.lstat().st_mode):
                raise ValueError("D7 stop evidence must be regular event files")
            raw = read_bytes(
                _safe_session_path(root, entry.relative_to(root)),
                manifest.limits.max_result_bytes,
            )
            event = HostEvent.model_validate_json(raw)
            if entry.name != f"{event.event_id}.json":
                raise ValueError("D7 stop event filename differs from its typed identity")
            validate_event(event)
            if event.kind == "monitor.stopped":
                validate_stopped(event)
                retain_native(workspace / "drained.json", raw, manifest.limits.max_result_bytes)
                return
            if event.emitter_id == manifest.operator_emitter_id:
                sequence = max(sequence, event.sequence + 1)
    stop = HostEvent.model_validate(
        {
            **manifest.model_dump(
                include={"version", "date", "run_id", "attempt", "job", "shard", "session_id"},
                mode="json",
            ),
            "kind": "monitor.stop",
            "event_id": str(uuid4()),
            "reply_to": None,
            "emitter_id": manifest.operator_emitter_id,
            "sequence": sequence,
            "emitted_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "body": {"reason": reason},
        }
    )
    write_document(workspace / "stop.json", stop)
    relative = (workspace / "stop.json").relative_to(root).as_posix()
    _invoke(root, workspace, binary, "event-send", "--command", relative)
    raw = _invoke(root, workspace, binary, "event-wait", "--command", relative)
    stopped = HostEvent.model_validate_json(raw)
    validate_stopped(stopped)
    retain_native(workspace / "drained.json", raw, manifest.limits.max_result_bytes)


def _cleanup(workspace: Path, binary: str | None) -> None:
    root = workspace
    if not (workspace / "manifest.json").exists():
        manifest_name = os.environ.get("IDHAZH_HOST_TELEMETRY_MANIFEST")
        if not manifest_name:
            return
        workspace = Path(manifest_name).resolve(strict=True).parent
    else:
        root = ROOT
    monitor_file = workspace / "monitor.json"
    manifest_file = workspace / "manifest.json"
    if not monitor_file.exists() or not manifest_file.exists():
        return
    target = ProcessTarget.model_validate_json(read_bytes(monitor_file, CONFIG_BYTES))
    if target.pid == os.getpid():
        raise ValueError("D7 monitor cleanup cannot target its own Python launcher")
    try:
        _invoke(
            root,
            workspace,
            _binary(binary),
            "monitor-cleanup",
            "--pid",
            str(target.pid),
            "--start-ticks",
            str(target.start_ticks),
        )
    except ValueError as error:
        # A monitor which already acknowledged stop is allowed to have exited.
        if "No such process" not in str(error):
            raise


def run(args: argparse.Namespace) -> int:
    if args.mode == "legacy":
        return subprocess.run(
            args.command, env={**os.environ, "IDHAZH_HOST_TELEMETRY_MODE": "legacy"}, check=False
        ).returncode
    if args.mode != "rust":
        raise SystemExit(f"unsupported IDHAZH_HOST_TELEMETRY_MODE={args.mode!r}")
    producer = _producer(args.command)
    if producer is None:
        raise SystemExit(
            "D7 Rust publication is not wired for this producer; refusing to start "
            "a Python writer or publisher in native mode"
        )
    stage, flags = producer
    if stage == "save_council_results" and not _council_has_publishable_work(flags):
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("IDHAZH_HOST_TELEMETRY_")
        }
        print("D7 skipped native collection: no active council publishers", file=sys.stderr)
        result = subprocess.run(args.command, env=env, check=False)
        if result.returncode == 0:
            _write_env({"IDHAZH_HOST_TELEMETRY_SKIPPED": "council-no-active-publishers"})
        return result.returncode
    if os.name != "posix" or not Path("/proc").is_dir():
        raise SystemExit("D7 Rust host telemetry requires a Linux /proc runner")
    binary = _binary(args.binary)
    native, _, _ = settings()
    source = config.load(Path(_flag(flags, "--config") or config.DEFAULT_CONFIG_DIR))
    registry = _ledger_registry(source)
    memory = {"on": True, "off": False}.get(args.memory_profiling)
    child_memory = _flag(flags, "--memory-profiling")
    if child_memory is not None:
        if child_memory not in {"on", "off"}:
            raise ValueError("producer memory profiling must be 'on' or 'off'")
        selected_memory = child_memory == "on"
        if memory is not None and memory != selected_memory:
            raise ValueError("launcher and producer memory profiling controls differ")
        memory = selected_memory
    job_name = JOB_ALIASES.get(args.job, args.job)
    job = ServerJob(job_name)
    controls = _controls(native, source, memory, job)
    invocation = _invocation(args, job, source)
    run_id = invocation.identity.run_id
    workspace = (
        ROOT
        / "backend/var/d7-host-telemetry"
        / run_id
        / str(args.attempt)
        / job.value
        / str(args.shard)
        / str(uuid4())
    )
    workspace.mkdir(parents=True, exist_ok=False)
    invocation, windows = _selected_plan(invocation, source, workspace)
    if len(windows) > native.limits.max_windows:
        raise ValueError("selected RunPlan shard exceeds the native manifest window cap")
    write_document(workspace / "invocation.json", invocation)
    started = _flag(flags, "--job-started-at") or os.environ.get("JOB_STARTED_AT")
    started = started or str(int(datetime.now(UTC).timestamp()))
    (workspace / "job-start.txt").write_text(started + "\n", encoding="ascii", newline="\n")
    inputs = [
        NamedHostInput(
            name="start",
            source=CaptureSource.CLOCK_LOG,
            relative_path=(workspace / "job-start.txt").relative_to(ROOT).as_posix(),
        )
    ]
    for name, option, default in (
        ("log", "--server-log", "llama-server.log"),
        ("metrics", "--counters-file", "llama-metrics.prom"),
    ):
        path = Path(_flag(flags, option) or default)
        path = path if path.is_absolute() else ROOT / path
        relative = path.absolute().relative_to(ROOT).as_posix()
        inputs.append(
            NamedHostInput(name=name, source=CaptureSource.CLOCK_LOG, relative_path=relative)
        )
    gate = workspace / "release"
    child: subprocess.Popen[bytes] | None = None
    monitor: subprocess.Popen[bytes] | None = None
    manifest: HostSessionManifest | None = None
    child_rc: int | None = None
    drained = False
    status = "failed"

    def cancelled(signum: int, frame: object) -> None:
        nonlocal status
        del signum, frame
        status = "cancelled"
        raise _CancelledError

    signal.signal(signal.SIGTERM, cancelled)
    signal.signal(signal.SIGINT, cancelled)
    try:
        env_file = workspace / "worker-env.json"
        gate_command = [
            sys.executable,
            "-c",
            GATE_CODE,
            str(gate),
            str(env_file),
            *args.command,
        ]
        child = subprocess.Popen(
            gate_command,
            env={
                **os.environ,
                "IDHAZH_HOST_TELEMETRY_MODE": "rust",
                "IDHAZH_HOST_TELEMETRY_ENV_FILE": str(env_file),
                "GITHUB_RUN_ATTEMPT": str(args.attempt),
            },
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        worker = identity(child.pid, native)
        server = _server_target(args.server_pid_file, native)
        manifest = _manifest(
            workspace=workspace,
            native=native,
            controls=controls,
            run_id=run_id,
            attempt=args.attempt,
            job=job,
            shard=args.shard,
            git_sha=invocation.identity.git_sha,
            worker=worker,
            server=server,
            windows=windows,
            named_inputs=tuple(inputs),
        )
        _effective_config(workspace, native, controls)
        env = {
            "IDHAZH_HOST_TELEMETRY_MODE": "rust",
            "IDHAZH_HOST_TELEMETRY_WORKSPACE": str(ROOT),
            "IDHAZH_HOST_TELEMETRY_SESSION": str(workspace),
            "IDHAZH_HOST_TELEMETRY_ARTIFACT_ROOT": str(workspace / "native-artifacts"),
            "IDHAZH_HOST_TELEMETRY_MANIFEST": str(workspace / "manifest.json"),
            "IDHAZH_HOST_TELEMETRY_CONFIG": str(workspace / "native-config.json"),
            "IDHAZH_HOST_TELEMETRY_INVOCATION": str(workspace / "invocation.json"),
            "IDHAZH_HOST_TELEMETRY_EFFECTIVE_CONFIG": str(workspace / "effective-config.json"),
            "IDHAZH_HOST_TELEMETRY_WORKER_PID": str(worker.pid),
            "IDHAZH_HOST_TELEMETRY_WORKER_START_TICKS": str(worker.start_ticks),
            "IDHAZH_HOST_TELEMETRY_MEMORY_PROFILING": str(
                controls.memory_profiling_enabled
            ).lower(),
            "IDHAZH_HOST_TELEMETRY_RECEIPT": str(workspace / "receipt.json"),
            "IDHAZH_HOST_TELEMETRY_BINARY": str(binary),
            "IDHAZH_HOST_TELEMETRY_VERIFIED": "0",
        }
        if server:
            env.update(
                {
                    "IDHAZH_MODEL_SERVER_PID": str(server.pid),
                    "IDHAZH_MODEL_SERVER_START_TICKS": str(server.start_ticks),
                }
            )
        write_json(env_file, env)
        _write_env(env)
        log = (workspace / "monitor.log").open("wb")
        monitor = subprocess.Popen(
            [
                str(binary),
                "monitor",
                "--workspace",
                str(ROOT),
                "--manifest",
                (workspace / "manifest.json").relative_to(ROOT).as_posix(),
                "--config",
                (workspace / "native-config.json").relative_to(ROOT).as_posix(),
                "--artifact-root",
                (workspace / "native-artifacts").relative_to(ROOT).as_posix(),
                "--cache-multiple",
                str(source.app.observability.host_fingerprint_bandwidth_cache_multiple),
                "--ledger-prefix",
                _host_ledger_prefix(source),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        write_document(workspace / "monitor.json", identity(monitor.pid, native))
        ready_raw = _invoke(ROOT, workspace, binary, "event-wait")
        ready = HostEvent.model_validate_json(ready_raw)
        if ready.kind != "monitor.ready" or ready.session_id != manifest.session_id:
            raise RuntimeError("D7 Rust monitor did not become ready before worker release")
        retain_native(
            workspace / "ready.json",
            ready_raw,
            native.limits.max_result_bytes,
        )
        gate.touch()
        child_rc = child.wait()
        status = "completed" if child_rc == 0 else "failed"
        try:
            _stop(workspace, manifest, status, root=ROOT, binary=binary)
            drained = True
            if not invocation.host_enabled:
                output_evidence = HostEventFiles._safe_path(
                    ROOT, Path(manifest.event_root) / "writes"
                )
                if output_evidence.exists():
                    for _ in output_evidence.iterdir():
                        raise ValueError("disabled native host producer attempted a host write")
            receipt = (
                _verified_receipt(
                    ROOT,
                    manifest,
                    native.verification_limits,
                    allow_incomplete_commands=child_rc != 0,
                )
                if invocation.host_enabled
                else HostPublicationReceipt(
                    version="2026-10-09", identity=invocation.identity, writes={}
                )
            )
            write_document(workspace / "receipt.json", receipt)
            from idhazh.telemetry.host_publication import verify_host_publication

            verify_host_publication(
                receipt,
                repo=ROOT,
                identity=invocation.identity,
                date=invocation.date,
                limits=native.verification_limits,
                registry=registry,
                host_enabled=invocation.host_enabled,
            )
        except (ValueError, OSError, RuntimeError, TimeoutError) as error:
            if child_rc == 0:
                raise
            print(f"D7 failed producer evidence was refused: {error}", file=sys.stderr)
            _write_env({"IDHAZH_HOST_TELEMETRY_VERIFIED": "0"})
            return child_rc
        _write_env({"IDHAZH_HOST_TELEMETRY_VERIFIED": "1"})
        return child_rc
    finally:
        active = sys.exception()
        if child and child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        if monitor and monitor.poll() is None and manifest is not None and not drained:
            try:
                _stop(workspace, manifest, status, root=ROOT, binary=binary)
            except (ValueError, OSError, RuntimeError, TimeoutError) as error:
                monitor.terminate()
                monitor.wait(timeout=native.limits.drain_timeout_ms / 1000)
                if active is None and (child_rc is None or child_rc == 0):
                    raise
                if active is not None:
                    active.add_note(f"D7 native drain also failed: {type(error).__name__}")
                else:
                    print(f"D7 failed producer drain also failed: {error}", file=sys.stderr)
        if monitor:
            try:
                _cleanup(workspace, str(binary))
            except (ValueError, OSError, RuntimeError, TimeoutError) as error:
                if active is None and (child_rc is None or child_rc == 0):
                    raise
                if active is not None:
                    active.add_note(f"D7 native cleanup also failed: {type(error).__name__}")
                else:
                    print(f"D7 failed producer cleanup also failed: {error}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="verb", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument(
        "--mode", default=os.environ.get("IDHAZH_HOST_TELEMETRY_MODE", "legacy")
    )
    run_parser.add_argument("--job", required=True)
    run_parser.add_argument("--run-id")
    run_parser.add_argument(
        "--attempt", type=int, default=int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    )
    run_parser.add_argument("--shard", type=int, default=0)
    run_parser.add_argument("--git-sha")
    run_parser.add_argument("--binary")
    run_parser.add_argument("--server-pid-file")
    run_parser.add_argument(
        "--memory-profiling",
        choices=("inherit", "on", "off"),
        default="inherit",
    )
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    clean_parser = sub.add_parser("cleanup")
    clean_parser.add_argument("--workspace", required=True)
    clean_parser.add_argument("--binary")
    args = parser.parse_args()
    if args.verb == "run":
        if args.command and args.command[0] == "--":
            args.command = args.command[1:]
        if not args.command:
            raise SystemExit("D7 run requires a command after --")
        return run(args)
    _cleanup(Path(args.workspace), args.binary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
