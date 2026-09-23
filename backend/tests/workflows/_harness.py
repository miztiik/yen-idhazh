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
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh import ledger, paths
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision, VisualKind, VisualState
from idhazh.telemetry.publish import series

WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"

SCRIPTS_DIR: Final = REPO_ROOT / ".github" / "scripts"

ACTIONS_DIR: Final = REPO_ROOT / ".github" / "actions"

#: How a workflow names an action that lives in this repository. A `./` path
#: resolves to the tree the run checked out, so what it runs is already under
#: test - but it sits outside `.github/workflows/`, which is where every oracle
#: here starts reading.
LOCAL_ACTION_PREFIX: Final = "./"

#: The five steps that stand a model server up, as one action. `digest.yml` and
#: `llm-council.yml` ran them as two copies that had to be edited together, and
#: the cache key was the half that drifted. Named here so the tests ask which
#: jobs call it rather than which jobs spell it.
MODEL_SERVER_ACTION: Final = "./.github/actions/model-server"
#: The five steps that action owns, in the order it runs them. A caller that
#: still spells one of these names owns a second copy of it, which is what the
#: extraction removed.
MODEL_SERVER_STEPS: Final = (
    "Cache weights and runtime",
    "Fetch runtime and weights",
    "Verify the weights",
    "Start the model",
    "Check model health",
)

EXPECTED_WORKFLOWS: Final = {
    "backfill.yml": ("Vector backfill", frozenset({"workflow_dispatch"})),
    "ci.yml": ("CI", frozenset({"pull_request", "push", "workflow_dispatch"})),
    "digest.yml": ("Content refresh", frozenset({"schedule", "workflow_dispatch"})),
    "drift.yml": ("Drift review", frozenset({"schedule", "workflow_dispatch"})),
    "idhazh-pipeline-tests.yaml": ("Pipeline tests", frozenset({"workflow_dispatch"})),
    "llm-council.yml": ("LLM-COUNCIL", frozenset({"schedule", "workflow_dispatch"})),
    "measure.yml": ("Measurements", frozenset({"workflow_dispatch"})),
    "pages.yml": (
        "Pages publication",
        frozenset({"workflow_run", "workflow_dispatch"}),
    ),
    "prune.yml": ("Corpus prune", frozenset({"schedule", "workflow_dispatch"})),
    "validate.yml": ("Model validation", frozenset({"workflow_dispatch"})),
}

CONTENT_REFRESH_UTC_HOURS: Final = (2, 6, 10, 14, 18)

# What the platform and the pipeline cost the clock, measured on `ubuntu-latest`
# over 2026-08-23/24, n=3: a scheduled run starts 40 to 70 minutes after its cron
# minute, then takes 164 to 184 minutes end to end
# (docs/architecture/sources/freshness.md). A schedule that has to miss a digest
# run derives its span from these two, rather than naming an hour.
SCHEDULED_START_DRIFT_MINUTES: Final = (40, 70)

CONTENT_REFRESH_RUN_MINUTES: Final = (164, 184)

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
    ("idhazh-pipeline-tests.yaml", "candidate_models_file"): DISPATCH_READ_BY_NAME,
    # The judge's own date, shaped by the same pattern and for the same reason:
    # it becomes the address the judged rows and the fitted row file under.
    ("llm-council.yml", "date"): "^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$",
    ("measure.yml", "candidate_models_file"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "corpus_links"): "^[1-9][0-9]{0,4}$",
    ("measure.yml", "runtime_candidate"): DISPATCH_CHOICE,
    # Read by name, and the floor is checked where it is used rather than by a
    # pattern here: "at least 2" is a statement about a spread, and a regex that
    # said it would be a second copy of the rule.
    ("measure.yml", "runtime_repeats"): DISPATCH_READ_BY_NAME,
    # Read by name for the reason above, plus one: the ceiling is the job
    # timeout and the timeout is spent per PASS, so what fits depends on how
    # many cases the dispatch runs. The contract bounds it on the way in.
    ("measure.yml", "runtime_corpus_items"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "runtime_corpus_offset"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "runtime_threads"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "runtime_threads_batch"): DISPATCH_READ_BY_NAME,
    ("measure.yml", "budget_samples"): "^[1-9][0-9]{0,4}$",
    ("measure.yml", "model_speed_case"): DISPATCH_CHOICE,
    ("measure.yml", "target"): DISPATCH_CHOICE,
    ("measure.yml", "threads"): "^[1-9][0-9]*$",
    ("prune.yml", "force"): DISPATCH_BOOLEAN,
    ("validate.yml", "candidate_models_file"): DISPATCH_READ_BY_NAME,
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

# The ceiling, not the dispatch rule. Guardrail #2 allows 20 concurrent jobs; a regex
# held the fan-out at four. The empty-input default below stays at four, because
# that is what every scheduled run gets and no eight-shard run is measured yet.
CONTENT_REFRESH_SHARDS: Final = frozenset({"1", "2", "3", "4", "5", "6", "7", "8"})

CONTENT_REFRESH_SHARD_DEFAULT: Final = "4"

# How long a worker may run and how many run at once. Both were literals in the
# work job while `config/idhazh.json` declared different numbers that nothing
# read, so config was a wrong answer with a schema behind it (Guardrail #6).
WORK_BOUND_KEYS: Final = frozenset({"timeout-minutes", "max-parallel"})
# The shared steps that install the build, the file that decides which build,
# and the workflows converted onto them. A converted caller carries no copy of
# the pin, so the two cannot disagree.
LLAMA_RUNTIME_SCRIPT: Final = "fetch-model-runtime.sh"

# The runtime half on its own. `fetch-model-runtime.sh` sources it.
LLAMA_INSTALL_SCRIPT: Final = "install-llama-runtime.sh"

LLAMA_SHARED_SCRIPTS: Final = (LLAMA_RUNTIME_SCRIPT, LLAMA_INSTALL_SCRIPT)

LLAMA_PIN_SCRIPT: Final = "llama-cpp-pin.sh"

# What a converted caller may not spell for itself. The build is the one an
# upgrade moves; the other two move with it and are what a half-done upgrade
# leaves behind.
LLAMA_PIN_NAMES: Final = ("LLAMA_CPP_BUILD", "LLAMA_CPP_ASSET", "LLAMA_CPP_SHA256")


def _read_the_pin() -> tuple[str, str, str]:
    """The three pin values, read from the one script that holds them.

    They were written here as well until now, so a pin bump was three edits in
    two files and a stale copy here would have agreed with itself while the
    runners ran something else.
    """
    text = (SCRIPTS_DIR / LLAMA_PIN_SCRIPT).read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for name in LLAMA_PIN_NAMES:
        found = re.search(rf"^{name}=(.+)$", text, re.MULTILINE)
        assert found, f"{LLAMA_PIN_SCRIPT} no longer declares {name}"
        values[name] = found.group(1).strip().strip('"')
    build = values["LLAMA_CPP_BUILD"]
    asset = values["LLAMA_CPP_ASSET"].replace("${LLAMA_CPP_BUILD}", build)
    return build, asset, values["LLAMA_CPP_SHA256"]


# One llama.cpp build for the pipeline, the validation case and the measurement
# harness. The sha256 is the release API's own `digest` field, confirmed by
# downloading the 16,377,727-byte archive and hashing it, on 2026-08-25.
PINNED_LLAMA_BUILD, PINNED_LLAMA_ASSET, PINNED_LLAMA_SHA256 = _read_the_pin()

# Every workflow that installs the pinned llama.cpp build, whether or not it
# then stands a server up. This is the set the pin and the digest check are
# asserted over: a second build downloaded anywhere is a second binary, and a
# number measured on one of them describes the other (Guardrail #10).
LLAMA_RUNTIME_WORKFLOWS: Final = frozenset(
    {
        "digest.yml",
        "idhazh-pipeline-tests.yaml",
        "llm-council.yml",
        "measure.yml",
        "validate.yml",
    }
)

# The three values themselves, which is what a converted caller is refused. The
# NAME is not the test: a job whose stage records which build decoded the bytes
# has to put `LLAMA_CPP_BUILD` in that step's environment, and taking it from
# the step that published the pin is reading the one home rather than copying
# it. A literal is the copy, and a literal is what drifts.
LLAMA_PIN_VALUES: Final = (PINNED_LLAMA_BUILD, PINNED_LLAMA_ASSET, PINNED_LLAMA_SHA256)
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
    ("idhazh-pipeline-tests.yaml", "cases"): (
        "Fetch runtime and weights",
        "Verify the weights",
        "Start the model",
        '["summarize"]["sha256"]',
    ),
    ("llm-council.yml", "judge"): (
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
    # The raw arm downloads the draft head and never runs it - llama-bench has
    # no speculative path. It fetches it to fill the cache the server arm
    # restores, which is why the check matters more here than the reader does:
    # nothing in this job would notice a corrupt copy, and the arm that loads it
    # is a different job on a different machine. The bench step is named below
    # as the ordering anchor, not as a reader of these bytes.
    ("measure.yml", "llama-bench"): (
        "Fetch the draft head",
        "Verify the draft head",
        "Benchmark the candidate",
        "${{ needs.models.outputs.candidate_draft_sha256 }}",
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

#: The draft head's refs, published beside the target's and empty where the
#: entry declares none. Held apart from MODEL_REF_OUTPUTS because they are
#: optional: a test that required them would fail on every day this repository
#: has published.
DRAFT_REF_OUTPUTS: Final = (
    "draft_repo",
    "draft_revision",
    "draft_file",
    "draft_sha256",
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

MEASUREMENT_TARGETS: Final = frozenset({"bench", "corpus", "batched", "budgets"})


#: The bench is one target and two jobs: raw prefill and decode first, then a
#: real server doing real work. The raw case saves the weights cache entry and
#: the server case restores it, so a key that differs by one character is a
#: second multi-gigabyte download inside one dispatch (Guardrail #2).
BENCH_TARGET: Final = "bench"

#: The job that drives the `llama-bench` binary. It was keyed `llm` until
#: 2026-09-17, which named a whole field of software rather than the one thing
#: the job does, and showed in the run list as a bare three-letter key because
#: no job in this file carried a `name:`.
BENCH_RAW_JOB: Final = "llama-bench"

#: How that key is spelled inside an expression. A hyphen is subtraction there,
#: so `needs.llama-bench.result` does not resolve and the index form is the only
#: reading of it.
BENCH_RAW_JOB_EXPRESSION: Final = f"needs['{BENCH_RAW_JOB}']"

BENCH_SERVER_JOB: Final = "runtime"

#: The dispatch input and the config knob that decide whether the speed case
#: runs at all, and the `models` output that carries the answer to a job's `if:`.
#: A job cannot read a step of its own job, so the decision travels as an output.
BENCH_SPEED_INPUT: Final = "model_speed_case"

BENCH_SPEED_KNOB: Final = "run_model_speed_case"

BENCH_SPEED_OUTPUT: Final = f"needs.models.outputs.{BENCH_SPEED_INPUT}"

BENCH_SPEED_MODULE: Final = "backend/utilities/model_speed_case.py"

BENCH_SPEED_SKIP_STEP: Final = "Say what a bypassed speed case cost this dossier"

BENCH_SUMMARY_STEP: Final = "Put the speed readings in the run summary"

BENCH_CACHE_KEY: Final = (
    "bench-${{ needs.models.outputs.candidate_cache_key }}-${{ env.LLAMA_CPP_BUILD }}"
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

#: Where a bench run's ledgers go. `run.trial_state_dirname` moves the state root
#: for every stage of that run, so one input on the action below puts the whole
#: bench under here and nothing of it beside the production rows.
#:
#: Owner decision, 2026-09-16. A bench is dispatched ad hoc, many times a day,
#: against unmerged branches; a bench row in the ledger the console reads would
#: mean every panel filtering by job for ever. The cost of the split is a join
#: whenever somebody asks what machines GitHub has given us across both, and
#: that is paid once, there, rather than on every read.
BENCH_TRIAL_STATE: Final = "pipeline-tests"

BENCH_LEDGER_ROOT: Final = f"state/{BENCH_TRIAL_STATE}"

#: The flag that puts a stage on the trial root, and the step that plans the
#: corpus. `cli` moves the state root from `run.trial_state_dirname`, which only
#: the scratch copy carries - so a stage invoked without this flag loads the
#: committed config and writes where the console reads. The bench's own `plan`
#: did exactly that until 2026-09-17: it appended to the production seen store,
#: so a dispatch marked real addresses seen and the next production day skipped
#: those stories without saying so.
BENCH_CONFIG_FLAG: Final = "--config"

BENCH_CORPUS_STEP: Final = "Build the fixed bench corpus"

BENCH_FINGERPRINT_STEP: Final = "What machine this bench drew"

#: The step that turns the probe's segment into the row the bench commits. The
#: probe writes `state/pipeline-tests/segments/host-fingerprint/...`, and this
#: workflow has no `assemble` to drain it - so without this step the bench stages
#: a day file nothing wrote and records no machine at all.
BENCH_COMPACT_STEP: Final = "Fold the machine record into its day"

BENCH_COMPACT_COMMAND: Final = "python -m idhazh compact"

#: The fold takes the run's own date and folds the days closed behind it. A call
#: that names no date has no cover to fold against and refuses.
COMPACT_DATE_FLAG: Final = "--date"

#: The one composite action in this repository. The step above was byte-identical
#: in two workflows apart from the job it read the models file from, and a step
#: duplicated across two files is a step that drifts the day one of them is
#: edited - which has happened twice in these two.
CANDIDATE_CONFIG_ACTION: Final = "candidate-config"

BENCH_EMIT_STEP: Final = "Emit the dossier body"


#: Row #13a's case. Its own target because retaking three token counts is minutes
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
#: The starters that are not steps. `measure.yml`'s runtime case starts a server
#: too, but it does it inside a module rather than inside a heredoc - so the
#: Oracle reads the module. It is held here, beside the steps, because the thing
#: that must never happen is a server started by a second spelling of the flag
#: list, and where that spelling lives does not change the rule.
SERVER_STARTER_MODULES: Final = (
    "backend/utilities/runtime_sweep.py",
    "backend/utilities/llama_argv.py",
)

#: What a step runs instead of rendering the flag list itself. A step that
#: reaches `server_argv` through this is still a starter, and `_server_starters`
#: counts it as one.
ARGV_MODULE_CALL: Final = "backend/utilities/llama_argv.py"
RSS_SAMPLE_FILE: Final = "rss-samples.tsv"

SERVER_LOG_FILE: Final = "llama-server.log"

MEMORY_PEAK_FILE: Final = "memory-peak.txt"

CGROUP_PEAK_PATH: Final = "/sys/fs/cgroup/memory.peak"

# The two steps of the work job that write and read those files. The third,
# which writes `memory-peak.txt`, is `SCRAPE_STEP` below.
SAMPLE_MEMORY_STEP: Final = "Sample memory"

MEMORY_SUMMARY_STEP: Final = "What memory this shard used"

# The sampler itself, which stopped being a heredoc inside that step on
# 2026-09-12: two jobs take this reading now, and a shell step two jobs run is
# what `.github/scripts/` is for (`CLAUDE.md` section 3). It is also now under
# `shellcheck`, which cannot see a `run:` body.
SAMPLE_SCRIPT: Final = SCRIPTS_DIR / "sample-rss.sh"
# The roll-call beside it: one row per python process per sample, so the count
# in `python_procs` can be attributed. Same reader hazard as above - the
# operator print reads it by position - so the same agreement is written down.
PYTHON_PROCS_FILE: Final = "python-procs.tsv"

PYTHON_PROCS_FIELDS: Final = {
    2: "pid",
    3: "comm",
    4: "vmrss_kb",
    6: "exe",
    7: "args",
}


# llama-server's own loopback counters, read once at job end. The two series are
# named because they are the two a run is read by: the busy-slot average says
# whether batching ever happened, and the high watermark says how close the day
# came to `n_ctx`. Both spellings were read from `tools/server/README.md` in
# ggml-org/llama.cpp on 2026-08-25.
METRICS_FILE: Final = "llama-metrics.prom"

METRICS_ENDPOINT: Final = "http://127.0.0.1:${LLAMA_PORT}/metrics"

METRICS_SERIES: Final = ("llamacpp:n_busy_slots_per_decode", "llamacpp:n_tokens_max")
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

# Which workflow each label's step lives in. `bench` is dispatched by hand, many
# times a day, and since 2026-09-17 it pushes the machine it drew.
#
# The council's own commit step is deliberately absent. Every label here stages
# paths spelled in the workflow file, which is what lets a test read them, split
# them and run the script over a real repository. The council stages what its
# tenants named, so there is no path in the file to read - and a night with no
# tenant stages nothing at all. `test_llm_council_workflow.py` is where that
# step is held, against the tenants rather than against a list.
COMMIT_WORKFLOWS: Final = {
    "plan": "digest.yml",
    "work": "digest.yml",
    "assemble": "digest.yml",
    "fold": "digest.yml",
    "bench": "measure.yml",
}

COMMIT_JOBS: Final = {
    "plan": "plan",
    "work": "work",
    "assemble": "assemble",
    "fold": "assemble",
    "bench": BENCH_SERVER_JOB,
}

COMMIT_STEPS: Final = {
    "plan": "Commit what the plan saw",
    "work": "Commit what this shard measured",
    "assemble": "Commit the day",
    "fold": "Commit the folded telemetry",
    "bench": "Commit the machine this bench drew",
}

#: The catch-up for a run whose assemble never drained the segment store. The
#: `plan` job is its only caller, and `prune.yml` may never be: that workflow
#: ends in a force push and commits nothing on 29 of 30 wakes.
COMPACT_STEP: Final = "Fold any segments an earlier run left behind"

#: The step that gives the fold above a current store to read. `actions/checkout`
#: restores the commit the run was triggered at, and the `digest` concurrency
#: group can hold a queued run for hours after that, so without this the fold
#: derives a day head from a store another run has already drained.
TAKE_STATE_STEP: Final = "Take the run state from the tip, not from the trigger commit"

TAKE_STATE_SCRIPT: Final = SCRIPTS_DIR / "take-state-from-the-tip.sh"

TAKE_STATE_CALL: Final = ("bash", ".github/scripts/take-state-from-the-tip.sh", "state")

#: The prune's own push, in a script rather than inline so a test can drive it
#: against a real repository. It is the one file in the repository that may
#: force-push, and the one that may refuse to.
PRUNE_PUSH_SCRIPT: Final = SCRIPTS_DIR / "push-rewritten-history.sh"

PRUNE_PUSH_CALL: Final = ("bash", ".github/scripts/push-rewritten-history.sh")

#: The commit the prune checked out, remembered before the squash rewrites it.
#: The push compares origin's tip against this, so a step that captured it after
#: the rewrite would be comparing the tip against a commit only this job holds.
PRUNE_BASE_ENV: Final = "BASE_COMMIT"

#: The step that remembers it, and the step that rewrites history afterwards.
PRUNE_REMEMBER_STEP: Final = "Remember the tip this job checked out"

PRUNE_SQUASH_STEP: Final = "Squash everything older than the boundary"

PRUNE_PUSH_STEP: Final = "Push the rewritten history"

#: The step the `plan` job exists for. The catch-up above runs ahead of it: a
#: fold that refuses a row ends the job, and a refusal that lands after the feed
#: reads has spent them for nothing.
PLAN_STEP: Final = "Plan the day"

COMMIT_BASE_ENV: Final = frozenset(
    {"COMMIT_MESSAGE", "NOTHING_STAGED_MESSAGE", "PUSH_FAILED_MESSAGE"}
)

# Two labels rebuild what they commit, and each one says which file it may
# rebuild. Only assemble commits rendered assets, so only assemble drops a raced
# one. Every other job takes the base three and nothing else: no path under
# `state/` has two writers now, so those commit steps settle nothing after their
# rebase.
#
# Four of the five name a push deadline. The bench does not: `measure.yml` has no
# job that reads config before the one that commits, so it takes the script's
# own value for a caller that names none.
COMMIT_SCRIPT_ENV: Final = {
    "plan": COMMIT_BASE_ENV | {"PUSH_DEADLINE_SECONDS"},
    "work": COMMIT_BASE_ENV | {"PUSH_DEADLINE_SECONDS", "SHARD"},
    "assemble": COMMIT_BASE_ENV
    | {
        "PUSH_DEADLINE_SECONDS",
        "REFRESH_PATHS",
        "REGENERATE_COMMAND",
        "DROP_RACED_ASSETS_COMMAND",
    },
    "fold": COMMIT_BASE_ENV | {"PUSH_DEADLINE_SECONDS"},
    "bench": COMMIT_BASE_ENV,
}

COMMIT_STAGED_PATHS: Final = {
    # `state` whole since 2026-09-17, where this was five paths named one at a
    # time. The catch-up compaction runs in this job and folds a segment into
    # whichever head that segment's own rows name, so what the job writes is not
    # knowable when the list is written - and a hand-listed set would commit the
    # segment deletions while leaving the heads behind.
    "plan": [
        "state",
    ],
    # `state/span-rollup` joined on 2026-09-15 and left on 2026-09-18. A shard is
    # the only thing that writes the fold, and until the first of those days
    # nothing staged it, so nine days of folded spans were measured and then
    # thrown away with the runner. `state/traces` is the raw evidence the fold is
    # taken from and was missed the same way.
    #
    # `state/segments` replaced `state/host-fingerprint` on 2026-09-17, and
    # `state/item-health`, `state/scores`, `state/score-index` and
    # `state/span-rollup` followed it on 2026-09-18. Each of those heads used to
    # be appended to by up to eight work
    # shards and by assemble; every writer now writes its own segment and
    # `assemble` folds them in, so this job stages the segment store and no
    # longer stages a head it does not write.
    "work": [
        "state/traces",
        "state/segments",
    ],
    "assemble": [
        "frontend/public/digest",
        "frontend/public/telemetry",
        "frontend/public/assist/index",
        "frontend/public/source-health.json",
        "frontend/public/console",
        "frontend/public/run-days",
        "frontend/public/day-metrics",
        "frontend/public/machine",
        "frontend/public/span-rollup",
        "frontend/public/run-timeline",
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
    # Under the trial root and nowhere near the production ledger. A bench runs
    # many times a day against unmerged branches, so one of its rows beside the
    # rows the console reads would mean every panel filtering by job for ever.
    #
    # The fingerprint directory alone, not `state/pipeline-tests` whole: the
    # sweep's item-health, scores and traces land under the same trial root
    # because the whole state root moved, and nothing reads them back.
    "bench": [f"{BENCH_LEDGER_ROOT}/{ledger.HOST_FINGERPRINT_DIRNAME}"],
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
# than listed here: the roots are named in `series` and every one of
# them ships with whatever its producer wrote, so a second list would be a
# second thing to keep in step. Seven directory listings, once a session.
CONSOLE_SEED: Final = tuple(
    f"frontend/public/{dirname}/{path.name}"
    for dirname in series.PUBLISHED_ROOTS
    for path in sorted((REPO_ROOT / "frontend" / "public" / dirname).glob("*"))
    if path.is_file()
)

# The step that scrapes llama-server's own counters and copies the kernel's
# memory peak out for the operator. It has to run before `JOB_CLOCK_STEP`,
# which reads the file it writes.
SCRAPE_STEP: Final = "What the server counted"

# Every job that records the machine it drew, and the `--job` value it files
# under. All three of them since 2026-09-17: a run is only as fast as its
# slowest job, and until that day only the middle one said what processor it was
# on, so the two jobs either side cost time nobody could attribute.
#
# One step name across all three, because it answers one question in each.
FINGERPRINT_STEP: Final = "What machine this job drew"

FINGERPRINT_COMMAND: Final = "python -m idhazh fingerprint"

FINGERPRINT_JOB_FLAG: Final = "--job"

FINGERPRINT_JOBS: Final = {"plan": "plan", "work": "work", "assemble": "assemble"}

# The bench draws a machine too, and it says so in its own words because its row
# goes somewhere else. `measure.yml` is dispatched by hand against unmerged
# branches, so its rows live under the trial root.
FINGERPRINT_BENCH_JOB: Final = "runtime"

# The two-row fixture the reader is driven over: one `work` row and one
# `visuals` row, sharing a date, a run and a shard index. Fixed in size, and it
# carries a case the committed ledger has never held (Guardrail #12). The
# `visuals` row is history - plan 11 row #6 retired that job - and the reader
# still has to read it back.
# Deliberately not `--metrics`: that is llama-server's own flag, and
# `test_every_job_that_starts_a_server_reaches_the_one_argv_builder` forbids any
# workflow step from spelling one.
COUNTERS_FLAG: Final = "--counters-file"

# The step that stamps the shard job's own clock. First in the job, so the clock
# covers the cache restore and the weight load as well as the model time, and
# read at `JOB_CLOCK_STEP`, which files the difference onto the host row.
CLOCK_STEP: Final = "Stamp the shard clock"

CLOCK_VARIABLES: Final = ("JOB_STARTED_AT",)

# The other end of `FINGERPRINT_STEP`. The probe runs before the model server so
# the bandwidth reading gets an idle machine; the job's own clock and what the
# weights cost to open are only knowable once the job is over. Both halves go to
# the one segment this job owns and the fold unites them.
JOB_CLOCK_STEP: Final = "What this job cost"

JOB_CLOCK_COMMAND: Final = "python -m idhazh job-clock"

# Neither of the work job's two steps may fail the shard. See the comment above
# them in the workflow for which loss is the cheaper one. `BaseLoader` keeps
# every scalar a string, so the value to compare is the word, not the boolean.
WORK_LEDGER_STEPS: Final = (RECORD_STEP, SCRAPE_STEP, JOB_CLOCK_STEP, COMMIT_STEPS["work"])

TOLERATED: Final = "true"

# The two artifacts a work shard hands to assemble, spelled the way `with.name`
# spells them. A step with no `if:` runs on `success()` and a job stopped by
# `timeout-minutes` is cancelled, so both were skipped on every shard that ran
# out of time while the `always()` ledger steps above them ran. They travel
# together or not at all: the decision naming a chart is in the first and the
# chart's own bytes are in the second.
#
# `evidence-*` is not here. It is the labelling queue's copy of the article
# text, no job downloads it and nothing on the publish path reads it, so
# guarding it is a decision of its own rather than part of this hand-off.
WORK_PAYLOAD_ARTIFACTS: Final = (
    "items-${{ matrix.shard }}",
    "shard-visuals-${{ matrix.shard }}",
)

COMMIT_IDENTITY: Final = "miztiik <miztiik@users.noreply.github.com>"


#: Every file that configures git before a job commits. A runner carries no
#: identity of its own, so each of these has to set one, and three copies of a
#: name drift in silence unless something reads all of them.
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

#: The dispatch input the bench commit message names, so a reader of `main` can
#: see which candidate a machine was drawn for.
SUBSTITUTED_CANDIDATE: Final = "candidate"

#: The name a council night files its rows under. The day the council RUNS and
#: then the platform's run id, so the prefix is deliberately a day later than
#: `SUBSTITUTED_DATE` - a judging run opens after the day it judges.
SUBSTITUTED_COUNCIL_RUN: Final = "2026-08-26-35534060762"

#: The tenant one cell of the council's matrix runs. A slug and nothing more:
#: the venue never checks it against a list of who may exist.
SUBSTITUTED_TENANT: Final = "a-paper-tenant"

#: What the plan job hands every commit step of the run, read from config by
#: `backend/utilities/shard_bound.py`. A stand-in for what Actions would expand,
#: like the date above it - the value config carries is checked where the knob
#: itself is, not here.
SUBSTITUTED_PUSH_DEADLINE: Final = "300"

EXPRESSION_VALUES: Final = {
    "needs.plan.outputs.date": SUBSTITUTED_DATE,
    "needs.plan.outputs.day_dir": SUBSTITUTED_DAY_DIR,
    "needs.plan.outputs.shards": SUBSTITUTED_SHARDS,
    "needs.plan.outputs.push_deadline_seconds": SUBSTITUTED_PUSH_DEADLINE,
    "needs.draw.outputs.date": SUBSTITUTED_DATE,
    "needs.draw.outputs.run_id": SUBSTITUTED_COUNCIL_RUN,
    "steps.decide.outputs.date": SUBSTITUTED_DATE,
    "steps.bounds.outputs.push_deadline_seconds": SUBSTITUTED_PUSH_DEADLINE,
    # What the `derived` step prints into `$GITHUB_OUTPUT`, computed rather than
    # written out. A second copy of that list is the thing this expression
    # exists to remove.
    "steps.derived.outputs.refresh_paths": paths.refresh_paths(day_dir=SUBSTITUTED_DAY_DIR),
    "github.sha": SUBSTITUTED_SHA,
    "matrix.shard": SUBSTITUTED_SHARD,
    "matrix.shards": SUBSTITUTED_SHARDS,
    "matrix.tenant": SUBSTITUTED_TENANT,
    "matrix.date": SUBSTITUTED_DATE,
    "inputs.runtime_candidate": SUBSTITUTED_CANDIDATE,
}

# The producer the harness drives through the loop. See its own docstring for
# why the pipeline's `assemble` cannot be the one under a temporary clone.
REBUILD_STAND_IN: Final = Path(__file__).with_name("rebuild_day.py")

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
    # Discovered, not compared against a list. A new workflow used to fail every
    # test in this directory here, before reaching the one that was about it.
    assert paths, f"{WORKFLOWS_DIR} ships no workflow, so nothing below reads anything"

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


def _stages_a_state_path(workflow: dict[str, object]) -> bool:
    """Whether any step of this workflow hands git a path under `state/`.

    Read off the file rather than listed here, so a workflow that starts
    committing a ledger is covered the day it lands. Two spellings count: the
    shared commit script, which stages every path it is handed, and a bare
    `git add` written inline.

    What it cannot see is a path built at run time. `llm-council.yml` stages
    what its registered tenants named, so the paths are in a shell variable and
    no reader of the file can resolve them - that workflow is covered by the
    tests that read it against its tenants instead.

    A folded `run: >-` body is one line by the time PyYAML has read it and a
    `run: |` body is many, so the search is per line with the continuations
    folded first.
    """
    roots = (ledger.STATE_DIRNAME, f"{ledger.STATE_DIRNAME}/")
    for body in _run_bodies(workflow):
        for line in body.replace("\\\n", " ").splitlines():
            if "commit-and-push.sh" not in line and "git add" not in line:
                continue
            if any(word == roots[0] or word.startswith(roots[1]) for word in line.split()):
                return True
    return False


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


_PARSED_ACTION_STEPS: dict[str, list[dict[str, object]]] = {}

_PARSED_ACTIONS: dict[str, dict[str, object]] = {}


def _local_action(uses: str) -> dict[str, object]:
    """A repository-local composite action, read and parsed once per action."""
    if uses not in _PARSED_ACTIONS:
        path = REPO_ROOT / uses.removeprefix(LOCAL_ACTION_PREFIX) / "action.yml"
        document = yaml.load(read_text(path), Loader=yaml.BaseLoader)
        assert isinstance(document, dict), f"{uses} must contain a YAML mapping"
        _PARSED_ACTIONS[uses] = cast(dict[str, object], document)
    return _PARSED_ACTIONS[uses]


def _local_action_inputs(uses: str) -> dict[str, dict[str, object]]:
    """What a repository-local composite action asks its callers for."""
    declared = _local_action(uses).get("inputs")
    if declared is None:
        return {}
    return {
        name: _mapping(body, f"{uses} input {name}")
        for name, body in _mapping(declared, f"{uses} inputs").items()
    }


def _local_action_steps(uses: str) -> list[dict[str, object]]:
    """The steps a repository-local composite action runs.

    Copied on the way out for the reason `_load_workflows` copies: a caller that
    edited one would be editing what every later test reads, and that failure is
    order-dependent.
    """
    if uses not in _PARSED_ACTION_STEPS:
        runs = _mapping(_local_action(uses).get("runs"), f"{uses} runs")
        assert runs.get("using") == "composite", f"{uses} must be a composite action"
        steps = runs.get("steps")
        assert isinstance(steps, list), f"{uses} must declare steps"
        assert all(isinstance(step, dict) for step in steps), f"{uses} steps must be mappings"
        _PARSED_ACTION_STEPS[uses] = cast(list[dict[str, object]], steps)
    return copy.deepcopy(_PARSED_ACTION_STEPS[uses])


def _declared_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    """What a job's own file spells, with no action resolved.

    `_steps` answers what a job runs; this answers what it says. An extraction
    is exactly the difference between those two, so a test that a block moved
    has to be able to read both sides of it.
    """
    raw_steps = _job(workflow, job_name).get("steps")
    assert isinstance(raw_steps, list), f"job {job_name} steps must contain a YAML list"
    assert all(isinstance(step, dict) for step in raw_steps), f"job {job_name} steps must be mappings"
    return cast(list[dict[str, object]], raw_steps)


def _action_call(workflow: dict[str, object], job_name: str, uses: str) -> dict[str, str]:
    """What a job hands a local action, as one mapping, asserted to be called once."""
    matches = [step for step in _declared_steps(workflow, job_name) if step.get("uses") == uses]
    assert len(matches) == 1, f"job {job_name} must call {uses} exactly once"
    given = matches[0].get("with")
    if given is None:
        return {}
    return {
        name: str(value)
        for name, value in _mapping(given, f"job {job_name} {uses} 'with'").items()
    }


def _steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    """A job's steps, with a repository-local composite action resolved in place.

    A step that calls `./.github/actions/<name>` runs that action's steps, so a
    reader stopping at the workflow file would report that a converted job no
    longer caches its weights, no longer checks a digest and no longer starts a
    server - which is the opposite of what happened. This file already follows
    one level of delegation into a shipped `.sh` (`_effective_shell`,
    `_starter_shell`); this is the same rule for the other kind of extraction,
    and it is what lets a step move without every oracle over it going quiet.

    The reference itself is kept, so a caller can still ask which action a job
    calls, and the action's own steps follow it in the order the runner runs
    them. An `if:` on either side is not evaluated: what this answers is what a
    job runs, never what it ran on one night.
    """
    resolved: list[dict[str, object]] = []
    for step in _declared_steps(workflow, job_name):
        resolved.append(step)
        uses = step.get("uses")
        if isinstance(uses, str) and uses.startswith(LOCAL_ACTION_PREFIX):
            resolved.extend(_local_action_steps(uses))
    return resolved


def _step(
    workflow: dict[str, object], job_name: str, key: str, value: str
) -> dict[str, object]:
    matches = [step for step in _steps(workflow, job_name) if step.get(key) == value]
    assert len(matches) == 1, f"job {job_name} must have one step with {key}={value}"
    return matches[0]


def _stage_invocations(
    workflow: dict[str, object], workflow_name: str
) -> list[tuple[str, str, str, list[str]]]:
    """Every `python -m idhazh <stage>` a workflow runs, as (job, step, stage, words).

    One reader, because two workflows ask the same question of their own jobs -
    can a dispatch that is not a production run reach the state root a published
    day is built from? - and a walker copied into both is a walker that drifts
    the day one of them is edited.

    Every job is walked rather than the ones that run a stage today, so a job
    that starts running one is caught by a test rather than by a production day
    that came up short.

    An Actions expression is not shell, so it is blanked before the line is
    split. What the platform puts there cannot turn a stage invocation into a
    different one.

    `idhazh` has to be the whole word. `python -m idhazh.council.run_identity`
    runs a module rather than a verb, and reading it as one leaves no word
    called `idhazh` in the line to take the next word after.
    """
    jobs = _mapping(workflow.get("jobs"), f"{workflow_name} jobs")
    found: list[tuple[str, str, str, list[str]]] = []
    for job_name in sorted(jobs):
        for step in _steps(workflow, job_name):
            script = step.get("run")
            if not isinstance(script, str):
                continue
            blanked = re.sub(r"\$\{\{.*?\}\}", "expression", script, flags=re.DOTALL)
            for line in blanked.replace("\\\n", " ").splitlines():
                if not re.search(r"\bpython3?\s+-m\s+idhazh(?=\s)", line):
                    continue
                words = shlex.split(line)
                stage = words[words.index("idhazh") + 1]
                found.append((job_name, str(step.get("name")), stage, words))
    return found


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


def _composite_action_script(name: str) -> str:
    """The shell a repository-local composite action runs, as one string.

    A `./`-prefixed action resolves to this repository at the commit the run
    checked out, so what it runs is in the tree the tests already read - but it
    is not in `.github/workflows/`, so every oracle that globs that directory
    stops seeing it. This is what keeps those oracles pointed at the shell after
    it moves out of a workflow file.
    """
    path = ACTIONS_DIR / name / "action.yml"
    document = yaml.safe_load(read_text(path))
    runs = _mapping(_mapping(document, path.name).get("runs"), f"{name} runs")
    assert runs.get("using") == "composite", f"{name} must be a composite action"
    steps = runs.get("steps")
    assert isinstance(steps, list), f"{name} must declare steps"

    scripts = [step["run"] for step in steps if isinstance(step, dict) and "run" in step]
    assert scripts, f"{name} runs no shell"
    return "\n".join(scripts)


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


#: A shipped script named inside a `run:` body. A name is letters, digits and
#: the punctuation a filename here uses, so the shellcheck step's
#: `.github/scripts/*.sh` glob is not read as a call to anything.
SCRIPT_CALL: Final = re.compile(r"\.github/scripts/(?P<name>[A-Za-z0-9._-]+\.sh)")


def _called_scripts(body: str) -> list[str]:
    """Every shipped script a shell body names outside a comment."""
    called: list[str] = []
    for line in body.splitlines():
        if line.lstrip().startswith("#"):
            continue
        called.extend(match.group("name") for match in SCRIPT_CALL.finditer(line))
    return called


def _script_closure(body: str) -> str:
    """A shell body plus every shipped script reachable from it, at any depth.

    One level of following was enough while every shipped script was a leaf. It
    stopped being enough the moment one script sourced another: a check written
    over the one-level text goes quietly green on a fetch that moved one file
    further away, which is the same hole the following was added to close. The
    visited set is what keeps two scripts that name each other from recursing.
    """
    bodies = [body]
    seen: set[str] = set()
    pending = _called_scripts(body)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        called = SCRIPTS_DIR / name
        if not called.is_file():
            continue
        text = called.read_text(encoding="utf-8")
        bodies.append(text)
        pending.extend(_called_scripts(text))
    return "\n".join(bodies)


def _effective_shell(step: Mapping[str, object]) -> str:
    """A step's own shell, plus the text of every shipped script it reaches.

    A step that calls a script runs that script's shell, so a search over `run:`
    bodies alone stops seeing a fetch the moment the fetch is extracted - and
    every check written over that search silently passes on nothing. Following
    the call is what lets extraction be a refactor rather than a hole.
    """
    script = step.get("run")
    if not isinstance(script, str):
        return ""
    return _script_closure(script)


def _llama_fetch_scripts(workflow: dict[str, object]) -> list[tuple[str, object, str]]:
    return [
        (job_name, step.get("name"), shell)
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if "ggml-org/llama.cpp/releases" in (shell := _effective_shell(step))
    ]


def _pin_output_name() -> str:
    """The key the pin prints when it is run, read out of the pin rather than retyped.

    A converted caller that needs the build takes it from a step that published
    this key, so the two halves of that arrangement are held together by the
    file itself instead of by two constants nobody diffs.
    """
    printed = (SCRIPTS_DIR / LLAMA_PIN_SCRIPT).read_text(encoding="utf-8")
    match = re.search(r'echo "([a-z_]+)=\$\{LLAMA_CPP_BUILD\}"', printed)
    assert match is not None, f"{LLAMA_PIN_SCRIPT} must print the build as key=value"
    return match.group(1)


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
                script = _effective_shell(step)
                if "huggingface.co/" not in script:
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


def _run_the_inline_program(
    script: str, config_root: Path, env: dict[str, str] | None = None
) -> dict[str, str]:
    """Run the program a plan-job step carries, and read what it would write.

    The step redirects its stdout into `$GITHUB_OUTPUT`, so its stdout IS the
    job output. Running the shipped bytes against a real config directory is
    what makes this a test of the step rather than of a copy of it.

    `env` is what the step's own `env:` block would deliver. Absent, the program
    runs with none of them set, which is the dispatch that filled nothing in.
    """
    match = re.search(r"<<'PY'[^\n]*\n(.*?)\nPY(?:\n|$)", script, flags=re.DOTALL)
    assert match is not None, "the step must carry an inline program"

    result = subprocess.run(
        [sys.executable, "-c", match.group(1)],
        cwd=config_root,
        env={**os.environ, **(env or {})},
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
    """The paths and the strings one commit step hands the shared script."""
    workflow = _load_workflows()[COMMIT_WORKFLOWS[label]]
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
    # This repository's own attributes file. The merge drivers it sets decide
    # whether two runs that both appended are in conflict, so a scripted origin
    # without it would test a different repository.
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
    return subprocess.run(
        [bash, COMMIT_SCRIPT.as_posix(), *staged_paths],
        cwd=runner,
        env={**env, **settings},
        capture_output=True,
        text=True,
    )


def _reject_the_first_pushes(origin: Path, count: int) -> None:
    """Make origin refuse the next `count` pushes and take everything after them.

    A racing commit can only reject one push, and what the deadline has to be
    shown doing is surviving more rejections than the old three-attempt loop
    allowed. A `pre-receive` hook is the only thing that can reject on demand,
    and it counts down in a file beside itself so each attempt sees one fewer.

    The rejection is what a lost race looks like to the pusher, which is the
    point: the script cannot tell the two apart and must not try to.
    """
    budget = origin / "reject-this-many-pushes"
    budget.write_text(f"{count}\n", encoding="utf-8", newline="\n")
    hook = origin / "hooks" / "pre-receive"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        "#!/bin/sh\n"
        'budget="$(dirname "$0")/../reject-this-many-pushes"\n'
        'left=$(cat "$budget" 2>/dev/null || echo 0)\n'
        'if [ "$left" -gt 0 ]; then\n'
        '  echo $((left - 1)) > "$budget"\n'
        '  echo "rejecting this push on purpose, $left left" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    hook.chmod(0o755)


def _push_attempts(stdout: str) -> list[dict[str, str]]:
    """Every `push attempt=` line the loop printed, as the fields it carries.

    Parsed rather than matched as text, because what the line is for is being
    read by whoever is deciding whether the deadline is the right number. The
    leading word is the line's own label and carries no value, so it goes.
    """
    return [
        dict(pair.split("=", 1) for pair in line.split()[1:])
        for line in stdout.splitlines()
        if line.startswith("push attempt=")
    ]


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
    the same, differing in the config attribute and two filenames. They run one
    script now. Reading the step alone would report that neither reaches
    `server_argv` any more, which is the opposite of what happened.
    """
    body = step.get("run")
    if not isinstance(body, str):
        return ""
    if START_SERVER_SCRIPT.name not in body:
        return body
    return body + "\n" + read_text(START_SERVER_SCRIPT)


def _model_server_callers(
    workflows: Mapping[str, dict[str, object]],
) -> set[tuple[str, str]]:
    """Every job that stands a model server up through the shared action.

    Read off the `uses:` line rather than listed here. The list meant a third
    caller had to be written down in a test file before it could exist, which
    is a test asking to be edited rather than a test naming a defect.
    """
    return {
        (filename, job_name)
        for filename, workflow in workflows.items()
        for job_name in _mapping(workflow.get("jobs"), f"{filename} jobs")
        for step in _declared_steps(workflow, job_name)
        if step.get("uses") == MODEL_SERVER_ACTION
    }


def _server_starters(
    workflows: Mapping[str, dict[str, object]],
) -> dict[tuple[str, str], tuple[str, ...]]:
    """Every step that reaches `server_argv`, found by reading, not by listing.

    A step that stands a server up any other way is a second answer to what the
    run executes, so the set this returns is compared by equality. A job's
    starters come back in the order its steps run, because a case that restarts
    a server is comparing itself against the cases before it and the order is
    what says which start each case ran under.
    """
    found: dict[tuple[str, str], tuple[str, ...]] = {}
    for filename, workflow in workflows.items():
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            for step in _steps(workflow, job_name):
                shell = _starter_shell(step)
                if "server_argv" not in shell and ARGV_MODULE_CALL not in shell:
                    continue
                name = step.get("name")
                assert isinstance(name, str), f"{filename}/{job_name}: name the step"
                where = (filename, job_name)
                found[where] = (*found.get(where, ()), name)
    return found
