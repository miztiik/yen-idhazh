"""Is a prune due, and what range would it collapse?

Standard library only: `prune.yml` runs this before any install, so importing
`idhazh` here would cost the cheap path a Python setup it does not need.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

FORCE_ENV = "FORCE"


def _whole_days(name: str, value: object) -> int:
    if type(value) is not int or value < 1:
        raise SystemExit(f"finetune.{name} must be a whole number of days, 1 or more")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--corpus-meta", type=Path, default=Path("corpus/corpus.meta.json"))
    args = parser.parse_args(argv)

    settings = json.loads((args.config_root / "idhazh.json").read_text(encoding="utf-8"))
    finetune = settings["finetune"]
    every = _whole_days("prune_every_days", finetune["prune_every_days"])
    keep = _whole_days("prune_keep_days", finetune["prune_keep_days"])

    today = datetime.now(tz=UTC).date()
    try:
        last = json.loads(args.corpus_meta.read_text(encoding="utf-8")).get("pruned_date")
    except FileNotFoundError:
        last = None

    # Never pruned is always due, and without the stamp this fires again tomorrow
    # and every day after - which is a force-push a day.
    elapsed = None if last is None else (today - date.fromisoformat(last)).days
    due = os.environ.get(FORCE_ENV) == "true" or elapsed is None or elapsed >= every

    print(f"due={'true' if due else 'false'}")
    print(f"keep_days={keep}")
    print(f"today={today.isoformat()}")
    print(f"boundary={(today - timedelta(days=keep)).isoformat()}")
    print(f"last_prune={last or 'never'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
