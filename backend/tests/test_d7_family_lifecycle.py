"""Bounded, artifact-only Linux proof of the real launcher and producer entry points."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from conftest import CONFIG_DIR, REPO_ROOT

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.host_output import HostPublicationReceipt
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.contracts.run_plan import RunPlan
from idhazh.publication import initialize_inventory
from idhazh.telemetry.host_evidence_inputs import NativeSettings
from idhazh.telemetry.host_publication import verify_host_publication
from utilities.model_runtime import server_identity
from utilities.runtime_sweep import native_memory

DAY = "2026-10-12"
EXECUTION = "771"
RUN = f"{DAY}-{EXECUTION}"
ATTEMPT = 2
LIVE = os.environ.get("IDHAZH_D7_LIVE_TEST") == "1"

PUBLISH_AND_NETWORK_BOUNDARY = dedent(
    """
    import json
    import os
    import socket
    import urllib.request

    class Response:
        def __init__(self, payload):
            self.payload = payload
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return self.payload

    def urlopen(url, *args, **kwargs):
        address = url.full_url if isinstance(url, urllib.request.Request) else str(url)
        if address.startswith("https://huggingface.co/api/models/d7-fixture/model/tree/"):
            return Response(json.dumps([{
                "path": "fixture.gguf",
                "lfs": {
                    "oid": os.environ["D7_FIXTURE_MODEL_SHA"],
                    "size": int(os.environ["D7_FIXTURE_MODEL_BYTES"]),
                },
            }]).encode())
        raise AssertionError("D7 integration test attempted network access: " + address)

    urllib.request.urlopen = urlopen
    original_socket = socket.socket
    class NoNetworkSocket(original_socket):
        def connect(self, address):
            if self.family != socket.AF_UNIX:
                raise OSError("D7 integration tests forbid network access")
            return super().connect(address)
        def connect_ex(self, address):
            if self.family != socket.AF_UNIX:
                raise OSError("D7 integration tests forbid network access")
            return super().connect_ex(address)
    socket.socket = NoNetworkSocket

    if os.environ.get("D7_PUBLISH_CAPTURE"):
        from utilities import publish_to_repo

        def publish(request, *, repo, **kwargs):
            request.validate(repo)
            with open(os.environ["D7_PUBLISH_CAPTURE"], "a", encoding="utf-8") as output:
                output.write(json.dumps({
                    "identity": request.identity.model_dump(mode="json"),
                    "writes": {
                        path: {"sha256": write.sha256, "immutable": write.immutable}
                        for path, write in sorted(request.writes.items())
                    },
                    "deletions": sorted(request.deletions),
                }, sort_keys=True) + "\\n")
            return publish_to_repo.PublicationResult(
                publish_to_repo.Status.NO_CHANGES, observed_tip=request.source_tip
            )

        publish_to_repo.publish = publish
    """
)

TORCH_FIXTURE = """
_threads = 1
def set_num_threads(value):
    global _threads
    _threads = value
def get_num_threads():
    return _threads
"""

SENTENCE_TRANSFORMERS_FIXTURE = """
import time
import numpy as np

class SentenceTransformer:
    def __init__(self, model_id, *, device, **kwargs):
        self.max_seq_length = 0
    def encode(self, texts, **kwargs):
        time.sleep(1.25)
        return np.asarray([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]], dtype=np.float32)
"""

LLAMA_BENCH_FIXTURE = """#!/usr/bin/env python3
import json
import os
import sys
import time

rows = [
    {"model_filename": "fixture.gguf", "n_threads": 1, "n_prompt": 8, "n_gen": 0,
     "avg_ts": 10.0, "stddev_ts": 0.2, "samples_ts": [9.8, 10.2],
     "build_number": 1, "build_commit": "fixture"},
    {"model_filename": "fixture.gguf", "n_threads": 1, "n_prompt": 0, "n_gen": 4,
     "avg_ts": 5.0, "stddev_ts": 0.1, "samples_ts": [4.9, 5.1],
     "build_number": 1, "build_commit": "fixture"},
]
time.sleep(1.25)
print(json.dumps(rows))
raise SystemExit(int(os.environ.get("D7_FIXTURE_BENCH_EXIT", "0")))
"""


def bounded_config(
    destination: Path, *, host_enabled: bool = True, council_paused: bool = False
) -> Path:
    shutil.copytree(CONFIG_DIR, destination)
    sources = json.loads((destination / "sources.json").read_text(encoding="utf-8"))
    sources["feeds"] = []
    sources["salience"] = []
    (destination / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
    for task in (destination / "gardener").glob("*.json"):
        if task.name != "compact-gardener.json":
            task.unlink()
    app_path = destination / "idhazh.json"
    app = json.loads(app_path.read_text(encoding="utf-8"))
    app["observability"]["host_fingerprint_bandwidth_floor_mib"] = 0
    app["observability"]["host_fingerprint"] = host_enabled
    app["observability"]["evaluation_enabled"] = False
    app["run"]["trial_state_dirname"] = None
    app["run"]["trial_case_dirname"] = None
    app_path.write_text(json.dumps(app), encoding="utf-8")
    gardener_path = destination / "idhazh_gardener.json"
    gardener = json.loads(gardener_path.read_text(encoding="utf-8"))
    gardener["shards"] = 1
    gardener["task_names"] = ["compact-gardener"]
    gardener_path.write_text(json.dumps(gardener), encoding="utf-8")
    if council_paused:
        judge_path = destination / "judges" / "content-similarity-judge.json"
        judge = json.loads(judge_path.read_text(encoding="utf-8"))
        judge["lifecycle_status"] = "paused"
        judge_path.write_text(json.dumps(judge), encoding="utf-8")
    return destination


def isolate(
    root: Path, *, host_enabled: bool = True, council_paused: bool = False
) -> tuple[Path, str]:
    root.mkdir(parents=True)
    bounded_config(root / "config", host_enabled=host_enabled, council_paused=council_paused)
    for package in ("idhazh", "utilities"):
        shutil.copytree(
            REPO_ROOT / "backend" / package,
            root / "backend" / package,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    initialize_inventory(
        root / "frontend" / "public" / "digest",
        seed=PublicationInventory(version=PublicationInventory.schema_version(), dates=[]),
    )
    support = root / "test-support"
    support.mkdir()
    (support / "sitecustomize.py").write_text(PUBLISH_AND_NETWORK_BOUNDARY, encoding="utf-8")
    git(root, "init", "-q")
    git(root, "config", "user.email", "d7-fixture@example.invalid")
    git(root, "config", "user.name", "D7 fixture")
    git(root, "add", "config", "backend", "frontend")
    git(root, "commit", "-qm", "bounded D7 fixture")
    commit = git(root, "rev-parse", "HEAD").strip()
    return root, commit


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True, text=True)
    return result.stdout


def test_generated_family_inputs_have_no_network_or_bandwidth_work(tmp_path: Path) -> None:
    selected = config.load(bounded_config(tmp_path / "config"))
    assert not selected.sources.feeds
    assert not selected.sources.salience
    assert selected.app.observability.host_fingerprint_bandwidth_floor_mib == 0


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


def run_digest_landing(
    repo: Path, *, commit: str, handoff: dict[str, str], environment: dict[str, str]
) -> list[dict[str, object]]:
    landed = subprocess.run(
        [
            sys.executable,
            "backend/utilities/digest_publish.py",
            "plan",
            "--date",
            DAY,
            "--execution",
            EXECUTION,
            "--commit",
            commit,
            "--shard",
            "0",
        ],
        cwd=repo,
        env=environment | handoff | {"IDHAZH_HOST_TELEMETRY_MODE": "rust"},
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert landed.returncode == 0, landed.stderr.decode("utf-8", errors="replace")
    capture = repo / "publisher-capture.jsonl"
    return [json.loads(line) for line in capture.read_text(encoding="utf-8").splitlines()]


@pytest.mark.skipif(not LIVE or sys.platform != "linux", reason="isolated Ubuntu D7 gate only")
@pytest.mark.parametrize(
    ("job", "memory", "failed"),
    [
        (job, memory, False)
        for job in (
            ServerJob.PLAN,
            ServerJob.WORK,
            ServerJob.ASSEMBLE,
            ServerJob.COLLECT,
            ServerJob.RUNTIME,
            ServerJob.RUN_TASKS,
        )
        for memory in ("on", "off")
    ]
    + [(ServerJob.RUNTIME, "on", True)],
)
def test_real_native_family_lifecycle_keeps_single_writer_paths(
    tmp_path: Path,
    job: ServerJob,
    memory: str,
    failed: bool,
    selected_server: tuple[int, int] | None = None,
) -> None:
    """Every measured family runs its real producer through the native event window."""
    binary = Path(os.environ["IDHAZH_HOST_TELEMETRY_BINARY"]).resolve(strict=True)
    repo, commit = isolate(tmp_path / "repo")
    address = [
        "--config",
        "config",
        "--date",
        DAY,
        "--execution",
        EXECUTION,
        "--commit",
        commit,
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
                git_sha=commit,
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
        encoder_config = json.loads(
            (repo / "config/encoder-comparison.json").read_text(encoding="utf-8")
        )
        encoder_config["encoders"] = [
            {
                "slug": "fixture",
                "model_id": "d7-fixture",
                "prefix": "",
                "parameters_millions": 1,
                "why": "bounded native lifecycle fixture",
            }
        ]
        encoder_config["encode"].update(
            {"threads": 1, "checkpoint_every_articles": 1, "batch_size": 4}
        )
        (repo / "config/encoder-comparison.json").write_text(
            json.dumps(encoder_config), encoding="utf-8"
        )
        (repo / "backend/var/encoder/pairs.json").parent.mkdir(parents=True)
        (repo / "backend/var/encoder/pairs.json").write_text(
            json.dumps(
                {
                    "texts": ["same title", "same title again", "different event", "other event"],
                    "same": [[0, 1]],
                    "different": [[0, 2]],
                    "ambiguous": [],
                    "related": [],
                }
            ),
            encoding="utf-8",
        )
        (repo / "test-support/torch.py").write_text(TORCH_FIXTURE, encoding="utf-8")
        (repo / "test-support/sentence_transformers.py").write_text(
            SENTENCE_TRANSFORMERS_FIXTURE, encoding="utf-8"
        )
        child = [
            sys.executable,
            "backend/utilities/compare_summary_encoders.py",
            "score",
            "--slug",
            "fixture",
            "--pairs",
            "backend/var/encoder/pairs.json",
            "--out",
            "backend/var/encoder/reading.json",
            "--vectors-out",
            "backend/var/encoder/vectors.npy",
            "--date",
            DAY,
            "--execution",
            EXECUTION,
            "--commit",
            commit,
            "--shard",
            "0",
        ]
    elif job == ServerJob.RUNTIME:
        model = repo / "backend/models/fixture.gguf"
        model.parent.mkdir(parents=True, exist_ok=True)
        model.write_bytes(b"bounded local GGUF fixture\n")
        digest = hashlib.sha256(model.read_bytes()).hexdigest()
        binary_path = repo / "backend/bin/llama-bench"
        binary_path.parent.mkdir(parents=True, exist_ok=True)
        binary_path.write_text(LLAMA_BENCH_FIXTURE, encoding="utf-8", newline="\n")
        binary_path.chmod(binary_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        child = [
            sys.executable,
            "backend/utilities/measure_llm.py",
            "bench",
            "--models",
            f"d7-fixture/model@{'a' * 40}:fixture.gguf",
            "--threads",
            "1",
            "--binary",
            "backend/bin/llama-bench",
            "--config",
            "config",
            *address[2:],
            "--memory-profiling",
            memory,
            "--models-dir",
            "backend/models",
            "--output",
            "backend/var/runtime/llm.json",
            "--weights-report",
            "backend/var/runtime/weights.txt",
            "--resources-report",
            "backend/var/runtime/resources.json",
            "--prompt-tokens",
            "8",
            "--generation-tokens",
            "4",
            "--repeats",
            "2",
            "--expect-sha256",
            digest,
            "--candidate-id",
            "d7-fixture",
            "--quantisation",
            "fixture",
            "--readings",
            "backend/var/runtime/raw-case.json",
        ]
        (repo / "runtime-model-identity.json").write_text(
            json.dumps({"sha256": digest, "bytes": model.stat().st_size}), encoding="utf-8"
        )
    else:
        child = [
            sys.executable,
            "backend/utilities/gardener_publish.py",
            "--shard",
            "0",
            "--run-id",
            RUN,
            "--attempt",
            str(ATTEMPT),
            "--repo-root",
            ".",
            "--config",
            "config",
        ]
    capture = repo / "publisher-capture.jsonl"
    fixture_env = {
        "D7_PUBLISH_CAPTURE": str(capture),
        "D7_FIXTURE_BENCH_EXIT": "17" if failed else "0",
    }
    if job == ServerJob.RUNTIME:
        fixture_identity = json.loads(
            (repo / "runtime-model-identity.json").read_text(encoding="utf-8")
        )
        fixture_env.update(
            {
                "D7_FIXTURE_MODEL_SHA": fixture_identity["sha256"],
                "D7_FIXTURE_MODEL_BYTES": str(fixture_identity["bytes"]),
            }
        )
    env_path = repo / "launcher.env"
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("IDHAZH_HOST_TELEMETRY_", "IDHAZH_MODEL_SERVER_"))
        and key != "COUNCIL_SELECTION"
    } | {
        "PYTHONPATH": os.pathsep.join((str(repo / "backend"), str(repo / "test-support"))),
        "GITHUB_ENV": str(env_path),
        "GITHUB_OUTPUT": str(repo / "launcher.output"),
        "GITHUB_STEP_SUMMARY": str(repo / "step-summary.md"),
        "GITHUB_RUN_ID": EXECUTION,
        "GITHUB_RUN_ATTEMPT": str(ATTEMPT),
        "GITHUB_SHA": commit,
        **fixture_env,
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
            commit,
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
    expected_exit = 1 if failed else 0
    assert result.returncode == expected_exit, result.stderr.decode("utf-8", errors="replace")
    if failed:
        assert b"CalledProcessError" in result.stderr
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
        git_sha=commit,
    )
    limits = NativeSettings.model_validate_json(
        (repo / "config/host-telemetry-experiment.json").read_bytes()
    ).verification_limits
    native = verify_host_publication(receipt, repo=repo, identity=identity, date=DAY, limits=limits)
    assert len(native) == 1
    assert dict(receipt.writes) == native
    for name, digest in native.items():
        assert name.startswith(f"state/raw/host-fingerprint/{DAY.replace('-', '/')}/")
        assert hashlib.sha256((repo / name).read_bytes()).hexdigest() == digest
    host_files = set((repo / "state/raw/host-fingerprint").rglob("*.parquet"))
    assert host_files == {repo / name for name in native}
    (row,) = ledger.load_days(
        repo / "state", LedgerName.HOST_FINGERPRINT, [DAY], model=HostFingerprintRow
    )
    assert (row.date, row.run_id, row.job, row.shard) == (DAY, RUN, job, 0)
    assert row.job_seconds is not None
    if job == ServerJob.PLAN and memory == "on":
        publications = run_digest_landing(
            repo, commit=commit, handoff=handoff, environment=environment
        )
        assert len(publications) == 1
        published_writes = publications[0]["writes"]
        assert isinstance(published_writes, dict)
        assert set(native) <= set(published_writes)
        for name, digest in native.items():
            entry = published_writes[name]
            assert isinstance(entry, dict)
            assert entry.get("sha256") == digest
    if job == ServerJob.COLLECT:
        assert row.job_seconds >= 1
        reading = json.loads(
            (repo / "backend/var/encoder/reading.json").read_text(encoding="utf-8")
        )
        assert reading["state"] == "measured"
        assert reading["articles_done"] == reading["articles_to_encode"] == 4
        assert (repo / "backend/var/encoder/vectors.npy").is_file()
    if job == ServerJob.RUNTIME and not failed:
        assert (
            json.loads((repo / "backend/var/runtime/raw-case.json").read_text())["identity"]["id"]
            == "d7-fixture"
        )
    if job == ServerJob.RUN_TASKS:
        gardener_rows = ledger.load_days(
            repo / "state", LedgerName.GARDENER, [DAY], model=CollectionPruneRow
        )
        assert gardener_rows
        publications = [
            json.loads(line) for line in capture.read_text(encoding="utf-8").splitlines()
        ]
        assert len(publications) == 1
        published_writes = publications[0]["writes"]
        assert isinstance(published_writes, dict)
        assert any(path.startswith("state/raw/host-fingerprint/") for path in published_writes)
        assert any(path.startswith("state/raw/gardener/") for path in published_writes)
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
def test_real_digest_producer_and_publisher_keep_host_collection_disabled(tmp_path: Path) -> None:
    binary = Path(os.environ["IDHAZH_HOST_TELEMETRY_BINARY"]).resolve(strict=True)
    repo, commit = isolate(tmp_path / "repo", host_enabled=False)
    capture = repo / "publisher-capture.jsonl"
    env_path = repo / "launcher.env"
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("IDHAZH_HOST_TELEMETRY_", "IDHAZH_MODEL_SERVER_"))
        and key != "COUNCIL_SELECTION"
    } | {
        "PYTHONPATH": os.pathsep.join((str(repo / "backend"), str(repo / "test-support"))),
        "GITHUB_ENV": str(env_path),
        "GITHUB_OUTPUT": str(repo / "launcher.output"),
        "GITHUB_STEP_SUMMARY": str(repo / "step-summary.md"),
        "GITHUB_RUN_ID": EXECUTION,
        "GITHUB_RUN_ATTEMPT": str(ATTEMPT),
        "GITHUB_SHA": commit,
        "D7_PUBLISH_CAPTURE": str(capture),
    }
    child = [
        sys.executable,
        "backend/utilities/digest_publish.py",
        "run",
        "plan",
        "--config",
        "config",
        "--date",
        DAY,
        "--execution",
        EXECUTION,
        "--commit",
        commit,
        "--memory-profiling",
        "off",
    ]
    result = subprocess.run(
        [
            sys.executable,
            "backend/utilities/d7_host_telemetry.py",
            "run",
            "--mode",
            "rust",
            "--job",
            ServerJob.PLAN.value,
            "--run-id",
            RUN,
            "--attempt",
            str(ATTEMPT),
            "--git-sha",
            commit,
            "--binary",
            str(binary),
            "--memory-profiling",
            "off",
            "--",
            *child,
        ],
        cwd=repo,
        env=environment,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    handoff = exported(env_path)
    assert handoff["IDHAZH_HOST_TELEMETRY_VERIFIED"] == "1"
    receipt = HostPublicationReceipt.model_validate_json(
        Path(handoff["IDHAZH_HOST_TELEMETRY_RECEIPT"]).read_bytes()
    )
    identity = WriterIdentity(
        run_id=RUN,
        attempt=ATTEMPT,
        job=ServerJob.PLAN,
        shard=0,
        producer="telemetry.silicon",
        git_sha=commit,
    )
    limits = NativeSettings.model_validate_json(
        (repo / "config/host-telemetry-experiment.json").read_bytes()
    ).verification_limits
    assert not receipt.writes
    assert not verify_host_publication(
        receipt,
        repo=repo,
        identity=identity,
        date=DAY,
        limits=limits,
        host_enabled=False,
    )
    assert not list((repo / "state/raw/host-fingerprint").rglob("*.parquet"))
    assert not ledger.load_days(
        repo / "state", LedgerName.HOST_FINGERPRINT, [DAY], model=HostFingerprintRow
    )
    publications = run_digest_landing(repo, commit=commit, handoff=handoff, environment=environment)
    assert len(publications) == 1
    published_writes = publications[0]["writes"]
    assert isinstance(published_writes, dict)
    assert not any(path.startswith("state/raw/host-fingerprint/") for path in published_writes)


@pytest.mark.skipif(not LIVE or sys.platform != "linux", reason="isolated Ubuntu D7 gate only")
def test_real_council_no_work_skips_native_monitor_and_publisher(tmp_path: Path) -> None:
    binary = Path(os.environ["IDHAZH_HOST_TELEMETRY_BINARY"]).resolve(strict=True)
    repo, commit = isolate(tmp_path / "repo", council_paused=True)
    capture = repo / "publisher-capture.jsonl"
    env_path = repo / "launcher.env"
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("IDHAZH_HOST_TELEMETRY_", "IDHAZH_MODEL_SERVER_"))
        and key != "COUNCIL_SELECTION"
    } | {
        "PYTHONPATH": os.pathsep.join((str(repo / "backend"), str(repo / "test-support"))),
        "GITHUB_ENV": str(env_path),
        "GITHUB_OUTPUT": str(repo / "launcher.output"),
        "GITHUB_STEP_SUMMARY": str(repo / "step-summary.md"),
        "GITHUB_RUN_ID": EXECUTION,
        "GITHUB_RUN_ATTEMPT": str(ATTEMPT),
        "GITHUB_SHA": commit,
        "D7_PUBLISH_CAPTURE": str(capture),
    }
    child = [
        sys.executable,
        "backend/utilities/council_publish.py",
        "--date",
        DAY,
        "--run-id",
        RUN,
        "--commit",
        commit,
        "--repo-root",
        ".",
        "--config-root",
        "config",
    ]
    result = subprocess.run(
        [
            sys.executable,
            "backend/utilities/d7_host_telemetry.py",
            "run",
            "--mode",
            "rust",
            "--job",
            ServerJob.SAVE_COUNCIL_RESULTS.value,
            "--run-id",
            RUN,
            "--attempt",
            str(ATTEMPT),
            "--git-sha",
            commit,
            "--binary",
            str(binary),
            "--memory-profiling",
            "off",
            "--",
            *child,
        ],
        cwd=repo,
        env=environment,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    handoff = exported(env_path)
    assert handoff == {"IDHAZH_HOST_TELEMETRY_SKIPPED": "council-no-active-publishers"}
    assert not (repo / "backend/var/host-events").exists()
    assert not capture.exists()


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
            tmp_path,
            ServerJob.RUNTIME,
            "on",
            False,
            selected_server=(target.pid, target.start_ticks),
        )
    finally:
        subject.terminate()
        subject.wait(timeout=10)
