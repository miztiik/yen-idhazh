"""What does the council do with the tenants it is hosting tonight?

Three units of work, in the order a night runs them: pick the work, run one
shard of it, and settle what came back. Each one resolves the slugs the config
names and calls the matching member on every tenant it got.

**The council owns the invocation, so it owns the outcome.** It starts the
clock, calls the tenant, and files its own row on the way out - so the venue's
record of a unit exists whether or not the tenant remembered to write anything
of its own. The cost cells on that row come off what the tenant handed back and
none of them is read out of a tenant's ledger.

Nothing here reads a result by name beyond those. What a tenant hands back
crosses whole, so a venue hosting a judge with a funnel and a judge with none
runs the same code for both.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Final

from idhazh import completed_writes, config, ledger, run_context
from idhazh.contracts.base import DateStamp, RunId, ServerJob
from idhazh.contracts.council_events import NightPlanned, RowsCollected, UnitFinished
from idhazh.contracts.council_invocation import (
    ArtifactFile,
    PreparationReceipt,
    ShardFiles,
    ShardReport,
)
from idhazh.contracts.council_run_record import (
    CouncilRunRecord,
    EvaluationStep,
    ShardOutcome,
)
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.council import event_log, metrics_sink, outcome, trial_paths, work_files
from idhazh.council.deadline import run_shard_under_the_clock
from idhazh.council.registry import VENUE_LEDGERS as VENUE_LEDGERS
from idhazh.council.registry import tenant, tenants
from idhazh.council.selection import Selection
from idhazh.council.tenancy import ShardResult, Tenant
from idhazh.ledger import lifecycle, staging

#: Where one night's work lands before a later job collects it. The council
#: names the root because the council is what carries it between jobs as an
#: artifact; what a tenant puts inside it is the tenant's own business.
COUNCIL_ROOT_RELPATH: Final = "backend/var/council"

COUNCIL_ROOT: Final = config.REPO_ROOT / COUNCIL_ROOT_RELPATH

#: The three slots the venue names inside the root it carries: what a date's
#: work was picked from, what the units measured on their way out, and the
#: venue's own record of how each of those units ended. A tenant may name a slot
#: of its own beside them - what the venue guarantees is the carrying, not the
#: list of names.
SELECTION_DIRNAME: Final = "selection"

METRICS_DIRNAME: Final = "metrics"

OUTCOMES_DIRNAME: Final = "outcomes"

#: How a recorded instant is spelled. The contract pins the shape, and this is
#: the one place a council row is stamped with it.
STARTED_AT_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"
_ROOT: ContextVar[Path | None] = ContextVar("council_invocation_root", default=None)


def invocation_root(selection: Selection, judge_id: str) -> Path:
    return work_files.invocation_root(COUNCIL_ROOT, selection, judge_id)


def artifact_path(path: Path) -> str:
    root = _ROOT.get()
    if root is None:
        raise work_files.FileIntegrityError("file declaration requires an invocation")
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise work_files.FileIntegrityError("file exceeds invocation root") from error


@contextmanager
def _route(selection: Selection, judge_id: str) -> Iterator[None]:
    root = invocation_root(selection, judge_id)
    token = _ROOT.set(root)
    try:
        with trial_paths.route(root if selection.trial(judge_id) else None):
            yield
    finally:
        _ROOT.reset(token)


def publication_paths(
    council: CouncilConfig, *, selection: Selection | None = None
) -> tuple[str, ...]:
    """The venue's and hosted tenants' declarations, never a blanket state claim."""
    names = council.running() if selection is None else selection.check(council).names(publish=True)
    hosted = tenants(names, council=council)
    if not hosted:
        return ()
    if any(
        path in ("state", "state/raw", "state/compact")
        for host in hosted
        for path in host.committed_paths
    ):
        raise ValueError("a tenant must declare its own paths, not a blanket state root")
    return tuple(
        dict.fromkeys(
            [
                *(staging.staged_path(which) for which in VENUE_LEDGERS),
                *(path for host in hosted for path in host.committed_paths),
            ]
        )
    )


def scratch_root(date: DateStamp) -> Path:
    """The directory one date's work is written under, on whichever runner runs it."""
    return trial_paths.scratch(_ROOT.get() or COUNCIL_ROOT) / date


def outcomes_dir(date: DateStamp) -> Path:
    """Where one date's council rows wait for the job that commits them.

    Beside the tenants' own uploads rather than inside one of them. The venue's
    record of a unit has to survive a tenant that wrote nothing, so it cannot
    live under a directory a tenant owns.
    """
    return scratch_root(date) / OUTCOMES_DIRNAME


def unit_dir(date: DateStamp, *, slot: str, judge_id: str) -> Path:
    """The one directory a tenant's files for a later job sit in.

    Under the root the council carries, because a path outside it reaches no
    other job at all: the runner that wrote it is thrown away when its job ends.
    The slug is a directory level for the reason `metrics_sink` makes it one - a
    reader lists a directory holding one tenant's files and can never take a
    second tenant's for its own.
    """
    return scratch_root(date) / slot / metrics_sink.checked_slug(judge_id)


def unit_file(
    date: DateStamp,
    *,
    slot: str,
    judge_id: str,
    shard: int | None = None,
    suffix: str = ".csv",
) -> Path:
    """What one unit calls the file it leaves inside that directory.

    `ledger.segment_name`'s grammar carrying the council's own identity: the
    elements hyphen-joined, the shard last and two digits wide, so the name says
    which date, which tenant and which unit wrote it wherever the file is read.
    Spelled here rather than taken from that helper, which asks for a run attempt
    the council never reads and a `ServerJob` none of this workflow's jobs is a
    member of - a name carrying an invented cell names nothing.

    Eight units of one date write eight names, so nothing they do concurrently
    can land on one path.

    **`shard` is None for the unit that picks the work.** A date has one draw and
    every unit of that date reads it, so a number there would claim a writer that
    never existed.
    """
    unit = "" if shard is None else f"-{shard:02d}"
    name = f"{date}-{metrics_sink.checked_slug(judge_id)}{unit}{suffix}"
    return unit_dir(date, slot=slot, judge_id=judge_id) / name


def shard_width(council: CouncilConfig, host: Tenant) -> int:
    """How many ways one tenant's work splits tonight.

    The tenant's own answer, narrowed by what the venue is willing to fan out
    to. Named here rather than computed twice: the matrix builds the cells from
    it and the two units that run once a date record it, so a second spelling
    would let a night's rows disagree with the night's own shape.
    """
    return min(host.shard_count, council.shards)


def prepare(
    council: CouncilConfig,
    *,
    date: DateStamp | None = None,
    run_id: RunId,
    selection: Selection,
) -> tuple[ShardResult, ...]:
    """Pick the work, once a date, before any shard runs.

    In the order the config names the tenants, because a venue that ran them in
    an order it never declared could not be re-run into the same state.
    """
    selected = selection.check(council)
    selected.identify(run_id=run_id, attempt=run_context.run_attempt(), git_sha=selected.git_sha)
    if date is not None and date not in selected.dates:
        raise ValueError("preparation date is not selected")
    # Resolve every declaration before the first plugin does work.
    hosted = tenants(selected.names(), council=council, trials=selected.trials)
    _check_widths(council, selected, hosted)
    results: list[ShardResult] = []
    for host in hosted:
        own = next(judge for judge in selected.judges if judge.tenant == host.judge_id)
        for day in own.dates:
            if date is not None and day != date:
                continue
            with _route(selected, host.judge_id):
                admitted: tuple[ArtifactFile, ...] = ()

                def work(
                    host: Tenant = host,
                    day: str = day,
                    width: int = own.shards,
                ) -> ShardResult:
                    nonlocal admitted
                    result = host.prepare(date=day, run_id=run_id, shards=width)
                    if result.outcome not in (ShardOutcome.COMPLETED, ShardOutcome.NOTHING_TO_DO):
                        raise ValueError("preparation must complete, decline or raise")
                    admitted = work_files.evidence(
                        invocation_root(selected, host.judge_id),
                        result.files,
                        day=day,
                        judge_id=host.judge_id,
                    )
                    if result.outcome is ShardOutcome.COMPLETED and not admitted:
                        raise work_files.FileIntegrityError("ready preparation has no task file")
                    return result

                try:
                    result = _recorded(
                        host.judge_id,
                        date=day,
                        run_id=run_id,
                        evaluation_step=EvaluationStep.SELECT_JUDGE_WORK,
                        work_part_index=None,
                        work_part_count=own.shards,
                        work=work,
                    )
                except BaseException as error:
                    if work_files.fatal(error):
                        raise
                    error_name, where = event_log.cause_of(error)
                    receipt = PreparationReceipt(
                        version=PreparationReceipt.schema_version(),
                        run_id=run_id,
                        attempt=selected.attempt,
                        git_sha=selected.git_sha,
                        judge_id=host.judge_id,
                        date=day,
                        state="failed",
                        shards=0,
                        files=(),
                        error=error_name,
                        where=where,
                    )
                    result = ShardResult(outcome=ShardOutcome.FAILED)
                else:
                    ready = result.outcome is ShardOutcome.COMPLETED
                    receipt = PreparationReceipt(
                        version=PreparationReceipt.schema_version(),
                        run_id=run_id,
                        attempt=selected.attempt,
                        git_sha=selected.git_sha,
                        judge_id=host.judge_id,
                        date=day,
                        state="ready" if ready else "no_work",
                        shards=own.shards if ready else 0,
                        files=admitted,
                    )
                work_files.write_document(
                    work_files.preparation_path(COUNCIL_ROOT, selected, host.judge_id, day),
                    receipt,
                )
                work_files.export(
                    COUNCIL_ROOT, COUNCIL_ROOT / "outgoing" / "planner", selected, receipt
                )
                _export_record(selected, host.judge_id, day, "select-judge-work", "planner")
                results.append(result)
    print("preparation_finished=true")
    return tuple(results)


def _check_widths(council: CouncilConfig, selected: Selection, hosted: Sequence[Tenant]) -> None:
    for host, judge in zip(hosted, selected.judges, strict=True):
        if host.judge_id != judge.tenant or shard_width(council, host) != judge.shards:
            raise ValueError("selected width differs from the plugin declaration")


def _export_record(selected: Selection, name: str, day: str, unit: str, bundle: str) -> None:
    import shutil

    source = outcomes_dir(day) / name / f"{unit}.csv"
    target = COUNCIL_ROOT / "outgoing" / bundle / source.relative_to(COUNCIL_ROOT)
    work_files.check_destination(target)
    work_files.checked_file(COUNCIL_ROOT, source.relative_to(COUNCIL_ROOT).as_posix())
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def settle(
    council: CouncilConfig,
    *,
    date: DateStamp,
    run_id: RunId,
    state_dir: Path,
    commit_sha: str,
    completed: Callable[[Tenant | None, dict[Path, str]], None] | None = None,
    selection: Selection,
    prepare_inputs: Callable[[Tenant], None] | None = None,
    reports: Callable[[str, str, int], tuple[ShardReport, ...]] | None = None,
) -> tuple[ShardResult, ...]:
    """Count, fit, or do nothing, once a date after every shard has reported.

    Then collect the night's own rows into the council's ledger, which is the one
    place in the night that writes under `state/`. The collect runs on the way
    out whatever the tenants did, so a tenant that died still leaves the venue
    holding the record of every unit that reported before it.

    Every tenant is handed the state root and the writer identity the council
    files its own rows under, so a tenant's files and the venue's name one run,
    one attempt and one commit.
    """
    selection.check(council).identify(
        run_id=run_id,
        attempt=run_context.run_attempt(),
        git_sha=commit_sha,
    )
    identity = _identify_writer(run_id=run_id, commit_sha=commit_sha)
    hosted = _hosted(council, date, selection)
    _check_widths(
        council,
        selection.model_copy(
            update={"judges": tuple(judge for judge in selection.judges if date in judge.dates)}
        ),
        hosted,
    )
    active = tuple(host for host in hosted if _trial_root(selection, host.judge_id, run_id) is None)
    results: list[ShardResult] = []
    failures: list[Exception] = []
    for host in hosted:
        trial = _trial_root(selection, host.judge_id, run_id)
        trial_writes = (
            nullcontext()
            if trial is None
            else lifecycle.isolated_trial(trial / "state", identity=identity)
        )
        with _route(selection, host.judge_id), trial_writes, completed_writes.collect() as evidence:
            try:
                prepared = work_files.read_preparation(COUNCIL_ROOT, selection, host.judge_id, date)
                if prepared is None or prepared.state == "failed":
                    raise ValueError("preparation failed or was not reported")
                for part in range(prepared.shards):
                    work_files.read_shard(COUNCIL_ROOT, selection, host.judge_id, date, part)
                if prepare_inputs is not None:
                    prepare_inputs(host)
                normalized = (
                    reports(host.judge_id, date, prepared.shards)
                    if reports is not None
                    else _reports(selection, host.judge_id, date, prepared.shards)
                )
                results.append(
                    _recorded(
                        host.judge_id,
                        date=date,
                        run_id=run_id,
                        evaluation_step=EvaluationStep.COMBINE_JUDGE_RESULTS,
                        work_part_index=None,
                        work_part_count=prepared.shards,
                        work=partial(
                            host.settle,
                            date=date,
                            run_id=run_id,
                            state_dir=state_dir if trial is None else trial / "state",
                            identity=identity,
                            prepared=prepared,
                            reports=normalized,
                        ),
                    )
                )
            except Exception as error:
                if work_files.fatal(error):
                    raise
                failures.append(error)
            finally:
                if completed is not None and trial is None:
                    try:
                        completed(host, evidence)
                    except Exception as error:
                        if work_files.fatal(error):
                            raise
                        failures.append(error)
            if trial is not None:
                try:
                    _collect((host,), date=date, state_dir=trial / "state", identity=identity)
                except Exception as error:
                    if work_files.fatal(error):
                        raise
                    failures.append(error)
    with completed_writes.collect() as evidence:
        try:
            if active:
                with _route(selection, active[0].judge_id):
                    _collect(active, date=date, state_dir=state_dir, identity=identity)
        except Exception as error:
            if work_files.fatal(error):
                raise
            failures.append(error)
        finally:
            if completed is not None and active:
                try:
                    completed(None, evidence)
                except Exception as error:
                    if work_files.fatal(error):
                        raise
                    failures.append(error)
    if failures:
        if len(failures) == 1:
            raise failures[0]
        raise ExceptionGroup("council settlement failures", failures)
    return tuple(results)


def run_shard(
    council: CouncilConfig,
    *,
    slug: str,
    date: DateStamp,
    run_id: RunId,
    shard: int,
    shards: int,
    started: float,
    selection: Selection,
) -> ShardResult:
    """One shard of one tenant's work, stopped on the council's own clock.

    One slug rather than every hosted tenant: a cell of the matrix is one
    invocation, so two tenants sharing a job would each be handed the whole span
    the venue meant for one of them.
    """
    host, prepared = verify_work(
        council,
        slug=slug,
        date=date,
        run_id=run_id,
        shard=shard,
        shards=shards,
        selection=selection,
    )
    with _route(selection, slug):
        bundle = f"shard-{slug}-{date}-{shard}"
        try:
            result = _recorded(
                host.judge_id,
                date=date,
                run_id=run_id,
                evaluation_step=EvaluationStep.EVALUATE_WORK_PART,
                work_part_index=shard,
                work_part_count=shards,
                work=partial(
                    run_shard_under_the_clock,
                    host,
                    date=date,
                    run_id=run_id,
                    shard=shard,
                    shards=shards,
                    council=council,
                    started=started,
                    prepared=prepared,
                ),
            )
        finally:
            if work_files.record_path(COUNCIL_ROOT, selection, slug, date, shard).is_file():
                _export_record(selection, slug, date, str(shard), bundle)
        work_files.verify(
            invocation_root(selection, slug),
            prepared.files,
            day=date,
            judge_id=slug,
        )
        files = work_files.evidence(
            invocation_root(selection, slug),
            result.files,
            day=date,
            judge_id=slug,
        )
        if {file.path for file in files} & {file.path for file in prepared.files}:
            raise work_files.FileIntegrityError("shard cannot overwrite preparation")
        document = ShardFiles(
            version=ShardFiles.schema_version(),
            run_id=run_id,
            attempt=selection.attempt,
            git_sha=selection.git_sha,
            judge_id=slug,
            date=date,
            shard=shard,
            shards=shards,
            files=files,
        )
        work_files.write_document(
            work_files.shard_path(COUNCIL_ROOT, selection, slug, date, shard),
            document,
        )
        work_files.export(COUNCIL_ROOT, COUNCIL_ROOT / "outgoing" / bundle, selection, document)
        return result


def verify_work(
    council: CouncilConfig,
    *,
    slug: str,
    date: str,
    run_id: str,
    shard: int,
    shards: int,
    selection: Selection,
) -> tuple[Tenant, PreparationReceipt]:
    selection.check(council).identify(
        run_id=run_id,
        attempt=run_context.run_attempt(),
        git_sha=selection.git_sha,
    )
    judge = selection.judge(slug, date)
    host = tenant(slug, council=council, trial=selection.trial(slug))
    if shards != judge.shards or shards != shard_width(council, host) or not 0 <= shard < shards:
        raise ValueError("shard differs from selected width")
    receipt = work_files.read_preparation(COUNCIL_ROOT, selection, slug, date)
    if receipt is None or receipt.state != "ready" or receipt.shards != shards:
        raise work_files.FileIntegrityError("shard has no matching ready preparation")
    return host, receipt


def _reports(selection: Selection, name: str, day: str, width: int) -> tuple[ShardReport, ...]:
    from idhazh.contracts.council_invocation import Cell
    from idhazh.council.run_summary import reported

    return tuple(
        reported(
            Cell(tenant=name, date=day, shard=part, shards=width, runs_model=False),
            COUNCIL_ROOT / "events",
            selection.run_id,
        ).normalized()
        for part in range(width)
    )


def _trial_root(selection: Selection | None, name: str, run_id: RunId) -> Path | None:
    return (
        trial_paths.root(COUNCIL_ROOT, run_id=run_id, judge_id=name)
        if selection is not None and selection.trial(name)
        else None
    )


def _hosted(council: CouncilConfig, date: DateStamp, selection: Selection) -> tuple[Tenant, ...]:
    """The tenants this night hosts, said out loud so an empty night is readable."""
    names = selection.check(council).names(date=date)
    hosted = tenants(names, council=council, trials=selection.trials)
    if not hosted:
        event_log.emit(NightPlanned(dates=(date,), judges=0, units=0))
    return hosted


def _recorded(
    judge_id: str,
    *,
    date: DateStamp,
    run_id: RunId,
    evaluation_step: EvaluationStep,
    work_part_index: int | None,
    work_part_count: int,
    work: Callable[[], ShardResult],
) -> ShardResult:
    """Run one unit of hosted work and file the council's own row on the way out.

    A returned result is filed before it is reported. A filing failure emits
    a failed unit event and propagates rather than reporting success.

    A raised unit files a failed row before propagating its exception. If filing
    also raises, both failures escape together. A platform kill cannot file a row.
    """
    began = datetime.now(UTC).strftime(STARTED_AT_FORMAT)
    started = time.monotonic()
    outcome.start_unit()
    failure: BaseException | None = None
    produced: ShardResult | None = None
    try:
        file_result = partial(
            _file,
            judge_id=judge_id,
            date=date,
            run_id=run_id,
            evaluation_step=evaluation_step,
            work_part_index=work_part_index,
            work_part_count=work_part_count,
            began=began,
        )
        try:
            produced = work()
            if produced.outcome is ShardOutcome.FAILED:
                raise ValueError("a failed council result requires a raised unit")
        except BaseException as work_error:
            try:
                file_result(
                    ShardResult(outcome=ShardOutcome.FAILED),
                    seconds=time.monotonic() - started,
                    failed=True,
                )
            except BaseException as filing_error:
                raise BaseExceptionGroup(
                    "council work and recording failures", [work_error, filing_error]
                ) from None
            raise
        else:
            file_result(produced, seconds=time.monotonic() - started)
        return produced
    except BaseException as error:
        failure = error
        raise
    finally:
        error_name, where = event_log.cause_of(failure)
        event_log.emit(
            UnitFinished(
                judge_id=judge_id,
                date=date,
                run_id=run_id,
                evaluation_step=evaluation_step,
                work_part_index=work_part_index,
                work_part_count=(
                    work_part_count
                    if evaluation_step is EvaluationStep.EVALUATE_WORK_PART
                    or evaluation_step is EvaluationStep.COMBINE_JUDGE_RESULTS
                    or (
                        failure is None
                        and produced is not None
                        and produced.outcome is not ShardOutcome.NOTHING_TO_DO
                    )
                    else 0
                ),
                outcome=produced.outcome
                if failure is None and produced is not None
                else ShardOutcome.FAILED,
                error=error_name,
                where=where,
            ),
            level=logging.ERROR
            if failure is not None or (produced is not None and outcome.of_results((produced,)))
            else logging.INFO,
        )


def _file(
    result: ShardResult,
    *,
    judge_id: str,
    date: DateStamp,
    run_id: RunId,
    evaluation_step: EvaluationStep,
    work_part_index: int | None,
    work_part_count: int,
    began: str,
    seconds: float,
    failed: bool = False,
) -> Path:
    """Write the venue's own row where the job that commits it will find it.

    Through the capability a tenant's own row ships on, so the night has one
    shipping path and not two. The four cost cells are copied off what the
    tenant handed back and read out of nothing else - a tenant with no model
    hands back nulls, and null is not zero.
    """
    row = CouncilRunRecord.model_validate(
        {
            "date": date,
            "run_id": run_id,
            "judge_id": judge_id,
            "evaluation_step": evaluation_step,
            "work_part_index": work_part_index,
            "work_part_count": (
                work_part_count
                if evaluation_step is EvaluationStep.EVALUATE_WORK_PART
                or evaluation_step is EvaluationStep.COMBINE_JUDGE_RESULTS
                or (not failed and result.outcome is not ShardOutcome.NOTHING_TO_DO)
                else 0
            ),
            "outcome": result.outcome,
            "fault": "raised" if result.outcome is ShardOutcome.FAILED else None,
            "started_at": began,
            "seconds_spent": seconds,
            "model_calls": result.model_calls,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "model_seconds": result.model_seconds,
        }
    )
    name = (
        str(work_part_index)
        if work_part_index is not None
        else evaluation_step.value.replace("_", "-")
    )
    work_files.check_destination(outcomes_dir(date) / judge_id / f"{name}.csv")
    return metrics_sink.ship_judge_metrics(
        row,
        judge_id=judge_id,
        name=name,
        out_dir=outcomes_dir(date),
    )


def _identify_writer(*, run_id: RunId, commit_sha: str) -> WriterIdentity:
    """Who wrote each file the job that saves the night's results files.

    Built once a date and shared: the council run, that job and its one shard,
    the platform's attempt at the run, and the commit the run checked out. The
    council files its own record under it, and a tenant files its own rows under
    it with its own stage as the producer.
    """
    return WriterIdentity(
        run_id=run_id,
        attempt=run_context.run_attempt(),
        job=ServerJob.SAVE_COUNCIL_RESULTS,
        shard=0,
        producer="council.session",
        git_sha=commit_sha,
    )


def _collect(
    hosted: Sequence[Tenant],
    *,
    date: DateStamp,
    state_dir: Path,
    identity: WriterIdentity,
) -> int:
    """File every row tonight's units wrote through the ledger door.

    What it reads is one directory a tenant, holding one file a unit, so it
    costs what the night fanned out to rather than what the archive has piled up
    (Guardrail #12).
    """
    recorded = [
        row
        for host in hosted
        for row in metrics_sink.shipped_rows(
            outcomes_dir(date), judge_id=host.judge_id, contract=CouncilRunRecord
        )
    ]
    written = ledger.persist(
        state_dir,
        recorded,
        ledger=LedgerName.COUNCIL_RUN_RECORDS,
        covers=date,
        identity=identity,
    )
    landed = len(recorded) if written else 0
    event_log.emit(RowsCollected(date=date, rows=landed))
    return landed
