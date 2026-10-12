"""Bounded, artifact-only Linux proof of the real launcher and producer recorder."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, SEED_COMMIT

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.host_output import HostPublicationReceipt
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import RunPlan
from idhazh.telemetry.host_evidence_inputs import NativeSettings
from idhazh.telemetry.host_publication import verify_host_publication
from utilities.model_runtime import server_identity
from utilities.runtime_sweep import native_memory

DAY = "2026-10-12"
EXECUTION = "771"
RUN = f"{DAY}-{EXECUTION}"
ATTEMPT = 2
LIVE = os.environ.get("IDHAZH_D7_LIVE_TEST") == "1"
RECORDER = """
import argparse
import time
from pathlib import Path
from idhazh import config
from idhazh.contracts.base import ServerJob
from idhazh.telemetry import job_machine

parser = argparse.ArgumentParser()
parser.add_argument("--config", type=Path)
parser.add_argument("--date")
parser.add_argument("--execution")
parser.add_argument("--commit")
parser.add_argument("--job")
parser.add_argument("--hold-seconds", type=float, default=0.0)
parser.add_argument("--exit-code", type=int, default=0)
args, _ = parser.parse_known_args()
settings = config.load(args.config)
with job_machine.record(
    date=args.date, run_id=f"{args.date}-{args.execution}", settings=settings,
    state_root=Path("state"), commit_sha=args.commit, job=ServerJob(args.job),
):
    sum(index * index for index in range(10000))
    time.sleep(args.hold_seconds)
if args.exit_code:
    raise SystemExit(args.exit_code)
"""


def bounded_config(destination: Path) -> Path:
    shutil.copytree(CONFIG_DIR, destination)
    sources = json.loads((destination / "sources.json").read_text(encoding="utf-8"))
    sources["feeds"] = []
    sources["salience"] = []
    (destination / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
    app_path = destination / "idhazh.json"
    app = json.loads(app_path.read_text(encoding="utf-8"))
    app["observability"]["host_fingerprint_bandwidth_floor_mib"] = 0
    app["run"]["trial_state_dirname"] = None
    app["run"]["trial_case_dirname"] = None
    app_path.write_text(json.dumps(app), encoding="utf-8")
    return destination


def test_generated_family_inputs_have_no_network_or_bandwidth_work(tmp_path: Path) -> None:
    selected = config.load(bounded_config(tmp_path / "config"))
    assert not selected.sources.feeds
    assert not selected.sources.salience
    assert selected.app.observability.host_fingerprint_bandwidth_floor_mib == 0


def isolate(root: Path) -> Path:
    bounded_config(root / "config")
    for package in ("idhazh", "utilities"):
        shutil.copytree(
            REPO_ROOT / "backend" / package,
            root / "backend" / package,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    return root


def exported(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    lines = iter(path.read_text(encoding="utf-8").splitlines())
    for line in lines:
        if "<<" in line:
            name, marker = line.split("<<", 1)
            value = next(lines)
            assert next(lines) == marker
            values[name] = value
        else:
            name, value = line.split("=", 1)
            values[name] = value
    return values


@pytest.mark.skipif(not LIVE or sys.platform != "linux", reason="isolated Ubuntu D7 gate only")
@pytest.mark.parametrize(
    ("job", "memory", "child_exit"),
    [
        (job, memory, 0)
        for job in (
            ServerJob.PLAN,
            ServerJob.WORK,
            ServerJob.ASSEMBLE,
            ServerJob.COLLECT,
            ServerJob.RUNTIME,
            ServerJob.RUN_TASKS,
            ServerJob.SAVE_COUNCIL_RESULTS,
        )
        for memory in ("on", "off")
    ]
    + [(ServerJob.RUNTIME, "on", 17)],
)
def test_real_native_family_lifecycle_keeps_single_writer_paths(
    tmp_path: Path,
    job: ServerJob,
    memory: str,
    child_exit: int,
    selected_server: tuple[int, int] | None = None,
) -> None:
    """Real digest/encoder capture; other families exercise their common recorder hook."""
    binary = Path(os.environ["IDHAZH_HOST_TELEMETRY_BINARY"]).resolve(strict=True)
    repo = isolate(tmp_path / "repo")
    address = [
        "--config",
        "config",
        "--date",
        DAY,
        "--execution",
        EXECUTION,
        "--commit",
        SEED_COMMIT,
    ]
    if job in {ServerJob.WORK, ServerJob.ASSEMBLE}:
        plan = RunPlan(
            version=RunPlan.schema_version(),
            date=DAY,
            run_id=RUN,
            generated_at=f"{DAY}T00:00:00Z",
            verticals=[],
            items=[],
        )
        ledger.persist(
            repo / "state",
            [plan],
            ledger=LedgerName.RUN_PLAN,
            covers=DAY,
            identity=WriterIdentity(
                run_id=RUN,
                attempt=ATTEMPT,
                job=ServerJob.PLAN,
                shard=0,
                producer="stages.plan",
                git_sha=SEED_COMMIT,
            ),
        )
    if job in {ServerJob.PLAN, ServerJob.WORK, ServerJob.ASSEMBLE}:
        child = [
            sys.executable,
            "backend/utilities/digest_publish.py",
            "run",
            job.value,
            *address,
            "--memory-profiling",
            memory,
        ]
    elif job == ServerJob.COLLECT:
        child = [
            sys.executable,
            "backend/utilities/record_publish.py",
            "run",
            "measure",
            "fingerprint",
            *address,
            "--job",
            job.value,
            "--memory-profiling",
            memory,
        ]
    else:
        script, prefix = {
            ServerJob.RUNTIME: ("measure_llm.py", ["bench"]),
            ServerJob.RUN_TASKS: ("gardener_publish.py", []),
            ServerJob.SAVE_COUNCIL_RESULTS: ("council_publish.py", []),
        }[job]
        fixture = repo / "backend" / "utilities" / script
        fixture.write_text(RECORDER, encoding="utf-8", newline="\n")
        child = [sys.executable, str(fixture), *prefix, *address, "--job", job.value]
        if selected_server is not None:
            child.extend(["--hold-seconds", "1.2"])
        if child_exit:
            child.extend(["--exit-code", str(child_exit)])
    env_path = repo / "launcher.env"
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("IDHAZH_HOST_TELEMETRY_", "IDHAZH_MODEL_SERVER_"))
    } | {
        "PYTHONPATH": str(repo / "backend"),
        "GITHUB_ENV": str(env_path),
        "GITHUB_RUN_ATTEMPT": str(ATTEMPT),
    }
    if selected_server is not None:
        environment.update(
            {
                "IDHAZH_MODEL_SERVER_PID": str(selected_server[0]),
                "IDHAZH_MODEL_SERVER_START_TICKS": str(selected_server[1]),
            }
        )
    result = subprocess.run(
        [
            sys.executable,
            str(repo / "backend/utilities/d7_host_telemetry.py"),
            "run",
            "--mode",
            "rust",
            "--job",
            job.value,
            "--run-id",
            RUN,
            "--attempt",
            str(ATTEMPT),
            "--git-sha",
            SEED_COMMIT,
            "--binary",
            str(binary),
            "--memory-profiling",
            memory,
            "--",
            *child,
        ],
        cwd=repo,
        env=environment,
        capture_output=True,
        timeout=120,
        check=False,
    )
    (repo / "launcher.stdout").write_bytes(result.stdout)
    (repo / "launcher.stderr").write_bytes(result.stderr)
    assert result.returncode == child_exit, result.stderr.decode("utf-8", errors="replace")
    handoff = exported(env_path)
    assert handoff["IDHAZH_HOST_TELEMETRY_VERIFIED"] == "1"
    receipt_path = Path(handoff["IDHAZH_HOST_TELEMETRY_RECEIPT"])
    receipt = HostPublicationReceipt.model_validate_json(receipt_path.read_bytes())
    identity = WriterIdentity(
        run_id=RUN,
        attempt=ATTEMPT,
        job=job,
        shard=0,
        producer="telemetry.silicon",
        git_sha=SEED_COMMIT,
    )
    limits = NativeSettings.model_validate_json(
        (repo / "config/host-telemetry-experiment.json").read_bytes()
    ).verification_limits
    native = verify_host_publication(receipt, repo=repo, identity=identity, date=DAY, limits=limits)
    assert len(native) == 1
    for name, digest in native.items():
        assert name.startswith(f"state/raw/host-fingerprint/{DAY.replace('-', '/')}/")
        assert hashlib.sha256((repo / name).read_bytes()).hexdigest() == digest
    (row,) = ledger.load_days(
        repo / "state", LedgerName.HOST_FINGERPRINT, [DAY], model=HostFingerprintRow
    )
    assert (row.date, row.run_id, row.job, row.shard) == (DAY, RUN, job, 0)
    assert row.job_seconds is not None
    session = Path(handoff["IDHAZH_HOST_TELEMETRY_SESSION"])
    drained = json.loads((session / "drained.json").read_text(encoding="utf-8"))
    assert drained["kind"] == "monitor.stopped"
    controls = json.loads((session / "effective-config.json").read_text(encoding="utf-8"))[
        "controls"
    ]
    assert controls["memory_profiling_enabled"] is (memory == "on")
    assert controls["memcpy_enabled"] is False
    if memory == "off":
        assert not (session / "native-artifacts").exists()
    if selected_server is not None:
        manifest = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
        assert (manifest["cpu_target"]["pid"], manifest["cpu_target"]["start_ticks"]) == (
            selected_server
        )
        server = manifest["workers"][0]["server"]
        assert (server["pid"], server["start_ticks"]) == selected_server
        samples, _ = native_memory(session)
        assert any("VmRSS" in sample for sample in samples)
    (repo / "verified-paths.json").write_text(json.dumps(native), encoding="utf-8")


@pytest.mark.skipif(not LIVE or sys.platform != "linux", reason="isolated Ubuntu D7 gate only")
def test_native_runtime_measures_the_explicit_bounded_subject_not_a_process_name(
    tmp_path: Path,
) -> None:
    """A real finite process proves PID/start-tick propagation without a network/model fixture."""
    subject = subprocess.Popen(
        [sys.executable, "-c", "import time; data = bytearray(1048576); time.sleep(60)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        target = server_identity(subject.pid)
        test_real_native_family_lifecycle_keeps_single_writer_paths(
            tmp_path, ServerJob.RUNTIME, "on", (target.pid, target.start_ticks)
        )
    finally:
        subject.terminate()
        subject.wait(timeout=10)
