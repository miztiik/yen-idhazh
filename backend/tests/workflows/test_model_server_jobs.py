"""Does every job that starts a model server go through the one builder, and what does it record?"""

from __future__ import annotations

import csv
import os
import re
import subprocess
from pathlib import Path

import pytest
from conftest import REPO_ROOT, llama_server_flags, read_text
from pydantic import ValidationError

from idhazh import ledger
from idhazh.contracts import runtime_counters
from idhazh.llm.server import DEFAULT_ENDPOINT, DEFAULT_PORT

from ._harness import (
    CGROUP_PEAK_PATH,
    COUNTERS_COMMAND,
    COUNTERS_FIXTURE,
    COUNTERS_JOB_FLAG,
    COUNTERS_JOBS,
    COUNTERS_STEP,
    CPU_STAT_READING,
    CPU_STAT_STEP,
    LLAMA_PORT_ENV,
    LLAMA_PORT_READ,
    LLAMA_PORT_VALUE,
    LLAMA_SERVER_WORKFLOWS,
    MEMORY_PEAK_FILE,
    MEMORY_SUMMARY_STEP,
    METRICS_ENDPOINT,
    METRICS_FILE,
    METRICS_SERIES,
    PYTHON_PROCS_FIELDS,
    PYTHON_PROCS_FILE,
    RSS_SAMPLE_FIELDS,
    RSS_SAMPLE_FILE,
    RUNTIME_IDENTITY_JOBS,
    RUNTIME_IDENTITY_STEP,
    RUNTIME_LOG_CAPTURES,
    RUNTIME_LOG_LINES,
    RUNTIME_LOG_SUMMARY_STEPS,
    RUNTIME_LOG_UNCLAIMED_TAG,
    SAMPLE_MEMORY_STEP,
    SAMPLE_SCRIPT,
    SCRIPTS_DIR,
    SERVER_LOG_FILE,
    SERVER_STARTERS,
    START_SERVER_SCRIPT,
    WORKFLOWS_DIR,
    _artifact_upload,
    _bash,
    _isolated_env,
    _load_workflows,
    _mapping,
    _script,
    _server_starters,
    _starter_shell,
    _step,
    _steps,
    _strings,
    requires_bash,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]


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
    assert starters == {
        where: tuple(name for name, _ in declared) for where, declared in SERVER_STARTERS.items()
    }

    for (filename, job_name), declared in sorted(SERVER_STARTERS.items()):
        for step_name, config_root in declared:
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
    assert declaring == set(LLAMA_SERVER_WORKFLOWS), (
        "every workflow that starts a llama-server declares the port and nothing else does"
    )

    for filename in sorted(LLAMA_SERVER_WORKFLOWS):
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
        ((start_step, _),) = SERVER_STARTERS[("digest.yml", job_name)]
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

    Two jobs of the daily run used to stand a llama-server up and they served
    different weights - `work` the summarizer at Qwen3.5-9B, `visuals` the
    planner at Qwen3-4B - and both spelled shard 0 of the same run. So
    `(date, run_id, shard)` names one record and described two servers, and a
    reader pooling them reports a rate that belongs to no model. Plan 11 row #6
    retired the second job; the committed ledger still holds its rows, so the
    reader still has to tell them apart.

    Driven from a two-row fixture rather than from `state/runtime-counters.csv`,
    which a run appends to five times a day (Guardrail #12). The fixture also carries
    a case the committed ledger cannot: until row #P4 landed, every row in it came
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
    assert set(by_job) == {row["job"] for row in raw}, "the reader must separate them by job"
    assert len(by_job) == len(rows), "two rows of one job prove nothing about the column"
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


@pytest.mark.parametrize("job_name", sorted(COUNTERS_JOBS))
def test_every_counters_step_says_which_job_it_is(job_name: str) -> None:
    """A default is not a statement, and every caller has to make one.

    `--job` defaults to `work`, which is what lets a row written before the
    column existed still validate. That same default is why every step has to
    name its own value out loud: a second server job would otherwise file its
    numbers under the summarizer's name, the ledger would accept them, and the
    console would pool two models into one rate. The committed ledger already
    holds rows from the retired visuals job, which is what the column is read
    back for.
    """
    step_name = {"work": COUNTERS_STEP}[job_name]
    script = _digest_step(job_name, step_name)
    assert COUNTERS_COMMAND in script, f"{step_name} must run {COUNTERS_COMMAND}"
    assert f"{COUNTERS_JOB_FLAG} {COUNTERS_JOBS[job_name]}" in script, (
        f"{step_name} must say it is the {job_name} job"
    )
    for other, value in COUNTERS_JOBS.items():
        if other != job_name:
            assert f"{COUNTERS_JOB_FLAG} {value}" not in script


def _uncommented(text: str) -> str:
    """The lines a runner acts on, without the ones explaining why.

    A comment that says "there is no incumbent arm" is documentation worth
    keeping; an assertion that greps the whole file cannot tell it apart from
    an incumbent arm.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
