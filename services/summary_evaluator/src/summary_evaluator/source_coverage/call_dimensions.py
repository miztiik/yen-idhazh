"""How is the existing callable boundary adapted without replacing its real model or converter?"""

from collections.abc import Callable
from dataclasses import dataclass

from summary_evaluator.source_coverage.contracts.model_call import ConvertInput


@dataclass(frozen=True)
class DimensionBoundary:
    convert_input: ConvertInput
    call: Callable[[list[dict[str, str]], str], list[dict[str, float]]]

    def evaluate_dimension(
        self, data: list[dict[str, str]], dimension: str
    ) -> list[dict[str, float]]:
        return self.call(data, dimension)
