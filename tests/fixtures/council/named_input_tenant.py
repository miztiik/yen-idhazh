"""Combine named committed inputs with a downloaded completed unit, without a model."""

from pathlib import Path

from idhazh import atomic_write
from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.council.tenancy import ShardResult

JUDGE_ID = __name__.split(".")[-2].replace("_", "-")


class NamedInputTenant:
    judge_id = JUDGE_ID
    shard_count = 1
    committed_paths = ("state/results/" + JUDGE_ID,)

    def nights_outstanding(self, *, window: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        return tuple(window)

    def prepare(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)

    def run_shard(
        self, *, date: DateStamp, run_id: RunId, shard: int, shards: int, deadline: float
    ) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)

    def publication_inputs(self, *, date: DateStamp) -> tuple[str, ...]:
        return (
            "state/input/" + JUDGE_ID + "/" + date,
            "state/index/" + JUDGE_ID + ".json",
            "state/optional/" + JUDGE_ID + "/" + date,
        )

    def settle(
        self, *, date: DateStamp, run_id: RunId, state_dir: Path, identity: WriterIdentity
    ) -> ShardResult:
        root = state_dir.parent
        names = (
            "state/input/" + JUDGE_ID + "/" + date + "/first.txt",
            "state/input/" + JUDGE_ID + "/" + date + "/second.txt",
            "state/index/" + JUDGE_ID + ".json",
            "backend/var/council/" + date + "/verdicts/" + JUDGE_ID + "/completed.txt",
        )
        contents = "".join((root / name).read_text(encoding="utf-8") for name in names)
        atomic_write.write_atomic(root / self.committed_paths[0] / (date + ".txt"), contents)
        return ShardResult(outcome=ShardOutcome.COMPLETED)


TENANT = NamedInputTenant()
