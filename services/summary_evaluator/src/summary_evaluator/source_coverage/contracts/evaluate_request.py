"""Which prepared source and summary are accepted without caller or machine metadata?"""

from summary_evaluator.shared.contracts.base import NonblankText
from summary_evaluator.source_coverage.contracts.base import CoverageContract


class CoverageRequest(CoverageContract):
    source_text: NonblankText
    summary_text: NonblankText
