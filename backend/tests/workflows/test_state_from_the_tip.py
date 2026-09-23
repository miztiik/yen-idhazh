"""Does the plan job fold the segment store origin has, or the one its trigger had?

`actions/checkout` restores the commit a run was triggered at. The run then
waits for a runner, and another run may commit under `state/` the whole time,
so nothing bounds the distance between those two moments. Every step in between
that only APPENDS survives a stale base, because a rebase applies two appends
whole. The catch-up fold does not: it derives a day head from the segment store,
so a stale store makes it re-fold rows another run has already folded and
rewrite a head that run has already written. Two derived versions of one file is
the one shape a rebase cannot settle.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ._harness import (
    TAKE_STATE_MODULE,
    _git,
    _isolated_env,
    _scripted_origin,
    _write,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

#: One waiting segment and the day head its rows name. A segment is named for
#: one shard of one run, which is why a rebase never has to settle one - and why
#: a checkout that still holds a drained copy is invisible until the fold reads
#: it.
SEGMENT = "state/segments/scores/2026-09-21-35645482100-1-work-03.csv"
HEAD = "state/scores/2026/09/21.csv"
OUTSIDE = "docs/unrelated.md"


def _take_the_state(
    runner: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TAKE_STATE_MODULE), *args],
        cwd=runner,
        env=env,
        capture_output=True,
        text=True,
    )


def _a_stale_checkout(tmp_path: Path, env: dict[str, str]) -> tuple[Path, str, str]:
    """A runner pinned to a commit the run ahead of it has already folded past.

    The runner's commit holds a segment nobody has folded. The commit after it,
    which only origin has, is that run's assemble: the segment is drained, the
    head carries its row, and a file outside `state` moved in the same commit.
    """
    origin, runner = _scripted_origin(tmp_path, env, ["state"])
    _write(runner / SEGMENT, "url_key,score\nitem-a,7\n")
    _write(runner / HEAD, "url_key,score\n")
    _git(runner, env, "add", "state")
    _git(runner, env, "commit", "-m", "the commit this run was triggered at")
    _git(runner, env, "push", "origin", "main")
    trigger = _git(runner, env, "rev-parse", "HEAD").strip()

    ahead = tmp_path / "ahead"
    _git(tmp_path, env, "clone", str(origin), str(ahead))
    (ahead / SEGMENT).unlink()
    _write(ahead / HEAD, "url_key,score\nitem-a,7\n")
    _write(ahead / OUTSIDE, "the run ahead edited this\n")
    _git(ahead, env, "add", "state", "docs")
    _git(ahead, env, "commit", "-m", "the run ahead folds and pushes")
    _git(ahead, env, "push", "origin", "main")
    return runner, trigger, _git(ahead, env, "rev-parse", "HEAD").strip()


def test_a_segment_the_run_ahead_drained_is_gone_before_the_fold_can_read_it(
    tmp_path: Path,
) -> None:
    """The file that starts the double fold, and the head that ends it.

    Restoring the tip's `state` on its own would leave the drained segment
    sitting there - git writes what the tip HAS and says nothing about what it
    does not. That one file is the whole failure: the fold reads it, folds a row
    the tip already folded, and writes a head that disagrees with the tip's.
    """
    env = _isolated_env(tmp_path)
    runner, _, tip = _a_stale_checkout(tmp_path, env)

    result = _take_the_state(runner, env, "state")

    assert result.returncode == 0, result.stderr
    assert not (runner / SEGMENT).exists()
    assert (runner / HEAD).read_text(encoding="ascii") == "url_key,score\nitem-a,7\n"
    assert _git(runner, env, "ls-files", "--", SEGMENT).strip() == ""
    assert _git(runner, env, "rev-parse", f"{tip}:{HEAD}").strip() == _git(
        runner, env, "hash-object", HEAD
    ).strip()


def test_the_code_the_job_runs_stays_on_the_commit_that_triggered_it(
    tmp_path: Path,
) -> None:
    """Only the named path moves, and the job's own history does not move at all.

    A job that took the tip whole would change its own behaviour halfway
    through: the run would be reading feeds with one build and committing with
    another, and no log line would say which. Moving HEAD would also hand the
    commit step a base it never read.
    """
    env = _isolated_env(tmp_path)
    runner, trigger, _ = _a_stale_checkout(tmp_path, env)

    result = _take_the_state(runner, env, "state")

    assert result.returncode == 0, result.stderr
    assert _git(runner, env, "rev-parse", "HEAD").strip() == trigger
    assert (runner / OUTSIDE).read_text(encoding="ascii") == "seed\n"


def test_the_path_to_take_is_required(tmp_path: Path) -> None:
    """A workflow edit that drops the argument must stop the job, not empty a tree.

    Without the guard the `git rm -r` below it runs over an empty pathspec, and
    git reads that as the whole repository.
    """
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, ["state"])

    assert _take_the_state(runner, env).returncode == 2
    assert _take_the_state(runner, env, "state", "corpus").returncode == 2
