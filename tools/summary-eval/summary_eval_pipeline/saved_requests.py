"""How does a bounded saved handoff retain each native source/summary pair?"""

from dataclasses import dataclass, field
from pathlib import Path

from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest

from .contracts import PipelineError, text_sha256
from .evaluate_pair import EvaluatorOutcomes
from .failures import WorkflowError


@dataclass
class SavedSummary:
    request: EvaluateRequest
    outcomes: EvaluatorOutcomes = field(default_factory=EvaluatorOutcomes)
    errors: list[PipelineError] = field(default_factory=list)

    @property
    def key(self) -> str:
        return text_sha256(self.request.model_dump_json())

    def requests(self) -> tuple[EvaluateRequest, UnievalRequest]:
        return self.request, UnievalRequest(
            source_text=self.request.source_text,
            summary_text=self.request.summary_text,
            request_id=self.request.request_id,
            correlation_id=self.request.correlation_id,
        )


def read_saved_requests(path: Path, max_bytes: int) -> tuple[SavedSummary, ...]:
    try:
        with path.open("rb") as stream:
            encoded = stream.read(max_bytes + 1)
    except OSError:
        raise WorkflowError("INPUT_INVALID", "input") from None
    if len(encoded) > max_bytes:
        raise WorkflowError("INPUT_TOO_LARGE", "input")
    try:
        requests = tuple(
            EvaluateRequest.model_validate_json(line) for line in encoded.splitlines()
        )
        if (
            not requests
            or any(
                request.request_id is None or request.correlation_id is None
                or request.hhem_full is not False
                for request in requests
            )
            or len({request.request_id for request in requests}) != len(requests)
        ):
            raise ValueError("Expected distinct native requests from saved generation")
    except ValueError:
        raise WorkflowError("INPUT_INVALID", "input") from None
    return tuple(SavedSummary(request) for request in requests)
