"""Does the shared publication runtime install and validate its real packages?"""

from __future__ import annotations

import pytest
import yaml  # type: ignore[import-untyped]

from ._harness import ACTIONS_DIR, _mapping

pytestmark = pytest.mark.workflow


def test_shared_publication_action_installs_locked_packages_then_proves_startup() -> None:
    action = _mapping(
        yaml.safe_load(
            (ACTIONS_DIR / "publication-runtime" / "action.yml").read_text(encoding="utf-8")
        ),
        "publication runtime action",
    )
    runs = _mapping(action["runs"], "publication runtime steps")
    assert runs["using"] == "composite"
    steps = runs["steps"]
    assert isinstance(steps, list)
    setup, install, readiness = (_mapping(step, "publication runtime step") for step in steps)
    assert setup["uses"] == "oven-sh/setup-bun@v2"
    assert setup["with"] == {"bun-version": "1.3.13"}
    assert install["working-directory"] == "${{ github.workspace }}"
    install_script = install["run"]
    assert isinstance(install_script, str)
    assert install_script.splitlines() == [
        f"bun install --frozen-lockfile --cwd packages/{package}"
        for package in ("common-contracts", "data-delivery", "ledger-file-writer")
    ]
    assert readiness["working-directory"] == "${{ runner.temp }}"
    assert readiness["run"] == (
        'bun run "$GITHUB_WORKSPACE/packages/ledger-file-writer/src/'
        'planner-file-validation-cli.ts" --check-runtime'
    )
    assert install["shell"] == readiness["shell"] == "bash"
    assert not any(
        _mapping(step, "publication runtime step").get(key)
        for step in steps
        for key in ("continue-on-error", "if")
    )
