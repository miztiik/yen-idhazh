"""Real Git publication preserves full evaluation input across job loss and push races."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, writer_identity

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.observation_lookup import ObservationBatch, ObservationLookupSettings
from idhazh.evals.observation_batches import (
    file_batch,
    incoming_path,
    input_root,
    load_batch,
    lookup_root,
    preparation_path,
    prepare,
    row_digest,
    save_batch,
)
from idhazh.evals.observation_lookup import ObservationLookup
from utilities.evaluation_inbox import publish_inputs

from ._harness import (
    _git,
    _isolated_env,
    _reject_the_first_pushes,
    _run_commit_script,
    _scripted_origin,
    _write,
)

pytestmark = pytest.mark.workflow

PREPARE_PROGRAM = REPO_ROOT / "backend/utilities/prepare_evaluation_publication.py"
PREPARED_PATHS = "backend/var/evaluation-inputs/prepared.json"


def _publication_origin(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    environment = _isolated_env(tmp_path)
    environment["PYTHONPATH"] = str(REPO_ROOT / "backend")
    origin, runner = _scripted_origin(tmp_path, environment, ["state/other"])
    _write(runner / ".gitignore", (REPO_ROOT / ".gitignore").read_text(encoding="ascii"))
    _write(
        runner / "config/observation-lookup.json",
        ObservationLookupSettings(max_leaf_bytes=16384).model_dump_json() + "\n",
    )
    _git(runner, environment, "add", ".gitignore", "config/observation-lookup.json")
    _git(runner, environment, "commit", "-m", "Configure the evaluation publisher")
    _git(runner, environment, "push", "origin", "main")
    return origin, runner, environment


def _commit_settings(runner: Path, batch: ObservationBatch, *, recovery: bool = False) -> dict[str, str]:
    source = (
        ["--batch-id", batch.batch_id]
        if recovery
        else [
            "--inputs", preparation_path(runner / "state", batch.identity).relative_to(runner).as_posix(),
            "--attempt", str(batch.identity.attempt),
        ]
    )
    return {
        "COMMIT_MESSAGE": "Publish evaluations",
        "NOTHING_STAGED_MESSAGE": "Evaluations are already published",
        "PUSH_FAILED_MESSAGE": "Could not publish evaluations",
        "PUSH_DEADLINE_SECONDS": "30",
        "PREPARE_COMMAND": " ".join(
            [sys.executable, str(PREPARE_PROGRAM), "--state-dir", "state", *source, "--paths-file", PREPARED_PATHS]
        ),
        "PREPARED_PATHS_FILE": PREPARED_PATHS,
    }


def _batch(
    *numbers: int,
    run_id: str = "2026-10-02-123",
    job: ServerJob = ServerJob.ASSEMBLE,
    shard: int = 0,
    attempt: int = 1,
) -> ObservationBatch:
    fixture = EvalRow.read(next((CONTRACT_FIXTURES_DIR / "eval-row").glob("*.json")))
    return ObservationBatch.model_validate(
        {
            "identity": writer_identity(run_id, job=job, shard=shard, attempt=attempt),
            "rows": [
                fixture.model_copy(
                    update={
                        "date": run_id[:10],
                        "run_id": run_id,
                        "url_key": hashlib.sha256(f"url-{number}".encode()).hexdigest(),
                        "output_digest": hashlib.sha256(f"output-{number}".encode()).hexdigest(),
                    }
                )
                for number in numbers
            ],
        }
    )


@pytest.mark.parametrize(
    "retry_config", [None, "config/push-retry.json"], ids=["default-config", "relative-config"]
)
def test_inbox_publication_preserves_every_uncommitted_job_output(
    tmp_path: Path, retry_config: str | None
) -> None:
    environment = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, environment, ["state/other"])
    if retry_config is not None:
        environment["PUSH_RETRY_CONFIG"] = retry_config
    _write(runner / ".git/info/exclude", "backend/var/\n")
    tracked = runner / "runner-noise.txt"
    untracked = runner / "state/new-result.json"
    _write(tracked, "the job has not committed this yet\n")
    _write(untracked, '{"result":"keep this"}\n')
    batch = _batch(1, 1, 2)
    save_batch(runner / "state", batch)
    before = _git(runner, environment, "status", "--porcelain")
    head = _git(runner, environment, "rev-parse", "HEAD")
    output = tmp_path / "github-output"
    _write(output, "unchanged\n")
    _reject_the_first_pushes(origin, 1)
    publish_inputs(
        runner / "state",
        [batch],
        environment={
            **environment,
            "PREPARE_COMMAND": "a-command-that-must-not-run",
            "PREPARED_PATHS_FILE": "must-not-write.json",
            "REFRESH_PATHS": "runner-noise.txt",
            "REGENERATE_COMMAND": "a-command-that-must-not-run",
            "GITHUB_OUTPUT": str(output),
        },
    )
    relative = incoming_path(runner / "state", batch.batch_id).relative_to(runner).as_posix()
    committed = _git(origin, environment, "show", f"main:{relative}")
    assert ObservationBatch.model_validate_json(committed) == batch
    assert _git(runner, environment, "status", "--porcelain") == before
    assert _git(runner, environment, "rev-parse", "HEAD") == head
    assert tracked.read_text() == "the job has not committed this yet\n"
    assert untracked.read_text() == '{"result":"keep this"}\n'
    assert output.read_text() == "unchanged\n"
    assert _git(origin, environment, "log", "-1", "--format=%an <%ae>").strip() == (
        "miztiik <miztiik@users.noreply.github.com>"
    )


def test_a_named_inbox_batch_survives_job_loss_and_is_not_republished(tmp_path: Path) -> None:
    origin, runner, environment = _publication_origin(tmp_path)
    batch = _batch(1, 1, 2)
    publish_inputs(runner / "state", [batch], environment=environment)
    trace = tmp_path / "repeated-publication.jsonl"
    publish_inputs(
        runner / "state", [batch], environment={**environment, "GIT_TRACE2_EVENT": str(trace)}
    )
    assert not any(
        record.get("event") == "start" and "push" in record.get("argv", [])
        for record in map(json.loads, trace.read_text().splitlines())
    )


    recovered = tmp_path / "recovered"
    _git(tmp_path, environment, "clone", str(origin), str(recovered))
    state = recovered / "state"
    assert load_batch(state, batch.batch_id) == batch
    manifest = preparation_path(state, batch.identity)
    paths = prepare(state, manifest, settings=ObservationLookupSettings())
    assert incoming_path(state, batch.batch_id).relative_to(recovered).as_posix() in paths
    assert not incoming_path(state, batch.batch_id).exists()
    assert ObservationBatch.read(input_root(state) / "batches" / f"{batch.batch_id}.json") == batch
    rows = ledger.load_ledger_rows(state, LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert len(rows) == 2
    assert {row_digest(row) for row in rows} == {row_digest(row) for row in batch.rows}
    with ObservationLookup(lookup_root(state)) as lookup:
        receipt = lookup.receipt(batch.batch_id)
        assert receipt is not None and receipt.accepted == 2
        assert all((state / path).relative_to(recovered).as_posix() in paths for path in receipt.output_paths)
        assert (lookup_root(state) / "root.json").relative_to(recovered).as_posix() in paths
    result = _run_commit_script(
        recovered,
        environment,
        ["state"],
        {
            "COMMIT_MESSAGE": "Publish recovered evaluations",
            "NOTHING_STAGED_MESSAGE": "Already published",
            "PUSH_FAILED_MESSAGE": "Could not publish evaluations",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    trace.unlink()
    publish_inputs(
        runner / "state", [batch], environment={**environment, "GIT_TRACE2_EVENT": str(trace)}
    )
    assert not any(
        record.get("event") == "start" and "push" in record.get("argv", [])
        for record in map(json.loads, trace.read_text().splitlines())
    )


def test_a_missing_job_input_writes_fresh_paths_without_an_install(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    paths = tmp_path / PREPARED_PATHS
    _write(paths, '["stale-output.json"]\n')
    result = subprocess.run(
        [
            sys.executable, "-S", str(PREPARE_PROGRAM), "--state-dir", str(state),
            "--inputs", "backend/var/evaluation-inputs/2026-10-02-123/work-0.json",
            "--paths-file", PREPARED_PATHS,
        ],
        env={name: value for name, value in os.environ.items() if name != "PYTHONPATH"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert paths.read_text() == "[]\n"


def test_inbox_preparation_imports_from_its_checkout_without_pythonpath(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    inputs = input_root(state) / "inbox.json"
    _write(inputs, '{"batches":[],"paths":[]}\n')
    result = subprocess.run(
        [
            sys.executable, "-I", str(PREPARE_PROGRAM), "--inbox-only",
            "--state-dir", str(state), "--inputs", str(inputs),
            "--paths-file", PREPARED_PATHS,
        ],
        cwd=tmp_path,
        env={name: value for name, value in os.environ.items() if name != "PYTHONPATH"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / PREPARED_PATHS).read_text() == "[]\n"


@pytest.mark.parametrize("additional_input", [False, True], ids=["consumed-only", "mixed-inputs"])
def test_an_inbox_push_race_does_not_recreate_a_consumed_named_batch(
    tmp_path: Path, additional_input: bool
) -> None:
    origin, runner, environment = _publication_origin(tmp_path)
    batch = _batch(1)
    other = _batch(2, run_id="2026-10-03-200")
    unrelated = _batch(3, run_id="2026-10-04-300")
    consumer = tmp_path / "consumer"
    _git(tmp_path, environment, "clone", str(origin), str(consumer))
    pending = incoming_path(consumer / "state", batch.batch_id)
    relative = pending.relative_to(consumer).as_posix()
    _write(pending, batch.to_json())
    unrelated_path = incoming_path(consumer / "state", unrelated.batch_id)
    _write(unrelated_path, unrelated.to_json())
    _git(consumer, environment, "add", relative, unrelated_path.relative_to(consumer).as_posix())
    _git(consumer, environment, "commit", "-m", "Record the competing evaluation input")
    save_batch(consumer / "state", batch)
    prepare(
        consumer / "state",
        preparation_path(consumer / "state", batch.identity),
        settings=ObservationLookupSettings(),
    )
    _git(consumer, environment, "add", "state")
    _git(consumer, environment, "commit", "-m", "Consume the competing evaluation input")
    _git(consumer, environment, "push", "origin", "HEAD:refs/heads/consumed")
    consumed = _git(consumer, environment, "rev-parse", "HEAD").strip()
    original = _git(origin, environment, "rev-parse", "main").strip()
    hook = origin / "hooks/pre-receive"
    _write(
        hook,
        "#!/bin/sh\n"
        'marker="$(dirname "$0")/../consumed-before-inbox-push"\n'
        'if [ ! -f "$marker" ]; then\n'
        '  printf "advanced\\n" > "$marker"\n'
        "  unset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES\n"
        f"  git update-ref refs/heads/main {consumed} {original} || exit 1\n"
        '  echo "sibling consumed the input before this push" >&2\n'
        "  exit 1\n"
        "fi\n",
    )
    hook.chmod(0o755)
    before = _git(runner, environment, "status", "--porcelain")

    publish_inputs(
        runner / "state",
        [batch, other] if additional_input else [batch],
        environment={**environment, "PUSH_DEADLINE_SECONDS": "90"},
    )

    assert (origin / "consumed-before-inbox-push").is_file()
    assert not _git(origin, environment, "ls-tree", "main", "--", relative)
    assert ObservationBatch.model_validate_json(
        _git(origin, environment, "show", f"main:{unrelated_path.relative_to(consumer).as_posix()}")
    ) == unrelated
    assert _git(runner, environment, "status", "--porcelain") == before
    changed = set(
        _git(origin, environment, "diff", "--name-only", consumed, "main").splitlines()
    )
    if additional_input:
        other_path = incoming_path(runner / "state", other.batch_id).relative_to(runner).as_posix()
        assert changed == {other_path}
        assert ObservationBatch.model_validate_json(
            _git(origin, environment, "show", f"main:{other_path}")
        ) == other
    else:
        assert not changed
        assert _git(origin, environment, "rev-parse", "main").strip() == consumed


def test_the_hook_publishes_a_previous_local_apply_and_removes_its_inbox(tmp_path: Path) -> None:
    origin, runner, environment = _publication_origin(tmp_path)
    batch = _batch(1, 2)
    state = runner / "state"
    assert file_batch(state, batch.rows, batch.identity, ObservationLookupSettings()) == 2
    original = preparation_path(state, batch.identity)
    before = original.read_bytes()
    result = _run_commit_script(runner, environment, ["state"], _commit_settings(runner, batch))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "push rejected" in result.stdout
    assert original.is_file() and before != b"[]\n"
    paths = json.loads((runner / PREPARED_PATHS).read_text())
    assert incoming_path(state, batch.batch_id).relative_to(runner).as_posix() in paths
    published = tmp_path / "published"
    _git(tmp_path, environment, "clone", str(origin), str(published))
    loaded = ledger.load_ledger_rows(published / "state", LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert {row_digest(row) for row in loaded} == {row_digest(row) for row in batch.rows}
    assert len(loaded) == 2
    assert not incoming_path(published / "state", batch.batch_id).exists()
    assert load_batch(state, batch.batch_id) == batch
    assert not _git(published, environment, "ls-files", "--", "*.observation-lookup-lock*")


@pytest.mark.parametrize("split", [False, True], ids=["overlap-across-days", "changed-partitions"])
def test_a_rejected_push_rechecks_the_full_batch_without_text_conflicts(
    tmp_path: Path, split: bool
) -> None:
    origin, losing, environment = _publication_origin(tmp_path)
    winning = tmp_path / "winning"
    _git(tmp_path, environment, "clone", str(origin), str(winning))
    winner = _batch(*(range(180) if split else [1, 2]), run_id="2026-10-02-200")
    loser = _batch(
        *(range(160, 210) if split else [2, 3]),
        run_id="2026-10-03-300", job=ServerJob.WORK, shard=3, attempt=2,
    )
    settings = ObservationLookupSettings(max_leaf_bytes=16384)
    assert file_batch(losing / "state", loser.rows, loser.identity, settings) == len(loser.rows)
    assert file_batch(winning / "state", winner.rows, winner.identity, settings) == len(winner.rows)
    result = _run_commit_script(winning, environment, ["state"], _commit_settings(winning, winner))
    assert result.returncode == 0, result.stdout + result.stderr
    winner_tip = _git(origin, environment, "rev-parse", "main").strip()
    if split:
        with ObservationLookup(lookup_root(winning / "state")) as lookup:
            assert lookup.manifest().node.kind == "page"
    result = _run_commit_script(losing, environment, ["state"], _commit_settings(losing, loser))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "push rejected" in result.stdout
    assert "CONFLICT" not in result.stdout + result.stderr
    published = tmp_path / "published"
    _git(tmp_path, environment, "clone", str(origin), str(published))
    state = published / "state"
    rows = ledger.load_ledger_rows(state, LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    expected = {row_digest(row) for row in [*winner.rows, *loser.rows]}
    assert len(rows) == len(expected)
    assert {row_digest(row) for row in rows} == expected
    first_day = {row_digest(row) for row in winner.rows}
    assert all(row.date == ("2026-10-02" if row_digest(row) in first_day else "2026-10-03") for row in rows)
    with ObservationLookup(lookup_root(state)) as lookup:
        assert lookup.recorded(expected) == expected
        receipt = lookup.receipt(loser.batch_id)
        assert receipt is not None and receipt.accepted == len(expected) - len(first_day)
        assert lookup.receipt(winner.batch_id) is not None
    paths = set(json.loads((losing / PREPARED_PATHS).read_text()))
    changed = set(
        _git(
            origin, environment, "diff", "--name-only", winner_tip, "main", "--",
            "state/raw/summary-quality-evals", "state/summary-quality-evals-index",
        ).splitlines()
    )
    assert changed <= paths
    assert incoming_path(losing / "state", loser.batch_id).relative_to(losing).as_posix() in paths
    assert load_batch(losing / "state", loser.batch_id) == loser
    assert not incoming_path(state, loser.batch_id).exists()
    if split:
        assert any("/nodes/" in path and not (state.parent / path).exists() for path in paths)


def test_a_failed_prepare_leaves_only_durable_input_for_named_recovery(tmp_path: Path) -> None:
    origin, runner, environment = _publication_origin(tmp_path)
    state = runner / "state"
    batch = _batch(9)
    save_batch(state, batch)
    _write(ledger.raw_root(state, LedgerName.SUMMARY_QUALITY_EVALS) / "unindexed.txt", "old output\n")
    result = _run_commit_script(runner, environment, ["state"], _commit_settings(runner, batch))
    assert result.returncode != 0
    assert "explicit observation lookup migration" in result.stdout + result.stderr
    assert json.loads((runner / PREPARED_PATHS).read_text()) == []
    pending = incoming_path(state, batch.batch_id).relative_to(runner).as_posix()
    assert ObservationBatch.model_validate_json(_git(origin, environment, "show", f"main:{pending}")) == batch
    assert not _git(origin, environment, "ls-tree", "-r", "--name-only", "main", "--", "state/raw/summary-quality-evals")
    assert not _git(origin, environment, "ls-tree", "-r", "--name-only", "main", "--", "state/summary-quality-evals-index/lookup")
    recovered = tmp_path / "recovered"
    _git(tmp_path, environment, "clone", str(origin), str(recovered))
    result = _run_commit_script(
        recovered, environment, ["state"], _commit_settings(recovered, batch, recovery=True)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert load_batch(recovered / "state", batch.batch_id) == batch
    assert not incoming_path(recovered / "state", batch.batch_id).exists()
    with ObservationLookup(lookup_root(recovered / "state")) as lookup:
        receipt = lookup.receipt(batch.batch_id)
        assert receipt is not None and receipt.accepted == 1
    rows = ledger.load_ledger_rows(recovered / "state", LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert len(rows) == 1 and row_digest(rows[0]) == row_digest(batch.rows[0])


def test_regeneration_publishes_a_new_batch_once_and_preserves_the_earlier_batch(tmp_path: Path) -> None:
    origin, runner, environment = _publication_origin(tmp_path)
    first = _batch(1)
    regenerated = _batch(2)
    settings = ObservationLookupSettings(max_leaf_bytes=16384)
    file_batch(runner / "state", first.rows, first.identity, settings)
    _write(runner / "state/assembly-output.json", '{"context":"before"}\n')
    other = tmp_path / "other"
    _git(tmp_path, environment, "clone", str(origin), str(other))
    _write(other / "tests/fixtures/assembly-context.json", regenerated.to_json())
    _git(other, environment, "add", "tests/fixtures/assembly-context.json")
    _git(other, environment, "commit", "-m", "Change the assembly input")
    _git(other, environment, "push", "origin", "main")
    regenerate = runner / "backend/var/regenerate.py"
    _write(
        regenerate,
        '"""Rebuild fixture evaluations from the competing committed context."""\n'
        "import json\n"
        "from pathlib import Path\n"
        "from idhazh import ledger\n"
        "from idhazh.config import load_observation_lookup\n"
        "from idhazh.contracts.eval_row import EvalRow\n"
        "from idhazh.contracts.ledger_name import LedgerName\n"
        "from idhazh.contracts.observation_lookup import ObservationBatch\n"
        "from idhazh.evals.observation_batches import file_batch, row_digest\n"
        'batch = ObservationBatch.read(Path("tests/fixtures/assembly-context.json"))\n'
        'file_batch(Path("state").resolve(), batch.rows, batch.identity, load_observation_lookup(Path("config")))\n'
        'rows = ledger.load_ledger_rows(Path("state").resolve(), LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)\n'
        'Path("state/assembly-output.json").write_text(json.dumps(sorted(row_digest(row) for row in rows)), encoding="ascii", newline="\\n")\n'
        'print("regenerated evaluation input")\n',
    )
    result = _run_commit_script(
        runner,
        environment,
        ["state"],
        {
            **_commit_settings(runner, first),
            "PUSH_DEADLINE_SECONDS": "90",
            "REFRESH_PATHS": "state/assembly-output.json",
            "REGENERATE_COMMAND": f"{sys.executable} {regenerate}",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("regenerated evaluation input") == 2
    subjects = _git(origin, environment, "log", "--format=%s", "main").splitlines()
    assert subjects.count("Record pending evaluation inputs") == 2
    assert subjects.count("Publish evaluations") == 1
    published = tmp_path / "published"
    _git(tmp_path, environment, "clone", str(origin), str(published))
    state = published / "state"
    rows = ledger.load_ledger_rows(state, LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert len(rows) == 2
    assert {row_digest(row) for row in rows} == {row_digest(first.rows[0]), row_digest(regenerated.rows[0])}
    assert set(json.loads((state / "assembly-output.json").read_text())) == {
        row_digest(row) for row in rows
    }
    with ObservationLookup(lookup_root(state)) as lookup:
        original_receipt = lookup.receipt(first.batch_id)
        changed_receipt = lookup.receipt(regenerated.batch_id)
        assert original_receipt is not None and changed_receipt is not None
        assert original_receipt.accepted == changed_receipt.accepted == 1
        assert set(original_receipt.output_paths).isdisjoint(changed_receipt.output_paths)
    for batch in (first, regenerated):
        assert load_batch(runner / "state", batch.batch_id) == batch
        assert not incoming_path(state, batch.batch_id).exists()


def test_a_successful_push_reported_as_failed_does_not_publish_twice(tmp_path: Path) -> None:
    origin, runner, environment = _publication_origin(tmp_path)
    state = runner / "state"
    batch = _batch(1, 2)
    save_batch(state, batch)
    publish_inputs(state, [batch], environment=environment)
    _git(runner, environment, "fetch", "origin", "main")
    _git(runner, environment, "merge", "--ff-only", "origin/main")
    file_batch(state, batch.rows, batch.identity, ObservationLookupSettings(max_leaf_bytes=16384))
    transport = tmp_path / "lose-push-response.sh"
    _write(
        transport,
        "#!/bin/sh\n"
        'git "$1" "$2"\n'
        "status=$?\n"
        'if [ "$status" -eq 0 ] && [ "$1" = "receive-pack" ] && [ ! -f "$2/response-lost" ]; then\n'
        '  printf "lost\\n" > "$2/response-lost"\n'
        "  exit 1\n"
        "fi\n"
        'exit "$status"\n',
    )
    _git(runner, environment, "config", "protocol.ext.allow", "always")
    _git(
        runner, environment, "remote", "set-url", "--push", "origin",
        f"ext::sh {transport.as_posix()} %s {origin.as_posix()}",
    )
    trace = tmp_path / "push-response.jsonl"
    result = _run_commit_script(
        runner, {**environment, "GIT_TRACE2_EVENT": str(trace)}, ["state"], _commit_settings(runner, batch)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (origin / "response-lost").is_file()
    assert "push rejected" in result.stdout
    assert sum(
        record.get("event") == "start" and "push" in record.get("argv", [])
        for record in map(json.loads, trace.read_text().splitlines())
    ) == 1
    assert _git(origin, environment, "log", "--format=%s").splitlines().count("Publish evaluations") == 1
    published = tmp_path / "published"
    _git(tmp_path, environment, "clone", str(origin), str(published))
    rows = ledger.load_ledger_rows(published / "state", LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert len(rows) == 2
    with ObservationLookup(lookup_root(published / "state")) as lookup:
        assert lookup.receipt(batch.batch_id) is not None
        assert lookup.recorded(row_digest(row) for row in rows) == {row_digest(row) for row in rows}
    assert not incoming_path(published / "state", batch.batch_id).exists()


@pytest.mark.parametrize("committed", [False, True], ids=["local-only", "published"])
def test_explicit_recovery_without_input_requires_a_committed_receipt(
    tmp_path: Path, committed: bool
) -> None:
    origin, runner, environment = _publication_origin(tmp_path)
    batch = _batch(1)
    state = runner / "state"
    file_batch(state, batch.rows, batch.identity, ObservationLookupSettings(max_leaf_bytes=16384))
    if committed:
        result = _run_commit_script(runner, environment, ["state"], _commit_settings(runner, batch))
        assert result.returncode == 0, result.stdout + result.stderr
        recovered = tmp_path / "recovered"
        _git(tmp_path, environment, "clone", str(origin), str(recovered))
    else:
        recovered = runner
        (input_root(state) / "batches" / f"{batch.batch_id}.json").unlink()
    before = _git(origin, environment, "rev-parse", "main")
    trace = tmp_path / "recovery.jsonl"
    result = _run_commit_script(
        recovered,
        {**environment, "GIT_TRACE2_EVENT": str(trace)},
        ["state"],
        _commit_settings(recovered, batch, recovery=True),
    )
    assert (result.returncode == 0) == committed, result.stdout + result.stderr
    assert json.loads((recovered / PREPARED_PATHS).read_text()) == []
    assert _git(origin, environment, "rev-parse", "main") == before
    assert not any(
        record.get("event") == "start" and "push" in record.get("argv", [])
        for record in map(json.loads, trace.read_text().splitlines())
    )


def test_empty_regeneration_restores_the_jobs_earlier_batch(tmp_path: Path) -> None:
    state = tmp_path / "state"
    batch = _batch(1)
    settings = ObservationLookupSettings(max_leaf_bytes=16384)
    assert file_batch(state, batch.rows, batch.identity, settings) == 1
    shutil.rmtree(lookup_root(state))
    shutil.rmtree(ledger.raw_root(state, LedgerName.SUMMARY_QUALITY_EVALS))
    assert file_batch(state, [], batch.identity, settings) == 0
    rows = ledger.load_ledger_rows(state, LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert len(rows) == 1 and row_digest(rows[0]) == row_digest(batch.rows[0])