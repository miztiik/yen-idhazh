"""Do the remaining real clients deliver only their checked completed files?"""

import dataclasses
import json
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, writer_identity
from gardener._garden import an_origin, git, quiet_git, write
from retention._trees import health_row
from test_host_publication import DAY as NATIVE_DAY
from test_host_publication import case as case
from test_host_publication import native_receipt

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry.traces import committed_trace_path
from utilities import (
    pipeline_test_ledgers,
    pipeline_test_publish,
    publication_evidence,
    record_publish,
)
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError
from utilities.publish_to_repo import Status

DATE = "2026-10-09"
EXECUTION = "123"
RETRY = {
    "deadline_seconds": {"default": 300},
    "base_step_seconds": 0.001,
    "ceiling_seconds": 0.001,
    "ceiling_after": 1,
}


def test_measure_publishes_the_real_native_probe_without_foreign_index(
    case: tuple[Path, Path, WriterIdentity],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin, repo, held = case
    source = held.git_sha
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("GITHUB_SHA", source)
    identity = WriterIdentity(
        run_id=held.run_id,
        attempt=1,
        job=ServerJob.RUNTIME,
        shard=0,
        producer="utilities.record_publish",
        git_sha=source,
    )
    receipt, limits = native_receipt(
        repo, identity, prefix=("pipeline-tests", "host-fingerprint")
    )
    assert receipt.writes
    publication_evidence.save(repo, identity, "measure", {})
    write(repo / "foreign-staged", "must not publish\n")
    git(repo, "add", "foreign-staged")
    index = (repo / ".git/index").read_bytes()
    assert record_publish.land(
        "measure", repo=repo, identity=identity, date=NATIVE_DAY,
        host_receipt=receipt, host_limits=limits, host_enabled=True,
    ) == 0
    assert (repo / ".git/index").read_bytes() == index
    assert Repository(origin).entry("main", "foreign-staged") is None
    for relative in receipt.writes:
        entry = Repository(origin).entry("main", relative)
        assert entry is not None
        assert Repository(origin).blob(entry.oid) == (repo / relative).read_bytes()


@pytest.mark.parametrize("wrong_execution", [False, True])
def test_pipeline_collector_checks_executed_raw_identity_and_declared_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    wrong_execution: bool,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, producer = an_origin(
        tmp_path,
        {"seed": "seed\n", "config/push-retry.json": json.dumps(RETRY) + "\n"},
    )
    source = git(producer, "rev-parse", "HEAD").strip()
    case = pipeline_test_ledgers._roots(CONFIG_DIR)[0]
    with ledger.use_registry(ledger.overlay_registry(("pipeline-tests", case))):
        ledger.persist(
            producer / "state",
            [health_row(day=DATE, run=123, number=1, stage=ItemStage.PUBLISH)],
            ledger=LedgerName.ITEM_HEALTH,
            covers=DATE,
            identity=writer_identity(f"{DATE}-{EXECUTION}", job=ServerJob.WORK).model_copy(
                update={"git_sha": source}
            ),
        )
        trace = committed_trace_path(
            producer / "state",
            run_id=f"{DATE}-{EXECUTION}",
            attempt=1,
            job=ServerJob.WORK,
            shard=0,
        )
        write(trace, "{}\n")
    collector = tmp_path / "collector"
    git(tmp_path, "clone", "--quiet", str(origin), str(collector))
    tree = collector / "backend/var/trial-ledgers"
    pipeline_test_ledgers.gather(
        producer / "state",
        tree,
        roots=[case],
        days=(DATE,),
    )
    if wrong_execution:
        with pytest.raises(IntegrityError, match="another invocation"):
            pipeline_test_publish.land(
                collector,
                tree,
                execution="other",
                attempt=1,
                code_sha=source,
                config_root=CONFIG_DIR,
            )
        assert git(origin, "rev-parse", "main").strip() == source
        return
    result = pipeline_test_publish.land(
        collector,
        tree,
        execution=EXECUTION,
        attempt=1,
        code_sha=source,
        config_root=CONFIG_DIR,
    )
    assert result.status is Status.LANDED, dataclasses.asdict(result)
    for path in tree.rglob("*"):
        if path.is_file():
            name, tier, *tail = path.relative_to(tree).parts
            if tier == pipeline_test_ledgers.TRACES:
                relative = ledger.tree_root(
                    Path("state"),
                    LedgerName.TRACES,
                    registry=ledger.overlay_registry(("pipeline-tests", name)),
                ).joinpath(*tail).as_posix()
            else:
                relative = "/".join(("state", tier, "pipeline-tests", name, *tail))
            entry = Repository(origin).entry("main", relative)
            assert entry is not None
            assert Repository(origin).blob(entry.oid) == path.read_bytes()
