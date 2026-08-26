"""Contract tests for GitHub Actions display names and event routing."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, cast

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh.contracts.route import Route, SpecFormat, VisualKind, VisualState

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
# The ceiling, not the dispatch rule. Rule #2 allows 20 concurrent jobs; a regex
# held the fan-out at four. The empty-input default below stays at four, because
# that is what every scheduled run gets and no eight-shard run is measured yet.
CONTENT_REFRESH_SHARDS: Final = frozenset({"1", "2", "3", "4", "5", "6", "7", "8"})
CONTENT_REFRESH_SHARD_DEFAULT: Final = "4"

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
# The one commit-and-push step both daily jobs run. They differ in what they
# stage, in the strings they pass, and in whether they can rebuild what they
# commit, which is what makes the retry behaviour executable by a test instead
# of only greppable in YAML.
COMMIT_SCRIPT: Final = SCRIPTS_DIR / "commit-and-push.sh"
COMMIT_SCRIPT_CALL: Final = ("bash", ".github/scripts/commit-and-push.sh")
COMMIT_STEPS: Final = {
    "plan": "Commit what the plan saw",
    "assemble": "Commit the day",
}
COMMIT_BASE_ENV: Final = frozenset(
    {"COMMIT_MESSAGE", "NOTHING_STAGED_MESSAGE", "PUSH_FAILED_MESSAGE"}
)
# Only assemble can rebuild what it commits, so only assemble carries the three
# settings that make the loop rebuild instead of merge - and only assemble
# commits rendered assets, so only assemble renumbers them.
COMMIT_SCRIPT_ENV: Final = {
    "plan": COMMIT_BASE_ENV,
    "assemble": COMMIT_BASE_ENV | {"REFRESH_PATHS", "REGENERATE_COMMAND", "RENUMBER_COMMAND"},
}
COMMIT_STAGED_PATHS: Final = {
    "plan": ["state/seen", "state/feed-health"],
    "assemble": ["frontend/public/digest", "frontend/public/telemetry", "state"],
}
COMMIT_IDENTITY: Final = (
    "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>"
)
# What a `${{ }}` expression stands in for when a test runs the real call site
# outside Actions. `day_dir` is the digest date as a path, which is what lets the
# refresh set name `digest.json` and `run.json` one file at a time.
SUBSTITUTED_DATE: Final = "2026-08-25"
SUBSTITUTED_DAY_DIR: Final = "frontend/public/digest/2026/08/25"
SUBSTITUTED_SHA: Final = "0" * 40
EXPRESSION_VALUES: Final = {
    "needs.plan.outputs.date": SUBSTITUTED_DATE,
    "needs.plan.outputs.day_dir": SUBSTITUTED_DAY_DIR,
    "steps.decide.outputs.date": SUBSTITUTED_DATE,
    "github.sha": SUBSTITUTED_SHA,
}
# What assemble hands back to origin's tip before it rebuilds. The day's own
# directory is never in this list: the routes artifact unpacks this run's
# rendered charts into it, and no producer in the assemble job can make those
# again, so the two payload files are named one at a time.
COMMIT_REFRESH_PATHS: Final = {
    "assemble": [
        f"{SUBSTITUTED_DAY_DIR}/digest.json",
        f"{SUBSTITUTED_DAY_DIR}/run.json",
        "frontend/public/telemetry",
        "state/published.csv",
        "state/scores.csv",
        "state/item-health",
    ],
}
# The producer the harness drives through the loop. See its own docstring for
# why the pipeline's `assemble` cannot be the one under a temporary clone.
REBUILD_STAND_IN: Final = Path(__file__).with_name("rebuild_day.py")
# The renumber, by contrast, IS the shipped one: it anchors on the working
# directory, so it runs inside a temporary clone unchanged.
RENUMBER_ENTRY_POINT: Final = REPO_ROOT / "backend" / "utilities" / "renumber_racing_assets.py"
RUN_ARTIFACTS: Final = "backend/var/run"
# One rendered chart, as the route job leaves it: an SVG in the day's directory
# and a route payload saying where it landed.
RACED_ASSET: Final = f"digest/{SUBSTITUTED_DATE.replace('-', '/')}/energy-01.svg"
NEXT_FREE_ASSET: Final = f"digest/{SUBSTITUTED_DATE.replace('-', '/')}/energy-02.svg"


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


def _evaluate_shard_matrix(script: str, requested_shards: str, derived: int) -> list[int] | None:
    """Read the fan-out step's shell and answer what matrix it writes.

    The step takes two inputs, so the harness does too: what an operator typed,
    and what the derivation printed when nobody typed anything.
    """
    lines = [line.strip() for line in script.splitlines()]
    pattern_line = "SHARD_PATTERN='^[1-8]$'"
    input_line = 'SHARDS="${{ inputs.shards }}"'
    derive_line = 'SHARDS=$(python -m idhazh shards --date "${{ steps.decide.outputs.date }}")'
    clamp_line = 'while [ "$SHARDS" -gt 1 ] && ! [[ "$SHARDS" =~ $SHARD_PATTERN ]]; do'
    guard_block = [
        'if ! [[ "$SHARDS" =~ $SHARD_PATTERN ]]; then',
        'echo "shards must be an integer from 1 through 8" >&2',
        "exit 1",
        "fi",
    ]
    matrix_line = (
        'echo "matrix=$(seq 0 $((SHARDS - 1)) | jq -R . | jq -sc .)" '
        '>> "$GITHUB_OUTPUT"'
    )

    assert [line for line in lines if line.startswith("SHARD_PATTERN=")] == [pattern_line]
    assert lines.count(input_line) == 1
    assert lines.count(derive_line) == 1, "the count comes from the plan, not from a literal"
    assert lines.count(clamp_line) == 1, "a derived count is clamped, never fatal"
    assert not [line for line in lines if line.startswith('[ -n "$SHARDS" ]')], (
        "the fixed default is what the derivation replaces"
    )
    assert [line for line in lines if line.startswith('echo "matrix=')] == [matrix_line]
    guard_index = lines.index(guard_block[0])
    assert lines[guard_index : guard_index + len(guard_block)] == guard_block
    assert (
        lines.index(pattern_line)
        < lines.index(input_line)
        < lines.index(derive_line)
        < lines.index(clamp_line)
        < guard_index
        < lines.index(matrix_line)
    )

    pattern_match = re.fullmatch(r"SHARD_PATTERN='([^']+)'", pattern_line)
    assert pattern_match is not None
    pattern = pattern_match.group(1)
    shards = requested_shards
    if not shards:
        shards = str(derived)
        while int(shards) > 1 and re.fullmatch(pattern, shards) is None:
            shards = str(int(shards) - 1)
    if re.fullmatch(pattern, shards) is None:
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


def _setup_python_versions(workflow: dict[str, object]) -> list[tuple[str, str]]:
    versions: list[tuple[str, str]] = []
    for job_name in _mapping(workflow.get("jobs"), "jobs"):
        for step in _steps(workflow, job_name):
            uses = step.get("uses")
            if not (isinstance(uses, str) and uses.startswith("actions/setup-python@")):
                continue
            with_block = _mapping(step.get("with"), f"job {job_name} setup-python 'with'")
            version = with_block.get("python-version")
            assert isinstance(version, str), f"job {job_name} must pin python-version"
            versions.append((job_name, version))
    return versions


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


def _substitute(text: str) -> str:
    """Stand in for what Actions would expand, so a test can run the real call site.

    Every expression is named. An unlisted one fails here rather than quietly
    substituting a date into a path and testing a string nothing ever produces.
    """

    def resolve(match: re.Match[str]) -> str:
        expression = match.group(1).strip()
        assert expression in EXPRESSION_VALUES, f"no test value for '{expression}'"
        return EXPRESSION_VALUES[expression]

    return re.sub(r"\$\{\{(.*?)\}\}", resolve, text, flags=re.DOTALL)


def _commit_call(job_name: str) -> tuple[list[str], dict[str, str]]:
    """The paths and the strings one daily job hands the shared commit script."""
    workflow = _load_workflows()["digest.yml"]
    step = _step(workflow, job_name, "name", COMMIT_STEPS[job_name])
    command = shlex.split(_script(step, f"job {job_name} commit step"))
    assert tuple(command[:2]) == COMMIT_SCRIPT_CALL, (
        f"job {job_name} must commit through {COMMIT_SCRIPT_CALL[1]}"
    )
    declared = _mapping(step.get("env"), f"job {job_name} commit env")
    settings = {name: _substitute(str(value)) for name, value in declared.items()}
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
# The loop word-splits `REGENERATE_COMMAND` on spaces, exactly as the workflow's
# own value expects, so a harness that has to name an interpreter needs a path
# without one.
requires_space_free_paths: Final = pytest.mark.skipif(
    " " in sys.executable
    or " " in str(REBUILD_STAND_IN)
    or " " in str(RENUMBER_ENTRY_POINT),
    reason="REGENERATE_COMMAND is word-split on spaces",
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
    # This repository's own attributes file. `merge=union` on the ledgers is
    # what decides whether two runs that both appended are in conflict, so a
    # scripted origin without it would test a different repository.
    _write(seed / ".gitattributes", read_text(REPO_ROOT / ".gitattributes"))
    _git(seed, env, "add", ".gitattributes", "docs", "runner-noise.txt", *staged_paths)
    _git(seed, env, "commit", "-m", "seed")
    _git(seed, env, "push", "-u", "origin", "main")
    runner = tmp_path / "runner"
    _git(tmp_path, env, "clone", str(origin), str(runner))
    return origin, runner


def _rebuild_command(date: str) -> str:
    """The producer the harness puts through the loop, as the loop word-splits it."""
    return f"{Path(sys.executable).as_posix()} {REBUILD_STAND_IN.as_posix()} --date {date}"


def _renumber_command(date: str) -> str:
    """The shipped renumber, as the loop word-splits it."""
    return f"{Path(sys.executable).as_posix()} {RENUMBER_ENTRY_POINT.as_posix()} --date {date}"


def _chart(repo: Path, date: str, item_id: str, relpath: str) -> None:
    """One rendered chart, exactly as the route job's artifact leaves it.

    An SVG under the day's directory and a real `Route` beside the run's items
    saying where it landed. The bytes carry the item id, because two runs that
    number a chart the same for different items with the SAME bytes is the case
    git resolves on its own.
    """
    _write(repo / "frontend" / "public" / relpath, f"<svg>{item_id}</svg>\n")
    route = Route(
        version=Route.schema_version(),
        item_id=item_id,
        url_key=hashlib.sha256(item_id.encode("ascii")).hexdigest(),
        kind=VisualKind.CHART,
        spec='{"mark": "bar"}',
        spec_format=SpecFormat.VEGA_LITE,
        asset_path=relpath,
        visual_state=VisualState.RENDERED,
        model_id="qwen3-4b",
        routed_at=f"{date}T00:00:00Z",
    )
    _write(repo / RUN_ARTIFACTS / date / "items" / f"{item_id}.route.json", route.to_json())


def _rebuild(repo: Path, env: dict[str, str], date: str, items: Sequence[str]) -> None:
    """One assemble run: write this run's artifacts, then publish them."""
    _write(
        repo / RUN_ARTIFACTS / date / "items.json",
        json.dumps({"items": list(items)}) + "\n",
    )
    subprocess.run(
        [sys.executable, str(REBUILD_STAND_IN), "--date", date],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def _digest_origin(tmp_path: Path, env: dict[str, str], date: str) -> tuple[Path, Path]:
    """An origin carrying a published day, plus the clone the assemble job runs in.

    The day is written by the same producer the loop reruns, so nothing here is
    a hand-made fixture of what that producer emits.
    """
    origin = tmp_path / "origin.git"
    _git(tmp_path, env, "init", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, env, "clone", str(origin), str(seed))
    _write(seed / ".gitattributes", read_text(REPO_ROOT / ".gitattributes"))
    _write(seed / "docs" / "unrelated.md", "seed\n")
    _rebuild(seed, env, date, ["item-a", "item-b"])
    _git(seed, env, "add", ".gitattributes", "docs", *COMMIT_STAGED_PATHS["assemble"])
    _git(seed, env, "commit", "-m", f"digest: {date}")
    _git(seed, env, "push", "-u", "origin", "main")
    runner = tmp_path / "runner"
    _git(tmp_path, env, "clone", str(origin), str(runner))
    return origin, runner


def _race_the_day(
    tmp_path: Path,
    env: dict[str, str],
    date: str,
    items: Sequence[str],
    pull_request: str,
    charts: Mapping[str, str] | None = None,
) -> None:
    """Origin gains another run of the same day AND an unrelated merge, in that order."""
    other = tmp_path / "other"
    _git(tmp_path, env, "clone", str(tmp_path / "origin.git"), str(other))
    for item_id, relpath in (charts or {}).items():
        _chart(other, date, item_id, relpath)
    _rebuild(other, env, date, items)
    _git(other, env, "add", *COMMIT_STAGED_PATHS["assemble"])
    _git(other, env, "commit", "-m", f"digest: {date}")
    _write(other / "docs" / "unrelated.md", "merged by a pull request\n")
    _git(other, env, "add", "docs")
    _git(other, env, "commit", "-m", pull_request)
    _git(other, env, "push", "origin", "main")


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def _tracked(repo: Path, env: dict[str, str], relative: str) -> bool:
    return relative in _git(repo, env, "ls-tree", "-r", "--name-only", "main").splitlines()


def _mid_rebase(runner: Path) -> bool:
    return (runner / ".git" / "rebase-merge").is_dir() or (
        runner / ".git" / "rebase-apply"
    ).is_dir()


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


def test_content_refresh_has_eight_total_work_shards_at_most() -> None:
    workflow = _load_workflows()["digest.yml"]
    shards = _mapping(_dispatch_inputs(workflow).get("shards"), "shards input")
    options = _string_list(shards.get("options"), "shards options")

    assert shards.get("type") == "choice"
    assert shards.get("default") == CONTENT_REFRESH_SHARD_DEFAULT
    assert len(options) == len(CONTENT_REFRESH_SHARDS)
    assert frozenset(options) == CONTENT_REFRESH_SHARDS

    strategy = _mapping(_job(workflow, "work").get("strategy"), "work strategy")
    # The concurrency cap matches the ceiling. Left at four it would queue half
    # of an eight-shard dispatch and hand back the wall-clock the fan-out buys.
    assert strategy.get("max-parallel") == "8"


def test_content_refresh_derives_the_shard_count_after_the_plan() -> None:
    """The matrix was written before the plan existed, so `run.shard_size` could not reach it.

    `shards` and `matrix` therefore move to their own step behind `Plan the day`,
    and the job outputs move with them. A relocated step id that nothing
    re-points is a silent break no shell assertion catches.
    """
    workflow = _load_workflows()["digest.yml"]
    outputs = _mapping(_job(workflow, "plan").get("outputs"), "plan outputs")
    assert outputs.get("shards") == "${{ steps.fanout.outputs.shards }}"
    assert outputs.get("matrix") == "${{ steps.fanout.outputs.matrix }}"

    steps = _steps(workflow, "plan")
    assert [step.get("id") for step in steps].index("fanout") > (
        [step.get("name") for step in steps].index("Plan the day")
    )
    decide_script = _step(workflow, "plan", "id", "decide").get("run")
    assert isinstance(decide_script, str)
    assert "SHARDS" not in decide_script, "the fan-out no longer rides on the date step"


def test_content_refresh_caps_total_jobs_by_behavior() -> None:
    workflow = _load_workflows()["digest.yml"]
    fanout = _step(workflow, "plan", "id", "fanout")
    script = fanout.get("run")
    assert isinstance(script, str)

    # Nobody asked, so the day decides. A day that needs fewer workers gets
    # fewer, and every extra worker restores the weights again.
    for derived in sorted(int(shards) for shards in CONTENT_REFRESH_SHARDS):
        assert _evaluate_shard_matrix(script, "", derived) == list(range(derived))
    # A config that outruns the ceiling costs the tail of the fan-out, never the
    # day: the feeds have already been read when this step runs.
    assert _evaluate_shard_matrix(script, "", 12) == list(range(int(max(CONTENT_REFRESH_SHARDS))))

    # An operator's own value still wins, and is still checked rather than clamped.
    expected = {shards: list(range(int(shards))) for shards in sorted(CONTENT_REFRESH_SHARDS)}
    for requested_shards, matrix in expected.items():
        assert _evaluate_shard_matrix(script, requested_shards, 1) == matrix
    # Both edges of the ceiling, plus the shapes that are not an integer.
    for invalid_shards in ("0", "9", "10", "-1", "1.5", "text", "04", " 4"):
        assert _evaluate_shard_matrix(script, invalid_shards, 4) is None


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
    scripts = [(where, body) for where, body in bodies if "git rebase" in body]
    assert scripts, "the daily run must still push through a rebase-and-retry loop"

    for where, script in scripts:
        lines = [line.strip() for line in script.splitlines()]
        # `--autostash` looks like the answer and is not: it stashes the noise,
        # then fails the step when the stash will not reapply.
        assert "--autostash" not in script, f"{where} must not stash before rebasing"
        discard = next(
            index for index, line in enumerate(lines) if line.startswith("git checkout -- .")
        )
        rebase = next(
            index
            for index, line in enumerate(lines)
            if "git rebase " in line and "--abort" not in line
        )
        assert discard < rebase, f"{where} must clear the tree before it rebases"
        assert any(
            "--untracked-files=no" in line for line in lines
        ), f"{where} must leave untracked files alone - they cannot block a rebase"
        # A rebase that cannot finish must not be left half-applied for the next
        # attempt to trip over.
        assert "git rebase --abort" in script, f"{where} must leave no rebase in progress"


def test_every_command_in_the_retry_loop_is_guarded() -> None:
    """`set -e` plus one unguarded command is the whole defect.

    `git pull --rebase origin main` was the only unguarded command in the loop,
    so a conflicting rebase ended the script inside attempt 1 and left the
    checkout mid-rebase. This reads the loop body and asserts every command in it
    is either a condition, a guarded call, or an `echo`, which is what makes the
    three attempts real. The Oracle test below proves the same thing by running
    it; this one names the line when a new command arrives unguarded.
    """
    lines = read_text(COMMIT_SCRIPT).splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("for attempt in "))
    end = next(index for index, line in enumerate(lines) if line.startswith("done"))
    assert start < end

    unguarded = []
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        guarded = (
            stripped.startswith(("if ", "elif ", "fi", "else", "echo ", "["))
            or stripped in {"exit 0", "break", "continue", "then"}
            or "||" in stripped
        )
        if not guarded:
            unguarded.append(stripped)
    assert unguarded == [], f"unguarded inside the retry loop: {unguarded}"


def test_both_daily_commit_steps_run_the_one_shared_script() -> None:
    """Two copies of a retry loop is one copy nobody can execute in a test."""
    assert COMMIT_SCRIPT.is_file()
    assert read_text(COMMIT_SCRIPT).startswith("#!/usr/bin/env bash\n")

    for job_name in COMMIT_STEPS:
        staged_paths, settings = _commit_call(job_name)
        assert staged_paths == COMMIT_STAGED_PATHS[job_name]
        assert set(settings) == COMMIT_SCRIPT_ENV[job_name]
        assert all(value for value in settings.values())

    plan = _commit_call("plan")[1]
    assemble = _commit_call("assemble")[1]
    # The two jobs say different things about the same event, and the extraction
    # kept both rather than choosing one.
    assert plan != assemble
    assert plan["COMMIT_MESSAGE"] == f"plan: {SUBSTITUTED_DATE}"
    assert assemble["COMMIT_MESSAGE"] == f"digest: {SUBSTITUTED_DATE}"


def test_only_assemble_rebuilds_and_it_rebuilds_with_its_own_publish_command() -> None:
    """The producer named in the loop is the producer the job already ran.

    Compared as argv rather than as text: the step runs its command through a
    shell and quotes what it interpolates, and the loop runs the same words with
    no shell at all. Two copies of the invocation would be two things to keep in
    step, and the one inside the loop only runs on a race - which is the copy
    nobody would notice going stale.
    """
    workflow = _load_workflows()["digest.yml"]
    publish = _script(
        _step(workflow, "assemble", "name", "Assemble and publish"), "assemble publish step"
    )
    settings = _commit_call("assemble")[1]

    # `shlex.split` keeps a backslash-newline as a token of its own, so the
    # step's line continuations are folded first.
    published_argv = shlex.split(_substitute(publish).replace("\\\n", " "))
    assert published_argv == settings["REGENERATE_COMMAND"].split()
    assert settings["REFRESH_PATHS"].split() == COMMIT_REFRESH_PATHS["assemble"]
    # Never the day's directory itself. The routes artifact unpacks this run's
    # rendered charts into it and no producer here can make them again, so the
    # two payload files are named one at a time.
    assert SUBSTITUTED_DAY_DIR not in settings["REFRESH_PATHS"].split()
    # Which is why the charts get their own answer: they are handed a free
    # number rather than handed back, so the rebase never sees two adds of one
    # path. The entry point is the shipped one, not a copy of its logic.
    assert settings["RENUMBER_COMMAND"].split()[1:] == [
        "backend/utilities/renumber_racing_assets.py",
        "--date",
        SUBSTITUTED_DATE,
    ]
    assert RENUMBER_ENTRY_POINT.is_file()
    # Neither setting may carry a space inside one of its words: the loop
    # word-splits both, and nothing here re-parses shell quoting.
    assert not any(
        '"' in value or "'" in value
        for value in (settings["REFRESH_PATHS"], settings["REGENERATE_COMMAND"])
    )
    # The plan job records what it saw and cannot rebuild it, so it resolves a
    # race by rebasing, and `.gitattributes` unions its ledgers. It commits no
    # rendered asset either, so it has nothing to renumber.
    assert "REGENERATE_COMMAND" not in _commit_call("plan")[1]
    assert "RENUMBER_COMMAND" not in _commit_call("plan")[1]


def test_the_append_only_ledgers_union_and_the_public_projection_does_not() -> None:
    """A text merge of two appends is a merge nobody asked for.

    Every file under `state/` is an append-only ledger of independent rows, so
    the union of both sides is the answer. `frontend/public/telemetry/` is a
    full rewrite of `state/item-health/`, so a union of two rewrites is a file
    with every row twice; assemble regenerates it instead.
    """
    attributes = read_text(REPO_ROOT / ".gitattributes")
    unioned = {
        line.split()[0]
        for line in attributes.splitlines()
        if line and not line.startswith("#") and "merge=union" in line
    }

    assert unioned == {"state/*.csv", "state/**/*.csv"}
    assert not any(
        "telemetry" in pattern or pattern.startswith("frontend") for pattern in unioned
    )


def test_the_plan_job_publishes_the_day_directory_it_decided() -> None:
    """The refresh set has to name two files inside the day, so the run says where it is."""
    workflow = _load_workflows()["digest.yml"]
    script = _script(_step(workflow, "plan", "id", "decide"), "plan decide step")
    outputs = _mapping(_job(workflow, "plan").get("outputs"), "plan outputs")

    assert outputs.get("day_dir") == "${{ steps.decide.outputs.day_dir }}"
    assert 'echo "day_dir=frontend/public/digest/${DATE//-//}" >> "$GITHUB_OUTPUT"' in [
        line.strip() for line in script.splitlines()
    ]
    # The expansion above, evaluated the way bash would.
    assert f"frontend/public/digest/{SUBSTITUTED_DATE.replace('-', '/')}" == SUBSTITUTED_DAY_DIR


@requires_bash
@pytest.mark.parametrize("job_name", sorted(COMMIT_STEPS))
def test_the_commit_step_pushes_what_it_staged(tmp_path: Path, job_name: str) -> None:
    staged_paths, settings = _commit_call(job_name)
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / staged_paths[0] / "ledger.csv", "header\nrow-0\nfresh\n")
    if "REGENERATE_COMMAND" in settings:
        # The push wins here, so the producer never runs. Point it at the
        # harness one anyway: the pipeline's own `assemble` anchors its paths on
        # the installed repository, so a regression that made it run would write
        # into the working repository rather than fail the test.
        settings = {**settings, "REGENERATE_COMMAND": _rebuild_command(SUBSTITUTED_DATE)}

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
def test_a_racing_append_to_the_same_ledger_unions_instead_of_conflicting(
    tmp_path: Path,
) -> None:
    """Two runs appended two independent rows. Both belong, and nothing has to choose.

    This is where the loop used to die. `git pull --rebase origin main` was the
    one unguarded command in it, so a conflicting rebase ended the script inside
    attempt 1 under `set -e`: no attempt 2, no failure message, no day, and a
    checkout left mid-rebase. Measured that way on 2026-08-25, git 2.55.0, bash
    5.3.15. The ledgers carry `merge=union` now, so the union of both appends is
    the merge, and every command in the loop is guarded.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, f"{staged_paths[0]}/ledger.csv", "header\nrow-0\ntheirs\n")
    _write(runner / staged_paths[0] / "ledger.csv", "header\nrow-0\nours\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert _git(origin, env, "log", "--format=%s", "-2").splitlines() == [
        settings["COMMIT_MESSAGE"],
        "racing change",
    ]
    landed = _git(origin, env, "show", f"main:{staged_paths[0]}/ledger.csv").splitlines()
    assert landed[0] == "header"
    assert sorted(landed[1:]) == ["ours", "row-0", "theirs"]
    assert not _mid_rebase(runner)


@requires_bash
def test_a_rebase_it_cannot_finish_still_ends_the_script_cleanly(tmp_path: Path) -> None:
    """The guard, proved by running it: no command in the loop can exit early.

    A ledger retired upstream while this run appended to it is a modify/delete,
    which no merge driver resolves. The loop must abort the rebase, say what
    happened, print the failure message and leave the checkout usable - not stop
    on the line that failed.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    other = tmp_path / "other"
    _git(tmp_path, env, "clone", str(tmp_path / "origin.git"), str(other))
    _git(other, env, "rm", "--quiet", f"{staged_paths[0]}/ledger.csv")
    _git(other, env, "commit", "-m", "retire the ledger")
    _git(other, env, "push", "origin", "main")
    _write(runner / staged_paths[0] / "ledger.csv", "header\nrow-0\nours\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert "the rebase did not apply cleanly" in result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] in result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == "retire the ledger"
    assert not _mid_rebase(runner)


@requires_bash
@requires_space_free_paths
def test_the_day_publishes_when_origin_moved_under_it(tmp_path: Path) -> None:
    """The Oracle: a stale base is answered by a current base, not by a text merge.

    Run `32772221068` lost a finished day here. The assemble job checks out
    main's tip at TRIGGER time and the run takes 164-184 min, so the day was
    always rebuilt from a base up to three hours old, and the push found a main
    that had moved. Here it has moved twice: another run published the same day,
    and a pull request merged on top.

    So the day is refreshed from the tip the push wants and built again against
    it. Both runs' items reach the reader, both runs' rows reach all three
    ledgers exactly once, the pull request is untouched, and this run's rendered
    chart - which no producer in this job can make again - is still there.
    """
    date = SUBSTITUTED_DATE
    month = date[:7]
    staged_paths, settings = _commit_call("assemble")
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command(date),
        "RENUMBER_COMMAND": _renumber_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(
        tmp_path, env, date, ["item-c"], "Merge pull request #123 from someone/branch"
    )
    # This run: the routes artifact unpacked a chart into the day's directory,
    # and assemble published two items on the base the checkout carried.
    _write(runner / SUBSTITUTED_DAY_DIR / "assets" / "chart-1.svg", "<svg />\n")
    _rebuild(runner, env, date, ["item-d", "item-e"])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert "rebuilding the day against origin/main" in result.stdout
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert _git(origin, env, "log", "--format=%s", "-3").splitlines() == [
        f"digest: {date}",
        "Merge pull request #123 from someone/branch",
        f"digest: {date}",
    ]

    day = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/digest.json"))
    assert day["items"] == ["item-a", "item-b", "item-c", "item-d", "item-e"]
    # Run three, not a second run two. The rebuild read the day origin holds, so
    # it knows which run it is; on its own last attempt it would not.
    assert day["runs"] == [
        {"n": 1, "items_added": 2},
        {"n": 2, "items_added": 1},
        {"n": 3, "items_added": 2},
    ]
    manifest = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/run.json"))
    assert manifest["runs"] == day["runs"]

    published = _rows(_git(origin, env, "show", "main:state/published.csv"))
    scores = _rows(_git(origin, env, "show", "main:state/scores.csv"))
    health = _rows(_git(origin, env, "show", f"main:state/item-health/{month}.csv"))
    every_item = ["item-a", "item-b", "item-c", "item-d", "item-e"]
    # Exactly once each. Two of these ledgers append blind, so a rebuild against
    # a base that already held this run's rows would show five items and seven
    # rows.
    assert [row["item_id"] for row in published] == every_item
    assert [row["item_id"] for row in scores] == every_item
    assert [row["item_id"] for row in health] == every_item

    telemetry = _rows(_git(origin, env, "show", f"main:frontend/public/telemetry/{month}.csv"))
    assert telemetry == health, "the public projection is a rewrite of item-health, not a merge"

    assert _git(origin, env, "show", "main:docs/unrelated.md") == "merged by a pull request\n"
    assert _tracked(origin, env, f"{SUBSTITUTED_DAY_DIR}/assets/chart-1.svg")
    assert (runner / SUBSTITUTED_DAY_DIR / "assets" / "chart-1.svg").is_file()
    assert not _mid_rebase(runner)


@requires_bash
@requires_space_free_paths
def test_two_runs_that_numbered_a_chart_the_same_both_keep_it(tmp_path: Path) -> None:
    """The Oracle above, with the one thing it never had: both sides create the path.

    Run `32869125768` finished eight workers and a router and then lost the
    whole day here. A chart is filed by its vertical and its ordinal within the
    day, and the ordinal is seeded by reading the day's directory - so two runs
    of one day, neither able to see what the other pushed, both wrote
    `energy-01.svg` for different items with different bytes. Git cannot rebase
    two adds of one path, `assemble` exited 1, and the `items-*` artifacts
    expired with every summary in them.

    The tip's chart is published and a reader may already hold that address, so
    the tip's never moves. This run's takes the next free number, the route
    payload naming it moves with it, and the rebuilt day points at a file that
    is really there.
    """
    date = SUBSTITUTED_DATE
    theirs, ours = "energy-0000000001", "energy-0000000002"
    staged_paths, settings = _commit_call("assemble")
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command(date),
        "RENUMBER_COMMAND": _renumber_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(
        tmp_path,
        env,
        date,
        [theirs],
        "Merge pull request #125 from someone/branch",
        charts={theirs: RACED_ASSET},
    )
    # This run's router numbered from a directory that could not see the push
    # above, so it wrote the same path for a different item.
    _chart(runner, date, ours, RACED_ASSET)
    _rebuild(runner, env, date, [ours])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert f"{RACED_ASSET} is already published, so this run's copy moved" in result.stdout
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert not _mid_rebase(runner)

    day = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/digest.json"))
    assert day["items"] == ["item-a", "item-b", theirs, ours]
    # Neither run lost its picture, and no two items share one.
    assert day["visuals"] == {theirs: RACED_ASSET, ours: NEXT_FREE_ASSET}
    assert len(set(day["visuals"].values())) == len(day["visuals"])
    # The gate a broken image would fail: every path the day publishes is a file
    # the day publishes. A picture that 404s is worse than a job that stops.
    for relpath in day["visuals"].values():
        assert _tracked(origin, env, f"frontend/public/{relpath}")
    # And the published one is byte-for-byte the one that was published, rather
    # than this run's chart wearing its address.
    assert _git(origin, env, "show", f"main:frontend/public/{RACED_ASSET}") == (
        f"<svg>{theirs}</svg>\n"
    )
    assert _git(origin, env, "show", f"main:frontend/public/{NEXT_FREE_ASSET}") == (
        f"<svg>{ours}</svg>\n"
    )
    assert _git(origin, env, "show", "main:docs/unrelated.md") == "merged by a pull request\n"


@requires_bash
@requires_space_free_paths
def test_a_rebuild_that_fails_spends_the_attempts_and_says_which(tmp_path: Path) -> None:
    """A producer that cannot run is a lost day, said out loud, not a half-rebased tree."""
    date = SUBSTITUTED_DATE
    staged_paths, settings = _commit_call("assemble")
    # A date this checkout has no artifacts for: the producer really fails, on a
    # real missing input, rather than being told to pretend.
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command("2026-08-24"),
        "RENUMBER_COMMAND": _renumber_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(tmp_path, env, date, ["item-c"], "Merge pull request #124 from someone/other")
    _rebuild(runner, env, date, ["item-d"])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert "the rebuild failed against origin/main" in result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] in result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == (
        "Merge pull request #124 from someone/other"
    )
    assert not _mid_rebase(runner)


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


def test_every_setup_python_pin_is_inside_the_declared_interpreter_range() -> None:
    """`requires-python` is the only thing that refuses an interpreter early.

    Without it pip does not stop - it falls back to a source build and hangs
    with no error at all. The bound is therefore load-bearing, and it has to
    agree with what CI installs in both directions: a CI pin above the ceiling
    installs an environment nobody can reproduce locally, and a ceiling below
    the pin breaks every run. Neither file mentions the other, so only this
    test keeps them together.
    """
    document = tomllib.loads(read_text(REPO_ROOT / "pyproject.toml"))
    declared = _mapping(document.get("project"), "pyproject [project]").get("requires-python")
    assert isinstance(declared, str), "pyproject must declare requires-python"

    bounds = re.fullmatch(r">=(\d+)\.(\d+),<(\d+)\.(\d+)(?:\.0a0)?", declared)
    assert bounds is not None, f"requires-python must carry both bounds: {declared}"
    floor = (int(bounds.group(1)), int(bounds.group(2)))
    ceiling = (int(bounds.group(3)), int(bounds.group(4)))

    pins = [
        (filename, job_name, version)
        for filename, workflow in _load_workflows().items()
        for job_name, version in _setup_python_versions(workflow)
    ]
    assert pins, "no workflow sets Python up"

    for filename, job_name, version in pins:
        where = f"{filename}/{job_name}"
        match = re.fullmatch(r"(\d+)\.(\d+)", version)
        assert match is not None, f"{where} must pin a major.minor, not {version}"
        minor = (int(match.group(1)), int(match.group(2)))
        assert floor <= minor < ceiling, f"{where} pins {version}, outside {declared}"


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
