"""Which bounded inputs and actual model predictions belong to a UniEval recording?"""

from pydantic import AwareDatetime

from .base import ContextIdentity, Count, Score, Sha256
from .unieval_contract import Dimension, UnievalContract, UnievalVersion
from .unieval_error import UnievalError
from .unieval_request import EffectiveUnievalControls, UnievalControls, UnievalRequest
from .unieval_result import UnievalWork


class UnievalRecordingInput(UnievalContract):
    id: ContextIdentity
    request: UnievalRequest
    controls: UnievalControls


class UnievalRecordingInputs(UnievalContract):
    version: UnievalVersion
    cases: tuple[UnievalRecordingInput, ...]


class RecordedUnievalComparison(UnievalContract):
    dimension: Dimension
    index: Count
    sentence_index: Count | None
    source_index: Count | None
    prompt_sha256: Sha256
    score: Score


class RecordedUnievalCase(UnievalContract):
    id: ContextIdentity
    input_sha256: Sha256
    effective_settings: EffectiveUnievalControls
    work: UnievalWork
    errors: tuple[UnievalError, ...]
    comparisons: tuple[RecordedUnievalComparison, ...]


class UnievalRecordingPredictions(UnievalContract):
    version: UnievalVersion
    recorded_at: AwareDatetime
    model_identity_sha256: Sha256
    cases: tuple[RecordedUnievalCase, ...]
