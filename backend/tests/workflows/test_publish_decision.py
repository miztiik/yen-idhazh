"""When does the Pages workflow publish, and which commit does it build?"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from utilities.pages_ci_evidence import CiRun, select_ci_anchor

from ._harness import PUBLISH_DECISION_MODULE

pytestmark = pytest.mark.workflow

STEP_NAMES: Final = frozenset(
    {"EVENT_NAME", "CONCLUSION", "CHECKED", "DEPLOYED", "TIP", "DISPATCHED_REF", "DEFAULT_BRANCH"}
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _commit(repo: Path, files: dict[str, str]) -> str:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "--", *files)
    _git(
        repo,
        "-c", "user.name=test",
        "-c", "user.email=test@example.invalid",
        "-c", "commit.gpgsign=false",
        "commit", "--quiet", "-m", "a change",
    )
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "checkout"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    first = _commit(repo, {"frontend/src/page.ts": "export const page = 1;\n"})
    return repo, first


def decision(workspace: Path, **step_env: str) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if name not in STEP_NAMES}
    env.update(step_env)
    result = subprocess.run(
        [sys.executable, str(PUBLISH_DECISION_MODULE)],
        cwd=workspace,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines())


def scheduled(
    repo: Path,
    *,
    tip: str,
    checked: str = "",
    deployed: str = "",
    conclusion: str = "not_verified",
    branch: str = "main",
) -> dict[str, str]:
    return decision(
        repo,
        EVENT_NAME="schedule",
        CONCLUSION=conclusion,
        CHECKED=checked,
        DEPLOYED=deployed,
        TIP=tip,
        DISPATCHED_REF=branch,
        DEFAULT_BRANCH="main",
    )


def _run(number: int, *, conclusion: str, gates: str, event: str = "push") -> CiRun:
    return CiRun(number, number, f"{number:040x}", "completed", conclusion, event, gates)


def test_ci_evidence_skips_documentation_only_runs() -> None:
    code = _run(1, conclusion="success", gates="success")
    docs = _run(2, conclusion="success", gates="skipped")
    evidence = select_ci_anchor([docs, code])
    assert evidence.sha == code.sha
    assert not evidence.blocked


def test_ci_evidence_does_not_skip_a_failed_push() -> None:
    docs = _run(3, conclusion="success", gates="skipped")
    failed = _run(2, conclusion="failure", gates="")
    older = _run(1, conclusion="success", gates="success")
    evidence = select_ci_anchor([docs, failed, older])
    assert evidence.sha == ""
    assert evidence.blocked


def test_ci_evidence_does_not_skip_a_pending_push() -> None:
    pending = CiRun(2, 2, "2" * 40, "in_progress", "", "push")
    older = _run(1, conclusion="success", gates="success")
    evidence = select_ci_anchor([pending, older])
    assert evidence.sha == ""
    assert evidence.blocked


def test_a_later_manual_full_ci_can_verify_code_after_a_failure() -> None:
    manual = _run(3, conclusion="success", gates="success", event="workflow_dispatch")
    failed = _run(2, conclusion="failure", gates="")
    evidence = select_ci_anchor([manual, failed])
    assert evidence.sha == manual.sha
    assert not evidence.blocked


def test_missing_code_gate_blocks_and_no_recent_code_gate_needs_evidence() -> None:
    missing = select_ci_anchor([_run(1, conclusion="success", gates="missing")])
    docs = select_ci_anchor([_run(1, conclusion="success", gates="skipped")])
    assert missing.blocked
    assert not docs.blocked
    assert docs.sha == ""


def test_generated_updates_can_reuse_deployed_code(repository: tuple[Path, str]) -> None:
    repo, deployed = repository
    tip = _commit(
        repo,
        {
            "frontend/public/publication.json": "{}\n",
            "state/raw/ledger/row.json": "{}\n",
            "corpus/corpus.jsonl": "{}\n",
            "corpus/corpus.meta.json": "{}\n",
            "docs/page.md": "# Updated\n",
        },
    )
    result = scheduled(repo, tip=tip, deployed=deployed)
    assert result["publish"] == "true"
    assert result["ref"] == tip


def test_generated_updates_can_use_a_full_ci_anchor(repository: tuple[Path, str]) -> None:
    repo, checked = repository
    tip = _commit(repo, {"frontend/public/digest/day.json": "{}\n"})
    result = scheduled(repo, tip=tip, checked=checked, conclusion="success")
    assert result["publish"] == "true"
    assert result["ref"] == tip


@pytest.mark.parametrize(
    "path",
    [
        "frontend/src/page.ts",
        ".github/workflows/ci.yml",
        "corpus/reference-dataset-1/config.json",
        "new-code.py",
    ],
)
def test_unverified_code_changes_block_publication(
    repository: tuple[Path, str], path: str
) -> None:
    repo, anchor = repository
    tip = _commit(repo, {path: "changed\n"})
    assert scheduled(repo, tip=tip, checked=anchor, deployed=anchor, conclusion="success")[
        "publish"
    ] == "false"
    assert scheduled(repo, tip=tip, checked=tip, deployed=anchor, conclusion="success")[
        "publish"
    ] == "true"


@pytest.mark.parametrize("path", ["state", "frontend/public"])
def test_generated_directories_cannot_be_replaced_by_files(
    repository: tuple[Path, str], path: str
) -> None:
    repo, anchor = repository
    tip = _commit(repo, {path: "not a data directory\n"})
    assert scheduled(repo, tip=tip, deployed=anchor)["publish"] == "false"


def test_failed_or_pending_push_ci_blocks_even_when_code_was_deployed(
    repository: tuple[Path, str]
) -> None:
    repo, tip = repository
    assert scheduled(repo, tip=tip, deployed=tip, conclusion="blocked")["publish"] == "false"


def test_scheduled_publish_is_limited_to_the_default_branch(
    repository: tuple[Path, str]
) -> None:
    repo, tip = repository
    assert scheduled(repo, tip=tip, checked=tip, conclusion="success", branch="other")[
        "publish"
    ] == "false"


def test_missing_evidence_cannot_publish(repository: tuple[Path, str]) -> None:
    repo, tip = repository
    assert scheduled(repo, tip=tip)["publish"] == "false"
    with pytest.raises(subprocess.CalledProcessError):
        scheduled(repo, tip=tip, deployed="invalid")
    with pytest.raises(subprocess.CalledProcessError):
        scheduled(repo, tip=tip, deployed=tip, conclusion="invalid")


def test_a_shallow_checkout_fetches_the_named_anchor(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    origin, checked = repository
    tip = _commit(origin, {"frontend/public/publication.json": "{}\n"})
    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "--quiet", "--no-local", "--depth=1", str(origin), str(shallow))
    result = scheduled(shallow, tip=tip, checked=checked, conclusion="success")
    assert result["publish"] == "true"
    assert result["ref"] == tip


@pytest.mark.parametrize(("dispatched", "published"), [("main", "true"), ("other", "false")])
def test_manual_publish_runs_from_main_only(
    tmp_path: Path, dispatched: str, published: str
) -> None:
    tip = "b" * 40
    result = decision(
        tmp_path,
        EVENT_NAME="workflow_dispatch",
        TIP=tip,
        DISPATCHED_REF=dispatched,
        DEFAULT_BRANCH="main",
    )
    assert result["publish"] == published
    assert result["ref"] == tip


@pytest.mark.parametrize("event", ["push", "pull_request", "workflow_run"])
def test_other_events_do_not_publish(tmp_path: Path, event: str) -> None:
    result = decision(
        tmp_path,
        EVENT_NAME=event,
        TIP="c" * 40,
        DEFAULT_BRANCH="main",
        DISPATCHED_REF="main",
    )
    assert result["publish"] == "false"
