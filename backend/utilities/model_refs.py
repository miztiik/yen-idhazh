"""Which files does a model declare, and is every value safe to hand to a program?

Every value here is pasted into a workflow `run:` body, where the Actions engine
substitutes it into the text before bash parses the line - so a value spelling
`$(id)` runs and one spelling `../..` escapes the config root. This module is
where such a value stops. It is not a Guardrail #11 question: a model file is
committed and reviewed, not fetched from the web.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn

#: Where a fetched model file lands on a runner. The only spelling of it in the
#: repository: `landed_path` and `weights_path` are composed from it, so a move
#: is one edit rather than nine that have to agree.
MODELS_DIR: Final = "backend/models"

#: The fields a workflow republishes about the weights it is about to open.
CANDIDATE_FIELDS: tuple[str, ...] = ("repo", "revision", "file", "sha256", "id", "quantisation")

#: What the daily run needs to fetch the configured weights. `id` sits beside
#: them rather than among them: it names the alias the server answers under,
#: which is not one of the three facts that decide which bytes arrive.
CONFIGURED_FIELDS: tuple[str, ...] = ("repo", "revision", "file")

#: A companion file is four fields or none. Three is a file fetched against a
#: blank digest, which `sha256sum --check` reports as "no properly formatted
#: checksum lines found" - naming neither the entry nor the field.
COMPANION_FIELDS: tuple[str, ...] = ("repo", "revision", "file", "sha256")

#: What a trial dispatch publishes beyond the fields above, composed here so
#: nothing downstream composes it a second time. The emit path iterates this
#: rather than spelling five appends, so a key cannot appear without a name here.
PUBLISHED_EXTRA: Final = ("models_file", "ref", "byte_count", "cache_key", "weights_path")

#: The same, for the pinned entry the daily run fetches.
CONFIGURED_EXTRA: Final = ("id", "weights_path", "cache_key")

DEFAULT_CONFIG_ROOT: Final = Path("config")
POINTER_FILE = "idhazh.json"
POINTER_KEY = "models_file"

# The grammar. Every pattern keeps its anchors AND is applied with `re.fullmatch`,
# because `$` matches before a trailing newline, so `re.match` admits a value the
# anchors look like they refuse. Nothing here is imported: `measure_llm.py` runs
# both by path in a job with no install and as a package under pytest, and no
# single plain import statement works in both. The three names this shares with
# it are held equal to its own by a test instead.

#: A Hugging Face repository. Equal to `measure_llm.REPO_RE`.
REPO_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
#: The weights file. Equal to `measure_llm.GGUF_RE`.
GGUF_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.gguf$")
#: A full commit. A branch is re-pointed on every upload, so a run that names one
#: cannot be repeated. Equal to `measure_llm.REVISION_RE`.
REVISION_RE: Final = re.compile(r"^[0-9a-f]{40}$")
#: One path segment. A companion carries no suffix rule because it may be a
#: projector, an adapter or a vocoder rather than a second GGUF.
SEGMENT_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
#: A digest, required of the weights and of every companion with no exception.
SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
#: The alias the server answers under. Equal to `idhazh.contracts.base.SLUG_PATTERN`.
SLUG_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
QUANTISATION_RE: Final = re.compile(r"^[A-Za-z0-9_.-]+$")
COUNT_RE: Final = re.compile(r"^[1-9][0-9]*$")
#: A server flag. One dash is legal: llama.cpp's short form for a draft model is
#: `-md`, and the live model's `server` block carries eleven single-dash flags.
FLAG_RE: Final = re.compile(r"^--?[A-Za-z0-9][A-Za-z0-9-]*$")
#: The backstop every value passes last: printable ASCII, no space. A character
#: class rather than `str.isprintable()`, which admits a combining accent and
#: DIVISION SLASH - either builds a hub URL that is not the one a reviewer read.
#: Empty passes, for the two values that are legitimately absent.
PRINTABLE_RE: Final = re.compile(r"^[\x21-\x7E]+$")


@dataclass(frozen=True, slots=True)
class ModelFile:
    """One file a model declares, every value already through its own rule."""

    repo: str
    revision: str
    file: str
    sha256: str
    #: `MODELS_DIR` plus the validated filename. Where this file lands.
    landed_path: str
    #: The server flag this file is passed under. Empty for the weights, which
    #: the launcher names itself rather than reading off config.
    flag: str = ""
    #: The declared size, as the string its rule is stated on. Empty where the
    #: entry declares none, and then the size cross-check downstream skips.
    byte_count: str = ""


@dataclass(frozen=True, slots=True)
class _Declared:
    """One model entry, with the two spellings of the file it came out of."""

    #: What a verb publishes: the proved path, relative to the config root.
    models_file: str
    #: What a refusal names: that path as this process opened it.
    opened: str
    #: Where the name of that file came from, for a refusal to point at.
    named_at: str
    summarize: dict[str, Any]


def _refuse(opened: str, where: str, says: str, value: object) -> NoReturn:
    """Four things in this order: the file, where in it, the rule, the value.

    Never the regex. A reader who wanted a character class would open this file;
    one reading a failed run wants the sentence and the value that broke it.
    """
    raise SystemExit(f"{opened}: {where}:\n  {says}: {value!r}")


def _printable(opened: str, where: str, value: str) -> str:
    """The backstop, applied last to every value that leaves this module.

    Empty passes, because `flag` and `byte_count` are legitimately absent and a
    backstop refusing empty would take the daily run down on the first merge.
    """
    if value and not PRINTABLE_RE.fullmatch(value):
        _refuse(opened, where, "not printable ASCII without spaces", value)
    return value


def _field(
    declared: _Declared,
    block: Mapping[str, Any],
    at: str,
    key: str,
    rule: re.Pattern[str],
    says: str,
    *,
    may_be_empty: bool = False,
) -> str:
    """One declared value against its rule, then against the backstop.

    A JSON number is read as the string that will be emitted, so a declared size
    of `0` is refused rather than read as absent.
    """
    raw = block.get(key)
    value = "" if raw is None else str(raw)
    where = f"{at}.{key}"
    if value:
        if not rule.fullmatch(value):
            _refuse(declared.opened, where, says, value)
    elif not may_be_empty:
        _refuse(declared.opened, where, says, value)
    return _printable(declared.opened, where, value)


def resolve_under_config(named: str, *, root: Path) -> Path:
    """Prove the named file sits inside the config root before anything opens it.

    Containment is proved rather than spelled, and that is stronger than any
    pattern: `..` in a form field is the whole reason this resolves the path
    instead of checking how it is written.

    The refusal names no models file because this value IS the name of one.
    """
    if not PRINTABLE_RE.fullmatch(named):
        raise SystemExit(f"{POINTER_KEY}:\n  not one printable word: {named!r}")
    path = (root / named).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix != ".json" or not path.is_file():
        raise SystemExit(f"candidate_models_file is not a models file under config/: {named}")
    return path


def _declared(config_root: Path, named: str) -> _Declared:
    """The entry a verb was pointed at, and both spellings of where it lives."""
    wanted = named.strip()
    named_at = "candidate_models_file" if wanted else f"{POINTER_FILE}:{POINTER_KEY}"
    if not wanted:
        pointer = config_root / POINTER_FILE
        wanted = str(json.loads(pointer.read_text(encoding="utf-8"))[POINTER_KEY])
    path = resolve_under_config(wanted, root=config_root)
    models_file = path.relative_to(config_root.resolve()).as_posix()
    summarize: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))["summarize"]
    return _Declared(models_file, (config_root / models_file).as_posix(), named_at, summarize)


def _a_file(declared: _Declared, block: Mapping[str, Any], at: str, *, weights: bool) -> ModelFile:
    """One declared file. A companion keeps the segment rule without the suffix."""
    rule, says = (
        (GGUF_RE, "not a .gguf filename") if weights else (SEGMENT_RE, "not one path segment")
    )
    filename = _field(declared, block, at, "file", rule, says)
    return ModelFile(
        repo=_field(declared, block, at, "repo", REPO_RE, "not a Hugging Face repository"),
        revision=_field(declared, block, at, "revision", REVISION_RE, "not a 40-character commit"),
        file=filename,
        sha256=_field(declared, block, at, "sha256", SHA256_RE, "not a 64-character digest"),
        landed_path=f"{MODELS_DIR}/{filename}",
        flag=_field(declared, block, at, "flag", FLAG_RE, "not a server flag", may_be_empty=True),
        byte_count=_field(
            declared, block, at, "byte_count", COUNT_RE, "not a count of bytes", may_be_empty=True
        ),
    )


def _model_files(declared: _Declared) -> list[ModelFile]:
    """The weights, then the companions in declared order.

    Two entries landing on one name is refused here rather than downstream,
    where one file overwrites the other and the digest check then passes on
    whichever was written last.
    """
    entry = declared.summarize
    companions: list[dict[str, Any]] = entry.get("companion_files") or []
    at = ["summarize"]
    at += [f"summarize.companion_files[{index}]" for index in range(len(companions))]
    files = [_a_file(declared, entry, at[0], weights=True)]
    files += [
        _a_file(declared, companion, at[index + 1], weights=False)
        for index, companion in enumerate(companions)
    ]

    landing: dict[str, list[str]] = {}
    for one, where in zip(files, at, strict=True):
        landing.setdefault(one.file, []).append(where)
    for filename, wheres in landing.items():
        if len(wheres) > 1:
            named = " and ".join(f"{where}.file {filename!r}" for where in wheres)
            raise SystemExit(
                f"{declared.opened}: summarize: two files land on one name:\n  {named}"
            )
    return files


def list_model_files(config_root: Path, named: str = "") -> list[ModelFile]:
    """Every file this model declares - the weights first, then the companions.

    The one reader of a model file. Each value has passed its own rule and the
    backstop, so nothing downstream re-parses or re-checks one. An empty `named`
    reads the file the committed pointer names.
    """
    return _model_files(_declared(config_root, named))


def _cache_key(files: Sequence[ModelFile]) -> str:
    """One fixed-width key naming every file the entry declares.

    A key naming only the weights served a complete-looking entry with a
    companion missing, and llama-server exits at load rather than at fetch. A
    digest rather than a join because the join reached 519 characters at seven
    files, past the 512 a cache key may carry.

    `flag` is out of it: that value reaches the server command line, so digesting
    it would throw away several gigabytes over an edit that changed no byte on
    disk. The config root is out too - it is how the files were found, never part
    of what they are, so two roots holding one entry render one key and a trial
    run reads the entry the daily run already paid to download.

    A plain `.encode("ascii")` is safe because every value here has passed its
    field rule and the backstop.
    """
    rows = b"\n".join(
        b"\t".join(part.encode("ascii") for part in (one.repo, one.revision, one.file, one.sha256))
        for one in files
    )
    key = hashlib.sha256(rows).hexdigest()
    if not SHA256_RE.fullmatch(key):
        raise SystemExit(f"the cache key is not a digest:\n  not a 64-character digest: {key!r}")
    return key


def _row(declared: _Declared, prefix: str, key: str, value: str, at: str) -> str:
    """One `KEY=value` line, backstopped last.

    A composed value is reported against the fields it was composed from, which
    is the line an operator edits to fix it.
    """
    return f"{prefix}{key}={_printable(declared.opened, at, value)}"


def _draft_rows(declared: _Declared, files: Sequence[ModelFile], *, prefix: str) -> list[str]:
    """The one companion's four refs, or four empty strings where there is none.

    The keys stay `draft_*` because two workflows read them under those names.
    Delete these four when `digest.yml:99-102`, `:563-566`, `llm-council.yml:80-83`
    and `:315-318` go; nothing else reads them.

    Two companions are refused rather than truncated. This publishes the first
    while the cache key digests all of them, so an entry declaring two keyed on
    two files and fetched one - a complete-looking cache entry with a file
    missing, which is the failure the key exists to prevent.
    """
    companions = files[1:]
    if len(companions) > 1:
        landed = [one.file for one in companions]
        raise SystemExit(
            f"{declared.opened}: summarize.companion_files:\n"
            f"  more than the one companion this publishes ({len(companions)}): {landed!r}"
        )
    companion = companions[0] if companions else None
    return [
        _row(
            declared,
            prefix,
            f"draft_{field}",
            getattr(companion, field) if companion else "",
            f"summarize.companion_files[0].{field}",
        )
        for field in COMPANION_FIELDS
    ]


def _values(declared: _Declared, files: Sequence[ModelFile]) -> dict[str, tuple[str, str]]:
    """Every value a verb may publish, with the field a refusal points at.

    `ref` holds three ruled parts, and its only consumer splits it back on `@`
    and `:` - so those two and `,` must stay outside `REPO_RE`, `REVISION_RE` and
    `GGUF_RE`, or that re-parse mis-splits.
    """
    entry = declared.summarize
    weights = files[0]
    values = {
        field: (getattr(weights, field), f"summarize.{field}")
        for field in ("repo", "revision", "file", "sha256", "byte_count")
    }
    values["id"] = (
        _field(declared, entry, "summarize", "id", SLUG_RE, "not a slug"),
        "summarize.id",
    )
    values["quantisation"] = (
        _field(declared, entry, "summarize", "quantisation", QUANTISATION_RE, "not a quantisation"),
        "summarize.quantisation",
    )
    values["models_file"] = (declared.models_file, declared.named_at)
    values["ref"] = (
        f"{weights.repo}@{weights.revision}:{weights.file}",
        "summarize.repo, summarize.revision and summarize.file",
    )
    values["cache_key"] = (_cache_key(files), "summarize and summarize.companion_files")
    values["weights_path"] = (weights.landed_path, "summarize.file")
    return values


def configured_rows(config_root: Path, *, with_draft: bool) -> list[str]:
    """The pinned entry's refs, and its head where the caller publishes one.

    The daily run needs the head because it fetches it. A measuring dispatch
    publishes the pinned refs only as the control it holds against, and fetches
    the trial entry's head rather than this one - so it asks for the fetch fields
    and would be confused by four more.
    """
    declared = _declared(config_root, "")
    files = _model_files(declared)
    values = _values(declared, files)
    rows = [
        _row(declared, "summarize_", name, *values[name])
        for name in (*CONFIGURED_FIELDS, *CONFIGURED_EXTRA)
    ]
    if with_draft:
        rows += _draft_rows(declared, files, prefix="")
    return rows


def candidate_rows(config_root: Path, named: str, *, prefix: str) -> list[str]:
    """What a measuring dispatch publishes about the model it was handed.

    One argument, so the two copies of a trial entry's facts cannot disagree. A
    form asking for the repository, the commit, the filename, the digest, the
    byte count, the alias and the quantisation asks an operator to retype seven
    facts the entry's own file already holds - and two copies can differ with
    every gate green.
    """
    declared = _declared(config_root, named)
    files = _model_files(declared)
    values = _values(declared, files)
    rows = [
        _row(declared, prefix, name, *values[name])
        for name in (*CANDIDATE_FIELDS, *PUBLISHED_EXTRA)
    ]
    rows += _draft_rows(declared, files, prefix=prefix)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("configured", "candidate"))
    parser.add_argument(
        "--models-file",
        default="",
        help="Models file under the config root. Empty reads the committed pointer.",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Prepended to every key, so one job can publish two entries.",
    )
    parser.add_argument(
        "--config-root",
        type=Path,
        default=DEFAULT_CONFIG_ROOT,
        help="Directory holding the pointer file and the models it names.",
    )
    parser.add_argument(
        "--also-configured",
        action="store_true",
        help="Publish the configured entry's refs beside the candidate's.",
    )
    args = parser.parse_args(argv)

    rows: list[str] = []
    if args.mode == "configured":
        rows += configured_rows(args.config_root, with_draft=True)
    else:
        if args.also_configured:
            rows += configured_rows(args.config_root, with_draft=False)
        rows += candidate_rows(args.config_root, args.models_file, prefix=args.prefix)
    sys.stdout.write("\n".join(rows) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
