"""What did the night's validated events report on the collecting job's page?"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from idhazh import event_lines
from idhazh.contracts.base import Model
from idhazh.contracts.council_events import (
    CouncilExit,
    CouncilProgram,
    Diagnostic,
    JudgeDeclared,
    NightPlanned,
    NightPublished,
    ProgramFinished,
    RowsCollected,
    RunIdentified,
    UnitFinished,
)
from idhazh.contracts.council_invocation import Cell as Cell
from idhazh.contracts.council_invocation import Selection, ShardReport, ShardReportState
from idhazh.contracts.council_run_record import EvaluationStep, ShardOutcome

# These are the existing transient event vocabulary and workflow matrix, not a ledger.
_EVENTS = {
    event_lines.name_of(kind): kind
    for kind in (
        Diagnostic,
        JudgeDeclared,
        NightPlanned,
        NightPublished,
        ProgramFinished,
        RowsCollected,
        RunIdentified,
        UnitFinished,
    )
}
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def cells(matrix: str) -> tuple[Cell, ...]:
    selected = TypeAdapter(tuple[Cell, ...]).validate_json(matrix)
    identities = {(cell.tenant, cell.date, cell.shard) for cell in selected}
    if len(identities) != len(selected):
        raise ValueError("duplicate planned cell")
    return selected


def read_events(path: Path) -> tuple[Model, ...]:
    """Read only one invocation file, refusing unknown fields and unsafe text."""
    if not path.exists():
        return ()
    events: list[Model] = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            data = json.loads(line)
            if not isinstance(data, dict):
                raise ValueError("event must be an object")
            name = data.pop("event", None)
            kind = _EVENTS.get(name) if isinstance(name, str) else None
            stamp = data.pop("at", None)
            level = data.pop("level", None)
            if (
                kind is None
                or not isinstance(stamp, str)
                or _STAMP.fullmatch(stamp) is None
                or level not in ("debug", "info", "warning", "error", "critical")
            ):
                raise ValueError("invalid event envelope")
            datetime.fromisoformat(stamp)
            has_exit_fields = "label" in data or "sentence" in data
            label, sentence = data.pop("label", None), data.pop("sentence", None)
            event = kind.model_validate_json(json.dumps(data), strict=True)
            if isinstance(event, ProgramFinished):
                if label != event.label or sentence != event.sentence:
                    raise ValueError("invalid exit label or sentence")
            elif has_exit_fields:
                raise ValueError("unexpected exit fields")
            events.append(event)
    return tuple(events)


@dataclass
class ReportedCell:
    cell: Cell
    unit: UnitFinished | None = None
    program: ProgramFinished | None = None
    verification: ProgramFinished | None = None
    invalid: bool = False
    dispatched: bool = True

    def normalized(self, *, dispatched: bool | None = None) -> ShardReport:
        dispatched = self.dispatched if dispatched is None else dispatched
        exit_report = self.program if self.program is not None else self.verification
        state: ShardReportState = (
            "not_dispatched"
            if not dispatched
            else "invalid"
            if self.invalid
            else "refused"
            if exit_report is not None and exit_report.code is CouncilExit.REFUSED
            else "missing"
            if self.unit is None or self.program is None
            else "reported"
        )
        return ShardReport(
            shard=self.cell.shard,
            shards=self.cell.shards,
            report_state=state,
            outcome=self.unit.outcome if state == "reported" and self.unit is not None else None,
            code=exit_report.code if exit_report is not None else None,
        )

    @property
    def failed(self) -> bool:
        return (
            self.invalid
            or not self.dispatched
            or self.unit is None
            or self.program is None
            or self.program.code is not CouncilExit.OK
            or (self.verification is not None and self.verification.code is not CouncilExit.OK)
            or self.unit.outcome in ("failed", ShardOutcome.STOPPED_ON_DEADLINE)
        )

    def ended(self) -> str:
        if not self.dispatched:
            return "**not dispatched**"
        if self.invalid:
            return "**invalid report**"
        if self.unit is None or self.program is None:
            if self.verification is not None and self.verification.code is not CouncilExit.OK:
                return f"not attempted; verification {_exit(self.verification)}"
            if self.program is not None and self.program.code is CouncilExit.REFUSED:
                return f"not attempted; {_exit(self.program)}"
            word = "**no report**"
            if self.unit is not None:
                word = f"{str(self.unit.outcome).replace('_', ' ')}; {word}"
            return word if self.program is None else f"{word}; {_exit(self.program)}"
        word = str(self.unit.outcome).replace("_", " ")
        if self.failed:
            word = f"**{word}**"
        return f"{word}; {_exit(self.program)}"


def reported(cell: Cell, root: Path, run_id: str) -> ReportedCell:
    result = ReportedCell(cell)
    try:
        for event in read_events(cell.event_path(root)):
            if isinstance(event, UnitFinished):
                if (
                    result.unit is not None
                    or event.run_id != run_id
                    or event.judge_id != cell.tenant
                    or event.date != cell.date
                    or event.evaluation_step is not EvaluationStep.EVALUATE_WORK_PART
                    or event.work_part_index != cell.shard
                    or event.work_part_count != cell.shards
                ):
                    raise ValueError("unit does not match its planned cell")
                result.unit = event
            elif isinstance(event, ProgramFinished):
                if event.program is CouncilProgram.VERIFY_WORK:
                    if result.verification is not None:
                        raise ValueError("duplicate verification result")
                    result.verification = event
                elif event.program is CouncilProgram.SHARD and result.program is None:
                    result.program = event
                else:
                    raise ValueError("unexpected program result")
            elif not isinstance(event, Diagnostic):
                raise ValueError("unexpected judging event")
        if (
            result.verification is not None
            and result.verification.code is not CouncilExit.OK
            and (result.unit is not None or result.program is not None)
        ):
            raise ValueError("work followed rejected verification")
        if (
            result.unit is not None
            and result.program is not None
            and result.program.code is CouncilExit.OK
            and result.unit.outcome in ("failed", ShardOutcome.STOPPED_ON_DEADLINE)
        ):
            raise ValueError("failed unit cannot report a successful exit")
    except (ValueError, OSError):
        result.invalid = True
        result.unit = None
        result.program = None
        result.verification = None
    return result


@dataclass
class Report:
    units: tuple[ReportedCell, ...] = ()
    planning: tuple[Model, ...] = ()
    invalid_plan: bool = False
    events: list[Model] = field(default_factory=list)
    selection: Selection | None = None
    expected_preparations: tuple[tuple[str, str], ...] = ()
    missing_preparations: tuple[tuple[str, str], ...] = ()

    @property
    def failed(self) -> bool:
        return (
            self.invalid_plan
            or bool(self.missing_preparations)
            or any(unit.failed for unit in self.units)
            or any(
                (
                    isinstance(event, UnitFinished)
                    and event.outcome in ("failed", ShardOutcome.STOPPED_ON_DEADLINE)
                )
                or (isinstance(event, ProgramFinished) and event.code is not CouncilExit.OK)
                for event in self.planning
            )
        )

    def load(
        self,
        matrix: str,
        root: Path,
        run_id: str,
        *,
        selection: Selection | None = None,
    ) -> None:
        self.selection = selection
        try:
            selected = cells(matrix)
        except ValueError:
            self.invalid_plan = True
            raise
        self.units = tuple(reported(cell, root, run_id) for cell in selected)
        if selection is not None:
            from idhazh.council import work_files

            expected: list[Cell] = []
            unknown: list[tuple[str, str]] = []
            for judge in selection.judges:
                for day in judge.dates:
                    prepared = work_files.read_preparation(
                        root.parent, selection, judge.tenant, day
                    )
                    if prepared is None:
                        unknown.append((judge.tenant, day))
                    elif prepared.state == "ready":
                        expected.extend(
                            Cell(
                                tenant=judge.tenant,
                                date=day,
                                shard=part,
                                shards=prepared.shards,
                                runs_model=False,
                            )
                            for part in range(prepared.shards)
                        )
            admitted = {(cell.tenant, cell.date, cell.shard, cell.shards) for cell in selected}
            authorized = {(cell.tenant, cell.date, cell.shard, cell.shards) for cell in expected}
            if not admitted <= authorized:
                self.invalid_plan = True
                raise ValueError("matrix contains work not authorized by ready preparation")
            self.units = tuple(
                ReportedCell(cell, dispatched=False)
                if (cell.tenant, cell.date, cell.shard, cell.shards) not in admitted
                else reported(cell, root, run_id)
                for cell in expected
            )
            self.missing_preparations = tuple(unknown)
        try:
            self.planning = read_events(root / "planner.jsonl")
            if selection is not None:
                self.expected_preparations = tuple(
                    (judge.tenant, day) for judge in selection.judges for day in judge.dates
                )
                actual = [
                    (event.judge_id, event.date)
                    for event in self.planning
                    if isinstance(event, UnitFinished)
                ]
                if len(actual) != len(set(actual)) or not set(actual) <= set(
                    self.expected_preparations
                ):
                    raise ValueError("unexpected planning unit")
                self.missing_preparations = tuple(
                    dict.fromkeys(
                        (
                            *self.missing_preparations,
                            *(pair for pair in self.expected_preparations if pair not in actual),
                        )
                    )
                )
            for event in self.planning:
                if isinstance(event, UnitFinished) and (
                    event.run_id != run_id
                    or event.evaluation_step is not EvaluationStep.SELECT_JUDGE_WORK
                ):
                    raise ValueError("unexpected planning unit")
                if isinstance(event, RunIdentified) and event.run_id != run_id:
                    raise ValueError("unexpected planning run")
                if isinstance(event, NightPublished | RowsCollected):
                    raise ValueError("unexpected planning event")
                if isinstance(event, ProgramFinished) and event.program not in (
                    CouncilProgram.PLAN,
                    CouncilProgram.IDENTITY,
                    CouncilProgram.MATRIX,
                    CouncilProgram.PREPARE,
                ):
                    raise ValueError("unexpected planning program")
        except (ValueError, OSError):
            self.invalid_plan = True
            self.planning = ()

    def _judges(self) -> tuple[str, ...]:
        selected = (
            () if self.selection is None else tuple(judge.tenant for judge in self.selection.judges)
        )
        names = [
            *selected,
            *(judge for judge, _ in self.expected_preparations),
            *(judge for judge, _ in self.missing_preparations),
            *(unit.cell.tenant for unit in self.units),
            *(
                event.judge_id
                for event in (*self.planning, *self.events)
                if isinstance(event, UnitFinished)
            ),
        ]
        return tuple(dict.fromkeys(names))

    def _dates(self, judge: str) -> tuple[str, ...]:
        selected = (
            ()
            if self.selection is None
            else tuple(
                day
                for selected_judge in self.selection.judges
                if selected_judge.tenant == judge
                for day in selected_judge.dates
            )
        )
        days = [
            *selected,
            *(day for name, day in self.expected_preparations if name == judge),
            *(day for name, day in self.missing_preparations if name == judge),
            *(unit.cell.date for unit in self.units if unit.cell.tenant == judge),
            *(
                event.date
                for event in (*self.planning, *self.events)
                if isinstance(event, UnitFinished) and event.judge_id == judge
            ),
        ]
        return tuple(dict.fromkeys(days))

    def _stage_events(
        self,
        judge: str,
        day: str,
        step: EvaluationStep,
    ) -> tuple[UnitFinished, ...]:
        source = self.planning if step is EvaluationStep.SELECT_JUDGE_WORK else self.events
        return tuple(
            event
            for event in source
            if isinstance(event, UnitFinished)
            and event.judge_id == judge
            and event.date == day
            and event.evaluation_step is step
        )

    def _stage_text(self, judge: str, day: str, step: EvaluationStep) -> str:
        if step is EvaluationStep.SELECT_JUDGE_WORK and (judge, day) in self.missing_preparations:
            return "**unknown; no report**"
        matches = self._stage_events(judge, day, step)
        if not matches:
            return "**no report**"
        if len(matches) != 1:
            return "**invalid report**"
        return _ended(matches[0].outcome)

    def _stage_complete(self, judge: str, day: str, step: EvaluationStep) -> bool:
        matches = self._stage_events(judge, day, step)
        return len(matches) == 1 and matches[0].outcome in (
            ShardOutcome.COMPLETED,
            ShardOutcome.NOTHING_TO_DO,
        )

    def _judge_units(self, judge: str, day: str) -> tuple[ReportedCell, ...]:
        return tuple(
            sorted(
                (
                    unit
                    for unit in self.units
                    if unit.cell.tenant == judge and unit.cell.date == day
                ),
                key=lambda unit: unit.cell.shard,
            )
        )

    def _judging_text(
        self,
        judge: str,
        day: str,
        units: tuple[ReportedCell, ...],
    ) -> str:
        successful = sum(not unit.failed for unit in units)
        if units:
            if successful == len(units):
                return f"{successful}/{len(units)} completed"
            return (
                f"{successful}/{len(units)} completed; "
                f"**{len(units) - successful} failed or incomplete**"
            )
        if (judge, day) in self.missing_preparations:
            return "**unknown; no report**"
        prepared = self._stage_events(judge, day, EvaluationStep.SELECT_JUDGE_WORK)
        if len(prepared) != 1:
            return self._stage_text(judge, day, EvaluationStep.SELECT_JUDGE_WORK)
        if prepared[0].outcome in (ShardOutcome.COMPLETED, ShardOutcome.NOTHING_TO_DO):
            return "no judging work"
        return "not run"

    def _judge_block(self, judge: str, table_index: int) -> str:
        letter = _table_letter(table_index)
        days = self._dates(judge)
        completed_dates = 0
        completed_units = 0
        unknown_dates = 0
        unit_count = 0
        rows = [
            f"Table {letter} - `{judge}` by date (UTC)",
            "| Id | Date (UTC) | Prepare | Judging | Settle |",
            "| --- | --- | --- | --- | --- |",
        ]
        details: list[str] = [
            "<details>",
            f"<summary>Unit reports for `{judge}`</summary>",
            "",
        ]
        for row_index, day in enumerate(days, 1):
            units = self._judge_units(judge, day)
            preparation_missing = (judge, day) in self.missing_preparations
            unknown_dates += preparation_missing
            successful = sum(not unit.failed for unit in units)
            completed_units += successful
            unit_count += len(units)
            prepare = self._stage_text(judge, day, EvaluationStep.SELECT_JUDGE_WORK)
            settle = self._stage_text(judge, day, EvaluationStep.COMBINE_JUDGE_RESULTS)
            judging = self._judging_text(judge, day, units)
            complete = (
                not preparation_missing
                and self._stage_complete(judge, day, EvaluationStep.SELECT_JUDGE_WORK)
                and self._stage_complete(judge, day, EvaluationStep.COMBINE_JUDGE_RESULTS)
                and successful == len(units)
            )
            completed_dates += complete
            rows.append(f"| {letter}{row_index} | {day} | {prepare} | {judging} | {settle} |")
            details.append(f"- {day} prepare: {prepare}")
            for unit in units:
                cell = unit.cell
                details.append(
                    f"- {day} shard {cell.shard} of {cell.shards} (starts at 0): {unit.ended()}"
                )
            if not units:
                details.append(f"- {day} judging: {judging}")
            details.append(f"- {day} settle: {settle}")
        details.append("</details>")
        date_word = "date" if len(days) == 1 else "dates"
        job_word = "job" if unit_count == 1 else "jobs"
        unknown_work = f"judging job count unknown for {unknown_dates} of {len(days)} {date_word}"
        work = (
            (
                f"{completed_units} of {unit_count} known judging {job_word} completed; "
                f"{unknown_work}"
                if unit_count
                else unknown_work
            )
            if unknown_dates
            else (
                "no judging jobs"
                if unit_count == 0
                else f"{completed_units} of {unit_count} judging {job_word} completed"
            )
        )
        return "\n\n".join(
            (
                f"#### Judge `{judge}`",
                f"{completed_dates} of {len(days)} {date_word} completed; {work}.",
                "\n".join(rows),
                "\n".join(details),
            )
        )

    def markdown(self) -> str:
        final = [
            event
            for event in self.events
            if isinstance(event, ProgramFinished) and event.program is CouncilProgram.PUBLISH
        ]
        heading = "### Council night: no collector report"
        if final:
            heading = (
                f"### Council night: {_exit(final[-1])}\n\n"
                f"{final[-1].sentence[:1].upper()}{final[-1].sentence[1:]}."
            )
        blocks = [heading]
        published = [event for event in self.events if isinstance(event, NightPublished)]
        if published:
            last = published[-1]
            write_word = "write" if last.writes == 1 else "writes"
            push_word = "push" if last.pushes == 1 else "pushes"
            blocks.append(
                f"Publication: `{last.landing}`; {last.writes} {write_word}; "
                f"{last.pushes} {push_word}. "
                f"Dates (UTC): {', '.join(last.dates)}."
            )
        if self.invalid_plan:
            blocks.append("**Invalid planning report.** Its events were rejected.")
        elif not self.planning:
            blocks.append("Planning events: **no report**.")
        failed = sum(unit.failed for unit in self.units)
        if self.missing_preparations:
            unknown = len(self.missing_preparations)
            noun = "judge/date" if unknown == 1 else "judge/dates"
            blocks.append(
                f"{len(self.units)} known planned judging jobs; {failed} failed or "
                f"incomplete reports. Judging work is unknown for {unknown} {noun}."
            )
        else:
            blocks.append(
                f"{len(self.units)} planned judging jobs; {failed} failed or incomplete reports."
            )
        judges = self._judges()
        if judges:
            blocks.extend(
                self._judge_block(judge, table_index) for table_index, judge in enumerate(judges)
            )
        else:
            blocks.append("No unit report was received.")
        blocks.append(
            "**No report** means no complete validated unit and exit report was received. "
            "It does not mean success, and does not prove why the job stopped. "
            "**Invalid report** means its events were rejected. "
            "Stopped on deadline means the unit reached its time limit. "
            "A shard is one part of a judge's work; its numbering starts at 0."
        )
        return "\n\n".join(blocks) + "\n"

    def write(self, path: Path) -> None:
        """Append exactly once, then group each judge and annotate its failed units."""
        with path.open("a", encoding="utf-8", newline="\n") as target:
            target.write(self.markdown())
        for judge in self._judges():
            print(f"::group::{event_lines.escaped_data(judge)}")
            failures: list[str] = []
            for unit in self.units:
                if unit.cell.tenant == judge:
                    message = (
                        f"{unit.cell.date} shard {unit.cell.shard}: "
                        f"{unit.ended().replace('**', '').replace('`', '')}"
                    )
                    print(event_lines.escaped_data(message))
                    if unit.failed:
                        failures.append(message)
            for event in (*self.planning, *self.events):
                if isinstance(event, UnitFinished) and event.judge_id == judge:
                    message = f"{event.date} {_step(event)}: {event.outcome}"
                    print(event_lines.escaped_data(message))
                    if event.outcome in ("failed", ShardOutcome.STOPPED_ON_DEADLINE):
                        failures.append(message)
            print("::endgroup::")
            for message in failures:
                print(
                    f"::error title={event_lines.escaped_property(judge)}::"
                    f"{event_lines.escaped_data(message)}"
                )
        if self.invalid_plan:
            print("::error title=council::Invalid planning report; events rejected.")


def _exit(event: ProgramFinished) -> str:
    return f"exit {event.code.value} `{event.label}`"


def _step(event: UnitFinished) -> str:
    return {
        EvaluationStep.SELECT_JUDGE_WORK: "prepare",
        EvaluationStep.EVALUATE_WORK_PART: "shard",
        EvaluationStep.COMBINE_JUDGE_RESULTS: "settle",
    }[event.evaluation_step]


def _ended(outcome: ShardOutcome) -> str:
    word = str(outcome).replace("_", " ")
    if outcome in ("failed", ShardOutcome.STOPPED_ON_DEADLINE):
        return f"**{word}**"
    return word


def _table_letter(index: int) -> str:
    index += 1
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
