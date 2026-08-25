"""Contract tests for GitHub Actions display names and event routing."""

from __future__ import annotations

import re
from typing import Final, cast

import yaml  # type: ignore[import-untyped]
from conftest import REPO_ROOT, read_text

WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"

EXPECTED_WORKFLOWS: Final = {
    "ci.yml": ("CI", frozenset({"pull_request", "push", "workflow_dispatch"})),
    "digest.yml": ("Content refresh", frozenset({"schedule", "workflow_dispatch"})),
    "drift.yml": ("Drift review", frozenset({"schedule", "workflow_dispatch"})),
    "measure.yml": ("Measurements", frozenset({"workflow_dispatch"})),
    "pages.yml": (
        "Pages publication",
        frozenset({"push", "workflow_run", "workflow_dispatch"}),
    ),
    "validate.yml": ("Model validation", frozenset({"workflow_dispatch"})),
}

CONTENT_REFRESH_CRON: Final = "20 2,6,10,14,18 * * *"
CONTENT_REFRESH_UTC_HOURS: Final = (2, 6, 10, 14, 18)
CONTENT_REFRESH_SHARDS: Final = frozenset({"1", "2", "3", "4"})

# Every major below was read from its own `action.yml` on 2026-08-24 and declares
# `using: node24`. `upload-pages-artifact@v5` is composite and pins a Node 24
# `upload-artifact`, so it carries no Node 20 of its own.
APPROVED_ACTION_MAJORS: Final = {
    "actions/cache": "v6",
    "actions/checkout": "v6",
    "actions/configure-pages": "v6",
    "actions/deploy-pages": "v5",
    "actions/download-artifact": "v8",
    "actions/setup-node": "v7",
    "actions/setup-python": "v7",
    "actions/upload-artifact": "v7",
    "actions/upload-pages-artifact": "v5",
}
# One llama.cpp build for the pipeline, the validation arm and the measurement
# harness. The sha256 was read from the release API's own `digest` field and
# confirmed by downloading the 16,377,727-byte archive and hashing it, on
# 2026-08-25.
PINNED_LLAMA_BUILD: Final = "b10598"
PINNED_LLAMA_ASSET: Final = f"llama-{PINNED_LLAMA_BUILD}-bin-ubuntu-x64.tar.gz"
PINNED_LLAMA_SHA256: Final = "d77a09db4165f8850b513629ed0ffeaab7851bb03e7cc3870b74e721f894694c"
LLAMA_RUNTIME_WORKFLOWS: Final = frozenset({"digest.yml", "measure.yml", "validate.yml"})
LLAMA_DIGEST_CHECK: Final = 'echo "${LLAMA_CPP_SHA256}  llama.tar.gz" | sha256sum --check'
LLAMA_PINNED_ENDPOINT: Final = (
    "https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/${LLAMA_CPP_BUILD}"
)
MEASUREMENT_TARGETS: Final = frozenset({"llm", "image", "corpus", "runtime"})
RUNTIME_CANDIDATES: Final = frozenset(
    {
        "baseline",
        "np1",
        "batch2048",
        "no_startup_warmup",
        "flash_attention_on",
        "load_mode_mmap_mlock",
        "kv_q8",
        "prio_poll",
        "threads",
        "threads_batch",
        "np2_inflight",
    }
)


def _load_workflows() -> dict[str, dict[str, object]]:
    paths = sorted((*WORKFLOWS_DIR.glob("*.yml"), *WORKFLOWS_DIR.glob("*.yaml")))
    assert {path.name for path in paths} == set(EXPECTED_WORKFLOWS)

    workflows: dict[str, dict[str, object]] = {}
    for path in paths:
        document = yaml.load(read_text(path), Loader=yaml.BaseLoader)
        assert isinstance(document, dict), f"{path.name} must contain a YAML mapping"
        workflows[path.name] = cast(dict[str, object], document)
    return workflows


def _triggers(workflow: dict[str, object]) -> dict[str, object]:
    triggers = workflow.get("on")
    assert isinstance(triggers, dict), "workflow 'on' must contain a YAML mapping"
    return cast(dict[str, object], triggers)


def _mapping(value: object, description: str) -> dict[str, object]:
    assert isinstance(value, dict), f"{description} must contain a YAML mapping"
    return cast(dict[str, object], value)


def _string_list(value: object, description: str) -> list[str]:
    assert isinstance(value, list), f"{description} must contain a YAML list"
    assert all(isinstance(item, str) for item in value), f"{description} must contain strings"
    return cast(list[str], value)


def _dispatch_inputs(workflow: dict[str, object]) -> dict[str, object]:
    dispatch = _mapping(_triggers(workflow).get("workflow_dispatch"), "workflow_dispatch")
    return _mapping(dispatch.get("inputs"), "workflow_dispatch inputs")


def _job(workflow: dict[str, object], name: str) -> dict[str, object]:
    jobs = _mapping(workflow.get("jobs"), "jobs")
    return _mapping(jobs.get(name), f"job {name}")


def _steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    raw_steps = _job(workflow, job_name).get("steps")
    assert isinstance(raw_steps, list), f"job {job_name} steps must contain a YAML list"
    assert all(isinstance(step, dict) for step in raw_steps), f"job {job_name} steps must be mappings"
    return cast(list[dict[str, object]], raw_steps)


def _step(
    workflow: dict[str, object], job_name: str, key: str, value: str
) -> dict[str, object]:
    matches = [step for step in _steps(workflow, job_name) if step.get(key) == value]
    assert len(matches) == 1, f"job {job_name} must have one step with {key}={value}"
    return matches[0]


def _action_references(workflow: dict[str, object]) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    for job_name in _mapping(workflow.get("jobs"), "jobs"):
        for step in _steps(workflow, job_name):
            uses = step.get("uses")
            if uses is None:
                continue
            assert isinstance(uses, str), f"job {job_name} 'uses' must be a string"
            references.append((job_name, uses))
    return references


def _evaluate_shard_matrix(script: str, requested_shards: str) -> list[int] | None:
    lines = [line.strip() for line in script.splitlines()]
    default_line = '[ -n "$SHARDS" ] || SHARDS=4'
    pattern_line = "SHARD_PATTERN='^[1-4]$'"
    guard_block = [
        'if ! [[ "$SHARDS" =~ $SHARD_PATTERN ]]; then',
        'echo "shards must be an integer from 1 through 4" >&2',
        "exit 1",
        "fi",
    ]
    matrix_line = (
        'echo "matrix=$(seq 0 $((SHARDS - 1)) | jq -R . | jq -sc .)" '
        '>> "$GITHUB_OUTPUT"'
    )

    assert lines.count(default_line) == 1
    assert [line for line in lines if line.startswith("SHARD_PATTERN=")] == [pattern_line]
    assert [line for line in lines if line.startswith('echo "matrix=')] == [matrix_line]
    guard_index = lines.index(guard_block[0])
    assert lines[guard_index : guard_index + len(guard_block)] == guard_block
    assert lines.index(default_line) < lines.index(pattern_line) < guard_index < lines.index(matrix_line)

    default_match = re.fullmatch(r'\[ -n "\$SHARDS" \] \|\| SHARDS=(\d+)', default_line)
    pattern_match = re.fullmatch(r"SHARD_PATTERN='([^']+)'", pattern_line)
    assert default_match is not None
    assert pattern_match is not None
    shards = requested_shards or default_match.group(1)
    if re.fullmatch(pattern_match.group(1), shards) is None:
        return None
    return list(range(int(shards)))


def _normalize_condition(value: object, description: str) -> str:
    assert isinstance(value, str), f"{description} must be a string"
    condition = value.strip()
    wrapper = re.fullmatch(r"\$\{\{\s*(.*?)\s*\}\}", condition, flags=re.DOTALL)
    if wrapper is not None:
        condition = wrapper.group(1)
    return " ".join(condition.split())


def _llama_fetch_scripts(workflow: dict[str, object]) -> list[tuple[str, object, str]]:
    return [
        (job_name, step.get("name"), script)
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if isinstance(script := step.get("run"), str)
        and "ggml-org/llama.cpp/releases" in script
    ]


def _runtime_cache_keys(workflow: dict[str, object]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for job_name in _mapping(workflow.get("jobs"), "jobs"):
        for step in _steps(workflow, job_name):
            uses = step.get("uses")
            if not (isinstance(uses, str) and uses.startswith("actions/cache@")):
                continue
            with_block = _mapping(step.get("with"), f"job {job_name} cache 'with'")
            path = with_block.get("path")
            assert isinstance(path, str), f"job {job_name} cache path must be a string"
            if "backend/bin" not in path:
                continue
            key = with_block.get("key")
            assert isinstance(key, str), f"job {job_name} cache key must be a string"
            keys.append((job_name, key))
    return keys


def test_workflow_names_and_trigger_classes_are_pinned() -> None:
    workflows = _load_workflows()

    for filename, (display_name, trigger_classes) in EXPECTED_WORKFLOWS.items():
        workflow = workflows[filename]
        assert workflow.get("name") == display_name
        assert set(_triggers(workflow)) == trigger_classes


def test_content_refresh_runs_at_the_five_approved_utc_hours() -> None:
    workflows = _load_workflows()
    schedule = _triggers(workflows["digest.yml"])["schedule"]

    assert schedule == [{"cron": CONTENT_REFRESH_CRON}]
    assert tuple(int(hour) for hour in CONTENT_REFRESH_CRON.split()[1].split(",")) == (
        CONTENT_REFRESH_UTC_HOURS
    )


def test_expensive_workflows_do_not_run_on_pull_request_or_push() -> None:
    workflows = _load_workflows()

    for filename in ("digest.yml", "measure.yml", "validate.yml"):
        assert {"pull_request", "push"}.isdisjoint(_triggers(workflows[filename]))


def test_ci_and_pages_keep_their_push_boundaries() -> None:
    workflows = _load_workflows()

    assert _triggers(workflows["ci.yml"])["push"] == {"branches": ["main"]}
    pages = _triggers(workflows["pages.yml"])
    pages_push = cast(dict[str, object], pages["push"])
    assert set(pages_push) == {"branches", "paths"}
    assert pages_push["branches"] == ["main"]
    assert frozenset(cast(list[str], pages_push["paths"])) == frozenset(
        {"frontend/**", "config/idhazh.json", "state/**"}
    )
    assert pages["workflow_run"] == {
        "workflows": ["Content refresh"],
        "types": ["completed"],
    }


def test_content_refresh_has_four_total_work_shards_at_most() -> None:
    workflow = _load_workflows()["digest.yml"]
    shards = _mapping(_dispatch_inputs(workflow).get("shards"), "shards input")
    options = _string_list(shards.get("options"), "shards options")

    assert shards.get("type") == "choice"
    assert shards.get("default") == "4"
    assert len(options) == len(CONTENT_REFRESH_SHARDS)
    assert frozenset(options) == CONTENT_REFRESH_SHARDS

    strategy = _mapping(_job(workflow, "work").get("strategy"), "work strategy")
    assert strategy.get("max-parallel") == "4"


def test_content_refresh_decide_step_caps_total_jobs_by_behavior() -> None:
    workflow = _load_workflows()["digest.yml"]
    decide = _step(workflow, "plan", "id", "decide")
    script = decide.get("run")
    assert isinstance(script, str)

    expected = {
        "": [0, 1, 2, 3],
        "1": [0],
        "2": [0, 1],
        "3": [0, 1, 2],
        "4": [0, 1, 2, 3],
    }
    for requested_shards, matrix in expected.items():
        assert _evaluate_shard_matrix(script, requested_shards) == matrix
    for invalid_shards in ("0", "5", "10", "-1", "1.5", "text"):
        assert _evaluate_shard_matrix(script, invalid_shards) is None


def test_no_rebase_in_the_daily_run_starts_on_a_dirty_tree() -> None:
    """A rebase that refuses to start throws away a day the run already computed.

    Run `32671663130` died exactly this way: one tracked file was modified in the
    checkout before any step ran, and the retry loop lost plan, four shards and
    assemble with it. The work is committed before the loop begins, so the fix is
    to drop what is left rather than to carry it into the rebase.
    """
    workflow = _load_workflows()["digest.yml"]
    jobs = _mapping(workflow.get("jobs"), "jobs")

    scripts = [
        (job_name, step.get("name"), script)
        for job_name in jobs
        for step in _steps(workflow, job_name)
        if isinstance(script := step.get("run"), str) and "git pull --rebase" in script
    ]
    assert scripts, "digest.yml must still push through a rebase-and-retry loop"

    for job_name, step_name, script in scripts:
        where = f"{job_name}/{step_name}"
        lines = [line.strip() for line in script.splitlines()]
        # `--autostash` looks like the answer and is not: it stashes the noise,
        # then fails the step when the stash will not reapply.
        assert "--autostash" not in script, f"{where} must not stash before rebasing"
        discard = lines.index("git checkout -- .")
        rebase = lines.index("git pull --rebase origin main")
        assert discard < rebase, f"{where} must clear the tree before it rebases"
        assert any(
            "--untracked-files=no" in line for line in lines
        ), f"{where} must leave untracked files alone - they cannot block a rebase"


def test_the_work_job_checks_the_weights_before_it_starts_the_server() -> None:
    """The Oracle. Wrong bytes fail here, not five hours later as wrong summaries.

    The check has no `if:` on purpose. A restored cache entry is the one case
    where nobody watched the bytes arrive, so it is the case that most needs it.
    """
    workflow = _load_workflows()["digest.yml"]
    names = [step.get("name") for step in _steps(workflow, "work")]

    assert names.index("Fetch runtime and weights") < names.index("Verify the weights")
    assert names.index("Verify the weights") < names.index("Start the model")

    verify = _step(workflow, "work", "name", "Verify the weights")
    assert "if" not in verify, "a restored cache is what most needs checking"
    script = verify.get("run")
    assert isinstance(script, str)
    assert '["models"]["summarize"]["sha256"]' in script, "read the expectation from config"
    assert "sha256sum --check" in script


def test_the_health_check_names_the_weights_that_answered() -> None:
    """Healthy says a server replied. It does not say which weights replied."""
    health = _step(_load_workflows()["digest.yml"], "work", "name", "Check model health")
    script = health.get("run")
    assert isinstance(script, str)

    assert '["models"]["summarize"]["id"]' in script, "the alias comes from config"
    assert "/v1/models" in script, "assert the served alias"
    assert "/props" in script, "assert the loaded path"
    assert "${MODEL_FILE}" in script


def test_measurements_dispatch_selects_exactly_one_target() -> None:
    workflow = _load_workflows()["measure.yml"]
    target = _mapping(_dispatch_inputs(workflow).get("target"), "target input")
    options = _string_list(target.get("options"), "target options")

    assert target.get("type") == "choice"
    assert target.get("required") == "true"
    assert target.get("default") == "llm"
    assert len(options) == len(MEASUREMENT_TARGETS)
    assert frozenset(options) == MEASUREMENT_TARGETS

    actual_conditions = {
        job_name: _normalize_condition(_job(workflow, job_name).get("if"), f"job {job_name} if")
        for job_name in MEASUREMENT_TARGETS
    }
    assert actual_conditions == {
        job_name: f"inputs.target == '{job_name}'" for job_name in MEASUREMENT_TARGETS
    }


def test_runtime_candidate_has_a_valid_default() -> None:
    workflow = _load_workflows()["measure.yml"]
    candidate = _mapping(
        _dispatch_inputs(workflow).get("runtime_candidate"), "runtime_candidate input"
    )
    options = _string_list(candidate.get("options"), "runtime_candidate options")

    assert candidate.get("type") == "choice"
    assert candidate.get("default") == "baseline"
    assert len(options) == len(RUNTIME_CANDIDATES)
    assert frozenset(options) == RUNTIME_CANDIDATES
    assert candidate.get("default") in options


def test_llm_measurement_does_not_cache_or_glob_candidate_weights() -> None:
    workflow = _load_workflows()["measure.yml"]
    steps = _steps(workflow, "llm")
    # Matched on the action, never on its version: pinning the version here would
    # quietly stop testing anything the next time the major moves.
    used = [step.get("uses") for step in steps]
    assert not any(
        isinstance(value, str) and value.startswith("actions/cache@") for value in used
    )
    benchmark = _step(workflow, "llm", "name", "Download and benchmark exact models")
    script = benchmark.get("run")
    assert isinstance(script, str)
    assert benchmark.get("env") == {
        "MODEL_REFS": "${{ inputs.models }}",
        "THREAD_COUNTS": "${{ inputs.threads }}",
    }
    assert "backend/utilities/measure_llm.py" in script
    assert "backend/models/*.gguf" not in script


def test_runtime_download_uses_the_existing_github_token() -> None:
    workflow = _load_workflows()["measure.yml"]
    download = _step(workflow, "runtime", "name", "Fetch runtime and weights")
    script = download.get("run")
    assert isinstance(script, str)
    assert download.get("env") == {"GITHUB_TOKEN": "${{ secrets.GITHUB_TOKEN }}"}
    assert 'Authorization: Bearer ${GITHUB_TOKEN}' in script
    assert "Authorization: ******" not in read_text(WORKFLOWS_DIR / "measure.yml")


def test_every_workflow_that_runs_llama_cpp_pins_the_same_build() -> None:
    """Production, the validation arm and the harness run one binary.

    A throughput number is only about the pipeline if the pipeline runs the
    build the number was measured on (Rule #10).
    """
    workflows = _load_workflows()

    for filename in sorted(LLAMA_RUNTIME_WORKFLOWS):
        env = _mapping(workflows[filename].get("env"), f"{filename} env")
        assert env.get("LLAMA_CPP_BUILD") == PINNED_LLAMA_BUILD, filename
        assert env.get("LLAMA_CPP_ASSET") == PINNED_LLAMA_ASSET, filename
        assert env.get("LLAMA_CPP_SHA256") == PINNED_LLAMA_SHA256, filename


def test_every_llama_cpp_fetch_is_pinned_and_digest_checked() -> None:
    workflows = _load_workflows()

    for filename in sorted(LLAMA_RUNTIME_WORKFLOWS):
        scripts = _llama_fetch_scripts(workflows[filename])
        assert scripts, f"{filename} must still fetch llama.cpp"

        for job_name, step_name, script in scripts:
            where = f"{filename}/{job_name}/{step_name}"
            assert LLAMA_PINNED_ENDPOINT in script, f"{where} must ask for one tag"
            assert LLAMA_DIGEST_CHECK in script, f"{where} must check the archive digest"


def test_no_workflow_takes_whichever_llama_cpp_release_is_newest() -> None:
    """The list endpoint hands back a different binary on every cache eviction."""
    for path in sorted((*WORKFLOWS_DIR.glob("*.yml"), *WORKFLOWS_DIR.glob("*.yaml"))):
        assert "releases?per_page" not in read_text(path), path.name


def test_the_runtime_cache_key_names_the_build_it_holds() -> None:
    """The fetch runs only on a miss, so the key is what dates the binary.

    Keyed on the weights alone, a hit serves whatever build happened to be
    newest when the entry was written, and nothing records which one that was.
    """
    workflows = _load_workflows()
    expected_cache_jobs = {"digest.yml": {"work", "route"}, "validate.yml": {"validate"}}

    for filename, job_names in expected_cache_jobs.items():
        keys = _runtime_cache_keys(workflows[filename])
        assert {job_name for job_name, _ in keys} == job_names, filename

        for job_name, key in keys:
            assert "${{ env.LLAMA_CPP_BUILD }}" in key, f"{filename}/{job_name}: {key}"


def test_every_action_is_pinned_to_an_approved_major() -> None:
    """GitHub retired Node 20 on the runners.

    An action major that still declares `using: node20` is force-run on Node 24
    today and stops running at all later. The warning names the action, not the
    workflow, so nothing in the repo pointed at the 35 call sites until this test
    existed. A new action must be added here with its Node 24 major.
    """
    for filename, workflow in _load_workflows().items():
        references = _action_references(workflow)
        assert references, f"{filename} must call at least one action"

        for job_name, uses in references:
            where = f"{filename}/{job_name}"
            action, separator, version = uses.partition("@")
            assert separator, f"{where} must pin a version: {uses}"
            assert action in APPROVED_ACTION_MAJORS, f"{where} uses unapproved {action}"
            expected = APPROVED_ACTION_MAJORS[action]
            assert version == expected, f"{where} must use {action}@{expected}, not {uses}"
