"""Which closed failure crossed a shared transport or lifecycle boundary?"""

from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode


class RuntimeFailure(Exception):
    """Carry a validated code without a scorer's public error projection."""

    def __init__(self, code: ErrorCode) -> None:
        if code not in ERROR_POLICIES:
            raise ValueError("Expected a declared runtime failure code")
        self.code = code
        super().__init__(code)
