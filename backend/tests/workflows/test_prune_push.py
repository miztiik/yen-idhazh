"""What does the prune do when `main` moves while it is rewriting history?

`prune.yml` squashes everything older than the boundary and force-pushes the
result. A force push is a whole-ref operation: it replaces the branch with this
checkout, so a commit another run pushed in the meantime is deleted and nothing
records that it existed. Until now the only thing holding that off was a cron
minute placed in the one idle gap the serial digest schedule leaves, and a gap
is not a lock.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ._harness import (
    PRUNE_BASE_ENV,
    PRUNE_PUSH_CALL,
    PRUNE_PUSH_MODULE,
    PRUNE_PUSH_STEP,
    PRUNE_REMEMBER_STEP,
    PRUNE_SQUASH_STEP,
    _git,
    _isolated_env,
    _load_workflows,
    _race,
    _script,
    _scripted_origin,
    _step,
    _steps,
    _write,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

#: What the prune's boundary collapses. A tree with `corpus/` in it, because the
#: rows the squash exists to bound are the ones under that path.
CORPUS_ROW_FILE = "corpus/corpus.jsonl"

#: What a run that is not the prune pushes while the prune is rewriting. Outside
#: `corpus/`, because the commit a force push deletes is any commit, not only one
#: that touched what the prune was collapsing.
RACED_FILE = "docs/unrelated.md"


def _push_the_rewritten_history(
    runner: Path, env: dict[str, str], base: str, squashed: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PRUNE_PUSH_MODULE)],
        cwd=runner,
        env={**env, PRUNE_BASE_ENV: base, "SQUASHED": squashed},
        capture_output=True,
        text=True,
    )


def _a_squashed_checkout(tmp_path: Path, env: dict[str, str]) -> tuple[Path, Path, str]:
    """The checkout the prune leaves behind, and the commit it started from.

    Two harvest commits so the orphan root has something to collapse, then the
    squash the workflow runs: a root commit holding the whole tree at the
    boundary, `main` rebased onto it, and the stamp on top. Every commit the
    checkout now carries is new, so only a force push can land it - which is what
    makes the refusal worth testing.
    """
    origin, runner = _scripted_origin(tmp_path, env, ["corpus"])
    for row in (1, 2):
        _write(runner / CORPUS_ROW_FILE, "".join(f'{{"row": {index}}}\n' for index in range(row)))
        _git(runner, env, "add", "corpus")
        _git(runner, env, "commit", "-m", f"corpus: harvest {row}")
    _git(runner, env, "push", "origin", "main")
    base = _git(runner, env, "rev-parse", "HEAD").strip()

    cut = _git(runner, env, "rev-parse", "HEAD~1").strip()
    _git(runner, env, "checkout", "--orphan", "pruned-root", cut)
    _git(runner, env, "commit", "-m", "corpus: squash history older than 60 days")
    root = _git(runner, env, "rev-parse", "HEAD").strip()
    _git(runner, env, "checkout", "main")
    _git(runner, env, "rebase", "--onto", root, cut, "main")

    _write(runner / "corpus" / "corpus.meta.json", '{"pruned_date": "2026-09-22"}\n')
    _git(runner, env, "add", "corpus")
    _git(runner, env, "commit", "-m", "corpus: pruned 2026-09-22")
    return origin, runner, base


def test_the_prune_refuses_to_force_over_a_commit_that_landed_while_it_ran(
    tmp_path: Path,
) -> None:
    """The oracle: a commit pushed between the checkout and the push survives.

    Without the re-fetch this push replaces `main` with a history the racing
    commit is not in, and the only copy of it left is the other run's log line
    saying it had pushed.
    """
    env = _isolated_env(tmp_path)
    origin, runner, base = _a_squashed_checkout(tmp_path, env)
    _race(tmp_path, env, RACED_FILE, "a run pushed while the prune was rewriting\n")
    raced = _git(tmp_path / "other", env, "rev-parse", "HEAD").strip()
    assert raced != base, "the racing push must have moved the tip, or this tests nothing"

    result = _push_the_rewritten_history(runner, env, base, squashed="true")

    assert result.returncode != 0, result.stdout
    # Both commits, so an operator reading the failed run knows what moved.
    assert base in result.stderr, result.stderr
    assert raced in result.stderr, result.stderr
    assert "due again" in result.stderr, result.stderr
    # The pushed commit is still the tip, and its content is still readable.
    assert _git(origin, env, "rev-parse", "main").strip() == raced
    assert "prune was rewriting" in _git(origin, env, "show", f"{raced}:{RACED_FILE}")


def test_the_prune_lands_the_rewritten_history_when_nothing_moved(tmp_path: Path) -> None:
    """The other half: a refusal that refused everything would bound nothing.

    `prune_keep_days` only bounds the repository when the rewrite reaches origin,
    so the day nobody raced, the force push still has to happen.
    """
    env = _isolated_env(tmp_path)
    origin, runner, base = _a_squashed_checkout(tmp_path, env)

    result = _push_the_rewritten_history(runner, env, base, squashed="true")

    assert result.returncode == 0, result.stderr
    assert (
        _git(origin, env, "rev-parse", "main").strip()
        == _git(runner, env, "rev-parse", "HEAD").strip()
    )
    # The pre-squash history is gone from origin, which is the whole point of it.
    assert base not in _git(origin, env, "log", "--format=%H", "main")


def test_a_prune_that_squashed_nothing_still_refuses_a_tip_that_moved(tmp_path: Path) -> None:
    """The stamp-only wake takes the same answer, and it costs nothing to give it.

    A plain push loses this race anyway - git refuses a non-fast-forward - so the
    outcome is the same failed step either way. Refusing here says which commit
    moved rather than leaving an operator to read a rejection message.
    """
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, ["corpus"])
    base = _git(runner, env, "rev-parse", "HEAD").strip()
    _write(runner / "corpus" / "corpus.meta.json", '{"pruned_date": "2026-09-22"}\n')
    _git(runner, env, "add", "corpus")
    _git(runner, env, "commit", "-m", "corpus: pruned 2026-09-22")
    _race(tmp_path, env, RACED_FILE, "a run pushed while the prune was reading\n")
    raced = _git(tmp_path / "other", env, "rev-parse", "HEAD").strip()

    result = _push_the_rewritten_history(runner, env, base, squashed="false")

    assert result.returncode != 0, result.stdout
    assert _git(origin, env, "rev-parse", "main").strip() == raced


def test_the_prune_remembers_its_tip_before_it_rewrites_anything() -> None:
    """A base commit read after the squash names a commit only this job holds.

    The comparison is against origin's tip, so the value it is compared with has
    to be what origin handed over. The rebase replaces every commit below the
    boundary, so by the time the stamp is written there is nothing left in the
    checkout that still names it - which is why the reading step sits above the
    squash rather than beside the push.
    """
    workflow = _load_workflows()["prune.yml"]
    names = [step.get("name") for step in _steps(workflow, "prune")]

    for step_name in (PRUNE_REMEMBER_STEP, PRUNE_SQUASH_STEP, PRUNE_PUSH_STEP):
        assert step_name in names, f"prune.yml no longer runs {step_name!r}"
    assert names.index(PRUNE_REMEMBER_STEP) < names.index(PRUNE_SQUASH_STEP)

    remembered = _script(_step(workflow, "prune", "name", PRUNE_REMEMBER_STEP), PRUNE_REMEMBER_STEP)
    assert f'{PRUNE_BASE_ENV}=$(git rev-parse HEAD)' in remembered
    assert '>> "$GITHUB_ENV"' in remembered, "a later step reads it, so it goes to the job env"

    pushed = _script(_step(workflow, "prune", "name", PRUNE_PUSH_STEP), PRUNE_PUSH_STEP)
    assert tuple(pushed.split()) == PRUNE_PUSH_CALL, (
        "the push runs the shipped script and nothing else, or the tests above "
        "are driving a second copy of it"
    )
