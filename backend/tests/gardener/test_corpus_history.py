"""Does the corpus squash collapse exactly the old history, keep the rest whole, and push it safely?

Every case builds a real repository - a bare origin and the full clone the
history job takes of it - with commits whose author and committer dates are
set, then runs `backend/utilities/corpus_history.py` in it the way the job does.
Nothing here touches this repository or the network.

The dates are in the first half of 2026, so the one commit this program makes
with today's clock - the record of the run - is always younger than any cut a
case asks for, whatever day the suite runs.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh.contracts.corpus import CorpusMeta
from utilities import commit_and_push, corpus_history

from ._garden import SEED_IDENTITY, a_config, quiet_git, write

pytestmark = pytest.mark.slow

#: The one identity the repository commits as, read from the commit program so a
#: squash that drifted to another name is caught on the commits it made.
THE_REPOSITORY: Final = f"{commit_and_push.COMMITTER_NAME} <{commit_and_push.COMMITTER_EMAIL}>"

#: The wake every case runs at, and the cut its 60-day window gives: 00:00 UTC on 2026-04-16.
TODAY: Final = "2026-06-15"
AT_THE_CUT: Final = "2026-04-16T00:00:00Z"
JUST_AFTER_THE_CUT: Final = "2026-04-16T00:00:01Z"


def a_declaration(**changes: Any) -> dict[str, Any]:
    """The squash's declaration, keeping 60 days, live, with some keys changed."""
    return {
        "dry_run": False,
        "every_days": 30,
        "kind": "history",
        "lifecycle_status": "active",
        "max_deletes_per_run": None,
        "owns": ["corpus"],
        "window": {"unit": "days", "value": 60},
    } | changes


def _epoch(instant: str) -> str:
    """An instant in git's own date format: seconds since the epoch, and UTC."""
    return f"{int(datetime.fromisoformat(instant).timestamp())} +0000"


def dated_git(repo: Path, instant: str, *args: str) -> str:
    """One git command as the seed's author, authored and committed at `instant`."""
    done = subprocess.run(
        ["git", *SEED_IDENTITY, *args],
        cwd=repo,
        env=os.environ | {"GIT_AUTHOR_DATE": _epoch(instant), "GIT_COMMITTER_DATE": _epoch(instant)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"git {' '.join(args)} failed: {done.stderr}"
    return done.stdout


def git(repo: Path, *args: str) -> str:
    return dated_git(repo, "2026-01-01T00:00:00Z", *args)


def commit(repo: Path, instant: str, subject: str, files: dict[str, str]) -> str:
    """One commit of these files, authored at `instant`. Returns its sha."""
    for relative, text in files.items():
        write(repo / relative, text)
    dated_git(repo, instant, "add", "--all")
    dated_git(repo, instant, "commit", "--quiet", "-m", subject)
    return git(repo, "rev-parse", "HEAD").strip()


class History:
    """A bare origin, a working clone that wrote its commits, and the job's own clone."""

    def __init__(self, root: Path, *, declared: dict[str, Any]) -> None:
        self.root = root
        self.origin = root / "origin.git"
        self.author = root / "author"
        git(root, "init", "--quiet", "--bare", "-b", "main", str(self.origin))
        git(root, "clone", "--quiet", str(self.origin), str(self.author))
        declaration = write(root / "declared" / "corpus-squash.json", json.dumps(declared))
        a_config(self.author, declaration)
        write(self.author / "corpus" / "corpus.meta.json", CorpusMeta(version=CorpusMeta.schema_version()).to_json())
        write(self.author / "corpus" / "corpus.jsonl", "")
        self.shas: dict[str, str] = {}

    def add(self, instant: str, subject: str, files: dict[str, str] | None = None) -> str:
        name = subject.replace(" ", "-")
        self.shas[subject] = commit(self.author, instant, subject, files or {f"docs/{name}.md": f"{subject}\n"})
        return self.shas[subject]

    def publish(self) -> Path:
        """Push what the author wrote, and take the full clone the history job takes."""
        git(self.author, "push", "--quiet", "origin", "HEAD:refs/heads/main")
        return self.clone("job")

    def clone(self, name: str) -> Path:
        checkout = self.root / name
        git(self.root, "clone", "--quiet", str(self.origin), str(checkout))
        return checkout

    def on_origin(self, *args: str) -> str:
        return git(self.origin, *args)

    def chain(self) -> list[str]:
        """Origin's `main` along first parents, oldest first, as `sha subject`."""
        return self.on_origin("log", "--first-parent", "--reverse", "--format=%H %s", "main").splitlines()


def squash(checkout: Path, today: str = TODAY) -> int:
    return corpus_history.main(
        ["--today", today, "--run-id", f"{today}-1", "--attempt", "1", "--repo-root", str(checkout)]
    )


def tree(repo: Path, commitish: str) -> str:
    return git(repo, "rev-parse", f"{commitish}^{{tree}}").strip()


def last_run_on_origin(history: History) -> str | None:
    meta = CorpusMeta.from_json(history.on_origin("show", "main:corpus/corpus.meta.json"))
    return meta.last_run


@pytest.fixture
def history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> History:
    """Six commits either side of the cut, the root a month before it."""
    quiet_git(tmp_path, monkeypatch)
    built = History(tmp_path, declared=a_declaration())
    built.add("2026-03-01T09:00:00Z", "the root")
    built.add("2026-03-10T09:00:00Z", "an old change")
    built.add(AT_THE_CUT, "a change at the cut")
    built.add(JUST_AFTER_THE_CUT, "a change just after the cut")
    built.add("2026-05-01T09:00:00Z", "a recent change")
    built.add("2026-06-01T09:00:00Z", "a harvest", {"corpus/corpus.jsonl": '{"row": 1}\n'})
    return built


def test_the_squash_collapses_the_commits_at_or_before_the_cut_and_keeps_every_later_one(
    history: History, capsys: pytest.CaptureFixture[str]
) -> None:
    """The oracle: one new root holding the boundary's tree, then every later commit, trees intact."""
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()
    boundary = history.shas["a change at the cut"]

    assert squash(checkout) == 0

    said = capsys.readouterr().out
    assert f"boundary 2026-04-16 resolves to {boundary}" in said
    assert "3 commits collapsed into" in said
    chain = [line.split(" ", 1) for line in history.chain()]
    assert [subject for _, subject in chain] == [
        "corpus: squash history older than 60 days",
        "a change just after the cut",
        "a recent change",
        "a harvest",
        f"corpus: pruned {TODAY}",
    ]
    root, after, recent, harvest, recorded = (sha for sha, _ in chain)
    assert history.on_origin("rev-list", "--parents", "-n", "1", root).split() == [root]
    assert tree(history.origin, root) == tree(checkout, boundary)
    for replayed, subject in ((after, "a change just after the cut"), (recent, "a recent change")):
        original = history.shas[subject]
        assert tree(history.origin, replayed) == tree(checkout, original)
        assert history.on_origin("log", "-1", "--format=%an %aI", replayed) == git(
            checkout, "log", "-1", "--format=%an %aI", original
        )
    assert tree(history.origin, harvest) == tree(checkout, tip), "the tip's tree moved"
    for gone in ("the root", "an old change", "a change at the cut"):
        assert history.shas[gone] not in history.on_origin("rev-list", "--all")
    authored = history.on_origin("log", "-1", "--format=%aI", root).strip()
    assert datetime.fromisoformat(authored) == datetime.fromisoformat(AT_THE_CUT)
    for made in (root, recorded):
        assert history.on_origin("log", "-1", "--format=%an <%ae>|%cn <%ce>", made).strip() == (
            f"{THE_REPOSITORY}|{THE_REPOSITORY}"
        )
    assert history.on_origin("log", "-1", "--format=%B", root).strip() == (
        "corpus: squash history older than 60 days"
    )
    changed = history.on_origin("diff", "--name-only", harvest, recorded).split()
    assert changed == ["corpus/corpus.meta.json"]
    assert last_run_on_origin(history) == TODAY


def test_a_second_squash_a_cadence_later_still_finds_history_to_collapse(
    history: History, capsys: pytest.CaptureFixture[str]
) -> None:
    """The replay restamps every committer date, so a cut read off those would find nothing."""
    assert squash(history.publish()) == 0
    capsys.readouterr()
    later = history.clone("next-job")
    commit(later, "2026-06-20T09:00:00Z", "a change after the first squash", {"docs/later.md": "x\n"})
    git(later, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    job = history.clone("second-job")

    assert squash(job, today="2026-07-15") == 0

    assert "3 commits collapsed into" in capsys.readouterr().out
    assert [line.split(" ", 1)[1] for line in history.chain()] == [
        "corpus: squash history older than 60 days",
        "a harvest",
        f"corpus: pruned {TODAY}",
        "a change after the first squash",
        "corpus: pruned 2026-07-15",
    ]


def test_an_old_commit_near_the_tip_cannot_pull_recent_work_into_the_squash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commit authored long before it landed stops nothing newer from surviving."""
    quiet_git(tmp_path, monkeypatch)
    history = History(tmp_path, declared=a_declaration())
    history.add("2026-03-01T09:00:00Z", "the root")
    history.add("2026-03-10T09:00:00Z", "an old change")
    history.add("2026-05-01T09:00:00Z", "a recent change")
    history.add("2026-03-05T09:00:00Z", "an old change that landed late")
    history.add("2026-06-01T09:00:00Z", "the newest change")

    assert squash(history.publish()) == 0

    assert [line.split(" ", 1)[1] for line in history.chain()] == [
        "corpus: squash history older than 60 days",
        "a recent change",
        "an old change that landed late",
        "the newest change",
        f"corpus: pruned {TODAY}",
    ]


def test_a_merge_above_the_boundary_is_replayed_with_the_tip_tree_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    history = History(tmp_path, declared=a_declaration())
    history.add("2026-03-01T09:00:00Z", "the root")
    history.add("2026-03-10T09:00:00Z", "an old change")
    git(history.author, "checkout", "--quiet", "-b", "side")
    history.add("2026-05-02T09:00:00Z", "a side change")
    git(history.author, "checkout", "--quiet", "main")
    history.add("2026-05-01T09:00:00Z", "a main change")
    dated_git(history.author, "2026-05-03T09:00:00Z", "merge", "--quiet", "--no-ff", "-m", "a merge", "side")
    history.add("2026-06-01T09:00:00Z", "the newest change")
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()

    assert squash(checkout) == 0

    newest = history.chain()[-2].split(" ", 1)[0]
    assert tree(history.origin, newest) == tree(checkout, tip)


def test_a_merge_that_carried_its_own_change_is_refused_before_anything_is_pushed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A replay drops a merge commit, so a change only the merge made would vanish from the tip."""
    quiet_git(tmp_path, monkeypatch)
    history = History(tmp_path, declared=a_declaration())
    history.add("2026-03-01T09:00:00Z", "the root")
    history.add("2026-03-10T09:00:00Z", "an old change")
    git(history.author, "checkout", "--quiet", "-b", "side")
    history.add("2026-05-02T09:00:00Z", "a side change")
    git(history.author, "checkout", "--quiet", "main")
    history.add("2026-05-01T09:00:00Z", "a main change")
    dated_git(history.author, "2026-05-03T09:00:00Z", "merge", "--quiet", "--no-ff", "--no-commit", "side")
    write(history.author / "docs" / "only-the-merge.md", "made by the merge\n")
    dated_git(history.author, "2026-05-03T09:00:00Z", "add", "--all")
    dated_git(history.author, "2026-05-03T09:00:00Z", "commit", "--quiet", "-m", "a merge with a change")
    checkout = history.publish()
    before = history.on_origin("rev-parse", "main").strip()

    assert squash(checkout) == corpus_history.EXIT_CANNOT_REWRITE

    assert "must be thrown away" in capsys.readouterr().err
    assert history.on_origin("rev-parse", "main").strip() == before


def test_a_replay_that_conflicts_is_aborted_and_nothing_is_pushed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two sides changed one line and a person merged them by hand; a replay cannot redo that."""
    quiet_git(tmp_path, monkeypatch)
    history = History(tmp_path, declared=a_declaration())
    history.add("2026-03-01T09:00:00Z", "the root", {"docs/line.md": "first\n"})
    history.add("2026-03-10T09:00:00Z", "an old change")
    git(history.author, "checkout", "--quiet", "-b", "side")
    history.add("2026-05-02T09:00:00Z", "the side's line", {"docs/line.md": "side\n"})
    git(history.author, "checkout", "--quiet", "main")
    history.add("2026-05-01T09:00:00Z", "main's line", {"docs/line.md": "main\n"})
    conflicted = subprocess.run(
        ["git", *SEED_IDENTITY, "merge", "--quiet", "side"],
        cwd=history.author,
        env=os.environ | {"GIT_AUTHOR_DATE": _epoch("2026-05-03T09:00:00Z")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert conflicted.returncode != 0 and (history.author / ".git" / "MERGE_HEAD").is_file(), (
        f"the two sides had to stop the merge on a conflict: {conflicted.stderr}"
    )
    write(history.author / "docs" / "line.md", "both\n")
    dated_git(history.author, "2026-05-03T09:00:00Z", "add", "--all")
    dated_git(history.author, "2026-05-03T09:00:00Z", "commit", "--quiet", "--no-edit")
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()

    assert squash(checkout) == corpus_history.EXIT_CANNOT_REWRITE

    assert "replaying the commits after" in capsys.readouterr().err
    assert git(checkout, "rev-parse", "HEAD").strip() == tip, "the replay was not aborted"
    assert history.on_origin("rev-parse", "main").strip() == tip


def test_a_wake_with_nothing_old_enough_records_the_run_and_pushes_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Recorded anyway, so the next wake is not due again - and a second run that day adds nothing."""
    quiet_git(tmp_path, monkeypatch)
    history = History(tmp_path, declared=a_declaration())
    history.add("2026-05-01T09:00:00Z", "the root")
    history.add("2026-06-01T09:00:00Z", "a recent change")
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()

    assert squash(checkout) == 0

    assert "no commit is older than 2026-04-16 - nothing to squash" in capsys.readouterr().out
    assert history.on_origin("rev-parse", "main~1").strip() == tip, "history was rewritten"
    assert last_run_on_origin(history) == TODAY
    recorded = history.on_origin("rev-parse", "main").strip()

    assert squash(history.clone("same-day-job")) == 0

    assert "the stamp did not move" in capsys.readouterr().out
    assert history.on_origin("rev-parse", "main").strip() == recorded


def test_a_tip_that_moved_while_it_ran_is_refused_and_the_run_is_not_recorded(
    history: History, capsys: pytest.CaptureFixture[str]
) -> None:
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()
    racer = history.clone("racer")
    raced = commit(racer, "2026-06-15T09:00:00Z", "a run pushed meanwhile", {"docs/raced.md": "x\n"})
    git(racer, "push", "--quiet", "origin", "HEAD:refs/heads/main")

    assert squash(checkout) == corpus_history.EXIT_TIP_MOVED

    err = capsys.readouterr().err
    assert f"  this job checked out {tip}" in err and f"  origin/main is now {raced}" in err
    assert history.on_origin("rev-parse", "main").strip() == raced
    assert last_run_on_origin(history) is None


def test_a_dry_run_says_what_it_would_collapse_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    quiet_git(tmp_path, monkeypatch)
    history = History(tmp_path, declared=a_declaration(dry_run=True))
    history.add("2026-03-01T09:00:00Z", "the root")
    history.add("2026-03-10T09:00:00Z", "an old change")
    history.add("2026-05-01T09:00:00Z", "a recent change")
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()
    meta = (checkout / "corpus" / "corpus.meta.json").read_bytes()

    assert squash(checkout) == 0

    assert "dry run: a squash would collapse 2 commits" in capsys.readouterr().out
    assert git(checkout, "rev-parse", "HEAD").strip() == tip
    assert git(checkout, "status", "--porcelain").strip() == ""
    assert (checkout / "corpus" / "corpus.meta.json").read_bytes() == meta
    assert history.on_origin("rev-parse", "main").strip() == tip


@pytest.mark.parametrize("status", ["paused", "retired"])
def test_a_squash_that_is_not_active_rewrites_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    quiet_git(tmp_path, monkeypatch)
    history = History(tmp_path, declared=a_declaration(lifecycle_status=status))
    history.add("2026-03-01T09:00:00Z", "the root")
    history.add("2026-03-10T09:00:00Z", "an old change")
    history.add("2026-05-01T09:00:00Z", "a recent change")
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()

    assert squash(checkout) == corpus_history.EXIT_CANNOT_REWRITE

    assert git(checkout, "rev-parse", "HEAD").strip() == tip
    assert history.on_origin("rev-parse", "main").strip() == tip


@pytest.mark.parametrize("state", ["dirty", "detached", "another-branch"])
def test_a_checkout_it_cannot_rewrite_is_refused_before_anything_moves(
    history: History, capsys: pytest.CaptureFixture[str], state: str
) -> None:
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()
    if state == "dirty":
        write(checkout / "docs" / "the-root.md", "an edit nobody committed\n")
    elif state == "detached":
        git(checkout, "checkout", "--quiet", "--detach")
    else:
        git(checkout, "checkout", "--quiet", "-b", "elsewhere")

    assert squash(checkout) == corpus_history.EXIT_CANNOT_REWRITE

    assert "nothing was rewritten" in capsys.readouterr().err
    assert git(checkout, "rev-parse", "HEAD").strip() == tip
    assert history.on_origin("rev-parse", "main").strip() == tip


def test_a_boundary_that_is_not_a_commit_is_refused(history: History) -> None:
    checkout = history.publish()
    with pytest.raises(corpus_history.CannotRewriteError, match="not a commit"):
        corpus_history.squash_below(checkout, boundary="0" * 40, message="unused")


def test_it_commits_as_the_one_identity_the_commit_program_sets() -> None:
    assert (corpus_history.COMMITTER_NAME, corpus_history.COMMITTER_EMAIL) == (
        commit_and_push.COMMITTER_NAME,
        commit_and_push.COMMITTER_EMAIL,
    )
