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
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, ClassVar, Final, Self, get_args

from annotated_types import MaxLen, MinLen
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StringConstraints,
    ValidationError,
    model_validator,
)
from pydantic.fields import FieldInfo

JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"

# A schema version is a date-stamp, extended to the minute or second when more
# than one revision lands on the same day (CLAUDE.md section 11).
SCHEMA_VERSION_PATTERN: Final = r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?$"
DATE_PATTERN: Final = r"^\d{4}-\d{2}-\d{2}$"
# `<YYYY>-<MM>`: a shard period. The same stem `frontend/public/telemetry/` and
# `frontend/public/scores/` already file by, so a payload that names its own
# month spells it the one way the directories do. It named `state/seen/` until
# 2026-09-13, when that ledger moved to day files - a published mirror's grain
# follows what a browser fetches and a ledger's follows what a run writes, so
# the two came apart and this pattern belongs to the mirrors.
MONTH_PATTERN: Final = r"^\d{4}-\d{2}$"
# UTC, second precision, no offset spelling. A payload timestamp leaves the
# process as text, so it is pinned as text: one spelling means a re-serialized
# payload is byte-identical to the one that was read.
TIMESTAMP_PATTERN: Final = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
SLUG_PATTERN: Final = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
# `<vertical>-<id>`: the reader-facing item address. The trailing field is
# derived from the address hash, not from a rank position, so the same article
# keeps the same id across every run of the day.
#
# Two branches, and this pattern only ever gains one. Decimal digits are what
# every day published before 2026-09-12 carries, and a published day is frozen -
# so the old branch stays for as long as those days do. Sixteen Crockford base32
# symbols are what a run writes now: the alphabet without `i`, `l`, `o` and `u`,
# which is a subset of the slug alphabet, so the id is still a slug.
ITEM_ID_PATTERN: Final = r"^[a-z0-9]+(?:-[a-z0-9]+)*-(?:[0-9]{2,}|[0-9a-hjkmnp-tv-z]{16})$"
# `<YYYY-MM-DD>-<execution>`: the run address. Readable, sortable, free of
# hashes, and unique per execution - the trailing field is the CI run id on
# anything the pipeline produced, and a count of the day's runs only on a
# developer machine, which cannot race itself. It used to be that count
# everywhere, and two overlapping runs read the same answer out of it.
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

# The two CHARACTER-CLASS patterns, and they are a different kind of rule from
# every pattern above. Those name an identity the pipeline mints - a date, a
# digest, an id - so a value that fails one is our own defect and refusing it is
# right. These two name which characters a cell may hold, and a value that fails
# one is a stranger's page or a runtime's own vocabulary arriving as it was
# written. Refusing that loses the row that was reporting the failure, so these
# two are the only patterns `fit_cell` folds a value into and every pattern above
# it leaves alone.
#
# One line of printable ASCII. A newline would break `merge=union` on a day file,
# which resolves line by line, and a control character would break the CSV.
PRINTABLE_LINE_PATTERN: Final = r"^[ -~]+$"
# A lowercase token the pipeline, a runtime or the config minted - a model id, a
# finish reason, a clock name. Never a sentence and never fetched prose.
LOWER_TOKEN_PATTERN: Final = r"^[a-z0-9][a-z0-9_.+-]*$"

#: The name of a pipeline job. Minted here rather than read from anywhere, so it
#: sits with the other identities: a job this repository does not run is not a
#: job a fold should invent a name for.
JOB_NAME_PATTERN: Final = r"^[a-z][a-z0-9_-]*$"

SchemaVersion = Annotated[str, StringConstraints(pattern=SCHEMA_VERSION_PATTERN)]
DateStamp = Annotated[str, StringConstraints(pattern=DATE_PATTERN)]
MonthStamp = Annotated[str, StringConstraints(pattern=MONTH_PATTERN)]
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


def derive_text_digest(text: str) -> str:
    """The one way this project digests a block of text.

    It lives here because a contract may not import the rest of `idhazh`
    (CLAUDE.md section 4), and a payload that rebuilds a text digest on read
    needs the same arithmetic the pipeline used to write it.
    `idhazh.fingerprint.text_digest` is this function under the name the stages
    already call, so the two can never drift into two conventions.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- making a value fit the column that will hold it -------------------------
#
# A helper whose output its own column can refuse is not a sanitizer. Everything
# below reads the rule off the annotated type rather than restating it, so the
# fold and the column cannot disagree and a column whose bound moves takes its
# folder with it (Guardrail #6).

#: Characters outside printable ASCII that carry a plain ASCII meaning, and what
#: that meaning is. These are what a page title actually holds - a typographer's
#: quotes, a dash somebody's CMS substituted, an ellipsis - and each mapping is a
#: spelling change rather than a translation, so nothing here invents a reading.
#: `U+FFFD` is in the table because it is what a decode error leaves behind, and
#: a question mark is the honest thing to put where a byte could not be read.
_ASCII_SPELLINGS: Final[dict[str, str]] = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u2039": "'",
    "\u203a": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u00ab": '"',
    "\u00bb": '"',
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2212": "-",
    "\u2026": "...",
    "\u2022": "*",
    "\u00b7": ".",
    "\u2044": "/",
    "\ufffd": "?",
}

#: A run of characters no ASCII spelling covers. A RUN and not a character: a
#: sentence of Cyrillic becomes one `?` rather than thirty, so the reader sees
#: that something could not be carried without the cell being buried under it.
_UNCARRIED: Final = re.compile(r"[^\x20-\x7e]+")

#: Anything the lowercase-token class does not admit, in runs, for the same
#: reason.
_NOT_TOKEN: Final = re.compile(r"[^a-z0-9_.+-]+")


def fold_to_ascii(text: str) -> str:
    """One line of printable ASCII, keeping every character that has an ASCII spelling.

    Three passes and each one is a different decision. Whitespace collapses
    first, because a newline in a cell splits the row in two under a line-based
    `merge=union` resolve and the CSV quoting that survives a comma does not
    survive that. Then the spellings table and a compatibility decomposition
    carry across everything that has a plain reading - `e-acute` becomes `e`, a
    curly quote becomes a straight one. What is left is replaced rather than
    transliterated: romanising Cyrillic would put an English reading of a Russian
    word into a cell whose whole job is to be evidence, and no reader could tell
    it from a word the page actually carried.
    """
    collapsed = " ".join(text.split())
    spelled = "".join(_ASCII_SPELLINGS.get(character, character) for character in collapsed)
    decomposed = unicodedata.normalize("NFKD", spelled)
    unmarked = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return _UNCARRIED.sub("?", unmarked).strip()


def fold_to_token(text: str) -> str:
    """The same value as a lowercase token, or nothing where no token survives.

    A runtime that reports `Length` and a config that spells a quantisation
    `Q4_K_M` are both writing a name rather than prose, so lowercasing is a
    spelling change and not a loss. A run of anything the class refuses becomes
    one hyphen, and a leading character the class cannot open with is dropped.
    """
    joined = _NOT_TOKEN.sub("-", fold_to_ascii(text).lower()).strip("-")
    return joined.lstrip("_.+-")


def column_bounds(column: Any) -> tuple[str | None, int | None, int | None]:
    """The pattern and the two lengths an annotated string type declares.

    Walks unions and nested `Annotated` forms, so a field declared
    `ItemHealthDetail | None` answers the same as the alias alone. Pass a model
    field through `field_column` first: Pydantic lifts a required field's
    constraints out of its annotation, and an annotation read without them looks
    like a column that declared nothing.
    """
    pattern: str | None = None
    minimum: int | None = None
    maximum: int | None = None

    def walk(node: Any) -> None:
        nonlocal pattern, minimum, maximum
        for part in get_args(node):
            if isinstance(part, StringConstraints):
                # `pattern` is typed to allow a compiled expression. Read its
                # source either way, so a column that compiled its rule is
                # compared against the character classes on the same terms as one
                # that wrote a string - it will not match either, which leaves it
                # classified as an identity and keeps its refusal.
                if part.pattern is not None:
                    pattern = (
                        part.pattern if isinstance(part.pattern, str) else part.pattern.pattern
                    )
                minimum = part.min_length if part.min_length is not None else minimum
                maximum = part.max_length if part.max_length is not None else maximum
            elif isinstance(part, MinLen):
                minimum = part.min_length
            elif isinstance(part, MaxLen):
                maximum = part.max_length
            else:
                walk(part)

    walk(column)
    return pattern, minimum, maximum


def field_column(field: FieldInfo) -> Any:
    """A model field's whole type, its constraints put back in the annotation.

    Pydantic moves a required field's `StringConstraints` into `field.metadata`
    and leaves `field.annotation` as a bare `str`, while an optional field keeps
    them in the annotation because they belong to one member of the union. Reading
    either half alone therefore answers differently for two columns declared the
    same way, and the half that goes quiet is the one that says `url_key` is a
    digest. Re-attaching gives one shape to read.
    """
    if not field.metadata:
        return field.annotation
    return Annotated[(field.annotation, *field.metadata)]


#: The two patterns that name which characters a cell may hold. A column
#: declaring one of these is saying what a value may be MADE OF, which is a
#: question a fold can answer; every other pattern in this module names an
#: identity, which is a question only the producer can answer.
CHARACTER_CLASS_PATTERNS: Final[frozenset[str]] = frozenset(
    {PRINTABLE_LINE_PATTERN, LOWER_TOKEN_PATTERN}
)

#: The patterns `fit_cell` knows how to fold a value into. `None` is here and not
#: above because a column with no pattern still gets the one-line collapse:
#: nothing declares a newline illegal in those cells and `merge=union` still
#: cannot hold one.
FOLDABLE_PATTERNS: Final[frozenset[str | None]] = frozenset({None}) | CHARACTER_CLASS_PATTERNS


def fit_cell(text: str, *, column: Any, absent: str) -> str:
    """The value a column will accept, from a value it might not have.

    `column` is the annotated type the value is going into, so the fold reads the
    character class and the length off the field that will hold it rather than
    restating either (Guardrail #6). `absent` is what a value that folds away to
    nothing becomes - a cell that reached this function had something to say, and
    an empty string would be refused by a `min_length` and would lose the fact
    that a failure happened at all.

    Raises where the column's pattern is not one of `FOLDABLE_PATTERNS`. Those
    patterns name an identity rather than a character class, and a fold that
    tried to satisfy one would invent a digest or a date - so this refuses to
    guess and the caller keeps the refusal it already had.
    """
    pattern, minimum, ceiling = column_bounds(column)
    if pattern not in FOLDABLE_PATTERNS:
        raise ValueError(f"fit_cell cannot fold a value into {pattern!r}; it names an identity")
    folded = fold_to_token(text) if pattern == LOWER_TOKEN_PATTERN else fold_to_ascii(text)
    if ceiling is not None:
        folded = folded[:ceiling].strip()
    if folded and (minimum is None or len(folded) >= minimum):
        return folded
    return absent[:ceiling] if ceiling is not None else absent


def fit_field(text: str, *, model: type[BaseModel], field: str, absent: str) -> str:
    """`fit_cell` against a named field of a model.

    A producer that writes one column says which column, and the rule comes back
    off that column. This is the form to reach for at a construction site: it is
    one line, and it cannot drift from the field the way a restated `[:200]` can.
    """
    return fit_cell(text, column=field_column(model.model_fields[field]), absent=absent)


def fits_its_column(constraints: StringConstraints, *, absent: str) -> BeforeValidator:
    """The validator that makes a string column fit whatever it is handed.

    Every helper above is a door a producer has to find. This is the column
    itself, so there is no door to miss: `fit_cell` runs inside validation, for
    the stage that builds the row, for a re-file that reads an old heading, for a
    test harness and for a writer nobody has written yet.

    **Declare it AFTER the constraints it folds into, and never before.** A
    `BeforeValidator` wraps everything that precedes it in the `Annotated` list,
    so constraints written first are checked second, which is the order that lets
    the fold rescue a value. Written first instead, the constraints become
    predicates over a function schema: the value is checked before the fold can
    reach it, and `pattern` disappears from the generated JSON Schema - which
    would move every `schemas/` file that carries such a column.
    `tests/contracts/test_cell_shapes.py` pins both halves.

    `constraints` is the same object the alias declares, so the bound is written
    once and the fold reads it off the column rather than restating it
    (Guardrail #6). `absent` belongs to the column rather than to the caller: a
    value that folds away to nothing still has to say something was there, and
    letting each producer choose the words is how two producers end up saying it
    differently in one file.

    An empty string is passed through untouched, so `min_length` still decides
    what an empty cell means. A cell that arrived with nothing in it is a reading
    nobody took, which is a different fact from a reading that could not be
    printed, and these columns are nullable for exactly that reason.
    """
    column = Annotated[str, constraints]

    def fold(value: Any) -> Any:
        if not isinstance(value, str) or not value:
            return value
        return fit_cell(value, column=column, absent=absent)

    return BeforeValidator(fold)


def canonical_json(payload: Any) -> str:
    """The one serialization every persisted payload uses.

    Sorted keys and a fixed indent so a re-serialized payload is byte-identical
    to the one that was read, and so a diff shows a changed value rather than a
    reshuffled dict.
    """
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def compact_json(payload: Any) -> str:
    """The same serialization with the whitespace taken out.

    Sorted keys, ASCII-escaped and one trailing newline, exactly as
    `canonical_json` - so a payload that is read and re-written is still
    byte-identical, and the drift gate can still compare bytes. Only the indent
    and the separator spaces are gone.

    A payload uses this when a reader downloads it whole and its entries are
    counted in thousands rather than in tens. Pretty-printing the month search
    index roughly doubles it for whitespace nobody reads, and that index is
    already the largest thing this project asks a browser to fetch. Every other
    persisted payload stays pretty-printed, because being able to review a
    committed diff by eye is worth more than its bytes.
    """
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=True) + "\n"


def _one_line(record: Any) -> str:
    """One record, no newline in it. The space after the colon is the only one kept."""
    return json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ": "))


def _record_lines(value: Any, indent: str) -> str:
    """`canonical_json`'s layout, except that a list of objects is one object a line."""
    step = indent + "  "
    if isinstance(value, dict):
        if not value:
            return "{}"
        pairs = (
            f"{step}{json.dumps(key, ensure_ascii=True)}: {_record_lines(value[key], step)}"
            for key in sorted(value)
        )
        return "{\n" + ",\n".join(pairs) + f"\n{indent}}}"
    if isinstance(value, list):
        if not value:
            return "[]"
        records = all(isinstance(item, dict) for item in value)
        items = (
            step + (_one_line(item) if records else _record_lines(item, step)) for item in value
        )
        return "[\n" + ",\n".join(items) + f"\n{indent}]"
    return json.dumps(value, ensure_ascii=True)


def records_json(payload: Any) -> str:
    """The same serialization with each record on one line.

    Sorted keys, ASCII-escaped, one trailing newline and the same two-space
    indent, exactly as `canonical_json` - so a file that is read and re-written
    is still byte-identical and a diff still shows a changed value rather than
    a reshuffled dict. The one thing that moves is where the newlines go: a
    list of objects is written one object a line, and everything else is
    unchanged.

    A payload uses this when a person curates it by hand and its entries are
    records of a dozen short fields that are read together or not at all. A
    feed in `config/sources.json` is one such record; at one field a line the
    215 of them are 2,391 lines, so comparing two feeds means scrolling past
    everything they agree on and adding one is a twelve-line diff. On one line
    a record the whole record is in view and the diff is one line per feed
    changed. Every other payload keeps the field-a-line layout, because a
    payload a program writes is reviewed by reading down a single record.
    """
    return _record_lines(payload, "") + "\n"


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


def without_retired_keys(data: Any, *keys: str) -> Any:
    """Drop named retired keys from an incoming payload, and nothing else.

    The read-side migration `CLAUDE.md` section 11 owes when a field leaves a
    shape whose older payloads are never rewritten. `extra="forbid"` above is
    what makes it necessary: a key the model no longer declares is refused
    rather than ignored, so a frozen published day stops parsing the day the
    field goes.

    **Named keys only, and that is the whole of the design.** A helper that
    filtered the payload down to the model's own fields would pass every test a
    named popper passes and silently turn `extra="forbid"` into `extra="ignore"`
    for the model it sits on - every future misspelling in every hand-written
    fixture would then parse, carrying none of the value it was meant to carry.
    For the same reason this is a plain function a model opts into rather than a
    validator on `Model` or `Contract`: inherited, it would open all fifty
    contracts to a key only two of them ever held.

    It returns a new mapping. A `mode="before"` validator is handed the caller's
    own dict, so popping in place would take the key out from under a caller
    that still holds it.
    """
    if not isinstance(data, dict):
        return data
    if not any(key in data for key in keys):
        return data
    return {name: value for name, value in data.items() if name not in keys}


class ChangelogEntry(Model):
    """One recorded change to a persisted shape."""

    version: SchemaVersion
    change: str
    why: str


class StalePayloadError(Exception):
    """A run's own payload, read back by a build whose contract has since moved.

    This is not a validation failure, and calling it one is what made the real
    incident unreadable. A payload that fails to parse is normally a defect in
    the payload. This one is exactly what its author meant to write; what moved
    underneath it is the build doing the reading. The two are told apart by the
    date-stamp the payload carries, never by the text of the parser's complaint,
    so a genuine defect still raises `ValidationError` untouched.

    It happens because a run's per-item payloads live for hours. One job writes
    them, later jobs read them, and a contract change can merge in between. They
    are not committed files, so the read-side migration `CLAUDE.md` section 11
    requires does not reach them - see
    `docs/reference/github-actions.md`.

    It carries both stamps and the remedy because the operator's next move is
    not the one a validation error asks for. Nothing about the payload can be
    corrected: the stage that wrote it has to run again under this build.
    """

    def __init__(self, *, contract: str, payload: str, written_under: str, read_by: str) -> None:
        self.contract = contract
        self.payload = payload
        self.written_under = written_under
        self.read_by = read_by
        super().__init__(
            f"{payload} was written under {contract} {written_under} and this build reads "
            f"{contract} {read_by}. The contract moved while the run was in flight, so the "
            f"payload cannot be repaired - re-run the stage that wrote it under this build."
        )


def _payload_name(path: Path) -> str:
    """The payload's address, in the form CLAUDE.md section 2 allows out of a process.

    Relative and POSIX-separated when the file is under the working directory,
    and the bare filename when it is not - which is still the minimal
    reconstructable form, because the run directory is derived from the date.
    """
    try:
        return path.resolve().relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name


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
        """The generated schema document. Never hand-edited (Guardrail #3)."""
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

    @classmethod
    def read(cls, path: Path) -> Self:
        """Read one payload off disk, and name a stale one rather than mis-report it.

        The stamp the payload carries is compared against the one this build
        declares **first**, so which of two conditions this is gets decided by a
        recorded fact rather than by the shape of a parser's complaint. A payload
        stamped with this build's own version raises `ValidationError` exactly as
        it always did - that is a defect and it must not be dressed up. Only a
        payload written under an older contract that this build then cannot read
        becomes `StalePayloadError`, which names both stamps and the remedy.

        Use this wherever a payload one job wrote is read back by another. A
        config file or a committed ledger read at the start of a run cannot
        straddle a contract change, and `from_json` stays the right call there.

        Cover: one payload. Unbounded because there is nothing to bound - this
        reads a single file, never a collection, so the cost follows the payload
        and not the archive. A partial read is not the cheaper answer either: a
        validator cannot pass what it has not read, and half a payload validated
        is a payload reported good on the half that happened to be first.
        """
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Not JSON at all, so there is no stamp to reason about. Hand it to
            # pydantic and let it raise the error it always raised.
            return cls.from_json(text)
        stamp = data.get("version") if isinstance(data, dict) else None
        if not isinstance(stamp, str) or stamp == cls.schema_version():
            return cls.model_validate(data)
        try:
            return cls.model_validate(data)
        except ValidationError as error:
            raise StalePayloadError(
                contract=cls.__name__,
                payload=_payload_name(path),
                written_under=stamp,
                read_by=cls.schema_version(),
            ) from error

    def to_json(self) -> str:
        return canonical_json(self.model_dump(mode="json"))
