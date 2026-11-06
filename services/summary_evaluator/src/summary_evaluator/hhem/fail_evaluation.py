"""How does an operation propagate a closed failure without input diagnostics?"""

from summary_evaluator.hhem.contracts.error_detail import ErrorDetail


class EvaluationFailure(Exception):
    """Carry only a validated body-free error across local control flow."""

    def __init__(self, error: ErrorDetail) -> None:
        self.error = error
        super().__init__(error.message)
