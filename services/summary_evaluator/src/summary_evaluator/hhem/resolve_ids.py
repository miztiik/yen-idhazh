"""How are caller, execution and deterministic event identities kept separate?"""

from dataclasses import dataclass
from typing import Final
from uuid import NAMESPACE_DNS, uuid4, uuid5

from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.shared.contracts.base import validate_uuid4

EVENT_NAMESPACE: Final = NAMESPACE_DNS


@dataclass(frozen=True)
class EvaluationIdentity:
    """Retain caller spelling beside an independently created execution ID."""

    execution_id: str
    request_id: str
    correlation_id: str


def resolve_ids(request: EvaluateRequest, execution_id: str) -> EvaluationIdentity:
    """Generate only omitted caller IDs, never replace an invalid supplied ID."""
    return EvaluationIdentity(
        execution_id=validate_uuid4(execution_id),
        request_id=(
            str(uuid4()) if request.request_id is None else validate_uuid4(request.request_id)
        ),
        correlation_id=(
            str(uuid4())
            if request.correlation_id is None
            else validate_uuid4(request.correlation_id)
        ),
    )


def create_event_seed(execution_id: str, sequence: int) -> str:
    """Encode the one event name without a trailing newline."""
    validate_uuid4(execution_id)
    if type(sequence) is not int or sequence < 1:
        raise ValueError("Event sequence must be a positive integer")
    return f"hhem\n{execution_id}\n{sequence}"


def create_event_id(execution_id: str, sequence: int) -> str:
    """Apply the standard UUIDv5 algorithm to the declared event name."""
    return str(uuid5(EVENT_NAMESPACE, create_event_seed(execution_id, sequence)))
