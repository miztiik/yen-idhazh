"""Where does a manually selected paused judge run without touching production?"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from pathlib import Path

from idhazh import run_context
from idhazh.council.metrics_sink import checked_slug
from idhazh.council.run_identity import opened_on

# Artifact layout names, not configuration knobs or additional ledger shapes.
TRIALS_DIRNAME = "trials"
_ROOT: ContextVar[Path | None] = ContextVar("council_trial_root", default=None)


def root(council_root: Path, *, run_id: str, judge_id: str) -> Path:
    date.fromisoformat(opened_on(run_id))
    return (
        council_root
        / TRIALS_DIRNAME
        / run_id
        / str(run_context.run_attempt())
        / checked_slug(judge_id)
    )


def scratch(default: Path) -> Path:
    selected = _ROOT.get()
    return default if selected is None else selected / "scratch"


def public_root(default: Path) -> Path:
    """Settlement reads its named downloaded inputs from the isolated trial tree."""
    selected = _ROOT.get()
    return default if selected is None else selected / "frontend" / "public"


@contextmanager
def route(root: Path | None) -> Iterator[None]:
    """Every existing tenant scratch helper sees the same invocation-local root."""
    token = _ROOT.set(root)
    try:
        yield
    finally:
        _ROOT.reset(token)
