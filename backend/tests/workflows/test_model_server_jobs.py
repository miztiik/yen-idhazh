"""Does every job that starts a model server go through the one builder, and what does it record?"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, llama_server_flags, read_text

from idhazh.llm.server import DEFAULT_ENDPOINT, DEFAULT_PORT
from idhazh.telemetry import silicon
from utilities import candidate_pointer, model_refs, pipeline_case_config

from ._harness import (
    ACTIONS_DIR,
    ARGV_MODULE_CALL,
    COUNTERS_FLAG,
    JOB_CLOCK_STEP,
    LLAMA_PORT_ENV,
    LLAMA_PORT_READ,
    LLAMA_PORT_VALUE,
    MEMORY_SUMMARY_STEP,
    METRICS_ENDPOINT,
    METRICS_FILE,
    METRICS_SERIES,
    MODEL_SERVER_ACTION,
    MODEL_SERVER_STEPS,
    PYTHON_PROCS_FILE,
    RSS_SAMPLE_FILE,
    RUNTIME_IDENTITY_JOBS,
    RUNTIME_IDENTITY_STEP,
    SAMPLE_MEMORY_STEP,
    SAMPLER_START_CALL,
    SAMPLER_SUMMARY_CALL,
    SCRAPE_STEP,
    SCRIPTS_DIR,
    SERVER_LOG_FILE,
    SERVER_STARTER_MODULES,
    START_SERVER_MODULE,
    WORKFLOWS_DIR,
    _action_call,
    _artifact_upload,
    _bash,
    _declared_steps,
    _isolated_env,
    _load_workflows,
    _local_action_inputs,
    _mapping,
    _model_server_callers,
    _published,
    _script,
    _server_starters,
    _starter_shell,
    _step,
    _steps,
    _strings,
    requires_bash,
)

pytestmark = pytest.mark.workflow

#: The step that prints what it found in llama-server's own log, and how much of
#: the log that was.
LOG_SUMMARY_STEP: Final = "Prompt cache log summary"

#: Every place a server is started, and the config root that start reads its
#: flags from. Five roots and three shapes: the committed tree, the scratch copy
#: the candidate action cuts, and the per-case copies cut from that one.
LAUNCH_ROOTS: Final = (
    ("digest.yml", "work", "Start the model", "config"),
    ("validate.yml", "qualify", "Start the candidate", "backend/var/candidate-config"),
    (
        "idhazh-pipeline-tests.yaml",
        "cases",
        "Start the model",
        "backend/var/cases/baseline/config",
    ),
    (
        "idhazh-pipeline-tests.yaml",
        "cases",
        "Restart the model with two slots",
        "backend/var/cases/parallel-2/config",
    ),
    ("measure.yml", "budgets", "Start the tokenizer", "backend/var/candidate-config"),
)

#: The variable those five steps used to be handed the model path in. Named
#: so it cannot come back: the config root already says which file.
MODEL_PATH_ENV: Final = "MODEL_PATH"


def test_every_job_that_starts_a_server_reaches_the_one_argv_builder() -> None:
    """The Oracle. One function spells a llama-server flag and everything reaches it.

    `backend/utilities/llama_server_argv.py` was a second copy of that list. It
    existed for one reason: `digest.yml` started its server before
    `pip install -e .` ran, so the package was not importable yet. The install
    moved one step earlier and the copy went. While it existed the two halves
    drifted, and the case that drifted was the one nobody diffed - `validate.yml`
    qualified a candidate on a server the daily run does not run.

    The install ordering is the whole reason, so it is asserted here rather than
    left as a comment: a job that installs after it starts is a job that needs a
    second copy again.
    """
    workflows = _load_workflows()
    starters = _server_starters(workflows)
    assert starters, "no job starts a server, so this is checking nothing"

    # The runtime case starts a server from a module rather than a heredoc, so
    # the Oracle follows it there. The rule is unchanged: one function spells a
    # llama-server flag, and a second spelling anywhere is the defect.
    for relative in SERVER_STARTER_MODULES:
        source = read_text(REPO_ROOT / relative)
        assert re.search(r"^\s*from idhazh\.llm\.server import .*\bserver_argv\b", source, re.M), (
            relative
        )

    for (filename, job_name), declared in sorted(starters.items()):
        for step_name in declared:
            where = f"{filename}/{job_name}/{step_name}"
            names = [step.get("name") for step in _steps(workflows[filename], job_name)]
            assert "Install" in names, f"{where} must install the package it imports"
            assert names.index("Install") < names.index(step_name), (
                f"{where} imports idhazh, so the install runs first"
            )

            script = _starter_shell(_step(workflows[filename], job_name, "name", step_name))
            assert ARGV_MODULE_CALL in script, where
            assert "--config-root " in script, f"{where} names no config root"
            # No weights argument. The config root's own entry names the file,
            # and a second way of saying which bytes is a second answer.
            assert "--weights" not in script, f"{where} is told its weights twice"

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


def test_the_model_block_is_one_action_with_a_contract_its_callers_can_read() -> None:
    """The Oracle for the extraction. One copy of the five steps, and a stated contract.

    `digest.yml`'s work shard and `llm-council.yml`'s judging shard ran the same
    cache, fetch, digest check, start and health probe as two copies, and the
    copies had already drifted: the daily run put the weights revision into its
    cache key and the other file got the same edit by hand afterwards. An action
    only removes that if nothing may go round it, so the caller set is
    closed-world and a caller that spells one of the five names again fails here.

    `idhazh-pipeline-tests.yaml` spells four of them and is left alone on
    purpose: it serves a candidate rather than the configured model, and it
    restarts the server inside the job to move a slot count. A shared block that
    took those two as parameters would be the duplication wearing one name.

    An action is a contract, so the contract is asserted rather than described.
    Every input carries a description, every optional one carries a default, and
    the declared set and the read set are compared both ways - an input nobody
    reads is a promise the action does not keep, and a `${{ inputs.x }}` nobody
    declared resolves to the empty string with no error at all, which is how a
    cache key silently loses a half.

    The action knows nothing about who called it, so the block can be built and
    tested without either caller being in the room.
    """
    workflows = _load_workflows()
    calling = _model_server_callers(workflows)
    assert calling, "no job calls the model-server action, so this is checking nothing"

    for filename, job_name in sorted(calling):
        spelled = [
            str(step.get("name"))
            for step in _declared_steps(workflows[filename], job_name)
            if step.get("name") in MODEL_SERVER_STEPS
        ]
        assert not spelled, f"{filename}/{job_name} owns a second copy of {spelled}"

    declared = _local_action_inputs(MODEL_SERVER_ACTION)
    for name, body in sorted(declared.items()):
        description = body.get("description")
        assert isinstance(description, str) and description.strip(), f"{name} has no description"
        if body.get("required") == "true":
            assert "default" not in body, f"{name} is required and cannot have a default"
        else:
            assert "default" in body, f"{name} is optional and names no default"

    text = read_text(ACTIONS_DIR / MODEL_SERVER_ACTION.rsplit("/", 1)[-1] / "action.yml")
    read = set(re.findall(r"\$\{\{\s*inputs\.([a-z_0-9]+)\s*\}\}", text))
    assert read == set(declared), f"declared {sorted(declared)} and read {sorted(read)}"

    for filename, job_name in sorted(calling):
        given = _action_call(workflows[filename], job_name, MODEL_SERVER_ACTION)
        required = {name for name, body in declared.items() if body.get("required") == "true"}
        # Required in, declared out. An optional input carries a default, so a
        # caller that leaves it out is taking that default - and forcing every
        # caller to spell it would be the default written twice.
        assert required <= set(given), (
            f"{filename}/{job_name} never passes {sorted(required - set(given))}"
        )
        assert set(given) <= set(declared), (
            f"{filename}/{job_name} hands over {sorted(set(given) - set(declared))}, "
            "which resolves to nothing"
        )
        names = [
            str(step.get("name") or step.get("uses") or "")
            for step in _declared_steps(workflows[filename], job_name)
        ]
        # A `./` action is this repository at the commit the run checked out, so
        # a job that calls one before checking out has nothing to call.
        assert names.index("actions/checkout@v6") < names.index(MODEL_SERVER_ACTION), (
            f"{filename}/{job_name} calls the action before it has the tree"
        )

    # The role is `models.summarize` and no caller chooses it, which is why the
    # two can share one cache entry - so naming it is correct. Naming a CALLER
    # is not: a block that knows who called it is a block one caller cannot be
    # built or tested without.
    for caller in ("judg", "council", "digest.yml"):
        assert caller not in text.lower(), f"the action names its caller: {caller}"


@requires_bash


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "required: verb"),
        (["summarize"], "invalid choice"),
        (["start-server", "--role", "gibberish"], "unrecognized arguments"),
    ],
)


def test_the_launcher_refuses_a_call_it_cannot_serve(
    argv: list[str], message: str, tmp_path: Path
) -> None:
    """Run it, do not read it.

    Five call sites hand this program a verb and a config root. A typo in either
    used to be impossible, because the shell was written out per job; now it is
    one string in a workflow, so the program says no rather than starting a
    server for the wrong model or writing a log nobody later reads.

    `--role` is one of the two arguments this row deleted. One role exists, the
    builder already defaults to it, and the old script carried a `case` block
    refusing a value nothing could produce - so a call that still passes it is
    a caller that was never converted.
    """
    completed = subprocess.run(
        [sys.executable, str(START_SERVER_MODULE), *argv],
        cwd=tmp_path,
        env={**_isolated_env(tmp_path), "LLAMA_PORT": "8080"},
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


def _run_work_step(name: str, tmp_path: Path) -> str:
    """Run one step of the work job for real, in a directory holding its inputs."""
    shell = _bash()
    assert shell is not None
    body = _script(_step(_load_workflows()["digest.yml"], "work", "name", name), name)
    completed = subprocess.run(
        [shell, "-c", body],
        cwd=tmp_path,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout + completed.stderr


@requires_bash


def test_the_log_summary_says_how_much_of_the_log_it_matched(tmp_path: Path) -> None:
    """The count that would have caught a pattern matching one line in forty.

    `^(srv|slot) ` matched nothing and had never matched anything: every line
    llama-server prints opens with a timestamp and a level letter, so the tag is
    the third field. The step still printed on every run, because the
    `n_ctx_slot` alternative beside it does match - which is why nobody noticed
    the other half was dead.

    A fixture of captured logs checked our pattern against a build we had
    already run. The count checks it against the build the run is on, every run,
    and says so the day llama.cpp renames a field.
    """
    matching = (
        "0.03.804.331 I srv    load_model: initializing, n_slots = 1, "
        "n_ctx_slot = 8192, kv_unified = 'false'",
        "3.09.738.586 I slot get_availabl: id  0 | task -1 | selected slot by LCP "
        "similarity, f_sim_best = 0.926 (> 0.100 thold), f_keep = 0.782",
    )
    unmatched = "0.00.061.210 I cmn    common_init_from_params: setting dry_penalty_last_n"
    (tmp_path / SERVER_LOG_FILE).write_text(
        "\n".join([*matching, unmatched]) + "\n", encoding="utf-8"
    )

    printed = _run_work_step(LOG_SUMMARY_STEP, tmp_path)

    assert f"matched {len(matching)} of 3" in printed, printed
    for line in matching:
        assert line in printed, f"the step would not print {line!r}"


def test_the_work_job_launches_the_sampler_detached_and_names_the_loop() -> None:
    """One step writes a pid and the next samples it, and nothing backgrounds anything.

    The sampler was a heredoc until 2026-09-12, a shell script until 2026-09-23,
    and is a module now. What this has protected across all three is the same
    agreement: the job hands the sampler the pid file its own start step wrote,
    so a copy-paste that left another job's name here would sample a process
    that never existed and record nothing, silently.

    It used to assert the literal `nohup`, and neither half of that survives.
    The program launches the loop into its own session itself, which is strictly
    more detached than `nohup`. What must not come back is the `&` that went
    with it: the shell recorded `$!`, the pid of the backgrounded *shell* rather
    than of the sampler, so a loop that died at once left a pid file naming a
    live shell and a step that passed.
    """
    script = _work_step(SAMPLE_MEMORY_STEP)

    assert SAMPLER_START_CALL in script, "the work job must launch the shared sampler"
    assert "cat llama-server.pid" in script, (
        "the work job must sample the server its own start step wrote"
    )
    assert not script.rstrip().endswith("&"), (
        "the sampler detaches itself, so a step that backgrounds it again records "
        "the shell's pid rather than the loop's"
    )
    assert "nohup" not in script, "nohup is what the launch shape replaced"


def test_the_memory_summary_reads_what_the_sampler_wrote() -> None:
    """One writer, one reader, and both files reach the artifact.

    The operator print was an `awk` program inside the step, reading a
    tab-separated file whose columns it named. It and the sampler agreed through
    a third copy of the column order written down in this file rather than with
    each other, which is how the step once reported `python_procs` - a count of
    three - as a peak in kilobytes, out by six orders of magnitude with nothing
    failing anywhere.

    The summary is a verb on the module that wrote the records now, so there is
    no second reader to disagree with and no column position left to get wrong.
    What a workflow test still owes is that the step calls it, and that the
    roll-call behind the sum can be downloaded: a roll-call nobody can fetch
    answers nothing.
    """
    operator = _work_step(MEMORY_SUMMARY_STEP)
    assert SAMPLER_SUMMARY_CALL in operator, (
        f"{MEMORY_SUMMARY_STEP} must read the records through the module that wrote them"
    )

    upload = _artifact_upload(
        _load_workflows()["digest.yml"], "work", "runtime-log-${{ matrix.shard }}"
    )
    uploaded = str(_mapping(upload.get("with"), "runtime log upload").get("path"))
    for name in (RSS_SAMPLE_FILE, PYTHON_PROCS_FILE):
        assert name in uploaded, f"{name} is written every sample and never uploaded"


def test_the_loopback_port_is_one_number_wherever_it_is_written() -> None:
    """A server on one port and a stage posting to another is every item failing.

    Every workflow that stands a llama-server up declares the port once at
    workflow level, the shared launcher reads it back from the environment, and
    `idhazh.llm.server` builds the address the stage posts to out of the same
    variable. Until 2026-09-09 the measurement harness was a fifth party: it
    starts its server from an inline python block rather than through the shared
    launcher, and it held its own `SERVER_PORT = 8080`. It reads the variable
    now, so the number is declared and never spelled.

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
    assert declaring, "no workflow declares the port, so this is checking nothing"

    for filename in sorted(declaring):
        for line in read_text(WORKFLOWS_DIR / filename).splitlines():
            if re.search(rf"\b{LLAMA_PORT_VALUE}\b", line):
                assert LLAMA_PORT_ENV in line, (
                    f"{filename} spells the port at `{line.strip()}` rather than "
                    f"reading {LLAMA_PORT_ENV} back"
                )

    assert f'PORT_ENV: Final = "{LLAMA_PORT_ENV}"' in read_text(START_SERVER_MODULE), (
        f"{START_SERVER_MODULE.name} must read {LLAMA_PORT_ENV} rather than hold a port"
    )
    # The one starter that does not go through the shared launcher. It sweeps a
    # setting over per-candidate config roots and holds the process object to
    # sample its memory, neither of which the launcher can do - so it keeps its
    # own start sequence and reads the port the workflow declared. It moved out
    # of `measure.yml` into a module on 2026-09-15; the rule did not move with it.
    assert f'PORT_ENV = "{LLAMA_PORT_ENV}"' in read_text(
        REPO_ROOT / "backend" / "utilities" / "runtime_sweep.py"
    ), f"the measurement harness must read {LLAMA_PORT_ENV} rather than hold a port"


def _launched_stem(script: str) -> str:
    """The log and pid stem a start call leaves behind, named or defaulted.

    A step that names none takes the launcher's own default, so the default is
    read out of the program rather than retyped here - otherwise this test would
    hold one answer and the runner another.
    """
    named = re.search(r"--name\s+(\S+)", script)
    if named:
        return named.group(1)
    default = re.search(r'"--name",\s*\n\s*default="([^"]+)"', read_text(START_SERVER_MODULE))
    assert default, f"{START_SERVER_MODULE.name} names no default log stem"
    return default.group(1)


def test_every_reader_of_a_server_log_reads_the_one_the_start_call_wrote() -> None:
    """One name, decided once at the start call, read by five later steps.

    The launcher writes `<name>.log` and `<name>.pid`, so the stem exists in the
    workflow once - as an argument or as the program's own default - and four
    more times as a literal in steps that read it. Every one of those readers
    ends `|| true` or `if: always()`, so a stem that no longer matches costs the
    job its runtime identity, its failure tail and its whole prompt-cache
    summary, and fails nothing.
    """
    workflow = _load_workflows()["digest.yml"]
    starters = _server_starters({"digest.yml": workflow})
    assert set(RUNTIME_IDENTITY_JOBS) <= set(_mapping(workflow.get("jobs"), "jobs")), (
        "a job named here no longer exists in digest.yml"
    )
    for job_name, (log_file, weights_output) in sorted(RUNTIME_IDENTITY_JOBS.items()):
        ((start_step,)) = starters[("digest.yml", job_name)]
        script = _script(_step(workflow, job_name, "name", start_step), start_step)
        assert ARGV_MODULE_CALL in script, f"{job_name} must start through the shared launcher"
        stem = _launched_stem(script)
        assert f"{stem}.log" == log_file, (
            f"{job_name} starts a server logging to {stem}.log and its readers read {log_file}"
        )

        identity = _digest_step(job_name, RUNTIME_IDENTITY_STEP)
        assert log_file in identity, f"{RUNTIME_IDENTITY_STEP} in {job_name} must read {log_file}"
        given = _mapping(
            _step(workflow, job_name, "name", RUNTIME_IDENTITY_STEP).get("env"),
            f"{RUNTIME_IDENTITY_STEP} env",
        )
        assert any(weights_output in str(value) for value in given.values()), (
            f"{RUNTIME_IDENTITY_STEP} in {job_name} must name the weights it ran"
        )
        assert "sha256sum backend/bin/llama-server" in identity, (
            f"{RUNTIME_IDENTITY_STEP} in {job_name} must name the binary it ran"
        )

        assert SERVER_LOG_FILE == log_file, (
            f"{LOG_SUMMARY_STEP} reads {SERVER_LOG_FILE} and {job_name} writes {log_file}"
        )
        assert log_file in _digest_step(job_name, LOG_SUMMARY_STEP), (
            f"{LOG_SUMMARY_STEP} must read {log_file}"
        )


def test_the_scrape_step_and_the_row_agree_on_what_it_reads() -> None:
    """Two readings of one file, taken in two steps, and a third in another language.

    The metrics body is written by one line of the scrape step and read by two
    more - the step's own grep and the job-clock step after it - so a rename in
    any one of them leaves the host row's counter cells empty and prints nothing
    that says why. The two series are named again in the module that parses
    them, in Python, and llama.cpp has renamed a counter before.
    """
    scrape = _work_step(SCRAPE_STEP)
    assert f"-o {METRICS_FILE}" in scrape, f"{SCRAPE_STEP} must write {METRICS_FILE}"
    assert f'"{METRICS_ENDPOINT}"' in scrape, f"{SCRAPE_STEP} must scrape {METRICS_ENDPOINT}"
    for series in METRICS_SERIES:
        assert series in scrape, f"{SCRAPE_STEP} stopped naming {series}"

    clock = _work_step(JOB_CLOCK_STEP)
    assert f"{COUNTERS_FLAG} {METRICS_FILE}" in clock, "the stage must read the file curl wrote"
    assert f"--server-log {SERVER_LOG_FILE}" in clock, "and the log the server wrote beside it"
    for wire in silicon._SERIES:
        assert wire in scrape, f"{SCRAPE_STEP} no longer names {wire}, which the host row parses"


def _uncommented(text: str) -> str:
    """The lines a runner acts on, without the ones explaining why.

    A comment that says "there is no incumbent case" is documentation worth
    keeping; an assertion that greps the whole file cannot tell it apart from
    an incumbent case.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _the_five_roots(tmp_path: Path) -> dict[str, Path]:
    """The five config roots a server is started from, built the way the jobs build them.

    Three of the five do not exist in this repository at all: a job cuts them at
    run time, one from `config/` and two from that copy. Reading them off disk
    would check nothing, so the real builders are driven here instead - which is
    also what makes a builder that starts moving the weights file turn this red.
    """
    committed = CONFIG_DIR
    scratch = tmp_path / "candidate-config"
    shutil.copytree(committed, scratch)
    pointer = _published(model_refs.trial_rows(committed, "", prefix=""))["models_file"]
    candidate_pointer.point_at(pointer, scratch=scratch)

    cases = tmp_path / "cases"
    pipeline_case_config.main(["--config-root", str(scratch), "--cases-root", str(cases)])

    return {
        "config": committed,
        "backend/var/candidate-config": scratch,
        "backend/var/cases/baseline/config": cases / "baseline" / "config",
        "backend/var/cases/parallel-2/config": cases / "parallel-2" / "config",
    }


def test_the_weights_path_a_launcher_derives_is_the_one_the_download_wrote(
    tmp_path: Path,
) -> None:
    """A path composed twice can differ; composed once from the root the flags come from, it cannot.

    Every one of these five steps used to be handed the weights path as text,
    through five expression hops from a job output, while reading its flags from
    a config root whose own entry already named the file. Two answers to one
    question, and the second one travelled.

    What remains is the property that made deleting the first one safe: the root
    each step names declares the same file the download fetched. A builder that
    starts moving the weights file turns this red before a server starts against
    bytes nobody downloaded.
    """
    workflows = _load_workflows()
    roots = _the_five_roots(tmp_path)
    landed = _published(model_refs.pinned_rows(CONFIG_DIR))["summarize_weights_path"]

    for filename, job_name, step_name, root_name in LAUNCH_ROOTS:
        where = f"{filename}/{job_name}/{step_name}"
        step = _step(workflows[filename], job_name, "name", step_name)
        shell = _starter_shell(step)
        assert ARGV_MODULE_CALL in shell, f"{where} starts a server some other way"
        assert root_name in shell or root_name in str(
            _mapping(step.get("env"), f"{where} env").values()
        ), f"{where} reads its flags from some root other than {root_name}"
        assert MODEL_PATH_ENV not in shell, f"{where} is still told which model file to open"

        derived = model_refs.list_model_files(roots[root_name])[0].landed_path
        assert derived == landed, (
            f"{root_name} declares {derived} and the download wrote {landed}"
        )
