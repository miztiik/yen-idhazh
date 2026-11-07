"""Which dated transient contract identifies the independent coverage method?"""

from typing import Literal

from pydantic import ConfigDict

from summary_evaluator.shared.contracts.base import NativeContract

COVERAGE_VERSION: Literal["2026-11-07"] = "2026-11-07"
CoverageVersion = Literal["2026-11-07"]


class CoverageContract(NativeContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": COVERAGE_VERSION,
            "changelog": [
                {
                    "version": COVERAGE_VERSION,
                    "change": "Declare independent source-coverage contracts.",
                }
            ],
        }
    )
