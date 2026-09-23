"""Two jobs fold one closed day: when does the push agree, and when must it refuse?

The fold rewrites a whole day into one file, so two jobs that fold the same day
are two jobs writing one path. That is the one thing the day directory was built
to stop, and it is allowed here for one reason only: the fold is deterministic,
so two jobs that read the same day write the same bytes and git merges them
without being asked.

When the two jobs did NOT read the same day, the bytes differ and git conflicts.
`settled.csv` carries no writer's identity, so the commit script cannot tell
whose it is and stops the push. That refusal is the subject of the second half
here, and the reason it must refuse rather than resolve is what the assertions
are written against: taking the tip's copy would leave this job's DELETION of a
straggler's file standing, because git does not call a deletion a conflict, and
the straggler's rows would then exist in no file at exit 0.

Driven by `tests/fixtures/day-shards/closed-day/`, which is six writer files
over three days. Bounded, so it costs the same whatever the archive has
accumulated (CLAUDE.md section 13), and it carries a case the archive has never
produced.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_DIR

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.stages import compact

from ._harness import COMMIT_PROGRAM, _git, _isolated_env

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

#: The tree the fixture was written with, and the day the two jobs fight over.
FIXTURE: Final = FIXTURES_DIR / "day-shards" / "closed-day"
TREE: Final = ledger.SegmentLedger.HOST_FINGERPRINT
CONTESTED_DAY: Final = "2026-09-07"

#: A date far enough past the fixture that every day in it is closed, and the
#: cover a fold is taken with here.
AFTER_THE_FIXTURE: Final = "2026-10-01"
AFTER_DAYS: Final = 7

#: The date that closes every day of the fixture EXCEPT the contested one. The
#: two quiet days are folded before any of this starts, so the only path two
#: jobs can disagree about is the one the test is about.
BEFORE_THE_CONTESTED_DAY: Final = "2026-09-14"

#: The job the runner plays, spelled once. The commit script builds the identity
#: it matches a conflicted filename against out of these four.
JOB_RUN_ID: Final = "40000000001"
JOB_ATTEMPT: Final = "1"
JOB_NAME: Final = "assemble"
JOB_SHARD: Final = "0"


def the_fixture_on(root: Path) -> Path:
    """The fixture copied into a working tree, and the tree's own `state/`.

    Copied rather than read in place, because every test here folds it and a
    fold deletes the files it read.
    """
    shutil.copytree(FIXTURE, root, dirs_exist_ok=True)
    return root / ledger.STATE_DIRNAME


def fold(state: Path, *, date: str = AFTER_THE_FIXTURE) -> compact.CompactionReport:
    """The fold taken against a date the days it is meant to take are closed behind."""
    return compact.stage_compact(state, date=date, after_days=AFTER_DAYS)


def day_dir(state: Path, date: str) -> Path:
    """Where one day of the fixture's tree sits."""
    return state / TREE.value / date[:4] / date[5:7] / date[8:10]


def files_under(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by POSIX relative path, with its bytes."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def machines_in(path: Path) -> list[str]:
    """Which machines a settled file names, read without newline translation."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [row["cpu_model"] for row in csv.DictReader(handle)]


def a_straggler(state: Path, date: str) -> Path:
    """One writer file landing on a day two other jobs already folded.

    A re-run of the day: the run id is a second execution, which is what makes
    its filename different from anything the fixture carries.
    """
    ledger.write_segment(
        state,
        TREE,
        [
            HostFingerprintRow.model_validate(
                {
                    "date": date,
                    "run_id": f"{date}-900000002",
                    "job": ServerJob.WORK,
                    "shard": 9,
                    "fingerprint": "fedcba9876543210",
                    "measured_at": f"{date}T12:00:00Z",
                    "cpu_model": "the straggler machine",
                }
            )
        ],
        run_id=f"{date}-900000002",
        attempt=1,
        job=ServerJob.WORK,
        shard=9,
    )
    return day_dir(state, date) / ledger.segment_name(
        run_id=f"{date}-900000002", attempt=1, job=ServerJob.WORK, shard=9
    )


# --- The fold is deterministic -------------------------------------------------


def test_two_folds_of_one_closed_day_write_the_same_bytes(tmp_path: Path) -> None:
    """The whole licence for two jobs writing one path.

    Two copies of one fixture, folded independently, compared byte for byte
    rather than row for row: a fold that agreed on the rows and disagreed on
    their order would conflict on every run, which is the cost this claim is
    supposed to rule out.
    """
    first = the_fixture_on(tmp_path / "first")
    second = the_fixture_on(tmp_path / "second")

    fold(first)
    fold(second)

    written = files_under(first)
    assert written, "the fixture folded to nothing, so this compared two empty trees"
    assert written == files_under(second)
    assert all(
        Path(relpath).name == day_shards.SETTLED_NAME for relpath in written
    ), "a writer file survived the fold, so the comparison was not about settled files"


def test_two_branches_that_both_fold_one_day_merge_without_being_asked(
    tmp_path: Path,
) -> None:
    """Determinism, taken where it has to hold: git's own merge of two folds.

    The previous test proves the bytes match. This one proves git agrees, which
    is the claim the pipeline actually rests on - two assemble jobs of one night
    both fold, both push, and neither run waits for the other.
    """
    env = _isolated_env(tmp_path)
    repo = tmp_path / "repo"
    state = the_fixture_on(repo)
    _git(repo, env, "init", "--initial-branch=main", "--quiet")
    _git(repo, env, "add", "--", ledger.STATE_DIRNAME)
    _git(repo, env, "commit", "--quiet", "-m", "the day before either job folded")

    _git(repo, env, "checkout", "--quiet", "-b", "first-job")
    fold(state)
    _git(repo, env, "add", "--all", "--", ledger.STATE_DIRNAME)
    _git(repo, env, "commit", "--quiet", "-m", "the first job folds the day")

    _git(repo, env, "checkout", "--quiet", "main")
    _git(repo, env, "checkout", "--quiet", "-b", "second-job")
    fold(state)
    _git(repo, env, "add", "--all", "--", ledger.STATE_DIRNAME)
    _git(repo, env, "commit", "--quiet", "-m", "the second job folds the day")

    merged = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "merge", "first-job"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )

    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert not _git(repo, env, "diff", "--name-only", "--diff-filter=U").strip()
    assert machines_in(day_dir(state, CONTESTED_DAY) / day_shards.SETTLED_NAME)


# --- The fold that read a different day ----------------------------------------


def test_a_fold_that_read_a_straggler_the_tip_did_not_stops_the_push(
    tmp_path: Path,
) -> None:
    """Two folds of one day that read different files, and the loser must not win.

    The runner's checkout carries a straggler the tip's fold never saw, so the
    two settled files differ and the rebase conflicts on `settled.csv`. It
    carries no writer's identity, so the script cannot say whose it is and stops.

    Resolving it per path is what loses rows here. Taking the tip's copy would
    leave this job's DELETION of the straggler standing - git does not call a
    deletion a conflict - and the straggler's rows would then be in no file at
    exit 0.
    """
    env = _isolated_env(tmp_path)

    # The base every side starts from: the two quiet days already folded, the
    # contested day still holding its writer files. Folded first so the only
    # path the two jobs can disagree about is the one this is about.
    origin = tmp_path / "origin.git"
    _git(tmp_path, env, "init", "--bare", "--initial-branch=main", "--quiet", str(origin))
    seed = tmp_path / "seed"
    seed_state = the_fixture_on(seed)
    fold(seed_state, date=BEFORE_THE_CONTESTED_DAY)
    contested = day_dir(seed_state, CONTESTED_DAY)
    assert day_shards.SETTLED_NAME not in {path.name for path in contested.iterdir()}, (
        "the contested day was folded before the test started"
    )
    _git(seed, env, "init", "--initial-branch=main", "--quiet")
    _git(seed, env, "remote", "add", "origin", str(origin))
    _git(seed, env, "add", "--", ledger.STATE_DIRNAME)
    _git(seed, env, "commit", "--quiet", "-m", "the quiet days folded, the contested day open")
    _git(seed, env, "push", "--quiet", "origin", "main")

    # What the tip will hold: an earlier job's fold of the contested day WITHOUT
    # the straggler. Folded from its own copy of the base, so the two sides
    # really did read different files rather than being told they did.
    earlier = the_fixture_on(tmp_path / "earlier")
    fold(earlier, date=BEFORE_THE_CONTESTED_DAY)
    fold(earlier)
    tip_settled = (day_dir(earlier, CONTESTED_DAY) / day_shards.SETTLED_NAME).read_bytes()

    # The straggler lands first, so the runner's checkout carries it.
    straggler = a_straggler(seed_state, CONTESTED_DAY)
    straggler_relpath = straggler.relative_to(seed).as_posix()
    _git(seed, env, "add", "--", ledger.STATE_DIRNAME)
    _git(seed, env, "commit", "--quiet", "-m", "a re-run's shard lands on a day two jobs will fold")
    _git(seed, env, "push", "--quiet", "origin", "main")

    runner = tmp_path / "runner"
    _git(tmp_path, env, "clone", "--quiet", str(origin), str(runner))
    runner_state = runner / ledger.STATE_DIRNAME
    assert (runner / straggler_relpath).exists(), "the runner did not check the straggler out"
    folded = fold(runner_state)
    assert folded.days_folded == 1, "the runner folded a day this test did not leave open"

    # The earlier job wins the race: its fold reaches origin while the runner is
    # still working, and the straggler stays beside it because that fold never
    # read it.
    settled_relpath = (
        (contested / day_shards.SETTLED_NAME).relative_to(seed).as_posix()
    )
    for path in sorted(contested.iterdir()):
        if path != straggler:
            path.unlink()
    (seed / settled_relpath).write_bytes(tip_settled)
    _git(seed, env, "add", "--all", "--", ledger.STATE_DIRNAME)
    _git(seed, env, "commit", "--quiet", "-m", "an earlier job folds the day it could see")
    _git(seed, env, "push", "--quiet", "origin", "main")

    refused = subprocess.run(
        [sys.executable, COMMIT_PROGRAM.as_posix(), ledger.STATE_DIRNAME],
        cwd=runner,
        env={
            **env,
            "COMMIT_MESSAGE": "fold the days that can gain no more rows",
            "NOTHING_STAGED_MESSAGE": "nothing to fold",
            "PUSH_FAILED_MESSAGE": "the fold could not be pushed",
            "PUSH_DEADLINE_SECONDS": "30",
            "GITHUB_RUN_ID": JOB_RUN_ID,
            "GITHUB_RUN_ATTEMPT": JOB_ATTEMPT,
            "GITHUB_JOB": JOB_NAME,
            "SHARD": JOB_SHARD,
        },
        capture_output=True,
        text=True,
    )

    assert refused.returncode != 0, (
        "the push reported success over a conflict nobody could resolve:\n"
        + refused.stdout
        + refused.stderr
    )
    said = refused.stdout + refused.stderr
    assert settled_relpath in said, (
        "the refusal did not name the contested path, so it stopped for another reason:\n" + said
    )

    # Nothing the tip held went with the refusal. Its own fold is still there,
    # and so is the straggler this job's commit would have deleted.
    after = tmp_path / "after"
    _git(tmp_path, env, "clone", "--quiet", str(origin), str(after))
    assert (after / settled_relpath).read_bytes() == tip_settled
    assert (after / straggler_relpath).exists(), (
        "the straggler's rows are in no file, which is what the refusal exists to stop"
    )
    held = machines_in(after / settled_relpath) + machines_in(after / straggler_relpath)
    assert "the straggler machine" in held
    assert len(held) == len(machines_in(tmp_path / "earlier" / settled_relpath)) + 1
