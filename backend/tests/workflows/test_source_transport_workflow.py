"""How does browser transport verification stay separate from production CI?"""

from __future__ import annotations

import pytest

from ._harness import _job, _load_workflows, _mapping, _script, _step, _triggers

pytestmark = pytest.mark.workflow


def test_browser_source_verification_has_its_own_candidate_and_frozen_dependencies() -> None:
    workflows = _load_workflows()
    workflow = workflows["source-transport-test.yml"]
    assert not _triggers(workflow)["workflow_dispatch"]
    assert workflow["permissions"] == {"contents": "read"}
    assert "browser_source_transport" not in _mapping(workflows["ci.yml"]["jobs"], "CI jobs")
    job = _job(workflow, "browser_source_transport")
    assert job["runs-on"] == "ubuntu-latest"
    checkout = _step(workflow, "browser_source_transport", "uses", "actions/checkout@v6")
    assert _mapping(checkout["with"], "candidate checkout")["ref"] == (
        "${{ github.event.pull_request.head.sha || github.sha }}"
    )
    installation = _script(
        _step(workflow, "browser_source_transport", "name", "Install browser source dependencies"),
        "browser dependency installation",
    )
    for path in ("services/feed-ingest-plan", "packages/feed-probe", "services/host-fingerprints"):
        assert f"bun install --cwd {path} --frozen-lockfile" in installation
    assert "bun run --cwd services/feed-ingest-plan browser:install" in installation
    verification = _step(
        workflow, "browser_source_transport", "name", "Verify checked browser source ownership"
    )
    assert not verification.get("continue-on-error")
    assert _script(verification, "browser response verification").splitlines()[-1] == (
        "bun run --cwd services/feed-ingest-plan test ./test/browser-request-policy.test.ts "
        "./test/playwright-transport.test.ts ./test/execution-resource-lifecycle.test.ts"
    )
