"""Do manual coverage scripts preserve bounded syntax and refuse unowned application readiness?"""

import asyncio
import json
import os
import subprocess
import sys

import pytest
import yaml
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.coverage_cases import running_coverage

from summary_evaluator.shared.contracts.api_paths import API_HEALTH_PATH
from summary_evaluator.shared.read_process_identity import read_owned_process_identity


@pytest.mark.skipif(
    sys.platform != "linux", reason="Linux Bash syntax proof runs in the Linux gate"
)
def test_named_manual_coverage_scripts_parse_without_running_inference() -> None:
    workflow = yaml.safe_load(
        (REPOSITORY / ".github" / "workflows" / "ai-pipeline-tests.yml").read_bytes()
    )
    names = {
        "Install existing inference and frozen evaluation dependencies",
        "Read the actual coverage listener and lifecycle bounds",
        "Start the explicitly selected source-coverage evaluator",
        "Stop the exact owned coverage server",
    }
    steps = workflow["jobs"]["run-pipeline"]["steps"]
    selected = {step["name"]: step["run"] for step in steps if step.get("name") in names}
    assert set(selected) == names
    for name in sorted(names):
        result = subprocess.run(
            ["bash", "-n"], input=selected[name], text=True, capture_output=True, timeout=10
        )
        assert result.returncode == 0, f"{name}: {result.stderr}"


@pytest.mark.skipif(
    sys.platform != "linux", reason="Actual coverage process identity is checked in the Linux gate"
)
def test_workflow_validator_requires_owned_singleton_application_and_worker() -> None:
    workflow = yaml.safe_load(
        (REPOSITORY / ".github" / "workflows" / "ai-pipeline-tests.yml").read_bytes()
    )
    startup = next(
        step["run"] for step in workflow["jobs"]["run-pipeline"]["steps"]
        if step.get("name") == "Start the explicitly selected source-coverage evaluator"
    )
    validator = startup.split("python -c '", 1)[1].split("\n'; then", 1)[0]

    async def check() -> None:
        async with running_coverage() as (client, worker, _, _):
            response = await client.get(API_HEALTH_PATH)
            assert response.status_code == 200
            observed = response.json()
            settings = worker.settings
            identity = read_owned_process_identity(
                os.getpid(), settings.worker.max_proc_identity_bytes
            )
            assert identity.start_ticks is not None
            environment = {
                **os.environ,
                "SERVER_PID": str(identity.pid),
                "SERVER_START_TICKS": identity.start_ticks,
                "MAX_IDENTITY_BYTES": str(settings.worker.max_proc_identity_bytes),
                "MAX_REPLY_BYTES": str(settings.worker.max_reply_bytes),
                "MODEL_REVISION": settings.assets.model.revision,
                "CODE_REVISION": settings.assets.code.revision,
            }
            for fault in ("none", "selection", "application", "pin", "version"):
                value = json.loads(response.content)
                current = environment.copy()
                if fault == "selection":
                    value["enabled_routes"] = ["hhem"]
                elif fault == "application":
                    original = observed["service_instance_id"]
                    value["coverage"]["service_instance_id"] = (
                        "12345678-1234-4234-8234-123456789abc"
                        if original != "12345678-1234-4234-8234-123456789abc"
                        else "87654321-4321-4321-8321-cba987654321"
                    )
                elif fault == "pin":
                    current["SERVER_START_TICKS"] = "0" if identity.start_ticks != "0" else "1"
                elif fault == "version":
                    value["version"] = "2026-11-05"
                result = await asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, "-c", validator],
                    input=json.dumps(value).encode("utf-8"),
                    env=current,
                    cwd=REPOSITORY,
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                assert result.returncode == (0 if fault == "none" else 1), result.stderr.decode()

    asyncio.run(check())
