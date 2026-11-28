"""How do local Python callers keep the native fingerprint's verified bytes?"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from idhazh import completed_writes, config, ledger, run_context
from idhazh.atomic_write import write_atomic_bytes
from idhazh.contracts.base import JobName, PipelineName, TaskName
from idhazh.contracts.file_envelope import HOST_FINGERPRINT_PRODUCER, WriterIdentity
from idhazh.contracts.host_fingerprint import HostHardwareRow
from idhazh.publication_paths import IntegrityError, safe_file
from idhazh.telemetry import machine_api, machine_evidence
from idhazh.telemetry.host_control import enabled

_CLI = "services/host-fingerprints/src/index.ts"


def writer_for_task(
    run_id: str, commit_sha: str, *, pipeline: PipelineName, task: TaskName,
    shard: int = 0, attempt: int | None = None, job: JobName | None = None,
) -> WriterIdentity:
    return WriterIdentity.for_pipeline_task(
        run_id=run_id, git_sha=commit_sha, shard=shard,
        job=job if job is not None else (os.environ.get("GITHUB_JOB") or None),
        pipeline_name=pipeline, task_name=task, producer=HOST_FINGERPRINT_PRODUCER,
        attempt=run_context.run_attempt() if attempt is None else attempt,
    )


def _capture(
    date: str, writer: WriterIdentity,
    settings: config.Settings | config.GardenerSettings, *, ask_placement: bool,
) -> machine_evidence.VerifiedFile | None:
    expected = machine_evidence.ExpectedFile(writer, date)
    client = machine_api.MachineApi.for_job()
    if client is not None:
        response = client.fingerprint(date, writer, ask_placement=ask_placement)
        with ledger.use_registry(None):
            return (
                machine_evidence.verify_capture(
                    machine_api.private_state(config.REPO_ROOT), response, expected,
                )
                if isinstance(response, machine_api.Captured) else None
            )
    if machine_api.job_runtime_expected():
        raise machine_api.MachineApiError("prepared listener did not start")
    with TemporaryDirectory(prefix="idhazh-native-host-") as directory:
        root = Path(directory)
        request = machine_api.fingerprint_request(date, writer, ask_placement=ask_placement)
        context = root / "context.json"
        context.write_text(json.dumps(request), encoding="ascii")
        selected = root / "settings.json"
        selected.write_text(
            settings.app.model_dump_json(include={"observability", "ledger"}),
            encoding="utf-8",
        )
        private = root / "state"
        result = subprocess.run(
            ["bun", "run", "--no-install", _CLI, "--fingerprint", "--context", str(context),
             "--state-root", str(private), "--settings", str(selected)],
            cwd=config.REPO_ROOT, stdout=subprocess.PIPE, check=False,
        )
        if result.returncode:
            raise machine_api.MachineApiError("native fingerprint command failed")
        response = machine_api.CAPTURE_RESPONSE.validate_json(result.stdout)
        # The child files in its normal root. The caller's active registry
        # chooses the final destination, which may be an isolated trial.
        with ledger.use_registry(None):
            return (
                machine_evidence.verify_capture(private, response, expected)
                if isinstance(response, machine_api.Captured) else None
            )


def file_opening(
    *,
    date: str, writer: WriterIdentity, state: Path,
    settings: config.Settings | config.GardenerSettings, ask_placement: bool = True,
) -> tuple[HostHardwareRow | None, list[Path]]:
    if not enabled(settings.app.observability) or not settings.app.observability.host_fingerprint:
        return None, []
    try:
        reading = _capture(date, writer, settings, ask_placement=ask_placement)
        if reading is None:
            return None, []
        if not isinstance(reading.row, HostHardwareRow):
            raise IntegrityError("current native capture did not return the hardware-only row")
        relative = ledger.raw_path(
            state, machine_evidence.HOST, date, reading.envelope.file_id,
        ).relative_to(state).as_posix()
        path = safe_file(state, relative, exists=False)
        if path.exists():
            if safe_file(state, relative, exists=True).read_bytes() != reading.data:
                raise IntegrityError("native opening would replace different local bytes")
            completed_writes.record(path, reading.data)
        else:
            write_atomic_bytes(path, reading.data)
        return reading.row, [path]
    except (OSError, ValueError, KeyError, machine_api.MachineApiError) as error:
        machine_api.unavailable(writer.task_key, "opening fingerprint", error)
        return None, []
