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

#: The one identity the repository commits as, read from the commit program so a
#: squash that drifted to another name is caught on the commits it made.
THE_REPOSITORY: Final = f"{commit_and_push.COMMITTER_NAME} <{commit_and_push.COMMITTER_EMAIL}>"

#: The wake every case runs at, and the cut its 60-day window gives: 00:00 UTC on 2026-04-16.
TODAY: Final = "2026-06-15"
AT_THE_CUT: Final = "2026-04-16T00:00:00Z"
JUST_AFTER_THE_CUT: Final = "2026-04-16T00:00:01Z"

#: What a fetched page might say, planted in a stamp the contract refuses; and
#: the part of it no line the squash prints may hold.
FETCHED: Final = "Breaking: click https://example.invalid/now"
PLANTED: Final = "example.invalid"


def a_declaration(**changes: Any) -> dict[str, Any]:
    """The squash's declaration, keeping 60 days, live, with some keys changed.

    Three pushes, as committed, and no wait between them, so a case that loses
    a race costs git's time and never a sleep.
    """
    return {
        "dry_run": False,
        "every_days": 30,
        "kind": "history",
        "lifecycle_status": "active",
        "max_deletes_per_run": None,
        "owns": ["corpus"],
        "push_attempts": 3,
        "push_retry_delay_seconds": 0,
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
        """A clone that reaches origin through git's transport, by a `file://` address."""
        checkout = self.root / name
        git(self.root, "clone", "--quiet", self.origin.as_uri(), str(checkout))
        return checkout

    def on_origin(self, *args: str) -> str:
        return git(self.root, "--git-dir", str(self.origin), *args)

    def tree(self, commitish: str) -> str:
        """The tree of one commit in the explicitly addressed bare origin."""
        return self.on_origin("rev-parse", f"{commitish}^{{tree}}").strip()

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


def the_six_commits(root: Path, **changes: Any) -> History:
    """Six commits either side of the cut, the root a month before it, under this declaration."""
    built = History(root, declared=a_declaration(**changes))
    built.add("2026-03-01T09:00:00Z", "the root")
    built.add("2026-03-10T09:00:00Z", "an old change")
    built.add(AT_THE_CUT, "a change at the cut")
    built.add(JUST_AFTER_THE_CUT, "a change just after the cut")
    built.add("2026-05-01T09:00:00Z", "a recent change")
    built.add("2026-06-01T09:00:00Z", "a harvest", {"corpus/corpus.jsonl": '{"row": 1}\n'})
    return built


@pytest.fixture
def history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> History:
    """Six commits either side of the cut, the root a month before it."""
    quiet_git(tmp_path, monkeypatch)
    return the_six_commits(tmp_path)


def a_racer_after_every_replay(checkout: Path, racer: Path, body: str) -> None:
    """Another run, pushing to origin from `racer` each time the job's replay finishes.

    A `post-rewrite` hook in the job's own clone. Git runs it when the replay
    after the squash finishes: after the program read its tip and before it
    pushes, which is the window a forcing push would delete a commit in and the
    one the lease exists for. `body` runs in `racer`, with the job's own git
    variables cleared so it cannot write to the job's repository.
    """
    hook = checkout / ".git" / "hooks" / "post-rewrite"
    hook.write_text(
        "#!/bin/sh\n"
        "cat >/dev/null\n"
        "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX\n"
        f'cd "{racer.as_posix()}" || exit 1\n'
        f"{body}\n",
        encoding="ascii",
        newline="\n",
    )
    hook.chmod(0o755)


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
    assert history.tree(root) == tree(checkout, boundary)
    for replayed, subject in ((after, "a change just after the cut"), (recent, "a recent change")):
        original = history.shas[subject]
        assert history.tree(replayed) == tree(checkout, original)
        assert history.on_origin("log", "-1", "--format=%an %aI", replayed) == git(
            checkout, "log", "-1", "--format=%an %aI", original
        )
    assert history.tree(harvest) == tree(checkout, tip), "the tip's tree moved"
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
    assert history.tree(newest) == tree(checkout, tip)


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


@pytest.mark.parametrize("bare_repository_policy", ("explicit", "all"))
def test_a_wake_with_nothing_old_enough_records_the_run_and_pushes_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    bare_repository_policy: str,
) -> None:
    """Recorded anyway, so the next wake is not due again - and a second run that day adds nothing."""
    quiet_git(tmp_path, monkeypatch)
    config_count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    monkeypatch.setenv("GIT_CONFIG_KEY_" + str(config_count), "safe.bareRepository")
    monkeypatch.setenv("GIT_CONFIG_VALUE_" + str(config_count), bare_repository_policy)
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(config_count + 1))
    assert git(tmp_path, "config", "--get", "safe.bareRepository").strip() == bare_repository_policy
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


def test_a_commit_that_lands_after_the_tip_was_read_is_refused_by_the_lease_and_kept_by_the_retry(
    history: History, capsys: pytest.CaptureFixture[str]
) -> None:
    """The oracle: the lease refuses the push, and a squash redone on the new tip keeps the commit.

    The other run pushes when the job's replay finishes, after the program read
    its tip and before its first push, where a forcing push would delete it. It
    changes three files, one of them the file the record writes, so the pass
    after the refusal has to record from the new tip's copy of that file.
    """
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()
    racer = history.clone("racer")
    harvested = CorpusMeta(version=CorpusMeta.schema_version(), harvested_date="2026-06-14")
    raced = commit(
        racer,
        "2026-06-14T09:00:00Z",
        "a run pushed meanwhile",
        {
            "docs/raced.md": "a run pushed meanwhile\n",
            "corpus/corpus.jsonl": '{"row": 1}\n{"row": 2}\n',
            "corpus/corpus.meta.json": harvested.to_json(),
        },
    )
    a_racer_after_every_replay(checkout, racer, "git push --quiet origin HEAD:refs/heads/main")

    assert squash(checkout) == corpus_history.EXIT_OK

    said = capsys.readouterr()
    assert said.err.count(corpus_history.MAIN_MOVED[0]) == 1, "one push was refused, and one only"
    assert f"  this job checked out {tip}" in said.err
    assert f"  origin/main is now {raced}" in said.err
    assert "waiting 0 s, then squashing again on the new tip: push 2 of 3" in said.err
    assert corpus_history.DUE_AGAIN not in said.err
    assert f"push 2 of 3 starts from {raced}" in said.out
    chain = history.chain()
    assert [line.split(" ", 1)[1] for line in chain] == [
        "corpus: squash history older than 60 days",
        "a change just after the cut",
        "a recent change",
        "a harvest",
        "a run pushed meanwhile",
        f"corpus: pruned {TODAY}",
    ]
    replayed, recorded = (line.split(" ", 1)[0] for line in chain[-2:])
    assert replayed != raced, "the commit is replayed inside the rewritten history"
    assert history.tree(replayed) == tree(racer, raced), "a file it changed is missing"
    assert history.on_origin("diff", "--name-only", replayed, recorded).split() == [
        "corpus/corpus.meta.json"
    ]
    meta = CorpusMeta.from_json(history.on_origin("show", "main:corpus/corpus.meta.json"))
    assert (meta.harvested_date, meta.last_run) == ("2026-06-14", TODAY)


def test_a_run_whose_every_push_is_refused_leaves_main_to_the_other_writer_and_stays_due(
    history: History, capsys: pytest.CaptureFixture[str]
) -> None:
    """The oracle: after the last refused push, exit 1, nothing of this run on main, and no stamp.

    The other run pushes after every replay, so every pass finds `main` moved
    again. Three pushes and no fourth, because the declaration says three.
    """
    checkout = history.publish()
    published = git(checkout, "rev-parse", "HEAD").strip()
    racer = history.clone("racer")
    identity = " ".join(f'"{part}"' for part in SEED_IDENTITY)
    a_racer_after_every_replay(
        checkout,
        racer,
        'echo "a run pushed meanwhile" >> docs/raced.md\n'
        "git add docs/raced.md\n"
        f'git {identity} commit --quiet -m "a run pushed meanwhile"\n'
        "git push --quiet origin HEAD:refs/heads/main",
    )

    assert squash(checkout) == corpus_history.EXIT_TIP_MOVED

    err = capsys.readouterr().err
    assert err.count(corpus_history.MAIN_MOVED[0]) == 3, "three pushes in all, as declared"
    assert err.count(corpus_history.DUE_AGAIN) == 1
    assert err.splitlines()[-1] == corpus_history.DUE_AGAIN
    assert history.on_origin("rev-parse", "main").strip() == git(racer, "rev-parse", "HEAD").strip()
    assert history.on_origin("log", "--format=%s", f"{published}..main").splitlines() == [
        "a run pushed meanwhile"
    ] * 3
    assert last_run_on_origin(history) is None


def test_with_one_push_a_tip_that_moved_is_refused_as_it_always_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """One push and no second pass: the refusal, its words and its exit code are the old ones.

    The other run pushed after the job's checkout and before the program ran,
    so the lease refuses the only push there is.
    """
    quiet_git(tmp_path, monkeypatch)
    history = the_six_commits(tmp_path, push_attempts=1)
    checkout = history.publish()
    tip = git(checkout, "rev-parse", "HEAD").strip()
    racer = history.clone("racer")
    raced = commit(racer, "2026-06-15T09:00:00Z", "a run pushed meanwhile", {"docs/raced.md": "x\n"})
    git(racer, "push", "--quiet", "origin", "HEAD:refs/heads/main")

    assert squash(checkout) == corpus_history.EXIT_TIP_MOVED

    err = capsys.readouterr().err
    assert err.splitlines()[-5:] == [
        "main moved while the prune was rewriting it, so nothing was pushed",
        f"  this job checked out {tip}",
        f"  origin/main is now {raced}",
        "pushing would discard every commit between the two.",
        "the prune is unstamped, so it is due again at the next daily wake.",
    ]
    assert err.count(corpus_history.MAIN_MOVED[0]) == 1
    assert history.on_origin("rev-parse", "main").strip() == raced
    assert last_run_on_origin(history) is None


def test_a_wake_with_nothing_old_enough_that_loses_its_push_records_the_run_on_the_new_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The plain push loses the same race, and the pass after it records on top of the winner."""
    quiet_git(tmp_path, monkeypatch)
    history = History(tmp_path, declared=a_declaration())
    history.add("2026-05-01T09:00:00Z", "the root")
    history.add("2026-06-01T09:00:00Z", "a recent change")
    checkout = history.publish()
    racer = history.clone("racer")
    raced = commit(racer, "2026-06-15T09:00:00Z", "a run pushed meanwhile", {"docs/raced.md": "x\n"})
    git(racer, "push", "--quiet", "origin", "HEAD:refs/heads/main")

    assert squash(checkout) == corpus_history.EXIT_OK

    assert capsys.readouterr().err.count(corpus_history.MAIN_MOVED[0]) == 1
    assert history.on_origin("rev-parse", "main~1").strip() == raced, "history was rewritten"
    assert last_run_on_origin(history) == TODAY


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


def test_a_run_it_cannot_record_names_where_it_broke_and_never_what_the_stamp_holds(
    history: History, capsys: pytest.CaptureFixture[str]
) -> None:
    """The stamp holds a prompt digest that is not one, so recording the run fails.

    The contract's error quotes the value, which stands in for fetched text.
    The due check reads only `last_run`, so a stamp like this one reaches the squash.
    """
    stamp = json.loads(CorpusMeta(version=CorpusMeta.schema_version()).to_json())
    history.add(
        "2026-06-02T09:00:00Z",
        "a stamp the contract refuses",
        {"corpus/corpus.meta.json": json.dumps(stamp | {"prompt_digest": FETCHED})},
    )
    checkout = history.publish()
    tip = history.on_origin("rev-parse", "main").strip()

    assert squash(checkout) == corpus_history.EXIT_CANNOT_REWRITE

    err = capsys.readouterr().err
    assert PLANTED not in err, err
    said = err.splitlines()
    assert "pydantic_core._pydantic_core.ValidationError" in said, err
    assert any(line.startswith("  idhazh.corpus:") for line in said), err
    assert said[-1] == "nothing was pushed: the run could not be recorded"
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
