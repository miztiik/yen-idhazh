"""How long does one candidate take over a fixed corpus of `bench.corpus_items` articles?

Shells `python -m idhazh work`, so what it times is production's own path.
Which repeats may be compared is a separate question, in `sweep_verdict.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.model_server import port_of_base_url
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.run_plan import RunPlan
from idhazh.llm.server import loopback_url, server_argv
from idhazh.stages.common import CAPTURES_DIRNAME
from idhazh.telemetry import silicon
from utilities import sweep_verdict
from utilities.memory_sampler import read_status
from utilities.model_runtime import refuse_a_server_that_died_at_startup

ROOT = Path("backend/var/runtime-sweep")
CONFIG_ROOT = ROOT / "configs"
CANDIDATE_CONFIG = Path("backend/var/candidate-config")
RUN_ROOT = Path("backend/var/run")
SERVER_BINARY = Path("backend/bin/llama-server")
WEIGHTS_DIR = Path("backend/models")

#: Where a repeat's prompts and replies are kept. Under `ROOT` because `ROOT` is
#: the one directory the workflow uploads, and the name is imported rather than
#: spelled again so this looks where the stage actually writes (Guardrail #6).
CAPTURES_ROOT = ROOT / CAPTURES_DIRNAME

#: What each named candidate changes about the server it starts. Every key is
#: llama-server's own flag spelling, except the two the entry carries outside the
#: server block - `companion_files` and the request values - which `write_config`
#: routes to where they live.
CANDIDATE_UPDATES: dict[str, tuple[dict[str, Any], int]] = {
    "baseline": ({}, 1),
    "np1": ({"-np": 1}, 1),
    "batch2048": ({"--batch-size": 2048}, 1),
    "no_startup_warmup": ({"--no-warmup": None}, 1),
    "flash_attention_on": ({"-fa": "on"}, 1),
    "load_mode_mmap_mlock": ({"--mlock": None}, 1),
    "kv_q8": ({"--cache-type-k": "q8_0", "--cache-type-v": "q8_0"}, 1),
    "prio_poll": ({"--prio": 2, "--poll": 100}, 1),
    "np2_inflight": ({"-np": 2, "--ctx-size": 16384}, 2),
    # The one candidate that reaches outside the server block. A model file
    # declaring no companion answers the question it exists for: what the head
    # is worth, measured on ONE machine instead of across two dispatches.
    "no_draft": ({"companion_files": []}, 1),
}

#: Entry keys a case may set that are not llama-server flags.
ENTRY_KEYS = ("companion_files", "request_timeout_minutes")

#: What goes in a request body rather than on the command line.
SAMPLING_KEYS = ("temperature", "top_p", "seed")

#: Two knobs whose value an operator types, so each is bounded where it is read.
SIZED_BY_DISPATCH = ("threads", "threads_batch")


class CaseSet(NamedTuple):
    """Several configurations measured against one of their own, inside one job.

    A named candidate above answers "what does this setting cost", so it runs
    the unchanged server and one variant. A case set answers "does this setting
    change the words", which needs every value of the setting worth trying and
    a reference that has it off - and no baseline case, because the unchanged
    server is already one of the values.
    """

    cases: tuple[tuple[str, dict[str, Any]], ...]
    reference: str
    shared: dict[str, Any]
    between_cases: str


#: The case that answers whether the head changes the words, and whether the
#: drafted depth is what controls it. The publisher of these exact weights says
#: it cannot: "The drafter shares the target's KV cache and does not change the
#: output (the target verifies every drafted token)." Two paired dispatches
#: refused that on nine of nine articles. The one difference on record between
#: their setup and ours is the drafted depth - their command passes 4 and the
#: entry pins 2 - and nobody had run it.
DRAFT_DEPTH = "draft_depth"

#: The reference the other three are read against. Not the baseline: the
#: question is what the head does to the text, so the case with no head is the
#: only honest zero.
HEAD_OFF = "head_off"

CASE_SETS: dict[str, CaseSet] = {
    DRAFT_DEPTH: CaseSet(
        cases=(
            (HEAD_OFF, {"companion_files": []}),
            ("n_max_1", {"--spec-draft-n-max": 1}),
            ("n_max_2", {"--spec-draft-n-max": 2}),
            ("n_max_4", {"--spec-draft-n-max": 4}),
        ),
        reference=HEAD_OFF,
        # **Temperature 0, pinned once and unoverridable.** Every committed entry
        # runs at 0.2, where the seed decides which token is drawn and the
        # sampler alone reworded six of seven articles between two readings of
        # ONE configuration on 2026-09-17. At 0.2 the head's effect and the
        # sampler's noise arrive as a single number nobody can split. At 0 a
        # changed summary can only be the head. It is declared here rather than
        # repeated into each case because three cases pinned and one forgotten
        # is a run that looks valid and measures nothing.
        shared={"temperature": 0.0},
        # The whole question is whether the cases disagree, so a disagreement is
        # the reading rather than a defect. Two repeats of ONE case that
        # disagree is still the model being unstable, and still fatal.
        between_cases=sweep_verdict.BETWEEN_CASES_IS_THE_READING,
    ),
}


class CasePlan(NamedTuple):
    """The cases one dispatch runs, and which of them the rest are read against."""

    cases: tuple[tuple[str, dict[str, Any], int], ...]
    reference: str
    between_cases: str


def corpus_items(config_root: Path | None, *, dispatch: str = "") -> int:
    """How many articles one repeat reads, from `bench.corpus_items`.

    One number, read from config by everything that needs it. Until 2026-09-17 it
    was two source literals - a `--cap` in the workflow and a constant here - and
    when they disagreed `freeze_corpus` killed the dispatch after the plan step
    (Guardrail #6). `None` is the committed tree, which is what a fresh clone has.

    **`dispatch` overrules the knob for one run, and does it by WRITING the
    value into the scratch config** rather than by printing a number the config
    does not carry. `freeze-corpus`, `work` and `collect` each read the config
    for themselves, so a printed-only override would be exactly the second
    spelling that killed that dispatch. It is bounded by the contract: the value
    is re-read through `config.load`, so anything outside 1..20 fails here
    rather than eight hours later.
    """
    settings = config.load(config_root) if config_root is not None else config.load()
    if not dispatch:
        return settings.app.bench.corpus_items
    if config_root is None:
        raise SystemExit("--dispatch needs --config: there is no scratch config to write")
    try:
        wanted = int(dispatch)
    except ValueError:
        raise SystemExit(f"runtime_corpus_items must be a whole number, not {dispatch!r}") from None
    path = config_root / "idhazh.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bench"]["corpus_items"] = wanted
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    # Refused by the contract BEFORE anything is written, so a value outside the
    # declared range leaves the scratch config as it was rather than corrupting
    # it and dying at the freeze step with the plan already paid for. The bound
    # is the contract's own and is not spelled again here (Guardrail #6).
    try:
        AppConfig.from_json(text)
    except ValidationError as error:
        raise SystemExit(f"runtime_corpus_items {wanted} is refused: {error}") from error
    path.write_text(text, encoding="utf-8")
    return wanted


def repeats(config_root: Path | None, *, dispatch: str = "") -> int:
    """How many times each case runs, from `bench.repeats`.

    The same shape `corpus_items` has, and for the same reason: the two numbers
    multiply into the passes the job timeout is spent on, so an operator who
    changes one sees the other in the file beside it (Guardrail #6).

    It stops short of that one's write. `corpus_items` is written into the
    scratch config because `freeze-corpus`, `work` and `collect` each read it
    back; this number has one reader, and a copy nothing reads is a second
    spelling waiting to disagree. The bound is still the contract's own - a
    dispatched value is re-read through `AppConfig`, so anything below two is
    refused here rather than after the first pass.
    """
    settings = config.load(config_root) if config_root is not None else config.load()
    if not dispatch:
        return settings.app.bench.repeats
    if config_root is None:
        raise SystemExit("--repeats needs a config root to validate against")
    try:
        wanted = int(dispatch)
    except ValueError:
        raise SystemExit(f"runtime_repeats must be a whole number, not {dispatch!r}") from None
    payload = json.loads((config_root / "idhazh.json").read_text(encoding="utf-8"))
    payload["bench"]["repeats"] = wanted
    try:
        AppConfig.from_json(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except ValidationError as error:
        raise SystemExit(f"runtime_repeats {wanted} is refused: {error}") from error
    return wanted


def candidate_update(name: str, *, threads: int, threads_batch: int) -> tuple[dict[str, Any], int]:
    """What this candidate changes, and how many workers it runs."""
    if name == "threads":
        return {"n_threads": threads}, 1
    if name == "threads_batch":
        return {"n_threads_batch": threads_batch}, 1
    if name not in CANDIDATE_UPDATES:
        raise SystemExit(f"unknown runtime candidate: {name}")
    update, workers = CANDIDATE_UPDATES[name]
    return dict(update), workers


def case_plan(name: str, *, threads: int, threads_batch: int) -> CasePlan:
    """What this dispatch runs: a whole case set, or the baseline and one candidate.

    One worker a case in a set. `np2_inflight` is the only candidate that needs
    two and it is not a member of one, so a set that asked for a worker count
    would be carrying a knob nothing turns.
    """
    if name in CASE_SETS:
        chosen = CASE_SETS[name]
        return CasePlan(
            # The shared pin is applied LAST, so a case cannot quietly drop the
            # control the whole set depends on.
            cases=tuple(
                (label, {**update, **chosen.shared}, 1) for label, update in chosen.cases
            ),
            reference=chosen.reference,
            between_cases=chosen.between_cases,
        )
    update, workers = candidate_update(name, threads=threads, threads_batch=threads_batch)
    cases: list[tuple[str, dict[str, Any], int]] = [(sweep_verdict.BASELINE, {}, 1)]
    if name != sweep_verdict.BASELINE:
        cases.append((name, update, workers))
    return CasePlan(
        cases=tuple(cases),
        reference=sweep_verdict.BASELINE,
        between_cases=sweep_verdict.BETWEEN_CASES_REJECTS,
    )


def write_config(label: str, update: dict[str, Any]) -> Path:
    """A scratch config for one case, from the candidate copy and never from `config/`.

    The committed config still names the incumbent, so a sweep that copied it
    would measure the wrong weights under the candidate's name.
    """
    dst = CONFIG_ROOT / label
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(CANDIDATE_CONFIG, dst)
    pointer = json.loads((dst / "idhazh.json").read_text(encoding="utf-8"))["models_file"]
    path = dst / pointer
    payload = json.loads(path.read_text(encoding="utf-8"))
    entry = payload["summarize"]
    for key, value in update.items():
        if key in ENTRY_KEYS:
            entry[key] = value
        elif key in SAMPLING_KEYS:
            entry.setdefault("sampling", {})[key] = value
        else:
            entry.setdefault("server", {})[key] = value
    # A speculation flag with no draft model is a server that refuses to start,
    # so taking the head away takes its settings with it.
    if not any(companion.get("flag") for companion in entry.get("companion_files") or []):
        entry["server"] = {
            flag: value
            for flag, value in entry.get("server", {}).items()
            if not flag.startswith("--spec-")
        }
    path.write_text(ModelsConfig.model_validate(payload).to_json(), encoding="utf-8")
    return dst


def cgroup_peak() -> str | None:
    path = Path("/sys/fs/cgroup/memory.peak")
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def parse_server_facts(log_path: Path) -> dict[str, str]:
    """What the server said it was doing, read back out of its own log."""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    facts = {}
    for key in ("n_slots", "n_ctx_slot", "n_ctx_per_seq", "kv_unified"):
        match = re.search(rf"{key}\s*=\s*'?([^,\s']+)'?", text)
        if match:
            facts[key] = match.group(1)
    return facts


def wait_for_health(port: int) -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(loopback_url(port) + "/health", timeout=2) as response:
                if response.status < 500:
                    return
        except OSError:
            pass
        time.sleep(5)
    raise RuntimeError("llama-server never became healthy")


def assert_the_candidate_is_serving(port: int, candidate_id: str) -> None:
    """Healthy says a server replied. It does not say which weights replied.

    Every number this job reports is filed under the candidate's id, so a server
    answering under any other alias makes the whole run a measurement of
    something else with the candidate's name on it (Guardrail #10).
    """
    with urllib.request.urlopen(loopback_url(port) + "/v1/models", timeout=5) as response:
        served = json.load(response)["data"][0]["id"]
    if served != candidate_id:
        raise RuntimeError(f"the server answers to {served}, not {candidate_id}")


class Collected(NamedTuple):
    """What one repeat read, what it wrote, and what each item cost."""

    sources: dict[str, str]
    digests: dict[str, str]
    per_item: list[dict[str, Any]]


def collect(date: str, label: str, repeat: int, *, items: int) -> Collected:
    """Read one repeat's output back off disk.

    `sources` is a digest of the article as extracted rather than of the page,
    so it moves when a publisher edits the text and not when they change an ad.

    Each item carries the words the candidate wrote, not only a digest of them.
    A digest proves two candidates disagreed; it never says how, so four sweeps
    have now shown a difference nobody could read. A few articles of our own
    prose is a small thing to carry and it is the only thing here a person can
    actually judge.

    The text is our own summary of an untrusted page, and it stays data
    (CLAUDE.md Guardrail #11): it is written into one JSON artifact under
    `ROOT`, and no caller turns it into a shell argument, a path or a URL. It is
    a bench artifact and reaches no reader - nothing in this module writes into
    the published tree.
    """
    items_dir = RUN_ROOT / date / "items"
    articles = sorted(items_dir.glob("*.article.json"))
    summaries = sorted(items_dir.glob("*.summary.json"))
    for what, found in (("articles", articles), ("summaries", summaries)):
        if len(found) != items:
            raise RuntimeError(f"{label} repeat {repeat} wrote {len(found)} {what}, not {items}")

    sources = {}
    for path in articles:
        data = json.loads(path.read_text(encoding="utf-8"))
        source = {
            key: data.get(key) for key in ("title", "text", "source_form", "truncated", "brief")
        }
        canonical = json.dumps(source, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        sources[data["item_id"]] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    digests = {}
    per_item = []
    for path in summaries:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") != "ok":
            raise RuntimeError(f"{path.name} did not summarize: {data.get('failure_detail')}")
        digests[data["item_id"]] = data["output_digest"]
        per_item.append(
            {
                "item_id": data["item_id"],
                "output_digest": data["output_digest"],
                "title": data["title"],
                "summary": data["summary"],
                "key_points": data["key_points"],
                **{
                    key: data[key]
                    for key in (
                        "duration_ms",
                        "fetch_ms",
                        "extract_ms",
                        "summarize_ms",
                        "input_tokens",
                        "output_tokens",
                    )
                },
            }
        )
    return Collected(sources, digests, per_item)


def keep_the_captures(date: str, label: str, repeat: int) -> str | None:
    """Move this repeat's prompts and replies where the artifact will carry them.

    `idhazh work` already writes one capture per call per item, under
    `capture_prompts` and `capture_replies`. It names each file for the item and
    the call and nothing else, so the second repeat overwrites the first and the
    next case overwrites that - and only `ROOT` is uploaded, so until this ran
    every prompt and every reply died with the runner. Four dispatches proved
    two configurations wrote different summaries and left nobody able to read
    how they differed.

    Moved rather than copied. That keeps this repeat's text AND leaves the
    directory empty, so a repeat that writes nothing cannot inherit the previous
    one's files and report them as its own.
    """
    written = RUN_ROOT / date / CAPTURES_DIRNAME
    if not written.exists():
        return None
    kept = CAPTURES_ROOT / f"{label}-{repeat}"
    if kept.exists():
        shutil.rmtree(kept)
    kept.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(written), str(kept))
    # POSIX and relative: it is about to leave the process inside a JSON
    # artifact (CLAUDE.md section 2).
    return kept.as_posix()


def run_once(
    label: str,
    update: dict[str, Any],
    repeat: int,
    worker_count: int,
    *,
    date: str,
    candidate: str,
    candidate_file: str,
    candidate_id: str,
    port: int,
) -> dict[str, Any]:
    """One server start, one pass over the fixed corpus, one set of readings."""
    cfg = write_config(f"{label}-{repeat}", update)
    settings = config.load(cfg)
    log_path = ROOT / f"{label}-{repeat}.llama-server.log"
    items_dir = RUN_ROOT / date / "items"
    # Both, and for the same reason: a repeat starts from an empty run directory
    # or it can report the previous one's files as its own.
    for stale in (items_dir, RUN_ROOT / date / CAPTURES_DIRNAME):
        if stale.exists():
            shutil.rmtree(stale)
    items_dir.mkdir(parents=True, exist_ok=True)
    argv = server_argv(
        binary=SERVER_BINARY,
        weights=WEIGHTS_DIR / candidate_file,
        model=settings.models.summarize,
        server=settings.models.summarize.server,
        port=port,
    )
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "backend/bin"
    started = time.perf_counter()
    rss_samples: list[dict[str, str]] = []
    with log_path.open("w", encoding="utf-8") as log:
        server = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env)
        refuse_a_server_that_died_at_startup(server, log_path)
        stop = threading.Event()

        def sample_rss() -> None:
            while not stop.is_set():
                rss_samples.append(read_status(server.pid))
                time.sleep(1)

        sampler = threading.Thread(target=sample_rss, daemon=True)
        sampler.start()
        try:
            wait_for_health(port)
            assert_the_candidate_is_serving(port, candidate_id)
            startup_ms = int((time.perf_counter() - started) * 1000)
            work_started = time.perf_counter()
            workers = [
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "idhazh",
                        "work",
                        "--config",
                        str(cfg),
                        "--date",
                        date,
                        "--shard",
                        str(shard),
                        "--shards",
                        str(worker_count),
                        "--no-faithfulness",
                    ]
                )
                for shard in range(worker_count)
            ]
            failures = [proc.wait() for proc in workers]
            if any(failures):
                raise RuntimeError(f"{label} repeat {repeat} worker failures: {failures}")
            work_ms = int((time.perf_counter() - work_started) * 1000)
            total_ms = int((time.perf_counter() - started) * 1000)
        finally:
            stop.set()
            server.terminate()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=20)
            sampler.join(timeout=5)

    found = collect(date, label, repeat, items=settings.app.bench.corpus_items)
    return {
        "label": label,
        "candidate": candidate,
        "repeat": repeat,
        "argv": argv,
        "worker_count": worker_count,
        "startup_ms": startup_ms,
        "work_ms": work_ms,
        "total_ms": total_ms,
        "model_path_ms": startup_ms + sum(item["summarize_ms"] for item in found.per_item),
        "server_rss_samples": rss_samples,
        "cgroup_memory_peak_bytes": cgroup_peak(),
        "server_facts": parse_server_facts(log_path),
        "sources": found.sources,
        "digests": found.digests,
        "per_item": found.per_item,
        "captures": keep_the_captures(date, label, repeat),
    }


def corpus_offset(dispatch: str) -> int:
    """Which slice of the day's plan this dispatch reads. 0 is the top of it.

    **Five articles cannot share one job with four cases.** Eight passes over
    five articles is about 524 minutes at the 13.1 minutes an article the
    slowest pass has recorded, against a 360-minute platform ceiling - so the
    breadth has to come from several jobs rather than a longer one. Each
    dispatch still runs every case, so every case-against-case comparison stays
    inside one machine, which is the whole reason the cases are paired
    (Guardrail #2, the ceiling is GitHub's and the design is what gives).

    The offset is what stops three dispatches on one day all reading the same
    top two articles and reporting two articles as six.
    """
    if not dispatch:
        return 0
    try:
        offset = int(dispatch)
    except ValueError:
        raise SystemExit(
            f"runtime_corpus_offset must be a whole number, not {dispatch!r}"
        ) from None
    if offset < 0:
        raise SystemExit(f"runtime_corpus_offset must be 0 or more, not {offset}")
    return offset


def freeze_corpus(date: str, *, items: int, offset: int = 0) -> None:
    """Cut the day's plan to `items` articles and keep a copy beside the readings.

    The plan is frozen so every repeat reads the same ADDRESSES. Their text is
    refetched each time, which is what `sweep_verdict` exists to notice.

    `offset` takes a later slice, so two dispatches of one day measure different
    articles. The refusal below is what makes a short plan a failure before the
    server starts rather than an hour in.
    """
    plan_path = RUN_ROOT / date / "plan.json"
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["items"] = payload["items"][offset : offset + items]
    if len(payload["items"]) != items:
        raise SystemExit(
            f"the runtime sweep needs {items} planned articles from offset {offset}"
        )
    counts = Counter(item["vertical"] for item in payload["items"])
    for vertical in payload["verticals"]:
        vertical["planned"] = counts.get(vertical["id"], 0)
    text = RunPlan.model_validate(payload).to_json()
    plan_path.write_text(text, encoding="utf-8")
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "plan.json").write_text(text, encoding="utf-8")


def _bounded(name: str, value: int) -> int:
    ceiling = 2 * (os.cpu_count() or 1)
    if not 1 <= value <= ceiling:
        raise SystemExit(f"runtime_{name} must be in 1..{ceiling}")
    return value


def server_port(config_root: Path) -> int:
    """The port this sweep's own config root names. Never a literal, never an argument.

    A server on one port and a stage posting to another is every item failing,
    so one value answers both: `model_server.base_url` says where the stage
    posts, and the port inside it is what the server binds. An argument named
    `--port` would also be a second spelling of a llama-server flag, and the
    flag list has exactly one spelling.
    """
    return port_of_base_url(config.load(config_root).app.model_server.base_url)


def sweep(args: argparse.Namespace) -> int:
    candidate = args.candidate
    repeat_count = repeats(CANDIDATE_CONFIG, dispatch=args.repeats)
    # Two, because a spread needs two readings and this stops a dispatch that
    # cannot produce one. It is the sweep's own statement about what it can
    # read, kept beside the contract's floor rather than deferred to it: the
    # contract bounds what may be configured, this bounds what may be judged.
    # The ceiling is the job timeout rather than taste: a named candidate runs
    # two cases, so the repeats multiply the corpus, and `bench.corpus_items`
    # is the knob sized against that same bound (Guardrail #2).
    if repeat_count < sweep_verdict.MIN_AGREEING_REPEATS:
        raise SystemExit("runtime_repeats must be at least 2 - one reading has no spread")
    port = server_port(CANDIDATE_CONFIG)
    threads = _bounded("threads", args.threads)
    threads_batch = _bounded("threads_batch", args.threads_batch)

    ROOT.mkdir(parents=True, exist_ok=True)
    plan = case_plan(candidate, threads=threads, threads_batch=threads_batch)
    labels = [label for label, _, _ in plan.cases]

    results = []
    for repeat in range(1, repeat_count + 1):
        for label, current, worker_count in plan.cases:
            result = run_once(
                label,
                current,
                repeat,
                worker_count,
                date=args.date,
                candidate=candidate,
                candidate_file=args.candidate_file,
                candidate_id=args.candidate_id,
                port=port,
            )
            results.append(result)
            print(
                f"{label} repeat {repeat}: startup_ms={result['startup_ms']} "
                f"work_ms={result['work_ms']} total_ms={result['total_ms']}"
            )

    found = sweep_verdict.judge(
        results,
        labels=labels,
        reference=plan.reference,
        between_cases=plan.between_cases,
    )
    summary = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "candidate": candidate,
        # Which cases ran and which one the rest are read against. A reader of
        # this artifact cannot work either out from `candidate` alone once a
        # dispatch can run more than two.
        "cases": labels,
        "reference": plan.reference,
        # The machine THIS job drew. `llama-bench` runs in a different job and the
        # platform places each separately, so the processor beside a prefill rate
        # is not the processor beside these wall-clock figures.
        "cpu": silicon.host_cpu_model() or "unrecorded",
        "repeats": repeat_count,
        # What the timing was actually taken over. It is not `repeats` whenever
        # a page moved mid-job, and a reader who assumed it was would be reading
        # a median over a denominator nobody told them about.
        "repeats_timed": len(found.comparable),
        "fixed_corpus": str(ROOT / "plan.json").replace("\\", "/"),
        "gguf_cache_hit": args.gguf_cache_hit,
        "verdict": found.verdict,
        "problems": found.problems,
        "timing": sweep_verdict.timings(found, labels=labels, reference=plan.reference),
        "results": results,
    }
    (ROOT / "runtime-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if found.verdict != sweep_verdict.PASSED:
        raise SystemExit(found.verdict)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    size = sub.add_parser("corpus-items", help="Print how many articles one repeat reads.")
    size.add_argument("--config", type=Path, default=None)
    size.add_argument(
        "--dispatch",
        default="",
        help=(
            "Overrule bench.corpus_items for this run and write it into the scratch "
            "config. Empty follows the knob."
        ),
    )

    freeze = sub.add_parser("freeze-corpus", help="Cut the day's plan to the configured size.")
    freeze.add_argument("--date", required=True)
    freeze.add_argument("--config", type=Path, default=None)
    freeze.add_argument("--offset", default="", help="Skip this many planned articles first.")

    cap = sub.add_parser(
        "corpus-cap",
        help="How many articles the plan step must produce: the slice plus what it skips.",
    )
    cap.add_argument("--config", type=Path, default=None)
    cap.add_argument("--offset", default="")

    run = sub.add_parser("sweep", help="Time the candidate against the baseline.")
    run.add_argument("--date", required=True)
    run.add_argument("--candidate", required=True)
    run.add_argument("--candidate-file", required=True)
    run.add_argument("--candidate-id", required=True)
    run.add_argument(
        "--repeats",
        default="",
        help="Overrule bench.repeats for this run. Empty follows the knob.",
    )
    run.add_argument("--threads", type=int, required=True)
    run.add_argument("--threads-batch", type=int, required=True)
    run.add_argument("--gguf-cache-hit", default="false")

    args = parser.parse_args(argv)
    if args.command == "corpus-items":
        print(corpus_items(args.config, dispatch=args.dispatch))
        return 0
    if args.command == "corpus-cap":
        # The plan has to hold the slice AND everything the slice skips, or
        # `freeze_corpus` refuses a plan that was never long enough.
        print(corpus_items(args.config) + corpus_offset(args.offset))
        return 0
    if args.command == "freeze-corpus":
        freeze_corpus(
            args.date,
            items=corpus_items(args.config),
            offset=corpus_offset(args.offset),
        )
        return 0
    return sweep(args)


if __name__ == "__main__":
    raise SystemExit(main())
