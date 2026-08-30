"""The local inference boundary.

Nothing in this package reaches any origin but loopback. Hosted inference is a
project non-goal (`CLAUDE.md` section 0a), and the OpenAI-shaped transport here
exists because it is the format local runtimes already speak - not as a step
towards one.
"""

from idhazh.llm.server import Completion, parse_completion, request_payload, server_argv

__all__ = ["Completion", "parse_completion", "request_payload", "server_argv"]
