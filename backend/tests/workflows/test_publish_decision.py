"""When does the Pages workflow publish, and which commit does it build?

Each case runs the decision the way the workflow does - a fresh interpreter, the
step's environment, stdout read as step outputs - inside a real repository built
in a temporary folder, so every path it compares comes from a real commit.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_DIR, read_text

from ._harness import PUBLISH_DECISION_MODULE, _load_workflows, _mapping, _step

pytestmark = pytest.mark.workflow

#: The environment the workflow's `rule` step hands the program, by name.
STEP_NAMES: Final = frozenset(
    {
        "EVENT_NAME",
        "TRIGGER",
        "TRIGGER_EVENT",
        "CONCLUSION",
        "CHECKED",
        "BEFORE",
        "TIP",
        "DISPATCHED_REF",
        "DEFAULT_BRANCH",
    }
)

#: Two CI runs recorded from GitHub: a pull request's and a push to main's.
RECORDED_RUNS: Final = FIXTURES_DIR / "pages-publication" / "recorded-ci-runs.json"

_EXPRESSION: Final = re.compile(r"\$\{\{\s*([A-Za-z_][\w.]*)\s*\}\}")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def a_commit(repo: Path, files: dict[str, str]) -> str:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(repo, "add", "--", *files)
    _git(
        repo,
        "-c", "user.name=test",
        "-c", "user.email=test@example.invalid",
        "-c", "commit.gpgsign=false",
        "commit", "--quiet", "-m", "a change",
    )
    return _git(repo, "rev-parse", "HEAD")


def a_repository(tmp_path: Path) -> tuple[Path, str]:
    """A checkout holding one file in each kind of place, and its first commit."""
    repo = tmp_path / "checkout"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    first = a_commit(
        repo,
        {
            "README.md": "about\n",
            "docs/page.md": "# A page\n",
            "frontend/src/page.ts": "export const page = 1;\n",
            "frontend/public/digest/2026/10/03/digest.json": "{}\n",
            "state/raw/feed-health/2026/10/03/rows.parquet": "rows\n",
        },
    )
    return repo, first


def decision(repo: Path, **step_env: str) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if name not in STEP_NAMES}
    env.update(step_env)
    done = subprocess.run(
        [sys.executable, str(PUBLISH_DECISION_MODULE)],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("=", 1) for line in done.stdout.splitlines())


def after_ci(
    repo: Path, *, before: str, checked: str, tip: str, event: str = "push", conclusion: str = "success"
) -> dict[str, str]:
    return decision(
        repo,
        EVENT_NAME="workflow_run",
        TRIGGER="CI",
        TRIGGER_EVENT=event,
        CONCLUSION=conclusion,
        CHECKED=checked,
        BEFORE=before,
        TIP=tip,
    )


def after_daily_run(repo: Path, *, checked: str, tip: str, conclusion: str) -> dict[str, str]:
    return decision(
        repo,
        EVENT_NAME="workflow_run",
        TRIGGER="Content refresh",
        TRIGGER_EVENT="schedule",
        CONCLUSION=conclusion,
        CHECKED=checked,
        TIP=tip,
    )


def test_a_pull_request_never_publishes_even_when_it_changed_the_site(tmp_path: Path) -> None:
    repo, first = a_repository(tmp_path)
    head = a_commit(repo, {"frontend/src/page.ts": "export const page = 2;\n"})
    result = after_ci(repo, before=first, checked=head, tip=head, event="pull_request")
    assert result["publish"] == "false", "an unmerged commit must never reach readers"


@pytest.mark.parametrize(("event", "conclusion"), [("push", "failure"), ("workflow_dispatch", "success")])
def test_a_failed_push_or_a_manual_ci_run_does_not_publish(
    tmp_path: Path, event: str, conclusion: str
) -> None:
    repo, first = a_repository(tmp_path)
    head = a_commit(repo, {"frontend/src/page.ts": "export const page = 2;\n"})
    result = after_ci(repo, before=first, checked=head, tip=head, event=event, conclusion=conclusion)
    assert result["publish"] == "false"


@pytest.mark.parametrize(
    ("changed", "published"),
    [
        ("frontend/src/page.ts", "true"),
        ("config/appearance.json", "true"),
        (".github/workflows/pages.yml", "true"),
        ("docs/page.md", "false"),
        ("README.md", "false"),
        ("backend/idhazh/stage.py", "false"),
        ("frontend/tests/page.spec.ts", "false"),
        (".github/workflows/ci.yml", "false"),
    ],
)
def test_a_push_publishes_only_when_it_changed_what_the_site_is_built_from(
    tmp_path: Path, changed: str, published: str
) -> None:
    repo, first = a_repository(tmp_path)
    head = a_commit(repo, {changed: "changed\n"})
    result = after_ci(repo, before=first, checked=head, tip=head)
    assert result["publish"] == published
    assert result["ref"] == head


def test_every_commit_of_a_push_counts_not_only_the_last(tmp_path: Path) -> None:
    repo, first = a_repository(tmp_path)
    a_commit(repo, {"frontend/src/page.ts": "export const page = 2;\n"})
    head = a_commit(repo, {"docs/page.md": "# A changed page\n"})
    assert after_ci(repo, before=first, checked=head, tip=head)["publish"] == "true"


def test_a_day_landing_while_ci_runs_is_published_with_the_push(tmp_path: Path) -> None:
    """The verdict arrives after the day, so building the checked commit would drop the day."""
    repo, first = a_repository(tmp_path)
    checked = a_commit(repo, {"frontend/src/page.ts": "export const page = 2;\n"})
    tip = a_commit(repo, {"frontend/public/digest/2026/10/04/digest.json": "{}\n"})
    result = after_ci(repo, before=first, checked=checked, tip=tip)
    assert result["publish"] == "true"
    assert result["ref"] == tip


def test_a_newer_push_of_site_code_waits_for_its_own_ci(tmp_path: Path) -> None:
    repo, first = a_repository(tmp_path)
    checked = a_commit(repo, {"frontend/src/page.ts": "export const page = 2;\n"})
    tip = a_commit(repo, {"frontend/src/page.ts": "export const page = 3;\n"})
    assert after_ci(repo, before=first, checked=checked, tip=tip)["publish"] == "false"


@pytest.mark.parametrize("before", ["", "0" * 40, "1" * 40], ids=["absent", "new-branch", "unknown"])
def test_a_push_whose_range_cannot_be_read_publishes(tmp_path: Path, before: str) -> None:
    repo, _ = a_repository(tmp_path)
    head = a_commit(repo, {"docs/page.md": "# A changed page\n"})
    assert after_ci(repo, before=before, checked=head, tip=head)["publish"] == "true"


@pytest.mark.parametrize("conclusion", ["success", "failure"])
def test_the_daily_run_publishes_a_day_it_landed_whatever_its_conclusion(
    tmp_path: Path, conclusion: str
) -> None:
    repo, first = a_repository(tmp_path)
    tip = a_commit(repo, {"frontend/public/digest/2026/10/04/digest.json": "{}\n"})
    result = after_daily_run(repo, checked=first, tip=tip, conclusion=conclusion)
    assert result["publish"] == "true"
    assert result["ref"] == tip


def test_the_daily_run_that_landed_nothing_the_site_serves_does_not_publish(tmp_path: Path) -> None:
    repo, first = a_repository(tmp_path)
    tip = a_commit(repo, {"state/raw/feed-health/2026/10/04/rows.parquet": "rows\n"})
    assert after_daily_run(repo, checked=first, tip=tip, conclusion="success")["publish"] == "false"


@pytest.mark.parametrize(("dispatched", "published"), [("main", "true"), ("a-branch", "false")])
def test_a_manual_publish_runs_from_main_only(tmp_path: Path, dispatched: str, published: str) -> None:
    repo, first = a_repository(tmp_path)
    result = decision(
        repo, EVENT_NAME="workflow_dispatch", TIP=first, DISPATCHED_REF=dispatched, DEFAULT_BRANCH="main"
    )
    assert result["publish"] == published


def _resolved(value: object, context: dict[str, object]) -> str:
    match = _EXPRESSION.fullmatch(str(value))
    assert match, f"{value} must be one plain expression, so this test can resolve it"
    found: object = context
    for part in match.group(1).split("."):
        found = found.get(part, "") if isinstance(found, dict) else ""
    return str(found)


@pytest.mark.parametrize(("recorded", "published"), [("pull_request", "false"), ("push", "true")])
def test_the_shipped_step_hands_the_decision_the_run_that_woke_it(
    tmp_path: Path, recorded: str, published: str
) -> None:
    """The recorded push's commits are not in this checkout, so its range cannot be read."""
    runs = json.loads(read_text(RECORDED_RUNS))
    repo, tip = a_repository(tmp_path)
    step = _step(_load_workflows()["pages.yml"], "decide", "id", "rule")
    env = _mapping(step.get("env"), "pages.yml decide rule env")
    assert set(env) == STEP_NAMES
    context: dict[str, object] = {
        "github": {
            "event_name": "workflow_run",
            "sha": tip,
            "ref_name": "main",
            "event": {"workflow_run": runs[recorded], "repository": {"default_branch": "main"}},
        },
        "steps": {"before": {"outputs": {"sha": runs["push_check_suite"]["before"]}}},
    }
    result = decision(repo, **{name: _resolved(value, context) for name, value in env.items()})
    assert result["publish"] == published
    assert result["ref"] == tip
