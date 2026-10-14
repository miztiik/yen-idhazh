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

from idhazh import completed_writes, config, event_lines
from idhazh.contracts.council_events import CouncilExit, CouncilProgram, NightPublished
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import event_log, outcome, run_identity, run_summary, session
from idhazh.council.night_plan import a_date
from idhazh.council.registry import tenants
from idhazh.council.selection import Selection, for_dates, from_environment
from idhazh.council.tenancy import Tenant
from idhazh.telemetry import task_telemetry
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
    selection: Selection | None = None,
) -> int:
    dates = tuple(a_date(date, what="--date") for date in dates)
    run_identity.opened_on(run_id)
    settings = config.load(config_root)
    selected = (
        for_dates(settings.council, dates)
        if selection is None
        else selection.check(settings.council)
    )
    if selection is not None:
        if dates and dates != selection.dates:
            raise SystemExit(CouncilExit.REFUSED)
        dates = selection.dates
    hosted = tenants(
        selected.names(),
        app=settings.app,
        council=settings.council,
        trials=selected.trials,
    )
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
    sparse = (
        git.git("config", "--get", "core.sparseCheckout").strip() == "true"
        if git.run("config", "--get", "core.sparseCheckout").returncode == 0
        else False
    )
    permissions = tuple(
        dict.fromkeys(
            (
                *VENUE_LEDGERS,
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
    task_failed = units_failed
    integrity_failed: IntegrityError | None = None
    identity = session._identify_writer(run_id=run_id, commit_sha=commit_sha)

    def completed(host: Tenant | None, evidence: dict[Path, str]) -> None:
        nonlocal integrity_failed
        allowed = VENUE_LEDGERS if host is None else host.committed_paths
        confirmed: dict[str, str] = {}
        for target, digest in evidence.items():
            path = target.relative_to(repo).as_posix()
            if path.startswith("backend/var/"):
                continue
            if not any(contains(scope, path) for scope in allowed):
                integrity_failed = IntegrityError(
                    "tenant output exceeds its own declaration", (path,)
                )
                raise integrity_failed
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
            raise
        target = repo / "backend" / "var" / "council" / "publication" / (f"{len(receipts):04}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(receipt.to_json(), encoding="utf-8", newline="\n")
        receipts.append(target)

    receipts: list[Path] = []

    def prepare_inputs(host: Tenant, *, date: str) -> None:
        nonlocal integrity_failed
        trial = session._trial_root(selected, host.judge_id, run_id)
        inputs = getattr(host, "publication_inputs", None)
        try:
            if inputs is None:
                if sparse:
                    raise IntegrityError(
                        "sparse tenant has no declared input paths", (host.judge_id,)
                    )
            else:
                materialize(
                    git,
                    source,
                    tuple(
                        path
                        for path in inputs(date=date)
                        if trial is not None or path not in writes
                    ),
                    repo if trial is None else trial,
                    preserve_existing=True,
                )
        except IntegrityError as error:
            if trial is None:
                integrity_failed = error
            raise

    active = selected.names(publish=True)
    machine_paths: list[Path] = []
    with completed_writes.collect() as machine_evidence:
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
            )
            if active
            else nullcontext(machine_paths)
        )
        with machine as machine_paths:
            for date in dates:
                try:
                    if sparse:
                        for host in hosted:
                            if host.judge_id in selected.names(date=date, publish=True) and (
                                getattr(host, "publication_inputs", None) is None
                            ):
                                integrity_failed = IntegrityError(
                                    "sparse tenant has no declared input paths", (host.judge_id,)
                                )
                                raise integrity_failed
                    results = session.settle(
                        settings.council,
                        date=date,
                        run_id=run_id,
                        state_dir=repo / "state",
                        commit_sha=commit_sha,
                        completed=completed,
                        selection=selected,
                        prepare_inputs=partial(prepare_inputs, date=date),
                    )
                    task_failed = bool(outcome.of_results(results)) or task_failed
                except Exception as error:
                    task_failed = True
                    event_log.failed(error)
    if active:
        try:
            machine_completed = dict(machine_evidence)
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
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--matrix", help="The planner's JSON list of expected judging jobs.")
    parser.add_argument(
        "--units-result", choices=("success", "failure", "cancelled", "skipped"), default="success"
    )
    args = parser.parse_args(argv)
    selected = from_environment(config.load_council(args.config_root))
    if selected is None and not args.date:
        raise SystemExit(CouncilExit.REFUSED)
    if report is not None and args.matrix is not None:
        report.load(
            args.matrix,
            args.repo_root / "backend" / "var" / "council" / "events",
            args.run_id,
        )
    return settle_and_publish(
        repo=args.repo_root,
        dates=tuple(args.date),
        run_id=args.run_id,
        commit_sha=args.commit,
        config_root=args.config_root,
        selection=selected,
        started_at=datetime.fromtimestamp(args.job_started_at, UTC)
        if args.job_started_at is not None
        else None,
        units_failed=args.units_result in ("failure", "cancelled")
        or (report is not None and report.failed),
    )


if __name__ == "__main__":
    raise SystemExit(main())
