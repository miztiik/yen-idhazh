"""Which model files will a shell see, and is every field it republishes one bare word?

Three workflows asked this and each carried its own copy of the answer inside a
YAML heredoc: `digest.yml` for the configured entry, `measure.yml` and
`validate.yml` for a dispatched candidate. The copies were never quite the same
- one of them let a draft head declare a file with no digest and fetch it
unchecked, and that survived because ruff never reads a heredoc, mypy never
sees it and no unit test can import it.

**Every value here becomes a shell argument or a download URL downstream.** A
job output is pasted into a command, so this is the one point where a value
carrying a space, a quote or a newline has to stop (`CLAUDE.md` Guardrail #11).
Nothing between here and those commands looks again.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

#: The fields a workflow republishes about the weights it is about to open.
#: `byte_count` is not here because it is a number rather than a bare word, and
#: it is optional besides.
CANDIDATE_FIELDS: tuple[str, ...] = ("repo", "revision", "file", "sha256", "id", "quantisation")

#: What the daily run needs to fetch the configured weights, and no more. It
#: never dispatches a candidate, so it never publishes an alias or a digest.
CONFIGURED_FIELDS: tuple[str, ...] = ("repo", "revision", "file")

#: A draft head is four fields or none. Three is a file fetched against a blank
#: digest, which `sha256sum --check` reports as "no properly formatted checksum
#: lines found" - naming neither the entry nor the field.
DRAFT_FIELDS: tuple[str, ...] = ("repo", "revision", "file", "sha256")

CONFIG_DIRNAME = "config"
POINTER_FILE = "idhazh.json"
POINTER_KEY = "models_file"


def one_bare_word(value: str, *, what: str) -> str:
    """Refuse anything a shell would read as more than one argument.

    `"".split()` is `[]` rather than `[""]`, so an empty value fails this - which
    is right for a field that must be present, and is why an optional block is
    checked only when the block exists.
    """
    if value.split() != [value]:
        raise SystemExit(f"{what} is empty or not one word")
    return value


def _entry(models_path: Path) -> dict[str, Any]:
    models: dict[str, Any] = json.loads(models_path.read_text(encoding="utf-8"))
    summarize: dict[str, Any] = models["summarize"]
    return summarize


def _pointer(repo_root: Path) -> str:
    """Which models file the committed config names. One line, read once."""
    path = repo_root / CONFIG_DIRNAME / POINTER_FILE
    pointer: str = json.loads(path.read_text(encoding="utf-8"))[POINTER_KEY]
    return pointer


def _pointed_at(repo_root: Path) -> Path:
    return repo_root / CONFIG_DIRNAME / _pointer(repo_root)


def _draft_rows(entry: dict[str, Any], names: str, *, prefix: str) -> list[str]:
    """The head's four refs, or four empty strings where the entry declares none.

    `if draft and`, never `if value and`. The looser spelling passed an empty
    field, so an entry naming a `file` with no `sha256` reached the fetch step.
    """
    draft: dict[str, Any] = entry.get("draft") or {}
    rows = []
    for field in DRAFT_FIELDS:
        value = str(draft.get(field) or "")
        if draft:
            one_bare_word(value, what=f"{names}.draft.{field}")
        rows.append(f"{prefix}draft_{field}={value}")
    return rows


def _cache_key(entry: dict[str, Any]) -> str:
    """One key naming every file the candidate needs.

    A key that named only the target would serve a complete-looking cache entry
    with the draft head missing, and the server would fail to start on a hit it
    could not see into. An entry with no head keeps the key it already had, so
    adding the head did not throw away what earlier runs paid to download.
    """
    draft = entry.get("draft") or {}
    key = str(entry["sha256"])
    return f"{key}-{draft['sha256']}" if draft else key


def resolve_under_config(named: str, *, root: Path) -> Path:
    """Prove the named file sits inside `config/` before anything opens it.

    Containment is proved rather than spelled: `..` in a form field is the whole
    reason this resolves the path instead of checking how it is written.
    """
    one_bare_word(named, what="candidate_models_file")
    path = (root / named).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix != ".json" or not path.is_file():
        raise SystemExit(f"candidate_models_file is not a models file under config/: {named}")
    return path


def configured_rows(repo_root: Path, *, with_draft: bool) -> list[str]:
    """The configured entry's refs, and its head where the caller publishes one.

    The daily run needs the head because it fetches it. A measuring dispatch
    publishes the configured refs only as the control it holds against, and
    fetches the candidate's head rather than this one - so it asks for the
    three and would be confused by four more.
    """
    entry = _entry(_pointed_at(repo_root))
    rows = []
    for field in CONFIGURED_FIELDS:
        value = str(entry.get(field) or "")
        one_bare_word(value, what=f"models.summarize.{field}")
        rows.append(f"summarize_{field}={value}")
    if with_draft:
        rows += _draft_rows(entry, "models.summarize", prefix="")
    return rows


def candidate_rows(repo_root: Path, named: str, *, prefix: str) -> list[str]:
    """What a measuring dispatch publishes about the model it was handed.

    One argument, so the two copies of a candidate's facts cannot disagree. A
    form asking for the repository, the commit, the filename, the digest, the
    byte count, the alias and the quantisation asks an operator to retype seven
    facts the candidate's own file already holds - and two copies can differ
    with every gate green.
    """
    config_dir = repo_root / CONFIG_DIRNAME
    pointer = _pointer(repo_root)
    models_file = named.strip() or pointer
    entry = _entry(resolve_under_config(models_file, root=config_dir))

    rows = [f"{prefix}models_file={models_file}"]
    for field in CANDIDATE_FIELDS:
        value = str(entry.get(field) or "")
        one_bare_word(value, what=f"{models_file} summarize.{field}")
        rows.append(f"{prefix}{field}={value}")
    rows.append(f"{prefix}ref={entry['repo']}@{entry['revision']}:{entry['file']}")
    # The entry's own declared size. Empty means nobody has fetched this entry
    # yet, and the cross-check downstream skips rather than refuses.
    rows.append(f"{prefix}byte_count={entry.get('byte_count') or ''}")
    rows += _draft_rows(entry, f"{models_file} summarize", prefix=prefix)
    rows.append(f"{prefix}cache_key={_cache_key(entry)}")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("configured", "candidate"))
    parser.add_argument(
        "--models-file",
        default="",
        help="Models file under config/. Empty reads the configured pointer.",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Prepended to every key, so one job can publish two entries.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path())
    parser.add_argument(
        "--also-configured",
        action="store_true",
        help="Publish the configured entry's refs beside the candidate's.",
    )
    args = parser.parse_args(argv)

    rows: list[str] = []
    if args.mode == "configured":
        rows += configured_rows(args.repo_root, with_draft=True)
    else:
        if args.also_configured:
            rows += configured_rows(args.repo_root, with_draft=False)
        rows += candidate_rows(args.repo_root, args.models_file, prefix=args.prefix)
    sys.stdout.write("\n".join(rows) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
