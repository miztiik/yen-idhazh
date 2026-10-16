"""What did the night's validated events report on the collecting job's page?"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from pydantic import Field, TypeAdapter, model_validator

from idhazh import event_lines
from idhazh.contracts.base import DateStamp, Model, Slug
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


class Cell(Model):
    """One planner-selected job whose report must not be inferred from output bytes."""

    tenant: Slug
    date: DateStamp
    shard: int = Field(ge=0, strict=True)
    shards: int = Field(ge=1, strict=True)
    runs_model: bool = Field(strict=True)

    @model_validator(mode="after")
    def valid_cell(self) -> Cell:
        date.fromisoformat(self.date)
        if self.shard >= self.shards:
            raise ValueError("shard must be below shards")
        return self

    def event_path(self, root: Path) -> Path:
        return root / self.tenant / self.date / f"{self.shard}.jsonl"


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
    invalid: bool = False

    @property
    def failed(self) -> bool:
        return (
            self.invalid
            or self.unit is None
            or self.program is None
            or self.program.code is not CouncilExit.OK
            or self.unit.outcome in ("failed", ShardOutcome.STOPPED_ON_DEADLINE)
        )

    def ended(self) -> str:
        if self.invalid:
            return "**invalid report**"
        if self.unit is None or self.program is None:
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
                if result.program is not None or event.program is not CouncilProgram.SHARD:
                    raise ValueError("unexpected program result")
                result.program = event
            elif not isinstance(event, Diagnostic):
                raise ValueError("unexpected judging event")
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
    return result


@dataclass
class Report:
    units: tuple[ReportedCell, ...] = ()
    planning: tuple[Model, ...] = ()
    invalid_plan: bool = False
    events: list[Model] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return (
            self.invalid_plan
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

    def load(self, matrix: str, root: Path, run_id: str) -> None:
        try:
            selected = cells(matrix)
        except ValueError:
            self.invalid_plan = True
            raise
        self.units = tuple(reported(cell, root, run_id) for cell in selected)
        try:
            self.planning = read_events(root / "planner.jsonl")
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
            blocks.append(
                f"Publication: `{last.landing}`; {last.writes} writes; {last.pushes} pushes. "
                f"Dates (UTC): {', '.join(last.dates)}."
            )
        if self.invalid_plan:
            blocks.append("**Invalid planning report.** Its events were rejected.")
        elif not self.planning:
            blocks.append("Planning events: **no report**.")
        failed = sum(unit.failed for unit in self.units)
        blocks.append(
            f"{len(self.units)} planned judging jobs; {failed} failed or incomplete reports."
        )
        rows = [
            "Table A - units reported by judge and date (UTC)",
            "| Id | Judge | Date (UTC) | Unit | How it ended |",
            "| --- | --- | --- | --- | --- |",
        ]
        index = 0
        for event in (*self.planning, *self.events):
            if isinstance(event, UnitFinished):
                index += 1
                word = str(event.outcome).replace("_", " ")
                if event.outcome in ("failed", ShardOutcome.STOPPED_ON_DEADLINE):
                    word = f"**{word}**"
                rows.append(
                    f"| A{index} | `{event.judge_id}` | {event.date} | {_step(event)} | {word} |"
                )
        for unit in self.units:
            index += 1
            cell = unit.cell
            rows.append(
                f"| A{index} | `{cell.tenant}` | {cell.date} | shard {cell.shard} "
                f"of {cell.shards} (starts at 0) | {unit.ended()} |"
            )
        if index:
            blocks.append("\n".join(rows))
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
        judges = dict.fromkeys(
            [
                *(unit.cell.tenant for unit in self.units),
                *(
                    event.judge_id
                    for event in (*self.planning, *self.events)
                    if isinstance(event, UnitFinished)
                ),
            ]
        )
        for judge in judges:
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
