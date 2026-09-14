"""Workflow readers, git harnesses and script drivers every workflow module needs."""

from __future__ import annotations

import ast
import copy
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
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import CONFIG_DIR, FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import publish_console
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision, VisualKind, VisualState

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
    ("measure.yml", "candidate_file"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "candidate_id"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "candidate_quantisation"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "candidate_repo"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "candidate_revision"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "candidate_sha256"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "corpus_links"): "^[1-9][0-9]{0,4}$",
    ("measure.yml", "runtime_candidate"): DISPATCH_CHOICE,
    ("measure.yml", "runtime_threads"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "runtime_threads_batch"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "budget_samples"): "^[1-9][0-9]{0,4}$",
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
        '["summarize"]["sha256"]',
    ),
    ("measure.yml", "runtime"): (
        "Fetch runtime and weights",
        "Verify the weights",
        "Measure runtime candidate",
        "${{ needs.models.outputs.candidate_sha256 }}",
    ),
    ("measure.yml", "batched"): (
        "Download the summarizer weights",
        "Verify the weights",
        "Benchmark parallel decode",
        '["summarize"]["sha256"]',
    ),
    ("measure.yml", "budgets"): (
        "Fetch runtime and weights",
        "Verify the weights",
        "Start the tokenizer",
        "${{ needs.models.outputs.candidate_sha256 }}",
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
WEIGHTS_CACHE_ROLES: Final = {"work": "summarize"}

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

MEASUREMENT_TARGETS: Final = frozenset({"bench", "image", "corpus", "batched", "budgets"})

#: The bench is one target and two jobs: raw prefill and decode first, then a
#: real server doing real work. The raw arm saves the weights cache entry and
#: the server arm restores it, so a key that differs by one character is a
#: second multi-gigabyte download inside one dispatch (Guardrail #2).
BENCH_TARGET: Final = "bench"

BENCH_RAW_JOB: Final = "llm"

BENCH_SERVER_JOB: Final = "runtime"

BENCH_CACHE_KEY: Final = (
    "bench-${{ needs.models.outputs.candidate_sha256 }}-${{ env.LLAMA_CPP_BUILD }}"
)

BENCH_ARTIFACTS: Final = {
    BENCH_RAW_JOB: "bench-raw",
    BENCH_SERVER_JOB: "bench-server-${{ inputs.runtime_candidate }}",
}

#: Ninety days, and the number is here rather than only in the file so moving it
#: is a decision somebody writes down. The sweep used to keep seven, which is
#: shorter than the gap between benching a model and adopting it - and an
#: expired artifact is a five-hour job run a second time for numbers that were
#: already measured.
BENCH_RETENTION_DAYS: Final = 90

#: What the bench builds instead of editing the committed config, and the step
#: that builds it.
BENCH_CANDIDATE_CONFIG: Final = "backend/var/candidate-config"

BENCH_CONFIG_STEP: Final = "Build the candidate config"

BENCH_EMIT_STEP: Final = "Emit the dossier body"

#: Row #13a's arm. Its own target because retaking three token counts is minutes
#: and the bench is hours, and nobody should have to spend the second to get the
#: first. It shares the bench's weights cache key, so the bytes are paid for once.
BUDGETS_JOB: Final = "budgets"

BUDGETS_EMIT_STEP: Final = "Retake the budgets a vocabulary sizes"

# Every job that stands up llama-server, and the log that job writes. Both must
# name the host, the binary and the weights: a shard's throughput is decided by
# the host it drew, and a number that cannot name the bytes that produced it is
# not a measurement (Guardrail #10).
RUNTIME_IDENTITY_JOBS: Final = {
    "work": ("llama-server.log", "summarize_file"),
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
    ("measure.yml", "runtime"): ("Measure runtime candidate", None),
    ("measure.yml", "budgets"): ("Start the tokenizer", "backend/var/candidate-config"),
    ("validate.yml", "qualify"): ("Start the candidate", "backend/var/candidate-config"),
}

RUNTIME_LOG_SUMMARY_STEPS: Final = {
    "work": ("Prompt cache log summary", "llama-server.log"),
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
    # The plan job records one verdict per feed per run. A second attempt at one
    # plan writes its own verdict for every feed, against a checkout that cannot
    # see the first attempt's push, so the union keeps both and one bad run reads
    # as two failures.
    "plan": COMMIT_BASE_ENV | {"DROP_REPEATED_ROWS_COMMAND"},
    # Its filters read a checkout frozen at the commit this run was triggered at,
    # so a second attempt cannot see the first attempt's pushed rows and the
    # union keeps both - which is what the post-merge pass is for.
    "work": COMMIT_BASE_ENV | {"DROP_REPEATED_ROWS_COMMAND"},
    "assemble": COMMIT_BASE_ENV
    | {"REFRESH_PATHS", "REGENERATE_COMMAND", "DROP_RACED_ASSETS_COMMAND"},
    "fold": COMMIT_BASE_ENV,
}

COMMIT_STAGED_PATHS: Final = {
    "plan": [
        "state/seen",
        "state/feed-health",
        "state/feed-retirements.csv",
        "state/counterfactual-scores",
    ],
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

# The step that lays out this run's visual decisions for a person to look at. It
# runs in assemble because that is the only job holding every population at
# once, and last because nothing on the publish path reads what it writes.
REVIEW_STEP: Final = "Build the day's review tree"

REVIEW_COMMAND: Final = "python backend/utilities/review_queue.py"

REVIEW_ARTIFACT: Final = "review"

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

# The flag that says which job a row came from. Only `work` stands a server up
# now, and the flag stays because the committed ledger holds rows from the
# retired visuals job: a row that cannot say which job wrote it proves nothing,
# and the two jobs both spelled shard 0 of the same run.
COUNTERS_JOB_FLAG: Final = "--job"

COUNTERS_JOBS: Final = {"work": "work"}

# The two-row fixture the reader is driven over: one `work` row and one
# `visuals` row, sharing a date, a run and a shard index. Fixed in size, and it
# carries a case the committed ledger has never held (Guardrail #12). The
# `visuals` row is history - plan 11 row #6 retired that job - and the reader
# still has to read it back.
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
# directory is never in this list: the `shard-visuals-*` artifacts unpack this
# run's rendered charts into it, and no producer in the assemble job can make
# those again, so the two payload files are named one at a time.
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

# One rendered chart, as a work shard leaves it: an SVG in the day's directory
# and a decision payload saying where it landed. The name is the item's own id,
# so a path both runs hold is that one item rendered twice.
RACED_ITEM_ID: Final = "energy-0000000001"

RACED_ASSET: Final = f"digest/{SUBSTITUTED_DATE.replace('-', '/')}/{RACED_ITEM_ID}.json"

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

CONFIG_FILE_NAME: Final = "idhazh.json"

#: The key in `config/idhazh.json` that names the active model's own file. A
#: program that indexes it is no longer reading the pointer file from that
#: point on, so this is what tells the two documents apart.
MODELS_POINTER_KEY: Final = "models_file"

#: What this file calls the document the pointer names, in a key-path result.
MODELS_DOCUMENT: Final = "models"

def _inline_programs(script: str) -> list[str]:
    """Every Python program a shell step carries, heredoc or `-c` one-liner.

    Both spellings index the config, so both are in scope. A step that carries
    neither contributes nothing and is not an error.
    """
    programs: list[str] = re.findall(
        r"<<'PY'[^\n]*\n(.*?)\nPY(?:\n|$)", script, flags=re.DOTALL
    )
    programs.extend(re.findall(r"python3?\s+-c\s+'([^']*)'", script))
    return programs

def _reads_the_config_file(node: ast.AST, aliases: frozenset[str]) -> bool:
    return any(
        (
            isinstance(inner, ast.Constant)
            and isinstance(inner.value, str)
            and inner.value.endswith(CONFIG_FILE_NAME)
        )
        or (isinstance(inner, ast.Name) and inner.id in aliases)
        for inner in ast.walk(node)
    )

def _parses_json(node: ast.AST) -> bool:
    return any(
        isinstance(inner, ast.Attribute)
        and inner.attr in {"load", "loads"}
        and isinstance(inner.value, ast.Name)
        and inner.value.id == "json"
        for inner in ast.walk(node)
    )

def _reads_the_environment(node: ast.AST) -> bool:
    """`os.environ[...]` or `os.environ.get(...)` anywhere in an expression."""
    return any(
        isinstance(inner, ast.Attribute)
        and inner.attr == "environ"
        and isinstance(inner.value, ast.Name)
        and inner.value.id == "os"
        for inner in ast.walk(node)
    )

def _names(node: ast.AST, name: str) -> bool:
    """Whether an expression reads a given name anywhere inside itself."""
    return any(
        isinstance(inner, ast.Name) and inner.id == name for inner in ast.walk(node)
    )

def _own_nodes(scope: ast.AST) -> list[ast.AST]:
    """Every node a scope owns, without descending into a nested function.

    Name tracking has to stop at a function boundary. The runtime sweep binds a
    local `path` to its copy of the config, and the module around it binds the
    same name to each summary file it reads; merging the two would resolve one
    against the other.
    """
    owned: list[ast.AST] = []
    stack: list[ast.AST] = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        owned.append(node)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        stack.extend(ast.iter_child_nodes(node))
    return owned

def _committed_models() -> dict[str, Any]:
    """The active model's file, found the way the workflows find it.

    Never by filename. A workflow follows the pointer, so a test that named the
    file would keep passing on the day the pointer moved and the workflow read
    something else.
    """
    pointer = json.loads(read_text(CONFIG_DIR / CONFIG_FILE_NAME))[MODELS_POINTER_KEY]
    payload: dict[str, Any] = json.loads(read_text(CONFIG_DIR / pointer))
    return payload

def _follows_the_pointer(node: ast.AST, tainted: frozenset[str]) -> bool:
    """Does this expression reach the model file rather than the pointer file?

    The whole model left `config/idhazh.json` on 2026-09-14, so a program that
    reads it opens two files: the pointer, and whatever the pointer names. A key
    path resolved against the wrong one of those two is a guard that passes on a
    key nothing carries, which is worse than no guard.

    Reaching `models_file` once taints the name it is bound to, and a name built
    out of a tainted name is tainted too - which is how the two-step form the
    workflows use (build the path, then open it) is followed.
    """
    return any(
        (
            isinstance(inner, ast.Subscript)
            and isinstance(inner.slice, ast.Constant)
            and inner.slice.value == MODELS_POINTER_KEY
        )
        or (isinstance(inner, ast.Name) and inner.id in tainted)
        for inner in ast.walk(node)
    )

def _config_mapping_names(nodes: list[ast.AST]) -> tuple[frozenset[str], frozenset[str]]:
    """The names one scope binds to each of the two committed config documents.

    Returns the names holding a parsed `idhazh.json`, and the names holding the
    model file it points at.

    Two spellings reach a file: a direct `json.load(open(...))`, and a copy of
    `config/` re-read through a path built earlier. Keying on the filename
    rather than on one call shape is what lets this see the copy the runtime
    sweep writes. The scan repeats until it stops growing, so a path built two
    statements before it is read is still recognised.
    """
    aliases: set[str] = set()
    mappings: set[str] = set()
    models: set[str] = set()
    tainted: set[str] = set()
    while True:
        before = (frozenset(aliases), frozenset(mappings), frozenset(models))
        for node in nodes:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            reachable = frozenset(aliases | mappings | models)
            if not _reads_the_config_file(node.value, reachable):
                continue
            follows = _follows_the_pointer(node.value, frozenset(tainted))
            if follows:
                tainted.add(target.id)
            if isinstance(node.value, ast.Call) and _parses_json(node.value):
                (models if follows else mappings).add(target.id)
            else:
                aliases.add(target.id)
        if before == (frozenset(aliases), frozenset(mappings), frozenset(models)):
            return frozenset(mappings), frozenset(models)

def _config_key_paths(program: str) -> list[tuple[str, tuple[str, ...]]]:
    """Every literal key path an inline program indexes, and which document on.

    A chain nested inside a longer one is skipped, because resolving the longest
    chain resolves every prefix of it. A key that is not a literal string cannot
    be resolved here and is left to the step itself.
    """
    tree = ast.parse(program)
    scopes: list[ast.AST] = [tree]
    scopes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    )
    found: list[tuple[str, tuple[str, ...]]] = []
    for scope in scopes:
        nodes = _own_nodes(scope)
        mappings, models = _config_mapping_names(nodes)
        nested = {id(node.value) for node in nodes if isinstance(node, ast.Subscript)}
        for node in nodes:
            if not isinstance(node, ast.Subscript) or id(node) in nested:
                continue
            keys: list[str] = []
            current: ast.expr = node
            while isinstance(current, ast.Subscript):
                key = current.slice
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    keys.clear()
                    break
                keys.append(key.value)
                current = current.value
            if not keys:
                continue
            if isinstance(current, ast.Name) and current.id in models:
                found.append((MODELS_DOCUMENT, tuple(reversed(keys))))
            elif (isinstance(current, ast.Name) and current.id in mappings) or (
                isinstance(current, ast.Call)
                and _parses_json(current)
                and _reads_the_config_file(current, frozenset())
            ):
                found.append((CONFIG_FILE_NAME, tuple(reversed(keys))))
    return found

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
    """One published visual, exactly as the work job's artifact leaves it.

    A marks file under the day's directory and a real `VisualDecision` beside the
    run's items saying where it landed. `body` is what makes two compiles of one
    item differ, which is the only case that can now put two adds on one path -
    identical bytes are the case git resolves on its own.
    """
    _write(repo / "frontend" / "public" / relpath, f'{{"item_id": "{body or item_id}"}}\n')
    decision = VisualDecision(
        version=VisualDecision.schema_version(),
        item_id=item_id,
        url_key=hashlib.sha256(item_id.encode("ascii")).hexdigest(),
        kind=VisualKind.CHART,
        spec='{"marks": []}',
        data_path=relpath,
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
