"""How are named same-run results bounded, validated and atomically replaced?"""

from pathlib import Path

from pydantic import BaseModel, ValidationError

from .failures import WorkflowError


def write_result(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value.model_dump_json(), encoding="utf-8")
    temporary.replace(path)


def read_result[Result: BaseModel](path: Path, contract: type[Result], limit: int) -> Result:
    try:
        with path.open("rb") as stream:
            encoded = stream.read(limit + 1)
        if len(encoded) > limit:
            raise ValueError("Oversized same-run result")
        return contract.model_validate_json(encoded)
    except (OSError, ValueError, ValidationError):
        raise WorkflowError("RECEIPT_INVALID", "input") from None
