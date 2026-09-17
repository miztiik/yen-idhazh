"""What does the bench dispatch hand the sweep, and does it still call it?

The behaviour these used to assert by searching YAML for Python now lives in
`backend/tests/test_sweep_verdict.py`, driven from built readings. What is left
here is the wiring: the call, the values it carries, and the candidate names the
form offers.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from conftest import CONFIG_DIR

from utilities import runtime_sweep

from ._harness import (
    BENCH_SERVER_JOB,
    RUNTIME_CANDIDATES,
    _declared_dispatch_inputs,
    _load_workflows,
    _script,
    _step,
)

pytestmark = pytest.mark.workflow

MEASURE = "measure.yml"
SWEEP_STEP = "Measure runtime candidate"
CORPUS_STEP = "Build the fixed bench corpus"
SWEEP_CALL = "python3 backend/utilities/runtime_sweep.py sweep"
FREEZE_CALL = "python3 backend/utilities/runtime_sweep.py freeze-corpus"
SIZE_CALL = "python3 backend/utilities/runtime_sweep.py corpus-items"


def _body(step_name: str) -> str:
    """One step's shell, read inside the test that asserts on it."""
    workflow = _load_workflows()[MEASURE]
    return _script(
        _step(workflow, BENCH_SERVER_JOB, "name", step_name),
        f"{MEASURE}/{BENCH_SERVER_JOB}/{step_name}",
    )


def test_the_step_calls_the_module_rather_than_carrying_its_own_copy() -> None:
    """A heredoc is not imported, so ruff never reads it and mypy never sees it.

    That is not a style objection. The sweep called `hashlib.sha256` without
    importing `hashlib` for weeks: every bench started a server, summarized
    every article, and then died on the collecting line fifty minutes in.
    """
    script = _body(SWEEP_STEP)

    assert SWEEP_CALL in script
    assert "<<'PY'" not in script, "the sweep is back inside the workflow"


def test_every_value_the_sweep_needs_reaches_it_as_a_named_argument() -> None:
    """A missing one is an argument error in the first second, not an hour in."""
    script = _body(SWEEP_STEP)

    for flag in (
        "--date",
        "--candidate",
        "--candidate-file",
        "--candidate-id",
        "--repeats",
        "--threads",
        "--threads-batch",
        "--gguf-cache-hit",
    ):
        assert f"{flag} " in script, f"the sweep is not told {flag}"

    # The port is not on that list, and is not asserted here either: it reaches
    # the sweep through `LLAMA_PORT`, and the rule that no executed shell may
    # spell a llama-server flag is held once, in test_model_server_jobs.py.
    # Spelling it here would make this file a second speller and fail that rule.


def test_the_corpus_is_frozen_by_the_same_module_that_reads_it() -> None:
    """The addresses are cut once. Which ones is what a repeat may not change."""
    script = _body(CORPUS_STEP)

    assert FREEZE_CALL in script
    assert "<<'PY'" not in script


def test_how_many_articles_the_bench_reads_is_config_and_not_two_literals() -> None:
    """One number, read once, by the module that also freezes the plan.

    Until 2026-09-17 the size was a `--cap 5` literal in the workflow and a
    `CORPUS_ITEMS = 5` constant in the sweep. Nothing held them together, and
    when they disagreed the dispatch died at the freeze step with the plan
    already paid for. The substitution test is the assertion at the bottom:
    change `bench.corpus_items` and the cut follows it, with no source edit
    (Guardrail #6).
    """
    script = _body(CORPUS_STEP)

    assert SIZE_CALL in script, "the workflow asks the module rather than spelling a number"
    assert '--cap "$CORPUS_ITEMS"' in script, "the plan cap is the value it just read"
    assert "--cap 5" not in script and "--cap 3" not in script, "a literal is back"

    committed = runtime_sweep.corpus_items(None)
    assert committed == 3, (
        "three fits the 330-minute job timeout at 236 minutes; five computes to 393.7"
    )


def test_the_repeat_count_is_dispatchable_and_the_floor_is_enforced_in_code() -> None:
    """The repeats multiply the corpus, so an operator moves one of the two.

    A named candidate runs two cases, so three repeats is six passes. At the
    committed three articles that is 236 minutes of a 330-minute job; at five it
    was 393.7 and the job died. The runner budget is GitHub's rather than ours,
    so the design is what gives (CLAUDE.md Guardrail #2) - an operator lowers
    the count or the corpus instead of asking for a longer job. Two is the
    floor, because one reading has no spread.
    """
    assert "runtime_repeats" in _declared_dispatch_inputs(_load_workflows()[MEASURE])
    assert "--repeats " in _body(SWEEP_STEP)

    with pytest.raises(SystemExit, match="at least 2"):
        runtime_sweep.main(
            [
                "sweep",
                "--date",
                "2026-09-15",
                "--candidate",
                "baseline",
                "--candidate-file",
                "w.gguf",
                "--candidate-id",
                "m",
                "--repeats",
                "1",
                "--threads",
                "4",
                "--threads-batch",
                "4",
            ]
        )


def test_the_draft_head_is_a_case_the_bench_can_pair_on_one_machine() -> None:
    """Two dispatches landed on two processors and answered nothing.

    On 2026-09-15 the cases differed by 5.3 percent across runs while the same
    `llama-bench` decode test on the same weights differed by 8.8 percent
    between two machines both reporting EPYC 7763. A paired case cancels the
    machine, and needs no second download because both open the same weights.
    """
    assert "no_draft" in RUNTIME_CANDIDATES

    update, workers = runtime_sweep.candidate_update("no_draft", threads=4, threads_batch=4)

    assert update == {"draft": None}
    assert workers == 1


def test_every_candidate_the_form_offers_is_one_the_sweep_knows() -> None:
    """A name in the dropdown the module refuses is an hour spent to reach a typo."""
    for name in sorted(RUNTIME_CANDIDATES):
        runtime_sweep.candidate_update(name, threads=4, threads_batch=4)

    with pytest.raises(SystemExit, match="unknown runtime candidate"):
        runtime_sweep.candidate_update("no-such-case", threads=4, threads_batch=4)


def test_a_case_that_changes_the_draft_head_reaches_outside_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`draft` is a sibling of `inference`, not a knob inside it.

    Applying it to `inference` writes a key the models contract refuses, so the
    case would die on a validation error rather than measure anything. It is
    written rather than indexed because an entry that declares no draft head
    has no such key to index.
    """
    scratch = tmp_path / "candidate-config"
    shutil.copytree(CONFIG_DIR, scratch)
    monkeypatch.setattr(runtime_sweep, "CANDIDATE_CONFIG", scratch)
    monkeypatch.setattr(runtime_sweep, "CONFIG_ROOT", tmp_path / "configs")

    written = runtime_sweep.write_config("no_draft-1", {"draft": None})

    pointer = json.loads((written / "idhazh.json").read_text(encoding="utf-8"))["models_file"]
    entry = json.loads((written / pointer).read_text(encoding="utf-8"))["summarize"]
    assert entry["draft"] is None
    assert "draft" not in entry["inference"], "the patch went to inference and would be refused"
