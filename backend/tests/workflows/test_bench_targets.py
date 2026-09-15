"""What does a bench dispatch measure, and what does it promise not to touch?"""

from __future__ import annotations

import re

import pytest

from ._harness import (
    BENCH_ARTIFACTS,
    BENCH_CACHE_KEY,
    BENCH_CANDIDATE_CONFIG,
    BENCH_CONFIG_STEP,
    BENCH_EMIT_STEP,
    BENCH_RAW_JOB,
    BENCH_RETENTION_DAYS,
    BENCH_SERVER_JOB,
    BENCH_TARGET,
    BUDGETS_EMIT_STEP,
    BUDGETS_JOB,
    CANDIDATE_CONFIG_ACTION,
    COMMIT_SCRIPT,
    MEASUREMENT_TARGETS,
    MODELS_POINTER_KEY,
    PINNED_LLAMA_BUILD,
    _artifact_upload,
    _composite_action_script,
    _declared_dispatch_inputs,
    _expression,
    _job,
    _load_workflows,
    _mapping,
    _needs,
    _normalize_condition,
    _runtime_cache_keys,
    _script,
    _step,
    _steps,
    _string_list,
)

pytestmark = pytest.mark.workflow


def test_the_bench_is_one_target_that_runs_two_arms_in_order() -> None:
    """Raw throughput first, then a real server, and the second waits for the first.

    They are two jobs rather than one because the cheap arm has to be able to
    fail alone: weights that cannot move tokens at all should never cost the
    server arm a runner hour. They are chained rather than parallel because the
    server arm restores the weights entry the raw arm wrote, and because the
    page body needs both halves in one place to be written at all.

    The target list is compared by equality. A sixth measurement path has to be
    written down here before it can exist, which is what stopped this file
    growing one arm per question.
    """
    workflow = _load_workflows()["measure.yml"]
    target = _mapping(_declared_dispatch_inputs(workflow)["target"], "measure.yml target")
    assert set(_string_list(target.get("options"), "target options")) == MEASUREMENT_TARGETS

    for job_name in (BENCH_RAW_JOB, BENCH_SERVER_JOB):
        condition = _normalize_condition(_job(workflow, job_name).get("if"), f"{job_name} if")
        assert condition == f"inputs.target == '{BENCH_TARGET}'", job_name

    assert _needs(workflow, BENCH_RAW_JOB) == ["models"]
    assert _needs(workflow, BENCH_SERVER_JOB) == ["models", BENCH_RAW_JOB], (
        "the server arm waits for the raw arm, or it downloads the weights again"
    )

    keys = dict(_runtime_cache_keys(workflow))
    assert keys == {
        BENCH_RAW_JOB: BENCH_CACHE_KEY,
        BENCH_SERVER_JOB: BENCH_CACHE_KEY,
        BUDGETS_JOB: BENCH_CACHE_KEY,
    }, "one key, written the same way twice, or the restore misses"
    composed = BENCH_CACHE_KEY.replace(
        _expression("needs.models.outputs.candidate_cache_key"), "a" * 64
    ).replace(_expression("env.LLAMA_CPP_BUILD"), PINNED_LLAMA_BUILD)
    assert "${{" not in composed, "every half of the key must resolve"


def test_the_budget_retake_is_its_own_target_and_writes_no_committed_file() -> None:
    """Row #13a. Minutes rather than the bench's hours, and nothing it writes is committed.

    It shares the bench's weights key, so a dispatch that follows a bench pays
    nothing for the bytes. It is a separate target because retaking three token
    counts should not cost a five-hour runner slot, and it waits on `models`
    alone for the same reason.

    The second half is the one that matters. Row #13's rejected option was a
    workflow writing a measurement into a commit, and the load-bearing clause
    was *writing*: this job prints into the run summary and uploads an artifact,
    and a person decides what lands.
    """
    workflow = _load_workflows()["measure.yml"]
    condition = _normalize_condition(_job(workflow, BUDGETS_JOB).get("if"), "budgets if")

    assert condition == "inputs.target == 'budgets'"
    assert _needs(workflow, BUDGETS_JOB) == ["models"], (
        "a retake that waited on the raw bench arm would cost the hours it exists to avoid"
    )

    names = [step.get("name") for step in _steps(workflow, BUDGETS_JOB)]
    assert names.index("Start the tokenizer") < names.index(BUDGETS_EMIT_STEP)
    emit = _step(workflow, BUDGETS_JOB, "name", BUDGETS_EMIT_STEP)
    body = emit.get("run")
    assert isinstance(body, str)
    assert 'cat backend/var/budgets/budgets.md >> "$GITHUB_STEP_SUMMARY"' in body

    for step in _steps(workflow, BUDGETS_JOB):
        script = step.get("run")
        if not isinstance(script, str):
            continue
        for committed in ("git commit", "git push", COMMIT_SCRIPT.name):
            assert committed not in script, (
                f"{BUDGETS_JOB}/{step.get('name')} commits, and a measurement a workflow "
                "committed would be a number a workflow decided"
            )
        for destination in ("docs/", "backend/idhazh/measured.py"):
            assert f"> {destination}" not in script and f">> {destination}" not in script, (
                f"{BUDGETS_JOB}/{step.get('name')} writes into {destination}"
            )


def test_a_bench_artifact_outlives_the_dispatch_that_wrote_it() -> None:
    """Both arms, ninety days each.

    The raw arm used to declare no retention at all and the sweep kept seven
    days. Seven is shorter than the gap between benching a model and deciding
    to adopt it, and the numbers are what the dossier page is pasted from - so
    an expired artifact is a five-hour job re-run for a measurement that was
    already taken. The tree is JSON and text, a few hundred kilobytes against
    the 500 MB ceiling, so the longer retention costs effectively nothing
    (Guardrail #2).
    """
    workflow = _load_workflows()["measure.yml"]
    for job_name, artifact in sorted(BENCH_ARTIFACTS.items()):
        upload = _artifact_upload(workflow, job_name, artifact)
        with_block = _mapping(upload.get("with"), f"{job_name} upload")
        assert int(str(with_block["retention-days"])) == BENCH_RETENTION_DAYS, job_name


def test_the_bench_measures_a_candidate_without_touching_the_committed_config() -> None:
    """A scratch copy differs in the active model file and in nothing else.

    Every control the numbers are read under - prompt, schema, sampler, context,
    threads, truncation cap - is the committed one by construction, because the
    copy is the committed tree with the pointer moved and nothing else touched.
    That is the exact line a swap moves, so the bench runs the swap rather than
    an imitation of it.

    The entry's own fields are the assertion. This step used to write `sha256`,
    `repo`, `revision`, `file`, `id` and `quantisation` onto the copied entry
    and overwrite both `declared_for` digests, which asserted that numbers
    measured for one model held for another.

    The shell moved into a composite action on 2026-09-15, because the bench and
    the validation arm carried byte-identical copies of it. This reads the
    action, and the call site is asserted below.
    """
    workflow = _load_workflows()["measure.yml"]
    step = _step(workflow, BENCH_SERVER_JOB, "name", BENCH_CONFIG_STEP)
    assert step.get("uses") == f"./.github/actions/{CANDIDATE_CONFIG_ACTION}", (
        "the bench builds its scratch config through the shared action"
    )

    script = _composite_action_script(CANDIDATE_CONFIG_ACTION)
    assert f"cp -a config {BENCH_CANDIDATE_CONFIG}" in script
    assert MODELS_POINTER_KEY in script, "through the pointer, never by filename"
    for field in ("sha256", "declared_for", "quantisation", "revision"):
        assert field not in script, (
            f"the scratch config writes {field} onto the entry instead of moving the pointer"
        )

    sweep = _script(
        _step(workflow, BENCH_SERVER_JOB, "name", "Measure runtime candidate"),
        f"measure.yml/{BENCH_SERVER_JOB}/Measure runtime candidate",
    )
    # The property, not the spelling. This assertion used to pin the name
    # `CANDIDATE` for the path, which was also the name the sweep read
    # `RUNTIME_CANDIDATE` into - so the test held the collision in place.
    copied = re.search(r"shutil\.copytree\((\w+), dst\)", sweep)
    assert copied, (
        "the sweep copies the candidate tree; copying `config` would measure the incumbent"
    )
    held = copied.group(1)
    assert f'{held} = Path("{BENCH_CANDIDATE_CONFIG}")' in sweep
    assert f'{held} = os.environ' not in sweep, (
        f"{held} holds the candidate config path and a dispatch input at once"
    )

    for job_name in (BENCH_RAW_JOB, BENCH_SERVER_JOB):
        for step in _steps(workflow, job_name):
            body = step.get("run")
            if not isinstance(body, str):
                continue
            where = f"measure.yml/{job_name}/{step.get('name')}"
            assert not re.search(r">\s*config/", body), f"{where} writes the committed config"
            assert "docs/reference/models" not in body, f"{where} writes a committed page"


def test_the_server_arm_reads_the_raw_arm_and_emits_a_page_to_paste() -> None:
    """The Oracle for this arm. Two artifacts of numbers are a transcription job.

    Emitting the dossier body with the numbers already in it is what makes
    adopting a model a paste. The step runs after the sweep, because half the
    page is what the sweep measured, and it writes under `backend/var` only -
    nothing about a bench reaches a committed file.
    """
    workflow = _load_workflows()["measure.yml"]
    steps = _steps(workflow, BENCH_SERVER_JOB)
    names = [str(step.get("name") or step.get("uses")) for step in steps]

    downloads = [
        step for step in steps if str(step.get("uses", "")).startswith("actions/download-artifact")
    ]
    assert len(downloads) == 1, "the server arm reads one artifact: the raw arm's"
    assert (
        _mapping(downloads[0].get("with"), "download").get("name")
        == BENCH_ARTIFACTS[BENCH_RAW_JOB]
    )

    script = _script(
        _step(workflow, BENCH_SERVER_JOB, "name", BENCH_EMIT_STEP),
        f"measure.yml/{BENCH_SERVER_JOB}/{BENCH_EMIT_STEP}",
    )
    assert "measure_llm.py emit" in script
    assert "--raw backend/var/raw-arm/" in script
    assert "--server backend/var/runtime-sweep/runtime-summary.json" in script
    assert "--dossier backend/var/" in script
    assert names.index("Measure runtime candidate") < names.index(BENCH_EMIT_STEP)
    assert names.index(BENCH_EMIT_STEP) < names.index("Upload runtime sweep")


def test_the_raw_arm_refuses_weights_the_dispatch_did_not_declare() -> None:
    """The raw arm downloads inside Python, so its byte check is a flag not a step.

    `measure_llm.py` resolves the Hub's own digest and compares it with the one
    the dispatch declared before it benches anything. Without the flag the
    harness measures whatever the repository holds today and says nothing, and a
    number filed under a model that never ran is worse than no number
    (Guardrail #10).
    """
    workflow = _load_workflows()["measure.yml"]
    script = _script(
        _step(workflow, BENCH_RAW_JOB, "name", "Benchmark the candidate"),
        f"measure.yml/{BENCH_RAW_JOB}/Benchmark the candidate",
    )
    assert "--expect-sha256" in script
    assert '--expect-sha256 "$CANDIDATE_SHA256"' in script, "read by name, never pasted"
