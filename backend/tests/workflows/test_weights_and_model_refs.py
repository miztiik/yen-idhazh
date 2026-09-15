"""Are the weights checked before anything reads them, and who may write a model ref?"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import cast

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from ._harness import (
    CONFIG_FILE_NAME,
    DRAFT_REF_OUTPUTS,
    LLAMA_RUNTIME_WORKFLOWS,
    MODEL_ENV_NAMES,
    MODEL_REF_FIELDS,
    MODEL_REF_OUTPUTS,
    MODELS_DOCUMENT,
    MODELS_POINTER_KEY,
    PINNED_LLAMA_BUILD,
    WEIGHTS_CACHE_ROLES,
    WEIGHTS_CACHE_SUFFIX,
    WEIGHTS_CHECKS,
    WEIGHTS_FETCH_FORM,
    WORKFLOWS_DIR,
    _committed_models,
    _config_key_paths,
    _declared_dispatch_inputs,
    _every_env,
    _expression,
    _inline_programs,
    _job,
    _load_workflows,
    _mapping,
    _names,
    _own_nodes,
    _plan_output,
    _reads_the_environment,
    _run_bodies,
    _run_the_inline_program,
    _runtime_cache_keys,
    _script,
    _step,
    _steps,
    _weights_fetch_steps,
)

pytestmark = pytest.mark.workflow


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

    assert '["summarize"]["id"]' in script, "the alias comes from config"
    assert "/v1/models" in script, "assert the served alias"
    assert "/props" in script, "assert the loaded path"
    assert _plan_output("summarize_file") in script


def test_no_arm_starts_measuring_before_it_knows_which_model_answered() -> None:
    """The Oracle. A number is about a model only if that model produced it.

    `validate.yml` has asked `/v1/models` since it was written. `measure.yml`
    waited for a 200 and started the clock, so a server answering under any
    other alias would have had its throughput filed under the candidate - which
    is a Guardrail #10 failure that no gate would have caught, because every
    number in the report would be internally consistent and wrong.

    Discovery is over every step that waits for `/health`, so an arm added later
    is held to the same rule whether or not anybody remembered it. The drift this
    catches has run in both directions: `test_model_server_jobs` records the last
    time it was `validate.yml` that nobody diffed.
    """
    for filename, workflow in sorted(_load_workflows().items()):
        for job_name in _mapping(workflow.get("jobs"), f"{filename} jobs"):
            for step in _steps(workflow, job_name):
                script = step.get("run")
                if not isinstance(script, str) or "/health" not in script:
                    continue
                where = f"{filename}/{job_name}/{step.get('name')}"
                assert "/v1/models" in script, (
                    f"{where} waits for health and never asks which model answered"
                )


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
    for name in (*MODEL_REF_OUTPUTS, *DRAFT_REF_OUTPUTS):
        assert outputs.get(name) == _expression(f"steps.models.outputs.{name}")

    step = _step(workflow, "plan", "id", "models")
    script = _script(step, "digest.yml/plan/models")
    assert "config/idhazh.json" in script, "the refs come from config"
    assert MODELS_POINTER_KEY in script, "and through the pointer, never by filename"
    assert '>> "$GITHUB_OUTPUT"' in script

    models = _committed_models()
    # The draft refs are published empty while no entry declares a draft head,
    # which is the arm that matters: a guard that refused the absent case would
    # take down every run this repository makes, and `"".split()` is `[]`
    # rather than `[""]`, so the obvious shape check does exactly that.
    assert _run_the_inline_program(script, REPO_ROOT) == {
        **{
            f"{role}_{field}": models[role][field]
            for role in set(WEIGHTS_CACHE_ROLES.values())
            for field in MODEL_REF_FIELDS
        },
        **dict.fromkeys(DRAFT_REF_OUTPUTS, ""),
    }

    # Every ref is substituted straight into a shell command downstream, so the
    # one step that writes them is where a value that is not one bare word has
    # to stop. Nothing else between config and those commands can catch it.
    pointer = "models/probe.json"
    (tmp_path / "config" / "models").mkdir(parents=True)
    models["summarize"]["file"] = "Qwen3-8B-Q4_K_M.gguf; rm -rf /"
    (tmp_path / "config" / pointer).write_text(json.dumps(models), encoding="utf-8")
    (tmp_path / "config" / "idhazh.json").write_text(
        json.dumps({MODELS_POINTER_KEY: pointer}), encoding="utf-8"
    )
    with pytest.raises(AssertionError, match=re.escape("models.summarize.file")):
        _run_the_inline_program(script, tmp_path)


def test_a_daily_run_refuses_a_draft_head_that_declares_only_half_of_itself(
    tmp_path: Path,
) -> None:
    """Four fields or none. A head with three is a file fetched against a blank.

    The guard read `if value and value.split() != [value]`, so an empty field
    passed it. An entry naming a draft `file` with no `sha256` therefore reached
    the fetch step, downloaded the head, and only then failed inside
    `sha256sum --check` on a line with nothing to check - which reports "no
    properly formatted checksum lines found" and names neither the entry nor
    the field. The two measurement arms have always used `if draft and`.

    The absent case is the one this must not break: no committed entry declares
    a head today, and a guard that refused `{}` would take down every run this
    repository makes.
    """
    script = _script(
        _step(_load_workflows()["digest.yml"], "plan", "id", "models"),
        "digest.yml/plan/models",
    )
    pointer = "models/probe.json"
    (tmp_path / "config" / "models").mkdir(parents=True)
    models = _committed_models()
    models["summarize"]["draft"] = {
        "repo": "publisher/head-GGUF",
        "revision": "8c5a9e4fd5482e2be20fe0bf013b4c262a8f4265",
        "file": "head.gguf",
        "sha256": "",
    }
    (tmp_path / "config" / pointer).write_text(json.dumps(models), encoding="utf-8")
    (tmp_path / "config" / "idhazh.json").write_text(
        json.dumps({MODELS_POINTER_KEY: pointer}), encoding="utf-8"
    )

    with pytest.raises(AssertionError, match=re.escape("models.summarize.draft.sha256")):
        _run_the_inline_program(script, tmp_path)


def test_a_candidate_is_named_by_its_models_file_and_by_nothing_else(tmp_path: Path) -> None:
    """One argument, so the two copies of a candidate's facts cannot disagree.

    A form that asked for the repository, the commit, the filename, the digest,
    the byte count, the alias and the quantisation was asking an operator to
    retype seven facts already written in the candidate's own file. Two copies
    can differ, and the failure is silent: the bench measures one set of bytes
    and the adoption points at another, with every gate green.

    The path becomes a file the step opens, so containment is proved rather than
    spelled - `..` in a form field is the whole reason this is a resolve check
    and not a name check.
    """
    committed = _committed_models()
    for filename, step_id in (("validate.yml", "candidate"), ("measure.yml", "models")):
        workflow = _load_workflows()[filename]
        declared = sorted(
            name for name in _declared_dispatch_inputs(workflow) if name.startswith("candidate")
        )
        assert declared == ["candidate_models_file"], (
            f"{filename} asks for more than the one file that already holds the answer"
        )

        script = _script(_step(workflow, "plan" if step_id == "candidate" else step_id, "id", step_id), filename)
        published = _run_the_inline_program(script, REPO_ROOT)
        for field in ("repo", "revision", "file", "id", "quantisation", "sha256"):
            key = field if filename == "validate.yml" else f"candidate_{field}"
            assert published[key] == committed["summarize"][field], (
                f"{filename} publishes a {field} the committed entry does not carry"
            )

        # A named file is read instead, and a traversal out of `config/` stops
        # here - nothing downstream opens the path again to check it.
        (tmp_path / "config" / "models").mkdir(parents=True, exist_ok=True)
        other = json.loads(json.dumps(committed))
        other["summarize"]["id"] = "some-other-model"
        (tmp_path / "config" / "models" / "other.json").write_text(
            json.dumps(other), encoding="utf-8"
        )
        (tmp_path / "config" / CONFIG_FILE_NAME).write_text(
            json.dumps({MODELS_POINTER_KEY: "models/other.json"}), encoding="utf-8"
        )
        named = _run_the_inline_program(
            script, tmp_path, {"CANDIDATE_MODELS_FILE": "models/other.json"}
        )
        assert named["id" if filename == "validate.yml" else "candidate_id"] == "some-other-model"

        with pytest.raises(AssertionError, match="under config/"):
            _run_the_inline_program(
                script, tmp_path, {"CANDIDATE_MODELS_FILE": "../../etc/passwd.json"}
            )


def test_every_config_key_a_workflow_indexes_is_in_the_committed_config() -> None:
    """A key that moved is a `KeyError` on the runner, and nothing earlier looks.

    The inline programs index the committed config by literal key. The schema
    cannot catch a stale one: the runtime sweep reads its copy as a plain dict,
    indexes it, and only validates the result afterwards, so the index raises
    first. This is the one place a renamed or moved knob is caught before a job
    spends a runner minute reaching for it.

    Two documents since 2026-09-14. A program that indexes `models_file` is
    reading the model's own file from that point on, so the key path is resolved
    against whichever of the two it really opened - resolving both against the
    pointer file would pass on a key neither carries.
    """
    documents: dict[str, object] = {
        CONFIG_FILE_NAME: json.loads(read_text(CONFIG_DIR / CONFIG_FILE_NAME)),
        MODELS_DOCUMENT: _committed_models(),
    }
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for filename, workflow in sorted(_load_workflows().items()):
        for script in _run_bodies(workflow):
            for program in _inline_programs(script):
                for document, keys in _config_key_paths(program):
                    seen.add((filename, document, keys))
                    node: object = documents[document]
                    for depth, key in enumerate(keys):
                        assert isinstance(node, dict) and key in node, (
                            f"{filename} indexes the {document} document at "
                            f"{'.'.join(keys)}, and there is no "
                            f"{'.'.join(keys[: depth + 1])}"
                        )
                        node = cast(dict[str, object], node)[key]

    # The sweep rewrites its own copy of the config, which is the read that went
    # stale. Naming it keeps this test from passing by finding nothing, and it
    # names a path in EACH document so neither half can go quiet on its own.
    assert ("measure.yml", MODELS_DOCUMENT, ("summarize", "inference")) in seen
    assert ("digest.yml", CONFIG_FILE_NAME, (MODELS_POINTER_KEY,)) in seen


def test_no_inline_program_rebinds_a_name_it_read_from_the_environment() -> None:
    """A dispatch input read into a name and then written over is silently ignored.

    `measure.yml` did exactly this: `CANDIDATE` was the runtime sweep's choice
    from `RUNTIME_CANDIDATE`, and four lines later the same name was rebound to
    the candidate config directory. Every later reader got the path, so a
    dispatch of the incumbent died on `unknown runtime candidate:
    backend/var/candidate-config` after paying for the weights download.

    **A rebind that consults the value it replaces is a fallback, not a
    collision** - `value = value or configured.get(field)` is how the same file
    lets config stand in for an absent input, and that is correct. What is
    banned is a second assignment that ignores what the first one read.
    """
    shadowed: list[str] = []
    for filename, workflow in sorted(_load_workflows().items()):
        for script in _run_bodies(workflow):
            for program in _inline_programs(script):
                tree = ast.parse(program)
                for scope in [tree, *(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))]:
                    from_environment: dict[str, int] = {}
                    assignments = sorted(
                        (n for n in _own_nodes(scope) if isinstance(n, ast.Assign)),
                        key=lambda n: n.lineno,
                    )
                    for node in assignments:
                        if len(node.targets) != 1:
                            continue
                        target = node.targets[0]
                        if not isinstance(target, ast.Name):
                            continue
                        if _reads_the_environment(node.value):
                            from_environment[target.id] = node.lineno
                        elif target.id in from_environment and not _names(node.value, target.id):
                            shadowed.append(
                                f"{filename}: {target.id} is read from the environment at "
                                f"line {from_environment[target.id]} of its inline program and "
                                f"written over at line {node.lineno} without reading it"
                            )

    assert not shadowed, "\n".join(shadowed)


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

    models = _committed_models()
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

    assert len(set(keys.values())) == len(keys), "one entry cannot hold two sets of weights"


#: Where each bench-side workflow decides what the candidate is: the step that
#: reads the entry, and the prefix it puts on what it publishes.
CANDIDATE_STEPS = (
    ("measure.yml", "models", "models", "candidate_"),
    ("validate.yml", "plan", "candidate", ""),
)


def _an_entry(**extra: object) -> dict[str, object]:
    """A summarize entry carrying everything the step requires, plus what a test adds."""
    return {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "model-Q4_K_M.gguf",
        "sha256": "a" * 64,
        "id": "model-q4-k-m",
        "quantisation": "Q4_K_M",
        **extra,
    }


def _a_config_tree(tmp_path: Path, summarize: dict[str, object]) -> Path:
    """One models file, built rather than borrowed.

    The committed tree has one entry with a draft head and two without, so a
    test driven from it could only ever ask what today's config happens to say -
    and it would go quiet on the day somebody retired the entry it relied on.
    """
    models = tmp_path / "config" / "models"
    models.mkdir(parents=True)
    (tmp_path / "config" / "idhazh.json").write_text(
        json.dumps({"models_file": "models/candidate.json"}) + "\n", encoding="utf-8"
    )
    (models / "candidate.json").write_text(
        json.dumps({"summarize": summarize}) + "\n", encoding="utf-8"
    )
    return tmp_path


def _candidate_outputs(
    filename: str, job_name: str, step_id: str, tmp_path: Path, summarize: dict[str, object]
) -> dict[str, str]:
    step = _step(_load_workflows()[filename], job_name, "id", step_id)
    return _run_the_inline_program(
        _script(step, f"{filename}/{job_name}/{step_id}"),
        _a_config_tree(tmp_path, summarize),
        {"CANDIDATE_MODELS_FILE": ""},
    )


@pytest.mark.parametrize(("filename", "job_name", "step_id", "prefix"), CANDIDATE_STEPS)
def test_a_declared_draft_head_is_published_and_named_in_the_cache_key(
    filename: str, job_name: str, step_id: str, prefix: str, tmp_path: Path
) -> None:
    """The cache holds every file the candidate needs, so the key names every digest.

    A key that named only the target served a complete-looking entry with the
    draft head missing, and llama-server exits at load rather than at fetch - so
    the arm that restored it spent a runner hour and measured nothing.
    """
    draft = {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "mtp-model.gguf",
        "sha256": "b" * 64,
    }
    published = _candidate_outputs(
        filename, job_name, step_id, tmp_path, _an_entry(draft=draft)
    )

    for field, value in draft.items():
        assert published[f"{prefix}draft_{field}"] == value

    key = published[f"{prefix}cache_key" if prefix else "cache_key"]
    assert key == f"{'a' * 64}-{'b' * 64}", "the key must name both digests"


@pytest.mark.parametrize(("filename", "job_name", "step_id", "prefix"), CANDIDATE_STEPS)
def test_an_entry_with_no_draft_head_keeps_the_key_it_already_had(
    filename: str, job_name: str, step_id: str, prefix: str, tmp_path: Path
) -> None:
    """Adding the draft to the key must not throw away what earlier runs downloaded.

    Two of three committed entries declare no draft head. If their key moved,
    the next dispatch for each would refetch several gigabytes to land on bytes
    it already had.
    """
    published = _candidate_outputs(filename, job_name, step_id, tmp_path, _an_entry())

    for field in ("repo", "revision", "file", "sha256"):
        assert published[f"{prefix}draft_{field}"] == ""

    key = published[f"{prefix}cache_key" if prefix else "cache_key"]
    assert key == "a" * 64, "an entry with no draft keeps the target digest alone"


@pytest.mark.parametrize(("filename", "job_name", "step_id", "prefix"), CANDIDATE_STEPS)
def test_a_draft_head_that_declares_no_digest_is_refused(
    filename: str, job_name: str, step_id: str, prefix: str, tmp_path: Path
) -> None:
    """A head with no digest would be downloaded unchecked, which is the one thing we never do."""
    entry = _an_entry(draft={"repo": "p/M", "revision": "0" * 40, "file": "mtp.gguf"})

    with pytest.raises(AssertionError, match=r"draft\.sha256"):
        _candidate_outputs(filename, job_name, step_id, tmp_path, entry)
