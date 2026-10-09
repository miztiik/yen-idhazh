"""Does a shard land exactly what it wrote and deleted, once, however the push race goes?

Every test pushes to a real bare repository standing in for origin, from a real
clone, with no network. A race is staged the way it happens: another clone
pushes first, or the origin refuses a push through its own hook, or the hook
moves main first and then refuses, the way a run of other writers looks. A
re-run is a clone whose paths main changed after the clone was made. The
idempotence oracle is that running the loop twice leaves the tree running it
once left, the moved-tip oracle is that the mover's change and this shard's both
survive, and the stale oracle is that main's newer file survives and nothing of
the shard lands.

The loop is `backend/utilities/gardener_publish.py`, because nothing under
`backend/idhazh/` may start a process.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as parquet
import pytest
from pydantic import ValidationError

from idhazh.contracts.shard_landing import ShardLanding
from idhazh.gardener.outcome import (
    EXIT_INTEGRITY,
    EXIT_OK,
    EXIT_PUSH_REFUSED,
    EXIT_TASK_FAILED,
    Shard,
    worst,
)
from utilities import commit_and_push, gardener_publish
from utilities.gardener_publish import PushOutcome

from ._garden import (
    OriginBlobs,
    a_hook,
    a_partial_clone,
    an_origin,
    commits_on,
    git,
    on_origin,
    quiet_git,
    write,
)

RECORD = "state/raw/gardener/2026/09/27/record.json"
AGED = "state/old/2026-01-01.txt"
KEPT = "state/old/2026-09-26.txt"
MESSAGE = "gardener: old on 2026-09-27"
SEEDED = {AGED: "aged\n", KEPT: "kept\n", "state/dir/a.txt": "a\n", ".gitignore": "*.skip\n"}

#: A pre-receive hook that moves `main` to the next prepared commit, `refs/race/<n>`
#: on the n-th push, and then refuses that push: on every try another writer lands
#: first. It steps out of the quarantine the pushed objects wait in, because git
#: refuses a ref update from inside it.
MOVE_MAIN_THEN_REFUSE = (
    'race=$(( $(cat "$GIT_DIR/race-count" 2>/dev/null || echo 0) + 1 ))\n'
    'echo "$race" > "$GIT_DIR/race-count"\n'
    "unset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES\n"
    'git update-ref refs/heads/main "refs/race/$race" || exit 2\n'
    "exit 1"
)


def a_shard(*, written: set[str] | None = None, deleted: set[str] | None = None) -> Shard:
    return Shard(
        index=0,
        task_names=("old",),
        record_path=RECORD,
        written_paths=frozenset({RECORD, *(written or set())}),
        deleted_paths=frozenset(deleted or set()),
        owned_prefixes=frozenset(
            {
                "state/raw/gardener",
                "state/old",
                "state/dir",
                "state/newdir",
                "state/compact/council-run-records",
            }
        ),
        message=MESSAGE,
    )


def a_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """An origin seeded with a small tree, and a clone whose shard wrote its record."""
    quiet_git(tmp_path, monkeypatch)
    origin, checkout = an_origin(tmp_path, SEEDED)
    write(checkout / RECORD, '{"task": "old"}\n')
    return origin, checkout


def landed(shard: Shard, checkout: Path, *, attempts: int = 6) -> tuple[PushOutcome, list[str]]:
    """What the push loop came to, and every line it printed."""
    said: list[str] = []
    pushed = gardener_publish.publish(shard, attempts=attempts, repo=checkout, say=said.append)
    return pushed, said


def test_a_shard_lands_its_writes_and_deletions_in_one_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    (checkout / AGED).unlink()

    pushed, said = landed(a_shard(deleted={AGED}), checkout)

    assert pushed == PushOutcome(EXIT_OK, ShardLanding.LANDED, 1)
    assert said == [], "a landing is the shard's event to say, not a printed line"
    assert on_origin(origin, RECORD) == '{"task": "old"}\n'
    assert on_origin(origin, AGED) is None
    assert on_origin(origin, KEPT) == "kept\n", "a file the shard did not delete went"
    identity = f"{commit_and_push.COMMITTER_NAME} <{commit_and_push.COMMITTER_EMAIL}>"
    assert commits_on(origin)[0] == f"{identity}: {MESSAGE}"
    assert (gardener_publish.COMMITTER_NAME, gardener_publish.COMMITTER_EMAIL) == (
        commit_and_push.COMMITTER_NAME,
        commit_and_push.COMMITTER_EMAIL,
    )


@pytest.mark.parametrize("deleting", [False, True])
def test_a_task_result_does_not_grant_an_undeclared_change_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, deleting: bool
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    tip = git(origin, "rev-parse", "main")
    if deleting:
        (checkout / "README.md").unlink()
        shard = a_shard(deleted={"README.md"})
    else:
        write(checkout / "README.md", "outside the task and venue declarations\n")
        shard = a_shard(written={"README.md"})

    pushed, said = landed(shard, checkout)

    assert pushed.exit_code == EXIT_INTEGRITY
    assert any("outside its declared" in line for line in said)
    assert git(origin, "rev-parse", "main") == tip
    assert on_origin(origin, RECORD) is None
    assert on_origin(origin, "README.md") == "seed\n"


def test_running_it_twice_leaves_the_tree_running_it_once_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    (checkout / AGED).unlink()
    shard = a_shard(deleted={AGED})

    assert landed(shard, checkout)[0].exit_code == EXIT_OK
    once = git(origin, "rev-parse", "main^{tree}"), len(commits_on(origin))
    pushed, said = landed(shard, checkout)

    assert pushed == PushOutcome(EXIT_OK, ShardLanding.ALREADY_ON_MAIN, 1)
    assert said == []
    assert (git(origin, "rev-parse", "main^{tree}"), len(commits_on(origin))) == once


def test_fetch_preserves_a_deep_checkouts_ancestry_for_its_push_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    root = git(checkout, "rev-parse", "HEAD").strip()
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / "README.md", "another commit\n")
    git(mover, "add", "README.md")
    git(mover, "commit", "--quiet", "-m", "advance main")
    git(mover, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    hook = write(
        checkout / ".git" / "hooks" / "pre-push",
        "#!/bin/sh\n"
        "while read -r local_ref local_sha remote_ref remote_sha; do\n"
        f'  git merge-base --is-ancestor {root} "$local_sha" || exit 1\n'
        "done\n",
    )
    hook.chmod(0o755)

    fetched = gardener_publish.Checkout(checkout).fetch()

    git(checkout, "merge-base", "--is-ancestor", root, fetched)
    assert git(checkout, "rev-parse", "--is-shallow-repository").strip() == "false"
    assert landed(a_shard(), checkout)[0].exit_code == EXIT_OK
    git(origin, "merge-base", "--is-ancestor", root, "main")


def test_fetch_keeps_a_depth_one_clone_shallow_and_downloads_only_new_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, mover = an_origin(tmp_path, SEEDED)
    for number in range(2):
        write(mover / "README.md", f"prior commit {number}\n")
        git(mover, "add", "README.md")
        git(mover, "commit", "--quiet", "-m", f"prior commit {number}")
    git(mover, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "--quiet", "--depth=1", origin.as_uri(), str(shallow))
    assert git(shallow, "rev-list", "--count", "origin/main").strip() == "1"
    for number in range(2):
        write(mover / "README.md", f"new commit {number}\n")
        git(mover, "add", "README.md")
        git(mover, "commit", "--quiet", "-m", f"new commit {number}")
    git(mover, "push", "--quiet", "origin", "HEAD:refs/heads/main")

    fetched = gardener_publish.Checkout(shallow).fetch()

    assert fetched == git(origin, "rev-parse", "main").strip()
    assert git(shallow, "rev-parse", "--is-shallow-repository").strip() == "true"
    assert git(shallow, "rev-list", "--count", "origin/main").strip() == "3"
    assert git(origin, "rev-list", "--count", "main").strip() == "5"
    gardener_publish.Checkout(shallow).fetch()
    assert git(shallow, "rev-list", "--count", "origin/main").strip() == "3"


def test_a_tip_that_moved_keeps_the_movers_change_and_this_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Main moved on a path this shard does not touch, so the shard's version is not stale."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / "docs/moved.md", "the other shard\n")
    git(mover, "add", "docs/moved.md")
    git(mover, "commit", "--quiet", "-m", "another shard landed first")
    git(mover, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    (checkout / AGED).unlink()

    pushed, _ = landed(a_shard(deleted={AGED}), checkout)

    assert pushed == PushOutcome(EXIT_OK, ShardLanding.LANDED, 1)
    assert on_origin(origin, "docs/moved.md") == "the other shard\n"
    assert on_origin(origin, RECORD) is not None
    assert on_origin(origin, AGED) is None
    assert [line.split(": ", 1)[1] for line in commits_on(origin)[:2]] == [
        MESSAGE,
        "another shard landed first",
    ]


def test_a_raw_arrival_survives_an_older_compactors_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    raw = "state/raw/council-run-records/2026/09/20/arrival.parquet"
    packed = "state/compact/council-run-records/daily/2026/09/20.parquet"
    mover = tmp_path / "writer"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    (mover / raw).parent.mkdir(parents=True, exist_ok=True)
    parquet.write_table(pa.table({"writer": ["later"]}), mover / raw)
    raw_bytes = (mover / raw).read_bytes()
    git(mover, "add", raw)
    git(mover, "commit", "--quiet", "-m", "another writer filed raw data")
    git(mover, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    (checkout / packed).parent.mkdir(parents=True, exist_ok=True)
    parquet.write_table(pa.table({"writer": ["older"]}), checkout / packed)

    pushed, _ = landed(a_shard(written={packed}), checkout)

    assert pushed.exit_code == EXIT_OK
    landed_checkout = tmp_path / "landed"
    git(tmp_path, "clone", "--quiet", str(origin), str(landed_checkout))
    assert (landed_checkout / raw).read_bytes() == raw_bytes
    assert parquet.read_table(landed_checkout / packed).to_pydict() == {"writer": ["older"]}


def test_a_push_that_lost_is_tried_again_on_the_new_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    a_hook(
        origin,
        'if [ -f "$GIT_DIR/lost-once" ]; then exit 0; fi\ntouch "$GIT_DIR/lost-once"\nexit 1',
    )

    pushed, said = landed(a_shard(), checkout, attempts=2)

    assert pushed == PushOutcome(EXIT_OK, ShardLanding.LANDED, 2), "a try that lost was not retried"
    assert said == []
    assert on_origin(origin, RECORD) is not None


def test_a_push_main_refuses_at_every_try_is_exit_3_and_lands_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Main did not move after the last try, so nobody else was landing: main refused the push."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    a_hook(origin, "exit 1")
    tip = git(origin, "rev-parse", "main")

    pushed, said = landed(a_shard(), checkout, attempts=2)

    assert pushed == PushOutcome(EXIT_PUSH_REFUSED, ShardLanding.REFUSED, 2)
    assert said == []
    assert git(origin, "rev-parse", "main") == tip
    assert on_origin(origin, RECORD) is None


def test_a_push_that_loses_to_other_writers_at_every_try_lands_nothing_and_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Main moved after the last try, so other writers are landing: a warning, not a red job."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    racer = tmp_path / "racer"
    git(tmp_path, "clone", "--quiet", str(origin), str(racer))
    for race in (1, 2):
        write(racer / f"docs/race-{race}.md", f"writer {race}\n")
        git(racer, "add", f"docs/race-{race}.md")
        git(racer, "commit", "--quiet", "-m", f"writer {race} landed")
        git(racer, "push", "--quiet", "origin", f"HEAD:refs/race/{race}")
    a_hook(origin, MOVE_MAIN_THEN_REFUSE)

    pushed, said = landed(a_shard(), checkout, attempts=2)

    assert pushed == PushOutcome(EXIT_OK, ShardLanding.LOST, 2)
    assert said == []
    assert git(origin, "rev-parse", "main") == git(origin, "rev-parse", "refs/race/2")
    assert on_origin(origin, RECORD) is None


def test_a_shard_whose_path_main_changed_after_its_commit_lands_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A re-run checks out its run's old commit, and main's newer file must survive it.

    The shard's other paths, which main left alone, do not land either, and nor
    does its record: the next wake does the whole of the work again.
    """
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / KEPT, "newer, on main\n")
    git(mover, "add", KEPT)
    git(mover, "commit", "--quiet", "-m", "main changed a file the shard also writes")
    git(mover, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    tip = git(origin, "rev-parse", "main")
    write(checkout / KEPT, "older, from the shard\n")
    (checkout / AGED).unlink()

    pushed, said = landed(a_shard(written={KEPT}, deleted={AGED}), checkout)

    assert pushed == PushOutcome(EXIT_OK, ShardLanding.STALE, 1, (KEPT,))
    assert said == []
    assert git(origin, "rev-parse", "main") == tip, "a stale shard landed a commit"
    assert on_origin(origin, KEPT) == "newer, on main\n"
    assert on_origin(origin, AGED) == "aged\n"
    assert on_origin(origin, RECORD) is None


def test_every_group_of_names_is_compared_and_the_warning_counts_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The names go to git in groups below Windows' process limit, and every group is read.

    Two hundred long names fill more than one group. Main changes the first of
    them, which sorts into the first group, and `KEPT`, which sorts into the last.
    """
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    many = sorted(f"state/old/2026-01-01-{'x' * 60}-{n:03}.txt" for n in range(200))
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / many[0], "made on main\n")
    write(mover / KEPT, "newer, on main\n")
    git(mover, "add", many[0], KEPT)
    git(mover, "commit", "--quiet", "-m", "main changed two paths the shard also changes")
    git(mover, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    write(checkout / KEPT, "older, from the shard\n")

    pushed, said = landed(a_shard(written={KEPT}, deleted=set(many)), checkout)

    assert pushed == PushOutcome(EXIT_OK, ShardLanding.STALE, 1, (many[0], KEPT))
    assert said == []
    assert on_origin(origin, RECORD) is None


def test_one_record_with_two_identities_is_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    assert landed(a_shard(), checkout)[0].exit_code == EXIT_OK
    write(checkout / RECORD, '{"task": "somebody else"}\n')

    pushed, said = landed(a_shard(), checkout)

    assert pushed == PushOutcome(EXIT_INTEGRITY)
    assert any("two runs claimed one record" in line for line in said)
    assert on_origin(origin, RECORD) == '{"task": "old"}\n'


def test_a_folder_named_as_a_write_is_refused_before_anything_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder handed over as a write stands for every file inside it, which nobody declared."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    write(checkout / "state/newdir/x.txt", "x\n")

    pushed, said = landed(a_shard(written={"state/newdir"}), checkout)

    assert pushed == PushOutcome(EXIT_INTEGRITY)
    assert said == [
        "shard 0: state/newdir is a folder, and a shard writes and deletes files one at a time"
    ]
    assert on_origin(origin, RECORD) is None


def test_a_write_that_did_not_stage_is_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file git ignores cannot be added, so the shard would push without it."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    write(checkout / "state/old/note.skip", "ignored\n")

    pushed, said = landed(a_shard(written={"state/old/note.skip"}), checkout)

    assert pushed == PushOutcome(EXIT_INTEGRITY)
    assert any("state/old/note.skip was written and did not stage" in line for line in said)
    assert on_origin(origin, RECORD) is None


def test_a_write_already_on_main_counts_as_landed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same bytes as main stage nothing, and that is a write somebody already finished."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)

    pushed, _ = landed(a_shard(written={KEPT}), checkout)

    assert pushed == PushOutcome(EXIT_OK, ShardLanding.LANDED, 1)
    assert git(origin, "show", "--name-only", "--format=", "main").split() == [RECORD]


def test_a_deletion_already_gone_from_main_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)

    pushed, _ = landed(a_shard(deleted={"state/old/never-there.txt"}), checkout)

    assert pushed == PushOutcome(EXIT_OK, ShardLanding.LANDED, 1)
    assert on_origin(origin, RECORD) is not None


def test_a_deletion_that_staged_nothing_while_main_holds_it_is_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder removed from the checkout still stages nothing: git will not remove it whole."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    shutil.rmtree(checkout / "state/dir")

    pushed, said = landed(a_shard(deleted={"state/dir"}), checkout)

    assert pushed == PushOutcome(EXIT_INTEGRITY)
    assert any("state/dir was deleted, did not stage" in line for line in said)
    assert on_origin(origin, "state/dir/a.txt") == "a\n"


def test_a_folder_named_for_deletion_is_refused_before_anything_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, checkout = a_checkout(tmp_path, monkeypatch)

    pushed, said = landed(a_shard(deleted={"state/dir"}), checkout)

    assert pushed == PushOutcome(EXIT_INTEGRITY)
    assert said == [
        "shard 0: state/dir is a folder, and a shard writes and deletes files one at a time"
    ]
    assert git(checkout, "diff", "--cached", "--name-only") == ""


def test_a_shard_reports_the_worst_code_it_earned() -> None:
    assert worst() == EXIT_OK
    assert worst(EXIT_OK, EXIT_TASK_FAILED) == EXIT_TASK_FAILED
    assert worst(EXIT_TASK_FAILED, EXIT_PUSH_REFUSED) == EXIT_PUSH_REFUSED
    assert worst(EXIT_PUSH_REFUSED, EXIT_INTEGRITY, EXIT_OK) == EXIT_INTEGRITY


def test_a_folder_that_is_not_a_checkout_has_no_commit_to_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record's envelope names a commit, so a shard with none to name runs nothing."""
    quiet_git(tmp_path, monkeypatch)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    loose = tmp_path / "loose"
    loose.mkdir()

    assert gardener_publish.Checkout(loose).head() is None


def test_the_commit_listing_names_only_the_requested_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read from the commit, so a folder the checkout lacks is still named.

    An owned folder with a trailing slash would list its children rather than
    itself, and the folder would read as absent - the slash is stripped. A child
    under `state/` that is not requested is not discovered.
    """
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(
        tmp_path,
        {
            "state/traces/2026/09/01/0001-0.jsonl": "a\n",
            "state/raw/visual-prunes/2026/09/01/x.csv": "b\n",
            "state/a-trial-run/2026-05-01.txt": "c\n",
            "frontend/public/digest/2026/09/01/digest.json": "{}\n",
        },
    )
    shutil.rmtree(checkout / "state" / "traces")

    listed = gardener_publish.Checkout(checkout).committed_folders(
        [
            "state/traces/",
            "state/a-folder-nothing-committed",
            "state/raw/visual-prunes",
            "frontend/public/digest",
        ]
    )

    assert listed == {
        "state/traces",
        "state/raw/visual-prunes",
        "frontend/public/digest",
    }


def test_a_period_a_step_names_as_the_shard_runs_is_listed_from_the_same_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """October was not in the listing the shard read; a step names it, and it is listed then.

    The clone never downloaded October's file, so its size is GitHub's, and the
    checkout widens for the folder only once the step has named it.
    """
    quiet_git(tmp_path, monkeypatch)
    september, october = "state/raw/x/2026/09/01/a.csv", "state/raw/x/2026/10/01/b.csv"
    origin, _ = an_origin(tmp_path, {september: "a\n", october: "bb\n"})
    shard = a_partial_clone(tmp_path, origin, "config")
    blobs = OriginBlobs(origin)
    listing = gardener_publish.read_the_listing(
        gardener_publish.Checkout(shard), shard, ["state/raw/x"], ["state/raw/x/2026/09"], blobs
    )
    assert dict(listing.sizes) == {september: 2}

    named = listing.name(["state/raw/x/2026/10"])
    named.fetch(["state/raw/x/2026/10"])

    assert named.size_of(october) == 3
    assert len(blobs.asked) == 2, "each file the clone lacked was sized by its blob, once"
    assert (shard / october).read_text(encoding="ascii") == "bb\n"
    assert listing.listed() == {september, october}


def test_a_shard_names_its_record_among_its_writes_and_never_both_writes_and_deletes() -> None:
    with pytest.raises(ValidationError, match="one of the files it writes"):
        Shard(
            index=0,
            task_names=("old",),
            record_path=RECORD,
            written_paths=frozenset(),
            deleted_paths=frozenset(),
            owned_prefixes=frozenset({"state/raw/gardener"}),
            message=MESSAGE,
        )
    with pytest.raises(ValidationError, match="both written and deleted"):
        a_shard(written={KEPT}, deleted={KEPT})
