"""Which local encoder and repository-authored entries classification compares."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    COMMIT_SHA_PATTERN,
    REL_PATH_PATTERN,
    SHA256_PATTERN,
    SLUG_PATTERN,
    Model,
)

RelativePath = Annotated[str, StringConstraints(pattern=REL_PATH_PATTERN)]
FieldName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
GroupId = Annotated[str, StringConstraints(pattern=SLUG_PATTERN)]
Sha256 = Annotated[str, StringConstraints(pattern=SHA256_PATTERN)]


class ComparisonGroup(Model):
    """Select one list of entries without expressions or generated file paths."""

    id: GroupId
    source: Annotated[
        str, StringConstraints(pattern=r"^config/[a-z0-9]+(?:[._-][a-z0-9]+)*\.json$")
    ]
    entries_key: FieldName
    id_field: FieldName
    text_fields: tuple[FieldName, ...] = Field(min_length=1)
    match: dict[FieldName, Annotated[str, StringConstraints(min_length=1)]]
    destination: Literal["desk", "lenses", "events", "entities", "comparison_only"]

    @model_validator(mode="after")
    def refuse_repeated_text_fields(self) -> Self:
        if len(set(self.text_fields)) != len(self.text_fields):
            raise ValueError(f"comparison group {self.id}: text_fields must be unique")
        return self


class ClassificationEncodingConfig(Model):
    """Independent settings; sharing asset bytes does not share search settings."""

    model_id: Annotated[str, StringConstraints(pattern=SLUG_PATTERN)]
    model_revision: Annotated[str, StringConstraints(pattern=COMMIT_SHA_PATTERN)]
    asset_directory: RelativePath
    model_file: RelativePath
    tokenizer_file: RelativePath
    model_digests: dict[RelativePath, Sha256] = Field(min_length=1)
    dimensions: int = Field(ge=1)
    max_tokens: int = Field(ge=1)
    pooling: Literal["attention-mask-mean"]
    normalization: Literal["l2"]
    comparison_groups: tuple[ComparisonGroup, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def refuse_incomplete_assets_and_repeated_groups(self) -> Self:
        for name in (self.model_file, self.tokenizer_file):
            if name not in self.model_digests:
                raise ValueError(f"classification_encoding.model_digests must name {name}")
        if self.model_file == self.tokenizer_file:
            raise ValueError("classification_encoding model_file and tokenizer_file must differ")
        ids = [group.id for group in self.comparison_groups]
        if len(set(ids)) != len(ids):
            raise ValueError("classification_encoding.comparison_groups ids must be unique")
        destinations = [
            group.destination
            for group in self.comparison_groups
            if group.destination != "comparison_only"
        ]
        if len(set(destinations)) != len(destinations):
            raise ValueError("classification_encoding assignment destinations must be unique")
        return self
