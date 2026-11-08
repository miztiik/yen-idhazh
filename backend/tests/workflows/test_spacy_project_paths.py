"""Do spaCy preparation and verification resolve the independent project and shared inputs?"""

from __future__ import annotations

import ast
import re
import shlex
import tomllib
from pathlib import Path

import pytest
from support.paths import REPO_ROOT

from ._harness import _load_workflows, _mapping, _steps

pytestmark = pytest.mark.workflow

PROJECT_PATH = "services/text_analysis/spacy"
PROJECT = REPO_ROOT / PROJECT_PATH


def _read_assignment(path: Path, name: str) -> ast.expr:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    )


def test_spacy_project_files_are_not_loose_in_the_parent() -> None:
    for name in (".python-version", "pyproject.toml", "uv.lock", "src", "scripts", "tests"):
        assert (PROJECT / name).exists()
        assert not (PROJECT.parent / name).exists()


def test_spacy_host_dependency_resolves_from_the_nested_project() -> None:
    manifest = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))
    host_path = manifest["tool"]["uv"]["sources"]["local-api-host"]["path"]
    expected = REPO_ROOT / "services" / "local_api_host"
    assert (PROJECT / host_path).resolve() == expected

    lock = tomllib.loads((PROJECT / "uv.lock").read_text(encoding="utf-8"))
    host = next(package for package in lock["package"] if package["name"] == "local-api-host")
    assert (PROJECT / host["source"]["directory"]).resolve() == expected


def test_spacy_workflow_uses_the_nested_project_and_existing_entrypoints() -> None:
    steps = _steps(_load_workflows()["spacy-tests.yml"], "spacy_live_test")
    sync = next(step for step in steps if step.get("run") == "uv sync --frozen")
    assert sync["working-directory"] == PROJECT_PATH

    commands = [
        shlex.split(str(step["run"]))
        for step in steps
        if str(step.get("run", "")).startswith("uv run ")
    ]
    assert commands
    for command in commands:
        assert command[command.index("--project") + 1] == PROJECT_PATH
        entrypoint = command[command.index("python") + 1]
        assert entrypoint.startswith(PROJECT_PATH + "/")
        assert (REPO_ROOT / entrypoint).is_file()

    contracts = next(
        step for step in steps if step.get("name") == "Check verification artifact contracts"
    )
    assert (
        _mapping(contracts["env"], "verification environment")["PYTHONPATH"]
        == PROJECT_PATH + "/scripts"
    )


def test_spacy_scripts_preserve_repository_root_and_shared_contract_resolution() -> None:
    for name in ("prepare-selected-model.py", "run-spacy-test.py"):
        script = PROJECT / "scripts" / name
        expression = ast.Expression(body=_read_assignment(script, "ROOT"))
        root = eval(
            compile(expression, script.name, "eval"),
            {"Path": Path, "__file__": str(script)},
        )
        assert root == REPO_ROOT

    runner = PROJECT / "scripts" / "run-spacy-test.py"
    probe_path = ast.literal_eval(_read_assignment(runner, "PROBE_PATH"))
    probe = PROJECT / "scripts" / "probe-text-analysis.ts"
    assert (REPO_ROOT / probe_path).resolve() == probe
    imports = re.findall(r'from "([^"]+)"', probe.read_text(encoding="utf-8"))
    assert imports
    assert (
        probe.parent / imports[0]
    ).resolve() == REPO_ROOT / "packages" / "common-contracts" / "src" / "index.ts"
