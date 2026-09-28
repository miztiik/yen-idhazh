"""Is the corpus squash due, and how many days of history would it keep?

The history job runs this on a shallow checkout, before any install, so it is the
standard library alone: importing `idhazh` here would cost the cheap path a Python
setup it does not need. It reads two committed files and writes nothing:

    python3 backend/utilities/corpus_squash_due.py     key=value lines for $GITHUB_OUTPUT

`every_days` and `window.value` come from `config/gardener/corpus-squash.json`, the
squash's own declaration, and the day it last ran from `corpus/corpus.meta.json`.
What that file says decides the answer:

| What the file says | The answer |
| --- | --- |
| There is no file | Due. The squash has never run |
| `last_run` is a day, or null | Due once `every_days` have passed that day. Null never ran |
| No `last_run`; `pruned_date` is a day or null | The same, read from `last_run`'s old name |
| Anything else | Exit non-zero and print no `due` |

**A stamp this cannot read is not "due".** The two ways to be wrong are different
sizes. A false "due" rewrites `main` every day: every clone has to be fetched
again and `git blame` loses its range. A false "not due" delays one squash by one
wake. So a key that is missing, a value that is not a day, or a file that is not
JSON ends this program before it prints an answer, and the job stops there.

**`pruned_date` is read here and in `CorpusMeta` alike**, because this program
cannot import the contract. Both prefer `last_run` when a file carries the two,
and a test holds them to the same keys and the same preference. They are removed
together or not at all.

A squash whose declaration is not `active` is never due, forced or not:
`lifecycle_status` is the gardener's off switch, and `dry_run` is not.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

FORCE_ENV = "FORCE"

#: The squash's declaration, under the config root.
DECLARATION = Path("gardener") / "corpus-squash.json"

#: The field the day is read from, then the name it had before.
LAST_RUN_KEY = "last_run"
LEGACY_LAST_RUN_KEY = "pruned_date"

#: The one status that runs.
ACTIVE = "active"

#: A day as the contract spells one, `YYYY-MM-DD`.
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


def _whole_days(name: str, value: object) -> int:
    if type(value) is not int or value < 1:
        raise SystemExit(
            f"config/{DECLARATION.as_posix()}: {name} must be a whole number of days, 1 or more"
        )
    return value


def _declaration(config_root: Path) -> dict[str, object]:
    path = config_root / DECLARATION
    try:
        declared = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"config/{DECLARATION.as_posix()} cannot be read: {error}") from error
    if not isinstance(declared, dict):
        raise SystemExit(f"config/{DECLARATION.as_posix()} is not a JSON object")
    return declared


def _keep_days(declared: dict[str, object]) -> int:
    window = declared.get("window")
    if not isinstance(window, dict) or window.get("unit") != "days":
        raise SystemExit(
            f"config/{DECLARATION.as_posix()}: window must be whole days, {{unit: days, value}}"
        )
    return _whole_days("window.value", window.get("value"))


def _a_day(key: str, value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str) or not DAY.fullmatch(value):
        raise ValueError(f"{key} is {value!r}, which is not a YYYY-MM-DD day")
    return date.fromisoformat(value)


def last_run(meta: object) -> date | None:
    """The day the squash last ran, from the parsed file. None is never.

    Raises `ValueError` for anything that is neither: the answer is missing, or
    it is not a day.
    """
    if not isinstance(meta, dict):
        raise ValueError("the file is not a JSON object")
    for key in (LAST_RUN_KEY, LEGACY_LAST_RUN_KEY):
        if key in meta:
            return _a_day(key, meta[key])
    raise ValueError(f"the file names neither {LAST_RUN_KEY} nor {LEGACY_LAST_RUN_KEY}")


def read_last_run(path: Path) -> date | None:
    """The day the squash last ran, from `corpus/corpus.meta.json`. No file is never."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    return last_run(json.loads(text))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--corpus-meta", type=Path, default=Path("corpus/corpus.meta.json"))
    args = parser.parse_args(argv)

    declared = _declaration(args.config_root)
    every = _whole_days("every_days", declared.get("every_days"))
    keep = _keep_days(declared)
    status = declared.get("lifecycle_status")

    today = datetime.now(tz=UTC).date()
    try:
        last = read_last_run(args.corpus_meta)
    except ValueError as unread:
        raise SystemExit(
            f"{args.corpus_meta.as_posix()} cannot be read: {unread}. No answer is "
            "printed, so the job stops before it can rewrite history on a guess."
        ) from unread

    # Never pruned is always due, and without the stamp this fires again tomorrow
    # and every day after - which is a force-push a day.
    elapsed = None if last is None else (today - last).days
    due = status == ACTIVE and (
        os.environ.get(FORCE_ENV) == "true" or elapsed is None or elapsed >= every
    )

    print(f"due={'true' if due else 'false'}")
    print(f"keep_days={keep}")
    print(f"today={today.isoformat()}")
    print(f"boundary={(today - timedelta(days=keep)).isoformat()}")
    print(f"last_run={last.isoformat() if last else 'never'}")
    print(f"lifecycle_status={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
