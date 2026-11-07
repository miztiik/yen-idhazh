"""Which exact legacy preparation rules and named resources are resolved before serving?"""

from typing import Literal, Self

from pydantic import Field, model_validator

from summary_evaluator.shared.contracts.base import (
    CommitId,
    ModelReference,
    NonblankText,
    PositiveCount,
    RelativePath,
    Score,
    Sha256,
)
from summary_evaluator.shared.contracts.service_settings import (
    EvaluationSettings,
    ListenerSettings,
    LoggingSettings,
    ModelAssetSettings,
    QueueSettings,
    WorkerSettings,
)
from summary_evaluator.source_coverage.contracts.base import CoverageContract, CoverageVersion


class CoverageCodeResources(CoverageContract):
    repository: ModelReference
    revision: CommitId
    files: dict[RelativePath, Sha256]
    download_timeout_ms: PositiveCount
    max_file_bytes: PositiveCount

    @model_validator(mode="after")
    def require_named_code(self) -> Self:
        if set(self.files) != {"metric/evaluator.py", "metric/scorer.py", "utils.py"}:
            raise ValueError("The legacy loader requires exactly its three upstream code files")
        return self


class CoverageSentenceResources(CoverageContract):
    archive_url: NonblankText
    archive_sha256: Sha256
    max_archive_bytes: PositiveCount
    download_timeout_ms: PositiveCount
    language: Literal["english"]
    files: tuple[RelativePath, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_named_sentences(self) -> Self:
        if not self.archive_url.startswith("https://") or len(set(self.files)) != len(self.files):
            raise ValueError("Sentence resources require a named distinct HTTPS inventory")
        return self


class CoverageAssets(CoverageContract):
    code: CoverageCodeResources
    model: ModelAssetSettings
    cache_directory: RelativePath
    sentences: CoverageSentenceResources


class CoveragePreparation(CoverageContract):
    chunk_words: PositiveCount
    stride_words: PositiveCount
    macro_words: PositiveCount
    macro_min_paragraph_chars: PositiveCount
    macro_complete_paragraphs: PositiveCount
    macro_no_paragraph_chars: PositiveCount
    macro_few_paragraph_chars: PositiveCount
    macro_lead_paragraphs: PositiveCount = 2
    macro_tail_paragraphs: PositiveCount = 1
    summary_min_sentence_chars: PositiveCount
    top_chunks: PositiveCount
    evidence_min_score: Score
    evidence_fallback_chars: PositiveCount
    grounding_threshold: Score
    score_decimals: int = Field(strict=True, ge=0)
    coverage_decimals: int = Field(strict=True, ge=0)
    threshold_decimals: int = Field(default=2, strict=True, ge=0)
    uncovered_excerpt_words: PositiveCount
    empty_summary: NonblankText
    empty_source: NonblankText
    empty_sentence: NonblankText
    empty_document: NonblankText
    empty_macro: NonblankText

    @model_validator(mode="after")
    def require_forward_stride(self) -> Self:
        if self.stride_words >= self.chunk_words:
            raise ValueError("Legacy overlapping chunks must advance")
        if self.macro_complete_paragraphs < self.macro_lead_paragraphs + self.macro_tail_paragraphs:
            raise ValueError("The legacy macro view must not duplicate its selected paragraphs")
        return self


class CoverageModelSettings(CoverageContract):
    max_length: PositiveCount
    device: Literal["cpu"]
    threads: PositiveCount | Literal["logical_processors"]


class CoverageWorkerSettings(WorkerSettings):
    max_reply_bytes: PositiveCount


class AuthoredCoverageSettings(CoverageContract):
    version: CoverageVersion
    assets: CoverageAssets
    preparation: CoveragePreparation
    model: CoverageModelSettings
    queue: QueueSettings
    evaluation: EvaluationSettings
    worker: CoverageWorkerSettings


class CoverageSettings(AuthoredCoverageSettings):
    listener: ListenerSettings
    logging: LoggingSettings
