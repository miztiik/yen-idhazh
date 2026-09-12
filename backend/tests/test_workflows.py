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
from conftest import CONFIG_DIR, FIXTURES_DIR, REPO_ROOT, llama_server_flags, read_text
from pydantic import ValidationError

from idhazh import ledger, publish_console, publish_telemetry
from idhazh.contracts import runtime_counters
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.evals import writer as score_writer
from idhazh.llm.server import DEFAULT_ENDPOINT, DEFAULT_PORT

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

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
        frozenset({"workflow_run", "workflow_dispatch"}),
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
# The generated summary of every plan-doc's Status Reckoner, and the one file in
# the repository with a single writer. It used to have one writer per branch: a
# gate regenerated it in every pull request, so two branches that each stamped a
# Reckoner row conflicted on every line that moved. Four of the six rows of plan
# 27 hit that on 2026-09-12, one of them twice, and each was settled by
# regenerating - a band-aid, not a fix (Guardrail #5).
STATUS_PAGE: Final = "TODO/STATUS.md"
STATUS_PAGE_JOB: Final = "status-page"
STATUS_PAGE_GUARD: Final = "A pull request never edits the plan queue"
STATUS_PAGE_WRITE: Final = "python backend/utilities/plan_status.py --write"
# The ceiling, not the dispatch rule. Guardrail #2 allows 20 concurrent jobs; a regex
# held the fan-out at four. The empty-input default below stays at four, because
# that is what every scheduled run gets and no eight-shard run is measured yet.
CONTENT_REFRESH_SHARDS: Final = frozenset({"1", "2", "3", "4", "5", "6", "7", "8"})
CONTENT_REFRESH_SHARD_DEFAULT: Final = "4"
# How long a worker may run and how many run at once. Both were literals in the
# work job while `config/idhazh.json` declared different numbers that nothing
# read, so config was a wrong answer with a schema behind it (Guardrail #6).
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
    ("digest.yml", "visuals"): (
        "Fetch runtime and visual planner weights",
        "Verify the visual planner weights",
        "Start the visual planner",
        '["models"]["visual_planner"]["sha256"]',
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
    "visual_planner_repo",
    "visual_planner_revision",
    "visual_planner_file",
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
WEIGHTS_CACHE_ROLES: Final = {"work": "summarize", "visuals": "visual_planner"}
# Bumped from v3 when the weights half of the key moved off the workflow `env`
# copy, so the first run after that lands refetches once instead of restoring an
# entry nobody can attribute.
WEIGHTS_CACHE_SUFFIX: Final = "v4"
# Where Playwright unpacks a browser, and so the one path a job caching one may
# name. Two paths would be two entries against the 10 GB ceiling in Guardrail #2,
# which the two weights entries already use most of.
BROWSER_CACHE_PATH: Final = "~/.cache/ms-playwright"
# Who reads the pinned browser build: workflow, job, step id, output name. One
# reader, because a key written twice drifts and a drifted key never hits.
BROWSER_VERSION_SOURCE: Final = ("ci.yml", "scope", "browsers", "playwright")
MEASUREMENT_TARGETS: Final = frozenset({"llm", "image", "corpus", "runtime", "batched"})
# Every job that stands up llama-server, and the log that job writes. Both must
# name the host, the binary and the weights: a shard's throughput is decided by
# the host it drew, and a number that cannot name the bytes that produced it is
# not a measurement (Guardrail #10).
RUNTIME_IDENTITY_JOBS: Final = {
    "work": ("llama-server.log", "summarize_file"),
    "visuals": ("visual-planner.log", "visual_planner_file"),
}
RUNTIME_IDENTITY_STEP: Final = "What this runner is"
# One loopback port per workflow, declared once. `server_argv` binds it, every
# probe reads it, and `idhazh.llm.server` reads it for the address the stage
# posts to - so a moved port cannot leave a server on one and a client on
# another (Guardrail #6).
LLAMA_PORT_ENV: Final = "LLAMA_PORT"
LLAMA_PORT_VALUE: Final = "8080"
LLAMA_PORT_READ: Final = "http://127.0.0.1:${LLAMA_PORT}"
# Every step in the repository that stands a llama-server up, and the config
# root each one reads. Discovery in the test is closed-world, so a new one fails
# here until it appears with an install ahead of it.
SERVER_STARTERS: Final = {
    ("digest.yml", "work"): ("Start the model", "config"),
    ("digest.yml", "visuals"): ("Start the visual planner", "config"),
    ("measure.yml", "runtime"): ("Measure runtime candidate", None),
    ("validate.yml", "qualify"): ("Start the candidate", "backend/var/candidate-config"),
}
RUNTIME_LOG_SUMMARY_STEPS: Final = {
    "work": ("Prompt cache log summary", "llama-server.log"),
    "visuals": ("Visual planner cache log summary", "visual-planner.log"),
}
# Four llama-server lines, copied from the captures under
# `tests/fixtures/runtime/` and then edited in one place each: the second
# carries `n_ctx_seq` where the capture carries `n_ctx_slot`, and the fourth
# carries `n_ctx_per_seq`. Those two spellings appear in no capture this project
# holds - they are what a later llama.cpp bump renames the field to, and the
# whole reason the summary step greps three names for one field.
#
# Until 2026-09-09 every line here opened at `srv` or `slot` and the first two
# said `kv_unified = 'true'`. No line llama-server prints looks like that: the
# tag is the third field, after a timestamp and a level letter, and all four
# captures print `'false'`. That is the same mistake the summary step's own
# pattern made, written down twice and agreeing with itself.
RUNTIME_LOG_LINES: Final = (
    (
        "0.03.804.331 I srv    load_model: initializing, n_slots = 1, "
        "n_ctx_slot = 8192, kv_unified = 'false'"
    ),
    (
        "0.03.804.331 I srv    load_model: initializing, n_slots = 1, "
        "n_ctx_seq = 8192, kv_unified = 'false'"
    ),
    (
        "3.09.738.586 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, "
        "f_sim_best = 0.926 (> 0.100 thold), f_keep = 0.782"
    ),
    (
        "0.33.179.385 I srv    load_model: initializing, n_slots = 1, "
        "n_ctx_per_seq = 8192, kv_unified = 'false'"
    ),
)
# The head of llama-server's own log, one per work shard of run `2026-08-29-3`.
# The pattern below is checked against these rather than against the four
# strings above, because a pattern nobody ran against a real line is how the
# `^(srv|slot) ` anchor survived review (Guardrail #7).
RUNTIME_LOG_CAPTURES: Final = sorted(
    (FIXTURES_DIR / "runtime").glob("2026-08-29-3-shard-*.server-head.txt")
)
# The tag a capture carries that this step is not for: the common-args block.
# Named so the count below is a number and not "most of them".
RUNTIME_LOG_UNCLAIMED_TAG: Final = "cmn"
RSS_SAMPLE_FILE: Final = "rss-samples.tsv"
SERVER_LOG_FILE: Final = "llama-server.log"
MEMORY_PEAK_FILE: Final = "memory-peak.txt"
CGROUP_PEAK_PATH: Final = "/sys/fs/cgroup/memory.peak"
# The two steps of the work job that write and read those files. The third,
# which writes `memory-peak.txt` and hands it to the stage, is `COUNTERS_STEP`
# below.
SAMPLE_MEMORY_STEP: Final = "Sample memory"
MEMORY_SUMMARY_STEP: Final = "What memory this shard used"
# The sampler itself, which stopped being a heredoc inside that step on
# 2026-09-12: two jobs take this reading now, and a shell step two jobs run is
# what `.github/scripts/` is for (`CLAUDE.md` section 3). It is also now under
# `shellcheck`, which cannot see a `run:` body.
SAMPLE_SCRIPT: Final = SCRIPTS_DIR / "sample-rss.sh"
# Which `rss-samples.tsv` column the operator print reads at each `awk` field
# number. It reads by position, so this mapping is the whole agreement between
# the step that writes the file and the step that reads it - and it lives in no
# other file, which is why it is written out here.
RSS_SAMPLE_FIELDS: Final = {
    2: "llama_vmrss_kb",
    3: "llama_vmhwm_kb",
    4: "python_vmrss_kb",
    6: "python_vmhwm_kb",
}
# The roll-call beside it: one row per python process per sample, so the count
# in `python_procs` can be attributed. Same two-reader hazard as above - the
# operator print reads it by position - so the same agreement is written down.
PYTHON_PROCS_FILE: Final = "python-procs.tsv"
PYTHON_PROCS_FIELDS: Final = {
    2: "pid",
    3: "comm",
    4: "vmrss_kb",
    6: "exe",
    7: "args",
}
#: The one reading that has to be taken at both ends of the job. `/proc/stat`
#: counts since boot, so a single read is mostly the minutes the runner spent
#: booting. `/proc/stat` rather than a cgroup file because two cgroup files this
#: repository has read - `memory.peak` and `cpu.max` - are absent on a
#: GitHub-hosted runner, and `/proc/stat` is on every Linux there is.
CPU_STAT_READING: Final = "awk '/^cpu / { print }' /proc/stat"
#: The step that takes the first of the two readings. The second is taken in
#: `COUNTERS_STEP`, which is also where both are handed to the row.
CPU_STAT_STEP: Final = "Stamp the shard clock and the host"
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
    "visuals": "visuals",
    "assemble": "assemble",
    "fold": "assemble",
}
COMMIT_STEPS: Final = {
    "plan": "Commit what the plan saw",
    "work": "Commit what this shard measured",
    "visuals": "Commit what the visual planner counted",
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
    # The plan job records one verdict per feed per run. A second attempt at one
    # plan writes its own verdict for every feed, against a checkout that cannot
    # see the first attempt's push, so the union keeps both and one bad run reads
    # as two failures.
    "plan": COMMIT_BASE_ENV | {"DROP_REPEATED_ROWS_COMMAND"},
    # Its filters read a checkout frozen at the commit this run was triggered at,
    # so a second attempt cannot see the first attempt's pushed rows and the
    # union keeps both - which is what the post-merge pass is for.
    "work": COMMIT_BASE_ENV | {"DROP_REPEATED_ROWS_COMMAND"},
    # One row, from a job that runs after every work shard has pushed. It still
    # settles, for the same reason: a second attempt at this job cannot see the
    # row the first attempt pushed, and the union merge keeps both.
    "visuals": COMMIT_BASE_ENV | {"DROP_REPEATED_ROWS_COMMAND"},
    "assemble": COMMIT_BASE_ENV
    | {"REFRESH_PATHS", "REGENERATE_COMMAND", "DROP_RACED_ASSETS_COMMAND"},
    "fold": COMMIT_BASE_ENV,
}
COMMIT_STAGED_PATHS: Final = {
    "plan": ["state/seen", "state/feed-health", "state/feed-retirements.csv"],
    # `state/score-index` is beside `state/scores` because it is the record of
    # what those rows are, and the writer reads it instead of them. A shard
    # committed without its index is a month the next run cannot recognise, so
    # it would append every measurement in it a second time.
    "work": [
        "state/item-health",
        "state/scores",
        "state/score-index",
        "state/runtime-counters.csv",
    ],
    # One file. The visuals job measures one server and writes one row, and the
    # `job` cell on it is what keeps that row out of the work shards' record.
    "visuals": ["state/runtime-counters.csv"],
    "assemble": [
        "frontend/public/digest",
        "frontend/public/telemetry",
        "frontend/public/assist/index",
        "frontend/public/source-health.json",
        "frontend/public/console",
        "frontend/public/scores",
        "frontend/public/feed-health",
        "frontend/public/run-days",
        "frontend/public/day-metrics",
        "frontend/public/machine",
        "frontend/public/span-rollup",
        "state",
        "corpus",
    ],
    # `state` whole, and deliberately not the directories the fold touches:
    # `state/telemetry-aggregate/` does not exist in a fresh checkout, and
    # `git add` on a path that is not there aborts the whole step.
    # `frontend/public/telemetry` is named beside it because the fold deletes the
    # browser's copy of a folded month, and `git add` records a removal only for
    # a path it is handed. That directory IS in every checkout.
    "fold": ["state", "frontend/public/telemetry"],
}
# The step that folds an out-of-window month before the step above commits it.
# It runs after the day's own commit, so a retirement that loses its push costs
# one run's bytes and never a published day.
FOLD_STEP: Final = "Retire the ledger shards and the visuals nothing still reads"
FOLD_COMMAND: Final = "python -m idhazh prune-state"
# Set on purpose. `prune.yml` force-pushes main on a schedule, so a state file
# this step deletes stops being recoverable from history once the prune passes
# over it (CLAUDE.md section 8). The step logs every file a live run would remove
# and removes nothing; turning the deletion on is a one-line commit of its own,
# taken after a scheduled run has printed that list.
FOLD_DRY_RUN_FLAG: Final = "--dry-run"
# The step that fills the two ledgers the step above commits, and the two things
# that decide which items are this shard's.
RECORD_STEP: Final = "Record what this shard measured"
RECORD_COMMAND: Final = "python -m idhazh record"
# The pass that runs after the merge, and the flag that says what it covers. A
# run appends only to the shard its own date routes to, so the date is the whole
# cover - without it the pass reads every feed-health, item-health and score
# shard the archive holds and costs more every month (Guardrail #12).
SETTLE_COMMAND: Final = ("python", "-m", "idhazh", "dedupe-ledgers")
SETTLE_COVER_FLAG: Final = "--date"
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
# One committed file per console payload root, read off the working tree rather
# than listed here: the roots are named in `publish_console` and every one of
# them ships with whatever its producer wrote, so a second list would be a
# second thing to keep in step. Seven directory listings, once a session.
CONSOLE_SEED: Final = tuple(
    f"frontend/public/{dirname}/{path.name}"
    for dirname in publish_console.PUBLISHED_ROOTS
    for path in sorted((REPO_ROOT / "frontend" / "public" / dirname).glob("*"))
    if path.is_file()
)
# The third ledger the same commit step stages: what llama-server itself counted
# for this shard. It has to sit between the other two, because the row it writes
# is committed by the step after it.
COUNTERS_STEP: Final = "What the server counted"
COUNTERS_COMMAND: Final = "python -m idhazh counters"
# The same three steps in the visuals job, which took none of these readings
# until 2026-09-12 - so every live-path figure on record belonged to the
# summarizer and none to the visual planner.
VISUALS_CLOCK_STEP: Final = "Stamp the visuals clock and the host"
VISUALS_SAMPLE_MEMORY_STEP: Final = "Sample visuals memory"
VISUALS_COUNTERS_STEP: Final = "What the visual planner counted"
VISUALS_MEMORY_SUMMARY_STEP: Final = "What memory the visual planner used"
VISUALS_SERVER_LOG_FILE: Final = "visual-planner.log"
# The flag that says which job a row came from, and the two values in use. A row
# that cannot say which job wrote it proves nothing: the two jobs serve
# different weights, and they both spell shard 0 of the same run.
COUNTERS_JOB_FLAG: Final = "--job"
COUNTERS_JOBS: Final = {"work": "work", "visuals": "visuals"}
# The two-row fixture the reader is driven over: one `work` row and one
# `visuals` row, sharing a date, a run and a shard index. Fixed in size, and it
# carries a case the committed ledger has never held (Guardrail #12).
COUNTERS_FIXTURE: Final = FIXTURES_DIR / "runtime-counters" / "visuals-job-row.csv"
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
# The same pair in the visuals job. It is one rung further down: the work job
# may not fail the shard, and this job may not fail at all - `continue-on-error`
# on the whole job plus assemble's `always()` means a visual planner that never
# started costs every item its picture and costs the day nothing.
VISUALS_LEDGER_STEPS: Final = (VISUALS_COUNTERS_STEP, COMMIT_STEPS["visuals"])
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
# directory is never in this list: the visuals artifact unpacks this run's
# rendered charts into it, and no producer in the assemble job can make those
# again, so the two payload files are named one at a time.
COMMIT_REFRESH_PATHS: Final = {
    "assemble": [
        f"{SUBSTITUTED_DAY_DIR}/digest.json",
        f"{SUBSTITUTED_DAY_DIR}/run.json",
        "frontend/public/telemetry",
        "frontend/public/assist/index",
        "frontend/public/source-health.json",
        "frontend/public/console",
        "frontend/public/scores",
        "frontend/public/feed-health",
        "frontend/public/run-days",
        "frontend/public/day-metrics",
        "frontend/public/machine",
        "frontend/public/span-rollup",
        "state/published",
        "state/scores",
        "state/score-index",
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
# One rendered chart, as the visuals job leaves it: an SVG in the day's directory
# and a decision payload saying where it landed. The name is the item's own id,
# so a path both runs hold is that one item rendered twice.
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


def _strings(node: object) -> Iterator[str]:
    """Every string anywhere in a YAML subtree, so an expression cannot hide in a nest."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in cast(dict[str, object], node).values():
            yield from _strings(value)
    elif isinstance(node, list):
        for item in cast(list[object], node):
            yield from _strings(item)


def _needs(workflow: dict[str, object], job_name: str) -> list[str]:
    """What a job waits on, whether it was written as one name or a list."""
    declared = _job(workflow, job_name).get("needs")
    if declared is None:
        return []
    if isinstance(declared, str):
        return [declared]
    return _string_list(declared, f"job {job_name} needs")


def _artifact_upload(
    workflow: dict[str, object], job_name: str, artifact: str
) -> dict[str, object]:
    matches = [
        step
        for step in _steps(workflow, job_name)
        if str(step.get("uses", "")).startswith("actions/upload-artifact")
        and _mapping(step.get("with"), f"{job_name} upload").get("name") == artifact
    ]
    assert len(matches) == 1, f"job {job_name} must upload one artifact named {artifact}"
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


#: A `python-version` that names a matrix key rather than a version.
_MATRIX_PIN: Final = re.compile(r"^\$\{\{\s*matrix\.([A-Za-z0-9_-]+)\s*\}\}$")


def _setup_python_versions(workflow: dict[str, object]) -> list[tuple[str, str]]:
    """Every interpreter a workflow sets up, with a matrix expanded to its values.

    A job that sets one up names a version; a job that sets two up names a
    matrix key, and the versions are in `strategy.matrix`. Reading the literal
    alone would let a matrix pin anything at all, which is the one place two
    versions can arrive.
    """
    versions: list[tuple[str, str]] = []
    for job_name in _mapping(workflow.get("jobs"), "jobs"):
        for step in _steps(workflow, job_name):
            uses = step.get("uses")
            if not (isinstance(uses, str) and uses.startswith("actions/setup-python@")):
                continue
            with_block = _mapping(step.get("with"), f"job {job_name} setup-python 'with'")
            version = with_block.get("python-version")
            assert isinstance(version, str), f"job {job_name} must pin python-version"
            for pinned in _matrix_values(workflow, job_name, version):
                versions.append((job_name, pinned))
    return versions


def _matrix_values(workflow: dict[str, object], job_name: str, version: str) -> list[str]:
    """One pin, or every value the matrix key it names carries."""
    named = _MATRIX_PIN.fullmatch(version)
    if named is None:
        return [version]
    key = named.group(1)
    strategy = _mapping(_job(workflow, job_name).get("strategy"), f"job {job_name} strategy")
    matrix = _mapping(strategy.get("matrix"), f"job {job_name} matrix")
    values = matrix.get(key)
    assert isinstance(values, list), f"job {job_name} names matrix.{key}, which lists nothing"
    assert values, f"job {job_name} names matrix.{key}, which is empty"
    return [str(value) for value in values]


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

    `GITHUB_OUTPUT` goes for a second reason. CI runs this suite inside a step
    that has one, so an inherited value would let the script append to the gates
    step's own outputs - and the test that the script survives without the
    variable would only be a real test on the machines that never had it.
    """
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {
        **{name: value for name, value in os.environ.items() if name != "GITHUB_OUTPUT"},
        "HOME": str(home),
        "USERPROFILE": str(home),
        "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _step_outputs(written: Path) -> dict[str, str]:
    """What Actions reads back from one step's `$GITHUB_OUTPUT` file."""
    return dict(
        cast(tuple[str, str], tuple(line.split("=", 1)))
        for line in written.read_text(encoding="utf-8").splitlines()
        if line
    )


def _reading_its_output(tmp_path: Path, settings: dict[str, str]) -> tuple[dict[str, str], Path]:
    """The step's own settings, plus the output file a workflow step would give it."""
    written = tmp_path / "github-output"
    written.write_text("", encoding="ascii")
    return {**settings, "GITHUB_OUTPUT": written.as_posix()}, written


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
    filename would have built a directory called `scores.csv`. The assemble job
    stages a named `.json` for the same reason, and it needs the same answer.
    """
    return staged if staged.endswith((".csv", ".json")) else f"{staged}/ledger.csv"


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
    """One rendered chart, exactly as the visuals job's artifact leaves it.

    An SVG under the day's directory and a real `VisualDecision` beside the run's items
    saying where it landed. `body` is what makes two renders of one item differ,
    which is the only case that can now put two adds on one path - identical
    bytes are the case git resolves on its own.
    """
    _write(repo / "frontend" / "public" / relpath, f"<svg>{body or item_id}</svg>\n")
    decision = VisualDecision(
        version=VisualDecision.schema_version(),
        item_id=item_id,
        url_key=hashlib.sha256(item_id.encode("ascii")).hexdigest(),
        kind=VisualKind.CHART,
        spec='{"mark": "bar"}',
        asset_path=relpath,
        visual_state=VisualState.RENDERED,
        model_id="qwen3-4b",
        decided_at=f"{date}T00:00:00Z",
    )
    _write(repo / RUN_ARTIFACTS / date / "items" / f"{item_id}{PAYLOAD_SUFFIX}", decision.to_json())


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
    # The console payload roots, for the same reason and copied the same way.
    # They are named in the commit step and in the refresh set, so a clone
    # without them fails at `git add` rather than at the payload.
    for relative in CONSOLE_SEED:
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
    # The shipped command resolves `state/` off the installed package, which
    # under a test is this repository rather than the temporary clone. Running it
    # unchanged would settle the developer's own committed ledgers and report
    # nothing, so a test that forgets `_settled_in_the_clone` fails here by name.
    settle = settings.get("DROP_REPEATED_ROWS_COMMAND", "")
    assert SETTLE_STAND_IN.as_posix() in settle or not settle, (
        "pass DROP_REPEATED_ROWS_COMMAND through _settled_in_the_clone: "
        "the shipped one would settle this repository's own state/"
    )
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
        "the slot arrives through env, never pasted into the script (Guardrail #11)"
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


#: What the shipped script has to answer through a real git history.
#:
#: The truth table itself is in `frontend/scripts/tests/test-scope.test.mjs`,
#: where a case is a function call. Here a case is a temporary repository, two
#: commits and a shell, and twenty-four of them cost 168 s of this module's
#: 585 s on an i7-1265U, 2026-09-05 - for an answer the pure function already
#: gives. These four are the plumbing rather than the policy: one change that
#: buys everything, one that buys the browser half without the console, one that
#: re-reads the archive because it moved the shape a day is read through, and
#: one that buys nothing.
BROWSER_SCOPE_CASES: Final = (
    ("frontend/src/routes/console/+page.svelte", True, True, True, False),
    ("frontend/src/routes/[date]/+page.svelte", True, True, False, False),
    ("config/idhazh.json", True, True, False, True),
    ("docs/reference/measurements.md", False, False, False, False),
)


def test_the_selector_tests_use_the_same_node_as_the_ci_selector() -> None:
    workflow = _load_workflows()["ci.yml"]
    versions: dict[str, object] = {}
    for job in ("scope", "gates"):
        steps = _steps(workflow, job)
        node_steps = [
            step for step in steps
            if str(step.get("uses", "")).startswith("actions/setup-node@")
        ]
        assert len(node_steps) == 1, f"{job} must declare the selector's Node runtime"
        settings = node_steps[0].get("with")
        assert isinstance(settings, dict)
        versions[job] = settings.get("node-version")
        if job == "gates":
            test_step = next(step for step in steps if step.get("run") == "pytest")
            assert steps.index(node_steps[0]) < steps.index(test_step)
    assert versions["scope"] is not None
    assert versions["gates"] == versions["scope"]


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
@pytest.mark.parametrize(
    ("changed", "browser", "code", "console", "validate_all"), BROWSER_SCOPE_CASES
)
def test_the_browser_half_is_skipped_only_for_a_change_that_cannot_reach_a_page(
    changed: str, browser: bool, code: bool, console: bool, validate_all: bool, tmp_path: Path
) -> None:
    """The filter is executed, not read.

    A copy of the pattern in this file would agree with itself forever while the
    shipped script skipped a change that breaks a published page. So the test
    builds a real two-commit history, runs the script the workflow runs, and
    reads the lines it writes to `$GITHUB_OUTPUT`.

    What is under test here is the plumbing - the shell, the git range and the
    output format. Which paths select which groups is decided by a pure function
    and checked case by case in `frontend/scripts/tests/test-scope.test.mjs`.
    """
    assert _browser_scope(tmp_path, [changed]) == {
        "browser": str(browser).lower(),
        "code": str(code).lower(),
        "console": str(console).lower(),
        "validate_all": str(validate_all).lower(),
    }


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
def test_a_push_carrying_code_still_never_consults_the_list(tmp_path: Path) -> None:
    """The group each path selects is a wager that nobody forgot a path. The
    merge commit is where that wager is settled, so a push that carries any code
    buys everything - a pull request the list was wrong about reddens `main`
    within minutes instead of reaching a reader.
    """
    assert _browser_scope(
        tmp_path, ["docs/x.md", "backend/idhazh/discover.py"], event="push"
    ) == {
        "browser": "true",
        "code": "true",
        "console": "true",
        "validate_all": "true",
    }


@requires_bash
def test_a_push_carrying_no_code_starts_no_code_job(tmp_path: Path) -> None:
    """The one question a push does read the paths for.

    A changed sentence cannot break an application check, so the merge that
    carries it should not spend the suite proving that. This is safe where the
    wager above is not, because the documentation branch is a closed list of
    prefixes: a path nobody classified falls to full coverage instead.
    """
    assert _browser_scope(tmp_path, ["docs/x.md"], event="push") == {
        "browser": "false",
        "code": "false",
        "console": "false",
        "validate_all": "false",
    }


def test_a_trunk_push_is_never_cancelled_by_the_next_one() -> None:
    """The rule that makes the `scope` job safe on a push.

    `scope` answers from each push's own changed paths, so a push carrying only
    documentation correctly checks nothing. That is only sound while it cannot
    cancel a push that carried code: the surviving run checks nothing because
    nothing in ITS range needed checking, and the code reaches the trunk with no
    verdict on the trunk. Measured 2026-09-12, before this was fixed: two pushes
    carrying 14 code files between them were cancelled by a third that changed
    one plan-doc.
    """
    concurrency = _mapping(_load_workflows()["ci.yml"]["concurrency"], "ci.yml concurrency")
    cancel = str(concurrency["cancel-in-progress"])
    assert cancel != "true", "a push to the trunk has to keep the run it started"
    assert "pull_request" in cancel, (
        "cancelling is still right on a pull request, where a newer commit "
        "supersedes the older one and its verdict is worth nothing"
    )
    assert "github.sha" in str(concurrency["group"]), (
        "a push groups by its own commit, so it is neither cancelled by nor "
        "queued behind the next push"
    )


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


def test_the_daily_publish_validates_the_day_it_wrote_and_not_every_other_one() -> None:
    """A published day is frozen, so re-opening all of them buys nothing.

    Measured 2026-09-05 on an i7-1265U: 16 committed days took 6.6 s to 7.1 s,
    about 0.27 s a day on top of a fixed start. The pipeline publishes five
    times a day, so a year of days would spend roughly eight minutes a day
    re-deriving an answer settled when each of those days was written
    (`CLAUDE.md` Guardrail #12).

    `backfill.yml` is deliberately not here: it repairs days it chooses, so the
    day it has to check is not one this file can name.
    """
    steps = _steps(_load_workflows()["digest.yml"], "assemble")
    call = next(
        shlex.split(str(step.get("run", "")))
        for step in steps
        if tuple(shlex.split(str(step.get("run", "")))[:4]) == VALIDATE_DAYS_CALL
    )
    assert "--day" in call, "the daily publish still opens every committed day"
    named = call[call.index("--day") + 1]
    assert "needs.plan.outputs.date" in named, (
        f"the day is {named!r}, which is not the day this run was planned for"
    )


def test_the_whole_tree_is_re_read_only_when_the_shape_it_is_read_through_moves() -> None:
    """The other half: `ci.yml` pays the full price on the change that earns it.

    A contract, schema, config or harness edit can invalidate a day nobody
    touched, and a merge to `main` always counts. Anything else leaves every
    committed day exactly as valid as it was when it was pushed.
    """
    workflow = _load_workflows()["ci.yml"]
    # `needs:` is a bare string for one dependency and a list for several.
    declared = _job(workflow, "gates").get("needs")
    waits_for = [declared] if isinstance(declared, str) else declared
    assert isinstance(waits_for, list) and "scope" in waits_for, (
        "gates cannot read the selector's answer without waiting for it"
    )
    outputs = _job(workflow, "scope").get("outputs")
    assert isinstance(outputs, dict) and "validate_all" in outputs, (
        "the selector's answer is not published for another job to read"
    )
    step = next(
        step
        for step in _steps(workflow, "gates")
        if tuple(shlex.split(str(step.get("run", "")))[:4]) == VALIDATE_DAYS_CALL
    )
    assert "validate_all" in str(step.get("if", "")), (
        "the full pass over the archive runs on every change, whatever moved"
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

    `npm run build` compiles every route and prerenders six of them, so a route
    that cannot build, and one of those six that cannot render, fails here
    instead of in a reader's browser. That day is broken and must not publish,
    so the build runs before the commit. The two dated reading routes render in
    the browser and the build no longer answers for them; `idhazh validate-days`
    sits beside it at the same severity and for the same reason - it is what
    opens the stories a seeded document never serialises.

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

    And it is conditional, because a push that landed first try left the tree
    the first build already read. The condition has to name every commit step
    that runs before it: `assemble` commits twice, the second stages
    `frontend/public/telemetry`, and the console pages read that - so a
    condition naming only the day's commit would skip the rebuild on the other
    one and put run 33270983446 straight back.
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

    assert "if" in steps[rebuilt[0]], (
        "an unconditional rebuild pays for the race on every run, raced or not"
    )
    condition = _normalize_condition(
        steps[rebuilt[0]].get("if"), f"{filename}/{job_name} rebuild condition"
    )
    for index in commits:
        # Either the step's own `id`, so the condition reads what it reported,
        # or the condition that decides whether it commits at all - which is how
        # a job with one commit step and a dispatch switch says the same thing.
        named = str(steps[index].get("id") or steps[index].get("if") or "")
        assert named and named in condition, (
            f"{steps[index].get('name')} can rewrite the checkout, so the rebuild's "
            "condition has to name it"
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


def test_ci_keeps_its_push_boundary_and_pages_publishes_only_a_verdict() -> None:
    workflows = _load_workflows()

    ci_push = cast(dict[str, object], _triggers(workflows["ci.yml"])["push"])
    assert set(ci_push) == {"branches", "paths-ignore"}
    assert ci_push["branches"] == ["main"]
    # The `status-page` job's loop guard, and the reason it is a trigger filter
    # rather than a job condition or a `[skip ci]` marker: a push holding only
    # this file starts no run at all, whoever pushed it, and every other gate on
    # that commit still runs.
    assert ci_push["paths-ignore"] == [STATUS_PAGE]

    pages = _triggers(workflows["pages.yml"])
    assert "push" not in pages, (
        "a push reaches this workflow at the same moment it reaches CI, so "
        "publishing on one publishes before anything has judged the commit"
    )
    assert pages["workflow_run"] == {
        "workflows": ["CI", "Content refresh"],
        "types": ["completed"],
    }

    jobs = _mapping(workflows["pages.yml"]["jobs"], "pages.yml jobs")
    decide = _mapping(jobs["decide"], "pages.yml decide job")
    condition = str(decide["if"])
    assert "conclusion == 'success'" in condition, (
        "a workflow_run trigger cannot be filtered by conclusion, so a CI run "
        "that failed has to be refused by the job that reads it"
    )
    assert "!= 'CI'" in condition, (
        "the daily path is deliberately not gated on conclusion: the job that "
        "writes a day validates it before committing, so a sibling job failing "
        "afterwards must not hold a good day back"
    )
    checkout = next(
        step
        for step in _steps(workflows["pages.yml"], "build")
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    pinned = str(_mapping(checkout["with"], "pages.yml build checkout").get("ref"))
    assert "needs.decide.outputs.ref" in pinned, (
        "what deploys is the commit that was verified, not the tip minutes later"
    )


def test_the_plan_queue_has_exactly_one_writer() -> None:
    """One job regenerates the page, and a pull request may not carry it.

    Two assertions, because either alone leaves the conflict in place: a second
    writer anywhere puts two branches back on the same lines, and a gate that
    does not refuse the file lets a branch bring its own copy.
    """
    workflow = _load_workflows()["ci.yml"]

    writers = [
        f"{job_name}/{step.get('name')}"
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if STATUS_PAGE_WRITE in str(step.get("run", ""))
    ]
    assert len(writers) == 1, f"{STATUS_PAGE} has one writer; these regenerate it: {writers}"
    assert writers[0].startswith(f"{STATUS_PAGE_JOB}/")

    guard = _step(workflow, "gates", "name", STATUS_PAGE_GUARD)
    assert _normalize_condition(guard.get("if"), "plan queue guard condition") == (
        "github.event_name == 'pull_request'"
    )
    script = _script(guard, f"ci.yml/gates/{STATUS_PAGE_GUARD}")
    assert STATUS_PAGE in script
    # A pull request is checked out as a merge commit whose first parent is the
    # base branch, so this range is what the branch changes - and reading it
    # needs the one extra commit below rather than a fetch over the network.
    assert "HEAD^1 HEAD" in script
    checkout = next(
        step
        for step in _steps(workflow, "gates")
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    assert _mapping(checkout.get("with"), "gates checkout 'with'").get("fetch-depth") == "2"


def test_the_status_page_job_writes_only_after_a_merge() -> None:
    workflow = _load_workflows()["ci.yml"]
    job = _job(workflow, STATUS_PAGE_JOB)

    assert _normalize_condition(job.get("if"), "status-page condition") == (
        "github.event_name == 'push'"
    )
    assert _mapping(workflow.get("permissions"), "ci.yml permissions") == {
        "contents": "read"
    }, "only the job that writes is widened, and it widens itself"
    assert _mapping(job.get("permissions"), "status-page permissions") == {"contents": "write"}
    assert "needs" not in job, (
        "the page is derived from the plan-docs alone, so a gate that is red "
        "about something else would only hold a correct page back"
    )

    names = [str(step.get("name")) for step in _steps(workflow, STATUS_PAGE_JOB)]
    commit_step = "Commit the plan queue, when a Reckoner moved"
    commit = _step(workflow, STATUS_PAGE_JOB, "name", commit_step)
    assert names.index("Regenerate the plan queue from the Reckoners") < names.index(commit_step)

    script = _script(commit, f"ci.yml/{STATUS_PAGE_JOB}/commit")
    # The termination argument the trigger filter does not carry: a run over a
    # tree this job already wrote finds no diff, so it commits nothing and there
    # is no second push to guard against.
    assert f"git diff --quiet -- {STATUS_PAGE}" in script
    assert f"git add {STATUS_PAGE}" in script
    assert "git push origin HEAD:main" in script


@requires_bash
def test_the_plan_queue_guard_reads_a_real_merge_commit(tmp_path: Path) -> None:
    """The shipped shell, against a real merge commit, both ways.

    The check is about what a pull request changes, and a pull request is a
    merge commit - so the fixture is one, built twice: once where the branch
    edits the page and once where it does not. A check that read the working
    tree, or the tip of `main`, would pass both arms.
    """
    bash = _bash()
    assert bash is not None, "requires_bash admitted a run with no bash"
    script = _script(
        _step(_load_workflows()["ci.yml"], "gates", "name", STATUS_PAGE_GUARD),
        f"ci.yml/gates/{STATUS_PAGE_GUARD}",
    )
    env = _isolated_env(tmp_path)

    for edits_the_page, expected in ((False, 0), (True, 1)):
        repo = tmp_path / ("edited" if edits_the_page else "untouched")
        repo.mkdir()
        _git(repo, env, "init", "-b", "main")
        _write(repo / STATUS_PAGE, "# The plan queue\n")
        _write(repo / "docs" / "page.md", "before\n")
        _git(repo, env, "add", ".")
        _git(repo, env, "commit", "-m", "the base")
        _git(repo, env, "switch", "-c", "branch")
        _write(repo / "docs" / "page.md", "after\n")
        if edits_the_page:
            _write(repo / STATUS_PAGE, "# The plan queue\n\nhand-edited\n")
        _git(repo, env, "add", ".")
        _git(repo, env, "commit", "-m", "the branch")
        _git(repo, env, "switch", "main")
        _git(repo, env, "merge", "--no-ff", "--no-edit", "branch")

        run = subprocess.run(
            [bash, "-c", script], cwd=repo, env=env, capture_output=True, text=True
        )
        assert run.returncode == expected, f"{run.stdout}\n{run.stderr}"
        if expected:
            assert STATUS_PAGE in run.stderr, "the message says which file and why"


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


def test_every_output_a_job_reads_is_one_its_producer_declares() -> None:
    """A renamed job leaves `needs.<old>.outputs.<x>` resolving to the empty string.

    GitHub does not fail on that. The expression evaluates to nothing, the step
    runs with an empty argument, and the run is green - so a job rename is the
    one edit whose damage shows up only in the output. This walks every
    `needs.<job>.outputs.<name>` in every workflow and asks two things of it:
    that the job is one this job waits on, and that the job declares that output.
    """
    for filename, workflow in sorted(_load_workflows().items()):
        jobs = _mapping(workflow.get("jobs"), "jobs")
        declared = {
            job_name: set(_mapping(_job(workflow, job_name).get("outputs") or {}, "outputs"))
            for job_name in jobs
        }
        for job_name in jobs:
            waits_on = set(_needs(workflow, job_name))
            read = {
                (match.group(1), match.group(2))
                for text in _strings(_job(workflow, job_name))
                for match in re.finditer(r"needs\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_-]+)", text)
            }
            for producer, output in sorted(read):
                where = f"{filename} job {job_name}"
                assert producer in jobs, f"{where} reads an output of the absent job {producer}"
                assert producer in waits_on, f"{where} reads {producer} without needing it"
                assert output in declared[producer], (
                    f"{where} reads needs.{producer}.outputs.{output}, "
                    f"which {producer} does not declare"
                )


def test_every_artifact_a_job_downloads_is_uploaded_by_a_job_it_waits_on() -> None:
    """An artifact name is a string agreed between two jobs and checked by nobody.

    `download-artifact` on a name nothing uploaded fails the step, and both of
    the daily run's cross-job downloads carry `continue-on-error` - so a
    mismatched name degrades the day to no visuals rather than failing it. Same
    silence as the glob below, one layer up.

    A `pattern:` download takes any number of matching artifacts, so it is
    checked as a prefix rather than as a name.
    """
    for filename, workflow in sorted(_load_workflows().items()):
        uploads = {
            str(_mapping(step.get("with"), "upload").get("name")): job_name
            for job_name in _mapping(workflow.get("jobs"), "jobs")
            for step in _steps(workflow, job_name)
            if str(step.get("uses", "")).startswith("actions/upload-artifact")
        }
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            reachable = set(_needs(workflow, job_name))
            for step in _steps(workflow, job_name):
                if not str(step.get("uses", "")).startswith("actions/download-artifact"):
                    continue
                asked = _mapping(step.get("with"), f"{job_name} download")
                where = f"{filename} job {job_name}"
                if isinstance(pattern := asked.get("pattern"), str):
                    prefix = pattern.removesuffix("*")
                    # A job's own later upload can match the prefix and cannot
                    # exist yet, so it is not a producer of this download:
                    # `validate.yml` reads `qualification-*` and then writes
                    # `qualification-report`.
                    producers = {
                        uploads[name] for name in uploads if name.startswith(prefix)
                    } - {job_name}
                    assert producers, f"{where} downloads pattern {pattern}, which nothing uploads"
                    assert producers <= reachable, (
                        f"{where} downloads pattern {pattern} from {sorted(producers - reachable)}, "
                        "which it does not wait on"
                    )
                    continue
                name = str(asked.get("name"))
                assert name in uploads, f"{where} downloads {name}, which no job uploads"
                assert uploads[name] in reachable, (
                    f"{where} downloads {name} from {uploads[name]}, which it does not wait on"
                )


def test_the_visuals_artifact_collects_the_file_the_stage_writes() -> None:
    """The upload glob and the Python writer are one pair, and only this holds them.

    `idhazh.cli` files one decision per item under `backend/var/run/<date>/items/`,
    and the `visuals` job hands them to `assemble` by globbing that suffix. The
    upload carries `if-no-files-found: ignore` on purpose - the stage is allowed
    to decide nothing - so a glob that no longer matches the writer uploads an
    empty artifact, `assemble` receives no decisions, every item publishes with
    no picture, and the run is green throughout. Nothing else in the repository
    connects the two: the glob is YAML and the suffix is a Python name.

    The second line is the run's own day, and this asserts that as well as the
    first, because the two failures are opposite and both are silent.
    `render.write.asset_relpath` files every chart under the day that names it,
    so a line naming the whole tree sends every committed day back to Actions on
    every run - a parcel that grows when nobody writes any code (Guardrail #12), and
    it grew 6.36 to 6.66 MB over six runs on 2026-09-07/08. A line that narrows
    past the day loses the charts instead, and the day publishes with none.
    """
    workflow = _load_workflows()["digest.yml"]
    upload = _mapping(_artifact_upload(workflow, "visuals", "visuals").get("with"), "upload")
    paths = _string_list(str(upload.get("path")).splitlines(), "visuals upload path")
    globs = [_substitute(path.strip()) for path in paths if path.strip()]

    # Closed, and in order, because both lines are load-bearing and each one
    # fails silently on its own: the day line without the items line publishes a
    # day with no pictures, and either line alone would move the artifact root
    # off the repository root that `assemble` unpacks into with `path: .`.
    assert globs == [
        f"{RUN_ARTIFACTS}/{SUBSTITUTED_DATE}/items/*{PAYLOAD_SUFFIX}",
        f"{SUBSTITUTED_DAY_DIR}/",
    ], (
        f"the visuals upload must glob *{PAYLOAD_SUFFIX}, which is what the stage "
        "writes, and carry this run's day rather than the whole digest tree"
    )
    assert upload.get("if-no-files-found") == "ignore", (
        "a stage that decided nothing must not fail the job - which is why the "
        "glob above has to be checked here"
    )


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

    A plain assignment is allowed because `set -e` has nothing to act on: the
    exit status is the value's, and a literal always succeeds. One whose value
    comes from a command substitution is still a command, so it is still
    flagged - that is where the hazard would come back.
    """
    lines = read_text(COMMIT_SCRIPT).splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("for attempt in "))
    end = next(index for index, line in enumerate(lines) if line.startswith("done"))
    assert start < end

    literal_assignment = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=[^\s`]*$")
    unguarded = []
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        guarded = (
            stripped.startswith(("if ", "elif ", "fi", "else", "echo ", "["))
            or stripped in {"exit 0", "break", "continue", "then"}
            or "||" in stripped
            or (literal_assignment.match(stripped) is not None and "$(" not in stripped)
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


def test_both_settling_commit_steps_name_the_run_they_settle() -> None:
    """The bound, mirrored where a workflow that drops it reds (Guardrail #12).

    A run appends only to the shard its own date routes to, so a repeat the union
    merge left can only be in a file that run wrote, and the date names it. Drop
    the flag and `cli.stage_dedupe_ledgers` walks every feed-health shard, every
    item-health shard and every score shard the archive holds - a bill that rises
    every month for an answer already given, because a finished month was settled
    when it was written and cannot change again.

    The command refuses to run with no cover at all, so a workflow that lost the
    flag fails its commit step rather than quietly reading the archive. This
    names the step instead of waiting for the run.
    """
    settling = [
        label for label, names in COMMIT_SCRIPT_ENV.items() if "DROP_REPEATED_ROWS_COMMAND" in names
    ]
    assert settling == ["plan", "work", "visuals"]

    for label in settling:
        settle = _commit_call(label)[1]["DROP_REPEATED_ROWS_COMMAND"].split()
        assert tuple(settle[: len(SETTLE_COMMAND)]) == SETTLE_COMMAND
        assert settle[len(SETTLE_COMMAND) :] == [SETTLE_COVER_FLAG, SUBSTITUTED_DATE], (
            f"{label} must name the run it settles, or the pass reads the whole archive"
        )


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
    # Never the day's directory itself. The visuals artifact unpacks this run's
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

    The set is closed rather than a membership check, because what this guards
    is the pattern nobody chose. The published day tree is named on a line of
    its own even though the catch-all above it already matched: a collection
    that inherits a merge rule in silence has had that rule decided for it, and
    a new pattern arriving here without its own reason should fail.

    `state/visual-prunes/**/*.csv` joined on 2026-09-08 when the cleanup record
    became a day tree, and it is here because this test refused it first. Its
    reason is its own rather than the neighbour's: a row is one pass by one run,
    so two runs of a day that both append are not in disagreement, and a repeat
    the union brings is dropped by `VISUAL_PRUNE_KEY`.
    """
    attributes = read_text(REPO_ROOT / ".gitattributes")
    unioned = {
        line.split()[0]
        for line in attributes.splitlines()
        if line and not line.startswith("#") and "merge=union" in line
    }

    assert unioned == {
        "state/*.csv",
        "state/**/*.csv",
        "state/published/**/*.csv",
        "state/visual-prunes/**/*.csv",
    }
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


def test_the_fold_ships_in_dry_run_because_the_history_it_deletes_from_is_rewritten() -> None:
    """Nothing this step deletes can be recovered once the scheduled prune passes.

    `.github/workflows/prune.yml` squashes and force-pushes `main` on a schedule
    (CLAUDE.md section 8), so `git revert` is not a recovery path for a state file
    older than `finetune.prune_keep_days`. The step therefore prints the files a
    live run would remove and removes none of them, and the flag is what makes
    that true rather than a comment saying it is.

    Deleting the flag is the one-line commit that turns the deletion on, and it
    is deliberately a commit somebody has to write and this test has to be
    changed for.
    """
    fold = _step(_load_workflows()["digest.yml"], "assemble", "name", FOLD_STEP)

    assert FOLD_DRY_RUN_FLAG in _script(fold, "assemble fold step")


def test_the_fold_stages_the_browser_copy_it_deletes() -> None:
    """A deletion reaches a commit only for a path `git add` is handed.

    `commit-and-push.sh` runs `git add "$@"` under `set -euo pipefail`. The fold
    unlinks `frontend/public/telemetry/<YYYY-MM>.csv` in the same step it folds
    the ledger behind it, so a commit that staged `state` alone would push the
    fold and leave the published copy of a month whose source is gone - the one
    state `observability.public_telemetry_keep_months` exists to prevent.

    Both paths are in a fresh checkout, which is the other half: `git add` on a
    path that is not there aborts the step and takes the fold with it.
    """
    staged = COMMIT_STAGED_PATHS["fold"]

    assert publish_telemetry.PUBLIC_TELEMETRY_DIRNAME in "/".join(staged)
    assert "frontend/public/telemetry" in staged
    for relative in staged:
        assert (REPO_ROOT / relative).is_dir(), f"{relative} must be in a fresh checkout"


def test_the_fold_stages_state_whole_because_two_of_its_stores_appear_late() -> None:
    """`state/telemetry-aggregate/` and `state/score-archive/` are written, never seeded.

    Neither exists in a fresh checkout: one appears the first time a month is
    folded and the other the first time a month is archived. Naming either in
    the commit step would abort `git add` under `set -euo pipefail` on every run
    before that day, and take the sibling ledgers staged in the same call with
    it. Row 1 solved the same problem for `state/feed-retirements.csv` by
    committing a header-only file; there is no header-only form of a directory,
    so the answer here is to stage `state`, which is always there.

    `state/visual-prunes/` is the third store this call covers and it needs no
    change here either. It moved from a flat file to a day tree on 2026-09-08,
    so a run now writes a path its own checkout did not carry - and staging
    `state` whole already reaches it, which is why that move needed nothing in
    this step.
    """
    staged = COMMIT_STAGED_PATHS["fold"]

    assert "state" in staged
    assert ledger.visual_prunes_relpath(SUBSTITUTED_DATE).split("/")[0] in staged
    for late in ("telemetry-aggregate", "score-archive"):
        assert f"state/{late}" not in staged, f"state/{late} is not in a fresh checkout"
        assert not (REPO_ROOT / "state" / late).exists(), (
            f"state/{late} is now committed, so this test is asserting the wrong thing"
        )


def test_the_cleanup_is_filed_under_the_run_that_published_the_day() -> None:
    """The step passes the same `github.run_id` the plan job filed its ledgers under.

    Without it the cleanup row would carry a run id counted off the committed
    manifest, and that count is what two overlapping runs were able to read the
    same answer from - so a row would join to the wrong run, or to a run that
    never happened.
    """
    fold = _step(_load_workflows()["digest.yml"], "assemble", "name", FOLD_STEP)

    assert "--execution \"${{ github.run_id }}\"" in _script(fold, "assemble fold step")


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

    Every path the step names is asked of the working tree, so a root added to
    the list without a committed file in it fails here rather than on the runner.
    The console payload roots are the seven that gained a producer on
    2026-09-09: each ships with the shard the producer wrote, which is the same
    pattern `state/feed-retirements.csv` takes.
    """
    for relative in CORPUS_SEED:
        assert (REPO_ROOT / relative).is_file(), f"{relative} must be committed, even when empty"
    for relative in COMMIT_STAGED_PATHS["assemble"]:
        assert (REPO_ROOT / relative).exists(), f"{relative} must be in a fresh checkout"
    for dirname in publish_console.PUBLISHED_ROOTS:
        root = REPO_ROOT / "frontend" / "public" / dirname
        assert root.is_dir(), f"frontend/public/{dirname} must be in a fresh checkout"
        committed = subprocess.run(
            ["git", "ls-files", f"frontend/public/{dirname}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert committed, f"frontend/public/{dirname} must hold at least one committed file"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", *CORPUS_SEED],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode == 0, tracked.stderr.strip()


def test_every_path_the_plan_stages_exists_in_a_fresh_checkout() -> None:
    """The same rule, for the ledger the plan job gained on 2026-09-02.

    Most runs retire nothing, so `state/feed-retirements.csv` is a file that is
    named on every run and written on almost none. It ships with its header for
    exactly that reason - a path that only appears the day a retirement happens
    would abort the plan's commit step every other day, and take the sight and
    health ledgers staged beside it.

    The two directories are named rather than derived because `git add` on a
    directory that does not exist fails the same way, and a fresh clone has both.
    """
    named = COMMIT_STAGED_PATHS["plan"]
    assert ledger.feed_retirements_relpath() in named
    for relative in named:
        assert (REPO_ROOT / relative).exists(), f"{relative} must be in a fresh checkout"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ledger.feed_retirements_relpath()],
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
    for name in VISUALS_LEDGER_STEPS:
        step = _step(workflow, "visuals", "name", name)
        assert step.get("continue-on-error") == TOLERATED, (
            f"visuals step {name} must not fail the job"
        )
    # Closed-world, because a publish step that swallowed its own failure would
    # publish nothing and report success. The one that was already here is
    # assemble's visuals download: `visuals` is allowed to produce no artifact at
    # all, and every item then publishes with no picture. The two fold steps join
    # it for the harvest's reason: they run after the day is committed and touch
    # only months past `observability.item_health_full_grain_months`, so the most
    # a failure costs is one run's worth of bytes and the next run folds the same
    # month again. The two visuals steps join it for the work job's reason, one
    # rung down: this job cannot stop a publication at all, so a scrape or a push
    # that fails there costs one reading and the day nothing.
    tolerant = {
        (job_name, step.get("name") or step.get("uses"))
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if step.get("continue-on-error") == TOLERATED
    }
    assert tolerant == {
        *(("work", name) for name in WORK_LEDGER_STEPS),
        *(("visuals", name) for name in VISUALS_LEDGER_STEPS),
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
        "state/score-index": f"state/score-index/{SUBSTITUTED_DATE[:7]}.csv",
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


def test_the_observation_index_travels_with_the_rows_it_describes() -> None:
    """The index is what the writer reads instead of the rows, so it has to be committed.

    A shard pushed without its index is a month the next run cannot recognise.
    The dedupe would read an index that stops short of the rows beside it, call
    every measurement past that point new, and append each one a second time -
    the one promise the eval ledger makes about itself.

    The assemble job refreshes it for the mirror-image reason. A retry hands the
    rows back to origin's tip and runs the producer again; an index left holding
    the first attempt's digests would make the producer refuse the day it just
    rebuilt, and the day's measurements would be lost rather than doubled.

    The directory is named rather than derived, and `git add` on a path that is
    not there aborts the whole step, so a fresh checkout has to carry it.
    """
    assert score_writer.INDEX_RELDIR in COMMIT_STAGED_PATHS["work"]
    assert score_writer.INDEX_RELDIR in COMMIT_REFRESH_PATHS["assemble"]
    assert (REPO_ROOT / score_writer.INDEX_RELDIR).is_dir()
    tracked = subprocess.run(
        ["git", "ls-files", score_writer.INDEX_RELDIR],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert tracked, f"{score_writer.INDEX_RELDIR} must be in a fresh checkout"


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


def test_assemble_hands_back_the_published_ledger_it_appends_to() -> None:
    """The refresh set covers the day file this stage writes, and asks it where.

    Assemble appends published rows blind, so a second attempt that rebuilt on
    top of its own first attempt would file every item twice. The day is handed
    back to origin's tip before the producer runs again, which is what makes the
    rebuilt append land on the file origin holds rather than on this attempt's.

    The path is read from the writer's own helper rather than spelled here, so
    moving the ledger again fails this instead of leaving a refresh set naming a
    directory nothing writes (Guardrail #6).
    """
    refreshed = _commit_call("assemble")[1]["REFRESH_PATHS"].split()
    day = ledger.published_relpath(SUBSTITUTED_DATE)

    assert any(day == path or day.startswith(f"{path}/") for path in refreshed), (
        f"{day} is written by this job and no entry of {refreshed} hands it back"
    )


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
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
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
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")

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
def test_a_push_that_landed_first_try_reports_no_rebase(tmp_path: Path) -> None:
    """What the rebuild step reads. A clean push left the tree it was handed.

    Written explicitly rather than left unwritten. An output nobody wrote is the
    empty string, which is falsy and would skip the rebuild too - and which is
    indistinguishable from the script dying before it could answer.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
    settings, written = _reading_its_output(tmp_path, settings)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected" not in result.stdout
    assert _step_outputs(written) == {"rebased": "false"}


@requires_bash
def test_a_commit_that_staged_nothing_reports_no_rebase(tmp_path: Path) -> None:
    """Nothing was pushed, so there is no new tree for a later step to read."""
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, staged_paths)
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
    settings, written = _reading_its_output(tmp_path, settings)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert settings["NOTHING_STAGED_MESSAGE"] in result.stdout
    assert _step_outputs(written) == {"rebased": "false"}


@requires_bash
def test_a_push_that_lost_the_race_reports_the_rebase(tmp_path: Path) -> None:
    """The rebase replaced the checkout, so the build made before it is stale.

    This is what `digest.yml` keys the rebuild on. Run 33270983446 weighed one
    tree's pages against another tree's ceilings and failed a day that had
    already published; a rebase that reported nothing would do it again.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, "docs/unrelated.md", "racing\n")
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")
    settings, written = _reading_its_output(tmp_path, settings)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected, rebasing (attempt 1)" in result.stdout
    assert _step_outputs(written) == {"rebased": "true"}


@requires_bash
def test_the_commit_script_still_runs_where_no_step_output_exists(tmp_path: Path) -> None:
    """The guard on the write, and it is what lets one copy of the script serve both.

    `set -u` ends the run on an unset variable, so an unguarded write would kill
    every one of these tests and anybody running the script by hand. Only a
    workflow step has `$GITHUB_OUTPUT`.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings = _settled_in_the_clone(settings, _seed_ledger(staged_paths[0]), "header")

    assert "GITHUB_OUTPUT" not in {**env, **settings}, "the harness is what removes it"
    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "GITHUB_OUTPUT" not in result.stderr, "an unset variable must not end the script"
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == settings["COMMIT_MESSAGE"]


def test_every_way_out_of_the_commit_script_says_whether_it_rebased() -> None:
    """Three exits return zero and a fixture reaches two of them.

    The third - origin already holding everything a rebuild produced - needs a
    racing run that publishes the same items, and the value it reports decides
    whether the day's own gate reads a stale build. So the exits are checked
    where they are written instead.

    The argument-error exits above the function are deliberately out of scope.
    They fire before anything is committed, they fail the step, and a step that
    failed has already stopped the rebuild.
    """
    lines = read_text(COMMIT_SCRIPT).splitlines()
    defined = next(
        index for index, line in enumerate(lines) if line.startswith("report_rebased()")
    )

    exits = [
        index
        for index, line in enumerate(lines)
        if line.strip() in {"exit 0", "exit 1"} and index > defined
    ]
    assert len(exits) == 4, "three ways out with nothing wrong, and the one that gives up"
    for index in exits:
        before = [
            line.strip()
            for line in lines[max(0, index - 3) : index]
            if line.strip() and not line.strip().startswith("#")
        ]
        assert any("report_rebased" in line for line in before), (
            f"line {index + 1} leaves without saying whether the checkout was rewritten"
        )


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
    settings = _settled_in_the_clone(settings, f"{staged_paths[0]}/ledger.csv", "header")

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
    settings = _settled_in_the_clone(settings, f"{staged_paths[0]}/ledger.csv", "header")

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
    # This run: the visuals artifact unpacked a chart into the day's directory,
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

    published = _rows(_git(origin, env, "show", f"main:{ledger.published_relpath(date)}"))
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

    Run `32869125768` finished eight workers and a visual planner and then lost
    the whole day here. A chart was filed by its vertical and its ordinal within
    the day, and the ordinal was seeded by reading the day's directory - so two
    runs of one day, neither able to see what the other pushed, wrote
    `energy-01.svg`
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
    and every eval row names a model that never ran (Guardrail #6, Guardrail #10).
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
    silently the day config moves (Guardrail #6).

    Every download also names an immutable commit. A branch hands back whatever
    was uploaded last, so a measurement taken from one describes bytes nobody
    can fetch again (Guardrail #10).

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
    what lets the weights cache key in `work` and `visuals` name the file it holds
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
        for role in ("summarize", "visual_planner")
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

    assert keys["work"] != keys["visuals"], "one entry cannot hold two sets of weights"
def test_every_workflow_that_runs_llama_cpp_pins_the_same_build() -> None:
    """Production, the validation arm and the harness run one binary.

    A throughput number is only about the pipeline if the pipeline runs the
    build the number was measured on (Guardrail #10).
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

    `work` and `visuals` ran 31 lines of near-identical inline shell, 80.6 percent
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


def _digest_step(job_name: str, name: str) -> str:
    """One step body of a daily-run job, without the shell comments."""
    workflow = _load_workflows()["digest.yml"]
    return _uncommented(_script(_step(workflow, job_name, "name", name), name))


def _work_step(name: str) -> str:
    """One step body of the daily work job, without the shell comments."""
    return _digest_step("work", name)


def _sample_header() -> list[str]:
    """The columns the memory sampler writes, in the order it writes them."""
    script = read_text(SAMPLE_SCRIPT)
    header = re.search(rf"printf '([^']*)' > {re.escape(RSS_SAMPLE_FILE)}", script)
    assert header, f"{SAMPLE_SCRIPT.name} must printf a header row into {RSS_SAMPLE_FILE}"
    return header.group(1).removesuffix("\\n").split("\\t")


def test_both_model_server_jobs_sample_memory_with_the_one_shared_script() -> None:
    """Two copies of a sampler is one copy nobody looked at this week.

    It was a heredoc inside the work job's own step until 2026-09-12, which was
    fine while one job took the reading. The visuals job needs the same one -
    `peak_rss_bytes` is one of the four figures the visual planner has never
    had - and pasting fifty lines of shell into a second `run:` body is the
    thing `.github/scripts/` exists to stop (`CLAUDE.md` section 3). Moving it
    also puts it under `shellcheck`, which cannot read a `run:` body at all.

    Each job hands it the pid file its own server wrote, so a copy-paste that
    left the work job's name in the visuals step would sample a process that
    never existed and record nothing, silently.
    """
    assert SAMPLE_SCRIPT.is_file()
    assert read_text(SAMPLE_SCRIPT).startswith("#!/usr/bin/env bash\n")

    launched = {
        "work": (_work_step(SAMPLE_MEMORY_STEP), "llama-server.pid"),
        "visuals": (_digest_step("visuals", VISUALS_SAMPLE_MEMORY_STEP), "visual-planner.pid"),
    }
    for job_name, (script, pid_file) in launched.items():
        assert f"bash {SAMPLE_SCRIPT.relative_to(REPO_ROOT).as_posix()}" in script, (
            f"the {job_name} job must run the shared sampler"
        )
        assert f"cat {pid_file}" in script, (
            f"the {job_name} job must sample the server its own start step wrote"
        )
        assert "nohup" in script, f"the {job_name} sampler must outlive its own step"


def test_the_memory_sampler_and_both_its_readers_agree_on_the_columns() -> None:
    """One writer, two readers, and only one of them reads by name.

    `rss-samples.tsv` has two consumers and they disagree about what a column
    is. `RuntimeCountersRow` reads it by NAME, so a rename there costs one empty
    cell and the row reads as unknown. The operator print in the same job reads
    it by POSITION, so a column inserted anywhere but the end shifts every field
    after it and the job log reports `python_procs` - a count of three - as a
    peak in kilobytes. Nothing fails, and the number is off by six orders of
    magnitude.

    That is why the sampler appends a new column at the END of the row. Nothing
    held it there until this test.
    """
    header = _sample_header()
    assert header[0] == "ts", header
    assert len(header) == len(set(header)), f"a column name is written twice: {header}"

    for column in (runtime_counters._RSS_PEAK_COLUMN, runtime_counters._PYTHON_RSS_PEAK_COLUMN):
        assert column in header, f"the row reads {column} by name and the sampler stopped writing it"

    operator = _work_step(MEMORY_SUMMARY_STEP)
    assert RSS_SAMPLE_FILE in operator, f"{MEMORY_SUMMARY_STEP} must read {RSS_SAMPLE_FILE}"
    for field, column in sorted(RSS_SAMPLE_FIELDS.items()):
        assert f"${field}" in operator, f"{MEMORY_SUMMARY_STEP} no longer reads field {field}"
        assert header[field - 1] == column, (
            f"{MEMORY_SUMMARY_STEP} reads field {field} as {column}, "
            f"and the sampler now writes {header[field - 1]} there"
        )


def test_the_kernel_peak_is_written_before_the_row_that_reads_it() -> None:
    """A file written after the row is a file the row never saw.

    One step writes `memory-peak.txt` and then calls the stage that reads it, so
    the order inside that body is the whole promise. Reversed, the committed row
    carries an empty cell while the job log prints a number that reached nobody.
    The operator print below takes no second reading of its own, for the same
    reason: two readings of a live kernel counter would not agree.
    """
    counters = _work_step(COUNTERS_STEP)

    written = counters.find(f"> {MEMORY_PEAK_FILE}")
    read = counters.find(f"--memory-peak-file {MEMORY_PEAK_FILE}")
    assert written >= 0, f"{COUNTERS_STEP} must write {MEMORY_PEAK_FILE}"
    assert read >= 0, f"{COUNTERS_STEP} must pass {MEMORY_PEAK_FILE} to the stage"
    assert written < read, f"{COUNTERS_STEP} reads {MEMORY_PEAK_FILE} before it writes it"

    # Guarded, because no GitHub-hosted runner this project has measured has the
    # file. An unguarded read fails the step and costs the shard its whole row.
    assert f"[ -f {CGROUP_PEAK_PATH} ]" in counters, f"{COUNTERS_STEP} must guard the cgroup read"
    assert runtime_counters._CGROUP_PEAK_KEY in counters, "the row parses the key this step writes"

    # The other two files the row reads are ones this job wrote.
    assert f"--rss-samples-file {RSS_SAMPLE_FILE}" in counters
    assert f"--server-log {SERVER_LOG_FILE}" in counters

    operator = _work_step(MEMORY_SUMMARY_STEP)
    assert f"cat {MEMORY_PEAK_FILE}" in operator, "the print must read the file the row read"
    assert CGROUP_PEAK_PATH not in operator, "the print must not take a second kernel reading"


def test_the_sampler_names_every_python_process_it_counts() -> None:
    """A count of three cannot say which three, and here two of them are not ours.

    Over the four captures of run `2026-08-29-3` the peak lands at three python
    processes on every shard, and two of those three are already running at the
    first sample - taken before this job's own python starts. So the recorded
    python figure carries about 66 MB that belongs to something the job did not
    launch, and no cell on the row or the artifact says what. The roll-call is
    what turns the next run into the answer.

    Two things are asserted because two things can disagree. The roll-call has
    to be written by the SAME loop that produces the count, or it names a
    different set from the one the sum was taken over; and the operator print
    reads the roll-call by POSITION, so a column inserted anywhere but the end
    silently reports a process id as a size in kilobytes.
    """
    script = read_text(SAMPLE_SCRIPT)
    header = re.search(rf"printf '([^']*)' > {re.escape(PYTHON_PROCS_FILE)}", script)
    assert header, f"{SAMPLE_SCRIPT.name} must printf a header row into {PYTHON_PROCS_FILE}"
    columns = header.group(1).removesuffix("\\n").split("\\t")
    assert columns[0] == "ts", columns
    assert len(columns) == len(set(columns)), f"a column name is written twice: {columns}"

    # One loop, one filter. The count and the roll-call have to come off the
    # same pass over `/proc`, or the sum is over a set the roll-call never named.
    loop = re.search(r"for proc in /proc/\[0-9\]\*; do\n(.*?)\n *done\n", script, re.DOTALL)
    assert loop, f"{SAMPLE_SCRIPT.name} must walk /proc once per sample"
    body = loop.group(1)
    assert "python_n=$((python_n + 1))" in body, "the count must be taken inside that walk"
    assert f">> {PYTHON_PROCS_FILE}" in body, "the roll-call must be written inside that walk"
    assert body.count("python*)") == 1, "one filter decides what counts as python, not two"

    operator = _work_step(MEMORY_SUMMARY_STEP)
    assert PYTHON_PROCS_FILE in operator, f"{MEMORY_SUMMARY_STEP} must read {PYTHON_PROCS_FILE}"
    for field, column in sorted(PYTHON_PROCS_FIELDS.items()):
        assert f"${field}" in operator, f"{MEMORY_SUMMARY_STEP} no longer reads field {field}"
        assert columns[field - 1] == column, (
            f"{MEMORY_SUMMARY_STEP} reads field {field} as {column}, "
            f"and the sampler now writes {columns[field - 1]} there"
        )

    upload = _artifact_upload(_load_workflows()["digest.yml"], "work", "runtime-log-${{ matrix.shard }}")
    uploaded = str(_mapping(upload.get("with"), "runtime log upload").get("path"))
    assert PYTHON_PROCS_FILE in uploaded, "a roll-call nobody can download answers nothing"


def _log_summary_pattern(job_name: str, step_name: str, log_file: str) -> re.Pattern[str]:
    """The `grep -E` the cache summary step runs, as this test can run it too.

    Read out of the workflow rather than restated here. A pattern a test writes
    down for itself agrees with itself and proves nothing.
    """
    found = re.search(
        rf"grep -E '([^']*)' {re.escape(log_file)}", _digest_step(job_name, step_name)
    )
    assert found, f"{step_name} must grep {log_file} for the lines the runtime prints"
    return re.compile(found.group(1))


def test_the_cache_log_summary_matches_the_lines_the_runtime_actually_prints() -> None:
    """The pattern that found one line in forty, and the captures that say so.

    `^(srv|slot) ` matched nothing and had never matched anything. Every line
    llama-server prints opens with a timestamp and a level letter, so the tag is
    the third field:

        0.03.804.331 I srv    load_model: initializing, n_slots = 1, ...

    The step still printed something on every run, because the `n_ctx_slot`
    alternative beside it does match - which is why nobody noticed the other
    half was dead. Measured over the four committed captures: the old anchor
    found 1 line of 40 and it was the `n_ctx_slot` one, so 37 lines of prefix
    reuse went unprinted on every shard of every run.

    Driven from real captures rather than from hand-written text, because a
    pattern nobody ran against a real line is how this got here (Guardrail #7). The
    four strings in `RUNTIME_LOG_LINES` are checked as well, for the two field
    spellings no capture carries.
    """
    assert RUNTIME_LOG_CAPTURES, "the committed captures this pattern is checked against are gone"

    for job_name, (step_name, log_file) in sorted(RUNTIME_LOG_SUMMARY_STEPS.items()):
        pattern = _log_summary_pattern(job_name, step_name, log_file)

        for line in RUNTIME_LOG_LINES:
            assert pattern.search(line), f"{step_name} would not print {line!r}"

        for capture in RUNTIME_LOG_CAPTURES:
            lines = read_text(capture).splitlines()
            missed = [line for line in lines if not pattern.search(line)]
            unclaimed = [line for line in missed if f" {RUNTIME_LOG_UNCLAIMED_TAG} " in line]
            assert missed == unclaimed, (
                f"{step_name} would not print these lines of {capture.name}: {missed[:3]}"
            )
            assert len(lines) - len(missed) > len(lines) // 2, (
                f"{step_name} prints {len(lines) - len(missed)} of {len(lines)} lines "
                f"of {capture.name}, which is not a summary of the log"
            )


def test_the_prefix_reuse_fields_match_a_real_line_too() -> None:
    """The other half of the same step, and this half was never broken.

    `f_sim_best` and `f_keep` are greped as `<field> = <number>` and both do
    match: llama-server prints them on one line together, and the two `grep -oE`
    passes take one number each. Checked because the anchor above was not, and
    "the rest of the step is fine" was an assumption until now.
    """
    for job_name, (step_name, log_file) in sorted(RUNTIME_LOG_SUMMARY_STEPS.items()):
        script = _digest_step(job_name, step_name)
        found = re.search(rf'grep -oE "\$\{{field\}} ([^"]*)" {re.escape(log_file)}', script)
        assert found, f"{step_name} must grep each field as a name and a number"
        fields = re.search(r"for field in ([a-z_ ]+); do", script)
        assert fields, f"{step_name} must name the fields it loops over"

        for field in fields.group(1).split():
            pattern = re.compile(f"{field} {found.group(1)}")
            seen = sum(len(pattern.findall(read_text(path))) for path in RUNTIME_LOG_CAPTURES)
            assert seen, f"{step_name} finds no {field} in any committed capture"


def test_the_loopback_port_is_one_number_wherever_it_is_written() -> None:
    """A server on one port and a stage posting to another is every item failing.

    Every workflow that stands a llama-server up declares the port once at
    workflow level, `start-llama-server.sh` refuses to start without it, and
    `idhazh.llm.server` builds the address the stage posts to out of the same
    variable. Until 2026-09-09 the measurement harness was a fifth party: it
    starts its server from an inline python block rather than through the shared
    script, and it held its own `SERVER_PORT = 8080`. It reads the variable now,
    so the number is declared and never spelled.

    The declaration is the only place a runtime workflow may write the digits.
    Asserted line by line on a whole-token match rather than as "the file holds
    it once", so a hex digest that happens to carry `8080` inside it does not
    read as a second port.

    The Python side carries a fallback literal for a developer running the stage
    by hand, and that literal is the one a port move would leave behind: the
    workflows set the variable, so nothing in CI would ever reach the fallback
    and nothing would say it had gone stale.
    """
    expected = os.environ.get(LLAMA_PORT_ENV) or LLAMA_PORT_VALUE
    assert str(DEFAULT_PORT) == expected, (
        f"{LLAMA_PORT_ENV} is {expected} and idhazh.llm.server answers {DEFAULT_PORT}"
    )
    address = LLAMA_PORT_READ.replace("${" + LLAMA_PORT_ENV + "}", expected)
    assert DEFAULT_ENDPOINT.startswith(f"{address}/"), (
        f"the stage posts to {DEFAULT_ENDPOINT} and the workflow probes {address}"
    )

    declaring = set()
    for filename, workflow in sorted(_load_workflows().items()):
        env = workflow.get("env")
        declared = env.get(LLAMA_PORT_ENV) if isinstance(env, dict) else None
        if declared is not None:
            declaring.add(filename)
            assert str(declared) == LLAMA_PORT_VALUE, (
                f"{filename} declares {LLAMA_PORT_ENV}={declared}, "
                f"and the fallback in idhazh.llm.server is {LLAMA_PORT_VALUE}"
            )
        for text in _strings(workflow):
            assert f"127.0.0.1:{LLAMA_PORT_VALUE}" not in text, (
                f"{filename} writes the port into an address instead of reading it back"
            )
    assert declaring == set(LLAMA_RUNTIME_WORKFLOWS), (
        "every workflow that starts a llama-server declares the port and nothing else does"
    )

    for filename in sorted(LLAMA_RUNTIME_WORKFLOWS):
        for line in read_text(WORKFLOWS_DIR / filename).splitlines():
            if re.search(rf"\b{LLAMA_PORT_VALUE}\b", line):
                assert LLAMA_PORT_ENV in line, (
                    f"{filename} spells the port at `{line.strip()}` rather than "
                    f"reading {LLAMA_PORT_ENV} back"
                )

    assert f'"${{{LLAMA_PORT_ENV}:?' in read_text(START_SERVER_SCRIPT), (
        f"{START_SERVER_SCRIPT.name} must refuse to start without {LLAMA_PORT_ENV}"
    )
    # The one starter that does not go through the shared script. It sweeps a
    # setting over per-candidate config roots and holds the process object to
    # sample its memory, neither of which the script can do - so it keeps its own
    # start sequence and reads the port the workflow declared.
    assert f'SERVER_PORT = int(os.environ["{LLAMA_PORT_ENV}"])' in read_text(
        WORKFLOWS_DIR / "measure.yml"
    ), f"the measurement harness must read {LLAMA_PORT_ENV} rather than hold a port"


def test_every_reader_of_a_server_log_reads_the_one_the_start_call_wrote() -> None:
    """One name, given once on a command line, read by five later steps.

    The start script takes the log stem as its second argument, so the filename
    exists in the workflow exactly once as an argument and four more times as a
    literal in steps that read it. Every one of those readers ends `|| true` or
    `if: always()`, so a stem that no longer matches costs the job its runtime
    identity, its failure tail and its whole prompt-cache summary, and fails
    nothing. `visual-planner` and `visual_planner` are one character apart and
    the second is the role name in the same command.
    """
    workflow = _load_workflows()["digest.yml"]
    assert set(RUNTIME_IDENTITY_JOBS) <= set(_mapping(workflow.get("jobs"), "jobs")), (
        "a job named here no longer exists in digest.yml"
    )
    for job_name, (log_file, weights_output) in sorted(RUNTIME_IDENTITY_JOBS.items()):
        start_step, _ = SERVER_STARTERS[("digest.yml", job_name)]
        call = re.search(r"start-llama-server\.sh (\S+) (\S+)", _digest_step(job_name, start_step))
        assert call, f"{job_name} must start its server through the shared script"
        assert f"{call.group(2)}.log" == log_file, (
            f"{job_name} starts a server logging to {call.group(2)}.log "
            f"and its readers read {log_file}"
        )

        identity = _digest_step(job_name, RUNTIME_IDENTITY_STEP)
        assert log_file in identity, f"{RUNTIME_IDENTITY_STEP} in {job_name} must read {log_file}"
        assert f"needs.plan.outputs.{weights_output}" in identity, (
            f"{RUNTIME_IDENTITY_STEP} in {job_name} must name the weights it ran"
        )
        assert "sha256sum backend/bin/llama-server" in identity, (
            f"{RUNTIME_IDENTITY_STEP} in {job_name} must name the binary it ran"
        )

        summary_step, summary_log = RUNTIME_LOG_SUMMARY_STEPS[job_name]
        assert summary_log == log_file, (
            f"{summary_step} reads {summary_log} and {job_name} writes {log_file}"
        )
        assert log_file in _digest_step(job_name, summary_step), f"{summary_step} must read {log_file}"


def test_the_counters_step_and_the_row_agree_on_what_it_reads() -> None:
    """Three readings, two of them taken in different steps an hour apart.

    The metrics body is written by one line of the step and read by two more, so
    a rename in any one of them leaves the row's counter cells empty and prints
    nothing that says why. The two series are named again in the contract that
    parses them, in another language, and llama.cpp has renamed a counter
    before. And `/proc/stat` is read at both ends of the job by two separate
    steps: a reading of the per-cpu line at one end and the aggregate at the
    other would make `cpu_busy_pct` a number with no meaning, and nothing would
    fail.
    """
    counters = _work_step(COUNTERS_STEP)
    assert f"-o {METRICS_FILE}" in counters, f"{COUNTERS_STEP} must write {METRICS_FILE}"
    assert f'"{METRICS_ENDPOINT}"' in counters, f"{COUNTERS_STEP} must scrape {METRICS_ENDPOINT}"
    assert f"--counters-file {METRICS_FILE}" in counters, "the stage must read the file curl wrote"
    for series in METRICS_SERIES:
        assert series in counters, f"{COUNTERS_STEP} stopped naming {series}"
        assert series in runtime_counters.SERIES, f"the row no longer parses {series}"

    clock = _work_step(CPU_STAT_STEP)
    assert clock.count(CPU_STAT_READING) == 1, f"{CPU_STAT_STEP} must read /proc/stat once"
    assert counters.count(CPU_STAT_READING) == 1, f"{COUNTERS_STEP} must read /proc/stat once"
    assert "--cpu-stat-at-start" in counters and "--cpu-stat-at-end" in counters, (
        "both readings must reach the row, or the difference between them is not taken"
    )
    assert runtime_counters._CPU_FIELDS[0] == "user", (
        "the row parses the aggregate cpu line, which is what both steps read"
    )


def test_a_counters_row_that_cannot_say_which_job_wrote_it_is_refused() -> None:
    """The Oracle for row #P4. A row with no job name proves nothing.

    Two jobs of the daily run stand a llama-server up and they serve different
    weights - `work` the summarizer at Qwen3.5-9B, `visuals` the planner at
    Qwen3-4B - and both spell shard 0 of the same run. So `(date, run_id,
    shard)` names one record and describes two servers, and a reader pooling
    them reports a rate that belongs to no model.

    Driven from a two-row fixture rather than from `state/runtime-counters.csv`,
    which a run appends to five times a day (Guardrail #12). The fixture also carries
    a case the committed ledger cannot: until this lands, every row in it came
    from `work`.

    Three assertions, because three things can go wrong. The reader has to
    separate the rows BY JOB, not by shard - they share a shard index. Each side
    has to carry a decode rate, or the fixture proves the separation and nothing
    about whether either row is worth having. And the parser has to REFUSE a row
    whose cell is empty rather than default it: a defaulted blank would file the
    planner's numbers under the summarizer's name and every gate would stay
    green.
    """
    with COUNTERS_FIXTURE.open(encoding="utf-8", newline="") as handle:
        raw = list(csv.DictReader(handle))
    rows = [runtime_counters.RuntimeCountersRow.from_csv_row(row) for row in raw]

    by_job = {row.job: row for row in rows}
    assert set(by_job) == set(COUNTERS_JOBS.values()), "the reader must separate them by job"
    assert len({(row.date, row.run_id, row.shard) for row in rows}) == 1, (
        "the fixture has to share a shard index, or it proves the wrong thing"
    )
    assert len({(row.date, row.run_id, row.job, row.shard) for row in rows}) == len(rows), (
        "the job is what tells the two apart, and nothing else on the row does"
    )
    assert tuple(ledger.RUNTIME_COUNTERS_KEY) == ("date", "run_id", "job", "shard"), (
        "the ledger key must hold the job, or the second row is dropped as a repeat"
    )

    for job_name, row in by_job.items():
        assert row.tokens_predicted_total, f"the {job_name} row carries no decoded tokens"
        assert row.tokens_predicted_seconds_total, f"the {job_name} row carries no decode seconds"
        rate = row.tokens_predicted_total / row.tokens_predicted_seconds_total
        assert rate > 0, f"the {job_name} row has no decode rate"

    nameless = {name: value for name, value in raw[0].items() if name != "job"}
    with pytest.raises(KeyError):
        runtime_counters.RuntimeCountersRow.from_csv_row(nameless)
    with pytest.raises(ValidationError):
        runtime_counters.RuntimeCountersRow.from_csv_row({**raw[0], "job": ""})

    # And the other half of `CLAUDE.md` section 11: a row written before the
    # column existed still validates. Proved by removing the key from a payload,
    # which cannot age out the way a count of unmigrated rows would.
    older = {
        name: value
        for name, value in rows[0].model_dump(mode="json").items()
        if name != "job"
    }
    assert runtime_counters.RuntimeCountersRow.model_validate(older).job == (
        runtime_counters.WORK_JOB
    )


def test_the_visuals_job_writes_a_counters_row_of_its_own() -> None:
    """The reading row #P4 exists to take, held where a workflow that drops it reds.

    `measurements.md` records the 4B at 13.00 +/- 0.03 tok/s on a `llama-bench`
    run, and a bench run produces no `prompt_tokens_cached_total`, no
    `peak_rss_bytes`, no `prompt_seconds_total` and no `n_ctx_configured`. Those
    four are what the labelling rows of plan 23 are priced against, and until
    this step existed every committed counters row came from `work`.

    The three inputs are asserted rather than the output, because the output is
    a dispatched run. Each of them is a way the step can produce a row that
    looks fine and says nothing: no clock stamp and `job_seconds` and
    `cpu_busy_pct` are empty; the wrong server log and `n_ctx_configured` is
    empty; no commit and the row never leaves the runner.
    """
    workflow = _load_workflows()["digest.yml"]
    names = [step.get("name") for step in _steps(workflow, "visuals")]

    for step_name in (
        VISUALS_CLOCK_STEP,
        VISUALS_SAMPLE_MEMORY_STEP,
        VISUALS_COUNTERS_STEP,
        COMMIT_STEPS["visuals"],
    ):
        assert step_name in names, f"the visuals job must carry {step_name}"

    # The clock is stamped before the checkout, so it covers the cache restore
    # and the weight load as well as the model time.
    assert names.index(VISUALS_CLOCK_STEP) == 0, "the clock must cover the whole job"
    assert names.index(VISUALS_SAMPLE_MEMORY_STEP) < names.index(VISUALS_COUNTERS_STEP)
    assert names.index(VISUALS_COUNTERS_STEP) < names.index(COMMIT_STEPS["visuals"]), (
        "the commit has to run after the row it commits is written"
    )

    clock = _digest_step("visuals", VISUALS_CLOCK_STEP)
    for variable in CLOCK_VARIABLES:
        assert variable in clock, f"{VISUALS_CLOCK_STEP} must stamp {variable}"
    assert clock.count(CPU_STAT_READING) == 1, f"{VISUALS_CLOCK_STEP} must read /proc/stat once"

    counters = _digest_step("visuals", VISUALS_COUNTERS_STEP)
    assert counters.count(CPU_STAT_READING) == 1
    assert f"--server-log {VISUALS_SERVER_LOG_FILE}" in counters, (
        "the window one sequence got is read off the planner's own log, not the summarizer's"
    )
    assert f"--rss-samples-file {RSS_SAMPLE_FILE}" in counters
    assert f"--memory-peak-file {MEMORY_PEAK_FILE}" in counters
    assert f"--counters-file {METRICS_FILE}" in counters


@pytest.mark.parametrize("job_name", sorted(COUNTERS_JOBS))
def test_every_counters_step_says_which_job_it_is(job_name: str) -> None:
    """A default is not a statement, and both callers have to make one.

    `--job` defaults to `work`, which is what lets a row written before the
    column existed still validate. That same default is why the visuals step has
    to name its own value out loud: a copy-paste that dropped the flag would
    file the planner's numbers under the summarizer's name, the ledger would
    accept them, and the console would pool two models into one rate.
    """
    step_name = {"work": COUNTERS_STEP, "visuals": VISUALS_COUNTERS_STEP}[job_name]
    script = _digest_step(job_name, step_name)
    assert COUNTERS_COMMAND in script, f"{step_name} must run {COUNTERS_COMMAND}"
    assert f"{COUNTERS_JOB_FLAG} {COUNTERS_JOBS[job_name]}" in script, (
        f"{step_name} must say it is the {job_name} job"
    )
    for other, value in COUNTERS_JOBS.items():
        if other != job_name:
            assert f"{COUNTERS_JOB_FLAG} {value}" not in script


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
    under a model that never ran (Guardrail #10)."""
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


def test_the_whole_day_check_gets_its_own_build_and_never_the_canary() -> None:
    """`frontend/build` is one directory, and two builds write it.

    `whole-day.spec.ts` refuses to load against a tree that is not the published
    site, which is the guard that makes it worth running at all. Sharing a job
    with the canary build would mean either running it against the thing it was
    written to catch, or ordering two builds inside one job and hoping nobody
    reorders them. Its own job cannot be got wrong that way.
    """
    workflow = _load_workflows()["ci.yml"]
    steps = _steps(workflow, "whole-day")
    scripts = [
        _script(step, "ci.yml/whole-day") for step in steps if isinstance(step.get("run"), str)
    ]
    joined = "\n".join(scripts)

    assert "build:canary" not in joined, "the canary must never reach this job's build directory"
    assert "build_canary_day" not in joined
    builds = [index for index, text in enumerate(scripts) if "npm run build" in text]
    checks = [index for index, text in enumerate(scripts) if "test:whole-day" in text]
    assert builds and checks, "the job builds the real site and then looks at it"
    assert max(builds) < min(checks), "the build has to land before the spec opens the tree"


def test_the_whole_day_check_is_bought_by_the_same_change_the_browser_half_is() -> None:
    """One allow-list, because it is one question about the published page.

    A second list would drift from the first, and the drift is silent: the
    change that needed this check is exactly the change that needed the browser
    half, and a job nobody buys is a check that stopped existing.
    """
    workflow = _load_workflows()["ci.yml"]

    assert _job(workflow, "whole-day")["if"] == _job(workflow, "browser")["if"]
    assert _job(workflow, "whole-day")["needs"] == "scope"


def _browser_install_jobs(
    workflows: Mapping[str, dict[str, object]],
) -> dict[tuple[str, str], list[dict[str, object]]]:
    """Every job in the repository that installs a browser, found and not listed.

    Found, because the hazard is the job nobody remembered: a new job that
    downloads 300 MB of Chromium on every run costs the same whether or not
    anybody added it to a list here.
    """
    found: dict[tuple[str, str], list[dict[str, object]]] = {}
    for filename, workflow in workflows.items():
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            steps = _steps(workflow, job_name)
            if any(
                isinstance(script := step.get("run"), str) and "playwright install" in script
                for step in steps
            ):
                found[(filename, job_name)] = steps
    return found


def test_every_job_that_installs_a_browser_restores_it_from_one_shared_key() -> None:
    """The browser bytes are restored, and the two jobs share one entry.

    Measured on run 34678620051, 2026-09-12: the download is 184.3 MB of
    Chromium, 114.7 MB of headless shell and 2.3 MB of FFmpeg, about 9 s of a
    23 s step, paid twice a run because `browser` and `whole-day` each need a
    browser. The other 14 s is the `--with-deps` apt-get, which a cache cannot
    hold - so the install step stays, and stays unconditional.

    Two keys would be the quiet failure rather than a loud one. The repository
    cache ceiling is 10 GB (Guardrail #2) and the two weights entries held 7.5 GB of
    it on 2026-09-12, so a second browser entry is not headroom this has. One
    key is also the only way either job can hit: they start together, so
    neither can ever warm the other.
    """
    workflows = _load_workflows()
    jobs = _browser_install_jobs(workflows)
    assert jobs, "the repository installs a browser somewhere, or this test is dead"

    keys: set[str] = set()
    for (filename, job_name), steps in jobs.items():
        where = f"{filename}/{job_name}"
        restores = [
            step for step in steps if str(step.get("uses", "")).startswith("actions/cache@")
        ]
        assert len(restores) == 1, f"{where}: one restore for the browser bytes, not {len(restores)}"
        with_block = _mapping(restores[0].get("with"), f"{where} cache 'with'")
        assert with_block.get("path") == BROWSER_CACHE_PATH, (
            f"{where}: cache the directory Playwright unpacks into"
        )
        key = with_block.get("key")
        assert isinstance(key, str), f"{where}: the cache key must be a string"
        keys.add(key)

        positions = {
            index: str(step.get("run", "")) for index, step in enumerate(steps)
        }
        install = min(
            index for index, script in positions.items() if "playwright install" in script
        )
        assert steps.index(restores[0]) < install, f"{where}: restore before the download"

    assert len(keys) == 1, f"one key for every browser job, found {sorted(keys)}"
    key = keys.pop()
    assert "hashFiles(" not in key, (
        "a lockfile hash moves when any dependency moves, so an unrelated bump "
        "would refetch 300 MB of browser for nothing"
    )
    source_file, source_job, source_step, source_output = BROWSER_VERSION_SOURCE
    assert f"needs.{source_job}.outputs.{source_output}" in key, (
        f"the key reads the version {source_file}/{source_job} published"
    )
    outputs = _mapping(
        _job(workflows[source_file], source_job).get("outputs"),
        f"{source_file}/{source_job} outputs",
    )
    assert outputs.get(source_output) == f"${{{{ steps.{source_step}.outputs.{source_output} }}}}"


def test_the_browser_cache_key_names_a_version_the_lockfile_really_holds() -> None:
    """The reader is run against the committed lockfile, not just read.

    This is the failure that has no symptom. A renamed package path or a moved
    lockfile makes the expression evaluate to nothing, the key becomes a
    constant prefix, and every run from then on restores an entry that was
    saved under it once - or misses forever. Nothing goes red; CI just gets
    slower and stays slower. So the test resolves the same path the step
    resolves and asserts it lands on a version.
    """
    source_file, source_job, source_step, source_output = BROWSER_VERSION_SOURCE
    step = _step(_load_workflows()[source_file], source_job, "id", source_step)
    script = _script(step, f"{source_file}/{source_job}/{source_step}")

    read = re.search(
        r"require\('(?P<lockfile>[^']+)'\)\.packages\['(?P<package>[^']+)'\]\.version",
        script,
    )
    assert read is not None, "the step reads one package's version out of one lockfile"
    lockfile = REPO_ROOT / read.group("lockfile")
    assert lockfile.is_file(), f"the step reads {read.group('lockfile')}, which is not there"
    packages = json.loads(lockfile.read_text(encoding="utf-8"))["packages"]
    assert read.group("package") in packages, (
        f"{read.group('package')} is not in {read.group('lockfile')}"
    )
    version = packages[read.group("package")]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"the pinned browser build reads as {version!r}, which the step would refuse"
    )

    assert f'echo "{source_output}=$version" >> "$GITHUB_OUTPUT"' in script
    assert r"^[0-9]+\.[0-9]+\.[0-9]+$" in script, (
        "the value is substituted into a cache key, so its shape is checked here first"
    )
    assert "exit 1" in script, "an unreadable version fails the step rather than keying on it"