"""Which converted data and genuine dimension results cross the legacy model boundary?"""

from typing import Protocol

from summary_evaluator.source_coverage.contracts.model_identity import CoverageModelIdentity


class ConvertInput(Protocol):
    def __call__(
        self, *, output_list: list[str], src_list: list[str] | None = None
    ) -> list[dict[str, str]]: ...


class CoverageBackend(Protocol):
    @property
    def convert_input(self) -> ConvertInput: ...

    def evaluate_dimension(
        self, data: list[dict[str, str]], dimension: str
    ) -> list[dict[str, float]]: ...


class LegacyEvaluator(Protocol):
    def evaluate(
        self, data: list[dict[str, str]], *, dims: list[str], overall: bool
    ) -> list[dict[str, float]]: ...


class CoverageRuntimeBackend(CoverageBackend, Protocol):
    @property
    def identity(self) -> CoverageModelIdentity: ...
