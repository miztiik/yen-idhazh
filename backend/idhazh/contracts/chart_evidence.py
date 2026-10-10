"""How many displayed chart figures were derived and have source references?"""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model


class ChartEvidence(Model):
    """Exact figure counts and their rates, shared by decisions and run reports."""

    displayed_values: int = Field(ge=0, strict=True)
    derived_values: int = Field(ge=0, strict=True)
    trusted_values: int = Field(
        ge=0,
        strict=True,
        description="Figures whose source id or every derived input id exists in the source table.",
    )
    derived_value_rate: float | None = Field(ge=0.0, le=1.0)
    trusted_data_ratio: float | None = Field(
        ge=0.0,
        le=1.0,
        description="Source-reference coverage, not a test of numeric or semantic correctness.",
    )

    @classmethod
    def from_counts(cls, *, displayed: int, derived: int, trusted: int) -> Self:
        """Divide exact totals once; an empty denominator has no rate."""
        return cls(
            displayed_values=displayed,
            derived_values=derived,
            trusted_values=trusted,
            derived_value_rate=derived / displayed if displayed else None,
            trusted_data_ratio=trusted / displayed if displayed else None,
        )

    @model_validator(mode="after")
    def _counts_and_rates_agree(self) -> Self:
        if (
            self.derived_values > self.displayed_values
            or self.trusted_values > self.displayed_values
        ):
            raise ValueError("derived and trusted figures must each fit inside displayed figures")
        for name, count, rate in (
            ("derived_value_rate", self.derived_values, self.derived_value_rate),
            ("trusted_data_ratio", self.trusted_values, self.trusted_data_ratio),
        ):
            expected = count / self.displayed_values if self.displayed_values else None
            if rate != expected:
                raise ValueError(f"{name} must equal its count divided by displayed_values")
        return self
