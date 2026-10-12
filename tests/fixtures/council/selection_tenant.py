"""Compute and file one selected date through the council's real invocation paths."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from idhazh import atomic_write
from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.council import session
from idhazh.council.tenancy import ShardResult


class FileJudge:
    """A model-free fixture judge that hashes its draw and checks it at settlement."""

    judge_id = __package__.rsplit(".", 1)[-1].replace("_", "-") if __package__ else "fixture"
    shard_count = 1

    @property
    def committed_paths(self) -> tuple[str, ...]:
        return (f"state/experiments/{self.judge_id}",)

    def publication_inputs(self, *, date: str) -> tuple[str, ...]:
        return (f"state/experiments/{self.judge_id}/seed.json",)

    def nights_outstanding(self, *, window: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        return window[-1:] if self.judge_id == "older-judge" else ()

    def prepare(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        target = session.unit_file(date, slot="selection", judge_id=self.judge_id, suffix=".json")
        atomic_write.write_atomic(target, json.dumps({"date": date, "run_id": run_id}))
        return ShardResult(outcome=ShardOutcome.COMPLETED)

    def run_shard(
        self, *, date: DateStamp, run_id: RunId, shard: int, shards: int, deadline: float
    ) -> ShardResult:
        drawn = session.unit_file(date, slot="selection", judge_id=self.judge_id, suffix=".json")
        target = session.unit_file(date, slot="verdicts", judge_id=self.judge_id, suffix=".json")
        atomic_write.write_atomic(target, hashlib.sha256(drawn.read_bytes()).hexdigest())
        return ShardResult(outcome=ShardOutcome.COMPLETED)

    def settle(
        self, *, date: DateStamp, run_id: RunId, state_dir: Path, identity: WriterIdentity
    ) -> ShardResult:
        drawn = session.unit_file(date, slot="selection", judge_id=self.judge_id, suffix=".json")
        verdict = session.unit_file(date, slot="verdicts", judge_id=self.judge_id, suffix=".json")
        if verdict.read_text(encoding="utf-8") != hashlib.sha256(drawn.read_bytes()).hexdigest():
            raise ValueError("the completed verdict does not match the selected work")
        directory = state_dir / "experiments" / self.judge_id
        seed = json.loads((directory / "seed.json").read_text(encoding="utf-8"))
        atomic_write.write_atomic(
            directory / f"{date}.json",
            json.dumps({"seed": seed, "digest": verdict.read_text(encoding="utf-8")}),
        )
        return ShardResult(outcome=ShardOutcome.COMPLETED)


TENANT = FileJudge()
