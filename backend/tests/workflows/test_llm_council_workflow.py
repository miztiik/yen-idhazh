"""Does the judging workflow bound its legs, reuse the daily run's cache, and commit once?

Driven by the committed YAML, never by a live run. Every assertion here is about
a shape a wrong run would only reveal hours later - a leg with no bound dies at
the 6 h ceiling with nothing written, and a second cache key costs a
multi-gigabyte download inside a job that has one.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, REPO_ROOT

from utilities import shard_bound

from ._harness import (
    _job,
    _load_workflows,
    _script,
    _step,
    _steps,
)

pytestmark = pytest.mark.workflow

FILENAME: Final = "llm-council.yml"

#: The knob the leg's bound is read from. Spelled once here and asserted in the
#: file, so a workflow that read a different knob fails rather than bounding the
#: leg by the work shard's clock.
TIMEOUT_KEY: Final = "judge_shard_timeout_minutes"

#: The commit calls, in the order the fold has to make them. Rows first: the
#: record is derived from them, so a record pushed ahead of its own evidence is a
#: record no later reader can reproduce.
COMMIT_ORDER: Final = (
    "state/story-similarity/scored-pairs",
    "state/story-similarity/score-distribution.json",
)


def _judges() -> dict[str, object]:
    return _load_workflows()[FILENAME]


def _named(job: str) -> list[str]:
    return [str(step.get("name") or step.get("uses") or "") for step in _steps(_judges(), job)]


def test_the_leg_reads_its_timeout_from_the_one_file_that_says_so() -> None:
    """The bound is a knob, and the workflow spells no number.

    A literal here would be a second answer to how long a leg may take, and the
    two can disagree - which is exactly what `digest.yml` did for a while, saying
    330 in the file while config said 150.
    """
    bounds = _step(_judges(), "draw", "id", "bounds")
    script = _script(bounds, "the bounds step")

    assert f"backend/utilities/shard_bound.py --key {TIMEOUT_KEY}" in script
    assert not re.search(r"\btimeout-minutes:\s*\d", str(_judges())), (
        "a timeout literal is a second answer to a question config already answers"
    )


def test_the_timeout_travels_as_a_job_output() -> None:
    """`timeout-minutes` resolves from `needs` before the job's first step.

    `steps` is not readable there, so a step output would leave the leg with no
    bound at all - and Actions takes whatever it is handed, so nothing would say
    so until the 6 h ceiling killed the job with nothing written.
    """
    draw = _job(_judges(), "draw")
    judge = _job(_judges(), "judge")
    outputs = draw.get("outputs")

    assert isinstance(outputs, dict)
    assert outputs[TIMEOUT_KEY] == f"${{{{ steps.bounds.outputs.{TIMEOUT_KEY} }}}}"
    assert judge["timeout-minutes"] == f"${{{{ fromJSON(needs.draw.outputs.{TIMEOUT_KEY}) }}}}"


@pytest.mark.parametrize("value", [200.0, "200", 0, -1, True])
def test_an_unreadable_timeout_is_refused_before_the_job_starts(
    value: object, tmp_path: Path
) -> None:
    """A float, a string, a zero and a bool are each a job with no bound.

    `True` is in the list because `isinstance(True, int)` is true in Python, and
    a bound of `True` reaches Actions as `true` - which it cannot read as a
    number. The refusal is `type(value) is not int`, and this is what holds that
    exact spelling shut.
    """
    (tmp_path / "idhazh.json").write_text(
        json.dumps({"run": {TIMEOUT_KEY: value}}), encoding="utf-8", newline="\n"
    )

    with pytest.raises(SystemExit):
        shard_bound.minutes(tmp_path, key=TIMEOUT_KEY)


def test_the_bound_reader_still_answers_its_first_caller() -> None:
    """One reader and one refusal. A second utility would be a second answer."""
    assert shard_bound.minutes(CONFIG_DIR) >= 1
    assert shard_bound.minutes(CONFIG_DIR, key=TIMEOUT_KEY) >= 1


def test_the_weights_key_is_the_string_the_daily_run_writes() -> None:
    """Same key, character for character, once the producing job is normalised.

    A raw text comparison would fail a correct implementation: `digest.yml` reads
    its refs off `needs.plan` and this file off `needs.draw`. What must match is
    everything else, because a second key is a second multi-gigabyte cache entry
    competing for eviction - and it would throw away the only throughput reading
    this feature has, which was taken on these weights.
    """

    def key_of(filename: str, job: str) -> str:
        cache = _step(_load_workflows()[filename], job, "id", "weights")
        with_key = cache.get("with")
        assert isinstance(with_key, dict)
        return re.sub(r"needs\.[a-z_]+\.outputs\.", "needs.<job>.outputs.", str(with_key["key"]))

    assert key_of(FILENAME, "judge") == key_of("digest.yml", "work")


def test_the_leg_fetches_the_draw_before_it_reads_it() -> None:
    """Without the draw a leg has nothing to judge and fails on a missing file."""
    names = _named("judge")
    download = names.index("actions/download-artifact@v8")
    judging = names.index("Judge this leg's pairs")

    assert download < judging


def test_the_matrix_width_is_the_knob_and_not_a_literal() -> None:
    """The draw deals against the same number the matrix runs.

    A literal would let the draw deal four ways while three legs ran, and a
    quarter of the day would go unjudged with nothing saying so.
    """
    strategy = _job(_judges(), "judge").get("strategy")

    assert isinstance(strategy, dict)
    assert strategy["max-parallel"] == "${{ fromJSON(needs.draw.outputs.shards) }}"
    matrix = strategy["matrix"]
    assert isinstance(matrix, dict)
    assert matrix["shard"] == "${{ fromJSON(needs.draw.outputs.matrix) }}"


def test_one_server_per_leg() -> None:
    """Four servers on four logical CPUs does not fit and would not be faster.

    One `llama-server` peaks at 12.57 to 13.16 GiB and reaches 14.31 GiB with the
    leg's python - 96.0 percent of the 16 GB runner, measured 2026-09-08 over
    four captures of run 2026-08-29-3. And this host is slower at 8 threads than
    at 4 at every prompt length.
    """
    starters = [name for name in _named("judge") if name.startswith("Start the")]

    assert starters == ["Start the model"]


def test_a_dead_leg_does_not_cancel_its_siblings() -> None:
    """A leg that runs out of clock costs its pairs for that day and nothing else."""
    strategy = _job(_judges(), "judge").get("strategy")
    fold = _job(_judges(), "fold")

    assert isinstance(strategy, dict)
    # The harness reads the file as text, so a YAML boolean arrives as the word
    # somebody wrote. Comparing to the word is what this file can actually see.
    assert str(strategy["fail-fast"]).lower() == "false"
    assert fold["if"] == "always()"
    assert fold["needs"] == ["draw", "judge"]


def test_no_leg_commits() -> None:
    """Four legs pushing into one union-merged file buys four races and four rebases.

    One fold is one push, so two processes never write one path: no merge driver
    to trust, no union stacking to census afterwards, and no key to settle across
    legs.
    """
    bodies = [
        _script(step, "a judge step") for step in _steps(_judges(), "judge") if "run" in step
    ]

    assert not [body for body in bodies if "commit-and-push.sh" in body]


def test_the_fold_runs_the_two_commit_calls_in_order() -> None:
    """Rows first, then the record, because the record is derived from the rows.

    A record pushed ahead of its own evidence is a record no later reader can
    reproduce.
    """
    calls = [
        _script(step, "a fold step")
        for step in _steps(_judges(), "fold")
        if "run" in step and "commit-and-push.sh" in _script(step, "a fold step")
    ]

    assert len(calls) == 2
    for call, path in zip(calls, COMMIT_ORDER, strict=True):
        assert path in call


def test_only_the_record_carries_refresh_paths() -> None:
    """The fitted row is what this run SAW; the record is what it derived.

    A lost race replays a row onto the new base and rebuilds a derivation. A
    fitted row regenerated against a moved tip would answer a different question
    and overwrite the answer to this one, so it is absent from `REFRESH_PATHS` -
    and so are the judged pairs, for the same reason.
    """
    record = _step(_judges(), "fold", "name", "Commit the record and the line")
    environment = record.get("env")

    assert isinstance(environment, dict)
    refresh = str(environment["REFRESH_PATHS"])
    assert "score-distribution.json" in refresh
    assert "fitted-thresholds" not in refresh
    assert "scored-pairs" not in refresh


def test_every_path_the_fold_stages_exists_in_a_fresh_checkout() -> None:
    """`git add` runs under `set -euo pipefail`, so a missing path aborts the step.

    A path named without a committed file behind it costs every ledger staged
    beside it, on the runner, hours in. It fails here instead.
    """
    staged: list[str] = []
    for step in _steps(_judges(), "fold"):
        if "run" not in step:
            continue
        body = _script(step, "a fold step")
        if "commit-and-push.sh" not in body:
            continue
        after = body.split("commit-and-push.sh", 1)[1]
        staged.extend(word for word in after.split() if word.startswith("state/"))

    assert staged, "the fold stages something"
    missing = [path for path in staged if not (REPO_ROOT / path).exists()]
    assert not missing, f"the fold stages paths a fresh checkout does not have: {missing}"
