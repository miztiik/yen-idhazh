"""The local inference boundary.

The address this package talks to is one committed config value,
`model_server.base_url`. Article text goes only to a model process this run's
operator controls (`CLAUDE.md` Guardrail #11). The OpenAI-shaped transport here
exists because it is the format local runtimes already speak.
"""

from idhazh.llm.server import Completion, parse_completion, request_payload, server_argv

__all__ = ["Completion", "parse_completion", "request_payload", "server_argv"]
