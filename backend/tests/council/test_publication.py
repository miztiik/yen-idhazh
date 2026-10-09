"""Can the collecting job publish only confirmed, declared files to a real origin?"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from conftest import CONTRACT_FIXTURES_DIR
from gardener._garden import an_origin, git, on_origin, quiet_git, write
from workflows._harness import _isolated_env, _run_commit_script

from idhazh import atomic_write, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.council_run_record import CouncilRunRecord
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import publication
from idhazh.ledger import staging

DAY = "2026-09-27"
RUN = f"{DAY}-18012345678"
PREFIXES = (staging.staged_path(LedgerName.COUNCIL_RUN_RECORDS), "state/paper")
PAPER = "state/paper/result.json"
OTHER = "state/paper/other-tenant.json"
RECEIPT = f"backend/var/council/{RUN}/publication-1.json"


def writer(checkout: Path) -> WriterIdentity:
    return WriterIdentity(
        run_id=RUN,
        attempt=1,
        job=ServerJob.SAVE_COUNCIL_RESULTS,
        shard=0,
        producer="council.session",
        git_sha=git(checkout, "rev-parse", "HEAD").strip(),
    )


@contextmanager
def recording(checkout: Path) -> Iterator[None]:
    with publication.record(
        state_dir=checkout / "state",
        identity=writer(checkout),
        prefixes=PREFIXES,
        destination=checkout / RECEIPT,
    ):
        yield


def collected(
    checkout: Path, tmp_path: Path, prefixes: tuple[str, ...] = PREFIXES
) -> CompletedProcess[str]:
    env = _isolated_env(tmp_path)
    return _run_commit_script(
        checkout,
        env,
        prefixes,
        {
            "COMMIT_MESSAGE": "council: fixture",
            "NOTHING_STAGED_MESSAGE": "nothing confirmed",
            "PUSH_FAILED_MESSAGE": "fixture publication failed",
            "PUBLICATION_RECEIPT": RECEIPT,
            "GITHUB_JOB": ServerJob.SAVE_COUNCIL_RESULTS.value,
            "GITHUB_RUN_ID": RUN.rsplit("-", 1)[-1],
            "GITHUB_RUN_ATTEMPT": "1",
            "SHARD": "0",
        },
    )


def garden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    quiet_git(tmp_path, monkeypatch)
    return an_origin(
        tmp_path,
        {
            ".gitignore": "backend/var/\n",
            "README.md": "unchanged\n",
            OTHER: "another tenant\n",
        },
    )


def test_confirmed_raw_and_flat_records_reach_origin_without_sweeping_a_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    row = CouncilRunRecord.from_json(
        (CONTRACT_FIXTURES_DIR / "council-run-record/a-selection-that-ran-no-model.json").read_text(
            encoding="utf-8"
        )
    )
    with recording(checkout):
        raw = ledger.persist(
            checkout / "state",
            [row],
            ledger=LedgerName.COUNCIL_RUN_RECORDS,
            covers=DAY,
            identity=writer(checkout),
        )[0]
        with publication.scope(state_dir=checkout / "state", prefixes=("state/paper",)):
            atomic_write.write_atomic(checkout / PAPER, '{"count":1}\n')

    result = collected(checkout, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert on_origin(origin, PAPER) == '{"count":1}\n'
    assert on_origin(origin, raw.relative_to(checkout).as_posix()) is not None
    assert on_origin(origin, OTHER) == "another tenant\n"
    assert on_origin(origin, RECEIPT) is None
    assert PublicationReceipt.from_json((checkout / RECEIPT).read_text()).writes.keys() == {
        PAPER,
        raw.relative_to(checkout).as_posix(),
    }


@pytest.mark.parametrize("path", ["README.md", "state/undeclared/result.json", OTHER])
@pytest.mark.parametrize("prestage", [False, True])
def test_an_unconfirmed_modification_is_refused_before_commit_or_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, prestage: bool
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    before = git(checkout, "rev-parse", "HEAD")
    with recording(checkout):
        atomic_write.write_atomic(checkout / PAPER, "confirmed\n")
    write(checkout / path, "not this writer's output\n")
    if prestage:
        git(checkout, "add", "--", path)
    staged_before = git(checkout, "diff", "--cached", "--name-only")

    result = collected(checkout, tmp_path)

    assert result.returncode == 2, result.stdout + result.stderr
    assert path in result.stderr
    assert git(checkout, "rev-parse", "HEAD") == before
    assert git(origin, "rev-parse", "main") == before
    assert git(checkout, "diff", "--cached", "--name-only") == staged_before
    assert on_origin(origin, PAPER) is None


def test_a_receipt_cannot_grant_a_path_the_declarations_did_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    with recording(checkout):
        atomic_write.write_atomic(checkout / PAPER, "confirmed\n")

    result = collected(checkout, tmp_path, prefixes=(PREFIXES[0],))

    assert result.returncode == 2
    assert "outside the declared" in result.stderr
    assert on_origin(origin, PAPER) is None


def test_changed_bytes_after_the_receipt_are_not_committed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    with recording(checkout):
        atomic_write.write_atomic(checkout / PAPER, "confirmed\n")
    write(checkout / PAPER, "changed afterwards\n")

    result = collected(checkout, tmp_path)

    assert result.returncode == 2
    assert "changed after" in result.stderr
    assert on_origin(origin, PAPER) is None


def test_a_later_failure_keeps_the_completed_writes_publishable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="later tenant failed"), recording(checkout):
        atomic_write.write_atomic(checkout / PAPER, "partial results\n")
        raise ValueError("later tenant failed")

    result = collected(checkout, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert on_origin(origin, PAPER) == "partial results\n"


def test_another_shards_raw_file_cannot_be_confirmed_by_this_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    row = CouncilRunRecord.from_json(
        (CONTRACT_FIXTURES_DIR / "council-run-record/a-selection-that-ran-no-model.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(ValueError, match="another raw-file writer"), recording(checkout):
        ledger.persist(
            checkout / "state",
            [row],
            ledger=LedgerName.COUNCIL_RUN_RECORDS,
            covers=DAY,
            identity=writer(checkout).model_copy(update={"shard": 1}),
        )

    result = collected(checkout, tmp_path)

    assert result.returncode == 2
    assert "no completed write" in result.stderr
    assert git(origin, "rev-parse", "main") == git(checkout, "rev-parse", "HEAD")


def test_a_tenant_cannot_write_a_second_tenants_declared_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, checkout = garden(tmp_path, monkeypatch)
    with (
        pytest.raises(ValueError, match="outside this writer"),
        recording(checkout),
        publication.scope(state_dir=checkout / "state", prefixes=(PREFIXES[0],)),
    ):
        atomic_write.write_atomic(checkout / PAPER, "wrong tenant\n")
    assert PublicationReceipt.from_json((checkout / RECEIPT).read_text()).writes == {}


def test_a_lost_race_rebases_only_confirmed_files_and_keeps_origins_new_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / "state/paper/new-sibling.json", "another writer landed\n")
    git(mover, "add", "--", "state/paper/new-sibling.json")
    git(mover, "commit", "--quiet", "-m", "a sibling landed first")
    git(mover, "push", "--quiet")
    with recording(checkout):
        atomic_write.write_atomic(checkout / PAPER, "confirmed\n")

    result = collected(checkout, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert on_origin(origin, PAPER) == "confirmed\n"
    assert on_origin(origin, "state/paper/new-sibling.json") == "another writer landed\n"
    assert "rebasing" in result.stdout


def test_two_settles_share_one_named_receipt_without_duplicate_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    for count in (1, 2):
        with recording(checkout):
            atomic_write.write_atomic(checkout / PAPER, f"{count}\n")
    receipt = PublicationReceipt.from_json((checkout / RECEIPT).read_text())
    assert len(receipt.writes) == 1
    result = collected(checkout, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert on_origin(origin, PAPER) == "2\n"


def test_git_line_ending_conversion_cannot_publish_unconfirmed_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    write(checkout / ".gitattributes", "state/paper/*.json text eol=lf\n")
    git(checkout, "add", "--", ".gitattributes")
    git(checkout, "commit", "--quiet", "-m", "declare text normalization")
    git(checkout, "push", "--quiet")
    before = git(checkout, "rev-parse", "HEAD")
    with recording(checkout):
        atomic_write.write_atomic(checkout / PAPER, '{"count":1}\r\n')

    result = collected(checkout, tmp_path)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "Git blob differs" in result.stderr
    assert git(checkout, "rev-parse", "HEAD") == before
    assert git(origin, "rev-parse", "main") == before
    assert on_origin(origin, PAPER) is None


def test_a_conflicted_uuid_raw_file_keeps_exactly_this_attempts_confirmed_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    row = CouncilRunRecord.from_json(
        (CONTRACT_FIXTURES_DIR / "council-run-record/a-selection-that-ran-no-model.json").read_text(
            encoding="utf-8"
        )
    )
    with recording(checkout):
        raw = ledger.persist(
            checkout / "state",
            [row],
            ledger=LedgerName.COUNCIL_RUN_RECORDS,
            covers=DAY,
            identity=writer(checkout),
        )[0]
    relative = raw.relative_to(checkout).as_posix()
    expected = git(checkout, "hash-object", "--", relative)
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / relative, "a competing copy of the same UUID\n")
    git(mover, "add", "--", relative)
    git(mover, "commit", "--quiet", "-m", "a competing raw file")
    git(mover, "push", "--quiet")

    result = collected(checkout, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"keeping what this job wrote at {relative}" in result.stdout
    assert git(origin, "rev-parse", f"main:{relative}") == expected
    assert on_origin(origin, OTHER) == "another tenant\n"


def test_a_clean_text_rebase_cannot_publish_bytes_absent_from_the_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout = garden(tmp_path, monkeypatch)
    write(checkout / PAPER, "first\nmiddle\nlast\n")
    git(checkout, "add", "--", PAPER)
    git(checkout, "commit", "--quiet", "-m", "the initial flat record")
    git(checkout, "push", "--quiet")
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    with recording(checkout):
        atomic_write.write_atomic(checkout / PAPER, "this attempt\nmiddle\nlast\n")
    write(mover / PAPER, "first\nmiddle\nanother writer\n")
    git(mover, "add", "--", PAPER)
    git(mover, "commit", "--quiet", "-m", "another writer's flat record")
    git(mover, "push", "--quiet")
    tip = git(origin, "rev-parse", "main")

    result = collected(checkout, tmp_path)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "changed after" in result.stderr
    assert git(origin, "rev-parse", "main") == tip
    assert on_origin(origin, PAPER) == "first\nmiddle\nanother writer\n"
