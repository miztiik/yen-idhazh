"""Are the existing manual coverage startup and cleanup scripts valid bounded Linux commands?"""

import subprocess
import sys

import pytest
import yaml
from summary_evaluator_cases.contract_examples import REPOSITORY


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
