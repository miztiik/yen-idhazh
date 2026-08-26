"""Shared base types for every persisted shape.

This module is the bottom of the dependency graph: it imports nothing from
`idhazh` outside `idhazh.contracts` (CLAUDE.md section 4). It owns the
`version` date-stamp, the in-schema `changelog`, the invariant that the two
cannot fall out of step, the canonical JSON serialization, and the JSON Schema
emitter that `schemas/` is generated from (CLAUDE.md section 11).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"

# A schema version is a date-stamp, extended to the minute or second when more
# than one revision lands on the same day (CLAUDE.md section 11).
SCHEMA_VERSION_PATTERN: Final = r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?$"
DATE_PATTERN: Final = r"^\d{4}-\d{2}-\d{2}$"
# UTC, second precision, no offset spelling. A payload timestamp leaves the
# process as text, so it is pinned as text: one spelling means a re-serialized
# payload is byte-identical to the one that was read.
TIMESTAMP_PATTERN: Final = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
SLUG_PATTERN: Final = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
# `<vertical>-<NN>`: the reader-facing item address. The digits are derived from
# the address hash, not from a rank position, so the same article keeps the same
# id across every run of the day. At least two, never capped.
ITEM_ID_PATTERN: Final = r"^[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]{2,}$"
# `<YYYY-MM-DD>-<N>`: the run address. Readable, sortable, and free of hashes.
RUN_ID_PATTERN: Final = r"^\d{4}-\d{2}-\d{2}-[0-9]+$"
URL_PATTERN: Final = r"^https?://[^\s\"'<>\\]+$"
SHA256_PATTERN: Final = r"^[0-9a-f]{64}$"
# A full git commit. Nothing shorter is a pin: an abbreviation can become
# ambiguous as a repository grows, and a branch or a tag is re-pointed.
COMMIT_SHA_PATTERN: Final = r"^[0-9a-f]{40}$"
# Relative, POSIX-separated, minimal reconstructable form (CLAUDE.md section 2).
# Spelled as an explicit segment grammar rather than with negative lookahead,
# because the regex engine behind the contracts has no look-around. Each segment
# needs one non-dot character, which is what rules out `.` and `..`; the segment
# alphabet is what rules out a leading `/`, a drive letter and a backslash.
_PATH_SEGMENT: Final = r"[A-Za-z0-9._-]*[A-Za-z0-9_-][A-Za-z0-9._-]*"
REL_PATH_PATTERN: Final = rf"^{_PATH_SEGMENT}(?:/{_PATH_SEGMENT})*$"

SchemaVersion = Annotated[str, StringConstraints(pattern=SCHEMA_VERSION_PATTERN)]
DateStamp = Annotated[str, StringConstraints(pattern=DATE_PATTERN)]
Timestamp = Annotated[str, StringConstraints(pattern=TIMESTAMP_PATTERN)]
Slug = Annotated[str, StringConstraints(pattern=SLUG_PATTERN)]
ItemId = Annotated[str, StringConstraints(pattern=ITEM_ID_PATTERN)]
RunId = Annotated[str, StringConstraints(pattern=RUN_ID_PATTERN)]
Url = Annotated[str, StringConstraints(pattern=URL_PATTERN, max_length=2048)]
Sha256 = Annotated[str, StringConstraints(pattern=SHA256_PATTERN)]
CommitSha = Annotated[str, StringConstraints(pattern=COMMIT_SHA_PATTERN)]
RelPath = Annotated[str, StringConstraints(pattern=REL_PATH_PATTERN, max_length=512)]
UrlKey = Annotated[str, StringConstraints(pattern=SHA256_PATTERN)]

_STEM_PATTERN: Final = re.compile(SLUG_PATTERN)


def derive_url_key(canonical_url: str) -> str:
    """Item identity for dedupe and skip.

    A payload field, never a path segment: paths are for humans and for globs,
    identity is for the contract. It is always recomputed from the canonical
    URL on read rather than trusted from the incoming payload.
    """
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()


def canonical_json(payload: Any) -> str:
    """The one serialization every persisted payload uses.

    Sorted keys and a fixed indent so a re-serialized payload is byte-identical
    to the one that was read, and so a diff shows a changed value rather than a
    reshuffled dict.
    """
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def derive_output_digest(
    summary: str | None, key_points: Sequence[str], *, title: str | None = None
) -> str:
    """What a later run compares against to detect a determinism violation.

    Digests the published words only. A re-run that produced the same text in a
    different wall-clock or token count did not drift, and must not read as if
    it had.

    A null title is left out of the payload rather than digested as null, which
    is what keeps this additive: every digest written before the model wrote
    titles still recomputes to the same value, so no committed payload had to be
    restamped (CLAUDE.md section 11).
    """
    payload: dict[str, Any] = {"key_points": list(key_points), "summary": summary}
    if title is not None:
        payload["title"] = title
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class Model(BaseModel):
    """Base for nested shapes: strict, and closed to unknown keys."""

    model_config = ConfigDict(extra="forbid", validate_default=True, frozen=False)


class ChangelogEntry(Model):
    """One recorded change to a persisted shape."""

    version: SchemaVersion
    change: str
    why: str


class Contract(Model):
    """Base for a top-level persisted document.

    A subclass declares `__schema_stem__` (the `schemas/<stem>.schema.json`
    filename) and `__changelog__` (newest entry first). The document's `version`
    defaults to the newest changelog entry but accepts an older date-stamp, so a
    payload written by an earlier run still validates and a read-side migration
    has something to branch on.
    """

    __schema_stem__: ClassVar[str] = ""
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = ()

    version: SchemaVersion

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        stem = cls.__schema_stem__
        if not _STEM_PATTERN.fullmatch(stem):
            raise TypeError(f"{cls.__name__}.__schema_stem__ must be a slug, got {stem!r}")
        if not cls.__changelog__:
            raise TypeError(f"{cls.__name__}.__changelog__ must carry at least one entry")
        versions = [entry.version for entry in cls.__changelog__]
        if versions != sorted(versions, reverse=True) or len(set(versions)) != len(versions):
            raise TypeError(f"{cls.__name__}.__changelog__ must be newest-first and distinct")

    @model_validator(mode="before")
    @classmethod
    def _stamp_current_version(cls, data: Any) -> Any:
        if isinstance(data, dict) and "version" not in data:
            return {**data, "version": cls.schema_version()}
        return data

    @classmethod
    def schema_version(cls) -> str:
        return cls.__changelog__[0].version

    @classmethod
    def schema_filename(cls) -> str:
        return f"{cls.__schema_stem__}.schema.json"

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """The generated schema document. Never hand-edited (Rule #3)."""
        schema = cls.model_json_schema()
        # A document that omits `version` is stamped with the current one on
        # read, so the schema says optional-with-a-default rather than required.
        # Anything this project writes emits it explicitly.
        schema["properties"]["version"]["default"] = cls.schema_version()
        required = [name for name in schema.get("required", []) if name != "version"]
        if required:
            schema["required"] = required
        else:
            schema.pop("required", None)
        # `$id` is the file's own relative name, not a URL, so an editor's
        # JSON Schema plugin resolves it offline with nothing to 404.
        schema["$schema"] = JSON_SCHEMA_DIALECT
        schema["$id"] = cls.schema_filename()
        schema["version"] = cls.schema_version()
        schema["changelog"] = [entry.model_dump(mode="json") for entry in cls.__changelog__]
        return schema

    @classmethod
    def schema_text(cls) -> str:
        return canonical_json(cls.json_schema())

    @classmethod
    def from_json(cls, text: str) -> Self:
        return cls.model_validate_json(text)

    def to_json(self) -> str:
        return canonical_json(self.model_dump(mode="json"))
