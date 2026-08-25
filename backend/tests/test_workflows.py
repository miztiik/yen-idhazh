"""Contract tests for GitHub Actions display names and event routing."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Final, cast

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import CONFIG_DIR, REPO_ROOT, read_text

WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
SCRIPTS_DIR: Final = REPO_ROOT / ".github" / "scripts"

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
MEASUREMENT_TARGETS: Final = frozenset({"llm", "image", "corpus", "runtime", "batched"})
# The batched-bench arm's own definition. `docs/reference/measurements.md`
# publishes these values as the invocation behind its number, so a silent edit
# here would leave that page describing a run nobody made.
BATCHED_BENCH_SETTINGS: Final = {
    "BENCH_PROMPT_TOKENS": "900",
    "BENCH_GENERATE_TOKENS": "300",
    "BENCH_PARALLEL_LEVELS": "1,2,4",
    "BENCH_REPEATS": "3",
    "BENCH_GATE_RATIO": "1.4",
}
# Every job that stands up llama-server, and the log that job writes. Both must
# name the host, the binary and the weights: a shard's throughput is decided by
# the host it drew, and a number that cannot name the bytes that produced it is
# not a measurement (Rule #10).
RUNTIME_IDENTITY_JOBS: Final = {
    "work": ("llama-server.log", "MODEL_FILE"),
    "route": ("router.log", "ROUTE_FILE"),
}
RUNTIME_IDENTITY_STEP: Final = "What this runner is"
RUNTIME_LOG_SUMMARY_STEPS: Final = {
    "work": ("Prompt cache log summary", "llama-server.log"),
    "route": ("Router cache log summary", "router.log"),
}
# Four real llama-server lines. The first two are the same field under the two
# spellings llama.cpp has used; the third is the one the old fixed pattern list
# hid for two measured runs.
RUNTIME_LOG_LINES: Final = (
    "srv    load_model: initializing, n_slots = 1, n_ctx_slot = 8192, kv_unified = 'true'",
    "srv    load_model: initializing, n_slots = 1, n_ctx_seq = 8192, kv_unified = 'true'",
    "slot get_availabl: id  3 | task -1 | selected slot by LCP similarity, "
    "f_sim_best = 0.923 (> 0.100 thold), f_keep = 0.811",
    "slot print_timing: id  3 | task 172 | prompt eval time = 7119.70 ms / 75 tokens",
)
RSS_SAMPLE_SECONDS: Final = 15
RSS_SAMPLE_FILE: Final = "rss-samples.tsv"
MEMORY_PEAK_FILE: Final = "memory-peak.txt"
CGROUP_PEAK_PATH: Final = "/sys/fs/cgroup/memory.peak"
# llama-server's own loopback counters, read once at job end. The two series are
# named because they are the two a run is read by: the busy-slot average says
# whether batching ever happened, and the high watermark says how close the day
# came to `n_ctx`. Both spellings were read from `tools/server/README.md` in
# ggml-org/llama.cpp on 2026-08-25.
METRICS_FILE: Final = "llama-metrics.prom"
METRICS_ENDPOINT: Final = "http://127.0.0.1:8080/metrics"
METRICS_SERIES: Final = ("llamacpp:n_busy_slots_per_decode", "llamacpp:n_tokens_max")
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
# The one commit-and-push step both daily jobs run. They differ only in what
# they stage and in the three strings they pass, which is what makes the retry
# behaviour executable by a test instead of only greppable in YAML.
COMMIT_SCRIPT: Final = SCRIPTS_DIR / "commit-and-push.sh"
COMMIT_SCRIPT_CALL: Final = ("bash", ".github/scripts/commit-and-push.sh")
COMMIT_STEPS: Final = {
    "plan": "Commit what the plan saw",
    "assemble": "Commit the day",
}
COMMIT_SCRIPT_ENV: Final = frozenset(
    {"COMMIT_MESSAGE", "NOTHING_STAGED_MESSAGE", "PUSH_FAILED_MESSAGE"}
)
COMMIT_STAGED_PATHS: Final = {
    "plan": ["state/seen", "state/feed-health"],
    "assemble": ["frontend/public/digest", "frontend/public/telemetry", "state"],
}
COMMIT_IDENTITY: Final = (
    "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>"
)
# What a `${{ }}` expression stands in for when a test runs the real call site
# outside Actions. Only the date expressions survive into these strings.
SUBSTITUTED_DATE: Final = "2026-08-25"


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


def _script(step: dict[str, object], description: str) -> str:
    script = step.get("run")
    assert isinstance(script, str), f"{description} must run a shell script"
    return script


def _grep_pattern(script: str, description: str) -> re.Pattern[str]:
    """The extended regular expression the log summary greps its log with.

    Extracted and compiled rather than compared as text, so the assertion is
    about what the pattern MATCHES. A pattern that merely mentions a field name
    in a comment would pass a substring check and hide the same signal again.
    """
    patterns = re.findall(r"grep -E '([^']+)'", script)
    assert len(patterns) == 1, f"{description} must grep its log with one -E pattern"
    return re.compile(patterns[0], flags=re.MULTILINE)


def _commit_call(job_name: str) -> tuple[list[str], dict[str, str]]:
    """The paths and the strings one daily job hands the shared commit script."""
    workflow = _load_workflows()["digest.yml"]
    step = _step(workflow, job_name, "name", COMMIT_STEPS[job_name])
    command = shlex.split(_script(step, f"job {job_name} commit step"))
    assert tuple(command[:2]) == COMMIT_SCRIPT_CALL, (
        f"job {job_name} must commit through {COMMIT_SCRIPT_CALL[1]}"
    )
    declared = _mapping(step.get("env"), f"job {job_name} commit env")
    settings = {
        name: re.sub(r"\$\{\{.*?\}\}", SUBSTITUTED_DATE, str(value))
        for name, value in declared.items()
    }
    return command[2:], settings


def _bash() -> str | None:
    """A bash that can run the commit script, or None on a host without one."""
    if os.name != "nt":
        return shutil.which("bash")
    candidates: list[Path] = []
    git = shutil.which("git")
    if git is not None:
        candidates.append(Path(git).resolve().parent.parent / "bin" / "bash.exe")
    for variable in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        root = os.environ.get(variable)
        if root:
            candidates.append(Path(root) / "Git" / "bin" / "bash.exe")
    return next((str(path) for path in candidates if path.is_file()), None)


requires_bash: Final = pytest.mark.skipif(
    _bash() is None,
    reason="no bash on this host to execute .github/scripts/commit-and-push.sh",
)


def _isolated_env(tmp_path: Path) -> dict[str, str]:
    """Git with no machine identity and no machine config to fall back on.

    The script sets its own committer, so the test must not supply one: an
    inherited `user.name` would hide the day the script stopped setting it.
    """
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _git(repo: Path, env: dict[str, str], *args: str) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Scripted Origin",
            "-c",
            "user.email=origin@example.invalid",
            *args,
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii", newline="\n")


def _scripted_origin(
    tmp_path: Path, env: dict[str, str], staged_paths: Sequence[str]
) -> tuple[Path, Path]:
    """A bare origin holding one commit, plus the clone a job would check out."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, env, "init", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, env, "clone", str(origin), str(seed))
    for index, staged in enumerate(staged_paths):
        _write(seed / staged / "ledger.csv", f"header\nrow-{index}\n")
    _write(seed / "docs" / "unrelated.md", "seed\n")
    _write(seed / "runner-noise.txt", "clean\n")
    _git(seed, env, "add", "docs", "runner-noise.txt", *staged_paths)
    _git(seed, env, "commit", "-m", "seed")
    _git(seed, env, "push", "-u", "origin", "main")
    runner = tmp_path / "runner"
    _git(tmp_path, env, "clone", str(origin), str(runner))
    return origin, runner


def _race(tmp_path: Path, env: dict[str, str], relative: str, text: str) -> None:
    """Somebody else pushes to origin while the job is still working."""
    other = tmp_path / "other"
    if not other.exists():
        _git(tmp_path, env, "clone", str(tmp_path / "origin.git"), str(other))
    _write(other / relative, text)
    _git(other, env, "add", relative)
    _git(other, env, "commit", "-m", "racing change")
    _git(other, env, "push", "origin", "main")


def _run_commit_script(
    runner: Path,
    env: dict[str, str],
    staged_paths: Sequence[str],
    settings: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    bash = _bash()
    assert bash is not None
    return subprocess.run(
        [bash, COMMIT_SCRIPT.as_posix(), *staged_paths],
        cwd=runner,
        env={**env, **settings},
        capture_output=True,
        text=True,
    )


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

    This reads the shared script and the workflow's own `run:` bodies, so an
    inline loop written back into a step is still covered.
    """
    workflow = _load_workflows()["digest.yml"]
    jobs = _mapping(workflow.get("jobs"), "jobs")

    bodies = [
        (f"{job_name}/{step.get('name')}", script)
        for job_name in jobs
        for step in _steps(workflow, job_name)
        if isinstance(script := step.get("run"), str)
    ]
    bodies += [
        (path.relative_to(REPO_ROOT).as_posix(), read_text(path))
        for path in sorted(SCRIPTS_DIR.glob("*.sh"))
    ]
    scripts = [(where, body) for where, body in bodies if "git pull --rebase" in body]
    assert scripts, "the daily run must still push through a rebase-and-retry loop"

    for where, script in scripts:
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


def test_both_daily_commit_steps_run_the_one_shared_script() -> None:
    """Two copies of a retry loop is one copy nobody can execute in a test."""
    assert COMMIT_SCRIPT.is_file()
    assert read_text(COMMIT_SCRIPT).startswith("#!/usr/bin/env bash\n")

    for job_name in COMMIT_STEPS:
        staged_paths, settings = _commit_call(job_name)
        assert staged_paths == COMMIT_STAGED_PATHS[job_name]
        assert set(settings) == COMMIT_SCRIPT_ENV
        assert all(value for value in settings.values())

    plan = _commit_call("plan")[1]
    assemble = _commit_call("assemble")[1]
    # The two jobs say different things about the same event, and the extraction
    # kept both rather than choosing one.
    assert plan != assemble
    assert plan["COMMIT_MESSAGE"] == f"plan: {SUBSTITUTED_DATE}"
    assert assemble["COMMIT_MESSAGE"] == f"digest: {SUBSTITUTED_DATE}"


@requires_bash
@pytest.mark.parametrize("job_name", sorted(COMMIT_STEPS))
def test_the_commit_step_pushes_what_it_staged(tmp_path: Path, job_name: str) -> None:
    staged_paths, settings = _commit_call(job_name)
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / staged_paths[0] / "ledger.csv", "header\nrow-0\nfresh\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == (
        settings["COMMIT_MESSAGE"]
    )
    # The script sets the committer itself, and the test supplies none.
    assert _git(origin, env, "log", "-1", "--format=%an <%ae>").strip() == COMMIT_IDENTITY
    assert _git(runner, env, "status", "--porcelain").strip() == ""


@requires_bash
def test_the_commit_step_says_so_and_stops_when_nothing_changed(tmp_path: Path) -> None:
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    before = _git(origin, env, "rev-parse", "main").strip()

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert settings["NOTHING_STAGED_MESSAGE"] in result.stdout
    assert _git(origin, env, "rev-parse", "main").strip() == before
    assert _git(runner, env, "rev-parse", "HEAD").strip() == before


@requires_bash
def test_the_commit_step_rebases_past_a_racing_commit(tmp_path: Path) -> None:
    """The whole point of the loop: a push that loses a race still lands."""
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, "docs/unrelated.md", "racing\n")
    _write(runner / staged_paths[0] / "ledger.csv", "header\nrow-0\nfresh\n")
    _write(runner / "runner-noise.txt", "dirty\n")
    _write(runner / "leftover.log", "kept\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected, rebasing (attempt 1)" in result.stdout
    assert "discarding working-tree noise before the rebase:" in result.stdout
    assert "runner-noise.txt" in result.stdout
    assert _git(origin, env, "log", "--format=%s", "-2").splitlines() == [
        settings["COMMIT_MESSAGE"],
        "racing change",
    ]
    # The noise was discarded; the untracked file was not.
    assert (runner / "runner-noise.txt").read_text(encoding="ascii") == "clean\n"
    assert (runner / "leftover.log").is_file()
    assert _git(runner, env, "status", "--porcelain", "--untracked-files=no").strip() == ""


@requires_bash
def test_the_commit_step_gives_up_on_the_first_conflicting_rebase(tmp_path: Path) -> None:
    """Today's behaviour, measured, not the behaviour the loop looks like it has.

    `git pull --rebase origin main` is the one unguarded command in the loop, so
    when it conflicts `set -e` ends the script inside attempt 1. There is no
    attempt 2, the three-attempt message never prints, the day never lands, and
    the checkout is left mid-rebase. Observed 2026-08-25 against a scripted local
    origin, git 2.55.0, bash 5.3.15.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, f"{staged_paths[0]}/ledger.csv", "header\nrow-0\ntheirs\n")
    _write(runner / staged_paths[0] / "ledger.csv", "header\nrow-0\nours\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert "push rejected, rebasing (attempt 2)" not in result.stdout
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert "CONFLICT (content)" in result.stdout + result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == "racing change"
    assert (runner / ".git" / "rebase-merge").is_dir() or (
        runner / ".git" / "rebase-apply"
    ).is_dir(), "the checkout is left mid-rebase"


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


def test_batched_bench_measures_one_host_against_itself() -> None:
    """The result is a ratio, so every parallel level runs in the same job.

    Prefill spans 3.4x across runner hosts, so a matrix member per level would
    compare hardware and report it as batching. The arm also asks config for the
    context and threading knobs: a literal copied into the workflow stops
    describing production the day config moves (Rule #6).
    """
    workflow = _load_workflows()["measure.yml"]
    job = _job(workflow, "batched")
    summarize = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models"]["summarize"]

    assert "strategy" not in job, "every parallel level must share one host"
    env = _mapping(job.get("env"), "job batched env")
    assert env.get("MODEL_FILE") == summarize["file"]
    assert env.get("MODEL_REPO") == summarize["repo"]
    for name, value in BATCHED_BENCH_SETTINGS.items():
        assert env.get(name) == value, name

    # A cache hit serves whatever binary or weights happened to be written into
    # the entry, and nothing records which. A measurement arm downloads.
    assert not any(
        isinstance(uses := step.get("uses"), str) and uses.startswith("actions/cache@")
        for step in _steps(workflow, "batched")
    )

    settings = _step(workflow, "batched", "name", "Read the production inference settings")
    settings_script = settings.get("run")
    assert isinstance(settings_script, str)
    assert "config/idhazh.json" in settings_script

    bench = _step(workflow, "batched", "name", "Benchmark parallel decode")
    script = bench.get("run")
    assert isinstance(script, str)
    assert '"$LLAMA_BIN/llama-batched-bench"' in script
    for flag, name in (
        ("-c", "BENCH_N_CTX"),
        ("-b", "BENCH_N_BATCH"),
        ("-ub", "BENCH_N_UBATCH"),
        ("-t", "BENCH_N_THREADS"),
    ):
        assert f'{flag} "${name}"' in script, f"{flag} must come from config"
    for flag, name in (
        ("-npp", "BENCH_PROMPT_TOKENS"),
        ("-ntg", "BENCH_GENERATE_TOKENS"),
        ("-npl", "BENCH_PARALLEL_LEVELS"),
    ):
        assert f'{flag} "${name}"' in script, f"{flag} must come from the pinned settings"
    # llama-batched-bench drops a level whose context does not fit and says
    # nothing, so the arm refuses before it spends the runner time.
    assert 'if [ "$NEEDED" -gt "$BENCH_N_CTX" ]' in script

    upload = _step(workflow, "batched", "name", "Upload batched bench")
    uploaded = _mapping(upload.get("with"), "batched upload 'with'")
    assert uploaded.get("path") == "backend/var/batched-bench/"
    assert upload.get("if") == "always()", "the raw tables outlive a failed summary"


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


def test_every_inference_job_names_its_host_binary_and_weights() -> None:
    """Six lines, so a number a job produced can name the bytes that made it.

    The route job printed the first three from 2026-08-25. The work job printed
    none, and the `route` prefill rate swings 3x between runs with the host as
    the only remaining suspect. Without the version and the two digests, a run
    still cannot say which binary and which weights served the day (Rule #10).
    """
    workflow = _load_workflows()["digest.yml"]

    for job_name, (log_name, weights_var) in RUNTIME_IDENTITY_JOBS.items():
        step = _step(workflow, job_name, "name", RUNTIME_IDENTITY_STEP)
        where = f"digest.yml/{job_name}/{RUNTIME_IDENTITY_STEP}"
        # A cancelled job skips a step with no condition, and a shard that died
        # is exactly the one whose host is worth naming.
        assert _normalize_condition(step.get("if"), f"{where} if") == "always()"
        script = _script(step, where)

        for probe in (
            "'model name' /proc/cpuinfo",
            "nproc",
            f"'system_info' {log_name}",
            "llama-server --version",
            "sha256sum backend/bin/llama-server",
            f'sha256sum "backend/models/${{{weights_var}}}"',
        ):
            assert probe in script, f"{where} must print {probe}"
        assert "${LLAMA_CPP_BUILD}" in script, f"{where} must name the pinned build"


def test_the_runtime_log_summary_cannot_hide_a_signal() -> None:
    """A fixed list of expected lines is a filter that reports what it expects.

    The old list greps `kv cache rm [`, a line this build never emits, and so
    `measurements.md` recorded prefix reuse as unprovable for two runs while the
    uploaded artifact carried the proof. `^(srv|slot) ` takes whatever the
    runtime chose to print instead.
    """
    workflow = _load_workflows()["digest.yml"]

    for job_name, (step_name, log_name) in RUNTIME_LOG_SUMMARY_STEPS.items():
        step = _step(workflow, job_name, "name", step_name)
        where = f"digest.yml/{job_name}/{step_name}"
        assert _normalize_condition(step.get("if"), f"{where} if") == "always()"
        script = _script(step, where)
        assert re.search(rf"grep -E '[^']+' {re.escape(log_name)}", script), (
            f"{where} must summarise {log_name}"
        )
        pattern = _grep_pattern(script, where)

        for line in RUNTIME_LOG_LINES:
            assert pattern.search(line) is not None, f"{where} would hide: {line}"
        assert pattern.search("main: server is listening on http://127.0.0.1:8080") is None, (
            f"{where} pattern is too wide to be a summary"
        )
        # Both spellings by name, so a llama.cpp rename cannot pass silently even
        # if the line it sits on ever stops starting with `srv`.
        for spelling in ("n_ctx_slot", "n_ctx_seq"):
            assert spelling in pattern.pattern, f"{where} must grep {spelling}"

        # The presence of the line is not the measurement; the spread is.
        extractors = re.findall(r'grep -oE "([^"]+)"', script)
        assert len(extractors) == 1, f"{where} must extract the reuse fields with one -oE pattern"
        for field, value in (("f_sim_best", "0.923"), ("f_keep", "0.811")):
            probe = re.compile(extractors[0].replace("${field}", field))
            found = probe.search(RUNTIME_LOG_LINES[2])
            assert found is not None, f"{where} would not capture {field}"
            assert found.group(0).split(" = ")[1] == value, f"{where} mis-reads {field}"
        assert "for field in f_sim_best f_keep" in script, f"{where} must read both fields"
        assert "median" in script, f"{where} must report a distribution, not a count"


def test_every_work_shard_records_what_memory_it_used() -> None:
    """Neither of the two runs `measurements.md` reads measured memory at all.

    `measure.yml` already samples `VmRSS` and reads the cgroup peak; the daily
    path did not, so nothing says how close a 16 GB runner came to its limit
    (Rule #2).
    """
    workflow = _load_workflows()["digest.yml"]

    sampler = _step(workflow, "work", "name", "Sample memory")
    sampler_script = _script(sampler, "digest.yml/work/Sample memory")
    assert "VmRSS" in sampler_script
    assert "VmHWM" in sampler_script
    assert f"sleep {RSS_SAMPLE_SECONDS}" in sampler_script
    assert RSS_SAMPLE_FILE in sampler_script
    assert "llama-server.pid" in sampler_script, "the sampler must follow the server it samples"

    peak = _step(workflow, "work", "name", "What memory this shard used")
    where = "digest.yml/work/What memory this shard used"
    assert _normalize_condition(peak.get("if"), f"{where} if") == "always()"
    peak_script = _script(peak, where)
    assert CGROUP_PEAK_PATH in peak_script
    assert MEMORY_PEAK_FILE in peak_script

    upload = _step(workflow, "work", "name", "Upload runtime log")
    with_block = _mapping(upload.get("with"), "work runtime-log upload 'with'")
    assert with_block.get("name") == "runtime-log-${{ matrix.shard }}"
    path = with_block.get("path")
    assert isinstance(path, str), "work runtime-log upload path must be a string"
    assert [line for line in path.splitlines() if line] == [
        "llama-server.log",
        RSS_SAMPLE_FILE,
        MEMORY_PEAK_FILE,
        METRICS_FILE,
    ]


def test_every_work_shard_records_how_hard_the_server_was_pushed() -> None:
    """Two numbers no log line carries: the busy-slot average and the context high watermark.

    `n_ctx` is 8192 and nothing said how close a day came to it, so a
    context-full failure could only be counted after it happened. Nothing said
    whether more than one slot was ever busy either, which makes a null result
    from a concurrency arm unreadable - it cannot separate "batching did not
    help" from "batching never happened".
    """
    workflow = _load_workflows()["digest.yml"]

    step = _step(workflow, "work", "name", "What the server counted")
    where = "digest.yml/work/What the server counted"
    # The shard that ran out of context is the shard whose high watermark is
    # worth reading, and that shard failed.
    assert _normalize_condition(step.get("if"), f"{where} if") == "always()"
    script = _script(step, where)

    assert METRICS_ENDPOINT in script, f"{where} must scrape the server's own endpoint"
    assert f"-o {METRICS_FILE}" in script, f"{where} must keep the raw body as {METRICS_FILE}"
    # Once, at the end. A per-request scrape adds requests to what it measures.
    assert script.count("curl") == 1, f"{where} must scrape once, not per request"
    for series in METRICS_SERIES:
        assert series in script, f"{where} must name {series} in the job log"

    upload = _step(workflow, "work", "name", "Upload runtime log")
    with_block = _mapping(upload.get("with"), "work runtime-log upload 'with'")
    path = with_block.get("path")
    assert isinstance(path, str), "work runtime-log upload path must be a string"
    assert METRICS_FILE in path.splitlines(), "the runtime artifact must carry the raw counters"
