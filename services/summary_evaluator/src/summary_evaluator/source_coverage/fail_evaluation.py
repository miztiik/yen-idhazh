"""Which closed shared failure becomes a safe coverage refusal without raw exception text?"""

from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode


class CoverageFailure(Exception):
    def __init__(self, code: ErrorCode, cleanup_code: ErrorCode | None = None) -> None:
        if code not in ERROR_POLICIES or (
            cleanup_code is not None and cleanup_code not in ERROR_POLICIES
        ):
            raise ValueError("Expected a declared coverage failure code")
        self.code, self.cleanup_code = code, cleanup_code
        super().__init__(ERROR_POLICIES[code].message)
