"""What does the shared commit script do when it loses the race to push?"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import read_text

from idhazh import ledger
from idhazh.evals import writer as score_writer

from ._harness import (
    COMMIT_IDENTITY,
    COMMIT_SCRIPT,
    COMMIT_STEPS,
    GIT_IDENTITY_SOURCES,
    RACED_ASSET,
    RACED_ITEM_ID,
    SUBSTITUTED_DATE,
    SUBSTITUTED_DAY_DIR,
    _chart,
    _commit_call,
    _digest_origin,
    _drop_command,
    _git,
    _isolated_env,
    _mid_rebase,
    _race,
    _race_the_day,
    _reading_its_output,
    _rebuild,
    _rebuild_command,
    _rows,
    _run_commit_script,
    _scripted_origin,
    _seed_ledger,
    _settled_in_the_clone,
    _step_outputs,
    _tracked,
    _write,
    requires_bash,
    requires_space_free_paths,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]


def test_every_committing_job_configures_the_same_identity() -> None:
    """The pipeline commits as itself, and it says so in one voice.

    A hosted runner carries no git identity, so a job that commits has to set
    one or `git commit` refuses. Two files set it and only one of them is
    executed by a test, so the other could drift to a different name and nothing
    would notice until a reader wondered who two different authors were.
    """
    found = {
        path.name: (
            re.search(r'git config user\.name "([^"]+)"', read_text(path)),
            re.search(r'git config user\.email "([^"]+)"', read_text(path)),
        )
        for path in GIT_IDENTITY_SOURCES
    }

    for name, (author, address) in found.items():
        assert author is not None, f"{name} commits, so it must set user.name"
        assert address is not None, f"{name} commits, so it must set user.email"
        assert f"{author.group(1)} <{address.group(1)}>" == COMMIT_IDENTITY


@requires_bash
@requires_space_free_paths
@pytest.mark.parametrize("job_name", sorted(COMMIT_STEPS))
def test_the_commit_step_pushes_what_it_staged(tmp_path: Path, job_name: str) -> None:
    staged_paths, settings = _commit_call(job_name)
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
    if "REGENERATE_COMMAND" in settings:
        # The push wins here, so the producer never runs. Point it at the
        # harness one anyway: the pipeline's own `assemble` anchors its paths on
        # the installed repository, so a regression that made it run would write
        # into the working repository rather than fail the test.
        settings = {**settings, "REGENERATE_COMMAND": _rebuild_command(SUBSTITUTED_DATE)}

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == (
        settings["COMMIT_MESSAGE"]
    )
    # The script sets the committer itself, and the test supplies none.
    assert _git(origin, env, "log", "-1", "--format=%an <%ae>").strip() == COMMIT_IDENTITY
    assert _git(runner, env, "status", "--porcelain").strip() == ""


@requires_bash
def test_the_commit_step_says_so_and_stops_when_nothing_changed(tmp_path: Path) -> None:
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
    before = _git(origin, env, "rev-parse", "main").strip()

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert settings["NOTHING_STAGED_MESSAGE"] in result.stdout
    assert _git(origin, env, "rev-parse", "main").strip() == before
    assert _git(runner, env, "rev-parse", "HEAD").strip() == before


@requires_bash
def test_the_commit_step_rebases_past_a_racing_commit(tmp_path: Path) -> None:
    """The whole point of the loop: a push that loses a race still lands."""
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, "docs/unrelated.md", "racing\n")
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    _write(runner / "runner-noise.txt", "dirty\n")
    _write(runner / "leftover.log", "kept\n")
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected, rebasing (attempt 1)" in result.stdout
    assert "discarding working-tree noise before the rebase:" in result.stdout
    assert "runner-noise.txt" in result.stdout
    assert _git(origin, env, "log", "--format=%s", "-2").splitlines() == [
        settings["COMMIT_MESSAGE"],
        "racing change",
    ]
    # The noise was discarded; the untracked file was not.
    assert (runner / "runner-noise.txt").read_text(encoding="ascii") == "clean\n"
    assert (runner / "leftover.log").is_file()
    assert _git(runner, env, "status", "--porcelain", "--untracked-files=no").strip() == ""


@requires_bash
def test_a_push_that_landed_first_try_reports_no_rebase(tmp_path: Path) -> None:
    """What the rebuild step reads. A clean push left the tree it was handed.

    Written explicitly rather than left unwritten. An output nobody wrote is the
    empty string, which is falsy and would skip the rebuild too - and which is
    indistinguishable from the script dying before it could answer.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
    settings, written = _reading_its_output(tmp_path, settings)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected" not in result.stdout
    assert _step_outputs(written) == {"rebased": "false"}


@requires_bash
def test_a_commit_that_staged_nothing_reports_no_rebase(tmp_path: Path) -> None:
    """Nothing was pushed, so there is no new tree for a later step to read."""
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, staged_paths)
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
    settings, written = _reading_its_output(tmp_path, settings)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert settings["NOTHING_STAGED_MESSAGE"] in result.stdout
    assert _step_outputs(written) == {"rebased": "false"}


@requires_bash
def test_a_push_that_lost_the_race_reports_the_rebase(tmp_path: Path) -> None:
    """The rebase replaced the checkout, so the build made before it is stale.

    This is what `digest.yml` keys the rebuild on. Run 33270983446 weighed one
    tree's pages against another tree's ceilings and failed a day that had
    already published; a rebase that reported nothing would do it again.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, "docs/unrelated.md", "racing\n")
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
    settings, written = _reading_its_output(tmp_path, settings)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected, rebasing (attempt 1)" in result.stdout
    assert _step_outputs(written) == {"rebased": "true"}


@requires_bash
def test_the_commit_script_still_runs_where_no_step_output_exists(tmp_path: Path) -> None:
    """The guard on the write, and it is what lets one copy of the script serve both.

    `set -u` ends the run on an unset variable, so an unguarded write would kill
    every one of these tests and anybody running the script by hand. Only a
    workflow step has `$GITHUB_OUTPUT`.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")

    assert "GITHUB_OUTPUT" not in {**env, **settings}, "the harness is what removes it"
    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "GITHUB_OUTPUT" not in result.stderr, "an unset variable must not end the script"
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == settings["COMMIT_MESSAGE"]


def test_every_way_out_of_the_commit_script_says_whether_it_rebased() -> None:
    """Three exits return zero and a fixture reaches two of them.

    The third - origin already holding everything a rebuild produced - needs a
    racing run that publishes the same items, and the value it reports decides
    whether the day's own gate reads a stale build. So the exits are checked
    where they are written instead.

    The argument-error exits above the function are deliberately out of scope.
    They fire before anything is committed, they fail the step, and a step that
    failed has already stopped the rebuild.
    """
    lines = read_text(COMMIT_SCRIPT).splitlines()
    defined = next(
        index for index, line in enumerate(lines) if line.startswith("report_rebased()")
    )

    exits = [
        index
        for index, line in enumerate(lines)
        if line.strip() in {"exit 0", "exit 1"} and index > defined
    ]
    assert len(exits) == 4, "three ways out with nothing wrong, and the one that gives up"
    for index in exits:
        before = [
            line.strip()
            for line in lines[max(0, index - 3) : index]
            if line.strip() and not line.strip().startswith("#")
        ]
        assert any("report_rebased" in line for line in before), (
            f"line {index + 1} leaves without saying whether the checkout was rewritten"
        )


@requires_bash
def test_a_racing_append_to_the_same_ledger_unions_instead_of_conflicting(
    tmp_path: Path,
) -> None:
    """Two runs appended two independent rows. Both belong, and nothing has to choose.

    This is where the loop used to die. `git pull --rebase origin main` was the
    one unguarded command in it, so a conflicting rebase ended the script inside
    attempt 1 under `set -e`: no attempt 2, no failure message, no day, and a
    checkout left mid-rebase. Measured that way on 2026-08-25, git 2.55.0, bash
    5.3.15. The ledgers carry `merge=union` now, so the union of both appends is
    the merge, and every command in the loop is guarded.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, f"{staged_paths[0]}/ledger.csv", "header\nrow-0\ntheirs\n")
    _write(runner / staged_paths[0] / "ledger.csv", "header\nrow-0\nours\n")
    settings = _settled_in_the_clone(settings, f"{staged_paths[0]}/ledger.csv", "header")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert _git(origin, env, "log", "--format=%s", "-2").splitlines() == [
        settings["COMMIT_MESSAGE"],
        "racing change",
    ]
    landed = _git(origin, env, "show", f"main:{staged_paths[0]}/ledger.csv").splitlines()
    assert landed[0] == "header"
    assert sorted(landed[1:]) == ["ours", "row-0", "theirs"]
    assert not _mid_rebase(runner)


@requires_bash
def test_a_rebase_it_cannot_finish_still_ends_the_script_cleanly(tmp_path: Path) -> None:
    """The guard, proved by running it: no command in the loop can exit early.

    A ledger retired upstream while this run appended to it is a modify/delete,
    which no merge driver resolves. The loop must abort the rebase, say what
    happened, print the failure message and leave the checkout usable - not stop
    on the line that failed.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    other = tmp_path / "other"
    _git(tmp_path, env, "clone", str(tmp_path / "origin.git"), str(other))
    _git(other, env, "rm", "--quiet", f"{staged_paths[0]}/ledger.csv")
    _git(other, env, "commit", "-m", "retire the ledger")
    _git(other, env, "push", "origin", "main")
    _write(runner / staged_paths[0] / "ledger.csv", "header\nrow-0\nours\n")
    settings = _settled_in_the_clone(settings, f"{staged_paths[0]}/ledger.csv", "header")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert "the rebase did not apply cleanly" in result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] in result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == "retire the ledger"
    assert not _mid_rebase(runner)


@requires_bash
@requires_space_free_paths
def test_the_day_publishes_when_origin_moved_under_it(tmp_path: Path) -> None:
    """The Oracle: a stale base is answered by a current base, not by a text merge.

    Run `32772221068` lost a finished day here. The assemble job checks out
    main's tip at TRIGGER time and the run takes 164-184 min, so the day was
    always rebuilt from a base up to three hours old, and the push found a main
    that had moved. Here it has moved twice: another run published the same day,
    and a pull request merged on top.

    So the day is refreshed from the tip the push wants and built again against
    it. Both runs' items reach the reader, both runs' rows reach all three
    ledgers exactly once, the pull request is untouched, and this run's rendered
    chart - which no producer in this job can make again - is still there.
    """
    date = SUBSTITUTED_DATE
    month = date[:7]
    staged_paths, settings = _commit_call("assemble")
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command(date),
        "DROP_RACED_ASSETS_COMMAND": _drop_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(
        tmp_path, env, date, ["item-c"], "Merge pull request #123 from someone/branch"
    )
    # This run: the visuals artifact unpacked a chart into the day's directory,
    # and assemble published two items on the base the checkout carried.
    _write(runner / SUBSTITUTED_DAY_DIR / "assets" / "chart-1.svg", "<svg />\n")
    _rebuild(runner, env, date, ["item-d", "item-e"])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert "rebuilding the day against origin/main" in result.stdout
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert _git(origin, env, "log", "--format=%s", "-3").splitlines() == [
        f"digest: {date}",
        "Merge pull request #123 from someone/branch",
        f"digest: {date}",
    ]

    day = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/digest.json"))
    assert day["items"] == ["item-a", "item-b", "item-c", "item-d", "item-e"]
    # Run three, not a second run two. The rebuild read the day origin holds, so
    # it knows which run it is; on its own last attempt it would not.
    assert day["runs"] == [
        {"n": 1, "items_added": 2},
        {"n": 2, "items_added": 1},
        {"n": 3, "items_added": 2},
    ]
    manifest = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/run.json"))
    assert manifest["runs"] == day["runs"]

    published = _rows(_git(origin, env, "show", f"main:{ledger.published_relpath(date)}"))
    scores = _rows(_git(origin, env, "show", f"main:{score_writer.ledger_relpath(date)}"))
    health = _rows(_git(origin, env, "show", f"main:{ledger.item_health_relpath(date)}"))
    every_item = ["item-a", "item-b", "item-c", "item-d", "item-e"]
    # Exactly once each. Two of these ledgers append blind, so a rebuild against
    # a base that already held this run's rows would show five items and seven
    # rows.
    assert [row["item_id"] for row in published] == every_item
    assert [row["item_id"] for row in scores] == every_item
    assert [row["item_id"] for row in health] == every_item

    telemetry = _rows(_git(origin, env, "show", f"main:frontend/public/telemetry/{month}.csv"))
    assert telemetry == health, "the public projection is a rewrite of item-health, not a merge"

    assert _git(origin, env, "show", "main:docs/unrelated.md") == "merged by a pull request\n"
    assert _tracked(origin, env, f"{SUBSTITUTED_DAY_DIR}/assets/chart-1.svg")
    assert (runner / SUBSTITUTED_DAY_DIR / "assets" / "chart-1.svg").is_file()
    assert not _mid_rebase(runner)


@requires_bash
@requires_space_free_paths
def test_two_runs_that_rendered_one_item_still_publish_the_day(tmp_path: Path) -> None:
    """The Oracle above, with the one thing it never had: both sides create the path.

    Run `32869125768` finished eight workers and a visual planner and then lost
    the whole day here. A chart was filed by its vertical and its ordinal within
    the day, and the ordinal was seeded by reading the day's directory - so two
    runs of one day, neither able to see what the other pushed, wrote
    `energy-01.svg`
    for DIFFERENT items with different bytes. Git cannot rebase two adds of one
    path, `assemble` exited 1, and the `items-*` artifacts expired with every
    summary in them.

    A chart is now filed under its item's own id, so that case cannot happen at
    all. What is left is this one: two runs rendering the SAME item, which is
    one story's picture drawn twice. The tip's copy is published and a reader
    may already hold that address, and the rebuild keeps the tip's item anyway,
    so this run's copy is dropped and the day publishes.
    """
    date = SUBSTITUTED_DATE
    raced, fresh = RACED_ITEM_ID, "energy-0000000002"
    fresh_asset = f"digest/{date.replace('-', '/')}/{fresh}.json"
    staged_paths, settings = _commit_call("assemble")
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command(date),
        "DROP_RACED_ASSETS_COMMAND": _drop_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(
        tmp_path,
        env,
        date,
        [raced],
        "Merge pull request #125 from someone/branch",
        charts={raced: RACED_ASSET},
    )
    # This run planned the same item, because the push above had not happened
    # when it planned - and drew it again, to different bytes.
    _chart(runner, date, raced, RACED_ASSET, body="ours")
    _chart(runner, date, fresh, fresh_asset)
    _rebuild(runner, env, date, [raced, fresh])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert f"{RACED_ASSET} is already published, so this run's copy of it was dropped" in (
        result.stdout
    )
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert not _mid_rebase(runner)

    day = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/digest.json"))
    assert day["items"] == ["item-a", "item-b", raced, fresh]
    # The item this run introduced kept its picture, and no two items share one.
    assert day["visuals"] == {raced: RACED_ASSET, fresh: fresh_asset}
    assert len(set(day["visuals"].values())) == len(day["visuals"])
    # The gate a broken image would fail: every path the day publishes is a file
    # the day publishes. A picture that 404s is worse than a job that stops.
    for relpath in day["visuals"].values():
        assert _tracked(origin, env, f"frontend/public/{relpath}")
    # The published address still holds the bytes that were published under it,
    # rather than this run's second attempt at the same picture.
    assert _git(origin, env, "show", f"main:frontend/public/{RACED_ASSET}") == (
        f'{{"item_id": "{raced}"}}\n'
    )
    assert _git(origin, env, "show", f"main:frontend/public/{fresh_asset}") == (
        f'{{"item_id": "{fresh}"}}\n'
    )
    assert _git(origin, env, "show", "main:docs/unrelated.md") == "merged by a pull request\n"


@requires_bash
@requires_space_free_paths
def test_a_rebuild_that_fails_spends_the_attempts_and_says_which(tmp_path: Path) -> None:
    """A producer that cannot run is a lost day, said out loud, not a half-rebased tree."""
    date = SUBSTITUTED_DATE
    staged_paths, settings = _commit_call("assemble")
    # A date this checkout has no artifacts for: the producer really fails, on a
    # real missing input, rather than being told to pretend.
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command("2026-08-24"),
        "DROP_RACED_ASSETS_COMMAND": _drop_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(tmp_path, env, date, ["item-c"], "Merge pull request #124 from someone/other")
    _rebuild(runner, env, date, ["item-d"])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert "the rebuild failed against origin/main" in result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] in result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == (
        "Merge pull request #124 from someone/other"
    )
    assert not _mid_rebase(runner)
