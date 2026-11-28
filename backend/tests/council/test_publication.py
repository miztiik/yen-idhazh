"""Does the real collecting publisher retain earlier and later completed tenant work?"""

import json
import shutil
import time
from functools import partial
from pathlib import Path

import pytest
from gardener._garden import an_origin, git, on_origin, quiet_git
from support.native_performance import Batch, capture_openings, write_batches

from idhazh import config, ledger
from idhazh.contracts.council_events import CouncilProgram
from idhazh.contracts.council_invocation import Cell, SelectedJudge, Selection
from idhazh.contracts.council_run_record import CouncilRunRecord
from idhazh.contracts.host_fingerprint import HostFingerprintRow, HostHardwareRow
from idhazh.contracts.knobs.council import CouncilTask, JudgeLifecycleStatus
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.task_performance import TaskPerformanceRow
from idhazh.council import outcome, performance, registry, session
from idhazh.council.model_selection import bind_model
from idhazh.ledger.keys import HOST_FINGERPRINT_KEY
from idhazh.ledger.raw_files import load_current_rows
from idhazh.llm.serving_metrics import serving_measurement
from idhazh.telemetry.machine_evidence import VerifiedFile
from utilities import council_machine_delivery
from utilities.council_publish import settle_and_publish
from utilities.publication_git import Repository

from ._config import (
    copy_config,
    prepared_selection,
    set_host_fingerprint_placement,
    write_declarations,
)
from ._tenants import TENANT_SOURCE, a_venue, forget
from .test_lifecycle import room

SOURCE = (
    TENANT_SOURCE.replace(
        "atomic_write.write_atomic(path, str(shards))",
        "atomic_write.write_atomic(path, '\"completed\\\\n\"')",
    )
    .replace(
        "return ShardResult(outcome=ShardOutcome.COMPLETED, files=(session.artifact_path(path),))",
        "return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO, files=(session.artifact_path(path),))",
        1,
    )
    .replace(
        "from pathlib import Path",
        "from pathlib import Path\nimport json\nfrom idhazh import atomic_write",
    )
    .replace(
        "        self.settled.append(date)",
        """        self.settled.append(date)
        atomic_write.write_atomic(
            state_dir.parent / self.committed_paths[0] / (date + ".json"),
            json.loads(session.unit_file(
                date, slot="tasks", judge_id=self.judge_id, suffix=".json"
            ).read_text(encoding="utf-8"))
        )
        if self.judge_id.endswith("failed") and date == "2026-10-08":
            raise RuntimeError("later tenant failed after completing its write")""",
    )
    .replace(
        "return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)\n\n\nTENANT",
        "return ShardResult(outcome=ShardOutcome.COMPLETED)\n\n\nTENANT",
    )
)


def configuration(root: Path, slugs: tuple[str, ...]) -> Path:
    target = copy_config(root)
    write_declarations(target, slugs)
    path = target / "llm_council.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["judge_names"] = list(slugs)
    path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    return target


def test_publication_resolves_only_the_active_judge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            "config/push-retry.json": '{"deadline_seconds":{"default":300},"base_step_seconds":0.001,'
            '"ceiling_seconds":0.001,"ceiling_after":1}\n',
        },
    )
    package = "publication_lifecycle"
    a_venue(
        tmp_path,
        package=package,
        slugs={"active-judge": (1, ("state/paper",))},
        poisoned_neighbour="paused-judge",
        source=SOURCE,
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    forget(package)
    try:
        target = room(
            tmp_path,
            {
                "paused-judge": ("paused", True),
                "active-judge": ("active", False),
                "retired-judge": ("retired", False),
            },
        )
        selected = prepared_selection(
            target,
            dates=("2026-10-10",),
            run_id="2026-10-11-123",
            commit_sha=git(repo, "rev-parse", "HEAD").strip(),
        )
        assert (
            settle_and_publish(
                repo=repo,
                dates=("2026-10-10",),
                run_id="2026-10-11-123",
                commit_sha=git(repo, "rev-parse", "HEAD").strip(),
                config_root=target,
                selection=selected,
            )
            == 0
        )
        assert on_origin(origin, "state/paper/2026-10-10.json") == "completed\n"
        rows = ledger.load_days(
            repo / "state",
            LedgerName.COUNCIL_RUN_RECORDS,
            ["2026-10-10"],
            model=CouncilRunRecord,
        )
        assert len(rows) == 2 and {row.judge_id for row in rows} == {"active-judge"}
    finally:
        forget(package)


def test_many_tenants_and_later_dates_survive_a_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "off")
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            "config/push-retry.json": '{"deadline_seconds":{"default":300},"base_step_seconds":0.001,'
            '"ceiling_seconds":0.001,"ceiling_after":1}\n',
        },
    )
    package = "publisher_tenants"
    slugs = ("first", "second-failed", "third")
    a_venue(
        tmp_path,
        package=package,
        slugs={slug: (1, (f"state/experiments/{slug}",)) for slug in slugs},
        source=SOURCE,
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    forget(package)
    try:
        config_root = configuration(tmp_path, slugs)
        selected = prepared_selection(
            config_root,
            dates=("2026-10-09", "2026-10-08"),
            run_id="2026-10-09-123",
            commit_sha=git(repo, "rev-parse", "HEAD").strip(),
        )
        assert settle_and_publish(
            repo=repo,
            dates=selected.dates,
            run_id="2026-10-09-123",
            commit_sha=git(repo, "rev-parse", "HEAD").strip(),
            config_root=config_root,
            selection=selected,
        ) == 1
        for slug in slugs:
            for date in ("2026-10-08", "2026-10-09"):
                assert on_origin(origin, f"state/experiments/{slug}/{date}.json") == "completed\n"
        rows = ledger.load_days(
            repo / "state",
            LedgerName.COUNCIL_RUN_RECORDS,
            ["2026-10-08", "2026-10-09"],
            model=CouncilRunRecord,
        )
        assert len(rows) == 12
        assert sum(row.outcome == "failed" and row.fault == "raised" for row in rows) == 1
        assert sum(row.date == "2026-10-09" for row in rows) == 6
        assert not ledger.raw_root(repo / "state", LedgerName.HOST_FINGERPRINT).exists()
    finally:
        forget(package)


def test_empty_venue_writes_no_row_or_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"seed": "seed\n"})
    before = git(origin, "rev-parse", "main")
    target = configuration(tmp_path, ())
    selected = prepared_selection(
        target,
        dates=("2026-10-09",),
        run_id="2026-10-09-123",
        commit_sha=git(repo, "rev-parse", "HEAD").strip(),
    )
    assert (
        settle_and_publish(
            repo=repo,
            run_id="2026-10-09-123",
            commit_sha=git(repo, "rev-parse", "HEAD").strip(),
            config_root=target,
            selection=selected,
        )
        == 0
    )
    assert git(origin, "rev-parse", "main") == before
    assert not (repo / "state").exists()


@pytest.mark.parametrize("missing", [False, True], ids=["every-runner", "missing-and-skipped"])
def test_council_lands_original_runner_bytes_and_keeps_trials_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: bool,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "typescript")
    origin, repo = an_origin(tmp_path, {
        "config/push-retry.json": '{"deadline_seconds":{"default":300},"base_step_seconds":0.001,'
        '"ceiling_seconds":0.001,"ceiling_after":1}\n',
    })
    revision = git(repo, "rev-parse", "HEAD").strip()
    package = "measured_venue"
    active, paused = "active-judge", "paused-judge"
    a_venue(tmp_path, package=package, slugs={active: (5, ()), paused: (1, ())})
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    root = tmp_path / "producers"
    collector = repo / "backend" / "var" / "council"
    monkeypatch.setattr(session, "COUNCIL_ROOT", root)
    target = room(tmp_path, {active: ("active", True), paused: ("paused", False)})
    council_file = target / "llm_council.json"
    current = json.loads(council_file.read_text(encoding="utf-8"))
    council_file.write_text(json.dumps({**current, "shards": 5}), encoding="utf-8")
    set_host_fingerprint_placement(target, False)
    settings = config.load(target)
    judged = "2026-10-09"
    selected = Selection(
        version=Selection.schema_version(), run_id="2026-10-10-123", attempt=1, git_sha=revision,
        mode="manual", anchor_date=judged, window=(judged,),
        judges=(
            SelectedJudge(
                tenant=active, status=JudgeLifecycleStatus.ACTIVE, dates=(judged,), shards=5,
                model=bind_model(settings.council, active),
            ),
            SelectedJudge(tenant=paused, status=JudgeLifecycleStatus.PAUSED, dates=(judged,), shards=1),
        ),
    )
    cells = tuple(
        Cell(tenant=judge.tenant, date=judged, shard=part, shards=judge.shards, runs_model=judge.tenant == active)
        for judge in selected.judges for part in range(judge.shards)
        if not (missing and judge.tenant == active and part == 3)
    )
    session.prepare(settings.council, run_id=selected.run_id, selection=selected)
    bundles = council_machine_delivery.incoming(root, selected, cells)
    captures: list[tuple[VerifiedFile, bool]] = []
    batches: list[Batch] = []
    direct = performance.selected_runner(collector, performance.Phase.SETTLE, selected)
    started = tuple(
        (bundle, cell) for bundle, cell in zip(bundles, [None, None, *cells], strict=True)
        if not (missing and cell is not None and cell.tenant == active and cell.shard == 4)
    )
    openings = capture_openings((
        *((bundle.runner.bundle, bundle.runner.opening) for bundle, _ in started),
        (direct.bundle, direct.opening),
    ))
    for (bundle, cell), opening in zip(started, openings[:-1], strict=True):
        host = bundle.runner
        assert isinstance(opening.row, HostHardwareRow)
        assert (opening.row.job, opening.row.pipeline_name) == (host.phase, "council")
        if cell is not None:
            assert (opening.row.task_name, opening.row.shard, opening.row.date) == (
                f"judge-{cell.tenant}", cell.shard, cell.date,
            )
            events = (
                root / "outgoing" / f"shard-{cell.tenant}-{cell.date}-{cell.shard}"
                / "events" / cell.tenant / cell.date / f"{cell.shard}.jsonl"
            )
            with monkeypatch.context() as scoped:
                scoped.setenv("COUNCIL_EVENT_FILE", str(events))

                def judge_cell(cell: Cell) -> int:
                    result = session.run_shard(
                        settings.council, slug=cell.tenant, date=cell.date,
                        run_id=selected.run_id, shard=cell.shard, shards=cell.shards,
                        started=time.monotonic(), selection=selected,
                    )
                    return outcome.of_results((result,))

                assert outcome.run(CouncilProgram.SHARD, partial(judge_cell, cell)) == 0
        captures.append((opening, not host.trial))
        observations = bundle.tasks
        if host.phase is performance.Phase.DRAW:
            observations = (*observations, host.task(judged, CouncilTask.PREPARE, paused))
        requests = []
        for expected in observations:
            if expected.kind == "model-serving":
                if cell is None or cell.shard != 0:
                    continue
                counters = serving_measurement(
                    "llamacpp:prompt_tokens_total 13\nllamacpp:prompt_seconds_total 2\n",
                    subject_id="test-model", outcome="success",
                )
                assert counters is not None
            else:
                counters = {"elapsed_ms": 23}
            requests.append((expected, counters, (
                host.tenant_store(selected, paused)
                if expected.writer.task_name == "prepare-paused-judge" else host.bundle
            )))
        batches.append(Batch(tmp_path / f"machine-{len(batches)}", tuple(requests), opening))
    opening = openings[-1]
    captures.append((opening, True))
    batches.append(Batch(tmp_path / "settlement-machine", (
        (direct.task(judged, CouncilTask.SETTLE, active), {"elapsed_ms": 11}, direct.bundle),
        (direct.task(judged, CouncilTask.SETTLE, paused), {"elapsed_ms": 11},
         direct.tenant_store(selected, paused)),
    ), opening))
    recorded = write_batches(batches)
    for bundle in bundles:
        outgoing = root / "outgoing" / bundle.name.removeprefix("council-metrics-")
        if bundle.runner.phase is not performance.Phase.JUDGE:
            outgoing = bundle.runner.bundle
        else:
            outgoing = outgoing.with_name("shard-" + outgoing.name)
        if outgoing.is_dir():
            shutil.copytree(outgoing, collector / "incoming" / bundle.name)
    monkeypatch.setattr(session, "COUNCIL_ROOT", collector)

    matrix = json.dumps([cell.model_dump(mode="json") for cell in cells])
    # A correct receipt and wrong actual bytes must still refuse the whole publication.
    first = recorded[0]
    imported = collector / "incoming" / bundles[0].name / first.path
    imported.write_bytes(first.data + b"foreign bytes")
    unchanged = git(origin, "rev-parse", "main")
    publish = partial(
        settle_and_publish, repo=repo, run_id=selected.run_id, commit_sha=revision,
        config_root=target, selection=selected, matrix=matrix, opening_attempted=True,
    )
    assert publish() == 1
    assert git(origin, "rev-parse", "main") == unchanged
    imported.write_bytes(first.data)
    bound_receipt = collector / "incoming" / bundles[0].name / bundles[0].tasks[0].receipt
    original = bound_receipt.read_text(encoding="utf-8")
    received = json.loads(original)
    received["identity"]["producer"] = "not-the-native-writer"
    bound_receipt.write_text(json.dumps(received), encoding="utf-8")
    assert publish() == 1
    assert git(origin, "rev-parse", "main") == unchanged
    bound_receipt.write_text(original, encoding="utf-8")
    assert publish() == int(missing)

    remote = Repository(origin, git_dir=origin)
    expected_runners = 6 if missing else 8
    assert sum(allowed for _, allowed in captures) == expected_runners
    assert len({item.envelope.unit_id for item, _ in captures}) == len(captures)
    judge = next(
        proof.row for proof in recorded
        if isinstance(proof.row, TaskPerformanceRow)
        and proof.row.task_name == f"judge-{active}" and proof.row.shard == 0
    )
    serving = next(
        proof.row for proof in recorded
        if isinstance(proof.row, TaskPerformanceRow) and proof.row.task_name == f"serve-{active}"
    )
    assert (judge.task_kind, judge.subject_id) == ("judge", active)
    assert serving.host_unit_id == judge.host_unit_id
    assert (serving.server_prompt_tokens, serving.server_prompt_seconds) == (13, 2)
    for proof, allowed in [
        *captures, *((proof, "paused" not in proof.envelope.identity.task_key) for proof in recorded),
    ]:
        entry = remote.entry("main", proof.path)
        if allowed:
            assert entry is not None and remote.blob(entry.oid) == proof.data
        else:
            assert entry is None
    settled = load_current_rows(
        repo / "state", LedgerName.HOST_FINGERPRINT, model=HostFingerprintRow,
        key=HOST_FINGERPRINT_KEY, days={judged, "2026-10-10"},
    )
    assert len(settled) == expected_runners
    assert {(row.job, row.task_name, row.shard) for row in settled} == {
        (proof.row.job, proof.row.task_name, proof.row.shard)
        for proof, allowed in captures if allowed and isinstance(proof.row, HostHardwareRow)
    }
    assert ledger.load_days(repo / "state", LedgerName.COUNCIL_RUN_RECORDS, [judged], model=CouncilRunRecord)
    if missing:
        assert all(proof.envelope.identity.shard not in (3, 4) for proof in recorded)
