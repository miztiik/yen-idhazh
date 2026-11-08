"""Which exact reference identity and relevance selection bind a current saved answer?"""

from typing import Annotated, Final, Literal, Self

from pydantic import ConfigDict, Field, RootModel, StrictBool, model_validator
from summary_evaluator.shared.contracts.base import NonblankText, Sha256

from .contracts import GenerationReceipt as PreviousGenerationReceipt
from .contracts import (
    LoadedModel,
    ModelSelection,
    PipelineError,
    RunIdentity,
    WorkflowContract,
    text_sha256,
)
from .contracts import PreparedRun as PreviousPreparedRun

RUN_VERSION: Final = "2026-11-08"
RunVersion = Literal["2026-11-08"]


class RunContract(WorkflowContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": RUN_VERSION,
            "readCompatibility": "read frozen preparation and receipt files by exact version",
            "changelog": [
                {
                    "version": RUN_VERSION,
                    "change": "Bind optional reference and relevance selection.",
                },
                {"version": "2026-11-05", "change": "Bind one native answer to its prepared run."},
            ],
        }
    )


class PreparedRun(RunContract):
    version: RunVersion
    run: RunIdentity
    selected: ModelSelection
    source_sha256: Sha256
    reference_summary_sha256: Sha256 | None
    evaluate_relevance: StrictBool
    status: Literal["pending", "complete", "failed"]
    errors: tuple[PipelineError, ...]

    @model_validator(mode="after")
    def require_preparation_outcome(self) -> Self:
        if (self.status == "failed") != bool(self.errors):
            raise ValueError("Failed preparation requires its original safe errors")
        if any(error.phase != "preparation" for error in self.errors):
            raise ValueError("Preparation errors must identify their own phase")
        return self


class GenerationReceipt(RunContract):
    version: RunVersion
    run: RunIdentity
    selected: ModelSelection
    loaded: LoadedModel | None
    source_sha256: Sha256
    reference_summary_sha256: Sha256 | None
    evaluate_relevance: StrictBool
    summary_sha256: Sha256 | None
    summary_text: NonblankText | None
    status: Literal["complete", "failed"]
    errors: tuple[PipelineError, ...]

    @model_validator(mode="after")
    def require_final_answer(self) -> Self:
        if self.status == "complete":
            if self.loaded is None or self.summary_text is None or self.errors:
                raise ValueError("Completed generation requires its loaded model and final answer")
            if (
                self.loaded.model_id != self.selected.model_id
                or self.loaded.sha256 != self.selected.sha256
                or self.loaded.weights_path != f"backend/models/{self.selected.filename}"
                or self.summary_sha256 != text_sha256(self.summary_text)
            ):
                raise ValueError("The generated answer must bind the loaded model and exact bytes")
        elif self.summary_text is not None or self.summary_sha256 is not None or not self.errors:
            raise ValueError("Failed generation has errors and no accepted answer")
        return self


PreparedResult = PreparedRun | PreviousPreparedRun
GenerationResult = GenerationReceipt | PreviousGenerationReceipt


class PreparedDocument(
    RootModel[Annotated[PreparedResult, Field(discriminator="version")]]
):
    pass


class GenerationDocument(
    RootModel[Annotated[GenerationResult, Field(discriminator="version")]]
):
    pass
