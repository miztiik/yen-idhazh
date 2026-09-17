"""Does this dispatch measure the model's raw speed, or skip it?

One question, asked once. `measure.yml` cannot answer it in the job that needs
the answer - a job's own `if:` may not read a step of that job - so the decision
is made in the `models` job and travels as an output. Putting the rule here
rather than in the workflow keeps it out of a `${{ }}` expression nobody can
run, and makes the substitution test something a test can drive: change
`bench.run_model_speed_case` and the answer follows it with no source edit
(CLAUDE.md Guardrail #6).

Prints one `name=value` line for `$GITHUB_OUTPUT`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from idhazh import config

#: What the dispatch input may say. `config` is the default and defers; the
#: other two overrule the knob for one run and nothing else.
FOLLOW_CONFIG = "config"
RUN = "run"
SKIP = "skip"
CHOICES = (FOLLOW_CONFIG, RUN, SKIP)

#: The output name the workflow reads back off the `models` job.
OUTPUT = "model_speed_case"


def decide(dispatch: str, *, configured: bool) -> str:
    """`run` or `skip`, with the dispatch input winning wherever it is set."""
    if dispatch not in CHOICES:
        raise ValueError(f"{OUTPUT} must be one of {', '.join(CHOICES)}, got {dispatch!r}")
    if dispatch != FOLLOW_CONFIG:
        return dispatch
    return RUN if configured else SKIP


def configured(config_root: Path | None) -> bool:
    """`bench.run_model_speed_case`, out of the config tree the dispatch runs on."""
    settings = config.load(config_root) if config_root is not None else config.load()
    return settings.app.bench.run_model_speed_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dispatch",
        default=FOLLOW_CONFIG,
        help=f"What the form said: one of {', '.join(CHOICES)}. Empty means {FOLLOW_CONFIG}.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Config root to read. Omitted reads the committed tree.",
    )
    args = parser.parse_args(argv)
    dispatch = args.dispatch.strip() or FOLLOW_CONFIG
    try:
        answer = decide(dispatch, configured=configured(args.config))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(f"{OUTPUT}={answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
