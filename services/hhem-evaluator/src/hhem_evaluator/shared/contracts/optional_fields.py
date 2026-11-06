"""How are omitted fields excluded without advertising null defaults?"""

from pydantic.json_schema import JsonSchemaValue


def is_absent(value: object) -> bool:
    """Omit the internal marker for a field the caller did not supply."""
    return value is None


def omit_default(schema: JsonSchemaValue) -> None:
    """Do not advertise the internal omission marker as a valid input default."""
    schema.pop("default", None)
