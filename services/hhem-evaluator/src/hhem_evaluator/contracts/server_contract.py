"""Which current schema identifies shared API settings and diagnostics?"""

from typing import Final, Literal

from pydantic import ConfigDict

from .base import NativeContract

SERVER_SCHEMA_VERSION: Final = "2026-11-03"
ServerSchemaVersion = Literal["2026-11-03"]


class ServerContract(NativeContract):
    """Keep shared-server contracts separate from unchanged scoring packets."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": SERVER_SCHEMA_VERSION,
            "changelog": [
                {
                    "version": SERVER_SCHEMA_VERSION,
                    "change": "Compose local HHEM and native llama APIs with safe diagnostics.",
                }
            ],
        }
    )
