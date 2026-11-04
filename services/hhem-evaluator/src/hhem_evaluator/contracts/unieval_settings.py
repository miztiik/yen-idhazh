"""Which named local assets, prompts and process bounds govern UniEval?"""

from typing import Self

from pydantic import Field, model_validator

from .base import CommitId, ContextIdentity, NonblankText, PositiveCount, RelativePath, Sha256
from .service_settings import (
    EvaluationSettings,
    ListenerSettings,
    LoggingSettings,
    ModelAssetSettings,
    QueueSettings,
    WorkerSettings,
)
from .unieval_contract import UnievalContract, UnievalVersion
from .unieval_request import UnievalControls


class SentenceResources(UnievalContract):
    archive_url: NonblankText
    archive_sha256: Sha256
    max_archive_bytes: PositiveCount
    download_timeout_ms: PositiveCount
    files: tuple[RelativePath, ...] = Field(min_length=1)
    language: ContextIdentity

    @model_validator(mode="after")
    def require_named_inventory(self) -> Self:
        if len(set(self.files)) != len(self.files):
            raise ValueError("Sentence resource files must be distinct")
        if not self.archive_url.startswith("https://"):
            raise ValueError("Sentence resources require a committed HTTPS destination")
        return self


class UnievalAssets(UnievalContract):
    model: ModelAssetSettings
    reference_code_revision: CommitId
    cache_directory: RelativePath
    sentences: SentenceResources


class UnievalPrompts(UnievalContract):
    fluency: NonblankText
    coherence: NonblankText
    consistency: NonblankText
    relevance: NonblankText
    positive_answer: NonblankText
    negative_answer: NonblankText

    @model_validator(mode="after")
    def require_declared_placeholders(self) -> Self:
        from string import Formatter

        required = {
            "fluency": {"summary"},
            "coherence": {"summary", "source"},
            "consistency": {"summary", "source"},
            "relevance": {"summary", "reference"},
        }
        for dimension, fields in required.items():
            parts = list(Formatter().parse(getattr(self, dimension)))
            actual = {field for _, field, _, _ in parts if field is not None}
            if actual != fields or any(spec or conversion for _, _, spec, conversion in parts):
                raise ValueError(f"{dimension} must use its declared plain placeholders")
        if self.positive_answer == self.negative_answer:
            raise ValueError("The positive and negative answers must differ")
        return self


class UnievalWorkerSettings(WorkerSettings):
    max_reply_bytes: PositiveCount


class AuthoredUnievalSettings(UnievalContract):
    version: UnievalVersion
    assets: UnievalAssets
    prompts: UnievalPrompts
    scoring: UnievalControls
    queue: QueueSettings
    evaluation: EvaluationSettings
    worker: UnievalWorkerSettings


class UnievalSettings(AuthoredUnievalSettings):
    listener: ListenerSettings
    logging: LoggingSettings
