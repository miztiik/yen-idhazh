"""Does the history job's due check tell the four states of its stamp apart?

`backend/utilities/corpus_squash_due.py` is the gate in front of the one job that
force-pushes `main`. It runs on a shallow checkout before any install, and its
`due` line decides whether that job takes a full clone and rewrites history.
Each case runs it the way the job does - a fresh interpreter, the checkout's two
files, stdout read as step outputs - against a checkout built in a temporary
folder.

**The last case is the one that protects the force push.** A stamp the check
cannot read must end it with no `due` printed at all, because the job reads a
missing line as "not due" and a wrong one as a daily rewrite of `main`.

Every stamp is a day far in the past or far in the future, so no case depends on
the day it runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ._harness import SQUASH_DUE_MODULE

pytestmark = pytest.mark.workflow

#: Long enough ago that any cadence has passed it.
LONG_AGO = "2000-01-01"

#: Far enough ahead that no cadence has passed it on any day this suite runs.
FAR_AHEAD = "2999-12-31"


def a_declaration(**changes: Any) -> dict[str, Any]:
    """The squash's declaration as the history job reads it, with some keys changed."""
    return {
        "dry_run": False,
        "every_days": 30,
        "kind": "history",
        "lifecycle_status": "active",
        "max_deletes_per_run": None,
        "owns": ["corpus"],
        "window": {"unit": "days", "value": 60},
    } | changes


def a_checkout(tmp_path: Path, meta: str | None, **declared: Any) -> Path:
    """The two files the job's shallow checkout gives the check, and nothing else."""
    config = tmp_path / "config" / "gardener"
    config.mkdir(parents=True)
    (config / "corpus-squash.json").write_text(
        json.dumps(a_declaration(**declared)), encoding="ascii"
    )
    if meta is not None:
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "corpus.meta.json").write_text(meta, encoding="ascii")
    return tmp_path


def ask(checkout: Path, *, force: bool = False) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if name != "FORCE"}
    if force:
        env["FORCE"] = "true"
    return subprocess.run(
        [sys.executable, str(SQUASH_DUE_MODULE)],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def answered(done: subprocess.CompletedProcess[str]) -> dict[str, str]:
    """The step outputs the job would read, from a check that answered."""
    assert done.returncode == 0, done.stderr
    return dict(line.split("=", 1) for line in done.stdout.splitlines())


def meta(**fields: Any) -> str:
    return json.dumps({"rows": 0, "version": "2026-09-28", **fields})


def test_no_file_has_never_run_and_is_due(tmp_path: Path) -> None:
    outputs = answered(ask(a_checkout(tmp_path, None)))
    assert (outputs["due"], outputs["last_run"]) == ("true", "never")


@pytest.mark.parametrize(("last", "due"), [(LONG_AGO, "true"), (FAR_AHEAD, "false")])
def test_a_last_run_is_compared_with_every_days(tmp_path: Path, last: str, due: str) -> None:
    outputs = answered(ask(a_checkout(tmp_path, meta(last_run=last))))
    assert (outputs["due"], outputs["last_run"]) == (due, last)


def test_null_is_the_contract_saying_never_run(tmp_path: Path) -> None:
    """A harvest before any squash writes null, and the first run's record replaces it."""
    outputs = answered(ask(a_checkout(tmp_path, meta(last_run=None))))
    assert (outputs["due"], outputs["last_run"]) == ("true", "never")


@pytest.mark.parametrize(
    "text",
    [
        meta(),
        meta(last_run="yesterday"),
        meta(last_run=20260830),
        meta(last_run="2026-13-45"),
        meta(last_run="20260830"),
        meta(pruned_date=FAR_AHEAD),
        "{not json",
        "[]",
    ],
    ids=[
        "no-last-run",
        "a-word",
        "a-number",
        "not-a-calendar-day",
        "not-the-contract-spelling",
        "only-the-old-name",
        "not-json",
        "not-an-object",
    ],
)
@pytest.mark.parametrize("force", [False, True], ids=["scheduled", "forced"])
def test_a_stamp_it_cannot_read_ends_the_check_with_no_due(
    tmp_path: Path, text: str, force: bool
) -> None:
    """The assertion that protects the force push. Forcing the run does not force a guess."""
    done = ask(a_checkout(tmp_path, text), force=force)
    assert done.returncode != 0
    assert "due=" not in done.stdout, done.stdout
    assert "cannot be read" in done.stderr, done.stderr


def test_a_forced_run_is_due_whatever_the_stamp_says(tmp_path: Path) -> None:
    outputs = answered(ask(a_checkout(tmp_path, meta(last_run=FAR_AHEAD)), force=True))
    assert outputs["due"] == "true"


@pytest.mark.parametrize("status", ["paused", "retired"])
@pytest.mark.parametrize("force", [False, True], ids=["scheduled", "forced"])
def test_a_squash_that_is_not_active_is_never_due(
    tmp_path: Path, status: str, force: bool
) -> None:
    """`lifecycle_status` is the off switch, and a forced run does not turn it back on."""
    checkout = a_checkout(tmp_path, meta(last_run=LONG_AGO), lifecycle_status=status)
    outputs = answered(ask(checkout, force=force))
    assert (outputs["due"], outputs["lifecycle_status"]) == ("false", status)


def test_the_window_it_keeps_is_the_declarations_and_counted_from_today(tmp_path: Path) -> None:
    outputs = answered(ask(a_checkout(tmp_path, None, window={"unit": "days", "value": 45})))
    assert outputs["keep_days"] == "45"
    today, boundary = date.fromisoformat(outputs["today"]), date.fromisoformat(outputs["boundary"])
    assert (today - boundary).days == 45


@pytest.mark.parametrize(
    "declared",
    [
        {"window": {"unit": "months", "value": 2}},
        {"window": {"unit": "days", "value": 0}},
        {"every_days": 0},
        {"every_days": "30"},
    ],
    ids=["a-month-window", "a-zero-window", "a-zero-cadence", "a-cadence-in-quotes"],
)
def test_a_declaration_it_cannot_count_ends_the_check_with_no_due(
    tmp_path: Path, declared: dict[str, Any]
) -> None:
    done = ask(a_checkout(tmp_path, meta(last_run=LONG_AGO), **declared))
    assert done.returncode != 0
    assert "due=" not in done.stdout, done.stdout
