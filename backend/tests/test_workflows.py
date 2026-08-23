"""Contract tests for GitHub Actions display names and event routing."""

from __future__ import annotations

import hashlib
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

CONTENT_REFRESH_CRON: Final = "20 6,10,14,18 * * *"
CONTENT_REFRESH_UTC_HOURS: Final = (6, 10, 14, 18)
CONTENT_REFRESH_SHARDS: Final = frozenset({"1", "2", "3", "4"})
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


def _evaluate_models_hash(script: str, models: str) -> str:
    lines = [line.strip() for line in script.splitlines()]
    assignment = (
        "MODELS_SHA256=$(printf '%s' \"$MODELS\" | sha256sum | cut -d ' ' -f 1)"
    )
    output = 'echo "models_sha256=$MODELS_SHA256" >> "$GITHUB_OUTPUT"'

    assert [line for line in lines if line.startswith("MODELS_SHA256=")] == [assignment]
    assert [line for line in lines if "models_sha256=" in line] == [output]
    return hashlib.sha256(models.encode()).hexdigest()


def test_workflow_names_and_trigger_classes_are_pinned() -> None:
    workflows = _load_workflows()

    for filename, (display_name, trigger_classes) in EXPECTED_WORKFLOWS.items():
        workflow = workflows[filename]
        assert workflow.get("name") == display_name
        assert set(_triggers(workflow)) == trigger_classes


def test_content_refresh_runs_at_the_four_approved_utc_hours() -> None:
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


def test_llm_cache_key_uses_the_requested_models_hash() -> None:
    workflow = _load_workflows()["measure.yml"]
    steps = _steps(workflow, "llm")
    hash_step = _step(workflow, "llm", "id", "models_hash")
    cache_step = _step(workflow, "llm", "id", "gguf")
    hash_script = hash_step.get("run")
    assert isinstance(hash_script, str)
    assert hash_step.get("env") == {"MODELS": "${{ inputs.models }}"}

    expected_hashes = {
        "Qwen/Qwen3-4B-GGUF:Qwen3-4B-Q4_K_M.gguf": (
            "e44a2225f6f322a8e8dbddd8579eb18e22d02fcb55ff67dcf67796f646f9c54d"
        ),
        "org/a:model-a.gguf,org/b:model-b.gguf": (
            "f545e92d7d4b908ed7670f2dc641c82c87759a997888b2716f8bd35462f53765"
        ),
    }
    for models, expected_hash in expected_hashes.items():
        assert _evaluate_models_hash(hash_script, models) == expected_hash
        assert hashlib.sha256(f"{models}\n".encode()).hexdigest() != expected_hash

    cache_with = _mapping(cache_step.get("with"), "GGUF cache inputs")
    cache_key = cache_with.get("key")
    assert cache_key == "gguf-${{ runner.os }}-${{ steps.models_hash.outputs.models_sha256 }}"
    assert "hashFiles(" not in cache_key
    assert steps.index(hash_step) < steps.index(cache_step)


def test_runtime_download_uses_the_existing_github_token() -> None:
    workflow = _load_workflows()["measure.yml"]
    download = _step(workflow, "runtime", "name", "Fetch runtime and weights")
    script = download.get("run")
    assert isinstance(script, str)
    assert download.get("env") == {"GITHUB_TOKEN": "${{ secrets.GITHUB_TOKEN }}"}
    assert 'Authorization: Bearer ${GITHUB_TOKEN}' in script
    assert "Authorization: ******" not in read_text(WORKFLOWS_DIR / "measure.yml")
