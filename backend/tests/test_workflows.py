"""Contract tests for GitHub Actions display names and event routing."""

from __future__ import annotations

import copy
import csv
import datetime
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Final, cast

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import CONFIG_DIR, REPO_ROOT, llama_server_flags, read_text

from idhazh import ledger
from idhazh.contracts.route import Route, SpecFormat, VisualKind, VisualState

WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
SCRIPTS_DIR: Final = REPO_ROOT / ".github" / "scripts"

EXPECTED_WORKFLOWS: Final = {
    "backfill.yml": ("Vector backfill", frozenset({"workflow_dispatch"})),
    "ci.yml": ("CI", frozenset({"pull_request", "push", "workflow_dispatch"})),
    "digest.yml": ("Content refresh", frozenset({"schedule", "workflow_dispatch"})),
    "drift.yml": ("Drift review", frozenset({"schedule", "workflow_dispatch"})),
    "measure.yml": ("Measurements", frozenset({"workflow_dispatch"})),
    "pages.yml": (
        "Pages publication",
        frozenset({"push", "workflow_run", "workflow_dispatch"}),
    ),
    "prune.yml": ("Corpus prune", frozenset({"schedule", "workflow_dispatch"})),
    "validate.yml": ("Model validation", frozenset({"workflow_dispatch"})),
}

CONTENT_REFRESH_UTC_HOURS: Final = (2, 6, 10, 14, 18)
# Every `workflow_dispatch` input in the repository, and the evidence that its
# value is shaped before anything acts on it. Discovery is closed-world, so a
# new input fails here until somebody writes down which of the three it is and
# the test finds the evidence in the file.
#
# `CHOICE` and `BOOLEAN` are the platform's own enumeration: GitHub renders a
# menu or a checkbox and no other value can be submitted. `READ_BY_NAME` means
# the value never lands in a script - it reaches a step as an environment
# variable, and the program that reads it decides what it means. Anything else
# is an anchored pattern the workflow matches the value against, and the value
# is one somebody could publish a wrong day with.
DISPATCH_CHOICE: Final = "choice"
DISPATCH_BOOLEAN: Final = "boolean"
DISPATCH_READ_BY_NAME: Final = "read by name"
DISPATCH_INPUT_SHAPES: Final[dict[tuple[str, str], str]] = {
    ("backfill.yml", "commit"): DISPATCH_BOOLEAN,
    # The one that decides a published address. See the two tests that run the
    # step for what it accepts and what it now stops.
    ("digest.yml", "date"): "^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$",
    ("digest.yml", "faithfulness"): DISPATCH_BOOLEAN,
    ("digest.yml", "shards"): DISPATCH_CHOICE,
    ("drift.yml", "baseline_days"): "^[0-9]{1,4}$",
    ("drift.yml", "recent_days"): "^[0-9]{1,4}$",
    ("measure.yml", "corpus_links"): "^[1-9][0-9]{0,4}$",
    ("measure.yml", "models"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "runtime_candidate"): DISPATCH_CHOICE,
    ("measure.yml", "runtime_threads"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "runtime_threads_batch"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "target"): DISPATCH_CHOICE,
    ("measure.yml", "threads"): "^[1-9][0-9]*$",
    ("prune.yml", "force"): DISPATCH_BOOLEAN,
    ("validate.yml", "candidate_bytes"): "^[0-9]{1,15}$",
    ("validate.yml", "candidate_file"): DISPATCH_READ_BY_NAME,
    ("validate.yml", "candidate_id"): DISPATCH_READ_BY_NAME,
    ("validate.yml", "candidate_quantisation"): DISPATCH_READ_BY_NAME,
    ("validate.yml", "candidate_repo"): DISPATCH_READ_BY_NAME,
    ("validate.yml", "candidate_revision"): DISPATCH_READ_BY_NAME,
    ("validate.yml", "candidate_sha256"): DISPATCH_READ_BY_NAME,
    ("validate.yml", "corpus_per_shard"): "^[1-9][0-9]{0,3}$",
    ("validate.yml", "job_budget_minutes"): "^[1-9][0-9]{0,3}$",
    ("validate.yml", "repeats"): "^[1-9][0-9]{0,3}$",
    ("validate.yml", "shards"): "^[1-8]$",
}
# The one variable digest.yml's `decide` step reads. Nothing else in that
# script may be an expression: a value pasted into a script is text before it
# is a value, and no pattern below the paste can see what it already changed.
DECIDE_ENV: Final = "DISPATCH_DATE"
# What a person types when they mean a day. Each of these publishes to an
# address no reader and no archive page looks at, and none of them fails
# anywhere else in the run.
UNPUBLISHABLE_DATES: Final = (
    "2026-8-27",
    "2026-08-27 ",
    " 2026-08-27",
    "2026/08/27",
    "27-08-2026",
    "2026-13-45",
    "yesterday",
)
# The shell linter and the one directory it reads. It cannot see a `run:` body,
# so the shell written inline in a workflow is held by the tests in this file
# instead.
SHELLCHECK_STEP: Final = "Lint the shell"
SHELLCHECK_COMMAND: Final = "shellcheck --severity=style .github/scripts/*.sh"
# The ceiling, not the dispatch rule. Rule #2 allows 20 concurrent jobs; a regex
# held the fan-out at four. The empty-input default below stays at four, because
# that is what every scheduled run gets and no eight-shard run is measured yet.
CONTENT_REFRESH_SHARDS: Final = frozenset({"1", "2", "3", "4", "5", "6", "7", "8"})
CONTENT_REFRESH_SHARD_DEFAULT: Final = "4"
# How long a worker may run and how many run at once. Both were literals in the
# work job while `config/idhazh.json` declared different numbers that nothing
# read, so config was a wrong answer with a schema behind it (Rule #6).
WORK_BOUND_KEYS: Final = frozenset({"timeout-minutes", "max-parallel"})

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
# One spelling for every download in the repository, weights and runtime alike.
# `-f` is the load-bearing letter: without it curl writes an HTTP error body
# into the file and exits 0. For a `.gguf` that matters twice over, because
# `backend/models` is a cache path in the daily run - the bad file is then saved
# under the pinned key and handed to every later run until the entry is evicted.
WEIGHTS_FETCH_FORM: Final = "curl -fsSL --retry 3 --retry-all-errors"
RELEASE_LOOKUP_FORM: Final = "curl -fsS -H"
# Every job in the repository that downloads a `.gguf`: the step that fetches
# it, the step that checks it, the first step that reads it, and the one place
# the expected digest is written. Discovery is closed-world - a tenth workflow
# that fetches weights fails the test until it appears here with a check.
WEIGHTS_CHECKS: Final = {
    ("digest.yml", "work"): (
        "Fetch runtime and weights",
        "Verify the weights",
        "Start the model",
        '["models"]["summarize"]["sha256"]',
    ),
    ("digest.yml", "route"): (
        "Fetch runtime and router weights",
        "Verify the router weights",
        "Start the router",
        '["models"]["route"]["sha256"]',
    ),
    ("measure.yml", "runtime"): (
        "Fetch runtime and weights",
        "Verify the weights",
        "Measure runtime candidate",
        '["models"]["summarize"]["sha256"]',
    ),
    ("measure.yml", "batched"): (
        "Download the summarizer weights",
        "Verify the weights",
        "Benchmark parallel decode",
        '["models"]["summarize"]["sha256"]',
    ),
    # The one candidate whose digest is not a config field: the plan job decides
    # it once, from the dispatch input or from config, and republishes it.
    ("validate.yml", "qualify"): (
        "Fetch the runtime and the candidate",
        "Verify the candidate bytes",
        "Start the candidate",
        "${{ needs.plan.outputs.candidate_sha256 }}",
    ),
}
# The refs the daily run needs and the one place they are written. The
# `plan` job reads `config/idhazh.json` and republishes them, so the workflow
# holds no model repo, no weights filename and no upload of those weights.
MODEL_REF_OUTPUTS: Final = (
    "summarize_repo",
    "summarize_revision",
    "summarize_file",
    "route_repo",
    "route_revision",
    "route_file",
)
MODEL_REF_FIELDS: Final = ("repo", "revision", "file")
# What the daily run used to call them at workflow scope. Named here so the
# defect cannot come back under its own name at any scope.
MODEL_ENV_NAMES: Final = frozenset(
    {
        "MODEL_REPO",
        "MODEL_REVISION",
        "MODEL_FILE",
        "ROUTE_REPO",
        "ROUTE_REVISION",
        "ROUTE_FILE",
    }
)
# The weights cache jobs, and the config role each one serves.
WEIGHTS_CACHE_ROLES: Final = {"work": "summarize", "route": "route"}
# Bumped from v3 when the weights half of the key moved off the workflow `env`
# copy, so the first run after that lands refetches once instead of restoring an
# entry nobody can attribute.
WEIGHTS_CACHE_SUFFIX: Final = "v4"
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
    "work": ("llama-server.log", "summarize_file"),
    "route": ("router.log", "route_file"),
}
RUNTIME_IDENTITY_STEP: Final = "What this runner is"
# One loopback port per workflow, declared once. `server_argv` binds it, every
# probe reads it, and `idhazh.llm.server` reads it for the address the stage
# posts to - so a moved port cannot leave a server on one and a client on
# another (Rule #6).
LLAMA_PORT_ENV: Final = "LLAMA_PORT"
LLAMA_PORT_VALUE: Final = "8080"
LLAMA_PORT_READ: Final = "http://127.0.0.1:${LLAMA_PORT}"
# Every step in the repository that stands a llama-server up, and the config
# root each one reads. Discovery in the test is closed-world, so a new one fails
# here until it appears with an install ahead of it.
SERVER_STARTERS: Final = {
    ("digest.yml", "work"): ("Start the model", "config"),
    ("digest.yml", "route"): ("Start the router", "config"),
    ("measure.yml", "runtime"): ("Measure runtime candidate", None),
    ("validate.yml", "qualify"): ("Start the candidate", "backend/var/candidate-config"),
}
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
SERVER_LOG_FILE: Final = "llama-server.log"
MEMORY_PEAK_FILE: Final = "memory-peak.txt"
CGROUP_PEAK_PATH: Final = "/sys/fs/cgroup/memory.peak"
#: The one reading that has to be taken at both ends of the job. `/proc/stat`
#: counts since boot, so a single read is mostly the minutes the runner spent
#: booting. `/proc/stat` rather than a cgroup file because two cgroup files this
#: repository has read - `memory.peak` and `cpu.max` - are absent on a
#: GitHub-hosted runner, and `/proc/stat` is on every Linux there is.
CPU_STAT_READING: Final = "awk '/^cpu / { print }' /proc/stat"
# llama-server's own loopback counters, read once at job end. The two series are
# named because they are the two a run is read by: the busy-slot average says
# whether batching ever happened, and the high watermark says how close the day
# came to `n_ctx`. Both spellings were read from `tools/server/README.md` in
# ggml-org/llama.cpp on 2026-08-25.
METRICS_FILE: Final = "llama-metrics.prom"
METRICS_ENDPOINT: Final = "http://127.0.0.1:${LLAMA_PORT}/metrics"
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
#
# Keyed by a label rather than by a job, because the assemble job commits twice:
# the day, and then the telemetry months the fold took out of full grain. The
# second one has to come after the first (see the workflow's own comment), so
# they cannot be one call.
COMMIT_SCRIPT: Final = SCRIPTS_DIR / "commit-and-push.sh"
COMMIT_SCRIPT_CALL: Final = ("bash", ".github/scripts/commit-and-push.sh")
COMMIT_JOBS: Final = {
    "plan": "plan",
    "work": "work",
    "assemble": "assemble",
    "fold": "assemble",
}
COMMIT_STEPS: Final = {
    "plan": "Commit what the plan saw",
    "work": "Commit what this shard measured",
    "assemble": "Commit the day",
    "fold": "Commit the folded telemetry",
}
COMMIT_BASE_ENV: Final = frozenset(
    {"COMMIT_MESSAGE", "NOTHING_STAGED_MESSAGE", "PUSH_FAILED_MESSAGE"}
)
# Only assemble can rebuild what it commits, so only assemble carries the three
# settings that make the loop rebuild instead of merge - and only assemble
# commits rendered assets, so only assemble drops a raced one.
COMMIT_SCRIPT_ENV: Final = {
    "plan": COMMIT_BASE_ENV,
    # The one recording step whose ledgers declare a key. Its filters read a
    # checkout frozen at the commit this run was triggered at, so a second
    # attempt cannot see the first attempt's pushed rows and the union keeps
    # both - which is what the post-merge pass is for.
    "work": COMMIT_BASE_ENV | {"DROP_REPEATED_ROWS_COMMAND"},
    "assemble": COMMIT_BASE_ENV
    | {"REFRESH_PATHS", "REGENERATE_COMMAND", "DROP_RACED_ASSETS_COMMAND"},
    "fold": COMMIT_BASE_ENV,
}
COMMIT_STAGED_PATHS: Final = {
    "plan": ["state/seen", "state/feed-health"],
    "work": ["state/item-health", "state/scores", "state/runtime-counters.csv"],
    "assemble": [
        "frontend/public/digest",
        "frontend/public/telemetry",
        "frontend/public/assist/index",
        "state",
        "corpus",
    ],
    # `state` whole, and deliberately not the two directories the fold touches:
    # `state/telemetry-aggregate/` does not exist in a fresh checkout, and
    # `git add` on a path that is not there aborts the whole step.
    "fold": ["state"],
}
# The step that folds an out-of-window month before the step above commits it.
# It runs after the day's own commit, so a retirement that loses its push costs
# one run's bytes and never a published day.
FOLD_STEP: Final = "Retire the ledger shards the pipeline no longer reads"
FOLD_COMMAND: Final = "python -m idhazh prune-state"
# The step that fills the two ledgers the step above commits, and the two things
# that decide which items are this shard's.
RECORD_STEP: Final = "Record what this shard measured"
RECORD_COMMAND: Final = "python -m idhazh record"
# The step that adds this run's accepted pairs to the training window. It runs
# in assemble because that is where the article text still exists: `items/` is
# gitignored and travels as a one-day artifact, so a workflow of its own would
# check out a fresh tree and harvest nothing. It may not fail the publish.
HARVEST_STEP: Final = "Harvest the training corpus"
HARVEST_COMMAND: Final = "python -m idhazh harvest"
# The seed a fresh checkout must already carry, because `commit-and-push.sh`
# runs `git add "$@"` under `set -euo pipefail` - a staged path that does not
# exist yet aborts the whole commit step and costs the ledgers staged beside it.
CORPUS_SEED: Final = ("corpus/corpus.jsonl", "corpus/corpus.meta.json", "corpus/holdout.txt")
# The third ledger the same commit step stages: what llama-server itself counted
# for this shard. It has to sit between the other two, because the row it writes
# is committed by the step after it.
COUNTERS_STEP: Final = "What the server counted"
COUNTERS_COMMAND: Final = "python -m idhazh counters"
# Deliberately not `--metrics`: that is llama-server's own flag, and
# `test_every_job_that_starts_a_server_reaches_the_one_argv_builder` forbids any
# workflow step from spelling one.
COUNTERS_FLAG: Final = "--counters-file"
# The step that stamps the shard job's own clock and names the host it drew.
# First in the job, so the clock covers the cache restore and the weight load as
# well as the model time, and read at the counters step - which is the only step
# that writes a committed row at shard grain.
CLOCK_STEP: Final = "Stamp the shard clock and the host"
CLOCK_VARIABLES: Final = ("JOB_STARTED_AT", "CPU_MODEL", "CPU_STAT_AT_START")
# Neither of the work job's two steps may fail the shard. See the comment above
# them in the workflow for which loss is the cheaper one. `BaseLoader` keeps
# every scalar a string, so the value to compare is the word, not the boolean.
WORK_LEDGER_STEPS: Final = (RECORD_STEP, COUNTERS_STEP, COMMIT_STEPS["work"])
TOLERATED: Final = "true"
COMMIT_IDENTITY: Final = "yen-idhazh pipeline <pipeline@yen-idhazh.invalid>"
#: Every file that configures git before a job commits. A runner carries no
#: identity of its own, so each of these has to set one, and two copies of a
#: name drift in silence unless something reads both.
#: `.invalid` is reserved by RFC 2606, so the address can never route anywhere.
GIT_IDENTITY_SOURCES: Final = (
    SCRIPTS_DIR / "commit-and-push.sh",
    WORKFLOWS_DIR / "prune.yml",
)
# What a `${{ }}` expression stands in for when a test runs the real call site
# outside Actions. `day_dir` is the digest date as a path, which is what lets the
# refresh set name `digest.json` and `run.json` one file at a time.
SUBSTITUTED_DATE: Final = "2026-08-25"
SUBSTITUTED_DAY_DIR: Final = "frontend/public/digest/2026/08/25"
SUBSTITUTED_SHA: Final = "0" * 40
SUBSTITUTED_SHARD: Final = "3"
SUBSTITUTED_SHARDS: Final = "8"
EXPRESSION_VALUES: Final = {
    "needs.plan.outputs.date": SUBSTITUTED_DATE,
    "needs.plan.outputs.day_dir": SUBSTITUTED_DAY_DIR,
    "needs.plan.outputs.shards": SUBSTITUTED_SHARDS,
    "steps.decide.outputs.date": SUBSTITUTED_DATE,
    "github.sha": SUBSTITUTED_SHA,
    "matrix.shard": SUBSTITUTED_SHARD,
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
        "frontend/public/assist/index",
        "state/published.csv",
        "state/scores",
        "state/item-health",
        "state/runtime-counters.csv",
    ],
}
# The producer the harness drives through the loop. See its own docstring for
# why the pipeline's `assemble` cannot be the one under a temporary clone.
REBUILD_STAND_IN: Final = Path(__file__).with_name("rebuild_day.py")
# The post-merge pass, for the same reason: the shipped stage resolves `state/`
# off the installed package, so under a test it would settle the developer's own
# repository rather than the temporary clone. The stand-in calls the shipped
# function with a path relative to the runner's working directory.
SETTLE_STAND_IN: Final = Path(__file__).with_name("settle_ledger.py")
# The drop, by contrast, IS the shipped one: it anchors on the working
# directory, so it runs inside a temporary clone unchanged.
DROP_ENTRY_POINT: Final = REPO_ROOT / "backend" / "utilities" / "drop_raced_assets.py"
RUN_ARTIFACTS: Final = "backend/var/run"
# One rendered chart, as the route job leaves it: an SVG in the day's directory
# and a route payload saying where it landed. The name is the item's own id, so
# a path both runs hold is that one item rendered twice.
RACED_ITEM_ID: Final = "energy-0000000001"
RACED_ASSET: Final = f"digest/{SUBSTITUTED_DATE.replace('-', '/')}/{RACED_ITEM_ID}.svg"


_PARSED_WORKFLOWS: dict[str, dict[str, object]] | None = None


def _parsed_workflows() -> dict[str, dict[str, object]]:
    """Every workflow in the repository, read and parsed once for the whole session.

    152,564 bytes of YAML through PyYAML's pure-Python loader, and this file
    asks for it 104 times a run - 64.0 s of a 351.1 s run, measured 2026-08-30
    on Windows 11, 12 logical CPUs. Nothing rewrites a workflow while the suite
    is running, so no two of those parses can disagree.
    """
    global _PARSED_WORKFLOWS
    if _PARSED_WORKFLOWS is not None:
        return _PARSED_WORKFLOWS

    paths = sorted((*WORKFLOWS_DIR.glob("*.yml"), *WORKFLOWS_DIR.glob("*.yaml")))
    assert {path.name for path in paths} == set(EXPECTED_WORKFLOWS)

    workflows: dict[str, dict[str, object]] = {}
    for path in paths:
        document = yaml.load(read_text(path), Loader=yaml.BaseLoader)
        assert isinstance(document, dict), f"{path.name} must contain a YAML mapping"
        workflows[path.name] = cast(dict[str, object], document)
    _PARSED_WORKFLOWS = workflows
    return workflows


def _load_workflows() -> dict[str, dict[str, object]]:
    """This caller's own copy of the parsed workflows.

    Copied rather than shared, because a caller that edited one would be editing
    what every later test reads - and that failure is order-dependent, so the
    file would pass alone and fail in the full suite. The copy costs 0.7 ms
    against the 111 ms parse it stands in for (2026-08-30, same box).
    """
    return copy.deepcopy(_parsed_workflows())


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


def _declared_dispatch_inputs(workflow: dict[str, object]) -> dict[str, object]:
    """The dispatch inputs a workflow declares, and `{}` when it declares none.

    `ci.yml` and `pages.yml` take a dispatch with no form at all, so the
    enumeration below has to tell "no inputs" apart from "a shape nobody wrote
    down" rather than failing on the first workflow it reads. A key with no
    value loads as the empty string, not as `None`.
    """
    dispatch = _triggers(workflow).get("workflow_dispatch")
    if not dispatch:
        return {}
    inputs = _mapping(dispatch, "workflow_dispatch").get("inputs")
    if not inputs:
        return {}
    return _mapping(inputs, "workflow_dispatch inputs")


def _run_bodies(workflow: dict[str, object]) -> list[str]:
    return [
        script
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if isinstance(script := step.get("run"), str)
    ]


def _names_the_input(text: str, name: str) -> bool:
    return re.search(rf"inputs\.{re.escape(name)}\b", text) is not None


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


def _values_keyed(node: object, names: frozenset[str]) -> list[tuple[str, str]]:
    """Every value under one of `names`, at any depth of a job body.

    Recursive rather than top-level: a step-level `timeout-minutes` written as a
    literal is the same defect as a job-level one, one level down.
    """
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in cast(dict[str, object], node).items():
            if key in names and isinstance(value, str):
                found.append((key, value))
            found.extend(_values_keyed(value, names))
    elif isinstance(node, list):
        for item in cast(list[object], node):
            found.extend(_values_keyed(item, names))
    return found


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


def _weights_fetch_steps(
    workflows: Mapping[str, dict[str, object]],
) -> dict[tuple[str, str], tuple[str, str]]:
    """Every step in the repository that downloads a `.gguf`, found not listed.

    Keyed by workflow and job, valued by the step's name and its shell. The
    search is over every workflow file, so a new one that fetches weights turns
    up here whether or not anybody remembered to pin it.
    """
    found: dict[tuple[str, str], tuple[str, str]] = {}
    for filename, workflow in workflows.items():
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            for step in _steps(workflow, job_name):
                script = step.get("run")
                if not (isinstance(script, str) and "huggingface.co/" in script):
                    continue
                name = step.get("name")
                assert isinstance(name, str), f"{filename}/{job_name}: name the fetch step"
                where = (filename, job_name)
                assert where not in found, f"{filename}/{job_name} fetches weights twice"
                found[where] = (name, script)
    return found


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


def _expression(body: str) -> str:
    return "${{ " + body + " }}"


def _plan_output(name: str) -> str:
    return _expression(f"needs.plan.outputs.{name}")


def _every_env(workflow: dict[str, object]) -> list[tuple[str, dict[str, object]]]:
    """Every `env` mapping in a workflow, at all three scopes it can appear at.

    A job-scoped or step-scoped copy of a model ref is the same defect as the
    workflow-scoped one that was deleted, so the search cannot stop at the top.
    """
    scopes: list[tuple[str, dict[str, object]]] = []
    if (top := workflow.get("env")) is not None:
        scopes.append(("workflow", _mapping(top, "workflow env")))
    for job_name in _mapping(workflow.get("jobs"), "jobs"):
        if (job_env := _job(workflow, job_name).get("env")) is not None:
            scopes.append((f"job {job_name}", _mapping(job_env, f"job {job_name} env")))
        for step in _steps(workflow, job_name):
            if (step_env := step.get("env")) is None:
                continue
            label = step.get("name") or step.get("id") or step.get("uses")
            where = f"job {job_name} step {label}"
            scopes.append((where, _mapping(step_env, f"{where} env")))
    return scopes


def _run_the_inline_program(script: str, config_root: Path) -> dict[str, str]:
    """Run the program a plan-job step carries, and read what it would write.

    The step redirects its stdout into `$GITHUB_OUTPUT`, so its stdout IS the
    job output. Running the shipped bytes against a real config directory is
    what makes this a test of the step rather than of a copy of it.
    """
    match = re.search(r"<<'PY'[^\n]*\n(.*?)\nPY(?:\n|$)", script, flags=re.DOTALL)
    assert match is not None, "the step must carry an inline program"

    result = subprocess.run(
        [sys.executable, "-c", match.group(1)],
        cwd=config_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip())
    return dict(
        cast(tuple[str, str], tuple(line.split("=", 1)))
        for line in result.stdout.splitlines()
        if line
    )


def _decide_script(step: dict[str, object]) -> str:
    """digest.yml's `decide` step, with its one remaining expression resolved.

    A scheduled run passes no inputs at all, so `faithfulness` stands in as the
    empty string a schedule really delivers. Nothing else may be an expression:
    the date has to arrive as a variable, or the pattern below it is reading a
    script somebody else already edited.
    """
    script = _script(step, "digest.yml/plan/decide").replace(
        _expression("inputs.faithfulness"), ""
    )
    assert "${{" not in script, "the decide step reads the dispatch date by name, not by paste"
    return script


def _run_the_decide_step(
    dispatch_date: str, tmp_path: Path
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    """Run the shipped `decide` step against one dispatch value, and read its output.

    The step redirects into `$GITHUB_OUTPUT`, so that file IS what the rest of
    the run reads. Running the shipped bytes is what makes this a test of the
    step rather than of a second copy of its pattern.
    """
    bash = _bash()
    assert bash is not None
    workflow = _load_workflows()["digest.yml"]
    step = _step(workflow, "plan", "id", "decide")
    script = tmp_path / "decide.sh"
    script.write_text(_decide_script(step), encoding="ascii", newline="\n")
    written = tmp_path / "github-output"
    written.write_text("", encoding="ascii")
    completed = subprocess.run(
        [bash, script.as_posix()],
        cwd=tmp_path,
        env={
            **os.environ,
            DECIDE_ENV: dispatch_date,
            "GITHUB_OUTPUT": written.as_posix(),
        },
        capture_output=True,
        text=True,
    )
    outputs = dict(
        cast(tuple[str, str], tuple(line.split("=", 1)))
        for line in written.read_text(encoding="utf-8").splitlines()
        if line
    )
    return completed, outputs


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


def _commit_call(label: str) -> tuple[list[str], dict[str, str]]:
    """The paths and the strings one daily commit step hands the shared script."""
    workflow = _load_workflows()["digest.yml"]
    job_name = COMMIT_JOBS[label]
    step = _step(workflow, job_name, "name", COMMIT_STEPS[label])
    command = shlex.split(_script(step, f"job {job_name} commit step {label}"))
    assert tuple(command[:2]) == COMMIT_SCRIPT_CALL, (
        f"{label} must commit through {COMMIT_SCRIPT_CALL[1]}"
    )
    declared = _mapping(step.get("env"), f"job {job_name} commit env {label}")
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
    or " " in str(SETTLE_STAND_IN)
    or " " in str(DROP_ENTRY_POINT),
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


def _transient(_directory: str, names: list[str]) -> set[str]:
    """Lock files git's own background maintenance leaves in a template.

    A template is copied once per test and several xdist workers copy the same
    one at the same time. git maintenance can create and delete
    objects/maintenance.lock between copytree listing a directory and
    reading it, which fails the copy with a file that was never part of the
    template anyway.
    """
    return {name for name in names if name.endswith('.lock')}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii", newline="\n")


def _seed_ledger(staged: str) -> str:
    """Where a scripted origin puts the ledger for one staged path.

    A staged path is either a directory of month shards or one named file, and
    the work job stages one of each - so a harness that always appended a
    filename would have built a directory called `scores.csv`.
    """
    return staged if staged.endswith(".csv") else f"{staged}/ledger.csv"


#: Where a built origin lives, keyed by what it holds. A template is built once
#: and copied per test, so the git processes behind the first commit are paid by
#: the session rather than by every test that starts from the same one.
_ORIGIN_TEMPLATES: Final[dict[tuple[str, ...], Path]] = {}


@pytest.fixture(scope="session", autouse=True)
def _discard_origin_templates() -> Iterator[None]:
    """Delete the built origins once the last test that copies one has run."""
    yield
    for root in _ORIGIN_TEMPLATES.values():
        shutil.rmtree(root, ignore_errors=True)
    _ORIGIN_TEMPLATES.clear()


def _template(key: tuple[str, ...]) -> tuple[Path, bool]:
    """The directory this template lives in, and whether it still has to be filled.

    Outside any test's `tmp_path`, because one build serves the whole session -
    and `tmp_path` is removed with the test that owned it.
    """
    root = _ORIGIN_TEMPLATES.get(key)
    if root is not None:
        return root, False
    root = Path(tempfile.mkdtemp(prefix="yen-idhazh-origin-"))
    _ORIGIN_TEMPLATES[key] = root
    return root, True


def _seed_scripted_origin(root: Path, staged_paths: Sequence[str]) -> None:
    """Build the bare origin every commit test starts from, in one template directory."""
    env = _isolated_env(root)
    origin = root / "origin.git"
    _git(root, env, "init", "--bare", "-b", "main", str(origin))
    seed = root / "seed"
    _git(root, env, "clone", str(origin), str(seed))
    for index, staged in enumerate(staged_paths):
        _write(seed / _seed_ledger(staged), f"header\nrow-{index}\n")
    _write(seed / "docs" / "unrelated.md", "seed\n")
    _write(seed / "runner-noise.txt", "clean\n")
    # This repository's own attributes file. `merge=union` on the ledgers is
    # what decides whether two runs that both appended are in conflict, so a
    # scripted origin without it would test a different repository.
    _write(seed / ".gitattributes", read_text(REPO_ROOT / ".gitattributes"))
    _git(seed, env, "add", ".gitattributes", "docs", "runner-noise.txt", *staged_paths)
    _git(seed, env, "commit", "-m", "seed")
    _git(seed, env, "push", "-u", "origin", "main")


def _scripted_origin(
    tmp_path: Path, env: dict[str, str], staged_paths: Sequence[str]
) -> tuple[Path, Path]:
    """A bare origin holding one commit, plus the clone a job would check out.

    Nine tests want the same first commit and building it costs six git
    processes, so it is built once for the session and copied here. Every test
    still gets a repository of its own: the copy is the one it pushes to,
    rebases and rewrites, and nothing ever writes to what was copied.
    """
    root, unbuilt = _template(("scripted", *staged_paths))
    if unbuilt:
        _seed_scripted_origin(root, staged_paths)
    origin = tmp_path / "origin.git"
    shutil.copytree(root / "origin.git", origin, ignore=_transient)
    runner = tmp_path / "runner"
    _git(tmp_path, env, "clone", str(origin), str(runner))
    return origin, runner


def _rebuild_command(date: str) -> str:
    """The producer the harness puts through the loop, as the loop word-splits it."""
    return f"{Path(sys.executable).as_posix()} {REBUILD_STAND_IN.as_posix()} --date {date}"


def _drop_command(date: str) -> str:
    """The shipped raced-asset drop, as the loop word-splits it."""
    return f"{Path(sys.executable).as_posix()} {DROP_ENTRY_POINT.as_posix()} --date {date}"


def _settle_command(relative: str, key: str) -> str:
    """The post-merge pass the harness puts through the loop, as it word-splits it."""
    return (
        f"{Path(sys.executable).as_posix()} {SETTLE_STAND_IN.as_posix()} "
        f"--path {relative} --key {key}"
    )


def _settled_in_the_clone(settings: dict[str, str], relative: str, key: str) -> dict[str, str]:
    """The step's own settings, with the one command that would reach this repository.

    `python -m idhazh dedupe-ledgers` resolves `state/` off the installed
    package, so running it unchanged from a temporary clone would settle the
    working repository's committed ledgers.
    """
    if "DROP_REPEATED_ROWS_COMMAND" not in settings:
        return settings
    return {**settings, "DROP_REPEATED_ROWS_COMMAND": _settle_command(relative, key)}


def _chart(repo: Path, date: str, item_id: str, relpath: str, body: str | None = None) -> None:
    """One rendered chart, exactly as the route job's artifact leaves it.

    An SVG under the day's directory and a real `Route` beside the run's items
    saying where it landed. `body` is what makes two renders of one item differ,
    which is the only case that can now put two adds on one path - identical
    bytes are the case git resolves on its own.
    """
    _write(repo / "frontend" / "public" / relpath, f"<svg>{body or item_id}</svg>\n")
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


def _seed_digest_origin(root: Path, date: str) -> None:
    """Build the origin carrying one published day, in one template directory."""
    env = _isolated_env(root)
    origin = root / "origin.git"
    _git(root, env, "init", "--bare", "-b", "main", str(origin))
    seed = root / "seed"
    _git(root, env, "clone", str(origin), str(seed))
    _write(seed / ".gitattributes", read_text(REPO_ROOT / ".gitattributes"))
    _write(seed / "docs" / "unrelated.md", "seed\n")
    # The corpus seed, exactly as a real checkout carries it. Without it
    # `git add corpus` aborts the commit step and takes the day's ledgers with it.
    for relative in CORPUS_SEED:
        _write(seed / relative, read_text(REPO_ROOT / relative))
    _rebuild(seed, env, date, ["item-a", "item-b"])
    _git(seed, env, "add", ".gitattributes", "docs", *COMMIT_STAGED_PATHS["assemble"])
    _git(seed, env, "commit", "-m", f"digest: {date}")
    _git(seed, env, "push", "-u", "origin", "main")


def _digest_origin(tmp_path: Path, env: dict[str, str], date: str) -> tuple[Path, Path]:
    """An origin carrying a published day, plus the clone the assemble job runs in.

    The day is written by the same producer the loop reruns, so nothing here is
    a hand-made fixture of what that producer emits. It is written once for the
    session and copied here, for the reason `_scripted_origin` gives.
    """
    root, unbuilt = _template(("digest", date))
    if unbuilt:
        _seed_digest_origin(root, date)
    origin = tmp_path / "origin.git"
    shutil.copytree(root / "origin.git", origin, ignore=_transient)
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
    """Five one-slot lines, not one five-hour line, and the difference is load-bearing.

    `github.event.schedule` hands a run the cron line that fired. With one
    `20 2,6,10,14,18 * * *` line that string cannot say which of the five slots
    it was, so a run could not report how late it started - and GitHub drops
    scheduled slots under load without leaving a failed run behind.
    """
    workflows = _load_workflows()
    schedule = _triggers(workflows["digest.yml"])["schedule"]

    assert schedule == [{"cron": f"20 {hour} * * *"} for hour in CONTENT_REFRESH_UTC_HOURS]
    for entry in cast(list[dict[str, str]], schedule):
        fields = entry["cron"].split()
        assert len(fields) == 5, "a five-field cron"
        assert "," not in fields[1], (
            "one hour per line, so github.event.schedule names a single slot"
        )


def test_a_scheduled_run_reports_which_slot_it_is_and_how_late() -> None:
    """The alarm is a report, not a gate. It cannot fix the platform.

    Measured 2026-08-27 to 2026-08-29: 13 slots elapsed, 5 produced a run, and
    every run that started succeeded. Nothing recorded the eight that were never
    created, so this step is the only place the loss becomes visible.
    """
    plan_steps = _steps(_load_workflows()["digest.yml"], "plan")
    late = [step for step in plan_steps if "how late" in str(step.get("name", ""))]

    assert len(late) == 1, "exactly one step reports lateness"
    step = late[0]
    assert step.get("if") == "github.event_name == 'schedule'", (
        "a dispatch has no slot to be late for"
    )
    env = _mapping(step.get("env"), "the lateness step's env")
    assert env.get("SLOT") == "${{ github.event.schedule }}", (
        "the slot arrives through env, never pasted into the script (Rule #11)"
    )
    body = str(step.get("run", ""))
    assert "::warning title=Late run::" in body, "it annotates the run summary"
    assert "10#" in body, "every clock field is forced to base ten, or 08 is octal"


def test_expensive_workflows_do_not_run_on_pull_request_or_push() -> None:
    workflows = _load_workflows()

    for filename in ("backfill.yml", "digest.yml", "measure.yml", "validate.yml"):
        assert {"pull_request", "push"}.isdisjoint(_triggers(workflows[filename]))


def test_every_dispatch_input_is_shaped_before_anything_acts_on_it() -> None:
    """A dispatch form is free text unless somebody constrained it, and a wrong
    value here is not loud - it is a run that finishes and publishes to an
    address nobody looks at.

    Discovery is closed-world. A new input turns up here whether or not anybody
    remembered it, and fails until it is written down as an enumeration, as a
    value read by name, or with the pattern the workflow matches it against.
    """
    workflows = _load_workflows()
    found = {
        (filename, name)
        for filename, workflow in workflows.items()
        for name in _declared_dispatch_inputs(workflow)
    }
    assert found == set(DISPATCH_INPUT_SHAPES), (
        "a dispatch input was added or removed without saying how its value is shaped"
    )

    for (filename, name), shape in sorted(DISPATCH_INPUT_SHAPES.items()):
        workflow = workflows[filename]
        where = f"{filename} input {name}"
        declared = _mapping(_declared_dispatch_inputs(workflow)[name], where)
        if shape == DISPATCH_CHOICE:
            assert declared.get("type") == "choice", f"{where} must be a choice"
            assert _string_list(declared.get("options"), f"{where} options"), (
                f"{where} is a choice with nothing to choose from"
            )
            continue
        if shape == DISPATCH_BOOLEAN:
            assert declared.get("type") == "boolean", f"{where} must be a boolean"
            continue
        if shape == DISPATCH_READ_BY_NAME:
            assert not any(_names_the_input(body, name) for body in _run_bodies(workflow)), (
                f"{where} is read by name, so it may not be pasted into a script"
            )
            assert any(
                _names_the_input(str(value), name)
                for _, scope in _every_env(workflow)
                for value in scope.values()
            ), f"{where} must reach a step through env"
            continue
        assert shape.startswith("^") and shape.endswith("$"), (
            f"{where}: an unanchored pattern matches a prefix, which is not a shape"
        )
        assert any(f"=~ {shape}" in body for body in _run_bodies(workflow)), (
            f"{where} must be matched against {shape} before anything acts on it"
        )


@requires_bash
def test_a_scheduled_run_still_decides_its_own_date(tmp_path: Path) -> None:
    """The pattern runs after the default, so the automatic path is the one it
    is proved against. A schedule passes no inputs at all, and a guard that
    rejected the empty string would take down every run this workflow makes.
    """
    before = datetime.datetime.now(datetime.UTC).date().isoformat()
    completed, outputs = _run_the_decide_step("", tmp_path)
    after = datetime.datetime.now(datetime.UTC).date().isoformat()

    assert completed.returncode == 0, completed.stderr
    assert outputs["date"] in {before, after}, "a scheduled run dates itself in UTC"
    assert outputs["day_dir"] == f"frontend/public/digest/{outputs['date'].replace('-', '/')}"
    assert outputs["faithfulness"] == "true"


@requires_bash
def test_a_dispatched_date_becomes_the_day_it_names(tmp_path: Path) -> None:
    completed, outputs = _run_the_decide_step("2026-08-25", tmp_path)

    assert completed.returncode == 0, completed.stderr
    assert outputs["date"] == "2026-08-25"
    assert outputs["day_dir"] == "frontend/public/digest/2026/08/25"


@requires_bash
@pytest.mark.parametrize("dispatched", UNPUBLISHABLE_DATES)
def test_a_date_that_is_not_a_day_stops_before_it_costs_a_run(
    dispatched: str, tmp_path: Path
) -> None:
    """Each of these reads as a date and publishes as a directory nobody visits.
    None of them fails anywhere else: the stages take the string, the commit
    lands, and the day is simply not where the site looks for it.
    """
    completed, outputs = _run_the_decide_step(dispatched, tmp_path)

    assert completed.returncode == 1, f"{dispatched!r} was accepted as a day"
    assert "YYYY-MM-DD" in completed.stderr
    assert outputs == {}, "a rejected date must not become a fact the run reads"


def test_the_gates_job_lints_the_shell_it_ships() -> None:
    """`ruff` and `mypy` stop at Python. The one script under .github/scripts/
    is the retry loop both daily commit steps run, and a bug in it costs a whole
    day's digest - so it gets a linter of its own, from the same manifest that
    pins the other two.
    """
    steps = _steps(_load_workflows()["ci.yml"], "gates")
    step = _step(_load_workflows()["ci.yml"], "gates", "name", SHELLCHECK_STEP)
    assert _script(step, f"ci.yml/gates/{SHELLCHECK_STEP}").strip() == SHELLCHECK_COMMAND

    names = [item.get("name") for item in steps]
    assert names.index("Install") < names.index(SHELLCHECK_STEP), (
        "shellcheck arrives as a dev dependency, so the install has to run first"
    )
    manifest = tomllib.loads(read_text(REPO_ROOT / "pyproject.toml"))
    dev = manifest["project"]["optional-dependencies"]["dev"]
    assert any(requirement.startswith("shellcheck-py") for requirement in dev), (
        "the linter is pinned by the manifest, not fetched by the step"
    )
    assert list(SCRIPTS_DIR.glob("*.sh")), "the gate reads a glob, so it needs something to read"


#: A change, and what it has to pay for: the browser half at all, and the
#: operator console's own 233 specs inside it. The backend rows are the trap the
#: allow-list exists to avoid - a module the canary day is built through, and a
#: fixture the attack text is read from, can move a published page without
#: touching `frontend/`. The two reading-route rows are the saving: they publish
#: a page and draw nothing the console draws.
BROWSER_SCOPE_CASES: Final = (
    ("frontend/src/routes/console/+page.svelte", True, True),
    ("frontend/src/lib/charts/engine.ts", True, True),
    ("frontend/src/lib/components/KpiCard.svelte", True, True),
    ("frontend/src/lib/server/payload.ts", True, True),
    ("frontend/tests/console-feeds.spec.ts", True, True),
    ("config/idhazh.json", True, True),
    ("backend/idhazh/contracts/item_health.py", True, True),
    ("backend/utilities/build_canary_day.py", True, True),
    ("frontend/src/routes/[date]/+page.svelte", True, False),
    ("frontend/src/lib/assist/loader.ts", True, False),
    ("frontend/src/app.html", True, False),
    ("backend/idhazh/sanitize.py", True, False),
    ("tests/fixtures/canaries/fake-system-delimiter.json", True, False),
    ("docs/reference/measurements.md", False, False),
    ("backend/tests/test_discover.py", False, False),
    ("backend/idhazh/discover.py", False, False),
    ("TODO/some-plan.md", False, False),
)


def _browser_scope(
    tmp_path: Path, changed: Sequence[str], event: str = "pull_request"
) -> dict[str, str]:
    """Run the shipped filter over a real two-commit history and read its answer."""
    env = _isolated_env(tmp_path)
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, env, "init", "--quiet", "--initial-branch=main")
    _write(root / "seed.txt", "seed\n")
    _git(root, env, "add", "seed.txt")
    _git(root, env, "commit", "--quiet", "-m", "seed")
    base = _git(root, env, "rev-parse", "HEAD").strip()
    for name in changed:
        _write(root / name, "changed\n")
        _git(root, env, "add", name)
    _git(root, env, "commit", "--quiet", "-m", "change")
    head = _git(root, env, "rev-parse", "HEAD").strip()

    shell = _bash()
    assert shell is not None
    completed = subprocess.run(
        [shell, (SCRIPTS_DIR / "browser-suite-needed.sh").as_posix()],
        cwd=root,
        env={**env, "EVENT": event, "BASE": base, "HEAD": head},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return dict(
        line.split("=", 1) for line in completed.stdout.strip().splitlines() if "=" in line
    )


@requires_bash
@pytest.mark.parametrize(("changed", "browser", "console"), BROWSER_SCOPE_CASES)
def test_the_browser_half_is_skipped_only_for_a_change_that_cannot_reach_a_page(
    changed: str, browser: bool, console: bool, tmp_path: Path
) -> None:
    """The filter is executed, not read.

    A copy of the pattern in this file would agree with itself forever while the
    shipped script skipped a change that breaks a published page. So the test
    builds a real two-commit history, runs the script the workflow runs, and
    reads the lines it writes to `$GITHUB_OUTPUT`.
    """
    assert _browser_scope(tmp_path, [changed]) == {
        "browser": str(browser).lower(),
        "console": str(console).lower(),
    }


@requires_bash
def test_the_console_half_is_never_bought_without_the_browser_half(tmp_path: Path) -> None:
    """A containment the two patterns must satisfy for any input.

    `SKIP_CONSOLE_SUITE` is only read inside the `browser` job, so a change that
    needed the console specs and not the job would silently run neither. Every
    case in the table is checked rather than the design being asserted in prose.
    """
    for changed, browser, console in BROWSER_SCOPE_CASES:
        assert not (console and not browser), f"{changed} asks for the console with no job"


@requires_bash
def test_one_reaching_path_in_a_mixed_change_still_buys_the_browser_suite(
    tmp_path: Path,
) -> None:
    """A pull request is a set, not one file. Docs beside a frontend edit is the
    ordinary shape of this repo's changes, and the frontend edit decides.
    """
    mixed = ["docs/reference/measurements.md", "frontend/src/routes/+page.svelte"]
    assert _browser_scope(tmp_path, mixed)["browser"] == "true"


@requires_bash
def test_a_push_to_main_never_consults_the_list(tmp_path: Path) -> None:
    """The allow-list is a wager that nobody forgot a path. The merge commit is
    where that wager is settled, so it does not apply there - a pull request the
    list was wrong about reddens `main` within minutes instead of reaching a
    reader.
    """
    assert _browser_scope(tmp_path, ["docs/x.md"], event="push") == {
        "browser": "true",
        "console": "true",
    }


#: Every job that builds the site and then commits what it built, named with the
#: step that publishes. Both jobs write a day payload that can be invalid, so
#: both carry the same two-severity order.
PUBLISHING_SITE_JOBS: Final = (
    ("digest.yml", "assemble", "Commit the day"),
    ("backfill.yml", "backfill", "Commit the repaired days"),
)

#: The step that opens every story in every committed day. Prerendering used to
#: do it for free.
VALIDATE_DAYS_CALL: Final = ("python", "-m", "idhazh", "validate-days")

#: Every job the command has to run in, and what each one buys. The publishing
#: jobs stop a broken day being pushed; `ci.yml` stops one being merged. The
#: pipeline's own pushes never start `ci.yml`, so neither job covers the other.
VALIDATE_DAYS_JOBS: Final = (
    ("ci.yml", "gates"),
    ("digest.yml", "assemble"),
    ("backfill.yml", "backfill"),
)


@pytest.mark.parametrize(("filename", "job_name"), VALIDATE_DAYS_JOBS)
def test_every_committed_day_is_validated_where_the_build_stopped_doing_it(
    filename: str, job_name: str
) -> None:
    """The guard that replaced the one the migration removed.

    A reading document carried every story its day published until 2026-09-01,
    so a story the contract refused failed `npm run build` and could not reach a
    reader. It carries a seed now and the browser fetches the rest, so the build
    never opens the stories past the seed. Nothing else does either, unless this
    step is in the job.

    It takes no path. There is exactly one committed digest tree, so unlike
    `--site-tree` a default here cannot name the wrong one.
    """
    steps = _steps(_load_workflows()[filename], job_name)
    calls = [
        index
        for index, step in enumerate(steps)
        if tuple(shlex.split(str(step.get("run", "")))[:4]) == VALIDATE_DAYS_CALL
    ]
    assert calls, f"{filename}/{job_name} never validates the committed days"
    assert "continue-on-error" not in steps[calls[0]], (
        "a day that fails its contract is a day no reader can read; the step still fails"
    )


@pytest.mark.parametrize(("filename", "job_name", "commit_step"), PUBLISHING_SITE_JOBS)
def test_the_day_is_validated_before_it_is_published(
    filename: str, job_name: str, commit_step: str
) -> None:
    """Same severity as the build, so the same side of the commit.

    A day whose stories no reader's browser can parse must not publish, and
    finding that out after the push costs the reader the day either way.
    """
    steps = _steps(_load_workflows()[filename], job_name)
    names = [step.get("name") for step in steps]
    validated = next(
        index
        for index, step in enumerate(steps)
        if tuple(shlex.split(str(step.get("run", "")))[:4]) == VALIDATE_DAYS_CALL
    )
    assert validated < names.index(commit_step), (
        "a day the contract refuses must never reach a reader"
    )


@pytest.mark.parametrize(("filename", "job_name", "commit_step"), PUBLISHING_SITE_JOBS)
def test_the_build_gates_the_publish_and_the_weight_gate_runs_after_it(
    filename: str, job_name: str, commit_step: str
) -> None:
    """Two severities, and only one of them may cost a reader the day.

    `npm run build` prerenders every route, so a route that cannot render fails
    here instead of in a reader's browser. That day is broken and must not
    publish, so the build runs before the commit. `idhazh validate-days` sits
    beside it at the same severity and for the same reason - it is what opens
    the stories a seeded document never serialises.

    `npm run bundle-gate` holds each capped page under the ceiling somebody
    priced for it. A page over it still reads correctly - what grew is the
    document, not the meaning - and stopping the publish for that throws away
    the day and the two to three hours that built it. So it runs after the
    commit, and stays fatal: the job goes red until somebody re-prices the
    ceiling.
    """
    steps = _steps(_load_workflows()[filename], job_name)
    names = [step.get("name") for step in steps]

    built = next(
        index for index, step in enumerate(steps) if "npm run build" in str(step.get("run", ""))
    )
    gate = next(
        index
        for index, step in enumerate(steps)
        if "npm run bundle-gate" in str(step.get("run", ""))
    )
    commit = names.index(commit_step)

    before_build = steps[:built]
    assert any(
        str(step.get("uses", "")).startswith("actions/setup-node@") for step in before_build
    ), "node must be set up before the site is built"
    assert any(
        "npm ci" in str(step.get("run", "")) for step in before_build
    ), "the site must be installed before it is built"
    assert built < commit, "a route that cannot render must never reach a reader"
    assert commit < gate, "a page over its ceiling loses the ceiling, not the day"
    assert "continue-on-error" not in steps[gate], "the gate publishes the day; it still fails"


@pytest.mark.parametrize(("filename", "job_name", "commit_step"), PUBLISHING_SITE_JOBS)
def test_the_weight_gate_reads_a_build_of_the_tree_that_was_pushed(
    filename: str, job_name: str, commit_step: str
) -> None:
    """One tree's pages may not be weighed against another tree's ceilings.

    `commit-and-push.sh` rebases when the push loses a race, and that brings
    main's tip into the checkout - its frontend source and its
    `config/idhazh.json` ceilings with it. `frontend/build` still holds the
    build made before the commit, so the gate would read limits the build it
    measures never saw. Run 33270983446 failed exactly that way, on a day that
    had already published and deployed.

    So a build sits after every commit step in the job, and the gate reads that
    one. `npm ci` is deliberately not repeated with it: the lockfile moves far
    more rarely than the source, and a reinstall would delete `node_modules` on
    every run to cover the rarer of the two.
    """
    steps = _steps(_load_workflows()[filename], job_name)
    names = [step.get("name") for step in steps]
    builds = [
        index for index, step in enumerate(steps) if "npm run build" in str(step.get("run", ""))
    ]
    commits = [
        index
        for index, step in enumerate(steps)
        if COMMIT_SCRIPT_CALL[1] in str(step.get("run", ""))
    ]
    gate = next(
        index
        for index, step in enumerate(steps)
        if "npm run bundle-gate" in str(step.get("run", ""))
    )

    assert names.index(commit_step) in commits, "the publishing step runs the shared commit script"
    rebuilt = [index for index in builds if index > max(commits)]
    assert rebuilt, "the gate must read a build made after the last commit, not before it"
    assert max(rebuilt) < gate, "the rebuild is what the gate reads, so it comes first"
    assert "continue-on-error" not in steps[rebuilt[0]], (
        "a rebuild that fails quietly leaves the gate reading the stale build again"
    )


#: Every job that builds the site, and so every job that can grow it past the cap.
SITE_WEIGHT_JOBS: Final = (
    ("ci.yml", "site"),
    ("digest.yml", "assemble"),
    ("backfill.yml", "backfill"),
)
SITE_WEIGHT_CALL: Final = ("python", "-m", "idhazh", "site-weight")


def _published_tree() -> str:
    """The directory the Pages deploy uploads, read off the deploy itself."""
    step = next(
        item
        for item in _steps(_load_workflows()["pages.yml"], "build")
        if str(item.get("uses", "")).startswith("actions/upload-pages-artifact@")
    )
    with_block = _mapping(step.get("with"), "pages.yml upload-pages-artifact with")
    path = with_block.get("path")
    assert isinstance(path, str), "the deploy must upload one named directory"
    return path.rstrip("/")


def _site_weight_step(workflow: dict[str, object], job_name: str) -> tuple[int, list[str]]:
    """Where the site-weight call sits in a job, and the argv it runs."""
    for index, step in enumerate(_steps(workflow, job_name)):
        argv = shlex.split(str(step.get("run", "")))
        if tuple(argv[:4]) == SITE_WEIGHT_CALL:
            directory = str(step.get("working-directory", "")).strip("/")
            return index, [directory, *argv]
    raise AssertionError(f"{job_name} builds the site and never measures it")


@pytest.mark.parametrize(("filename", "job_name"), SITE_WEIGHT_JOBS)
def test_the_site_gate_measures_the_tree_the_deploy_uploads(filename: str, job_name: str) -> None:
    """The 1 GB cap is a property of the published bundle, so that is what gets
    measured - the same directory `pages.yml` hands to the deploy.

    This is the defect the row fixed. The alarm used to measure
    `frontend/public/digest`, which is the pipeline's committed output and not
    the site: 7,027,075 bytes against 128,064,853 on 2026-08-27, eighteen times
    apart and growing at different rates. An alarm at 800 MB on that tree could
    not have fired before the site was already six times past the cap.

    Deriving the expected path from the deploy is what makes the fix structural.
    Point the gate back at `frontend/public/digest`, or anywhere else, and the
    two stop agreeing here.
    """
    workflow = _load_workflows()[filename]
    index, argv = _site_weight_step(workflow, job_name)
    directory, *call = argv

    assert "--site-tree" in call, "the tree is named at the call site, never defaulted"
    measured = f"{directory}/{call[call.index('--site-tree') + 1]}".strip("/")
    assert measured == _published_tree(), (
        f"{filename}/{job_name} measures {measured!r}; the deploy uploads "
        f"{_published_tree()!r}. One of the two is measuring the wrong tree."
    )
    assert not measured.startswith("frontend/public"), (
        "frontend/public is what the pipeline writes, not what a reader downloads"
    )

    built = next(
        position
        for position, step in enumerate(_steps(workflow, job_name))
        if "npm run build" in str(step.get("run", ""))
    )
    assert built < index, "the tree does not exist until the site is built"


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


def test_the_work_job_reads_its_bound_and_its_width_from_the_plan() -> None:
    """A bound written twice is a bound that can disagree with itself.

    `timeout-minutes` said 330 while `run.shard_timeout_minutes` said 150 and
    nothing read the config number, so a model sized against config was sized
    against a number production ignored. Both keys now resolve through
    `needs.plan.outputs`, and neither may go back to being a number typed here.
    """
    workflow = _load_workflows()["digest.yml"]
    work = _job(workflow, "work")
    strategy = _mapping(work.get("strategy"), "work strategy")

    assert work.get("timeout-minutes") == _expression(
        "fromJSON(needs.plan.outputs.shard_timeout_minutes)"
    )
    # The run's own worker count, never a fixed one. Held at four it would queue
    # half of an eight-shard dispatch and hand back the wall-clock the fan-out
    # buys; held at eight it says nothing true about a four-worker day.
    assert strategy.get("max-parallel") == _expression("fromJSON(needs.plan.outputs.shards)")

    for key, value in _values_keyed(work, WORK_BOUND_KEYS):
        assert not value.isdigit(), f"the work job writes {key} as the literal {value}"


def test_the_work_bound_is_whatever_the_config_says_it_is(tmp_path: Path) -> None:
    """Change the number in `config/idhazh.json` and the rendered bound changes.

    Running the shipped program against a real config directory is what makes
    this a test of the step rather than of a copy of its arithmetic.
    """
    workflow = _load_workflows()["digest.yml"]
    outputs = _mapping(_job(workflow, "plan").get("outputs"), "plan outputs")
    assert outputs.get("shard_timeout_minutes") == _expression(
        "steps.bounds.outputs.shard_timeout_minutes"
    )

    script = _script(_step(workflow, "plan", "id", "bounds"), "digest.yml/plan/bounds")
    assert "config/idhazh.json" in script, "the bound comes from config"
    assert '>> "$GITHUB_OUTPUT"' in script

    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["run"]
    assert _run_the_inline_program(script, REPO_ROOT) == {
        "shard_timeout_minutes": str(committed["shard_timeout_minutes"])
    }

    def config_saying(minutes: object) -> Path:
        (tmp_path / "config").mkdir(exist_ok=True)
        (tmp_path / "config" / "idhazh.json").write_text(
            json.dumps({"run": {"shard_timeout_minutes": minutes}}), encoding="utf-8"
        )
        return tmp_path

    moved = int(committed["shard_timeout_minutes"]) + 7
    assert _run_the_inline_program(script, config_saying(moved)) == {
        "shard_timeout_minutes": str(moved)
    }

    # `timeout-minutes` takes whatever it is handed, and a value it cannot read
    # as a number leaves the worker with no bound at all - which the run finds
    # out six hours later. So the one step that writes it is where a bound that
    # is not a whole count of minutes has to stop.
    for unusable in ("150", 0, -1, 12.5, True, None):
        with pytest.raises(AssertionError, match="shard_timeout_minutes"):
            _run_the_inline_program(script, config_saying(unusable))


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
    # And the fold says a third thing, in the same job as the day's own commit.
    assert _commit_call("fold")[1]["COMMIT_MESSAGE"] != assemble["COMMIT_MESSAGE"]


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
    # Which is why the charts get their own answer: this run's copy is dropped
    # rather than handed back, so the rebase never sees two adds of one path.
    # The entry point is the shipped one, not a copy of its logic.
    assert settings["DROP_RACED_ASSETS_COMMAND"].split()[1:] == [
        "backend/utilities/drop_raced_assets.py",
        "--date",
        SUBSTITUTED_DATE,
    ]
    assert DROP_ENTRY_POINT.is_file()
    # Neither setting may carry a space inside one of its words: the loop
    # word-splits both, and nothing here re-parses shell quoting.
    assert not any(
        '"' in value or "'" in value
        for value in (settings["REFRESH_PATHS"], settings["REGENERATE_COMMAND"])
    )
    # The plan job records what it saw and cannot rebuild it, so it resolves a
    # race by rebasing, and `.gitattributes` unions its ledgers. It commits no
    # rendered asset either, so it has nothing to drop.
    assert "REGENERATE_COMMAND" not in _commit_call("plan")[1]
    assert "DROP_RACED_ASSETS_COMMAND" not in _commit_call("plan")[1]


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
def test_the_harvest_runs_where_the_article_text_still_is() -> None:
    """A corpus built anywhere else is a corpus of nothing.

    `backend/var/run/<date>/items/` is gitignored and travels as a one-day
    artifact, so a workflow of its own would check out a fresh tree and find an
    empty directory - and it would report success while doing it. The step
    therefore sits in the job that already downloaded that artifact, between the
    publish that proves the day and the commit that pushes it.
    """
    workflow = _load_workflows()["digest.yml"]
    names = [step.get("name") for step in _steps(workflow, "assemble")]
    step = _step(workflow, "assemble", "name", HARVEST_STEP)

    assert HARVEST_COMMAND in _script(step, "assemble harvest step")
    assert step.get("continue-on-error") == TOLERATED, (
        "a corpus that will not build must never be what stops a reader getting the day"
    )
    assert (
        names.index("Assemble and publish")
        < names.index(HARVEST_STEP)
        < names.index(COMMIT_STEPS["assemble"])
    )


def test_the_telemetry_fold_runs_only_once_the_day_is_committed() -> None:
    """A fold that ran first could delete a month from a tree nothing pushed.

    The fold unlinks a committed file. Run before the day's own commit, a lost
    push would hand `state/item-health` back to origin's tip and rebuild against
    it, so the deletion would silently un-happen while the aggregate it wrote
    stayed - and the next run would fold a shard that had already been folded.
    Behind the commit, the worst it can cost is one run's worth of bytes.

    Neither step may fail the job. What assemble owes a reader is the published
    day, and a thirteen-month-old month file must never be what stops one.
    """
    workflow = _load_workflows()["digest.yml"]
    names = [step.get("name") for step in _steps(workflow, "assemble")]
    fold = _step(workflow, "assemble", "name", FOLD_STEP)

    assert FOLD_COMMAND in _script(fold, "assemble fold step")
    assert names.index(COMMIT_STEPS["assemble"]) < names.index(FOLD_STEP)
    assert names.index(FOLD_STEP) < names.index(COMMIT_STEPS["fold"])
    for step_name in (FOLD_STEP, COMMIT_STEPS["fold"]):
        step = _step(workflow, "assemble", "name", step_name)
        assert step.get("continue-on-error") == TOLERATED, (
            f"{step_name} must never be what costs a reader the day"
        )


def test_the_corpus_is_committed_but_never_rebuilt() -> None:
    """The window records what a run saw. It is not derived from origin's tip.

    So it is staged by the commit step and deliberately absent from the refresh
    set: on a lost race the answer is to replay this run's rows onto the new
    base, which is what the rebase already does, and never to run a producer
    again over articles the new checkout cannot see.
    """
    staged, settings = _commit_call("assemble")

    assert "corpus" in staged
    assert "corpus" not in settings["REFRESH_PATHS"].split()
    assert "corpus" not in settings["REGENERATE_COMMAND"].split()


def test_every_path_the_day_stages_exists_in_a_fresh_checkout() -> None:
    """`git add "$@"` runs under `set -euo pipefail`.

    A staged path that only appears once its producer succeeded therefore aborts
    the whole commit step, and takes every sibling ledger staged in the same call
    with it. The seed is what makes the corpus path safe to name.
    """
    for relative in CORPUS_SEED:
        assert (REPO_ROOT / relative).is_file(), f"{relative} must be committed, even when empty"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", *CORPUS_SEED],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode == 0, tracked.stderr.strip()


def test_the_corpus_is_not_union_merged() -> None:
    """A rolling window is not an append-only ledger.

    Asked of git rather than of a pattern matcher written here. Unioning two
    rolls produces a file that carries evicted rows again and sits above
    `finetune.corpus_rows`, which is the one shape this file must never take.
    """
    answered = subprocess.run(
        ["git", "check-attr", "merge", "--", *CORPUS_SEED],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert answered == [f"{path}: merge: unspecified" for path in CORPUS_SEED]


def test_only_the_scheduled_prune_may_force_push() -> None:
    """The single exception in `CLAUDE.md` section 8, held closed-world.

    Discovery is over every workflow body and every shipped script, so a second
    force-push fails here whoever adds it and wherever they put it.
    """
    forcing: set[tuple[str, object]] = set()
    for filename, workflow in _load_workflows().items():
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            for step in _steps(workflow, job_name):
                script = step.get("run")
                if isinstance(script, str) and re.search(r"push\s+(--force|-f)\b", script):
                    forcing.add((filename, step.get("name")))
    for path in sorted(SCRIPTS_DIR.glob("*.sh")):
        assert not re.search(r"push\s+(--force|-f)\b", read_text(path)), (
            f"{path.name} force-pushes, and only .github/workflows/prune.yml may"
        )

    assert forcing == {("prune.yml", "Push the rewritten history")}


def test_the_prune_reads_both_its_numbers_from_config() -> None:
    """The cadence is a config value, so it cannot be a cron line.

    `on.schedule` is parsed before any step runs, so nothing in `config/` can
    reach it, and 5-field cron has no every-N-days field to write one with. The
    daily cron is the wake-up; this step is the schedule. Run against the real
    committed config, so a renamed knob fails here.
    """
    workflow = _load_workflows()["prune.yml"]
    step = _step(workflow, "prune", "id", "due")
    outputs = _run_the_inline_program(_script(step, "prune due step"), REPO_ROOT)
    finetune = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["finetune"]

    assert outputs["due"] in {"true", "false"}
    assert outputs["keep_days"] == str(finetune["prune_keep_days"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", outputs["today"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", outputs["boundary"])
    assert (
        datetime.date.fromisoformat(outputs["today"])
        - datetime.date.fromisoformat(outputs["boundary"])
    ).days == finetune["prune_keep_days"]

    schedule = _triggers(workflow)["schedule"]
    assert isinstance(schedule, list) and len(schedule) == 1
    cron = _mapping(cast(list[object], schedule)[0], "prune cron")["cron"]
    assert isinstance(cron, str)
    assert "*/" not in cron, (
        "a step-value cron is not an every-N-days cadence: */30 fires on the 1st and 31st"
    )


def test_the_prune_only_clones_the_whole_history_when_it_is_due() -> None:
    """29 wakes out of 30 read one committed file and stop.

    The deep fetch, the Python setup, the install and the push are each gated on
    the same output, so a repository nobody is pruning costs a shallow checkout a
    day rather than a full clone a day.
    """
    workflow = _load_workflows()["prune.yml"]
    steps = _steps(workflow, "prune")
    depths = [
        _mapping(step.get("with"), "checkout with").get("fetch-depth")
        for step in steps
        if isinstance(step.get("uses"), str)
        and cast(str, step.get("uses")).startswith("actions/checkout@")
    ]

    assert depths == ["1", "0"], "a shallow read first, and the full history only when due"
    gated = [
        _normalize_condition(step["if"], "prune step condition")
        for step in steps
        if "if" in step
    ]
    assert gated.count("steps.due.outputs.due == 'true'") == len(gated) - 1
    for step in steps:
        if step.get("name") == "Push the rewritten history":
            assert _normalize_condition(step["if"], "push condition") == (
                "steps.due.outputs.due == 'true'"
            )
            break
    else:
        pytest.fail("the prune must have a push step")


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


def test_a_worker_commits_its_rows_before_the_run_can_throw_them_away() -> None:
    """The Oracle, in YAML: a cancelled job runs `always()` steps and skips the rest.

    The items artifact carries a shard's verdicts for one day and has no `if:`,
    so a cancelled job never uploads it. A run stopped between the workers and
    the publish had measured every item and kept none of the measurements.
    """
    workflow = _load_workflows()["digest.yml"]
    names = [step.get("name") for step in _steps(workflow, "work")]

    for name in WORK_LEDGER_STEPS:
        step = _step(workflow, "work", "name", name)
        assert _normalize_condition(step.get("if"), f"work step {name}") == "always()"

    record = _substitute(
        _script(_step(workflow, "work", "name", RECORD_STEP), f"work step {RECORD_STEP}")
    )
    assert RECORD_COMMAND in record
    assert f'--date "{SUBSTITUTED_DATE}"' in record
    # This shard's own items. A record step that asked for the whole day would
    # file rows for items seven other workers are still holding. The step's line
    # continuations are folded first, the way bash reads them.
    assert shlex.split(record.replace("\\\n", " "))[-4:] == [
        "--shard",
        SUBSTITUTED_SHARD,
        "--shards",
        SUBSTITUTED_SHARDS,
    ]
    # Ahead of every `always()` step that only writes a log, because a cancelled
    # job spends one grace period on all of them in order and these are the ones
    # whose loss the group exists to prevent. Consecutive, and in this order: the
    # counters step writes a row the commit step stages.
    assert [names.index(name) for name in WORK_LEDGER_STEPS] == [
        names.index(RECORD_STEP) + offset for offset in range(len(WORK_LEDGER_STEPS))
    ]
    assert names.index(COMMIT_STEPS["work"]) < names.index("Prompt cache log summary")


def test_a_ledger_that_will_not_push_cannot_cost_the_day_a_worker() -> None:
    """Which loss is cheaper, said in the workflow rather than left to an exit code.

    The shard's product is the items artifact assemble publishes from, and
    assemble writes the same census again - so a ledger push that spends its
    three attempts costs this run an early copy of rows it gets anyway. A failed
    shard costs the day a whole worker. The script exits 1 when it gives up
    (proved in `test_a_rebase_it_cannot_finish_still_ends_the_script_cleanly`),
    which is why saying so is load-bearing rather than decorative.
    """
    workflow = _load_workflows()["digest.yml"]

    for name in WORK_LEDGER_STEPS:
        step = _step(workflow, "work", "name", name)
        assert step.get("continue-on-error") == TOLERATED, (
            f"work step {name} must not fail the shard"
        )
    # Closed-world, because a publish step that swallowed its own failure would
    # publish nothing and report success. The one that was already here is
    # assemble's routes download: `route` is allowed to produce no artifact at
    # all, and every item then publishes with no picture. The two fold steps join
    # it for the harvest's reason: they run after the day is committed and touch
    # only months past `observability.keep_months`, so the most a failure costs is
    # one run's worth of bytes and the next run folds the same month again.
    tolerant = {
        (job_name, step.get("name") or step.get("uses"))
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if step.get("continue-on-error") == TOLERATED
    }
    assert tolerant == {
        *(("work", name) for name in WORK_LEDGER_STEPS),
        ("assemble", "actions/download-artifact@v8"),
        ("assemble", HARVEST_STEP),
        ("assemble", FOLD_STEP),
        ("assemble", COMMIT_STEPS["fold"]),
    }


def test_every_path_the_work_shard_stages_is_union_merged() -> None:
    """Eight shards append to one branch, so both ledgers need the union driver.

    Asked of git rather than of a pattern matcher written here: `.gitattributes`
    is the file that decides, and a second implementation of its globbing could
    agree with this test and disagree with the merge.
    """
    # The file each staged path resolves to. A directory is monthly shards.
    written = {
        "state/item-health": f"state/item-health/{SUBSTITUTED_DATE[:7]}.csv",
        "state/scores": f"state/scores/{SUBSTITUTED_DATE[:7]}.csv",
        "state/runtime-counters.csv": "state/runtime-counters.csv",
    }
    assert set(written) == set(COMMIT_STAGED_PATHS["work"])

    answered = subprocess.run(
        ["git", "check-attr", "merge", "--", *written.values()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert answered == [f"{path}: merge: union" for path in written.values()]


def test_the_retirement_ledger_needs_no_gitattributes_edit() -> None:
    """`state/**/*.csv` already answers union, so the new ledger inherits the driver.

    Asked of git rather than of a pattern matcher written here, for the same
    reason the test above is: `.gitattributes` is the file that decides. Two
    stale checkouts can each append the same retirement, and the union keeps both
    lines - which is why the file is also registered in `ledger.keyed_paths`, so
    the post-merge settlement collapses them to one.
    """
    relative = ledger.feed_retirements_relpath()

    answered = subprocess.run(
        ["git", "check-attr", "merge", "--", relative],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert answered == [f"{relative}: merge: union"]


@requires_bash
@requires_space_free_paths
def test_every_shard_of_a_full_fan_out_lands_its_rows(tmp_path: Path) -> None:
    """Eight workers, one branch, one row each.

    They run in turn from clones taken before any of them pushed, so every one
    after the first finds a base that has already moved - which is the state a
    real fan-out puts them in. What this proves is that the rebase resolves it
    and no row is lost, and that the post-merge pass leaves eight different rows
    alone: they share a file, not a key. It does not prove the three-attempt
    budget: eight truly concurrent pushes cannot be made deterministic in a test.
    """
    staged_paths, settings = _commit_call("work")
    env = _isolated_env(tmp_path)
    origin, _ = _scripted_origin(tmp_path, env, staged_paths)
    relative = _seed_ledger(staged_paths[0])
    settings = _settled_in_the_clone(settings, relative, "header")
    shards = range(8)
    runners = []
    for shard in shards:
        runner = tmp_path / f"shard-{shard}"
        _git(tmp_path, env, "clone", str(origin), str(runner))
        _write(runner / relative, f"header\nrow-0\nshard-{shard}\n")
        runners.append(runner)

    results = [_run_commit_script(runner, env, staged_paths, settings) for runner in runners]

    assert [result.returncode for result in results] == [0] * len(runners)
    landed = _git(origin, env, "show", f"main:{relative}").splitlines()
    assert landed[0] == "header"
    assert sorted(landed[1:]) == ["row-0", *(f"shard-{shard}" for shard in shards)]
    assert not any(_mid_rebase(runner) for runner in runners)


def _keyed_origin(tmp_path: Path, env: dict[str, str], relative: str) -> tuple[Path, Path]:
    """An origin holding one keyed ledger, and a clone taken before anything raced it.

    Built here rather than through `_scripted_origin`, which seeds a one-word
    ledger: two rows that share a key and disagree about everything else need
    two columns, and that shape is what this file is about.
    """
    origin = tmp_path / "origin.git"
    tmp_path.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, env, "init", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, env, "clone", str(origin), str(seed))
    _write(seed / ".gitattributes", read_text(REPO_ROOT / ".gitattributes"))
    _write(seed / relative, "key,cells\n")
    _git(seed, env, "add", ".gitattributes", relative)
    _git(seed, env, "commit", "-m", "seed")
    _git(seed, env, "push", "-u", "origin", "main")
    runner = tmp_path / "runner"
    _git(tmp_path, env, "clone", str(origin), str(runner))
    return origin, runner


@requires_bash
@requires_space_free_paths
def test_a_second_attempt_at_one_shard_leaves_the_row_the_first_one_pushed(
    tmp_path: Path,
) -> None:
    """The defect this step exists for, reproduced and then closed, on real git.

    A shard's append filters against the checkout, and `actions/checkout` pins a
    job to the commit its run was triggered at. So a second attempt at the same
    work cannot see the row the first attempt pushed afterwards: it appends its
    own, `merge=union` keeps both lines, and the ledger ends up with a key twice.
    That is how run `2026-08-29-3` came to hold six counter rows for four shards.

    Both arms run the shipped script over the same repository. The one without
    the setting is the defect; the one with it is the fix. The row that survives
    is the one origin already published, so the commit adds nothing and deletes
    nothing the tip holds - which is the property that makes settling after a
    merge safe rather than a rewrite of somebody else's history.
    """
    relative = "state/runtime-counters.csv"
    _, settings = _commit_call("work")

    def attempt(root: Path, drop: bool) -> list[str]:
        root.mkdir(parents=True, exist_ok=True)
        env = _isolated_env(root)
        origin, runner = _keyed_origin(root, env, relative)
        _race(root, env, relative, "key,cells\nk1,attempt-one\n")
        _write(runner / relative, "key,cells\nk1,attempt-two\n")
        settled = (
            _settled_in_the_clone(settings, relative, "key")
            if drop
            else {name: value for name, value in settings.items() if "REPEATED" not in name}
        )
        result = _run_commit_script(runner, env, [relative], settled)
        assert result.returncode == 0, result.stderr
        assert "rebasing" in result.stdout, "the push has to lose, or nothing merged"
        return _git(origin, env, "show", f"main:{relative}").splitlines()

    assert attempt(tmp_path / "unsettled", drop=False) == [
        "key,cells",
        "k1,attempt-one",
        "k1,attempt-two",
    ], "without the pass the union keeps both attempts, which is the defect"

    assert attempt(tmp_path / "settled", drop=True) == ["key,cells", "k1,attempt-one"]


def test_assemble_hands_back_every_ledger_a_worker_committed() -> None:
    """Why assemble cannot append a row a shard already pushed.

    Assemble checks out main as it was when the run was queued, so its copy of
    these two ledgers predates the shards' pushes and its own push always loses
    the race. The loop answers a lost race by restoring the rebuilt paths from
    the tip it wants and running the producer again - so the assemble that
    finally commits reads the file the workers wrote and files against it. A
    staged path missing from that refresh set would be rebased instead, and
    `merge=union` keeps both appends.
    """
    refreshed = _commit_call("assemble")[1]["REFRESH_PATHS"].split()

    assert set(COMMIT_STAGED_PATHS["work"]) <= set(refreshed)


def test_every_committing_job_configures_the_same_identity() -> None:
    """The pipeline commits as itself, and it says so in one voice.

    A hosted runner carries no git identity, so a job that commits has to set
    one or `git commit` refuses. Two files set it and only one of them is
    executed by a test, so the other could drift to a different name and nothing
    would notice until a reader wondered who two different authors were.
    """
    found = {
        path.name: (
            re.search(r'git config user\.name "([^"]+)"', read_text(path)),
            re.search(r'git config user\.email "([^"]+)"', read_text(path)),
        )
        for path in GIT_IDENTITY_SOURCES
    }

    for name, (author, address) in found.items():
        assert author is not None, f"{name} commits, so it must set user.name"
        assert address is not None, f"{name} commits, so it must set user.email"
        assert f"{author.group(1)} <{address.group(1)}>" == COMMIT_IDENTITY


@requires_bash
@requires_space_free_paths
@pytest.mark.parametrize("job_name", sorted(COMMIT_STEPS))
def test_the_commit_step_pushes_what_it_staged(tmp_path: Path, job_name: str) -> None:
    staged_paths, settings = _commit_call(job_name)
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
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
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
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
        "DROP_RACED_ASSETS_COMMAND": _drop_command(date),
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
    scores = _rows(_git(origin, env, "show", f"main:state/scores/{month}.csv"))
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
def test_two_runs_that_rendered_one_item_still_publish_the_day(tmp_path: Path) -> None:
    """The Oracle above, with the one thing it never had: both sides create the path.

    Run `32869125768` finished eight workers and a router and then lost the
    whole day here. A chart was filed by its vertical and its ordinal within the
    day, and the ordinal was seeded by reading the day's directory - so two runs
    of one day, neither able to see what the other pushed, wrote `energy-01.svg`
    for DIFFERENT items with different bytes. Git cannot rebase two adds of one
    path, `assemble` exited 1, and the `items-*` artifacts expired with every
    summary in them.

    A chart is now filed under its item's own id, so that case cannot happen at
    all. What is left is this one: two runs rendering the SAME item, which is
    one story's picture drawn twice. The tip's copy is published and a reader
    may already hold that address, and the rebuild keeps the tip's item anyway,
    so this run's copy is dropped and the day publishes.
    """
    date = SUBSTITUTED_DATE
    raced, fresh = RACED_ITEM_ID, "energy-0000000002"
    fresh_asset = f"digest/{date.replace('-', '/')}/{fresh}.svg"
    staged_paths, settings = _commit_call("assemble")
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command(date),
        "DROP_RACED_ASSETS_COMMAND": _drop_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(
        tmp_path,
        env,
        date,
        [raced],
        "Merge pull request #125 from someone/branch",
        charts={raced: RACED_ASSET},
    )
    # This run planned the same item, because the push above had not happened
    # when it planned - and drew it again, to different bytes.
    _chart(runner, date, raced, RACED_ASSET, body="ours")
    _chart(runner, date, fresh, fresh_asset)
    _rebuild(runner, env, date, [raced, fresh])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert f"{RACED_ASSET} is already published, so this run's copy of it was dropped" in (
        result.stdout
    )
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert not _mid_rebase(runner)

    day = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/digest.json"))
    assert day["items"] == ["item-a", "item-b", raced, fresh]
    # The item this run introduced kept its picture, and no two items share one.
    assert day["visuals"] == {raced: RACED_ASSET, fresh: fresh_asset}
    assert len(set(day["visuals"].values())) == len(day["visuals"])
    # The gate a broken image would fail: every path the day publishes is a file
    # the day publishes. A picture that 404s is worse than a job that stops.
    for relpath in day["visuals"].values():
        assert _tracked(origin, env, f"frontend/public/{relpath}")
    # The published address still holds the bytes that were published under it,
    # rather than this run's second attempt at the same picture.
    assert _git(origin, env, "show", f"main:frontend/public/{RACED_ASSET}") == (
        f"<svg>{raced}</svg>\n"
    )
    assert _git(origin, env, "show", f"main:frontend/public/{fresh_asset}") == (
        f"<svg>{fresh}</svg>\n"
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
        "DROP_RACED_ASSETS_COMMAND": _drop_command(date),
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


def test_every_weights_fetch_fails_loudly() -> None:
    """One spelling, everywhere, so a fourth workflow cannot reintroduce the bug.

    `digest.yml` fetched both its models with a bare `curl -sSL`. Without `-f`
    curl writes an HTTP error body into the .gguf and exits 0, and
    `backend/models` is a cache path - so a rate-limited minute produced a
    junk file that was then saved under the pinned key and served to every
    later run until the entry was evicted.
    """
    fetches = _weights_fetch_steps(_load_workflows())
    assert fetches, "some workflow must still download weights"

    for (filename, job_name), (step_name, script) in sorted(fetches.items()):
        where = f"{filename}/{job_name}/{step_name}"
        assert WEIGHTS_FETCH_FORM in script, where
        assert "curl -sSL" not in script, f"{where} must fail on an HTTP error"
        assert "resolve/main" not in script, f"{where} must name an immutable revision"


def test_every_fetched_weight_is_checked_before_anything_reads_it() -> None:
    """The Oracle. Wrong bytes fail on one step, not hours later as wrong output.

    Closed-world: the fetches are discovered by reading every workflow, and the
    discovered set must equal the table. A tenth workflow that downloads a
    `.gguf` fails here until it carries a check of its own.

    No check carries an `if:`, on purpose. A restored cache entry is the one
    case where nobody watched the bytes arrive, so it is the case that most
    needs checking.
    """
    workflows = _load_workflows()
    assert set(_weights_fetch_steps(workflows)) == set(WEIGHTS_CHECKS)

    for (filename, job_name), expected in sorted(WEIGHTS_CHECKS.items()):
        fetch_name, check_name, reader_name, digest_source = expected
        where = f"{filename}/{job_name}"
        names = [step.get("name") for step in _steps(workflows[filename], job_name)]

        for expected_name in (fetch_name, check_name, reader_name):
            assert expected_name in names, f"{where} has no step named {expected_name!r}"
        assert names.index(fetch_name) < names.index(check_name), where
        assert names.index(check_name) < names.index(reader_name), where

        check = _step(workflows[filename], job_name, "name", check_name)
        assert "if" not in check, f"{where}: a restored cache is what most needs checking"
        script = _script(check, f"{where}/{check_name}")
        assert digest_source in script, f"{where} must read one recorded digest"
        assert "sha256sum --check" in script, where


def test_the_health_check_names_the_weights_that_answered() -> None:
    """Healthy says a server replied. It does not say which weights replied."""
    health = _step(_load_workflows()["digest.yml"], "work", "name", "Check model health")
    script = health.get("run")
    assert isinstance(script, str)

    assert '["models"]["summarize"]["id"]' in script, "the alias comes from config"
    assert "/v1/models" in script, "assert the served alias"
    assert "/props" in script, "assert the loaded path"
    assert _plan_output("summarize_file") in script


def test_the_daily_run_writes_no_model_ref_of_its_own() -> None:
    """The Oracle. One place writes a production model ref, and it is config.

    `digest.yml` used to carry the repo and the filename as workflow `env` while
    the alias came from config. Two answers to one question drift the moment
    either is edited: llama-server then serves the old bytes under the new alias
    and every eval row names a model that never ran (Rule #6, Rule #10).
    """
    text = read_text(WORKFLOWS_DIR / "digest.yml")
    assert ".gguf" not in text, "a weights filename is written in config, not here"
    assert not re.search(r"huggingface\.co/(?!\$\{\{)", text), "no repo literal"

    workflow = _load_workflows()["digest.yml"]
    for scope, env in _every_env(workflow):
        named = MODEL_ENV_NAMES & set(env)
        assert not named, f"{scope} names a model through env: {sorted(named)}"


def test_no_workflow_that_loads_weights_writes_a_model_ref_or_a_moving_one() -> None:
    """The Oracle, widened to every workflow that downloads weights.

    `digest.yml` had already been cleaned; `measure.yml` still carried the two
    production refs as job `env` and a third copy as a dispatch default, and
    `validate.yml` carried a candidate's repo and filename as defaults. Each was
    a second answer to a question config already answers, and each one drifts
    silently the day config moves (Rule #6).

    Every download also names an immutable commit. A branch hands back whatever
    was uploaded last, so a measurement taken from one describes bytes nobody
    can fetch again (Rule #10).

    A dispatch INPUT is not a hardcode and is deliberately left alone: it is how
    an operator points the measurement harness at a model config does not name.
    What this test forbids is a literal written into the file.
    """
    hub = re.compile(r"huggingface\.co/(?!\$\{)")
    branch = re.compile(r"(?:resolve|tree|blob|raw)/(?:main|master)\b")
    # A weights repository is `<publisher>/<name>GGUF` by convention, so the
    # shape catches the next one; the two publishers that were written into
    # these files are named outright, so a repository that breaks the
    # convention is still caught.
    repo_shape = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]*GGUF\b")
    publishers = re.compile(r"\b(?:Qwen|unsloth|bartowski|TheBloke)\b")

    for filename in sorted(LLAMA_RUNTIME_WORKFLOWS):
        text = read_text(WORKFLOWS_DIR / filename)
        assert ".gguf" not in text, f"{filename}: a weights filename belongs in config"
        assert not hub.search(text), f"{filename}: a repository literal belongs in config"
        assert not repo_shape.search(text), f"{filename}: a repository literal belongs in config"
        assert not publishers.search(text), f"{filename}: a model publisher belongs in config"
        assert not branch.search(text), f"{filename}: a download must name an immutable commit"

        for scope, env in _every_env(_load_workflows()[filename]):
            for name, value in env.items():
                if name not in MODEL_ENV_NAMES:
                    continue
                assert isinstance(value, str) and value.startswith("${{"), (
                    f"{filename}: {scope} writes {name} as a literal"
                )


def test_the_plan_job_publishes_the_model_refs_it_read_from_config(tmp_path: Path) -> None:
    """`needs` resolves before a job's first step. `steps` does not.

    That difference is the whole reason the refs travel as job outputs: it is
    what lets the weights cache key in `work` and `route` name the file it holds
    rather than be told by a copy that can disagree with config.
    """
    workflow = _load_workflows()["digest.yml"]
    outputs = _mapping(_job(workflow, "plan").get("outputs"), "plan outputs")
    for name in MODEL_REF_OUTPUTS:
        assert outputs.get(name) == _expression(f"steps.models.outputs.{name}")

    step = _step(workflow, "plan", "id", "models")
    script = _script(step, "digest.yml/plan/models")
    assert "config/idhazh.json" in script, "the refs come from config"
    assert '>> "$GITHUB_OUTPUT"' in script

    models = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models"]
    assert _run_the_inline_program(script, REPO_ROOT) == {
        f"{role}_{field}": models[role][field]
        for role in ("summarize", "route")
        for field in MODEL_REF_FIELDS
    }

    # Every ref is substituted straight into a shell command downstream, so the
    # one step that writes them is where a value that is not one bare word has
    # to stop. Nothing else between config and those commands can catch it.
    (tmp_path / "config").mkdir()
    models["summarize"]["file"] = "Qwen3-8B-Q4_K_M.gguf; rm -rf /"
    (tmp_path / "config" / "idhazh.json").write_text(
        json.dumps({"models": models}), encoding="utf-8"
    )
    with pytest.raises(AssertionError, match=re.escape("models.summarize.file")):
        _run_the_inline_program(script, tmp_path)
def test_the_weights_cache_key_names_the_model_and_the_build_it_holds() -> None:
    """Every part of what the entry holds, and all of them from one source.

    The fetch step runs only on a cache miss, so a key that omits any part turns
    that step into dead code and serves the wrong bytes silently. The revision
    is one of those parts: two uploads share a filename, so without it a
    repinned config gets a hit whose bytes then fail the checksum on every run
    until the entry expires. The composed string is asserted too: an expression
    that does not resolve leaves a literal `${{` in the key, and Actions would
    key the cache on that text.
    """
    workflow = _load_workflows()["digest.yml"]
    keys = dict(_runtime_cache_keys(workflow))
    assert set(keys) == set(WEIGHTS_CACHE_ROLES)

    models = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models"]
    for job_name, role in WEIGHTS_CACHE_ROLES.items():
        weights = _plan_output(f"{role}_file")
        revision = _plan_output(f"{role}_revision")
        build = _expression("env.LLAMA_CPP_BUILD")
        assert keys[job_name] == (
            f"llm-{weights}-{revision}-{build}-{WEIGHTS_CACHE_SUFFIX}"
        ), job_name

        composed = (
            keys[job_name]
            .replace(weights, models[role]["file"])
            .replace(revision, models[role]["revision"])
            .replace(build, PINNED_LLAMA_BUILD)
        )
        assert "${{" not in composed, f"{job_name}: every half of the key must resolve"
        assert composed == (
            f"llm-{models[role]['file']}-{models[role]['revision']}"
            f"-{PINNED_LLAMA_BUILD}-{WEIGHTS_CACHE_SUFFIX}"
        ), job_name

    assert keys["work"] != keys["route"], "one entry cannot hold two sets of weights"
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
            assert RELEASE_LOOKUP_FORM in script, f"{where} must fail on an HTTP error"
            assert WEIGHTS_FETCH_FORM in script, f"{where} must fail on an HTTP error"


def test_no_workflow_takes_whichever_llama_cpp_release_is_newest() -> None:
    """The list endpoint hands back a different binary on every cache eviction."""
    for path in sorted((*WORKFLOWS_DIR.glob("*.yml"), *WORKFLOWS_DIR.glob("*.yaml"))):
        assert "releases?per_page" not in read_text(path), path.name
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


#: The shared start sequence `digest.yml` delegates to. A step that calls it is
#: still a server starter, and the shell it really runs is its own body plus
#: this file's.
START_SERVER_SCRIPT: Final = SCRIPTS_DIR / "start-llama-server.sh"


def _starter_shell(step: Mapping[str, object]) -> str:
    """Everything a starter step executes, following one level of delegation.

    `work` and `route` ran 31 lines of near-identical inline shell, 80.6 percent
    the same, differing in the config attribute and two filenames. They call one
    script now. Reading the step alone would report that neither reaches
    `server_argv` any more, which is the opposite of what happened.
    """
    body = step.get("run")
    if not isinstance(body, str):
        return ""
    if START_SERVER_SCRIPT.name not in body:
        return body
    return body + "\n" + read_text(START_SERVER_SCRIPT)


def _server_starters(
    workflows: Mapping[str, dict[str, object]],
) -> dict[tuple[str, str], str]:
    """Every step that reaches `server_argv`, found by reading, not by listing.

    A step that stands a server up any other way is a second answer to what the
    run executes, so the set this returns is compared by equality.
    """
    found: dict[tuple[str, str], str] = {}
    for filename, workflow in workflows.items():
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            for step in _steps(workflow, job_name):
                if "server_argv" not in _starter_shell(step):
                    continue
                name = step.get("name")
                assert isinstance(name, str), f"{filename}/{job_name}: name the step"
                where = (filename, job_name)
                assert where not in found, f"{filename}/{job_name} starts two servers"
                found[where] = name
    return found


def test_every_job_that_starts_a_server_reaches_the_one_argv_builder() -> None:
    """The Oracle. One function spells a llama-server flag and everything reaches it.

    `backend/utilities/llama_server_argv.py` was a second copy of that list. It
    existed for one reason: `digest.yml` started its server before
    `pip install -e .` ran, so the package was not importable yet. The install
    moved one step earlier and the copy went. While it existed the two halves
    drifted, and the arm that drifted was the one nobody diffed - `validate.yml`
    qualified a candidate on a server the daily run does not run.

    The install ordering is the whole reason, so it is asserted here rather than
    left as a comment: a job that installs after it starts is a job that needs a
    second copy again.
    """
    workflows = _load_workflows()
    starters = _server_starters(workflows)
    assert starters == {where: name for where, (name, _) in SERVER_STARTERS.items()}

    for (filename, job_name), (step_name, config_root) in sorted(SERVER_STARTERS.items()):
        where = f"{filename}/{job_name}/{step_name}"
        names = [step.get("name") for step in _steps(workflows[filename], job_name)]
        assert "Install" in names, f"{where} must install the package it imports"
        assert names.index("Install") < names.index(step_name), (
            f"{where} imports idhazh, so the install runs first"
        )

        script = _starter_shell(_step(workflows[filename], job_name, "name", step_name))
        assert "from idhazh.llm.server import server_argv" in script, where
        if config_root is None:
            continue
        assert f'config.load(Path("{config_root}"))' in script, f"{where} reads {config_root}"
        # NUL-separated, so a flag value carrying a space stays one argument.
        assert "mapfile -d '' LLAMA_ARGV" in script, where
        assert 'port=int(os.environ["LLAMA_PORT"])' in script, where

    # The other side of the same Oracle: no command a runner executes renders
    # the list itself. Only `run:` scripts are read, because a dispatch-form
    # description that names `-tb` tells an operator what an input tunes and
    # starts nothing. The shipped shell under .github/scripts/ is read too - a
    # flag moved out of a workflow into a script is still a second spelling.
    flags = llama_server_flags()
    executed: list[tuple[str, str]] = [
        (path.name, read_text(path)) for path in sorted(SCRIPTS_DIR.glob("*.sh"))
    ]
    for filename, workflow in sorted(workflows.items()):
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            for step in _steps(workflow, job_name):
                body = step.get("run")
                if not isinstance(body, str):
                    continue
                executed.append((f"{filename}/{job_name}/{step.get('name')}", body))

    for where, body in executed:
        commands = _uncommented(body)
        for flag in flags:
            # A whole token: `-fa` sits inside `fail-fast`, so a substring
            # search reports a flag nobody wrote.
            spelled = re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", commands)
            assert not spelled, f"{where} spells {flag} instead of importing it"


@requires_bash
@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "usage:"),
        (["summarize"], "usage:"),
        (["gibberish", "llama-server"], "unknown role"),
    ],
)
def test_the_start_script_refuses_a_call_it_cannot_serve(
    argv: list[str], message: str, tmp_path: Path
) -> None:
    """Run it, do not read it.

    Two jobs share this script and each passes a role and a filename. A typo in
    either used to be impossible, because the shell was written out per job; now
    it is one string in a workflow, so the script says no rather than starting a
    server for the wrong model or writing a log nobody later reads.
    """
    shell = _bash()
    assert shell is not None
    completed = subprocess.run(
        [shell, START_SERVER_SCRIPT.as_posix(), *argv],
        cwd=tmp_path,
        env={**_isolated_env(tmp_path), "LLAMA_WEIGHTS": "w.gguf", "LLAMA_PORT": "8080"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2, completed.stdout
    assert message in completed.stderr
# --- The qualification arm (Row #10) ----------------------------------------


def _uncommented(text: str) -> str:
    """The lines a runner acts on, without the ones explaining why.

    A comment that says "there is no incumbent arm" is documentation worth
    keeping; an assertion that greps the whole file cannot tell it apart from
    an incumbent arm.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
def test_the_candidate_bytes_are_verified_before_the_server_starts() -> None:
    """Wrong weights must cost one step, not a whole shard of measurements filed
    under a model that never ran (Rule #10)."""
    workflow = _load_workflows()["validate.yml"]
    names = [step.get("name") for step in _steps(workflow, "qualify")]
    verify = names.index("Verify the candidate bytes")
    assert verify < names.index("Start the candidate")
    assert verify < names.index("Freeze the corpus and replay it")

    step = _step(workflow, "qualify", "name", "Verify the candidate bytes")
    script = _script(step, "validate.yml/qualify/Verify the candidate bytes")
    assert "sha256sum --check" in script
    assert "inputs.candidate_bytes" in script, "the declared byte count is checked too"
    assert step.get("if") is None, "a restored cache entry is checked as well"


def test_the_qualification_uploads_no_article_body() -> None:
    """This repository is public. A frozen corpus is hashes and measurements;
    the article text stays on the runner that captured it and dies with it."""
    workflow = _load_workflows()["validate.yml"]
    upload = _step(workflow, "qualify", "uses", "actions/upload-artifact@v7")
    path = _mapping(upload.get("with"), "qualify upload 'with'").get("path")
    assert path == "backend/var/qualification/shard-*.json"
    assert "items" not in str(path)
