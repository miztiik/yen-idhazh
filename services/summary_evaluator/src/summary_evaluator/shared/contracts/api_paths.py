"""Which fixed first-party paths identify evaluator operations?"""

from typing import Final

HTTP_PROTOCOL_VERSION: Final = "2026-11-05"

API_PREFIX: Final = f"/api/{HTTP_PROTOCOL_VERSION}"

EVALUATE_PATH: Final = f"{API_PREFIX}/evaluate-summary-hhem"

HHEM_HEALTH_PATH: Final = f"{API_PREFIX}/get-hhem-health"

API_HEALTH_PATH: Final = f"{API_PREFIX}/get-summary-evaluator-health"

API_SCHEMA_PATH: Final = f"{API_PREFIX}/get-summary-evaluator-schema"

COVERAGE_EVALUATE_PATH: Final = f"{API_PREFIX}/evaluate-summary-coverage"

COVERAGE_HEALTH_PATH: Final = f"{API_PREFIX}/get-summary-coverage-health"
