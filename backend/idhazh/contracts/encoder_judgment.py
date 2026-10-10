"""The pair frame and append-only verdicts used to evaluate saved encoders."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import DateStamp, Model, Sha256, Timestamp, Url


class PairVerdict(StrEnum):
    SAME = "same"
    DIFFERENT = "different"
    CANNOT_TELL = "cannot_tell"


class JudgmentArticle(Model):
    title: str
    summary: str
    outlet: str
    day: DateStamp
    url: Url


class JudgmentPair(Model):
    id: Annotated[str, Field(pattern=r"^p[0-9]{4}$")]
    group: str
    verdict: str
    note: str
    a: JudgmentArticle
    b: JudgmentArticle


class JudgmentFrame(Model):
    version: str
    pairs_to_read: Annotated[int, Field(ge=1)]
    repeated: Annotated[int, Field(ge=0)]
    groups: dict[str, int]
    taken: dict[str, int]
    verdicts_allowed: list[PairVerdict]
    rows: list[JudgmentPair]


class PairDecision(Model):
    verdict: PairVerdict
    note: Annotated[str, Field(min_length=1)]
    confidence: Literal["high", "medium", "low", "unrecorded"] = "unrecorded"


class EncoderJudgment(PairDecision):
    version: Literal["2026-10-09"] = "2026-10-09"
    pair_id: Annotated[str, Field(pattern=r"^p[0-9]{4}$")]
    frame_sha256: Sha256
    pair_sha256: Sha256
    label_source: Literal["model", "human"]
    labeler: Annotated[str, Field(min_length=1)]
    recorded_at: Timestamp
    human_verdict: PairVerdict | None = None

    @model_validator(mode="after")
    def check_review_provenance(self) -> Self:
        if self.label_source == "model" and self.human_verdict is not None:
            raise ValueError("a model judgment cannot claim human review")
        if self.label_source == "human" and self.human_verdict != self.verdict:
            raise ValueError("a human judgment must carry its reviewed verdict")
        return self
