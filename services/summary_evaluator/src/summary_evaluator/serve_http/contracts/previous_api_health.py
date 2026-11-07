"""Which saved three-slot health observations can still describe maintained scorers?"""

from pydantic import ConfigDict

from summary_evaluator.serve_http.contracts.api_health import ApiHealth, DisabledEvaluatorHealth


class PreviousApiHealth(ApiHealth):
    """Read a previous observation only when its retired scorer was disabled."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": "2026-11-07",
            "readCompatibility": "read_only; preserve observed shared or independent ownership",
            "changelog": [
                {"version": "2026-11-07", "change": "Read saved health with disabled coverage."}
            ],
        }
    )

    coverage: DisabledEvaluatorHealth
