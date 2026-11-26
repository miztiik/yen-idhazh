"""How does the council's one collecting job publish every tenant's completed outputs?"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from contextlib import nullcontext
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import completed_writes, config, event_lines, run_context
from idhazh.contracts.council_events import CouncilExit, CouncilProgram, NightPublished
from idhazh.contracts.council_invocation import Cell, ShardReport
from idhazh.contracts.knobs.council import CouncilConfig, CouncilTask
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import (
    event_log,
    outcome,
    performance,
    run_identity,
    run_summary,
    session,
    work_files,
)
from idhazh.council.night_plan import a_date
from idhazh.council.registry import tenants
from idhazh.council.selection import Selection, from_environment
from idhazh.council.tenancy import Tenant
from idhazh.ledger.staging import staged_path
from idhazh.telemetry import machine_api, machine_evidence, task_telemetry
from idhazh.telemetry.host_control import enabled as telemetry_enabled
from utilities import council_machine_delivery
from utilities.council_matrix import VENUE_LEDGERS
from utilities.publication_evidence import identified
from utilities.publication_git import Repository
from utilities.publication_inputs import materialize
from utilities.publication_request import IntegrityError, PublicationRequest, Write, contains
from utilities.publish_to_repo import PublicationResult, Status, publish
from utilities.push_retry import DEFAULT_CONFIG, load_retry


def settle_and_publish(
    *,
    repo: Path,
    dates: tuple[str, ...] = (),
    run_id: str,
    commit_sha: str,
    config_root: Path,
    started_at: datetime | None = None,
    clock: Callable[[], datetime] = task_telemetry.utc_now,
    units_failed: bool = False,
    selection: Selection,
    matrix: str | None = None,
    report: run_summary.Report | None = None,
    opening_attempted: bool = False,
) -> int:
    dates = tuple(a_date(date, what="--date") for date in dates)
    run_identity.opened_on(run_id)
    settings = config.load(config_root)
    selected = selection.check(settings.council).identify(
        run_id=run_id,
        attempt=run_context.run_attempt(),
        git_sha=commit_sha,
    )
    if dates and dates != selection.dates:
        raise SystemExit(CouncilExit.REFUSED)
    dates = selection.dates
    active = selected.names(publish=True)
    instrumented = telemetry_enabled(settings.app.observability)
    warn_opening = (
        opening_attempted and instrumented and settings.app.observability.host_fingerprint
    )
    try:
        received = _import_work(
            selected, matrix, settings.council, admit_readings=instrumented,
            expect_opening=warn_opening,
        )
    except (OSError, ValueError) as error:
        event_log.failed(error)
        event_log.emit(
            NightPublished(
                dates=dates,
                run_id=run_id,
                landing="integrity-refused",
                pushes=0,
                writes=0,
                code=CouncilExit.FAILED,
            )
        )
        return CouncilExit.FAILED
    if report is not None:
        report.load(matrix or "[]", session.COUNCIL_ROOT / "events", run_id, selection=selected)
        units_failed = report.failed or units_failed
    dispatched = None if matrix is None else run_summary.cells(matrix)
    task_failed = units_failed

    def reports(name: str, day: str, width: int) -> tuple[ShardReport, ...]:
        nonlocal task_failed
        admitted = {
            (cell.tenant, cell.date, cell.shard)
            for cell in (() if dispatched is None else dispatched)
        }
        normalized = tuple(
            run_summary.reported(
                Cell(tenant=name, date=day, shard=part, shards=width, runs_model=False),
                session.COUNCIL_ROOT / "events",
                run_id,
            ).normalized(dispatched=dispatched is None or (name, day, part) in admitted)
            for part in range(width)
        )
        checked = tuple(
            ShardReport(shard=item.shard, shards=item.shards, report_state="invalid")
            if item.report_state == "reported"
            and not work_files.shard_path(
                session.COUNCIL_ROOT,
                selected,
                name,
                day,
                item.shard,
            ).is_file()
            else item
            for item in normalized
        )
        task_failed = task_failed or any(
            item.report_state != "reported"
            or item.code != CouncilExit.OK
            or item.outcome in ("failed", "stopped_on_deadline")
            for item in checked
        )
        return checked

    hosted = tenants(
        selected.names(),
        app=settings.app,
        council=settings.council,
        trials=selected.trials,
    )
    if warn_opening and not active:
        machine_api.warn("Council evidence stays in artifacts: no active selection")
    if not hosted:
        code = CouncilExit.FAILED if units_failed else CouncilExit.OK
        event_log.emit(
            NightPublished(
                dates=dates, run_id=run_id, landing="no-changes", pushes=0, writes=0, code=code
            )
        )
        return code
    git = Repository(repo)
    source = git.git("rev-parse", "HEAD").strip()
    permissions = tuple(
        dict.fromkeys(
            (
                *VENUE_LEDGERS,
                *(council_machine_delivery.scopes(selected) if active else ()),
                *(
                    path
                    for host in hosted
                    if not selected.trial(host.judge_id)
                    for path in host.committed_paths
                ),
            )
        )
    )
    writes: dict[str, Write] = {}
    integrity_failed: IntegrityError | None = None
    identity = session._identify_writer(run_id=run_id, commit_sha=commit_sha)
    settlement = performance.selected_runner(
        session.COUNCIL_ROOT, performance.Phase.SETTLE, selected,
    )
    opening = None

    def include_machine(proof: machine_evidence.VerifiedFile) -> None:
        path = proof.path
        if path in writes or not any(contains(scope, path) for scope in permissions):
            raise IntegrityError("Council measurement exceeds or overlaps its scope", (path,))
        proof.place(repo)
        writes[path] = Write(proof.sha256, git.entry(source, path), True)

    def completed(host: Tenant | None, evidence: dict[Path, str]) -> None:
        nonlocal integrity_failed
        allowed = VENUE_LEDGERS if host is None else host.committed_paths
        confirmed: dict[str, str] = {}
        for target, digest in evidence.items():
            path = target.relative_to(repo).as_posix()
            if path.startswith("backend/var/"):
                continue
            if contains(staged_path(machine_evidence.TASK), path) or not any(
                contains(scope, path) for scope in allowed
            ):
                integrity_failed = IntegrityError(
                    "tenant output exceeds its own declaration", (path,)
                )
                raise work_files.FileIntegrityError("tenant output exceeds declaration")
            confirmed[path] = digest
            writes[path] = Write(digest, git.entry(source, path), path.startswith("state/raw/"))
        # A receipt is a bounded invocation file, never a new commit ledger.
        receipt = PublicationReceipt(
            version=PublicationReceipt.schema_version(), identity=identity, writes=confirmed
        )
        try:
            identified(repo, identity, confirmed)
        except IntegrityError as error:
            integrity_failed = error
            raise work_files.FileIntegrityError("completed output integrity failed") from error
        target = repo / "backend" / "var" / "council" / "publication" / (f"{len(receipts):04}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(receipt.to_json(), encoding="utf-8", newline="\n")
        receipts.append(target)

    receipts: list[Path] = []

    def prepare_inputs(host: Tenant, *, date: str) -> None:
        nonlocal integrity_failed
        trial = session._trial_root(selected, host.judge_id, run_id)
        try:
            materialize(
                git,
                source,
                tuple(
                    path
                    for path in host.publication_inputs(date=date)
                    if trial is not None or path not in writes
                ),
                repo if trial is None else trial,
                preserve_existing=True,
            )
        except IntegrityError as error:
            if trial is None:
                integrity_failed = error
                raise work_files.FileIntegrityError("settlement input integrity failed") from error
            raise

    if active and instrumented:
        try:
            for proof in received:
                include_machine(proof)
            # The legacy clock still reads the one opening written by its own writer.
            opening = machine_evidence.read_receipt(settlement.bundle, settlement.opening)
            if opening is not None:
                include_machine(opening)
            elif warn_opening:
                machine_api.warn("Council settlement opening fingerprint not delivered")
        except (OSError, ValueError) as error:
            event_log.failed(error)
            event_log.emit(NightPublished(
                dates=dates, run_id=run_id, landing="integrity-refused",
                pushes=0, writes=0, code=CouncilExit.FAILED,
            ))
            return CouncilExit.FAILED

    machine_paths: list[Path] = []
    with completed_writes.collect() as legacy_evidence:
        machine = (
            task_telemetry.record(
                date=run_identity.opened_on(run_id),
                run_id=run_id,
                settings=settings,
                state_root=repo / "state",
                commit_sha=commit_sha,
                job=identity.job,
                attempt=identity.attempt,
                started_at=started_at,
                clock=clock,
                capture_opening=not opening_attempted and opening is None,
            )
            if active
            else nullcontext(machine_paths)
        )
        with machine as machine_paths:
            for date in dates:
                try:
                    results = session.settle(
                        settings.council,
                        date=date,
                        run_id=run_id,
                        state_dir=repo / "state",
                        commit_sha=commit_sha,
                        completed=completed,
                        selection=selected,
                        prepare_inputs=partial(prepare_inputs, date=date),
                        reports=reports,
                    )
                    task_failed = bool(outcome.of_results(results)) or task_failed
                except Exception as error:
                    if work_files.fatal(error):
                        if work_files.integrity_failure(error):
                            integrity_failed = IntegrityError("council file integrity failed")
                            task_failed = True
                            event_log.failed(error)
                            break
                        raise
                    task_failed = True
                    event_log.failed(error)
    if active:
        try:
            for judge in selected.judges if instrumented else ():
                if selected.trial(judge.tenant):
                    continue
                for day in judge.dates:
                    expected = settlement.task(day, CouncilTask.SETTLE, judge.tenant)
                    proof = machine_evidence.read_receipt(settlement.bundle, expected)
                    if proof is not None:
                        machine_evidence.verify_host_link(proof, opening)
                        include_machine(proof)
            machine_completed = dict(legacy_evidence)
            for path in machine_paths:
                if path not in machine_completed:
                    relative = path.relative_to(repo).as_posix()
                    raise IntegrityError("machine output has no completed evidence", (relative,))
            completed(None, {path: machine_completed[path] for path in machine_paths})
        except (ValueError, OSError) as error:
            integrity_failed = (
                error if isinstance(error, IntegrityError) else IntegrityError(str(error))
            )
    else:
        code = CouncilExit.FAILED if task_failed else CouncilExit.OK
        event_log.emit(
            NightPublished(
                dates=dates, run_id=run_id, landing="no-changes", pushes=0, writes=0, code=code
            )
        )
        return code
    if integrity_failed is not None:
        event_log.failed(integrity_failed)
        event_log.emit(
            NightPublished(
                dates=dates,
                run_id=run_id,
                landing="integrity-refused",
                pushes=0,
                writes=len(writes),
                code=CouncilExit.FAILED,
            )
        )
        return CouncilExit.FAILED
    request = PublicationRequest(
        identity,
        "council: " + " ".join(dates),
        source,
        permissions,
        (),
        writes,
    )
    result = publish(request, repo=repo, retry=load_retry(repo / DEFAULT_CONFIG))
    code = outcome.worst((_publication_code(result), int(task_failed)))
    event_log.emit(
        NightPublished(
            dates=dates,
            run_id=run_id,
            landing=result.status.value,
            pushes=result.push_count,
            writes=len(writes),
            code=code,
        )
    )
    return code


def _publication_code(result: PublicationResult) -> CouncilExit:
    """Keep rejection distinct from lost/stale work without using the publisher's prose."""
    if result.status is Status.REFUSED and result.push_count > 0:
        return CouncilExit.PUSH_REFUSED
    if result.status in (Status.LANDED, Status.ALREADY_ON_MAIN, Status.NO_CHANGES):
        return CouncilExit.OK
    return CouncilExit.FAILED


def _import_work(
    selected: Selection, matrix: str | None, council: CouncilConfig, *,
    admit_readings: bool, expect_opening: bool,
) -> tuple[machine_evidence.VerifiedFile, ...]:
    """Admit only named planner and dispatched worker bundles, never merge trees."""
    root = session.COUNCIL_ROOT
    incoming = root / "incoming"
    cells = () if matrix is None else run_summary.cells(matrix)
    for cell in cells:
        judge = selected.judge(cell.tenant, cell.date)
        if cell.shards != judge.shards:
            raise work_files.FileIntegrityError("matrix width differs from selected cell")
        if cell.runs_model != council.declaration(cell.tenant).runs_model:
            raise work_files.FileIntegrityError("matrix model selection differs from declaration")
    bundles = council_machine_delivery.incoming(root, selected, cells)
    downloads = work_files.downloaded_bundles(
        incoming, selected, cells,
        extra_markers={bundle.name: bundle.markers() for bundle in bundles},
    )
    readings = (
        tuple(
            proof for bundle in bundles if not bundle.runner.trial
            for proof in bundle.readings(downloads, expect_opening=expect_opening)
        )
        if admit_readings and selected.names(publish=True) else ()
    )
    planner = downloads.get(f"council-selection-{selected.anchor_date}")
    if planner is not None:
        for judge in selected.judges:
            for day in judge.dates:
                work_files.import_preparation(root, planner, selected, judge.tenant, day)
        work_files.copy_events(root, planner, "planner.jsonl")
    for cell in cells:
        prepared = work_files.read_preparation(root, selected, cell.tenant, cell.date)
        if prepared is None or prepared.state != "ready":
            raise work_files.FileIntegrityError("matrix cell has no ready receipt")
        bundle = downloads.get(f"council-metrics-{cell.tenant}-{cell.date}-{cell.shard}")
        if bundle is not None:
            arrived = work_files.import_shard(
                root,
                bundle,
                selected,
                cell.tenant,
                cell.date,
                cell.shard,
            )
            if arrived is None:
                work_files.copy_record(
                    root,
                    bundle,
                    selected,
                    cell.tenant,
                    cell.date,
                    cell.shard,
                )
            work_files.copy_events(
                root,
                bundle,
                f"{cell.tenant}/{cell.date}/{cell.shard}.jsonl",
            )
    return readings


def main(argv: list[str] | None = None) -> int:
    event_lines.install_crash_printer()
    previous = os.environ.get("GIT_NO_LAZY_FETCH")
    os.environ["GIT_NO_LAZY_FETCH"] = "1"
    try:
        report = run_summary.Report()
        with event_log.capture() as events:
            code = outcome.run(CouncilProgram.PUBLISH, lambda: _main(argv, report=report))
        report.events = events
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            report.write(Path(summary))
        return code
    finally:
        if previous is None:
            os.environ.pop("GIT_NO_LAZY_FETCH", None)
        else:
            os.environ["GIT_NO_LAZY_FETCH"] = previous


def _main(argv: list[str] | None = None, *, report: run_summary.Report | None = None) -> int:
    parser = outcome.Parser(description=__doc__)
    parser.add_argument("--date", action="append", default=[])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--job-started-at", type=int)
    parser.add_argument("--opening-attempted", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--matrix", help="The planner's JSON list of expected judging jobs.")
    parser.add_argument(
        "--planning-result",
        choices=("success", "failure", "cancelled", "skipped"),
        default="success",
    )
    parser.add_argument(
        "--units-result", choices=("success", "failure", "cancelled", "skipped"), default="success"
    )
    args = parser.parse_args(argv)
    selected = from_environment(config.load_council(args.config_root))
    if args.planning_result == "cancelled" or args.units_result == "cancelled":
        raise SystemExit(CouncilExit.FAILED)
    return settle_and_publish(
        repo=args.repo_root,
        dates=tuple(args.date),
        run_id=args.run_id,
        commit_sha=args.commit,
        config_root=args.config_root,
        selection=selected,
        matrix=args.matrix,
        report=report,
        opening_attempted=args.opening_attempted,
        started_at=datetime.fromtimestamp(args.job_started_at, UTC)
        if args.job_started_at is not None
        else None,
        units_failed=args.units_result in ("failure", "cancelled")
        or args.planning_result in ("failure", "cancelled", "skipped")
        or (report is not None and report.failed),
    )


if __name__ == "__main__":
    raise SystemExit(main())
