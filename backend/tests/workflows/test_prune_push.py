"""What does the corpus squash do when `main` moves while it is rewriting history?

`idhazh-gardener.yml`'s history job squashes everything older than the boundary
and force-pushes the result. A force push is a whole-ref operation: it replaces
the branch with this checkout, so a commit another run pushed in the meantime is
deleted and nothing records that it existed. A cron minute placed in the one
idle gap the serial digest schedule leaves lowers the odds, and a gap is not a
lock, so the push carries a lease on the tip the job read.

These drive one push of `backend/utilities/corpus_history.py` against real
repositories. The squash in front of it, and the passes after a refused push,
are driven end to end by `backend/tests/gardener/test_corpus_history.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utilities import corpus_history

from ._harness import (
    PRUNE_PUSH_CALL,
    PRUNE_PUSH_STEP,
    _git,
    _isolated_env,
    _load_workflows,
    _mapping,
    _race,
    _script,
    _scripted_origin,
    _step,
    _steps,
    _write,
)

pytestmark = pytest.mark.workflow

#: What the prune's boundary collapses. A tree with `corpus/` in it, because the
#: rows the squash exists to bound are the ones under that path.
CORPUS_ROW_FILE = "corpus/corpus.jsonl"

#: What a run that is not the prune pushes while the prune is rewriting. Outside
#: `corpus/`, because the commit a force push deletes is any commit, not only one
#: that touched what the prune was collapsing.
RACED_FILE = "docs/unrelated.md"


def _the_same_git(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """The program's own git calls see the isolated configuration the harness's do."""
    for name in ("HOME", "USERPROFILE", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"):
        monkeypatch.setenv(name, env[name])
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)


def _a_squashed_checkout(tmp_path: Path, env: dict[str, str]) -> tuple[Path, Path, str]:
    """The checkout the squash leaves behind, and the commit it started from.

    Two harvest commits so the orphan root has something to collapse, then the
    squash the program runs: a root commit holding the whole tree at the
    boundary, `main` rebased onto it, and the record of the run on top. Every
    commit the checkout now carries is new, so only a force push can land it -
    which is what makes the refusal worth testing.
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

    _write(runner / "corpus" / "corpus.meta.json", '{"last_run": "2026-09-22"}\n')
    _git(runner, env, "add", "corpus")
    _git(runner, env, "commit", "-m", "corpus: pruned 2026-09-22")
    return origin, runner, base


def test_the_prune_refuses_to_force_over_a_commit_that_landed_while_it_ran(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The oracle: a commit pushed between the checkout and the push survives.

    Without the lease this push replaces `main` with a history the racing
    commit is not in, and the only copy of it left is the other run's log line
    saying it had pushed. The words are pinned whole: they are what an operator
    reads, and they have not changed since the push was a program of its own.
    """
    env = _isolated_env(tmp_path)
    _the_same_git(env, monkeypatch)
    origin, runner, base = _a_squashed_checkout(tmp_path, env)
    _race(tmp_path, env, RACED_FILE, "a run pushed while the prune was rewriting\n")
    raced = _git(tmp_path / "other", env, "rev-parse", "HEAD").strip()
    assert raced != base, "the racing push must have moved the tip, or this tests nothing"

    code = corpus_history.push_rewritten(runner, tip_before=base, rewritten=True)

    assert code == 1
    assert capsys.readouterr().err.splitlines()[-5:] == [
        "main moved while the prune was rewriting it, so nothing was pushed",
        f"  this job checked out {base}",
        f"  origin/main is now {raced}",
        "pushing would discard every commit between the two.",
        "the prune is unstamped, so it is due again at the next daily wake.",
    ]
    # The pushed commit is still the tip, and its content is still readable.
    assert _git(origin, env, "rev-parse", "main").strip() == raced
    assert "prune was rewriting" in _git(origin, env, "show", f"{raced}:{RACED_FILE}")


def test_the_prune_lands_the_rewritten_history_when_nothing_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half: a refusal that refused everything would bound nothing.

    The window only bounds the repository when the rewrite reaches origin, so
    the day nobody raced, the force push still has to happen.
    """
    env = _isolated_env(tmp_path)
    _the_same_git(env, monkeypatch)
    origin, runner, base = _a_squashed_checkout(tmp_path, env)

    assert corpus_history.push_rewritten(runner, tip_before=base, rewritten=True) == 0

    assert (
        _git(origin, env, "rev-parse", "main").strip()
        == _git(runner, env, "rev-parse", "HEAD").strip()
    )
    # The pre-squash history is gone from origin, which is the whole point of it.
    assert base not in _git(origin, env, "log", "--format=%H", "main")


def test_a_run_that_rewrote_nothing_never_forces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a rewrite earns a forcing push, so a run that says it made none cannot replace main.

    Handed a checkout that only a force could land, the plain push is refused
    and origin keeps the history it had.
    """
    env = _isolated_env(tmp_path)
    _the_same_git(env, monkeypatch)
    origin, runner, base = _a_squashed_checkout(tmp_path, env)

    assert corpus_history.push_rewritten(runner, tip_before=base, rewritten=False) != 0

    assert _git(origin, env, "rev-parse", "main").strip() == base


def test_a_prune_that_squashed_nothing_still_refuses_a_tip_that_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record-only wake takes the same answer, and it costs nothing to give it.

    A plain push loses this race anyway - git refuses a non-fast-forward - so the
    outcome is the same failed step either way. Refusing here says which commit
    moved rather than leaving an operator to read a rejection message.
    """
    env = _isolated_env(tmp_path)
    _the_same_git(env, monkeypatch)
    origin, runner = _scripted_origin(tmp_path, env, ["corpus"])
    base = _git(runner, env, "rev-parse", "HEAD").strip()
    _write(runner / "corpus" / "corpus.meta.json", '{"last_run": "2026-09-22"}\n')
    _git(runner, env, "add", "corpus")
    _git(runner, env, "commit", "-m", "corpus: pruned 2026-09-22")
    _race(tmp_path, env, RACED_FILE, "a run pushed while the prune was reading\n")
    raced = _git(tmp_path / "other", env, "rev-parse", "HEAD").strip()

    assert corpus_history.push_rewritten(runner, tip_before=base, rewritten=False) == 1

    assert _git(origin, env, "rev-parse", "main").strip() == raced


def test_the_history_step_runs_the_shipped_program_and_nothing_else() -> None:
    """One step squashes, records and pushes, so the decision to force stays in one process.

    The tip the lease names has to be read before the rewrite, and the program
    reads it itself, so no step hands a commit or a flag to a later one through
    the job's environment. The day it squashes against is the due step's own
    reading, so the job reads the clock once.
    """
    workflow = _load_workflows()["idhazh-gardener.yml"]
    step = _step(workflow, "history", "name", PRUNE_PUSH_STEP)

    assert tuple(_script(step, PRUNE_PUSH_STEP).split()) == PRUNE_PUSH_CALL, (
        "the step runs the shipped program and nothing else, or the tests are "
        "driving a second copy of it"
    )
    assert _mapping(step.get("env"), "history step env") == {
        "TODAY": "${{ steps.due.outputs.today }}",
        "RUN_ID": "${{ steps.due.outputs.today }}-${{ github.run_id }}",
        "ATTEMPT": "${{ github.run_attempt }}",
    }
    for other in _steps(workflow, "history"):
        script = other.get("run")
        assert not (isinstance(script, str) and "GITHUB_ENV" in script), (
            f"{other.get('name') or other.get('id')} writes the job environment, and the "
            "squash takes nothing from another step but the due step's outputs"
        )
