"""Real Git publication regressions, without the retired checkout/rebase engine."""

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest
from conftest import CONFIG_DIR
from gardener._garden import an_origin, git, on_origin, quiet_git, write

from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from utilities import publish_to_repo
from utilities.publication_git import Repository
from utilities.publication_request import PublicationRequest, Write
from utilities.publish_to_repo import Status, publish
from utilities.push_retry import PushRetry, load_retry

from ._harness import _reject_the_first_pushes

RETRY = PushRetry({"default": 300}, 0.001, 0.001, 1)
PATH = "state/raw/seen/2026/10/09/[item].json"


def evidence(repo: Path) -> PublicationRequest:
    source = git(repo, "rev-parse", "HEAD").strip()
    return PublicationRequest(
        WriterIdentity(
            run_id="2026-10-09-123",
            attempt=1,
            job=ServerJob.PLAN,
            shard=0,
            producer="tests.publisher",
            git_sha=source,
        ),
        "completed",
        source,
        ("state/raw/seen",),
        (),
        {
            PATH: Write(
                hashlib.sha256((repo / PATH).read_bytes()).hexdigest(),
                Repository(repo).entry(source, PATH),
                True,
            )
        },
    )


def test_the_production_backoff_grows_and_caps() -> None:
    retry = load_retry(CONFIG_DIR / "push-retry.json")
    assert [retry.backoff_seconds(n) for n in range(1, 8)] == [1, 2, 4, 8, 8, 8, 8]
    assert retry.deadline_for("work") == 120
    assert retry.deadline_for("assemble") == 300
    assert retry.deadline_for("a-new-job") == 300


@pytest.mark.parametrize(
    ("base", "ceiling", "after", "expected"),
    [
        (0.003, 0.024, 4, [0.003, 0.006, 0.012, 0.024, 0.024]),
        (0.003, 0.010, 4, [0.003, 0.006, 0.010, 0.010, 0.010]),
        (0.003, 0.024, 2, [0.003, 0.006, 0.012, 0.012, 0.012]),
    ],
)
def test_each_backoff_knob_changes_the_real_step(
    base: float, ceiling: float, after: int, expected: list[float]
) -> None:
    retry = PushRetry({"default": 300, "work": 120}, base, ceiling, after)
    assert [retry.backoff_seconds(n) for n in range(1, 6)] == pytest.approx(expected)
    assert retry.backoff_seconds(10**6) == pytest.approx(expected[-1])
    with pytest.raises(ValueError, match="failures"):
        retry.backoff_seconds(0)


@pytest.mark.parametrize(
    "key", ["deadline_seconds", "base_step_seconds", "ceiling_seconds", "ceiling_after"]
)
@pytest.mark.parametrize("invalid", [None, True, "1", 0, -1, float("inf"), float("nan")])
def test_invalid_or_missing_retry_knobs_are_refused_by_name(
    tmp_path: Path, key: str, invalid: object
) -> None:
    declared = json.loads((CONFIG_DIR / "push-retry.json").read_text(encoding="utf-8"))
    if invalid is None:
        del declared[key]
    else:
        declared[key] = invalid
    target = tmp_path / "retry.json"
    write(target, json.dumps(declared) + "\n")
    with pytest.raises(ValueError, match=key):
        load_retry(target)


@pytest.mark.parametrize("job", ["default", "work"])
@pytest.mark.parametrize("invalid", [None, True, "1", 0, -1, float("inf"), float("nan")])
def test_invalid_or_missing_job_deadlines_are_refused_by_name(
    tmp_path: Path, job: str, invalid: object
) -> None:
    declared = json.loads((CONFIG_DIR / "push-retry.json").read_text(encoding="utf-8"))
    if invalid is None and job == "default":
        del declared["deadline_seconds"][job]
    else:
        declared["deadline_seconds"][job] = invalid
    target = tmp_path / "retry.json"
    write(target, json.dumps(declared) + "\n")
    with pytest.raises(ValueError, match=f"deadline_seconds.{job}"):
        load_retry(target)


def test_fractional_deadlines_and_falling_backoff_are_checked(tmp_path: Path) -> None:
    declared = {
        "deadline_seconds": {"default": 0.05},
        "base_step_seconds": 0.003,
        "ceiling_seconds": 0.024,
        "ceiling_after": 4,
    }
    target = tmp_path / "retry.json"
    write(target, json.dumps(declared) + "\n")
    retry = load_retry(target)
    assert retry.deadline_for("plan") == 0.05
    assert retry.backoff_seconds(1) == 0.003
    declared["ceiling_seconds"] = 0.001
    write(target, json.dumps(declared) + "\n")
    with pytest.raises(ValueError, match="base_step_seconds"):
        load_retry(target)


def test_literal_paths_and_untracked_racing_noise_are_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"seed": "seed\n"})
    write(repo / PATH, "completed\n")
    write(repo / "foreign.txt", "local\n")
    before = git(repo, "rev-parse", "HEAD"), (repo / ".git" / "index").read_bytes()
    result = publish(evidence(repo), repo=repo, retry=RETRY)
    assert result.status is Status.LANDED
    assert on_origin(origin, PATH) == "completed\n"
    assert (repo / "foreign.txt").read_text() == "local\n"
    assert before == (git(repo, "rev-parse", "HEAD"), (repo / ".git" / "index").read_bytes())


def test_an_uncertain_push_that_actually_landed_is_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"seed": "seed\n"})
    write(repo / PATH, "completed\n")

    class UncertainTransport(Repository):
        def push(self, candidate: str) -> bool:
            assert super().push(candidate)
            raise RuntimeError("connection disappeared after the remote accepted the ref")

    monkeypatch.setattr(publish_to_repo, "Repository", UncertainTransport)
    result = publish(evidence(repo), repo=repo, retry=RETRY)
    assert result.status is Status.LANDED
    assert result.push_count == 1
    assert on_origin(origin, PATH) == "completed\n"


@pytest.mark.parametrize("clears_operations", [False, True], ids=["already-published", "empty"])
def test_preparation_that_finds_nothing_left_to_publish_does_not_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clears_operations: bool,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {PATH: "old\n"})
    write(repo / PATH, "this run\n")
    original = evidence(repo)
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / PATH, "this run and another run\n")
    git(mover, "add", "--", PATH)
    git(mover, "commit", "--quiet", "-m", "both runs are already represented")
    git(mover, "push", "--quiet", "origin", "HEAD:main")
    tip = git(origin, "rev-parse", "main").strip()
    prepared_at: list[str] = []

    def prepare(base: str, active: PublicationRequest) -> PublicationRequest:
        prepared_at.append(base)
        current = git(repo, "show", f"{base}:{PATH}")
        write(repo / PATH, current)
        return dataclasses.replace(
            active,
            source_tip=base,
            writes={}
            if clears_operations
            else {
                PATH: Write(
                    hashlib.sha256((repo / PATH).read_bytes()).hexdigest(),
                    Repository(repo).entry(base, PATH),
                )
            },
        )

    requested = dataclasses.replace(
        original,
        writes={PATH: dataclasses.replace(original.writes[PATH], immutable=False)},
        preparation_scopes=(PATH,),
        prepare=prepare,
    )

    result = publish(requested, repo=repo, retry=RETRY)

    assert prepared_at == [tip]
    assert result.status is (Status.NO_CHANGES if clears_operations else Status.ALREADY_ON_MAIN)
    assert result.prepared and result.push_count == 0
    assert result.candidate is None
    assert git(origin, "rev-parse", "main").strip() == tip


def test_mode_conversion_is_an_integrity_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {PATH: "old\n"})
    git(repo, "update-index", "--chmod=+x", PATH)
    git(repo, "commit", "--quiet", "-m", "executable source")
    git(repo, "push", "--quiet", "origin", "HEAD:main")
    write(repo / PATH, "new\n")
    result = publish(evidence(repo), repo=repo, retry=RETRY)
    assert result.status is Status.INTEGRITY_REFUSED
    assert on_origin(origin, PATH) == "old\n"


@pytest.mark.parametrize("path", ["../escape", "/absolute", "state/../escape", ".git/config"])
def test_non_repository_paths_never_reach_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"seed": "seed\n"})
    write(repo / PATH, "completed\n")
    original = evidence(repo)
    result = publish(
        dataclasses.replace(
            original, writes={path: original.writes[PATH]}, write_permissions=(path,)
        ),
        repo=repo,
        retry=RETRY,
    )
    assert result.status is Status.INTEGRITY_REFUSED
    assert result.push_count == 0
    assert Repository(origin).entry("main", PATH) is None


def test_expired_deadline_does_not_count_a_candidate_as_a_push(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"seed": "seed\n"})
    write(repo / PATH, "completed\n")
    result = publish(
        evidence(repo), repo=repo, retry=PushRetry({"default": 0.00001}, 0.001, 0.001, 1)
    )
    assert result.status is Status.REFUSED
    assert result.push_count == 0
    assert Repository(origin).entry("main", PATH) is None


@pytest.mark.parametrize("maximum,landed,pushes", [(2, False, 2), (4, True, 4)])
def test_real_rejections_count_actual_pushes_not_candidate_builds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    maximum: int,
    landed: bool,
    pushes: int,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"seed": "seed\n"})
    write(repo / PATH, "completed\n")
    _reject_the_first_pushes(origin, 3)
    result = publish(evidence(repo), repo=repo, retry=RETRY, max_pushes=maximum)
    assert result.push_count == pushes
    assert (result.status is Status.LANDED) is landed
    assert (Repository(origin).entry("main", PATH) is not None) is landed


def test_clean_filters_cannot_change_confirmed_candidate_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(
        tmp_path,
        {"seed": "seed\n", ".gitattributes": "*.json text eol=lf\n"},
    )
    (repo / PATH).parent.mkdir(parents=True)
    (repo / PATH).write_bytes(b"completed\r\n")
    result = publish(evidence(repo), repo=repo, retry=RETRY)
    assert result.status is Status.INTEGRITY_REFUSED
    assert result.push_count == 0
    assert Repository(origin).entry("main", PATH) is None


@pytest.mark.parametrize("mode", ["120000", "160000"])
def test_symlink_and_submodule_source_entries_cannot_become_data_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {PATH: "original\n"})
    oid = git(repo, "rev-parse", "HEAD" if mode == "160000" else f"HEAD:{PATH}").strip()
    git(repo, "update-index", "--cacheinfo", mode, oid, PATH)
    git(repo, "commit", "--quiet", "-m", "non-data source entry")
    git(repo, "push", "--quiet", "origin", "HEAD:main")
    write(repo / PATH, "completed\n")
    result = publish(evidence(repo), repo=repo, retry=RETRY)
    assert result.status is Status.INTEGRITY_REFUSED
    assert result.push_count == 0
    entry = Repository(origin).entry("main", PATH)
    assert entry is not None and entry.mode == mode
