"""Does a shard land exactly what it wrote and deleted, once, however the push race goes?

Every test pushes to a real bare repository standing in for origin, from a real
clone, with no network. A race is staged the way it happens: another clone
pushes first, or the origin refuses a push through its own hook. The idempotence
oracle is that running the loop twice leaves the tree running it once left, and
the moved-tip oracle is that the mover's change and this shard's both survive.

The loop is `backend/utilities/gardener_publish.py`, because nothing under
`backend/idhazh/` may start a process.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from idhazh.gardener.outcome import (
    EXIT_INTEGRITY,
    EXIT_OK,
    EXIT_PUSH_KEPT_LOSING,
    EXIT_TASK_FAILED,
    Shard,
    worst,
)
from utilities import commit_and_push, gardener_publish

from ._garden import a_hook, an_origin, commits_on, git, on_origin, quiet_git, write

RECORD = "state/raw/gardener/2026/09/27/record.json"
AGED = "state/old/2026-01-01.txt"
KEPT = "state/old/2026-09-26.txt"
MESSAGE = "gardener: old on 2026-09-27"
SEEDED = {AGED: "aged\n", KEPT: "kept\n", "state/dir/a.txt": "a\n", ".gitignore": "*.skip\n"}


def a_shard(*, written: set[str] | None = None, deleted: set[str] | None = None) -> Shard:
    return Shard(
        index=0,
        task_names=("old",),
        record_path=RECORD,
        written_paths=frozenset({RECORD, *(written or set())}),
        deleted_paths=frozenset(deleted or set()),
        message=MESSAGE,
    )


def a_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """An origin seeded with a small tree, and a clone whose shard wrote its record."""
    quiet_git(tmp_path, monkeypatch)
    origin, checkout = an_origin(tmp_path, SEEDED)
    write(checkout / RECORD, '{"task": "old"}\n')
    return origin, checkout


def landed(shard: Shard, checkout: Path, *, attempts: int = 6) -> tuple[int, list[str]]:
    said: list[str] = []
    code = gardener_publish.publish(shard, attempts=attempts, repo=checkout, say=said.append)
    return code, said


def test_a_shard_lands_its_writes_and_deletions_in_one_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    (checkout / AGED).unlink()

    code, _ = landed(a_shard(deleted={AGED}), checkout)

    assert code == EXIT_OK
    assert on_origin(origin, RECORD) == '{"task": "old"}\n'
    assert on_origin(origin, AGED) is None
    assert on_origin(origin, KEPT) == "kept\n", "a file the shard did not delete went"
    identity = f"{commit_and_push.COMMITTER_NAME} <{commit_and_push.COMMITTER_EMAIL}>"
    assert commits_on(origin)[0] == f"{identity}: {MESSAGE}"
    assert (gardener_publish.COMMITTER_NAME, gardener_publish.COMMITTER_EMAIL) == (
        commit_and_push.COMMITTER_NAME,
        commit_and_push.COMMITTER_EMAIL,
    )


def test_running_it_twice_leaves_the_tree_running_it_once_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    (checkout / AGED).unlink()
    shard = a_shard(deleted={AGED})

    assert landed(shard, checkout)[0] == EXIT_OK
    once = git(origin, "rev-parse", "main^{tree}"), len(commits_on(origin))
    code, said = landed(shard, checkout)

    assert code == EXIT_OK
    assert (git(origin, "rev-parse", "main^{tree}"), len(commits_on(origin))) == once
    assert any("already on main" in line for line in said)


def test_a_tip_that_moved_keeps_the_movers_change_and_this_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / "docs/moved.md", "the other shard\n")
    git(mover, "add", "docs/moved.md")
    git(mover, "commit", "--quiet", "-m", "another shard landed first")
    git(mover, "push", "--quiet", "origin", "HEAD:refs/heads/main")

    code, _ = landed(a_shard(), checkout)

    assert code == EXIT_OK
    assert on_origin(origin, "docs/moved.md") == "the other shard\n"
    assert on_origin(origin, RECORD) is not None
    assert [line.split(": ", 1)[1] for line in commits_on(origin)[:2]] == [
        MESSAGE,
        "another shard landed first",
    ]


def test_a_push_that_lost_is_tried_again_on_the_new_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    a_hook(origin, 'if [ -f "$GIT_DIR/lost-once" ]; then exit 0; fi\ntouch "$GIT_DIR/lost-once"\nexit 1')

    code, said = landed(a_shard(), checkout, attempts=2)

    assert code == EXIT_OK
    assert "shard 0: try 1 of 2 lost the push" in said
    assert on_origin(origin, RECORD) is not None


def test_a_push_that_keeps_losing_is_exit_3_and_lands_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    a_hook(origin, "exit 1")

    code, said = landed(a_shard(), checkout, attempts=2)

    assert code == EXIT_PUSH_KEPT_LOSING
    assert on_origin(origin, RECORD) is None
    assert sum("lost the push" in line for line in said) == 2


def test_one_record_with_two_identities_is_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    assert landed(a_shard(), checkout)[0] == EXIT_OK
    write(checkout / RECORD, '{"task": "somebody else"}\n')

    code, said = landed(a_shard(), checkout)

    assert code == EXIT_INTEGRITY
    assert any("two runs claimed one record" in line for line in said)
    assert on_origin(origin, RECORD) == '{"task": "old"}\n'


def test_a_folder_named_as_a_write_is_refused_before_anything_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder handed over as a write stands for every file inside it, which nobody declared."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    write(checkout / "state/newdir/x.txt", "x\n")

    code, said = landed(a_shard(written={"state/newdir"}), checkout)

    assert code == EXIT_INTEGRITY
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

    code, said = landed(a_shard(written={"state/old/note.skip"}), checkout)

    assert code == EXIT_INTEGRITY
    assert any("state/old/note.skip was written and did not stage" in line for line in said)
    assert on_origin(origin, RECORD) is None


def test_a_write_already_on_main_counts_as_landed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same bytes as main stage nothing, and that is a write somebody already finished."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)

    code, _ = landed(a_shard(written={KEPT}), checkout)

    assert code == EXIT_OK
    assert git(origin, "show", "--name-only", "--format=", "main").split() == [RECORD]


def test_a_deletion_already_gone_from_main_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = a_checkout(tmp_path, monkeypatch)

    code, _ = landed(a_shard(deleted={"state/old/never-there.txt"}), checkout)

    assert code == EXIT_OK
    assert on_origin(origin, RECORD) is not None


def test_a_deletion_that_staged_nothing_while_main_holds_it_is_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder removed from the checkout still stages nothing: git will not remove it whole."""
    origin, checkout = a_checkout(tmp_path, monkeypatch)
    shutil.rmtree(checkout / "state/dir")

    code, said = landed(a_shard(deleted={"state/dir"}), checkout)

    assert code == EXIT_INTEGRITY
    assert any("state/dir was deleted, did not stage" in line for line in said)
    assert on_origin(origin, "state/dir/a.txt") == "a\n"


def test_a_folder_named_for_deletion_is_refused_before_anything_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, checkout = a_checkout(tmp_path, monkeypatch)

    code, said = landed(a_shard(deleted={"state/dir"}), checkout)

    assert code == EXIT_INTEGRITY
    assert said == [
        "shard 0: state/dir is a folder, and a shard writes and deletes files one at a time"
    ]
    assert git(checkout, "diff", "--cached", "--name-only") == ""


def test_a_shard_reports_the_worst_code_it_earned() -> None:
    assert worst() == EXIT_OK
    assert worst(EXIT_OK, EXIT_TASK_FAILED) == EXIT_TASK_FAILED
    assert worst(EXIT_TASK_FAILED, EXIT_PUSH_KEPT_LOSING) == EXIT_PUSH_KEPT_LOSING
    assert worst(EXIT_PUSH_KEPT_LOSING, EXIT_INTEGRITY, EXIT_OK) == EXIT_INTEGRITY


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
        ["state/traces/", "state/summary-quality-evals-index", "state/raw/visual-prunes", "frontend/public/digest"]
    )

    assert listed == {
        "state/traces",
        "state/raw/visual-prunes",
        "frontend/public/digest",
    }


def test_a_shard_names_its_record_among_its_writes_and_never_both_writes_and_deletes() -> None:
    with pytest.raises(ValidationError, match="one of the files it writes"):
        Shard(
            index=0,
            task_names=("old",),
            record_path=RECORD,
            written_paths=frozenset(),
            deleted_paths=frozenset(),
            message=MESSAGE,
        )
    with pytest.raises(ValidationError, match="both written and deleted"):
        a_shard(written={KEPT}, deleted={KEPT})
