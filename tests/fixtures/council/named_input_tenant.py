"""Combine named committed inputs with a downloaded completed unit, without a model."""

from pathlib import Path

from idhazh import atomic_write
from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_invocation import (
    JudgeSchedule,
    PreparationReceipt,
    ScheduleRequest,
    ShardReport,
)
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.council import session
from idhazh.council.tenancy import ShardResult

JUDGE_ID = __name__.split(".")[-2].replace("_", "-")


class NamedInputTenant:
    judge_id = JUDGE_ID
    shard_count = 1
    committed_paths = ("state/results/" + JUDGE_ID,)

    def schedule(self, *, request: ScheduleRequest) -> JudgeSchedule:
        return JudgeSchedule(dates=(request.anchor_date,))

    def prepare(self, *, date: DateStamp, run_id: RunId, shards: int) -> ShardResult:
        path = session.unit_file(date, slot="verdicts", judge_id=JUDGE_ID, suffix=".txt")
        atomic_write.write_atomic(path, JUDGE_ID + " completed unit\n")
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO, files=(session.artifact_path(path),))

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
        prepared: PreparationReceipt,
    ) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)

    def publication_inputs(self, *, date: DateStamp) -> tuple[str, ...]:
        return (
            "state/input/" + JUDGE_ID + "/" + date,
            "state/index/" + JUDGE_ID + ".json",
            "state/optional/" + JUDGE_ID + "/" + date,
        )

    def settle(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        state_dir: Path,
        identity: WriterIdentity,
        prepared: PreparationReceipt,
        reports: tuple[ShardReport, ...],
    ) -> ShardResult:
        root = state_dir.parent
        names = (
            "state/input/" + JUDGE_ID + "/" + date + "/first.txt",
            "state/input/" + JUDGE_ID + "/" + date + "/second.txt",
            "state/index/" + JUDGE_ID + ".json",
        )
        contents = "".join((root / name).read_text(encoding="utf-8") for name in names)
        contents += session.unit_file(
            date, slot="verdicts", judge_id=JUDGE_ID, suffix=".txt"
        ).read_text(encoding="utf-8")
        atomic_write.write_atomic(root / self.committed_paths[0] / (date + ".txt"), contents)
        return ShardResult(outcome=ShardOutcome.COMPLETED)


TENANT = NamedInputTenant()
