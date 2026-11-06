"""How does a UniEval failure retain only its declared body-free error?"""

from summary_evaluator.unieval.contracts.unieval_error import UnievalError


class UnievalFailure(Exception):
    def __init__(self, error: UnievalError) -> None:
        self.error = error
        super().__init__(error.message)
