"""Which strict primitives preserve the existing native wire metadata?"""

import re
from pathlib import PurePosixPath
from typing import Annotated, Final, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictStr, StringConstraints

# Existing native schemas inherit this historical metadata unchanged.
SCHEMA_VERSION = "2026-11-02"
OutcomeStatus = Literal["complete", "partial", "failed"]

ServiceStatus = Literal["disabled", "loading", "ready", "replacing", "stopping", "failed"]

UUID4_PATTERN: Final = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


class NativeContract(BaseModel):
    """Reject undeclared fields and coercion in a frozen native contract."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
        json_schema_extra={
            "version": SCHEMA_VERSION,
            "changelog": [
                {"version": SCHEMA_VERSION, "change": "Declare standalone HHEM service contracts."}
            ],
        },
    )


def validate_uuid4(value: str) -> str:
    """Retain the exact supplied spelling of a hyphenated RFC UUIDv4."""
    if not re.fullmatch(UUID4_PATTERN, value):
        raise ValueError("Expected a hyphenated UUIDv4")
    return value


def validate_text(value: str) -> str:
    """Check nonblank UTF-8 text without changing its bytes."""
    if not value.strip():
        raise ValueError("Text must not be blank")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Text must be valid UTF-8") from None
    return value


def validate_relative_path(value: str) -> str:
    """Accept only a canonical relative POSIX path."""
    path = PurePosixPath(value)
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", value)
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or value == "."
    ):
        raise ValueError("Expected a relative POSIX path without parent traversal")
    return value


Uuid4 = Annotated[str, StringConstraints(strict=True, pattern=UUID4_PATTERN)]

Uuid5 = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    ),
]

Count = Annotated[int, Field(strict=True, ge=0)]

PositiveCount = Annotated[int, Field(strict=True, gt=0)]

Score = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]

Delta = Annotated[float, Field(strict=True, ge=-1, le=1, allow_inf_nan=False)]

Milliseconds = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]

NonblankText = Annotated[
    str, StringConstraints(strict=True, pattern=r"\S"), AfterValidator(validate_text)
]

CommitId = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{40}$")]

Sha256 = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]

ModelReference = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?$",
    ),
]

AssetName = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]

RelativePath = Annotated[StrictStr, AfterValidator(validate_relative_path)]

ContextIdentity = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
]
